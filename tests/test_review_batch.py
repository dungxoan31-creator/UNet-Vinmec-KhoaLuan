import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")


@pytest.fixture
def auth_tokens():
    from backend.app.routers.auth import create_access_token
    doc_token = create_access_token({"sub": "doctor"})
    admin_token = create_access_token({"sub": "admin"})
    other_doc_token = create_access_token({"sub": "bacsi"})
    return {
        "doctor": {"Authorization": f"Bearer {doc_token}"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
        "other_doctor": {"Authorization": f"Bearer {other_doc_token}"},
    }


@pytest.fixture
def bilateral_case():
    from backend.db import database
    db = next(database.get_db())
    try:
        patient = database.PatientModel(
            id=str(uuid.uuid4()),
            anonymized_pid=f"TEST_BATCH_{uuid.uuid4().hex[:6]}",
        )
        db.add(patient)
        study = database.StudyModel(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            study_code="BATCH_STUDY_1",
            study_date="2026-10-16",
            status="ANALYZED",
            ovary_side="BOTH",
            review_revision=0,
        )
        db.add(study)

        empty_mask = {"shape": [512, 512], "first_val": 0, "counts": [262144]}
        ai_mask = {"shape": [512, 512], "first_val": 0, "counts": [1000, 200, 260944]}

        img_l = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="left_ovary.png",
            laterality="L",
            raw_path="nonexistent_l.png",
            width=640,
            height=480,
        )
        img_r = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="right_ovary.png",
            laterality="R",
            raw_path="nonexistent_r.png",
            width=640,
            height=480,
        )
        db.add_all([img_l, img_r])

        pred_l = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img_l.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle=ai_mask,
            measurements={},
        )
        pred_r = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img_r.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle=ai_mask,
            measurements={},
        )
        db.add_all([pred_l, pred_r])
        db.commit()

        return {
            "study_id": study.id,
            "img_l_id": img_l.id,
            "img_r_id": img_r.id,
            "pred_l_id": pred_l.id,
            "pred_r_id": pred_r.id,
            "ai_mask": ai_mask,
            "empty_mask": empty_mask,
        }
    finally:
        db.close()


def test_reject_non_doctor_403(auth_tokens, bilateral_case):
    from backend.app.main import app
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    # Admin is not DOCTOR -> 403
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["admin"])
    assert resp.status_code == 403


