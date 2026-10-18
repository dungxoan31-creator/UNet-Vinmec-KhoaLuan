"""Regression tests for audit fixes - MINOR issues."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers.auth import create_access_token
from backend.db.database import Base, UserModel, get_db


def test_be_24_create_user_empty_payload_rejects_with_422(tmp_path, monkeypatch):
    """BE-24: Creating user with empty payload or blank username must return HTTP 422, not HTTP 200 SUCCESS."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-long-random-string-for-minor-fixes-123456")
    db_file = tmp_path / "be24.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = UserModel(
            id="admin-be24",
            username="admin_be24",
            full_name="Admin Test",
            role="ADMIN",
            password_hash="fakehash",
            is_active=True,
        )
        session.add(admin)
        session.commit()

    token = create_access_token({"sub": "admin_be24", "uid": "admin-be24", "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    def override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # Empty body
        res = client.post("/api/admin/users", json={}, headers=headers)
        assert res.status_code == 422, f"BE-24 VULNERABILITY: Empty payload returned {res.status_code} instead of 422!"
        assert "không được để trống" in res.json().get("detail", "")

        # Blank username
        res2 = client.post("/api/admin/users", json={"username": "   "}, headers=headers)
        assert res2.status_code == 422
        assert "không được để trống" in res2.json().get("detail", "")

        # Verify no users were created
        with Session(engine) as s:
            assert s.query(UserModel).count() == 1  # Only the admin
    finally:
        app.dependency_overrides.pop(get_db, None)
