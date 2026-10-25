import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app import security
from backend.app.main import app
from backend.db.database import (
    AuditLogModel,
    Base,
    CaseLeaseModel,
    HITLEventModel,
    HITLSessionModel,
    ImageModel,
    PatientModel,
    PredictionModel,
    StudyModel,
    UserModel,
)

OWNER = {"tab_id": "tab-owner-00000001", "page_instance_id": "page-owner-00000001"}
OTHER = {"tab_id": "tab-other-00000002", "page_instance_id": "page-other-00000002"}


def release_payload(identity, lease_token):
    return {"page_instance_id": identity["page_instance_id"], "lease_token": lease_token}


@pytest.fixture
def lease_api(tmp_path):
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'case-leases.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(db_engine)
    test_session = sessionmaker(bind=db_engine, autoflush=False)
    with test_session() as db:
        db.add_all(
            [
                UserModel(id="lease-doctor", username="lease-doctor", full_name="Doctor", role="DOCTOR"),
                UserModel(id="lease-admin", username="lease-admin", full_name="Admin", role="ADMIN"),
            ]
        )
        db.add(PatientModel(id="lease-patient", anonymized_pid="SYN-LEASE", age_bucket="40-49"))
        db.add(
            StudyModel(
                id="lease-study",
                patient_id="lease-patient",
                study_code="LEASE-1",
                study_date="2026-10-21",
                status="PENDING",
            )
        )
        db.commit()

    active_user = {
        "value": UserModel(id="lease-doctor", username="lease-doctor", full_name="Doctor", role="DOCTOR")
    }

    def get_test_db():
        with test_session() as db:
            yield db

    app.dependency_overrides[security.get_current_user] = lambda: active_user["value"]
    from backend.db.database import get_db

    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as client:
            yield client, active_user, test_session
    finally:
        app.dependency_overrides.pop(security.get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        db_engine.dispose()


def lease_path(study_id="lease-study"):
    return f"/api/workspace/cases/{study_id}/lease"


def test_case_lease_is_exclusive_token_bound_and_releasable(lease_api):
    client, _, _ = lease_api
    path = lease_path()
    first = client.post(path, json=OWNER)
    assert first.status_code == 200
    owner = first.json()
    assert owner["granted"] is True
    assert len(owner["lease_token"]) >= 32

    contender = client.post(path, json=OTHER)
    assert contender.status_code == 200
    assert contender.json()["granted"] is False

    bad_token = client.post(
        path,
        json={**OWNER, "lease_token": "x" * 40},
    )
    assert bad_token.json()["granted"] is False
    cloned_page = client.post(
        path,
        json={**OWNER, "page_instance_id": "page-clone-00000001", "lease_token": owner["lease_token"]},
    )
    assert cloned_page.json()["granted"] is False

    renewed = client.post(
        path,
        json={**OWNER, "lease_token": owner["lease_token"]},
    )
    assert renewed.json()["granted"] is True
    assert renewed.json()["lease_token"] == owner["lease_token"]

    denied_release = client.request(
        "DELETE", path, json=release_payload(OTHER, owner["lease_token"])
    )
    assert denied_release.status_code == 200
    assert denied_release.json()["released"] is False

    released = client.request(
        "DELETE", path, json=release_payload(OWNER, owner["lease_token"])
    )
    assert released.json()["released"] is True
    assert client.post(path, json=OTHER).json()["granted"] is True


def test_lease_commit_acknowledgement_failure_returns_persisted_token(lease_api, monkeypatch):
    _, active_user, test_session = lease_api
    from backend.services.case_lease_service import acquire_case_lease, hash_lease_token

    with test_session() as db:
        real_commit = db.commit

        def commit_then_lose_acknowledgement():
            real_commit()
            raise RuntimeError("simulated lost lease commit acknowledgement")

        def fail_rollback():
            raise RuntimeError("simulated lease rollback failure")

        monkeypatch.setattr(db, "commit", commit_then_lose_acknowledgement)
        monkeypatch.setattr(db, "rollback", fail_rollback)
        result = acquire_case_lease(
            db,
            "lease-study",
            active_user["value"],
            OWNER["tab_id"],
            OWNER["page_instance_id"],
            None,
        )

    assert result["granted"] is True
    assert len(result["lease_token"]) >= 32
    with test_session() as db:
        lease = db.get(CaseLeaseModel, "lease-study")
        assert lease is not None
        assert lease.token_hash == hash_lease_token(result["lease_token"])


def test_lease_release_commit_acknowledgement_failure_reports_persisted_release(lease_api, monkeypatch):
    client, active_user, test_session = lease_api
    from backend.services.case_lease_service import release_case_lease

    lease_response = client.post(lease_path(), json=OWNER)
    assert lease_response.status_code == 200
    token = lease_response.json()["lease_token"]

    with test_session() as db:
        real_commit = db.commit

        def commit_then_lose_acknowledgement():
            real_commit()
            raise RuntimeError("simulated lost release acknowledgement")

        def fail_rollback():
            raise RuntimeError("simulated release rollback failure")

        monkeypatch.setattr(db, "commit", commit_then_lose_acknowledgement)
        monkeypatch.setattr(db, "rollback", fail_rollback)
        result = release_case_lease(
            db,
            "lease-study",
            active_user["value"],
            token,
            OWNER["page_instance_id"],
        )

    assert result["released"] is True
    with test_session() as db:
        assert db.get(CaseLeaseModel, "lease-study") is None


def test_case_lease_validates_identity_case_state_and_role(lease_api):
    client, active_user, test_session = lease_api
    path = lease_path()
    assert client.post(path, json={**OWNER, "tab_id": "  "}).status_code == 422
    assert client.post(lease_path("absent"), json=OWNER).status_code == 404

    with test_session() as db:
        study = db.get(StudyModel, "lease-study")
        study.status = "APPROVED"
        db.commit()
    assert client.post(path, json=OWNER).status_code == 409

    active_user["value"] = UserModel(
        id="lease-admin", username="lease-admin", full_name="Admin", role="ADMIN"
    )
    assert client.post(path, json=OWNER).status_code == 403


def test_expired_lease_can_be_taken_over_atomically(lease_api):
    client, _, test_session = lease_api
    path = lease_path()
    first = client.post(path, json=OWNER).json()
    with test_session() as db:
        lease = db.execute(text("SELECT study_id FROM case_leases WHERE study_id = 'lease-study'")).first()
        assert lease is not None
        db.execute(
            text("UPDATE case_leases SET expires_at = '2000-01-01 00:00:00' WHERE study_id = 'lease-study'")
        )
        db.commit()

    contenders = [
        {"tab_id": "tab-other-00000002", "page_instance_id": "page-other-00000002"},
        {"tab_id": "tab-other-00000003", "page_instance_id": "page-other-00000003"},
    ]

    def acquire(identity):
        return client.post(path, json=identity).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, contenders))
    assert sum(result["granted"] for result in results) == 1
    assert client.request(
        "DELETE", path, json=release_payload(OWNER, first["lease_token"])
    ).json()["released"] is False