def test_action_mismatch_422(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    # Action ACCEPTED_RAW but mask is empty -> mismatch -> 422
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["empty_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


@pytest.mark.parametrize("side", ["LEFT", "BOTH"])
def test_partial_review_never_marks_case_complete_with_unreviewed_image(
    auth_tokens, bilateral_case, active_case_lease, side
):
    from backend.app.main import app
    from backend.db import database

    with Session(database.engine) as db:
        study = db.get(database.StudyModel, bilateral_case["study_id"])
        study.ovary_side = side
        if side == "LEFT":
            db.get(database.ImageModel, bilateral_case["img_r_id"]).laterality = "L"
        else:
            extra = database.ImageModel(id=str(uuid.uuid4()), study_id=study.id,
                                        filename="extra.png", raw_path="missing.png", laterality="L")
            db.add(extra)
        db.commit()
    with TestClient(app) as client:
        lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
        count = 1 if side == "LEFT" else 2
        for index, suffix in enumerate(("l", "r")[:count]):
            payload = {
                "study_id": bilateral_case["study_id"],
                "image_id": bilateral_case[f"img_{suffix}_id"],
                "prediction_id": bilateral_case[f"pred_{suffix}_id"],
                "verified_mask_rle": bilateral_case["ai_mask"],
                "expected_revision": index,
                "request_id": str(uuid.uuid4()),
                **lease,
            }
            response = client.post("/api/review", json=payload, headers=auth_tokens["doctor"])
            assert response.status_code == 200, response.text
    with Session(database.engine) as db:
        assert db.get(database.StudyModel, bilateral_case["study_id"]).status == "PARTIALLY_REVIEWED"
    if side == "LEFT":
        with TestClient(app) as client:
            final = client.post("/api/review", headers=auth_tokens["doctor"], json={
                "study_id": bilateral_case["study_id"], "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"], "verified_mask_rle": bilateral_case["ai_mask"],
                "expected_revision": 1, "request_id": str(uuid.uuid4()), **lease,
            })
            assert final.status_code == 200, final.text
        with Session(database.engine) as db:
            assert db.get(database.StudyModel, bilateral_case["study_id"]).status == "REVIEWED"


def test_unilateral_batch_requires_all_images(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    from backend.db import database
    with Session(database.engine) as db:
        study = db.get(database.StudyModel, bilateral_case["study_id"])
        study.ovary_side = "LEFT"
        db.get(database.ImageModel, bilateral_case["img_r_id"]).laterality = "L"
        db.commit()
    with TestClient(app) as client:
        lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
        payload = {
            "study_id": bilateral_case["study_id"], "expected_revision": 0,
            "request_id": str(uuid.uuid4()), **lease,
            "reviews": [{"image_id": bilateral_case["img_l_id"],
                         "prediction_id": bilateral_case["pred_l_id"],
                         "verified_mask_rle": bilateral_case["ai_mask"]}],
        }
        response = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
        assert response.status_code == 422
    with Session(database.engine) as db:
        assert db.get(database.StudyModel, bilateral_case["study_id"]).review_revision == 0


def test_modified_empty_mask_rejected_atomically(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    client = TestClient(app)
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        "reviews": [
            {"image_id": bilateral_case["img_l_id"], "prediction_id": bilateral_case["pred_l_id"],
             "doctor_action": "MODIFIED", "verified_mask_rle": bilateral_case["empty_mask"]},
            {"image_id": bilateral_case["img_r_id"], "prediction_id": bilateral_case["pred_r_id"],
             "doctor_action": "ACCEPTED_RAW", "verified_mask_rle": bilateral_case["ai_mask"]},
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    response = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert response.status_code == 422


def test_foreign_prediction_422(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    # pred_r used for img_l -> foreign prediction -> 422
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


def test_stale_version_409(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    # study has review_revision=0, expected_revision=5 -> 409
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 5,
        "request_id": req_id,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 409


def test_rollback_on_second_image_failure(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    from backend.db import database
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    # Second review has foreign prediction -> second review will fail
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": "nonexistent-pred-id",
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code in (404, 422)

    # Verify that image L was NOT saved to reviews (clean rollback!)
    db = next(database.get_db())
    try:
        revs = db.query(database.ReviewModel).filter(database.ReviewModel.image_id == bilateral_case["img_l_id"]).all()
        assert len(revs) == 0, f"Expected 0 reviews due to transaction rollback, found {len(revs)}"
        study = db.query(database.StudyModel).filter(database.StudyModel.id == bilateral_case["study_id"]).one()
        assert study.review_revision == 0
    finally:
        db.close()


def test_atomic_success_and_idempotent_retry(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    from backend.db import database
    client = TestClient(app)
    req_id = str(uuid.uuid4())
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "telemetry_tasks": [{"task_id": "task-left", "last_seq": 2}],
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
                "clinical_notes": "Note L",
                "clinician_overrides": {"lesion_type": "simple_cyst"},
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
                "clinical_notes": "Note R",
            },
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))

    # 1. First execution -> SUCCESS
    resp1 = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()
    assert data1["status"] == "SUCCESS"
    assert data1["review_revision"] == 1
    assert len(data1["reviews"]) == 2

    # Check database state
    db = next(database.get_db())
    try:
        study = db.query(database.StudyModel).filter(database.StudyModel.id == bilateral_case["study_id"]).one()
        assert study.review_revision == 1
        assert study.status == "REVIEWED"
        revs = db.query(database.ReviewModel).filter(database.ReviewModel.image_id.in_([bilateral_case["img_l_id"], bilateral_case["img_r_id"]])).all()
        assert len(revs) == 2
        for rev in revs:
            assert rev.is_official_ground_truth is False
        queue = db.query(database.ActiveLearningQueueModel).one()
        assert queue.study_id == bilateral_case["study_id"]
        assert queue.image_id == bilateral_case["img_l_id"]
        assert queue.sample["clinician_overrides"] == {"lesion_type": "simple_cyst"}
        left_review = db.query(database.ReviewModel).filter_by(
            image_id=bilateral_case["img_l_id"]
        ).one()
        assert left_review.hitl_feedback["clinician_overrides"] == {
            "lesion_type": "simple_cyst"
        }
    finally:
        db.close()

    # 2. Idempotent replay: exact same payload and request_id -> returns same 200 and same review IDs
    resp2 = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2 == data1

    altered_override = dict(payload)
    altered_override["reviews"] = [dict(review) for review in payload["reviews"]]
    altered_override["reviews"][0]["clinician_overrides"] = {
        "lesion_type": "endometrioma"
    }
    changed_override_response = client.post(
        "/api/reviews/batch",
        json=altered_override,
        headers=auth_tokens["doctor"],
    )
    assert changed_override_response.status_code == 409

    # Client telemetry can advance between retries; it is separately persisted and
    # must not change the identity of the same clinical review mutation.
    telemetry_retry = dict(payload)
    telemetry_retry["telemetry_tasks"] = [{"task_id": "task-left", "last_seq": 5}]
    resp3 = client.post("/api/reviews/batch", json=telemetry_retry, headers=auth_tokens["doctor"])
    assert resp3.status_code == 200, resp3.text
    assert resp3.json() == data1

    case_response = client.get(f"/api/cases/{bilateral_case['study_id']}", headers=auth_tokens["doctor"])
    assert case_response.status_code == 200, case_response.text
    assert case_response.json()["latest_review_request_id"] == req_id

    # 3. Same request_id but altered payload -> 409 conflict
    altered_payload = dict(payload)
    altered_payload["reviews"] = [dict(payload["reviews"][0])]
    resp4 = client.post("/api/reviews/batch", json=altered_payload, headers=auth_tokens["doctor"])
    assert resp4.status_code == 409

    # 4. Another actor attempting to use the same request_id -> 409
    resp5 = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["other_doctor"])
    assert resp5.status_code == 409


def test_diagnosis_only_edit_is_queued_without_mask_change(
    auth_tokens, bilateral_case, active_case_lease
):
    from backend.app.main import app
    from backend.db import database

    client = TestClient(app)
    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
    left = {
        "image_id": bilateral_case["img_l_id"],
        "prediction_id": bilateral_case["pred_l_id"],
        "doctor_action": "ACCEPTED_RAW",
        "verified_mask_rle": bilateral_case["ai_mask"],
        "lesion_type": "simple_cyst",
        "orads": "O-RADS 2",
        "morphology_description": "Thành trơn",
    }
    right = {
        "image_id": bilateral_case["img_r_id"],
        "prediction_id": bilateral_case["pred_r_id"],
        "doctor_action": "ACCEPTED_RAW",
        "verified_mask_rle": bilateral_case["ai_mask"],
    }
    first = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        **lease,
        "reviews": [left, right],
    }
    saved = client.post("/api/reviews/batch", json=first, headers=auth_tokens["doctor"])
    assert saved.status_code == 200, saved.text

    changed = {**left, "lesion_type": "mucinous_cystadenoma", "orads": "O-RADS 3",
               "morphology_description": "Thành không đều"}
    second = {
        **first,
        "expected_revision": 1,
        "request_id": str(uuid.uuid4()),
        "reviews": [changed, right],
    }
    updated = client.post("/api/reviews/batch", json=second, headers=auth_tokens["doctor"])
    assert updated.status_code == 200, updated.text

    db = next(database.get_db())
    try:
        queue = db.query(database.ActiveLearningQueueModel).filter_by(
            study_id=bilateral_case["study_id"], image_id=bilateral_case["img_l_id"]
        ).order_by(database.ActiveLearningQueueModel.created_at.desc()).first()
        assert queue is not None
        assert queue.sample["doctor_action"] == "ACCEPTED_RAW"
        assert queue.sample["clinician_overrides"] == {
            "lesion_type": "mucinous_cystadenoma",
            "orads": "O-RADS 3",
            "morphology_description": "Thành không đều",
        }
    finally:
        db.close()


def test_manual_calipers_are_saved_as_source_image_measurements(
    auth_tokens, bilateral_case, active_case_lease
):
    from backend.app.main import app
    from backend.db import database

    db = next(database.get_db())
    try:
        db.get(database.ImageModel, bilateral_case["img_l_id"]).pixel_spacing_mm = 0.1
        db.get(database.ImageModel, bilateral_case["img_l_id"]).calibration_source = "MANUAL"
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        **lease,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
                "manual_calipers": [
                    {"label": "D1", "points": [[10, 20], [110, 20]]},
                    {"label": "D2", "points": [[20, 10], [20, 60]]},
                ],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }

    saved = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert saved.status_code == 200, saved.text
    with Session(database.engine) as db:
        review = db.query(database.ReviewModel).filter_by(image_id=bilateral_case["img_l_id"]).one()
        assert review.max_diameter_mm == 10.0
        assert review.ortho_diameter_mm == 5.0
        assert review.hitl_feedback["manual_measurements"]["D1"]["diameter_px"] == 100.0
        assert review.hitl_feedback["manual_measurements"]["D1"]["calibration_source"] == "MANUAL"
        assert review.hitl_feedback["manual_calipers"][0]["coordinate_space"] == "decoded-source-image"
        assert review.hitl_feedback["measurement_context"]["status"] == "UNAVAILABLE"

    out_of_bounds = {
        **payload,
        "request_id": str(uuid.uuid4()),
        "expected_revision": 1,
        "reviews": [dict(payload["reviews"][0]), dict(payload["reviews"][1])],
    }
    out_of_bounds["reviews"][0]["manual_calipers"] = [
        {"label": "D1", "points": [[10, 20], [640, 20]]},
    ]
    rejected = client.post("/api/reviews/batch", json=out_of_bounds, headers=auth_tokens["doctor"])
    assert rejected.status_code == 422, rejected.text


def test_review_batch_rejects_boolean_manual_caliper_coordinates(
    auth_tokens, bilateral_case, active_case_lease
):
    from backend.app.main import app

    client = TestClient(app)
    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        **lease,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
                "manual_calipers": [
                    {"label": "D1", "points": [[True, 20], [110, 20]]},
                ],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }

    response = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])

    assert response.status_code == 422, response.text
    assert any(
        "manual_calipers" in ".".join(str(part) for part in error.get("loc", []))
        for error in response.json()["detail"]
    )


