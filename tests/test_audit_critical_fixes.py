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


def test_be_06_session_revocation_on_password_change_and_logout(tmp_path, monkeypatch):
    """BE-06: Existing access tokens must be invalidated when password changes, resets, or user logs out."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    import time

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be06.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="u1",
                username="doctor",
                full_name="BS. Test",
                role="DOCTOR",
                is_active=True,
                password_hash=hash_password("old_password_123"),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            token1 = create_access_token({"sub": "doctor", "uid": "u1"})
            h1 = {"Authorization": f"Bearer {token1}"}

            # 1. token1 should be valid before password change
            res_before = client.get("/api/auth/current-user", headers=h1)
            assert res_before.status_code == 200

            time.sleep(0.05)

            # 2. Change password via change-password endpoint
            change_res = client.post(
                "/api/auth/change-password",
                headers=h1,
                json={"old_password": "old_password_123", "new_password": "new_password_456"},
            )
            assert change_res.status_code == 200

            # 3. token1 MUST now be revoked and rejected with 401
            res_after = client.get("/api/auth/current-user", headers=h1)
            assert res_after.status_code == 401, (
                f"BE-06 VULNERABILITY DETECTED: Access token remained valid after password change! Status: {res_after.status_code}"
            )

            # 4. Login with new password to get token2
            login_res = client.post("/api/auth/login", json={"username": "doctor", "password": "new_password_456"})
            assert login_res.status_code == 200
            token2 = login_res.json()["access_token"]
            h2 = {"Authorization": f"Bearer {token2}"}

            res2_valid = client.get("/api/auth/current-user", headers=h2)
            assert res2_valid.status_code == 200

            # 5. Call logout endpoint
            logout_res = client.post("/api/auth/logout", headers=h2)
            assert logout_res.status_code == 200, f"Logout endpoint missing or failed: {logout_res.status_code}"

            # 6. token2 MUST now be revoked and rejected with 401
            res2_after_logout = client.get("/api/auth/current-user", headers=h2)
            assert res2_after_logout.status_code == 401, (
                f"BE-06 VULNERABILITY DETECTED: Access token remained valid after logout! Status: {res2_after_logout.status_code}"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_07_old_token_cannot_rebind_to_recreated_username(tmp_path, monkeypatch):
    """BE-07: Old token from deleted user cannot rebind to newly created account with same username."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be07.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="old-uid-123",
                username="doctor1",
                full_name="BS. Old Account",
                role="DOCTOR",
                is_active=True,
                password_hash=hash_password("password123"),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        # Issue token for old user with immutable uid
        old_token = create_access_token({"sub": "doctor1", "uid": "old-uid-123"})
        h_old = {"Authorization": f"Bearer {old_token}"}

        # Also test legacy token without uid issued at t0 cannot rebind to recreated user at t1
        import datetime
        legacy_token = create_access_token({"sub": "doctor1"})
        h_legacy = {"Authorization": f"Bearer {legacy_token}"}

        with TestClient(app) as client:
            # 1. Old token valid initially
            res1 = client.get("/api/auth/current-user", headers=h_old)
            assert res1.status_code == 200
            assert res1.json()["id"] == "old-uid-123"

            # 2. Delete old user and re-create a new user with same username but new ID and later created_at
            with Session(engine) as db:
                db.query(UserModel).filter(UserModel.username == "doctor1").delete()
                db.add(
                    UserModel(
                        id="new-uid-456",
                        username="doctor1",
                        full_name="BS. Recreated Account",
                        role="DOCTOR",
                        is_active=True,
                        password_hash=hash_password("newpassword456"),
                        created_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=5),
                    )
                )
                db.commit()

            # 3. Old token with uid MUST NOT rebind to new account - must be rejected with 401
            res_rebind = client.get("/api/auth/current-user", headers=h_old)
            assert res_rebind.status_code == 401, (
                f"BE-07 VULNERABILITY DETECTED: Old token rebound to new user ID {res_rebind.json().get('id')}! Status: {res_rebind.status_code}"
            )

            # 4. Old token WITHOUT uid issued before new user creation MUST ALSO be rejected with 401
            res_legacy_rebind = client.get("/api/auth/current-user", headers=h_legacy)
            assert res_legacy_rebind.status_code == 401, (
                f"BE-07 VULNERABILITY DETECTED: Legacy token without uid rebound to new user! Status: {res_legacy_rebind.status_code}"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_08_feedback_requires_auth_and_prevents_actor_spoofing(tmp_path, monkeypatch):
    """BE-08: Feedback endpoint must require authentication and derive actor strictly from server session."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token
    from backend.db.database import AuditLogModel, Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be08.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="u1", username="doctor1", full_name="BS. Test", role="DOCTOR", is_active=True))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            # 1. Anonymous feedback submission MUST be rejected with 401
            anon_resp = client.post("/api/feedback", json={"actor_id": "auditadmin", "message": "unauthenticated spoof"})
            assert anon_resp.status_code == 401, (
                f"BE-08 VULNERABILITY DETECTED: Anonymous feedback was accepted! Status: {anon_resp.status_code}"
            )

            # 2. Authenticated user cannot spoof actor_id
            token = create_access_token({"sub": "doctor1", "uid": "u1"})
            h = {"Authorization": f"Bearer {token}"}
            auth_resp = client.post(
                "/api/feedback",
                headers=h,
                json={"actor_id": "auditadmin", "title": "Góp ý UI", "message": "Giao diện rất tốt"},
            )
            assert auth_resp.status_code == 200
            feedback_id = int(auth_resp.json()["feedback_id"])

            with Session(engine) as db:
                row = db.query(AuditLogModel).filter(AuditLogModel.id == feedback_id).one()
                assert row.actor_id == "doctor1", (
                    f"BE-08 VULNERABILITY DETECTED: Client claimed actor spoofed audit log! Expected doctor1, got {row.actor_id}"
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_09_security_audit_logging_for_auth_read_and_admin(tmp_path, monkeypatch):
    """BE-09: Login success/failure, clinical case read, and admin modifications must emit durable audit events."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import AuditLogModel, Base, PatientModel, StudyModel, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be09.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="u_doc",
                username="auditdoc",
                full_name="BS. Audit",
                role="DOCTOR",
                is_active=True,
                password_hash=hash_password("docpassword123"),
            )
        )
        db.add(
            UserModel(
                id="u_adm",
                username="auditadmin",
                full_name="Admin Audit",
                role="ADMIN",
                is_active=True,
                password_hash=hash_password("adminpassword123"),
            )
        )
        db.add(PatientModel(id="p1", anonymized_pid="PID-001"))
        db.add(StudyModel(id="s1", patient_id="p1", study_date="2026-10-18", ovary_side="RIGHT", status="PENDING"))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            doc_token = create_access_token({"sub": "auditdoc", "uid": "u_doc"})
            admin_token = create_access_token({"sub": "auditadmin", "uid": "u_adm"})
            dh = {"Authorization": f"Bearer {doc_token}"}
            ah = {"Authorization": f"Bearer {admin_token}"}

            with Session(engine) as db:
                before_count = db.query(AuditLogModel).count()

            # 1. Login success
            login_ok = client.post("/api/auth/login", json={"username": "auditdoc", "password": "docpassword123"})
            assert login_ok.status_code == 200

            # 2. Login failure
            login_fail = client.post("/api/auth/login", json={"username": "auditdoc", "password": "wrongpassword"})
            assert login_fail.status_code == 401

            # 3. Clinical case read
            case_read = client.get("/api/cases/s1", headers=dh)
            assert case_read.status_code == 200

            # 4. Admin update user
            admin_update = client.patch("/api/admin/users/u_doc", headers=ah, json={"department": "Khoa Phu San"})
            assert admin_update.status_code == 200

            with Session(engine) as db:
                after_count = db.query(AuditLogModel).count()
                new_logs = db.query(AuditLogModel).offset(before_count).all()
                actions = {log.action_type for log in new_logs}

            assert "LOGIN_SUCCESS" in actions, f"BE-09 VULNERABILITY: LOGIN_SUCCESS missing from audit! Found: {actions}"
            assert "LOGIN_FAILURE" in actions, f"BE-09 VULNERABILITY: LOGIN_FAILURE missing from audit! Found: {actions}"
            assert "CLINICAL_CASE_READ" in actions, f"BE-09 VULNERABILITY: CLINICAL_CASE_READ missing from audit! Found: {actions}"
            assert "ADMIN_USER_UPDATE" in actions, f"BE-09 VULNERABILITY: ADMIN_USER_UPDATE missing from audit! Found: {actions}"
            assert after_count - before_count >= 4
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_12_review_idempotency_hash_includes_orads_and_descriptors(tmp_path, monkeypatch):
    """BE-12: Idempotency hash must include O-RADS and morphology descriptors to prevent silent data discard on retry."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token
    from backend.db.database import Base, ImageModel, PatientModel, PredictionModel, StudyModel, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be12.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    mask = {"shape": [512, 512], "first_val": 0, "counts": [10000, 20000, 232144]}
    with Session(engine) as db:
        db.add(UserModel(id="u_doc", username="doctor1", full_name="BS. Test", role="DOCTOR", is_active=True))
        db.add(PatientModel(id="p1", anonymized_pid="PID-001"))
        db.add(StudyModel(id="s1", patient_id="p1", study_date="2026-10-18", ovary_side="RIGHT", status="PENDING", review_revision=0))
        db.add(ImageModel(id="img1", study_id="s1", filename="img1.png", raw_path="img1.png", width=512, height=512))
        db.add(PredictionModel(id="pred1", image_id="img1", raw_mask_rle=mask, measurements={}))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            token = create_access_token({"sub": "doctor1", "uid": "u_doc"})
            dh = {"Authorization": f"Bearer {token}"}

            body = {
                "study_id": "s1",
                "expected_revision": 0,
                "request_id": "batch-idemp-123",
                "reviews": [
                    {
                        "image_id": "img1",
                        "prediction_id": "pred1",
                        "doctor_action": "ACCEPTED_RAW",
                        "verified_mask_rle": mask,
                        "orads": "2",
                        "morphology_description": "initial descriptor",
                    }
                ],
            }

            # 1. Initial save succeeds (200)
            res1 = client.post("/api/reviews/batch", headers=dh, json=body)
            assert res1.status_code == 200

            # 2. Replay with identical request_id but changed orads/morphology MUST BE REJECTED with 409
            body_changed = {
                "study_id": "s1",
                "expected_revision": 0,
                "request_id": "batch-idemp-123",
                "reviews": [
                    {
                        "image_id": "img1",
                        "prediction_id": "pred1",
                        "doctor_action": "ACCEPTED_RAW",
                        "verified_mask_rle": mask,
                        "orads": "5",
                        "morphology_description": "changed descriptor",
                    }
                ],
            }
            res2 = client.post("/api/reviews/batch", headers=dh, json=body_changed)
            assert res2.status_code == 409, (
                f"BE-12 VULNERABILITY DETECTED: Retry with changed O-RADS/descriptor was accepted as idempotent replay! Status: {res2.status_code}"
            )

            # 3. True identical retry succeeds (200)
            res3 = client.post("/api/reviews/batch", headers=dh, json=body)
            assert res3.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_25_secure_provisioning_and_no_shared_default_password(tmp_path, monkeypatch):
    """BE-25: User creation and reset without password must generate random temporary secrets with must_change_password requirement."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be25.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="u_adm",
                username="admin1",
                full_name="Admin",
                role="ADMIN",
                is_active=True,
                password_hash=hash_password("adminpass123"),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            admin_token = create_access_token({"sub": "admin1", "uid": "u_adm"})
            ah = {"Authorization": f"Bearer {admin_token}"}

            # 1. Admin creates user without explicit password
            create_resp = client.post(
                "/api/admin/users",
                headers=ah,
                json={"username": "newdoc", "full_name": "BS. New", "role": "DOCTOR"},
            )
            assert create_resp.status_code == 200
            create_data = create_resp.json()
            assert create_data.get("must_change_password") is True
            temp_pw = create_data.get("temp_password")
            assert temp_pw and temp_pw != "Default@123", "BE-25 VULNERABILITY: Static default password used in provisioning!"

            # 2. Login with temporary password returns must_change_password=True
            login_resp = client.post("/api/auth/login", json={"username": "newdoc", "password": temp_pw})
            assert login_resp.status_code == 200
            login_data = login_resp.json()
            assert login_data.get("must_change_password") is True, "BE-25 VULNERABILITY: must_change_password flag missing in login response!"

            # 3. Change password clears must_change_password flag
            doc_token = login_data["access_token"]
            dh = {"Authorization": f"Bearer {doc_token}"}
            ch_resp = client.post(
                "/api/auth/change-password",
                headers=dh,
                json={"old_password": temp_pw, "new_password": "permanentpassword123"},
            )
            assert ch_resp.status_code == 200

            # 4. Subsequent login has must_change_password=False
            login2 = client.post("/api/auth/login", json={"username": "newdoc", "password": "permanentpassword123"})
            assert login2.status_code == 200
            assert login2.json().get("must_change_password") is False

            # 5. Admin reset password without new_password generates random temp password with must_change_password=True
            reset_resp = client.post(f"/api/admin/users/{create_data['user_id']}/reset-password", headers=ah, json={})
            assert reset_resp.status_code == 200
            reset_data = reset_resp.json()
            assert reset_data.get("must_change_password") is True
            reset_temp_pw = reset_data.get("temp_password")
            assert reset_temp_pw and reset_temp_pw != "Vinmec@2026", "BE-25 VULNERABILITY: Static fallback used in admin password reset!"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_ops_01_enforce_tls_and_no_plaintext_exposure():
    """OPS-01: Deployment configurations must terminate TLS, enforce HTTPS redirect, and restrict backend binding."""
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parent.parent
    compose_file = root / "docker-compose.yml"
    nginx_file = root / "nginx.conf"

    assert compose_file.exists(), "docker-compose.yml not found"
    assert nginx_file.exists(), "nginx.conf not found"

    compose_text = compose_file.read_text(encoding="utf-8")
    compose_data = yaml.safe_load(compose_text)

    # 1. Backend app service must not expose raw 8000 on 0.0.0.0
    app_svc = compose_data.get("services", {}).get("app", {})
    app_ports = [str(p) for p in app_svc.get("ports", [])]
    assert "8000:8000" not in app_ports, (
        "OPS-01 VULNERABILITY: Backend port 8000 directly published on 0.0.0.0!"
    )

    # 2. Proxy service must publish port 443 for HTTPS
    nginx_svc = compose_data.get("services", {}).get("nginx", {})
    nginx_ports = [str(p) for p in nginx_svc.get("ports", [])]
    has_443 = any("443:443" in p or "443" in p for p in nginx_ports)
    assert has_443, "OPS-01 VULNERABILITY: Nginx proxy does not publish port 443!"

    # 3. Proxy service must mount TLS certificate volume
    nginx_volumes = [str(v) for v in nginx_svc.get("volumes", [])]
    has_cert_mount = any("certs" in v for v in nginx_volumes)
    assert has_cert_mount, "OPS-01 VULNERABILITY: Nginx proxy missing TLS certificate mount!"

    # 4. Nginx configuration must enforce HTTPS redirect on port 80
    nginx_text = nginx_file.read_text(encoding="utf-8")
    assert "return 301 https://$host$request_uri;" in nginx_text or "rewrite ^(.*) https://$host$1 permanent;" in nginx_text, (
        "OPS-01 VULNERABILITY: Nginx port 80 does not enforce redirect to HTTPS!"
    )

    # 5. Nginx configuration must listen on 443 ssl with TLSv1.2/1.3 and HSTS
    assert "listen 443 ssl" in nginx_text, "OPS-01 VULNERABILITY: Nginx missing 'listen 443 ssl' server block!"
    assert "ssl_protocols" in nginx_text and "TLSv1.2" in nginx_text and "TLSv1.3" in nginx_text, (
        "OPS-01 VULNERABILITY: Nginx missing secure TLS protocol definition (TLSv1.2 TLSv1.3)!"
    )
    assert "Strict-Transport-Security" in nginx_text, (
        "OPS-01 VULNERABILITY: Nginx missing HSTS security header!"
    )






