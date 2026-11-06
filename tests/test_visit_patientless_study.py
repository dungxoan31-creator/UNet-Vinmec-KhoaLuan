import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    PatientModel,
    SessionLocal,
    StudyModel,
    UserModel,
    VisitModel,
)
from backend.services.patient_identity import get_or_create_patient


@pytest.fixture
def visit_sync_env():
    prefix = uuid.uuid4().hex[:8]
    test_db = SessionLocal()

    fac = FacilityModel(
        id=f"FAC-VS-{prefix}",
        name=f"Facility Sync {prefix}",
        facility_code=f"FVS-{prefix}",
        is_active=True,
    )
    test_db.add(fac)
    test_db.commit()

    pwd_hash = hash_password("SecurePass123!")

    doc = UserModel(
        id=f"doc-vs-{prefix}",
        username=f"doctor_vs_{prefix}",
        full_name="Dr. Sync",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()

    token_doc = create_access_token({"sub": doc.username, "role": "DOCTOR", "facility_id": fac.id})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "fac": fac,
            "doc": doc,
            "token_doc": token_doc,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_visit_for_patientless_study_with_pid(visit_sync_env):
    """Linking visit with PID to a patientless study assigns the same PatientModel to both atomically."""
    client = visit_sync_env["client"]
    db = visit_sync_env["db"]
    fac = visit_sync_env["fac"]
    token_doc = visit_sync_env["token_doc"]
    prefix = visit_sync_env["prefix"]

    # Create patientless study
    study = StudyModel(
        id=f"study-pl-1-{prefix}",
        study_code=f"ST-PL-1-{prefix}",
        study_date="2026-11-01",
        facility_id=fac.id,
        patient_id=None,
        status="PENDING",
    )
    db.add(study)
    db.commit()

    resp = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {token_doc}"},
        json={
            "facility_id": fac.id,
            "study_id": study.id,
            "patient_id": f"PATIENT-{prefix}-1",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # Check visit
    visit_id = data["id"]
    visit = db.get(VisitModel, visit_id)
    assert visit is not None
    assert visit.patient_id is not None

    # Check study updated with the same patient
    db.refresh(study)
    assert study.patient_id == visit.patient_id
    assert study.visit_id == visit.id


def test_visit_for_patientless_study_without_pid(visit_sync_env):
    """Linking visit without PID to a patientless study keeps both patientless."""
    client = visit_sync_env["client"]
    db = visit_sync_env["db"]
    fac = visit_sync_env["fac"]
    token_doc = visit_sync_env["token_doc"]
    prefix = visit_sync_env["prefix"]

    study = StudyModel(
        id=f"study-pl-2-{prefix}",
        study_code=f"ST-PL-2-{prefix}",
        study_date="2026-11-01",
        facility_id=fac.id,
        patient_id=None,
        status="PENDING",
    )
    db.add(study)
    db.commit()

    resp = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {token_doc}"},
        json={
            "facility_id": fac.id,
            "study_id": study.id,
            "patient_id": None,
        },
    )
    assert resp.status_code == 201, resp.text

    # Both remain patientless
    db.refresh(study)
    assert study.patient_id is None
    assert study.visit_id is not None

    visit = db.get(VisitModel, study.visit_id)
    assert visit is not None
    assert visit.patient_id is None


def test_visit_for_study_with_existing_patient_hmac_validation(visit_sync_env):
    """When study already has a patient, valid PID matches via HMAC; conflicting PID raises 422."""
    client = visit_sync_env["client"]
    db = visit_sync_env["db"]
    fac = visit_sync_env["fac"]
    token_doc = visit_sync_env["token_doc"]
    prefix = visit_sync_env["prefix"]

    raw_pid = f"PATIENT-REAL-{prefix}"
    patient = get_or_create_patient(db, raw_pid, facility_id=fac.id)

    study = StudyModel(
        id=f"study-pl-3-{prefix}",
        study_code=f"ST-PL-3-{prefix}",
        study_date="2026-11-01",
        facility_id=fac.id,
        patient_id=patient.id,
        status="PENDING",
    )
    db.add(study)
    db.commit()

    # 1. Matching PID
    resp_ok = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {token_doc}"},
        json={
            "facility_id": fac.id,
            "study_id": study.id,
            "patient_id": raw_pid,
        },
    )
    assert resp_ok.status_code == 201, resp_ok.text

    # 2. Conflicting PID -> 422
    resp_conflict = client.post(
        "/api/v1/visits",
        headers={"Authorization": f"Bearer {token_doc}"},
        json={
            "facility_id": fac.id,
            "study_id": study.id,
            "patient_id": "DIFFERENT-PATIENT-ID",
        },
    )
    assert resp_conflict.status_code == 422, resp_conflict.text
