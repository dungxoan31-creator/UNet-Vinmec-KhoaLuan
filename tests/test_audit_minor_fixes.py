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


def test_be_11_audit_events_export_endpoint(tmp_path, monkeypatch):
    """BE-11: UI calls /api/admin/audit-events/export which must exist, require admin, and return filtered export data."""
    from datetime import datetime

    from backend.db.database import AuditLogModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-long-random-string-for-minor-fixes-123456")
    db_file = tmp_path / "be11.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = UserModel(
            id="admin-be11",
            username="admin_be11",
            full_name="Admin Test",
            role="ADMIN",
            password_hash="fakehash",
            is_active=True,
        )
        session.add(admin)
        log1 = AuditLogModel(
            id=1,
            timestamp=datetime(2026, 10, 18, 10, 0, 0),
            actor_id="admin_be11",
            action_type="LOGIN",
            entity_name="user",
            entity_id="admin-be11",
            details="Admin login",
        )
        log2 = AuditLogModel(
            id=2,
            timestamp=datetime(2026, 10, 18, 11, 0, 0),
            actor_id="dr_dung",
            action_type="SIGN_PRELIM",
            entity_name="study",
            entity_id="study-123",
            details="Review signed",
        )
        session.add_all([log1, log2])
        session.commit()

    admin_token = create_access_token({"sub": "admin_be11", "uid": "admin-be11", "role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    def override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # 1. Unauthenticated request must be rejected 401
        unauth_res = client.get("/api/admin/audit-events/export")
        assert unauth_res.status_code == 401

        # 2. Authenticated export request must return 200 with items
        res = client.get("/api/admin/audit-events/export", headers=admin_headers)
        assert res.status_code == 200, f"BE-11 VULNERABILITY: /api/admin/audit-events/export returned {res.status_code}!"
        data = res.json()
        assert "items" in data
        assert len(data["items"]) == 2
        item = data["items"][0]
        assert "timestamp" in item
        assert "actor_id" in item
        assert "action_type" in item
        assert "entity_id" in item

        # 3. Filtered export by action
        res_filtered = client.get("/api/admin/audit-events/export?action=LOGIN", headers=admin_headers)
        assert res_filtered.status_code == 200
        filtered_items = res_filtered.json()["items"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["action_type"] == "LOGIN"
    finally:
        app.dependency_overrides.pop(get_db, None)