def test_active_lease_is_required_for_review_writes(lease_api):
    client, _, _ = lease_api
    path = lease_path()
    lease = client.post(path, json=OWNER).json()
    body = {
        "study_id": "lease-study",
        "expected_revision": 0,
        "request_id": "lease-review-attempt",
        "reviews": [],
        "page_instance_id": OWNER["page_instance_id"],
    }

    assert client.post("/api/reviews/batch", json=body).status_code == 423
    wrong_token = {**body, "lease_token": "x" * 40}
    assert client.post("/api/reviews/batch", json=wrong_token).status_code == 423
    wrong_page = {
        **body,
        "lease_token": lease["lease_token"],
        "page_instance_id": "page-clone-00000001",
    }
    assert client.post("/api/reviews/batch", json=wrong_page).status_code == 423

    owner_attempt = {**body, "lease_token": lease["lease_token"]}
    # The owner passes the lease guard and reaches the normal empty-review validation.
    assert client.post("/api/reviews/batch", json=owner_attempt).status_code == 422


def test_review_writes_require_a_lease_after_expiry_or_release(lease_api):
    client, _, test_session = lease_api
    body = {
        "study_id": "lease-study",
        "expected_revision": 0,
        "request_id": "lease-required-after-revoke",
        "reviews": [],
        "page_instance_id": OWNER["page_instance_id"],
    }

    assert client.post("/api/reviews/batch", json=body).status_code == 423
    lease = client.post(lease_path(), json=OWNER).json()
    assert lease["granted"] is True

    with test_session() as db:
        db.execute(
            text("UPDATE case_leases SET expires_at = '2000-01-01 00:00:00' WHERE study_id = 'lease-study'")
        )
        db.commit()

    expired_attempt = {
        **body,
        "lease_token": lease["lease_token"],
        "page_instance_id": OWNER["page_instance_id"],
    }
    assert client.post("/api/reviews/batch", json=expired_attempt).status_code == 423

    client.request("DELETE", lease_path(), json=release_payload(OWNER, lease["lease_token"]))
    assert client.post("/api/reviews/batch", json=body).status_code == 423