def test_review_does_not_persist_mm_from_unverified_legacy_spacing(
    auth_tokens, bilateral_case, active_case_lease, tmp_path,
):
    import cv2
    import numpy as np

    from backend.app.main import app
    from backend.db import database

    source_path = tmp_path / "legacy-unverified-spacing.png"
    source = np.full((480, 640), 96, dtype=np.uint8)
    assert cv2.imwrite(str(source_path), source)
    db = next(database.get_db())
    try:
        image = db.get(database.ImageModel, bilateral_case["img_l_id"])
        image.raw_path = str(source_path)
        image.pixel_spacing_mm = 0.1
        image.calibration_source = None
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        **lease,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }

    saved = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert saved.status_code == 200, saved.text
    with Session(database.engine) as db:
        review = db.query(database.ReviewModel).filter_by(
            image_id=bilateral_case["img_l_id"],
        ).one()
        assert review.max_diameter_mm is None
        assert review.ortho_diameter_mm is None
        assert review.total_area_cm2 is None
        assert review.hitl_feedback["measurement_context"]["calibration_source"] == "UNKNOWN"
        feedback = dict(review.hitl_feedback)
        feedback["manual_measurements"] = {
            "D1": {
                "diameter_px": 100.0,
                "diameter_mm": 10.0,
                "calibrated": True,
                "calibration_source": "UNKNOWN",
            },
        }
        review.max_diameter_mm = 10.0
        review.ortho_diameter_mm = 5.0
        review.total_area_cm2 = 0.5
        review.hitl_feedback = feedback
        prediction = db.get(database.PredictionModel, bilateral_case["pred_l_id"])
        prediction.measurements = {
            "calibrated": True,
            "calibration_source": "UNKNOWN",
            "pixel_spacing_mm": 0.1,
            "max_diameter_mm": 10.0,
            "ortho_diameter_mm": 5.0,
            "total_area_cm2": 0.5,
        }
        prediction.provenance_json = {
            "calibration_source": "UNKNOWN",
            "pixel_spacing_mm": 0.1,
        }
        db.commit()

    detail = client.get(
        f"/api/cases/{bilateral_case['study_id']}", headers=auth_tokens["doctor"],
    )
    assert detail.status_code == 200, detail.text
    detail_review = detail.json()["images"][0]["review"]
    assert detail_review["max_diameter_mm"] is None
    assert detail_review["ortho_diameter_mm"] is None
    assert detail_review["total_area_cm2"] is None
    assert detail_review["hitl_feedback"]["manual_measurements"]["D1"]["diameter_mm"] is None
    assert detail_review["hitl_feedback"]["manual_measurements"]["D1"]["calibrated"] is False
    detail_prediction = detail.json()["images"][0]["prediction"]
    assert detail_prediction["measurements"]["max_diameter_mm"] is None
    assert detail_prediction["measurements"]["pixel_spacing_mm"] is None
    assert detail_prediction["provenance"]["pixel_spacing_mm"] is None

    worklist = client.get("/api/cases", headers=auth_tokens["doctor"])
    assert worklist.status_code == 200, worklist.text
    worklist_case = next(
        row for row in worklist.json() if row["study_id"] == bilateral_case["study_id"]
    )
    assert worklist_case["max_diameter_mm"] is None


