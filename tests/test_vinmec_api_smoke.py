"""Synthetic-fixture API smoke test for the research segmentation and review flow."""

import base64
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import (
    AuditLogModel,
    Base,
    ImageModel,
    PatientModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)

pytestmark = pytest.mark.usefixtures("doctor_access")


def synthetic_fixture_image():
    from scripts.generate_synthetic_e2e_fixtures import FIXTURES_DIR, generate_fixtures

    image = FIXTURES_DIR / "synthetic_left.png"
    if not image.is_file():
        generate_fixtures()
    if not image.is_file():
        raise FileNotFoundError(f"Synthetic E2E fixture was not generated: {image}")
    return image


def test_upload_predict_edit_confirm_and_retrieve(tmp_path, monkeypatch, active_case_lease):
    from backend.app.config import model_registry
    from backend.app.main import app
    from backend.app.routers import inference

    image_path = synthetic_fixture_image()
    assert image_path.is_file()
    assert model_registry.get_primary_adapter().is_loaded

    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'smoke.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(db_engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))
    with Session(db_engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.commit()

    def temporary_db():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            with image_path.open("rb") as image:
                uploaded = client.post("/api/upload", files={"file": (image_path.name, image, "image/png")})
            assert uploaded.status_code == 200, uploaded.text
            image_id = uploaded.json()["image_id"]
            study_id = uploaded.json()["study_id"]
            lease = active_case_lease(client, study_id)
            lease_headers = {
                "X-Case-Lease-Token": lease["lease_token"],
                "X-Case-Page-Instance-Id": lease["page_instance_id"],
            }

            predicted = client.post(f"/api/predict/{image_id}", headers=lease_headers)
            assert predicted.status_code == 200, predicted.text
            prediction = predicted.json()
            assert prediction["prediction_id"]
            assert prediction["overlay_base64"].startswith("data:image/png;base64,")
            assert prediction["original_image_base64"].startswith("data:image/png;base64,")
            from ai_training.dataset_loader import cv2_imread_unicode
            from backend.services.preprocessor import UltrasoundPreprocessor

            original_png = base64.b64decode(prediction["original_image_base64"].split(",", 1)[1])
            displayed_gray = cv2.imdecode(np.frombuffer(original_png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            source_gray = cv2_imread_unicode(str(image_path), cv2.IMREAD_GRAYSCALE)
            expected_gray, _ = UltrasoundPreprocessor(target_size=(512, 512)).letterbox_resize(source_gray)
            assert np.array_equal(displayed_gray, expected_gray), "API and evaluator must decode the same grayscale pixels"
            assert prediction["provenance"]["pixel_spacing_mm"] is None
            assert prediction["measurements"]["max_diameter_mm"] is None
            assert prediction["measurements"]["total_area_cm2"] is None
            assert prediction["cdss_classification"] == {}

            rle = prediction["rle_mask"]
            adapter = model_registry.get_primary_adapter()
            edited_mask = adapter.engine.rle_to_mask(rle)
            edited_mask[0:4, 0:4] = 1 - edited_mask[0:4, 0:4]
            edited_rle = adapter.engine.mask_to_rle(edited_mask)
            assert edited_rle != rle

            for endpoint in ("/api/review", "/api/v1/cases/confirm"):
                for action, final_mask in (
                    ("ACCEPTED_RAW", edited_rle),
                    ("MODIFIED", rle),
                    ("REJECTED_ALL", edited_rle if not np.any(adapter.engine.rle_to_mask(rle)) else rle),
                    ("INVENTED", rle),
                ):
                    invalid_review = client.post(
                        endpoint,
                        json={
                            "image_id": image_id,
                            "prediction_id": prediction["prediction_id"],
                            "doctor_action": action,
                            "verified_mask_rle": final_mask,
                            "expected_revision": 0,
                            "request_id": str(uuid.uuid4()),
                            **lease,
                        },
                    )
                    assert invalid_review.status_code == 422, (endpoint, action, invalid_review.text)

            with Session(db_engine) as db:
                assert db.query(ReviewModel).count() == 0

            review_request = {
                "image_id": image_id,
                "prediction_id": prediction["prediction_id"],
                "doctor_id": "TEST_REVIEWER",
                "doctor_action": "MODIFIED",
                "verified_mask_rle": edited_rle,
                "time_spent_seconds": 1,
                "expected_revision": 0,
                "request_id": str(uuid.uuid4()),
                **lease,
            }
            reviewed = client.post("/api/review", json=review_request)
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["is_ground_truth"] is False
            assert reviewed.json()["message"] == "Đã lưu mask rà soát và nhật ký thao tác."

            replayed = client.post("/api/v1/cases/confirm", json=review_request)
            assert replayed.status_code == 200, replayed.text
            assert replayed.json()["review_id"] == reviewed.json()["review_id"]
            assert replayed.json()["is_ground_truth"] is False
            assert replayed.json()["message"] == reviewed.json()["message"]

            case = client.get(f"/api/cases/{study_id}")
            assert case.status_code == 200, case.text
            saved = case.json()
            assert saved["status"] == "REVIEWED"
            assert saved["images"][0]["prediction"]["rle_mask"] == rle
            assert saved["images"][0]["review"]["verified_mask_rle"] == edited_rle
            assert saved["images"][0]["review"]["time_spent_seconds"] == 1

        with Session(db_engine) as db:
            image_record = db.get(ImageModel, image_id)
            study = db.get(StudyModel, study_id)
            patient = db.get(PatientModel, study.patient_id)
            review = db.get(ReviewModel, reviewed.json()["review_id"])
            audit = db.query(AuditLogModel).filter(AuditLogModel.entity_id == review.id).one()
            upload_audit = db.query(AuditLogModel).filter(
                AuditLogModel.entity_id == image_id,
                AuditLogModel.action_type == "UPLOAD_IMAGE",
            ).one()
            assert image_record.pixel_spacing_mm is None
            assert study.device_vendor is None
            assert patient.age_bucket is None
            assert patient.anonymized_pid != "ANON-VINMEC-185"
            assert review.is_official_ground_truth is False
            assert review.doctor_id == "doctor"
            assert audit.actor_id == "doctor"
            assert upload_audit.actor_id == "doctor"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_engine.dispose()


def test_upload_with_unknown_study_does_not_leave_file(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'unknown_study.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(db_engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    def temporary_db():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        image_path = synthetic_fixture_image()
        with TestClient(app) as client, image_path.open("rb") as image:
            response = client.post(
                "/api/upload",
                data={"study_id": "missing-study"},
                files={"file": (image_path.name, image, "image/png")},
            )
        assert response.status_code == 404
        assert list(upload_dir.iterdir()) == []
        with Session(db_engine) as db:
            assert db.query(ImageModel).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_engine.dispose()