def test_image_calibration_requires_the_active_case_lease(lease_api):
    client, _, test_session = lease_api
    with test_session() as db:
        db.add(
            ImageModel(
                id="lease-image",
                study_id="lease-study",
                filename="lease.png",
                raw_path="lease.png",
                width=100,
                height=100,
                pixel_spacing_mm=0.2,
            )
        )
        db.commit()

    calibration_url = "/api/images/lease-image/calibrate?pixel_spacing_mm=0.4"
    assert client.post(calibration_url).status_code == 423
    with test_session() as db:
        assert db.get(ImageModel, "lease-image").pixel_spacing_mm == 0.2

    lease = client.post(lease_path(), json=OWNER).json()
    headers = {
        "X-Case-Lease-Token": lease["lease_token"],
        "X-Case-Page-Instance-Id": OWNER["page_instance_id"],
    }
    assert client.post(calibration_url, headers=headers).status_code == 200

    with test_session() as db:
        db.execute(
            text("UPDATE case_leases SET expires_at = '2000-01-01 00:00:00' WHERE study_id = 'lease-study'")
        )
        db.commit()
    assert client.post(calibration_url, headers=headers).status_code == 423
    with test_session() as db:
        assert db.get(ImageModel, "lease-image").pixel_spacing_mm == 0.4
    released = client.request(
        "DELETE", lease_path(), json=release_payload(OWNER, lease["lease_token"])
    )
    assert released.json()["released"] is True
    assert client.post(calibration_url, headers=headers).status_code == 423
    with test_session() as db:
        assert db.get(ImageModel, "lease-image").pixel_spacing_mm == 0.4