def test_concurrent_batches_with_same_revision_commit_only_once(
    auth_tokens, bilateral_case, monkeypatch, tmp_path, active_case_lease
):
    from backend.app.main import app
    from backend.db import database
    from backend.services import review_service

    client = TestClient(app)

    left_path = tmp_path / "left.png"
    right_path = tmp_path / "right.png"
    left_path.touch()
    right_path.touch()

    db = next(database.get_db())
    try:
        db.get(database.ImageModel, bilateral_case["img_l_id"]).raw_path = str(left_path)
        db.get(database.ImageModel, bilateral_case["img_r_id"]).raw_path = str(right_path)
        db.commit()
    finally:
        db.close()

    def measure_without_source(*_args, **_kwargs):
        return {
            "max_diameter_mm": None,
            "ortho_diameter_mm": None,
            "total_area_cm2": None,
        }

    monkeypatch.setattr(review_service, "decode_ultrasound_image", lambda _path: object())
    monkeypatch.setattr(review_service, "measure_source_mask", measure_without_source)

    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])

    def payload(request_id):
        return {
            "study_id": bilateral_case["study_id"],
            "expected_revision": 0,
            "request_id": request_id,
            **lease,
            "reviews": [
                {
                    "image_id": bilateral_case["img_l_id"],
                    "prediction_id": bilateral_case["pred_l_id"],
                    "doctor_action": "REJECTED_ALL",
                    "verified_mask_rle": bilateral_case["empty_mask"],
                    "clinician_overrides": {"lesion_type": "simple_cyst"},
                },
                {
                    "image_id": bilateral_case["img_r_id"],
                    "prediction_id": bilateral_case["pred_r_id"],
                    "doctor_action": "ACCEPTED_RAW",
                    "verified_mask_rle": bilateral_case["ai_mask"],
                },
            ],
        }

    def submit(request_id):
        return TestClient(app).post(
            "/api/reviews/batch",
            json=payload(request_id),
            headers=auth_tokens["doctor"],
        )

    request_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(submit, request_ids))

    assert sorted(response.status_code for response in responses) == [200, 409]

    db = next(database.get_db())
    try:
        study = db.get(database.StudyModel, bilateral_case["study_id"])
        assert study.review_revision == 1
        assert db.query(database.ReviewModel).filter(
            database.ReviewModel.image_id.in_(
                [bilateral_case["img_l_id"], bilateral_case["img_r_id"]]
            )
        ).count() == 2
        assert db.query(database.ReviewBatchModel).filter(
            database.ReviewBatchModel.request_id.in_(request_ids)
        ).count() == 1
        assert db.query(database.ActiveLearningQueueModel).filter_by(
            study_id=bilateral_case["study_id"]
        ).count() == 1
    finally:
        db.close()


