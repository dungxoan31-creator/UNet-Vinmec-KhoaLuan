"""Regression tests for audit fixes - CRITICAL issues."""
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.auth import create_reset_token


def test_be_03_reset_token_cannot_be_reused(tmp_path, monkeypatch):
    """BE-03: Reset password token must be strictly one-time use and cannot be reused."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be03.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="u1", username="doctor", full_name="BS. Test", role="DOCTOR", is_active=True))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        token = create_reset_token("doctor")
        with TestClient(app) as client:
            # First reset attempt with token: MUST succeed (200)
            resp1 = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "firstpassword123"},
            )
            assert resp1.status_code == 200, f"First reset failed: {resp1.text}"

            # Second reset attempt with same token: MUST BE REJECTED with 400
            resp2 = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "secondpassword456"},
            )
            assert resp2.status_code == 400, (
                f"BE-03 VULNERABILITY DETECTED: Reused reset token succeeded! Status: {resp2.status_code}, Body: {resp2.text}"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
