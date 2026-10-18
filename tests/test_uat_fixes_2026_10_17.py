"""Verification tests for the 12 UAT bugs identified on 2026-10-17."""

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from backend.db.database import (
    Base,
    ImageModel,
    PatientModel,
    PredictionModel,
    ReviewBatchModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)


@pytest.fixture
def uat_app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-uat-password")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-uat-password")

    from backend.app.main import app

    db_path = tmp_path / "uat_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all([
            UserModel(id="doctor-1", username="doctor", full_name="BS. Doctor One", role="DOCTOR"),
            UserModel(id="doctor-2", username="bacsi", full_name="BS. Doctor Two", role="DOCTOR"),
            UserModel(id="admin-1", username="admin", full_name="Admin Ops", role="ADMIN"),
        ])
        db.commit()

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_uat_01_registration_cannot_self_grant_admin(uat_app_client):
    """UAT-01: Public registration with role ADMIN must return 403 Forbidden."""
    client, _ = uat_app_client
    resp = client.post("/api/auth/register", json={
        "username": "attacker",
        "password": "password123",
        "full_name": "Attacker Trying Admin",
        "role": "ADMIN",
    })
    assert resp.status_code == 403
    assert "quản trị" in resp.json()["detail"].lower()


def test_uat_04_admin_cannot_access_clinical_case_or_image(uat_app_client):
    """UAT-04: Admin token must receive 403 on clinical case detail and image source."""
    client, engine = uat_app_client

    # Create a case with doctor
    with Session(engine) as db:
        patient = PatientModel(id="p1", anonymized_pid="PID-UAT-04")
        study = StudyModel(id="s1", patient_id=patient.id, study_code="STD-04", study_date="2026-10-17")
        image = ImageModel(id="img-04", study_id=study.id, filename="test.png", raw_path="nonexistent.png")
        db.add_all([patient, study, image])
        db.commit()

    # Admin login
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-uat-password"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Doctor login
    doc_login = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-uat-password"})
    assert doc_login.status_code == 200
    doc_token = doc_login.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Admin is blocked with 403 on case detail and image endpoints
    assert client.get("/api/cases/s1", headers=admin_headers).status_code == 403
    assert client.get("/api/images/img-04/source.png", headers=admin_headers).status_code == 403
    assert client.get("/api/images/img-04/viewer-source", headers=admin_headers).status_code == 403
    assert client.get("/api/images/img-04/mask.png", headers=admin_headers).status_code == 403

    # Doctor can read case detail
    doc_resp = client.get("/api/cases/s1", headers=doc_headers)
    assert doc_resp.status_code == 200
    assert doc_resp.json()["study_id"] == "s1"


def test_uat_02_concurrent_revision_conflict_and_batch_binding(uat_app_client):
    """UAT-02: Simultaneous batch save with same expected revision must reject conflict with 409.
    Case detail must return reviews belonging to the same batch snapshot."""
    client, engine = uat_app_client

    with Session(engine) as db:
        patient = PatientModel(id="p-uat-2", anonymized_pid="PID-UAT-02")
        study = StudyModel(
            id="s-uat-2", patient_id=patient.id, study_code="STD-02", study_date="2026-10-17",
            ovary_side="BOTH", review_revision=0,
        )
        img_l = ImageModel(id="img-l", study_id=study.id, filename="l.png", raw_path="nonexistent.png", laterality="L")
        img_r = ImageModel(id="img-r", study_id=study.id, filename="r.png", raw_path="nonexistent.png", laterality="R")
        pred_l = PredictionModel(
            id="pred-l", image_id=img_l.id, model_version="UNet-v1.0",
            raw_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0}, measurements={},
        )
        pred_r = PredictionModel(
            id="pred-r", image_id=img_r.id, model_version="UNet-v1.0",
            raw_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0}, measurements={},
        )
        db.add_all([patient, study, img_l, img_r, pred_l, pred_r])
        db.commit()

    # Doc 1 login
    doc1 = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-uat-password"}).json()["access_token"]
    # Doc 2 login
    doc2 = client.post("/api/auth/login", json={"username": "bacsi", "password": "doctor-uat-password"}).json()["access_token"]

    rle_empty = {"shape": [512, 512], "counts": [262144], "first_val": 0}
    batch_payload_1 = {
        "study_id": "s-uat-2",
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        "reviews": [
            {
                "image_id": "img-l", "prediction_id": "pred-l", "doctor_action": "REJECTED_ALL",
                "verified_mask_rle": rle_empty, "clinical_notes": "Note Doc1 Left", "lesion_type": "Nang",
            },
            {
                "image_id": "img-r", "prediction_id": "pred-r", "doctor_action": "REJECTED_ALL",
                "verified_mask_rle": rle_empty, "clinical_notes": "Note Doc1 Right", "lesion_type": "Nang",
            },
        ],
    }

    batch_payload_2 = {
        "study_id": "s-uat-2",
        "expected_revision": 0,  # Same expected revision!
        "request_id": str(uuid.uuid4()),
        "reviews": [
            {
                "image_id": "img-l", "prediction_id": "pred-l", "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": rle_empty, "clinical_notes": "Note Doc2 Left", "lesion_type": "Bình thường",
            },
            {
                "image_id": "img-r", "prediction_id": "pred-r", "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": rle_empty, "clinical_notes": "Note Doc2 Right", "lesion_type": "Bình thường",
            },
        ],
    }

    resp1 = client.post("/api/reviews/batch", json=batch_payload_1, headers={"Authorization": f"Bearer {doc1}"})
    assert resp1.status_code == 200
    assert resp1.json()["review_revision"] == 1

    # Second request with expected_revision 0 must be rejected with 409 Conflict
    resp2 = client.post("/api/reviews/batch", json=batch_payload_2, headers={"Authorization": f"Bearer {doc2}"})
    assert resp2.status_code == 409

    # Reopening the case must return consistent reviews from Batch 1 for both sides
    detail = client.get("/api/cases/s-uat-2", headers={"Authorization": f"Bearer {doc1}"}).json()
    assert detail["review_revision"] == 1
    for img in detail["images"]:
        rev = img["review"]
        assert rev is not None
        assert rev["doctor_id"] == "doctor"
        assert rev["doctor_action"] == "REJECTED_ALL"


