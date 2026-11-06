import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import numpy as np

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import UPLOAD_DIR
from backend.app.main import app
from backend.core.patient_identity import patient_id_digest
from backend.db.database import PatientModel, SessionLocal, StudyModel
from backend.services.patient_identity import get_or_create_patient
from tests.helpers.fixture_factory import create_test_facility


def test_same_source_id_in_two_facilities_has_distinct_patient_records():
    source_pid = f"LOCAL-{uuid4().hex}"
    with SessionLocal() as db:
        facility_a = create_test_facility(db, f"fac-a-{uuid4().hex[:8]}")
        facility_b = create_test_facility(db, f"fac-b-{uuid4().hex[:8]}")

        patient_a = get_or_create_patient(db, source_pid, facility_id=facility_a.id)
        patient_b = get_or_create_patient(db, source_pid, facility_id=facility_b.id)
        same_facility_patient = get_or_create_patient(db, source_pid, facility_id=facility_a.id)

        assert patient_a.id != patient_b.id
        assert patient_a.id == same_facility_patient.id
        assert patient_a.facility_id == facility_a.id
        assert patient_b.facility_id == facility_b.id
        assert patient_a.source_pid_hmac == patient_id_digest(source_pid, facility_id=facility_a.id)
        assert patient_b.source_pid_hmac == patient_id_digest(source_pid, facility_id=facility_b.id)


def test_case_intake_pseudonymizes_and_reuses_source_patient_id(doctor_access, caplog):
    source_pid = "937142809"

    with TestClient(app) as client:
        first = client.post("/api/cases", json={"patient_id": source_pid, "study_date": "2026-10-21"},
                            headers={"Idempotency-Key": str(uuid4())})
    with caplog.at_level(logging.INFO), TestClient(app) as client:
        second = client.post("/api/cases", json={"patient_id": source_pid, "study_date": "2026-10-21"},
                             headers={"Idempotency-Key": str(uuid4())})
        persisted = client.get(f"/api/cases/{first.json()['study_id']}")
        source_search = client.post("/api/cases/search", json={"search": source_pid})
        url_search = client.get("/api/cases", params={"search": first.json()["study_code"]})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert source_search.status_code == 200, source_search.text
    assert url_search.status_code == 200, url_search.text
    first_data = first.json()
    second_data = second.json()
    assert first_data["patient_id"].startswith("SYN-")
    assert first_data["patient_id"] != source_pid
    assert second_data["patient_id"] == first_data["patient_id"]
    assert first_data["visit_no"].isascii() and first_data["visit_no"].isdigit()
    assert len(first_data["visit_no"]) == 6
    assert second_data["visit_no"] != first_data["visit_no"]
    assert persisted.status_code == 200
    assert persisted.json()["patient_id"] == first_data["patient_id"]
    assert persisted.json()["visit_no"] == first_data["visit_no"]
    assert len(source_search.json()) >= 2
    assert source_pid not in str(first.request.url)
    assert source_pid not in str(source_search.request.url)
    assert source_pid not in caplog.text
    assert source_pid not in {row["patient_id"] for row in url_search.json()}
    assert first_data["study_code"] in {row["study_code"] for row in url_search.json()}

    with SessionLocal() as db:
        patient = db.query(PatientModel).filter_by(anonymized_pid=first_data["patient_id"]).one()
        assert patient.source_pid_hmac == patient_id_digest(source_pid, facility_id="FAC-DEFAULT-TEST")
        assert patient.pid_hmac_key_id
        persisted_values = " ".join(str(value) for value in vars(patient).values())
        assert source_pid not in persisted_values


def test_legacy_upload_path_pseudonymizes_source_patient_id(doctor_access):
    source_pid = "LEGACY-UPLOAD-PID-SENTINEL-5f92"
    buffer = BytesIO()
    Image.fromarray(np.random.default_rng(42).integers(30, 200, (256, 256), dtype=np.uint8)).save(buffer, format="PNG")

    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            data={"anonymized_pid": source_pid},
            files={"file": ("patient-image.png", buffer.getvalue(), "image/png")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert source_pid not in response.text
    with SessionLocal() as db:
        study = db.get(StudyModel, payload["study_id"])
        assert study is not None
        patient = db.get(PatientModel, study.patient_id)
        assert patient is not None
        assert patient.anonymized_pid.startswith("SYN-")
        assert patient.source_pid_hmac == patient_id_digest(source_pid, facility_id="FAC-DEFAULT-TEST")
        assert source_pid not in " ".join(str(value) for value in vars(patient).values())


def test_legacy_upload_rejects_whitespace_only_pid_without_side_effects(doctor_access):
    buffer = BytesIO()
    Image.fromarray(np.random.default_rng(42).integers(30, 200, (256, 256), dtype=np.uint8)).save(buffer, format="PNG")
    upload_dir = Path(UPLOAD_DIR)
    files_before = {path.name for path in upload_dir.iterdir()}
    with SessionLocal() as db:
        patients_before = db.query(PatientModel).count()
        studies_before = db.query(StudyModel).count()

    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            data={"anonymized_pid": " \t\r\n "},
            files={"file": ("patient-image.png", buffer.getvalue(), "image/png")},
        )

    assert response.status_code == 422
    assert "PID" in response.json()["detail"]
    assert {path.name for path in upload_dir.iterdir()} == files_before
    with SessionLocal() as db:
        assert db.query(PatientModel).count() == patients_before
        assert db.query(StudyModel).count() == studies_before


def test_patient_pid_key_requires_a_separate_strong_secret(monkeypatch, tmp_path):
    from backend.core.patient_identity import patient_pid_secret

    from backend.app import config

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENVIRONMENT", "PRODUCTION")
    monkeypatch.delenv("APP_PATIENT_PID_HMAC_SECRET", raising=False)
    try:
        patient_pid_secret()
    except RuntimeError as exc:
        assert "APP_PATIENT_PID_HMAC_SECRET" in str(exc)
    else:
        raise AssertionError("Patient identity mapping must fail closed without its dedicated key")


def test_case_search_body_is_bounded_and_rejects_unknown_fields(doctor_access):
    with TestClient(app) as client:
        too_long = client.post("/api/cases/search", json={"search": "x" * 257})
        too_many = client.post("/api/cases/search", json={"limit": 101})
        unknown = client.post("/api/cases/search", json={"search": "SYN-", "include_raw": True})

    assert too_long.status_code == 422
    assert too_many.status_code == 422
    assert unknown.status_code == 422


def test_case_search_treats_sql_injection_payload_as_plain_text(doctor_access):
    import uuid

    marker = f"SQLI-CANARY-{uuid.uuid4().hex}"
    with TestClient(app) as client:
        created = client.post(
            "/api/cases",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "patient_id": f"{uuid.uuid4().int % 1_000_000_000:09d}",
                "study_code": marker,
                "study_date": "2026-10-29",
            },
        )
        assert created.status_code == 200, created.text

        normal = client.get("/api/cases", params={"search": marker})
        attack = client.get(
            "/api/cases",
            params={"search": f"' OR 1=1 -- {uuid.uuid4().hex}"},
        )

    assert normal.status_code == 200
    assert any(row["study_id"] == created.json()["study_id"] for row in normal.json())
    assert attack.status_code == 200
    assert attack.json() == [], "SQL syntax must remain a literal search string, not broaden the query."
