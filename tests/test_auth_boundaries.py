"""A caller cannot gain admin rights by choosing a role or omitting credentials."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, UserModel, get_db


@pytest.mark.parametrize("token_kind", ["missing_exp", "missing_iat", "expired"])
def test_access_tokens_require_valid_lifetime_claims(tmp_path, monkeypatch, token_kind):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from backend.app.main import app
    from backend.app.security import JWT_ALGORITHM

    engine = create_engine(f"sqlite:///{tmp_path / 'token-claims.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = UserModel(id="doctor-id", username="doctor", full_name="Doctor", role="DOCTOR")
        if token_kind == "missing_iat":
            user.tokens_revoked_at = datetime.now(UTC)
        db.add(user)
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    if token_kind == "expired":
        from backend.app.security import create_access_token

        token = create_access_token(
            {"sub": "doctor", "uid": "doctor-id", "token_version": 1},
            expires_delta=timedelta(seconds=-1),
        )
    else:
        claims = {"sub": "doctor", "uid": "doctor-id"}
        if token_kind != "missing_iat":
            claims["token_version"] = 1
        now = datetime.now(UTC)
        if token_kind == "missing_exp":
            claims["iat"] = now
        else:
            claims["exp"] = now + timedelta(minutes=5)
        token = jwt.encode(claims, "test-only-long-random-signing-secret-123456", algorithm=JWT_ALGORITHM)

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/auth/current-user", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


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
            doctor_headers = {"Authorization": f"Bearer {doctor_token}"}
            assert client.get("/api/admin/models", headers=doctor_headers).status_code == 403
            for method, path, payload in [
                ("GET", "/api/admin/audit-events", None),
                ("GET", "/api/admin/cases", None),
                ("POST", "/api/admin/backups/create", None),
                ("PUT", "/api/admin/settings", {"report_header": "Doctor must not update this"}),
            ]:
                response = client.request(method, path, headers=doctor_headers, json=payload)
                assert response.status_code == 403, (method, path, response.status_code, response.text)
            admin = client.post("/api/auth/login", json={"username": "admin", "password": "admin-test-password"})
            assert admin.status_code == 200
            admin_token = admin.json()["access_token"]
            assert client.get("/api/admin/models", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
