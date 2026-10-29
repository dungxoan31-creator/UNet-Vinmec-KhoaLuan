from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.core.case_idempotency import case_create_idempotency_digest
from backend.core.patient_identity import patient_id_digest
from backend.db.database import Base, PatientModel, StudyModel, get_db


def test_simultaneous_case_creation_for_same_pid_creates_both_studies(
    tmp_path, doctor_access
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'case-create-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    patient_insert_barrier = Barrier(2)

    def synchronize_patient_inserts(_connection, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("INSERT INTO PATIENTS"):
            patient_insert_barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", synchronize_patient_inserts)
    payload = {
        "patient_id": "PID-CONCURRENT-CASE",
        "study_date": "2026-10-21",
        "active_ovary_side": "BOTH",
    }

    def create_case():
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post("/api/cases", json=payload, headers={"Idempotency-Key": str(uuid4())})

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(lambda _: create_case(), range(2)))

        assert [response.status_code for response in responses] == [200, 200], [
            (response.status_code, response.text) for response in responses
        ]
        assert len({response.json()["study_id"] for response in responses}) == 2
        visit_numbers = [response.json()["visit_no"] for response in responses]
        assert len(set(visit_numbers)) == 2
        assert all(value.isascii() and value.isdigit() and len(value) == 6 for value in visit_numbers)
        with Session(engine) as db:
            assert db.query(PatientModel).filter_by(source_pid_hmac=patient_id_digest(payload["patient_id"])).count() == 1
            assert db.query(StudyModel).count() == 2
            assert {study.visit_no for study in db.query(StudyModel).all()} == set(visit_numbers)
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_patient_inserts)
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_simultaneous_case_creation_with_same_idempotency_key_replays_one_study(
    tmp_path, doctor_access
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'case-idempotency-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    patient_insert_barrier = Barrier(2)

    def synchronize_patient_inserts(_connection, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("INSERT INTO PATIENTS"):
            patient_insert_barrier.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", synchronize_patient_inserts)
    key = uuid4()
    payload = {
        "patient_id": "PID-IDEMPOTENT-CONCURRENT",
        "study_date": "2026-10-29",
        "active_ovary_side": "BOTH",
    }
    headers = {"Idempotency-Key": str(key)}

    def create_case():
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post("/api/cases", json=payload, headers=headers)

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(lambda _: create_case(), range(2)))

        assert [response.status_code for response in responses] == [200, 200], [
            (response.status_code, response.text) for response in responses
        ]
        case_ids = [response.json()["study_id"] for response in responses]
        assert len(set(case_ids)) == 1
        visit_numbers = [response.json()["visit_no"] for response in responses]
        assert len(set(visit_numbers)) == 1
        with Session(engine) as db:
            digest = case_create_idempotency_digest(key, "test-doctor")
            assert db.query(StudyModel).filter_by(idempotency_key_digest=digest).count() == 1
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_patient_inserts)
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
