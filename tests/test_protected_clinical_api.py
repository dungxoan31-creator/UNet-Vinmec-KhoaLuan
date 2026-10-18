"""Clinical records and images require an authenticated account."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, UserModel, get_db


def test_clinical_api_requires_token_and_doctor_can_read_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-password")
    from backend.app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'protected.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="doctor-id", username="doctor", full_name="Doctor", role="DOCTOR"))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            for method, path in [
                ("GET", "/api/cases"),
                ("GET", "/api/stats"),
                ("POST", "/api/upload"),
                ("POST", "/api/review"),
                ("POST", "/api/v1/cdss/evaluate"),
                ("GET", "/api/evaluation/metrics"),
                ("GET", "/api/images/missing/viewer-source"),
            ]:
                assert client.request(method, path).status_code == 401, path

            login = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-test-password"})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            assert client.get("/api/cases", headers=headers).status_code == 200
            assert client.get("/api/stats", headers=headers).status_code == 200
            assert client.get("/api/health").status_code == 200
            assert client.get("/data/anything.png").status_code == 404
            foreign = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
            assert "access-control-allow-origin" not in foreign.headers

            # UAT-04: Admin token must be forbidden (403) from accessing clinical details and images
            with Session(engine) as db:
                db.add(UserModel(id="admin-id", username="admin", full_name="Admin", role="ADMIN"))
                db.commit()
            monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
            admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-test-password"})
            assert admin_login.status_code == 200
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

            assert client.get("/api/cases/any-study-id", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/source.png", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/viewer-source", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/mask.png", headers=admin_headers).status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
