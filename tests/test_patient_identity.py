from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import UPLOAD_DIR
from backend.app.main import app
from backend.core.patient_identity import patient_id_digest
from backend.db.database import PatientModel, SessionLocal, StudyModel


def test_case_intake_pseudonymizes_and_reuses_source_patient_id(doctor_access):
    source_pid = "EXTERNAL-PATIENT-SENTINEL-9f14d12a"

    with TestClient(app) as client:
        first = client.post("/api/cases", json={"patient_id": source_pid, "study_date": "2026-10-21"})
        second = client.post("/api/cases", json={"patient_id": source_pid, "study_date": "2026-10-21"})
        source_search = client.post("/api/cases/search", json={"search": source_pid})
        url_search = client.get("/api/cases", params={"search": source_pid})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert source_search.status_code == 200, source_search.text
    assert url_search.status_code == 200, url_search.text
    first_data = first.json()
    second_data = second.json()
    assert first_data["patient_id"].startswith("SYN-")
    assert first_data["patient_id"] != source_pid
    assert second_data["patient_id"] == first_data["patient_id"]
    assert len(source_search.json()) >= 2
    assert first_data["patient_id"] not in {row["patient_id"] for row in url_search.json()}

    with SessionLocal() as db:
        patient = db.query(PatientModel).filter_by(anonymized_pid=first_data["patient_id"]).one()
        assert patient.source_pid_hmac == patient_id_digest(source_pid)
        assert patient.pid_hmac_key_id
        persisted_values = " ".join(str(value) for value in vars(patient).values())
        assert source_pid not in persisted_values


def test_legacy_upload_path_pseudonymizes_source_patient_id(doctor_access):
    source_pid = "LEGACY-UPLOAD-PID-SENTINEL-5f92"
    buffer = BytesIO()
    Image.new("L", (64, 64), color=120).save(buffer, format="PNG")

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
        assert patient.source_pid_hmac == patient_id_digest(source_pid)
        assert source_pid not in " ".join(str(value) for value in vars(patient).values())


def test_legacy_upload_rejects_whitespace_only_pid_without_side_effects(doctor_access):
    buffer = BytesIO()
    Image.new("L", (64, 64), color=120).save(buffer, format="PNG")
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


def test_patient_pid_key_requires_a_separate_strong_secret(monkeypatch):
    from backend.core.patient_identity import patient_pid_secret

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
