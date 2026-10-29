"""
Verification and Policy Regression for Use Cases UC-73, UC-74, and UC-75.
Enforces:
- UC-73: Research export fails closed until trusted approval, consent, and de-identification records exist.
- UC-74: Admin Ground Truth Export remains disabled until trusted research records exist.
- UC-75: Evaluation samples & artifact downloads strictly require authentication, return 401 for anonymous,
         and return clear 404 for missing samples.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers.auth import create_access_token, hash_password
from backend.db.database import (
    Base,
    ImageModel,
    PatientModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-key-for-uc73-74-75-verification-123456")
    db_file = tmp_path / "test_uc73_75.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    # Populate Users: DOCTOR, ADMIN, TECHNICIAN
    with Session(engine) as db:
        doctor_user = UserModel(
            id="u-doc",
            username="doctor_test",
            password_hash=hash_password("doc-pass"),
            full_name="Dr. Test",
            role="DOCTOR",
        )
        admin_user = UserModel(
            id="u-admin",
            username="admin_test",
            password_hash=hash_password("admin-pass"),
            full_name="Admin Test",
            role="ADMIN",
        )
        tech_user = UserModel(
            id="u-tech",
            username="tech_test",
            password_hash=hash_password("tech-pass"),
            full_name="Tech Test",
            role="TECHNICIAN",
        )
        db.add_all([doctor_user, admin_user, tech_user])

        patient = PatientModel(
            id="pat-01",
            anonymized_pid="PID-ANON-001",
            age_bucket="30-39",
            menopausal_status="PREMENOPAUSAL",
        )
        db.add(patient)

        # Populate a sample study, image, prediction, review for UC-73
        study = StudyModel(
            id="std-01",
            study_code="ST-2026-001",
            patient_id="pat-01",
            study_date=datetime.now(UTC).date().isoformat(),
            review_revision=1,
            status="REVIEWED",
        )
        db.add(study)

        # Create dummy image on disk
        img_file = tmp_path / "raw_image.jpg"
        import cv2
        import numpy as np
        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), dummy_img)

        import hashlib
        img_sha = hashlib.sha256(img_file.read_bytes()).hexdigest()

        image = ImageModel(
            id="img-01",
            study_id="std-01",
            filename="raw_image.jpg",
            raw_path=str(img_file),
            file_hash=img_sha,
            width=512,
            height=512,
            laterality="L",
        )
        db.add(image)

        # Binary RLE for 512x512
        rle = {"shape": [512, 512], "counts": [262144, 262144], "first_value": 0}
        pred = PredictionModel(
            id="pred-01",
            image_id="img-01",
            raw_mask_rle=rle,
            measurements={},
            model_version="unetplusplus_resnet34",
            provenance_json={"arch": "unetplusplus_resnet34"},
        )
        db.add(pred)

        review = ReviewModel(
            id="rev-01",
            image_id="img-01",
            prediction_id="pred-01",
            doctor_id="doctor_test",
            doctor_action="ACCEPTED_RAW",
            verified_mask_rle=rle,
            is_official_ground_truth=True,
            lesion_type="CYST",
            created_at=datetime.now(UTC),
        )
        db.add(review)
        db.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    doc_token = create_access_token({"sub": "doctor_test", "role": "DOCTOR"})
    admin_token = create_access_token({"sub": "admin_test", "role": "ADMIN"})
    tech_token = create_access_token({"sub": "tech_test", "role": "TECHNICIAN"})

    yield {
        "client": client,
        "engine": engine,
        "doc_headers": {"Authorization": f"Bearer {doc_token}"},
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "tech_headers": {"Authorization": f"Bearer {tech_token}"},
    }

    app.dependency_overrides.clear()


# ==========================================
# UC-73: Research Export ZIP Policy Tests
# ==========================================

def test_uc73_export_rejected_without_patient_consent(test_setup):
    client = test_setup["client"]
    headers = test_setup["doc_headers"]

    payload = {
        "review_ids": ["rev-01"],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": False,
    }
    resp = client.post("/api/cases/std-01/research-export", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "recorded participant consent" in resp.json()["detail"]


def test_uc73_export_rejected_with_empty_ethics_code(test_setup):
    client = test_setup["client"]
    headers = test_setup["doc_headers"]

    payload = {
        "review_ids": ["rev-01"],
        "expected_revision": 1,
        "ethics_approval_code": "   ",
        "patient_consent_confirmed": True,
    }
    resp = client.post("/api/cases/std-01/research-export", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "research approval code" in resp.json()["detail"]


def test_uc73_export_fails_closed_with_unverified_self_attestations(test_setup):
    client = test_setup["client"]
    headers = test_setup["doc_headers"]

    payload = {
        "review_ids": ["rev-01"],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post("/api/cases/std-01/research-export", json=payload, headers=headers)
    assert resp.status_code == 501
    assert "disabled" in resp.json()["detail"]


def test_uc73_export_rejected_when_ethics_code_missing(test_setup):
    client = test_setup["client"]
    headers = test_setup["doc_headers"]

    payload = {
        "review_ids": ["rev-01"],
        "expected_revision": 1,
        "patient_consent_confirmed": True,
    }
    resp = client.post("/api/cases/std-01/research-export", json=payload, headers=headers)
    assert resp.status_code == 422


def test_uc73_export_rejected_when_consent_omitted(test_setup):
    client = test_setup["client"]
    headers = test_setup["doc_headers"]

    # Omitting patient_consent_confirmed should default to False and be rejected
    payload = {
        "review_ids": ["rev-01"],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
    }
    resp = client.post("/api/cases/std-01/research-export", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "recorded participant consent" in resp.json()["detail"]


# ==========================================
# UC-74: Admin Ground Truth Export Policy Tests
# ==========================================

def test_uc74_export_rejected_for_non_admin_roles(test_setup):
    client = test_setup["client"]
    doc_headers = test_setup["doc_headers"]
    tech_headers = test_setup["tech_headers"]

    # DOCTOR must be forbidden
    resp_doc = client.get("/api/admin/export-ground-truth?ethics_approval_code=UNVERIFIED-USER-INPUT&consent_confirmed=true", headers=doc_headers)
    assert resp_doc.status_code == 403

    # TECHNICIAN must be forbidden
    resp_tech = client.get("/api/admin/export-ground-truth?ethics_approval_code=UNVERIFIED-USER-INPUT&consent_confirmed=true", headers=tech_headers)
    assert resp_tech.status_code == 403


def test_uc74_export_fails_closed_even_when_request_self_attests_approval_and_consent(test_setup):
    client = test_setup["client"]
    admin_headers = test_setup["admin_headers"]

    resp = client.get(
        "/api/admin/export-ground-truth?split=test&ethics_approval_code=UNVERIFIED&consent_confirmed=true",
        headers=admin_headers,
    )
    assert resp.status_code == 501
    assert "disabled" in resp.json()["detail"]
    assert "patient-level split provenance" in resp.json()["detail"]


# ==========================================
# UC-75: Evaluation Images Download Policy Tests
# ==========================================

def test_uc75_anonymous_blocked_from_evaluation_samples(test_setup):
    client = test_setup["client"]
    # Anonymous request without Authorization header
    resp = client.get("/api/evaluation/samples/43/workstation-bundle")
    assert resp.status_code == 401

    resp_download = client.get("/api/evaluation/samples/43/download/image")
    assert resp_download.status_code == 401


def test_uc75_authenticated_doctor_is_blocked_from_unverified_legacy_archive(test_setup):
    client = test_setup["client"]
    doc_headers = test_setup["doc_headers"]

    # Historical benchmark data is unavailable until its source provenance is reviewed.
    resp_bundle = client.get("/api/evaluation/samples/43/workstation-bundle", headers=doc_headers)
    assert resp_bundle.status_code == 503
    assert "provenance" in resp_bundle.json()["detail"].lower()

    for art in ["image", "ground_truth", "prediction", "overlay"]:
        resp_art = client.get(f"/api/evaluation/samples/43/download/{art}", headers=doc_headers)
        assert resp_art.status_code == 503
        assert "provenance" in resp_art.json()["detail"].lower()

    resp_invalid = client.get("/api/evaluation/samples/43/download/invalid_type", headers=doc_headers)
    assert resp_invalid.status_code == 422

    resp_missing = client.get("/api/evaluation/samples/999999/download/image", headers=doc_headers)
    assert resp_missing.status_code == 503
