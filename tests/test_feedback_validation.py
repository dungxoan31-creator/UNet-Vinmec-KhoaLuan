from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers.auth import create_access_token
from backend.db.database import AuditLogModel, Base, UserModel, get_db


def _client_with_doctor(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-feedback-signing-secret-123456")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'feedback.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="feedback-doctor", username="feedback-doctor", full_name="Doctor", role="DOCTOR"))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    token = create_access_token({"sub": "feedback-doctor", "uid": "feedback-doctor"})
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, engine


def test_feedback_rejects_blank_or_non_string_fields(tmp_path, monkeypatch):
    client, engine = _client_with_doctor(tmp_path, monkeypatch)
    try:
        for payload in (
            {"title": "   ", "message": "description"},
            {"title": "title", "message": "  "},
            {"title": None, "message": "description"},
            {"title": 123, "message": "description"},
        ):
            assert client.post("/api/feedback", json=payload).status_code == 422
        with Session(engine) as db:
            assert db.query(AuditLogModel).filter_by(action_type="USER_FEEDBACK").count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_feedback_rejects_oversized_and_unexpected_fields(tmp_path, monkeypatch):
    client, engine = _client_with_doctor(tmp_path, monkeypatch)
    try:
        assert client.post("/api/feedback", json={"title": "t" * 121, "message": "description"}).status_code == 422
        assert client.post("/api/feedback", json={"title": "title", "message": "m" * 2001}).status_code == 422
        assert client.post(
            "/api/feedback",
            json={"title": "title", "message": "description", "actor_id": "admin"},
        ).status_code == 422
        with Session(engine) as db:
            assert db.query(AuditLogModel).filter_by(action_type="USER_FEEDBACK").count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()
