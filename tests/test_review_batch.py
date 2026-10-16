import os
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

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


def test_action_mismatch_422(auth_tokens, bilateral_case):
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
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


def test_foreign_prediction_422(auth_tokens, bilateral_case):
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
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


def test_stale_version_409(auth_tokens, bilateral_case):
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
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 409


def test_rollback_on_second_image_failure(auth_tokens, bilateral_case):
    from backend.db import database
    from backend.app.main import app
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


def test_atomic_success_and_idempotent_retry(auth_tokens, bilateral_case):
    from backend.db import database
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
                "clinical_notes": "Note L",
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
    finally:
        db.close()

    # 2. Idempotent replay: exact same payload and request_id -> returns same 200 and same review IDs
    resp2 = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2 == data1

    # 3. Same request_id but altered payload -> 409 conflict
    altered_payload = dict(payload)
    altered_payload["reviews"] = [dict(payload["reviews"][0])]
    resp3 = client.post("/api/reviews/batch", json=altered_payload, headers=auth_tokens["doctor"])
    assert resp3.status_code == 409

    # 4. Another actor attempting to use the same request_id -> 409
    resp4 = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["other_doctor"])
    assert resp4.status_code == 409


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


def test_bilateral_study_requires_both_sides(auth_tokens, bilateral_case):
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
    resp = client.post("/api/reviews/batch", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422