def test_active_learning_queue_rolls_back_with_failed_review_batch(
    auth_tokens, bilateral_case, monkeypatch, tmp_path, active_case_lease
):
    from backend.app.main import app
    from backend.db import database
    from backend.services import review_service

    left_path = tmp_path / "queue-left.png"
    right_path = tmp_path / "queue-right.png"
    left_path.touch()
    right_path.touch()
    db = next(database.get_db())
    try:
        db.get(database.ImageModel, bilateral_case["img_l_id"]).raw_path = str(left_path)
        db.get(database.ImageModel, bilateral_case["img_r_id"]).raw_path = str(right_path)
        db.commit()
    finally:
        db.close()

    calls = []

    def fail_while_measuring_second_image(*_args, **_kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("simulated second-image measurement failure")
        return {
            "max_diameter_mm": None,
            "ortho_diameter_mm": None,
            "total_area_cm2": None,
        }

    monkeypatch.setattr(review_service, "decode_ultrasound_image", lambda _path: object())
    monkeypatch.setattr(
        review_service, "measure_source_mask", fail_while_measuring_second_image
    )
    legacy_queue = tmp_path / "legacy-active-learning.jsonl"
    monkeypatch.setattr(review_service, "ACTIVE_LEARNING_QUEUE_PATH", legacy_queue)

    client = TestClient(app, raise_server_exceptions=False)
    lease = active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"])
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        **lease,
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "REJECTED_ALL",
                "verified_mask_rle": bilateral_case["empty_mask"],
                "clinician_overrides": {"lesion_type": "simple_cyst"},
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }

    response = client.post(
        "/api/reviews/batch", json=payload, headers=auth_tokens["doctor"]
    )

    assert response.status_code == 500
    assert len(calls) == 2
    db = next(database.get_db())
    try:
        image_ids = [bilateral_case["img_l_id"], bilateral_case["img_r_id"]]
        assert db.query(database.ReviewModel).filter(
            database.ReviewModel.image_id.in_(image_ids)
        ).count() == 0
        assert db.query(database.ActiveLearningQueueModel).filter_by(
            study_id=bilateral_case["study_id"]
        ).count() == 0
        assert db.get(database.StudyModel, bilateral_case["study_id"]).review_revision == 0
    finally:
        db.close()
    assert not legacy_queue.exists()


