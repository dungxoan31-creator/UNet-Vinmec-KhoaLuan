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


def test_demo_01_report_generator_removes_hardcoded_placeholders():
    """DEMO-01: Report generator must require mandatory patient ID and must NOT fill fake patient identity, fake D1/D2/area measurements, or fake O-RADS 2 conclusions."""
    import pytest

    from backend.services.report_generator import MedicalReportGenerator

    generator = MedicalReportGenerator()

    # 1. Missing patient identifier must raise ValueError
    with pytest.raises(ValueError, match="mã định danh bệnh nhân"):
        generator._normalize_report_data({})

    # 2. When patient ID is provided but other clinical fields are empty, no hardcoded clinical placeholders may appear
    norm = generator._normalize_report_data({"patientId": "BN-TEST-001"})
    assert norm["patientId"] == "BN-TEST-001"

    # Must NOT contain hardcoded patient or doctor names
    assert norm["patientName"] != "Nguyễn Thị Phượng", "DEMO-01 VULNERABILITY: Hardcoded patient name used as fallback!"
    assert "Trương Thị Phượng" not in norm.get("doctorName", "")
    assert "Lê Khắc Hiếu" not in norm.get("referringDoctor", "")

    # Must NOT invent measurements D1=28.5, D2=21.0, area=4.62
    conc1 = norm.get("conclusion_l1", "")
    ovary_r3 = norm.get("ovary_r3", "")
    assert "28.5" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded D1=28.5 used as fallback!"
    assert "21" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded D2=21 used as fallback!"
    assert "4.62" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded area=4.62 used as fallback!"

    # Must NOT invent O-RADS 2 classification or 3-month follow-up without clinical input
    assert "O-RADS 2" not in conc1, "DEMO-01 VULNERABILITY: Hardcoded O-RADS 2 conclusion used as fallback!"
    assert "3 THÁNG" not in norm.get("conclusion_l2", ""), "DEMO-01 VULNERABILITY: Hardcoded 3-month recall used as fallback!"