def test_uat_10_search_over_50_cases(uat_app_client):
    """UAT-10: Searching for an older patient PID when there are > 50 cases must succeed."""
    client, engine = uat_app_client

    with Session(engine) as db:
        # Create target patient first (oldest)
        target_patient = PatientModel(id="target-p", anonymized_pid="UAT-PID-TARGET")
        target_study = StudyModel(
            id="target-s", patient_id=target_patient.id, study_code="STD-TARGET",
            study_date="2026-01-01", created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        db.add_all([target_patient, target_study])

        # Now create 55 newer cases
        for idx in range(55):
            p = PatientModel(id=f"other-p-{idx}", anonymized_pid=f"OTHER-PID-{idx:03d}")
            s = StudyModel(
                id=f"other-s-{idx}", patient_id=p.id, study_code=f"STD-{idx:03d}",
                study_date="2026-10-17", created_at=datetime(2026, 10, 17, 10, 0, idx, tzinfo=UTC),
            )
            db.add_all([p, s])
        db.commit()

    doc_token = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-uat-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Search specifically for the oldest PID
    resp = client.get("/api/cases?search=UAT-PID-TARGET", headers=headers)
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 1
    assert cases[0]["patient_id"] == "UAT-PID-TARGET"


def test_uat_09_physical_units_null_when_uncalibrated(tmp_path):
    """UAT-09: Research export must set physical_units=None when saved review has null max_diameter_mm."""
    from backend.services.research_export import build_research_bundle
    from backend.core.image_utils import cv2_imwrite_unicode
    import numpy as np
    import zipfile
    import json

    engine = create_engine(f"sqlite:///{tmp_path / 'export_test.db'}")
    Base.metadata.create_all(engine)

    img_file = tmp_path / "sample.png"
    cv2_imwrite_unicode(str(img_file), np.zeros((100, 100, 3), dtype=np.uint8))

    with Session(engine) as db:
        p = PatientModel(id="p-exp", anonymized_pid="PID-EXP")
        s = StudyModel(id="s-exp", patient_id=p.id, study_code="STD-EXP", study_date="2026-10-17", review_revision=1)
        # Image has pixel_spacing_mm calibrated later, but review was saved without calibration!
        img = ImageModel(id="img-exp", study_id=s.id, filename="sample.png", raw_path=str(img_file), laterality="L", pixel_spacing_mm=0.1)
        pred = PredictionModel(
            id="pred-exp", image_id=img.id, model_version="UNet",
            raw_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0}, measurements={},
        )
        rev = ReviewModel(
            id="rev-exp", image_id=img.id, prediction_id=pred.id, doctor_id="doctor",
            doctor_action="ACCEPTED_RAW", verified_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0},
            max_diameter_mm=None, ortho_diameter_mm=None, total_area_cm2=None,  # Uncalibrated review!
        )
        actor = UserModel(id="doc", username="doctor", full_name="BS", role="DOCTOR")
        db.add_all([p, s, img, pred, rev, actor])
        db.commit()

        zip_bytes = build_research_bundle(db, s.id, [rev.id], 1, actor)

    export_zip_path = tmp_path / "out.zip"
    export_zip_path.write_bytes(zip_bytes)
    with zipfile.ZipFile(export_zip_path) as zf:
        manifest = json.loads(zf.read("metadata.json").decode("utf-8"))
        img_meta = manifest["images"][0]
        assert img_meta["physical_units"] is None, f"Expected physical_units to be None for uncalibrated review, got {img_meta['physical_units']}"
