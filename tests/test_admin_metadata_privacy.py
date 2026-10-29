from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import AuditLogModel, Base, PatientModel, StudyModel, UserModel, get_db


def test_admin_case_metadata_api_returns_only_operational_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-admin-metadata-123456")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-metadata.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                UserModel(id="admin-id", username="admin", full_name="Admin", role="ADMIN"),
                PatientModel(id="patient-1", anonymized_pid="SENSITIVE-PID"),
                StudyModel(
                    id="study-1",
                    patient_id="patient-1",
                    study_code="STUDY-001",
                    study_date="2026-10-21",
                    clinical_indication="Sensitive clinical indication",
                ),
            ]
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin-test-password"},
            )
            assert login.status_code == 200
            response = client.get(
                "/api/admin/cases", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
            )
            assert response.status_code == 200
            body = response.json()
            assert body["total"] == 1
            assert body["items"][0]["study_code"] == "STUDY-001"
            assert set(body["items"][0]) == {
                "study_code",
                "visit_no",
                "status",
                "department",
                "created_at",
                "version",
            }
            assert len(body["items"][0]["visit_no"]) == 6
            assert body["items"][0]["visit_no"].isascii()
            assert body["items"][0]["visit_no"].isdigit()
            assert "SENSITIVE-PID" not in response.text
            assert "Sensitive clinical indication" not in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_admin_audit_apis_redact_details_and_do_not_search_them(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-admin-audit-123456")
    from backend.app.main import app
    from backend.app.routers.auth import create_access_token

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-audit-privacy.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                UserModel(
                    id="admin-audit-id",
                    username="admin-audit",
                    full_name="Admin Audit",
                    role="ADMIN",
                    is_active=True,
                ),
                AuditLogModel(
                    entity_name="study",
                    entity_id="study-1",
                    action_type="READ",
                    actor_id="admin-audit-id",
                    details={
                        "patient_id": "AUDIT-PHI-SECRET",
                        "clinical_note": "Sensitive audit note",
                        "checkpoint": "C:/private/model.pt",
                    },
                ),
                AuditLogModel(
                    entity_name="user_feedback",
                    entity_id="feedback-1",
                    action_type="USER_FEEDBACK",
                    actor_id="admin-audit-id",
                    details={
                        "title": "Synthetic privacy regression",
                        "message": "PATIENT-ID-MARKER-MUST-NOT-LEAK",
                    },
                ),
            ]
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'admin-audit', 'uid': 'admin-audit-id'})}"
    }
    try:
        with TestClient(app) as client:
            for path in (
                "/api/admin/audit-logs",
                "/api/admin/audit-events",
                "/api/admin/audit-events/export",
            ):
                response = client.get(path, headers=headers)
                assert response.status_code == 200
                assert "AUDIT-PHI-SECRET" not in response.text
                assert "PATIENT-ID-MARKER-MUST-NOT-LEAK" not in response.text
                body = response.json()
                items = body if isinstance(body, list) else body["items"]
                assert all(item["details"] is None for item in items)

            filtered = client.get(
                "/api/admin/audit-events",
                params={"q": "AUDIT-PHI-SECRET"},
                headers=headers,
            )
            assert filtered.status_code == 200
            assert filtered.json()["total"] == 0
            feedback_filtered = client.get(
                "/api/admin/audit-events",
                params={"q": "PATIENT-ID-MARKER-MUST-NOT-LEAK"},
                headers=headers,
            )
            assert feedback_filtered.status_code == 200
            assert feedback_filtered.json()["total"] == 0

            for path in (
                "/api/admin/audit-logs?limit=-1",
                "/api/admin/audit-events?page=0",
                "/api/admin/audit-events?page_size=101",
                "/api/admin/audit-events?limit=1&offset=10000001",
                "/api/admin/audit-events/export?limit=10001",
            ):
                assert client.get(path, headers=headers).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_admin_backup_api_never_includes_media_or_exposes_server_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-admin-backup-123456")
    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.services import backup_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-backup-privacy.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="admin-backup-id",
                username="admin-backup",
                full_name="Admin Backup",
                role="ADMIN",
                is_active=True,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    included_images = []

    class StubBackupService:
        def create_backup(self, include_images=True):
            included_images.append(include_images)
            return {
                "status": "SUCCESS",
                "backup_filename": "metadata.tar.gz",
                "backup_path": "C:/private/metadata.tar.gz",
                "included_images": include_images,
            }

        def list_backups(self):
            return [{"filename": "metadata.tar.gz", "path": "C:/private/metadata.tar.gz", "size_mb": 1.0}]

    monkeypatch.setattr(backup_service, "BackupService", StubBackupService)
    app.dependency_overrides[get_db] = temporary_db
    headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'admin-backup', 'uid': 'admin-backup-id'})}"
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/admin/backups/create?include_images=true", headers=headers)
            assert created.status_code == 200
            assert included_images == [False]
            assert created.json()["included_images"] is False
            assert "backup_path" not in created.json()

            listed = client.get("/api/admin/backups/list", headers=headers)
            assert listed.status_code == 200
            assert "path" not in listed.json()[0]
            assert "C:/private" not in listed.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
