import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
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
)


@pytest.fixture
def r2_client_env():
    test_db = SessionLocal()
    prefix = uuid.uuid4().hex[:6]

    fac = FacilityModel(
        id=f"fac-{prefix}",
        facility_code=f"F-{prefix}".upper(),
        name=f"Hospital {prefix}",
        is_active=True,
    )
    test_db.add(fac)

    doc = UserModel(
        id=str(uuid.uuid4()),
        username=f"doc_{prefix}",
        full_name="Dr. Tester",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()

    token = create_access_token({"sub": doc.username, "uid": doc.id})
    client = TestClient(app)

    try:
        yield {
            "client": client,
            "fac": fac,
            "doc": doc,
            "token": token,
            "headers": {
                "Authorization": f"Bearer {token}",
            },
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_create_case_without_patient_id(r2_client_env):
    """POST /api/cases without patient_id succeeds with patient_id=None (R2 P1)."""
    client = r2_client_env["client"]
    headers = {**r2_client_env["headers"], "Idempotency-Key": str(uuid.uuid4())}
    db = r2_client_env["db"]

    payload = {
        "study_date": "2026-10-31",
        "active_ovary_side": "RIGHT",
        "study_code": f"STUDY-ANON-{r2_client_env['prefix']}",
    }

    resp = client.post("/api/cases", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["patient_id"] is None
    study_id = data["study_id"]

    # Verify database model
    study = db.get(StudyModel, study_id)
    assert study is not None
    assert study.patient_id is None
    assert study.patient is None

    # Verify GET /api/cases/{study_id}
    detail_resp = client.get(f"/api/cases/{study_id}", headers=r2_client_env["headers"])
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["patient_id"] is None
    assert detail["patient_age"] is None
    assert detail["study_code"] == f"STUDY-ANON-{r2_client_env['prefix']}"


def test_create_case_with_null_patient_id(r2_client_env):
    """POST /api/cases with patient_id=None succeeds with patient_id=None."""
    client = r2_client_env["client"]
    headers = {**r2_client_env["headers"], "Idempotency-Key": str(uuid.uuid4())}
    db = r2_client_env["db"]

    payload = {
        "patient_id": None,
        "study_date": "2026-10-31",
        "active_ovary_side": "LEFT",
        "contralateral_status": "NORMAL",
    }

    resp = client.post("/api/cases", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["patient_id"] is None
    study_id = data["study_id"]

    study = db.get(StudyModel, study_id)
    assert study is not None
    assert study.patient_id is None


def test_create_case_legacy_with_valid_patient_id(r2_client_env):
    """POST /api/cases with valid patient_id persists and resolves patient pseudonym (Backward Compatibility)."""
    client = r2_client_env["client"]
    headers = {**r2_client_env["headers"], "Idempotency-Key": str(uuid.uuid4())}
    db = r2_client_env["db"]

    source_pid = f"{int(r2_client_env['prefix'], 16):09d}"
    payload = {
        "patient_id": source_pid,
        "study_date": "2026-10-31",
        "patient_age": "30-34",
        "active_ovary_side": "BOTH",
    }

    resp = client.post("/api/cases", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["patient_id"] is not None
    assert data["patient_id"] != source_pid  # Anonymized pseudonym
    study_id = data["study_id"]

    study = db.get(StudyModel, study_id)
    assert study is not None
    assert study.patient_id is not None
    assert study.patient is not None
    assert study.patient.age_bucket == "30-34"

    detail_resp = client.get(f"/api/cases/{study_id}", headers=r2_client_env["headers"])
    assert detail_resp.status_code == 200
    assert detail_resp.json()["patient_id"] == study.patient.anonymized_pid
    assert detail_resp.json()["patient_age"] == "30-34"


def test_list_and_search_cases_with_anonymous_study(r2_client_env):
    """GET /api/cases and POST /api/cases/search return anonymous studies without error."""
    client = r2_client_env["client"]
    headers = {**r2_client_env["headers"], "Idempotency-Key": str(uuid.uuid4())}

    anon_code = f"CODE-ANON-{r2_client_env['prefix']}"
    payload = {
        "study_code": anon_code,
        "study_date": "2026-10-31",
        "active_ovary_side": "RIGHT",
    }
    create_resp = client.post("/api/cases", headers=headers, json=payload)
    assert create_resp.status_code == 200
    study_id = create_resp.json()["study_id"]

    # List cases
    list_resp = client.get("/api/cases", headers=r2_client_env["headers"])
    assert list_resp.status_code == 200
    items = list_resp.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    found = next((item for item in items if item["study_id"] == study_id), None)
    assert found is not None
    assert found["patient_id"] is None
    assert found["patient_age"] is None

    # Search cases
    search_resp = client.post(
        "/api/cases/search",
        headers=r2_client_env["headers"],
        json={"search": anon_code},
    )
    assert search_resp.status_code == 200
    search_items = search_resp.json()
    assert any(item["study_id"] == study_id for item in search_items)


def test_idempotent_replay_without_patient_id(r2_client_env):
    """Replaying intake without patient_id returns same study with patient_id=None."""
    client = r2_client_env["client"]
    idempotency_key = str(uuid.uuid4())
    headers = {**r2_client_env["headers"], "Idempotency-Key": idempotency_key}

    payload = {
        "study_date": "2026-10-31",
        "active_ovary_side": "LEFT",
    }
    resp1 = client.post("/api/cases", headers=headers, json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["patient_id"] is None

    # Replay
    resp2 = client.post("/api/cases", headers=headers, json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["study_id"] == data1["study_id"]
    assert data2["patient_id"] is None
    assert "tiếp tục dùng ca này" in data2["message"]