def test_legacy_endpoints_require_expected_revision_and_request_id(auth_tokens, bilateral_case):
    from backend.app.main import app
    client = TestClient(app)
    # 1. Missing expected_revision -> 422
    payload_no_rev = {
        "image_id": bilateral_case["img_l_id"],
        "prediction_id": bilateral_case["pred_l_id"],
        "doctor_action": "ACCEPTED_RAW",
        "verified_mask_rle": bilateral_case["ai_mask"],
        "request_id": str(uuid.uuid4()),
    }
    resp1 = client.post("/api/review", json=payload_no_rev, headers=auth_tokens["doctor"])
    assert resp1.status_code == 422

    # 2. Missing request_id -> 422
    payload_no_req_id = {
        "image_id": bilateral_case["img_l_id"],
        "prediction_id": bilateral_case["pred_l_id"],
        "doctor_action": "ACCEPTED_RAW",
        "verified_mask_rle": bilateral_case["ai_mask"],
        "expected_revision": 0,
    }
    resp2 = client.post("/api/review", json=payload_no_req_id, headers=auth_tokens["doctor"])
    assert resp2.status_code == 422


def test_bilateral_study_requires_both_sides(auth_tokens, bilateral_case, active_case_lease):
    from backend.app.main import app
    client = TestClient(app)
    # Batch submitting only 1 image on a bilateral study -> 422
    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            }
        ],
    }
    payload.update(active_case_lease(client, bilateral_case["study_id"], auth_tokens["doctor"]))
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


@pytest.mark.parametrize("final_status", ["SIGNED_PRELIM", "APPROVED", "LOCKED"])
def test_finalized_case_rejects_review_mutations(auth_tokens, bilateral_case, final_status):
    from backend.app.main import app
    from backend.db import database

    db = next(database.get_db())
    try:
        study = db.get(database.StudyModel, bilateral_case["study_id"])
        study.status = final_status
        db.commit()
    finally:
        db.close()

    payload = {
        "study_id": bilateral_case["study_id"],
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        "reviews": [
            {
                "image_id": bilateral_case["img_l_id"],
                "prediction_id": bilateral_case["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
            {
                "image_id": bilateral_case["img_r_id"],
                "prediction_id": bilateral_case["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": bilateral_case["ai_mask"],
            },
        ],
    }
    response = TestClient(app).post(
        "/api/reviews/batch", json=payload, headers=auth_tokens["doctor"]
    )

    assert response.status_code == 409
    db = next(database.get_db())
    try:
        study = db.get(database.StudyModel, bilateral_case["study_id"])
        assert study.status == final_status
        assert study.review_revision == 0
        assert db.query(database.ReviewModel).filter(
            database.ReviewModel.image_id.in_([bilateral_case["img_l_id"], bilateral_case["img_r_id"]])
        ).count() == 0
    finally:
        db.close()

