from fastapi.testclient import TestClient
import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.security import create_access_token
from backend.db.database import Base, FacilityModel, PatientDirectoryModel, StudyModel, UserModel, get_db


@pytest.fixture
def patient_directory_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "isolated-patient-directory-test-secret-123456")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'patient-directory.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        facility_a = FacilityModel(id="DIR-FAC-A", facility_code="DIR-A", name="Directory A", is_active=True)
        facility_b = FacilityModel(id="DIR-FAC-B", facility_code="DIR-B", name="Directory B", is_active=True)
        doctor_a = UserModel(
            id="dir-doctor-a", username="dir-doctor-a", full_name="Doctor A", role="DOCTOR",
            facility_id=facility_a.id, is_active=True,
        )
        doctor_b = UserModel(
            id="dir-doctor-b", username="dir-doctor-b", full_name="Doctor B", role="DOCTOR",
            facility_id=facility_b.id, is_active=True,
        )
        doctor_unassigned = UserModel(
            id="dir-doctor-unassigned", username="dir-doctor-unassigned", full_name="Doctor Unassigned",
            role="DOCTOR", facility_id=None, is_active=True,
        )
        db.add_all([facility_a, facility_b, doctor_a, doctor_b, doctor_unassigned])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    client = TestClient(app)
    try:
        yield {
            "client": client,
            "engine": engine,
            "token_a": create_access_token({"sub": "dir-doctor-a", "uid": "dir-doctor-a"}),
            "token_b": create_access_token({"sub": "dir-doctor-b", "uid": "dir-doctor-b"}),
            "token_unassigned": create_access_token({"sub": "dir-doctor-unassigned", "uid": "dir-doctor-unassigned"}),
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_patient_directory_is_facility_scoped_and_uses_optimistic_versions(patient_directory_env):
    env = patient_directory_env
    client = env["client"]
    headers_a = {"Authorization": f"Bearer {env['token_a']}"}
    headers_b = {"Authorization": f"Bearer {env['token_b']}"}

    created = client.post(
        "/api/patient-directory",
        headers=headers_a,
        json={"display_name": "Synthetic Patient Alpha", "birth_year": 1988},
    )
    patient = created.json()
    listed_a = client.get("/api/patient-directory", headers=headers_a)
    listed_b = client.get("/api/patient-directory", headers=headers_b)
    update_a = client.put(
        f"/api/patient-directory/{patient.get('id', 'missing')}",
        headers=headers_a,
        json={"display_name": "Synthetic Patient Alpha Updated", "expected_version": 1},
    )
    stale_update = client.put(
        f"/api/patient-directory/{patient.get('id', 'missing')}",
        headers=headers_a,
        json={"display_name": "Stale Overwrite", "expected_version": 1},
    )
    cross_facility_update = client.put(
        f"/api/patient-directory/{patient.get('id', 'missing')}",
        headers=headers_b,
        json={"display_name": "Cross-Facility Overwrite", "expected_version": 2},
    )
    deleted = client.delete(
        f"/api/patient-directory/{patient.get('id', 'missing')}?expected_version=2",
        headers=headers_a,
    )
    reopened_list = client.get("/api/patient-directory", headers=headers_a)

    assert created.status_code == 201, created.text
    assert patient["version"] == 1
    assert "source_patient_id" not in patient
    assert listed_a.status_code == listed_b.status_code == 200
    assert len(listed_a.json()["items"]) == 1
    assert listed_b.json()["items"] == []
    assert update_a.status_code == 200, update_a.text
    assert update_a.json()["version"] == 2
    assert stale_update.status_code == 409
    assert cross_facility_update.status_code == 404
    assert deleted.status_code == 204
    assert reopened_list.json()["items"] == []

    with Session(env["engine"]) as db:
        row = db.execute(
            text("SELECT display_name, is_active FROM patient_directory WHERE id = :id"),
            {"id": patient["id"]},
        ).one()
        assert row.display_name == "Synthetic Patient Alpha Updated"
        assert not row.is_active


def test_patient_directory_rejects_raw_identifier_fields_and_unassigned_users(patient_directory_env):
    client = patient_directory_env["client"]
    headers_a = {"Authorization": f"Bearer {patient_directory_env['token_a']}"}
    headers_unassigned = {"Authorization": f"Bearer {patient_directory_env['token_unassigned']}"}
    invalid = client.post(
        "/api/patient-directory",
        headers=headers_a,
        json={"display_name": "Synthetic Patient", "source_patient_id": "REAL-PID-MUST-NOT-BE-STORED"},
    )
    denied = client.post(
        "/api/patient-directory",
        headers=headers_unassigned,
        json={"display_name": "Unassigned User Record"},
    )

    assert invalid.status_code == 422
    assert denied.status_code == 403


def test_patient_directory_search_and_pagination_are_facility_scoped(patient_directory_env):
    client = patient_directory_env["client"]
    headers_a = {"Authorization": f"Bearer {patient_directory_env['token_a']}"}
    headers_b = {"Authorization": f"Bearer {patient_directory_env['token_b']}"}
    for name in ("Directory Alpha", "Directory Beta", "Directory Gamma"):
        response = client.post(
            "/api/patient-directory",
            headers=headers_a,
            json={"display_name": name},
        )
        assert response.status_code == 201, response.text

    page = client.get("/api/patient-directory?limit=1&offset=1", headers=headers_a)
    searched = client.get("/api/patient-directory?search=Beta", headers=headers_a)
    cross_facility = client.get("/api/patient-directory?search=Beta", headers=headers_b)

    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["display_name"] == "Directory Beta"
    assert cross_facility.json()["total"] == 0
    assert cross_facility.json()["items"] == []


def test_case_links_facility_directory_record_and_rejects_cross_facility_reference(patient_directory_env):
    env = patient_directory_env
    client = env["client"]
    headers_a = {"Authorization": f"Bearer {env['token_a']}", "Idempotency-Key": str(uuid4())}
    headers_b = {"Authorization": f"Bearer {env['token_b']}", "Idempotency-Key": str(uuid4())}
    patient_response = client.post(
        "/api/patient-directory",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={"display_name": "Directory Linked Patient", "birth_year": 1990},
    )
    patient_id = patient_response.json()["id"]

    case_a = client.post(
        "/api/cases",
        headers=headers_a,
        json={
            "patient_directory_id": patient_id,
            "patient_age": "34",
            "study_date": "2026-11-04",
            "active_ovary_side": "UNKNOWN",
        },
    )
    case_b = client.post(
        "/api/cases",
        headers=headers_b,
        json={
            "patient_directory_id": patient_id,
            "study_date": "2026-11-04",
            "active_ovary_side": "UNKNOWN",
        },
    )

    assert patient_response.status_code == 201, patient_response.text
    assert case_a.status_code == 200, case_a.text
    assert case_a.json()["patient_directory_id"] == patient_id
    assert case_a.json()["patient_name"] == "Directory Linked Patient"
    assert case_a.json()["patient_age"] == "34"
    assert case_b.status_code == 404
    with Session(env["engine"]) as db:
        study = db.query(StudyModel).filter_by(id=case_a.json()["study_id"]).one()
        directory_patient = db.query(PatientDirectoryModel).filter_by(id=patient_id).one()
        assert study.patient_directory_id == patient_id
        assert study.patient_age == "34"
        assert study.facility_id == directory_patient.facility_id == "DIR-FAC-A"
        assert study.patient_id is None
        assert db.query(StudyModel).count() == 1


def test_concurrent_patient_directory_updates_do_not_overwrite_each_other(patient_directory_env):
    env = patient_directory_env
    client = env["client"]
    created = client.post(
        "/api/patient-directory",
        headers={"Authorization": f"Bearer {env['token_a']}"},
        json={"display_name": "Concurrent Original", "birth_year": 1991},
    )
    patient_id = created.json()["id"]
    select_barrier = Barrier(2)

    def synchronize_reads(_connection, _cursor, statement, parameters, _context, _executemany):
        normalized = statement.lower()
        values = parameters.values() if isinstance(parameters, dict) else parameters
        if normalized.startswith("update patient_directory") and patient_id in values:
            select_barrier.wait(timeout=10)

    event.listen(env["engine"], "before_cursor_execute", synchronize_reads)

    def update(name):
        with TestClient(client.app) as concurrent_client:
            return concurrent_client.put(
                f"/api/patient-directory/{patient_id}",
                headers={"Authorization": f"Bearer {env['token_a']}"},
                json={"display_name": name, "expected_version": 1},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(update, ["Concurrent Edit A", "Concurrent Edit B"]))
    finally:
        event.remove(env["engine"], "before_cursor_execute", synchronize_reads)

    assert sorted(response.status_code for response in responses) == [200, 409], [
        (response.status_code, response.text) for response in responses
    ]
    with Session(env["engine"]) as db:
        saved = db.get(PatientDirectoryModel, patient_id)
        assert saved.version == 2
        assert saved.display_name in {"Concurrent Edit A", "Concurrent Edit B"}