def test_upload_iqa_and_prediction_writes_require_the_active_lease(
    lease_api, monkeypatch, tmp_path
):
    import base64
    from types import SimpleNamespace

    import cv2
    import numpy as np

    from backend.app.routers import inference

    client, _, test_session = lease_api
    with test_session() as db:
        db.get(StudyModel, "lease-study").ovary_side = "BOTH"
        db.commit()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(
        inference,
        "decode_ultrasound_image",
        lambda *_args, **_kwargs: np.full((128, 128), 127, dtype=np.uint8),
    )
    monkeypatch.setattr(
        inference.preprocessor,
        "validate_ultrasound_suitability",
        lambda _image: {
            "is_suitable": True,
            "iqa_score": 0.95,
            "checklist": [],
            "error_message": "",
            "laplacian_variance": 1.0,
            "contrast_std": 2.0,
        },
    )

    encoded, image_bytes = cv2.imencode(".png", np.full((128, 128), 127, dtype=np.uint8))
    assert encoded
    map_encoded, map_buffer = cv2.imencode(".png", np.zeros((512, 512, 4), dtype=np.uint8))
    assert map_encoded
    uncertainty_map_png = map_buffer.tobytes()
    upload_args = {
        "data": {"study_id": "lease-study", "laterality": "R"},
        "files": {"file": ("right.png", image_bytes.tobytes(), "image/png")},
    }
    assert client.post("/api/upload", **upload_args).status_code == 423
    with test_session() as db:
        assert db.query(ImageModel).filter_by(study_id="lease-study").count() == 0
    assert list(upload_dir.iterdir()) == []

    lease = client.post(lease_path(), json=OWNER).json()
    headers = {
        "X-Case-Lease-Token": lease["lease_token"],
        "X-Case-Page-Instance-Id": OWNER["page_instance_id"],
    }
    uploaded = client.post("/api/upload", headers=headers, **upload_args)
    assert uploaded.status_code == 200, uploaded.text
    image_id = uploaded.json()["image_id"]

    validate_url = f"/api/validate-image?image_id={image_id}"
    assert client.post(validate_url).status_code == 423
    assert client.post(validate_url, headers=headers).status_code == 200
    with test_session() as db:
        assert db.query(AuditLogModel).filter_by(action_type="VALIDATE_IQA").count() == 1

    adapter = SimpleNamespace(
        is_loaded=True,
        architecture="Test U-Net",
        engine=SimpleNamespace(model_checksum="a" * 64, threshold=0.5),
    )
    inference_result = {
        "confidence_score": 0.95,
        "provenance": {"model_checksum": "a" * 64, "model_version": "test"},
        "rle_mask": {"shape": [512, 512], "first_val": 0, "counts": [262144]},
        "measurements": {
            "has_lesion": False,
            "total_lesions": 0,
            "lesions": [],
            "max_diameter_mm": None,
            "ortho_diameter_mm": None,
            "total_area_cm2": None,
        },
        "overlay_base64": "data:image/png;base64,",
        "uncertainty_map_png": uncertainty_map_png,
        "quality_gate": {},
        "uncertainty": {},
        "timings": {},
    }
    monkeypatch.setattr(
        inference.preprocessor,
        "preprocess_for_inference",
        lambda _image: (
            None,
            np.zeros((512, 512), dtype=np.uint8),
            {"scale": 1.0, "pad_w": 0, "pad_h": 0, "new_w": 512, "new_h": 512},
            {
                "iqa_score": 0.95,
                "laplacian_variance": 1.0,
                "contrast_std": 2.0,
                "shadow_ratio": 0.0,
                "flags": [],
                "is_acceptable": True,
                "message": "",
            },
        ),
    )
    monkeypatch.setattr(
        inference,
        "model_registry",
        SimpleNamespace(
            get_primary_adapter=lambda: adapter,
            model_selection={},
            predict=lambda *_args, **_kwargs: inference_result,
        ),
    )

    prediction_url = f"/api/predict/{image_id}"
    assert client.post(prediction_url).status_code == 423
    predicted = client.post(prediction_url, headers=headers)
    assert predicted.status_code == 200, predicted.text
    expected_map_data_uri = "data:image/png;base64," + base64.b64encode(uncertainty_map_png).decode("ascii")
    assert predicted.json()["uncertainty_map_base64"] == expected_map_data_uri
    with test_session() as db:
        prediction = db.query(PredictionModel).filter_by(image_id=image_id).one()
        assert prediction.uncertainty_map_png == uncertainty_map_png
        assert db.get(StudyModel, "lease-study").status == "ANALYZED"

    case_detail = client.get("/api/cases/lease-study")
    assert case_detail.status_code == 200, case_detail.text
    assert case_detail.json()["images"][0]["prediction"]["uncertainty_map_base64"] == expected_map_data_uri


def test_deleting_case_cascades_its_active_lease(lease_api):
    client, active_user, test_session = lease_api
    lease = client.post(lease_path(), json=OWNER).json()
    assert lease["granted"] is True

    active_user["value"] = UserModel(
        id="lease-admin", username="lease-admin", full_name="Admin", role="ADMIN"
    )
    response = client.delete("/api/cases/lease-study")
    assert response.status_code == 200

    with test_session() as db:
        assert db.query(CaseLeaseModel).count() == 0


def test_hitl_session_and_event_writes_require_the_active_lease(lease_api):
    client, _, test_session = lease_api
    with test_session() as db:
        db.add(
            ImageModel(
                id="lease-hitl-image",
                study_id="lease-study",
                filename="lease.png",
                raw_path="lease.png",
                width=100,
                height=100,
            )
        )
        db.commit()

    session_body = {"study_id": "lease-study", "participant_code": "LEASE-HITL"}
    assert client.post("/api/hitl/sessions", json=session_body).status_code == 423
    with test_session() as db:
        assert db.query(HITLSessionModel).filter_by(study_id="lease-study").count() == 0

    lease = client.post(lease_path(), json=OWNER).json()
    headers = {
        "X-Case-Lease-Token": lease["lease_token"],
        "X-Case-Page-Instance-Id": OWNER["page_instance_id"],
    }
    created = client.post("/api/hitl/sessions", json=session_body, headers=headers)
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    event = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "image_id": "lease-hitl-image",
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-21T12:00:00Z",
                "elapsed_ms": 1.0,
                "session_elapsed_ms": 1.0,
            }
        ]
    }

    event_url = f"/api/hitl/sessions/{session_id}/events"
    assert client.post(event_url, json=event).status_code == 423
    with test_session() as db:
        assert db.query(HITLEventModel).filter_by(session_id=session_id).count() == 0

    saved = client.post(event_url, json=event, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["accepted_count"] == 1
