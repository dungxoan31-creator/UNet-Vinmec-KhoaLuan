"""Authorization, atomic case creation, and bounded case-list queries."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers import cases
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
from backend.schemas.schemas import CreateCaseRequest


def test_delete_case_requires_admin_even_with_doctor_token(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-case-delete-signing-key-1234567890")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-password")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
    engine = create_engine(f"sqlite:///{tmp_path / 'roles.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            UserModel(id="doctor", username="doctor", full_name="Doctor", role="DOCTOR"),
            UserModel(id="admin", username="admin", full_name="Admin", role="ADMIN"),
            PatientModel(id="patient", anonymized_pid="PID-DELETE"),
            StudyModel(id="study", patient_id="patient", study_date="2026-10-11"),
        ])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            assert client.delete("/api/cases/study").status_code == 401
            doctor = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-test-password"})
            assert doctor.status_code == 200
            doctor_headers = {"Authorization": f"Bearer {doctor.json()['access_token']}"}
            assert client.delete("/api/cases/study", headers=doctor_headers).status_code == 403
            with Session(engine) as db:
                assert db.get(StudyModel, "study") is not None
            admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin-test-password"})
            assert admin.status_code == 200
            admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
            assert client.delete("/api/cases/study", headers=admin_headers).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_failed_study_insert_rolls_back_new_patient(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'atomic.db'}")
    Base.metadata.create_all(engine)

    def fail_study_insert(_mapper, _connection, _target):
        raise RuntimeError("simulated study insert failure")

    event.listen(StudyModel, "before_insert", fail_study_insert)
    try:
        with Session(engine) as db:
            with pytest.raises(RuntimeError, match="study insert failure"):
                cases.create_new_case(CreateCaseRequest(patient_id="PID-ATOMIC"), db=db)
            assert db.is_active, "The failed transaction must be rolled back explicitly"
            assert db.query(PatientModel).filter_by(anonymized_pid="PID-ATOMIC").first() is None
            assert db.query(StudyModel).count() == 0
    finally:
        event.remove(StudyModel, "before_insert", fail_study_insert)
        engine.dispose()


def test_case_list_uses_bounded_queries_for_related_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'list.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for number in range(5):
            patient_id, study_id, image_id = f"patient-{number}", f"study-{number}", f"image-{number}"
            db.add(PatientModel(id=patient_id, anonymized_pid=f"PID-{number}"))
            db.add(StudyModel(id=study_id, patient_id=patient_id, study_date="2026-10-11"))
            db.add(ImageModel(id=image_id, study_id=study_id, filename="image.png", raw_path="image.png"))
            db.add(PredictionModel(id=f"prediction-{number}", image_id=image_id,
                                   raw_mask_rle={}, measurements={}))
            db.add(ReviewModel(id=f"review-{number}", image_id=image_id, verified_mask_rle={}))
        db.commit()
    selects = []

    def count_selects(_conn, _cursor, statement, _params, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        with Session(engine) as db:
            rows = cases.list_cases(db=db)
        assert len(rows) == 5
        assert all(row["doctor_action"] == "ACCEPTED_RAW" for row in rows)
        assert len(selects) <= 4, f"Expected bounded eager loads, got {len(selects)} SELECTs"
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
        engine.dispose()
