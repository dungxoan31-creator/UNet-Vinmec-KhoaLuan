"""A caller cannot gain admin rights by choosing a role or omitting credentials."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, UserModel, get_db


def test_admin_requires_password_and_admin_token(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-password")
    from backend.app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            UserModel(id="admin-id", username="admin", full_name="Admin", role="ADMIN"),
            UserModel(id="doctor-id", username="doctor", full_name="Doctor", role="DOCTOR"),
        ])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            assert client.get("/api/admin/models").status_code == 401
            assert client.post("/api/auth/switch-role", json={"role": "ADMIN"}).status_code in (404, 410)
            assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
            doctor = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-test-password"})
            assert doctor.status_code == 200
            doctor_token = doctor.json()["access_token"]
            assert client.get("/api/admin/models", headers={"Authorization": f"Bearer {doctor_token}"}).status_code == 403
            admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin-test-password"})
            assert admin.status_code == 200
            admin_token = admin.json()["access_token"]
            assert client.get("/api/admin/models", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
