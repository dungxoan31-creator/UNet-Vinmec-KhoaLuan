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



