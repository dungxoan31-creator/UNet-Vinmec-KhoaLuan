"""Unit tests for user registration, PBKDF2 hashing, and login authentication."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, UserModel, get_db


def test_user_registration_and_login_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-password")
    monkeypatch.setattr("backend.app.routers.auth.send_registration_otp", lambda *_: None)
    from backend.app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'auth_reg.db'}", connect_args={"check_same_thread": False})
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
            # 1. Existing accounts still authenticate via env password
            doc_login = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-test-password"})
            assert doc_login.status_code == 200
            assert doc_login.json()["user"]["username"] == "doctor"

            # 2. Register a new doctor account
            reg_payload = {
                "username": "dr_hoang",
                "password": "securepassword123",
                "full_name": "BS. Nguyễn Văn Hoàng",
                "email": "dr.hoang@example.org",
                "department": "Khoa Chẩn đoán Hình ảnh",
                "role": "DOCTOR",
            }
            reg_resp = client.post("/api/auth/register", json=reg_payload)
            assert reg_resp.status_code == 202, reg_resp.text
            reg_data = reg_resp.json()
            assert reg_data["email"] == "dr.hoang@example.org"
            assert reg_data["email_verification_required"] is True

            # 3. Verify user was stored with password_hash, not plain text, and pending approval (is_active=False)
            with Session(engine) as db:
                user_in_db = db.query(UserModel).filter(UserModel.username == "dr_hoang").first()
                assert user_in_db is not None
                assert user_in_db.password_hash is not None
                assert "securepassword123" not in user_in_db.password_hash
                assert ":" in user_in_db.password_hash
                assert user_in_db.is_active is False
                assert user_in_db.email_verified is False
                assert user_in_db.hospital == "Chưa cấu hình"

            # 4a. Login before admin approval must be rejected with 401
            pre_approval_login = client.post("/api/auth/login", json={"username": "dr_hoang", "password": "securepassword123"})
            assert pre_approval_login.status_code == 401

            # 4b. Admin verifies identity and activates the clinical doctor account
            with Session(engine) as db:
                user_in_db = db.query(UserModel).filter(UserModel.username == "dr_hoang").first()
                user_in_db.email_verified = True
                user_in_db.is_active = True
                db.commit()

            # 4c. Login succeeds after admin approval
            login_success = client.post("/api/auth/login", json={"username": "dr_hoang", "password": "securepassword123"})
            assert login_success.status_code == 200
            assert "access_token" in login_success.json()

            # 5. Login with invalid password fails
            login_fail = client.post("/api/auth/login", json={"username": "dr_hoang", "password": "wrongpassword"})
            assert login_fail.status_code == 401

            # 6. Duplicate registration returns 409 Conflict
            reg_dup = client.post("/api/auth/register", json=reg_payload)
            assert reg_dup.status_code == 409

            # 7. Short password returns 400 Bad Request
            reg_short_pw = client.post("/api/auth/register", json={
                "username": "dr_short",
                "password": "123",
                "full_name": "BS Test",
                "email": "short@example.org",
            })
            assert reg_short_pw.status_code == 400

            # 8. Short username returns 400 Bad Request
            reg_short_user = client.post("/api/auth/register", json={
                "username": "ab",
                "password": "securepassword123",
                "full_name": "BS Test",
                "email": "short-user@example.org",
            })
            assert reg_short_user.status_code == 400

            # 9. Registering with role ADMIN must be rejected with 403 Forbidden
            reg_admin_attempt = client.post("/api/auth/register", json={
                "username": "fake_admin",
                "password": "securepassword123",
                "full_name": "Fake Admin",
                "email": "fake-admin@example.org",
                "role": "ADMIN",
            })
            assert reg_admin_attempt.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_temporary_password_blocks_clinical_apis_until_rotation_and_returns_fresh_session(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from backend.app.main import app
    from backend.app.security import hash_password

    engine = create_engine(f"sqlite:///{tmp_path / 'forced-password.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="forced-doctor-id",
                username="forced-doctor",
                full_name="Forced Password Doctor",
                role="DOCTOR",
                is_active=True,
                password_hash=hash_password("temporary-password"),
                must_change_password=True,
            )
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
                json={"username": "forced-doctor", "password": "temporary-password"},
            )
            assert login.status_code == 200, login.text
            assert login.json()["must_change_password"] is True
            assert login.json()["user"]["must_change_password"] is True

            old_token = login.json()["access_token"]
            old_headers = {"Authorization": f"Bearer {old_token}"}
            assert client.get("/api/auth/current-user", headers=old_headers).json()["must_change_password"] is True
            assert client.get("/api/cases", headers=old_headers).status_code == 403

            changed = client.post(
                "/api/auth/change-password",
                headers=old_headers,
                json={
                    "current_password": "temporary-password",
                    "new_password": "rotated-password-2026",
                    "confirmation": "rotated-password-2026",
                },
            )
            assert changed.status_code == 200, changed.text
            assert changed.json()["must_change_password"] is False
            assert changed.json()["user"]["must_change_password"] is False
            assert client.get("/api/cases", headers=old_headers).status_code == 401

            new_headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
            assert client.get("/api/cases", headers=new_headers).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
