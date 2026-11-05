import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import sqlite3
import uuid
from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    AuditLogModel,
    FacilityModel,
    HITLSessionModel,
    SessionLocal,
    StudyModel,
    UIEventModel,
    UserModel,
)


@pytest.fixture
def tenant_hardening_env(tmp_path):
    prefix = uuid.uuid4().hex[:8]
    test_db = SessionLocal()

    fac_a = FacilityModel(
        id=f"FAC-A-{prefix}",
        name=f"Facility Alpha {prefix}",
        facility_code=f"FA-{prefix}",
        is_active=True,
    )
    fac_b = FacilityModel(
        id=f"FAC-B-{prefix}",
        name=f"Facility Beta {prefix}",
        facility_code=f"FB-{prefix}",
        is_active=True,
    )
    test_db.add_all([fac_a, fac_b])
    test_db.commit()

    pwd_hash = hash_password("SecurePass123!")

    doc_a = UserModel(
        id=f"doc-a-{prefix}",
        username=f"doctor_a_{prefix}",
        full_name="Dr. Alpha",
        role="DOCTOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    doc_b = UserModel(
        id=f"doc-b-{prefix}",
        username=f"doctor_b_{prefix}",
        full_name="Dr. Beta",
        role="DOCTOR",
        facility_id=fac_b.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    admin_fac_a = UserModel(
        id=f"admin-a-{prefix}",
        username=f"admin_a_{prefix}",
        full_name="Admin Alpha",
        role="ADMIN",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    admin_global = UserModel(
        id=f"admin-global-{prefix}",
        username=f"admin_global_{prefix}",
        full_name="Global Administrator",
        role="ADMIN",
        facility_id=None,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add_all([doc_a, doc_b, admin_fac_a, admin_global])
    test_db.commit()

    token_doc_a = create_access_token({"sub": doc_a.username, "role": "DOCTOR", "facility_id": fac_a.id})
    token_doc_b = create_access_token({"sub": doc_b.username, "role": "DOCTOR", "facility_id": fac_b.id})
    token_admin_a = create_access_token({"sub": admin_fac_a.username, "role": "ADMIN", "facility_id": fac_a.id})
    token_admin_global = create_access_token({"sub": admin_global.username, "role": "ADMIN", "facility_id": None})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "fac_a": fac_a,
            "fac_b": fac_b,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "admin_fac_a": admin_fac_a,
            "admin_global": admin_global,
            "token_doc_a": token_doc_a,
            "token_doc_b": token_doc_b,
            "token_admin_a": token_admin_a,
            "token_admin_global": token_admin_global,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_hitl_session_detail_tenant_forbidden(tenant_hardening_env):
    """Doctor or facility admin from Facility B cannot view HITL session of Study in Facility A."""
    client = tenant_hardening_env["client"]
    db = tenant_hardening_env["db"]
    fac_a = tenant_hardening_env["fac_a"]
    doc_a = tenant_hardening_env["doc_a"]
    token_doc_b = tenant_hardening_env["token_doc_b"]

    study_a = StudyModel(
        id=f"study-a-{tenant_hardening_env['prefix']}",
        study_code=f"ST-A-{tenant_hardening_env['prefix']}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
    )
    session_a = HITLSessionModel(
        id=f"sess-a-{tenant_hardening_env['prefix']}",
        study_id=study_a.id,
        actor_id=doc_a.username,
        participant_code="DOC-ALPHA",
        participant_role="clinician",
        data_origin="live",
        status="IN_PROGRESS",
        created_at=datetime.now(UTC),
    )
    db.add_all([study_a, session_a])
    db.commit()

    resp = client.get(
        f"/api/hitl/sessions/{session_a.id}",
        headers={"Authorization": f"Bearer {token_doc_b}"},
    )
    assert resp.status_code == 403, resp.text


def test_facility_admin_settings_do_not_leak_between_facilities(tenant_hardening_env):
    client = tenant_hardening_env["client"]
    token_a = tenant_hardening_env["token_admin_a"]
    admin_b = UserModel(
        id=f"admin-b-{tenant_hardening_env['prefix']}",
        username=f"admin_b_{tenant_hardening_env['prefix']}",
        full_name="Admin Beta",
        role="ADMIN",
        facility_id=tenant_hardening_env["fac_b"].id,
        password_hash=hash_password("SecurePass123!"),
        is_active=True,
    )
    tenant_hardening_env["db"].add(admin_b)
    tenant_hardening_env["db"].commit()
    token_b = create_access_token({"sub": admin_b.username, "role": "ADMIN", "facility_id": admin_b.facility_id})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    saved = client.put(
        "/api/admin/settings",
        headers=headers_a,
        json={"report_header": f"FACILITY-A-{tenant_hardening_env['prefix']}"},
    )
    facility_b_settings = client.get("/api/admin/settings", headers=headers_b)

    assert saved.status_code == 200, saved.text
    assert facility_b_settings.status_code == 200, facility_b_settings.text
    assert facility_b_settings.json().get("report_header") != saved.json()["settings"]["report_header"]


def test_facility_admin_cannot_trigger_or_list_global_backups(tenant_hardening_env, monkeypatch, tmp_path):
    from backend.services.backup_service import BackupService

    calls = []
    monkeypatch.setattr(BackupService, "__init__", lambda self, *args, **kwargs: setattr(self, "backup_dir", str(tmp_path)))
    monkeypatch.setattr(BackupService, "create_backup", lambda self, **kwargs: calls.append("create") or {"status": "SUCCESS"})
    monkeypatch.setattr(BackupService, "list_backups", lambda self: calls.append("list") or [])
    headers = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_a']}"}

    created = tenant_hardening_env["client"].post("/api/admin/backups/create", headers=headers)
    listed = tenant_hardening_env["client"].get("/api/admin/backups/list", headers=headers)

    assert created.status_code == 403
    assert listed.status_code == 403
    assert calls == []


def test_global_admin_settings_require_and_honor_facility_scope(tenant_hardening_env):
    client = tenant_hardening_env["client"]
    headers_global = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_global']}"}
    headers_a = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_a']}"}
    facility_a = tenant_hardening_env["fac_a"]
    facility_b = tenant_hardening_env["fac_b"]

    missing_scope = client.get("/api/admin/settings", headers=headers_global)
    saved_a = client.put(
        "/api/admin/settings",
        headers=headers_global,
        json={"facility_id": facility_a.id, "report_header": "GLOBAL-ALPHA-HEADER"},
    )
    global_b = client.get(f"/api/admin/settings?facility_id={facility_b.id}", headers=headers_global)
    cross_facility = client.put(
        "/api/admin/settings",
        headers=headers_a,
        json={"facility_id": facility_b.id, "report_header": "MUST-BE-FORBIDDEN"},
    )

    assert missing_scope.status_code == 422
    assert saved_a.status_code == 200, saved_a.text
    assert global_b.status_code == 200, global_b.text
    assert global_b.json()["report_header"] != saved_a.json()["settings"]["report_header"]
    assert cross_facility.status_code == 403


def test_admin_metadata_requires_and_uses_the_authorized_facility(tenant_hardening_env):
    client = tenant_hardening_env["client"]
    facility_a = tenant_hardening_env["fac_a"]
    facility_b = tenant_hardening_env["fac_b"]
    headers_global = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_global']}"}
    headers_a = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_a']}"}

    missing_scope = client.get("/api/admin/metadata", headers=headers_global)
    global_a = client.get(f"/api/admin/metadata?facility_id={facility_a.id}", headers=headers_global)
    global_b = client.get(f"/api/admin/metadata?facility_id={facility_b.id}", headers=headers_global)
    facility_a_default = client.get("/api/admin/metadata", headers=headers_a)
    facility_a_cross_scope = client.get(
        f"/api/admin/metadata?facility_id={facility_b.id}", headers=headers_a,
    )

    assert missing_scope.status_code == 422
    assert global_a.status_code == global_b.status_code == facility_a_default.status_code == 200
    assert global_a.json()["hospital_name"] == facility_a.name
    assert global_b.json()["hospital_name"] == facility_b.name
    assert facility_a_default.json()["hospital_name"] == facility_a.name
    assert facility_a_cross_scope.status_code == 403


def test_global_backup_endpoint_writes_only_to_explicit_temp_storage(
    tenant_hardening_env, monkeypatch, tmp_path,
):
    source_db = tmp_path / "synthetic-source.sqlite3"
    with sqlite3.connect(source_db) as connection:
        connection.execute("CREATE TABLE synthetic_record (value TEXT NOT NULL)")
        connection.execute("INSERT INTO synthetic_record VALUES ('sandbox-only')")
    backup_dir = tmp_path / "isolated-backups"
    monkeypatch.setenv("APP_DB_PATH", str(source_db))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_BACKUP_DIR", str(backup_dir))
    headers = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_global']}"}

    created = tenant_hardening_env["client"].post(
        "/api/admin/backups/create?include_images=true", headers=headers,
    )
    listed = tenant_hardening_env["client"].get("/api/admin/backups/list", headers=headers)

    assert created.status_code == 200, created.text
    assert created.json()["included_images"] is False
    assert listed.status_code == 200, listed.text
    assert [item["filename"] for item in listed.json()] == [created.json()["backup_filename"]]
    assert {path.name for path in backup_dir.iterdir()} == {created.json()["backup_filename"]}


def test_backup_archive_is_removed_when_audit_commit_fails(
    tenant_hardening_env, monkeypatch, tmp_path,
):
    from sqlalchemy.orm import Session
    from fastapi.testclient import TestClient
    from backend.app.main import app

    source_db = tmp_path / "synthetic-source.sqlite3"
    with sqlite3.connect(source_db) as connection:
        connection.execute("CREATE TABLE synthetic_record (value TEXT NOT NULL)")
    backup_dir = tmp_path / "isolated-backups"
    monkeypatch.setenv("APP_DB_PATH", str(source_db))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_BACKUP_DIR", str(backup_dir))

    def fail_commit(_session):
        raise OSError("simulated audit persistence failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    headers = {"Authorization": f"Bearer {tenant_hardening_env['token_admin_global']}"}
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/admin/backups/create", headers=headers)
    client.close()

    assert response.status_code == 500
    assert list(backup_dir.iterdir()) == []


def test_ui_events_batch_cross_facility_rejected_entirely(tenant_hardening_env):
    """If UI events batch contains any event for a study outside the user's facility, reject entirely with 403."""
    client = tenant_hardening_env["client"]
    db = tenant_hardening_env["db"]
    fac_a = tenant_hardening_env["fac_a"]
    fac_b = tenant_hardening_env["fac_b"]
    token_doc_a = tenant_hardening_env["token_doc_a"]

    prefix = tenant_hardening_env["prefix"]
    study_a = StudyModel(id=f"case-a-{prefix}", study_code=f"CASE-A-{prefix}", study_date="2026-11-01", facility_id=fac_a.id, status="PENDING")
    study_b = StudyModel(id=f"case-b-{prefix}", study_code=f"CASE-B-{prefix}", study_date="2026-11-01", facility_id=fac_b.id, status="PENDING")
    db.add_all([study_a, study_b])
    db.commit()

    events_payload = {
        "events": [
            {
                "case_id": study_a.id,
                "event": "case_open",
                "payload": {"view": "workstation"},
                "t_ms": 100,
            },
            {
                "case_id": study_b.id,  # From facility B!
                "event": "stroke",
                "payload": {"tool": "brush"},
                "t_ms": 200,
            },
        ]
    }

    resp = client.post(
        "/api/hitl/events",
        headers={"Authorization": f"Bearer {token_doc_a}"},
        json=events_payload,
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    # Verify fail-closed: NO events were saved for either case
    saved_events = db.query(UIEventModel).filter(UIEventModel.case_id.in_([study_a.id, study_b.id])).all()
    assert len(saved_events) == 0, f"Expected 0 events saved, found {len(saved_events)}"


def test_admin_audit_logs_facility_filtering(tenant_hardening_env):
    """Facility admin only sees audit logs traceable to their facility; global admin sees all."""
    client = tenant_hardening_env["client"]
    db = tenant_hardening_env["db"]
    fac_a = tenant_hardening_env["fac_a"]
    fac_b = tenant_hardening_env["fac_b"]
    token_admin_a = tenant_hardening_env["token_admin_a"]
    token_admin_global = tenant_hardening_env["token_admin_global"]
    prefix = tenant_hardening_env["prefix"]

    study_a = StudyModel(id=f"study-log-a-{prefix}", study_code=f"ST-LA-{prefix}", study_date="2026-11-01", facility_id=fac_a.id, status="PENDING")
    study_b = StudyModel(id=f"study-log-b-{prefix}", study_code=f"ST-LB-{prefix}", study_date="2026-11-01", facility_id=fac_b.id, status="PENDING")
    db.add_all([study_a, study_b])
    db.commit()

    log_a = AuditLogModel(
        entity_name="study",
        entity_id=study_a.id,
        action_type="REVIEW_CONFIRMED",
        actor_id="doctor_a",
        timestamp=datetime.now(UTC),
    )
    log_b = AuditLogModel(
        entity_name="study",
        entity_id=study_b.id,
        action_type="REVIEW_CONFIRMED",
        actor_id="doctor_b",
        timestamp=datetime.now(UTC),
    )
    log_system = AuditLogModel(
        entity_name="system",
        entity_id=str(uuid.uuid4()),
        action_type="CONFIG_CHANGED",
        actor_id="system_admin",
        timestamp=datetime.now(UTC),
    )
    db.add_all([log_a, log_b, log_system])
    db.commit()

    # Facility Admin A views logs
    resp_a = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token_admin_a}"},
    )
    assert resp_a.status_code == 200, resp_a.text
    logs_view_a = resp_a.json()
    log_ids_a = [item["id"] for item in logs_view_a]

    assert log_a.id in log_ids_a, "Facility admin A must see logs from Facility A"
    assert log_b.id not in log_ids_a, "Facility admin A must NOT see logs from Facility B"
    assert log_system.id not in log_ids_a, "Facility admin A must NOT see untraceable system logs"

    # Global Admin views logs
    resp_global = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token_admin_global}"},
    )
    assert resp_global.status_code == 200, resp_global.text
    logs_view_global = resp_global.json()
    log_ids_global = [item["id"] for item in logs_view_global]

    assert log_a.id in log_ids_global
    assert log_b.id in log_ids_global
    assert log_system.id in log_ids_global

    for path in ("/api/admin/audit-events", "/api/admin/audit-events/export"):
        facility_response = client.get(
            path,
            headers={"Authorization": f"Bearer {token_admin_a}"},
        )
        assert facility_response.status_code == 200, facility_response.text
        facility_ids = [item["id"] for item in facility_response.json()["items"]]
        assert log_a.id in facility_ids
        assert log_b.id not in facility_ids
        assert log_system.id not in facility_ids

        global_response = client.get(
            path,
            headers={"Authorization": f"Bearer {token_admin_global}"},
        )
        assert global_response.status_code == 200, global_response.text
        global_ids = [item["id"] for item in global_response.json()["items"]]
        assert {log_a.id, log_b.id, log_system.id}.issubset(global_ids)


def test_admin_cases_offset_limit_consistency(tenant_hardening_env):
    """GET /api/admin/cases handles limit & offset consistently."""
    client = tenant_hardening_env["client"]
    db = tenant_hardening_env["db"]
    token_admin_global = tenant_hardening_env["token_admin_global"]
    prefix = tenant_hardening_env["prefix"]

    created_cases = []
    for i in range(15):
        st = StudyModel(
            id=f"study-pg-{prefix}-{i:02d}",
            study_code=f"ST-PG-{prefix}-{i:02d}",
            study_date="2026-11-01",
            facility_id=tenant_hardening_env["fac_a"].id,
            status="PENDING",
            created_at=datetime.now(UTC),
        )
        created_cases.append(st)
    db.add_all(created_cases)
    db.commit()

    # 1. offset=5 & limit=5
    resp = client.get(
        f"/api/admin/cases?search=ST-PG-{prefix}&offset=5&limit=5",
        headers={"Authorization": f"Bearer {token_admin_global}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 15
    assert len(data["items"]) == 5

    # 2. offset=10 without limit should use default limit/page_size and skip 10
    resp_offset_only = client.get(
        f"/api/admin/cases?search=ST-PG-{prefix}&offset=10",
        headers={"Authorization": f"Bearer {token_admin_global}"},
    )
    assert resp_offset_only.status_code == 200, resp_offset_only.text
    data_offset = resp_offset_only.json()
    assert data_offset["total"] == 15
    assert len(data_offset["items"]) == 5

    # 3. page=2, page_size=6 without offset/limit
    resp_page = client.get(
        f"/api/admin/cases?search=ST-PG-{prefix}&page=2&page_size=6",
        headers={"Authorization": f"Bearer {token_admin_global}"},
    )
    assert resp_page.status_code == 200, resp_page.text
    data_page = resp_page.json()
    assert data_page["total"] == 15
    assert len(data_page["items"]) == 6
