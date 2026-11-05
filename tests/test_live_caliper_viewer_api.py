"""
Test live integration of Caliper Removal and Denoising via REST API:
- GET /api/images/{image_id}/viewer-source?enable_caliper_removal=true&denoise_method=lee
- POST /api/predict/{image_id}?enable_caliper_removal=true&denoise_method=lee
"""

from datetime import date, datetime, UTC
import base64
import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import (
    Base,
    FacilityModel,
    ImageModel,
    PatientModel,
    StudyModel,
    UserModel,
    get_db,
)

pytestmark = pytest.mark.usefixtures("doctor_access")


def test_viewer_source_with_caliper_removal_and_denoise(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    # Create dummy image with a synthetic crosshair caliper on it
    img_np = np.ones((512, 512), dtype=np.uint8) * 80
    # Add crosshair caliper mark at center
    cv2.line(img_np, (240, 256), (272, 256), 255, 2)
    cv2.line(img_np, (256, 240), (256, 272), 255, 2)

    image_file = tmp_path / "test_caliper.png"
    cv2.imwrite(str(image_file), img_np)

    # Set up test database
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'caliper_test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(db_engine)

    with Session(db_engine) as db:
        fac = db.query(FacilityModel).filter_by(id="FAC-DEFAULT-TEST").first()
        if not fac:
            fac = FacilityModel(id="FAC-DEFAULT-TEST", facility_code="FAC-DEFAULT-TEST", name="Default Facility", is_active=True)
            db.add(fac)
        doc = db.query(UserModel).filter_by(id="test-doctor").first()
        if not doc:
            doc = UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR", facility_id="FAC-DEFAULT-TEST")
            db.add(doc)
        patient = PatientModel(id="PAT-001", anonymized_pid="ANON-PID-001")
        study = StudyModel(id="ST-001", patient_id=patient.id, facility_id="FAC-DEFAULT-TEST", status="ANALYZED", study_date=date.today())
        image = ImageModel(
            id="IMG-001",
            study_id=study.id,
            filename="test_caliper.png",
            raw_path=str(image_file),
            file_hash="hash123",
        )
        db.add_all([patient, study, image])
        db.commit()

    def override_get_db():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # 1. Call viewer-source with caliper removal OFF
        resp_raw = client.get("/api/images/IMG-001/viewer-source?enable_caliper_removal=false&denoise_method=none")
        assert resp_raw.status_code == 200, resp_raw.text
        data_raw = resp_raw.json()
        assert data_raw["image_id"] == "IMG-001"
        assert data_raw["caliper_removed"] is False
        assert "data:image/png;base64," in data_raw["original_image_base64"]

        # 2. Verify caliper removal is fail-closed with 422 per clinical safety protocol
        resp_locked = client.get("/api/images/IMG-001/viewer-source?enable_caliper_removal=true&denoise_method=lee")
        assert resp_locked.status_code == 422
        assert "Tự động xóa caliper chưa được xác thực" in resp_locked.json()["detail"]

        # 3. Call viewer-source with caliper removal OFF and Lee filter active
        resp_clean = client.get("/api/images/IMG-001/viewer-source?enable_caliper_removal=false&denoise_method=lee")
        assert resp_clean.status_code == 200, resp_clean.text
        data_clean = resp_clean.json()
        assert data_clean["caliper_removed"] is False
        assert data_clean["denoise_method"] == "lee"
        assert "data:image/png;base64," in data_clean["original_image_base64"]

        # Decode cleaned image and verify valid shape
        clean_bytes = base64.b64decode(data_clean["original_image_base64"].split(",")[1])
        clean_arr = cv2.imdecode(np.frombuffer(clean_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        assert clean_arr is not None
        assert clean_arr.shape == (512, 512)

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_predict_with_caliper_removal_and_denoise(tmp_path, monkeypatch, active_case_lease):
    from backend.app.config import model_registry
    from backend.app.main import app
    from tests.test_vinmec_api_smoke import synthetic_fixture_image
    from tests.helpers.synthetic_inference import enable_synthetic_inference

    enable_synthetic_inference(monkeypatch, model_registry)

    image_path = synthetic_fixture_image()
    assert image_path.is_file()
    assert model_registry.get_primary_adapter().is_loaded

    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'caliper_predict_test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(db_engine)

    with Session(db_engine) as db:
        fac = db.query(FacilityModel).filter_by(id="FAC-DEFAULT-TEST").first()
        if not fac:
            fac = FacilityModel(id="FAC-DEFAULT-TEST", facility_code="FAC-DEFAULT-TEST", name="Default Facility", is_active=True)
            db.add(fac)
        doc = db.query(UserModel).filter_by(id="test-doctor").first()
        if not doc:
            doc = UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR", facility_id="FAC-DEFAULT-TEST")
            db.add(doc)
        patient = PatientModel(id="PAT-002", anonymized_pid="ANON-PID-002")
        db.add(patient)
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

            # Run prediction with caliper removal ON -> must fail-closed with 422
            predict_url_locked = f"/api/predict/{image_id}?enable_caliper_removal=true&denoise_method=lee&generate_overlay=true"
            predicted_locked = client.post(predict_url_locked, headers=lease_headers)
            assert predicted_locked.status_code == 422
            assert "Tự động xóa caliper chưa được xác thực" in predicted_locked.json()["detail"]

            # Run prediction with caliper removal OFF and speckle filtering active -> must succeed with 200
            predict_url = f"/api/predict/{image_id}?enable_caliper_removal=false&denoise_method=lee&generate_overlay=true"
            predicted = client.post(predict_url, headers=lease_headers)
            assert predicted.status_code == 200, predicted.text
            prediction = predicted.json()
            assert prediction["prediction_id"]
            assert prediction["overlay_base64"].startswith("data:image/png;base64,")
            assert prediction["original_image_base64"].startswith("data:image/png;base64,")
            assert "rle_mask" in prediction
            assert "measurements" in prediction
    finally:
        app.dependency_overrides.pop(get_db, None)
