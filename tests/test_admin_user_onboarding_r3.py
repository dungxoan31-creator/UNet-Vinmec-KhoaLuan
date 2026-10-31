import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import Base, UserModel, get_db
from backend.schemas.schemas import AdminCreateUserRequest, AdminCreateUserResponse, AdminResetPasswordRequest


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-r3-onboarding-credential-handover-998877")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    db_path = tmp_path / "test_admin_r3.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    admin_id = str(uuid.uuid4())
    doctor_id = str(uuid.uuid4())

    with Session(engine) as db:
        admin_user = UserModel(
            id=admin_id,
            username="admin_r3",
            full_name="Admin R3",
            role="ADMIN",
            password_hash=hash_password("AdminPass123!"),
            is_active=True,
            token_version=1,
        )
        doctor_user = UserModel(
            id=doctor_id,
            username="doctor_r3",
            full_name="Doctor R3",
            role="DOCTOR",
            password_hash=hash_password("DoctorPass123!"),
            is_active=True,
            token_version=1,
            must_change_password=False,
        )
        db.add_all([admin_user, doctor_user])
        db.commit()

    def temporary_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = temporary_db
    client = TestClient(app, raise_server_exceptions=False)

    admin_headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "admin_r3", "uid": admin_id, "token_version": 1})
    }
    doctor_headers = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "doctor_r3", "uid": doctor_id, "token_version": 1})
    }

    try:
        yield {
            "client": client,
            "engine": engine,
            "admin_headers": admin_headers,
            "doctor_headers": doctor_headers,
            "admin_id": admin_id,
            "doctor_id": doctor_id,
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_schema_contracts():
    """Verify schema models match R3 specification."""
    reset_req = AdminResetPasswordRequest(new_password=None)
    assert reset_req.new_password is None

    create_resp = AdminCreateUserResponse(
        status="SUCCESS",
        user_id="test-id",
        username="test_user",
        must_change_password=True,
        temp_password="temp-secret-pass",
    )
    assert create_resp.status == "SUCCESS"
    assert create_resp.temp_password == "temp-secret-pass"


def test_admin_create_doctor_without_password_generates_temp_password_and_requires_change(test_env):
    """
    When admin creates a new doctor without supplying a password:
    - Backend generates a secure temporary password.
    - Sets must_change_password=True.
    - User can authenticate with temp_password and is marked must_change_password.
    """
    client = test_env["client"]
    admin_headers = test_env["admin_headers"]

    payload = {
        "username": "dr_new_specialist",
        "full_name": "BS. Nguyễn Văn Mới",
        "role": "DOCTOR",
        "department": "Khoa Phụ sản",
    }
    resp = client.post("/api/admin/users", headers=admin_headers, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["username"] == "dr_new_specialist"
    assert data["must_change_password"] is True
    assert "temp_password" in data
    assert data["temp_password"] is not None
    assert len(data["temp_password"]) >= 12

    # Verify doctor can login with the temp_password
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "dr_new_specialist", "password": data["temp_password"]},
    )
    assert login_resp.status_code == 200, login_resp.text
    login_data = login_resp.json()
    assert login_data["must_change_password"] is True
    assert "access_token" in login_data


def test_admin_reset_password_with_null_new_password_generates_temp_password_and_revokes_tokens(test_env):
    """
    When admin resets password with {"new_password": null}:
    - Backend generates a new temp_password.
    - must_change_password is set to True.
    - token_version is incremented and previous doctor sessions are revoked.
    - Doctor can login with the new temp_password.
    """
    client = test_env["client"]
    admin_headers = test_env["admin_headers"]
    doctor_headers = test_env["doctor_headers"]
    doctor_id = test_env["doctor_id"]
    engine = test_env["engine"]

    # Verify doctor's existing token works
    check_prev = client.get("/api/auth/current-user", headers=doctor_headers)
    assert check_prev.status_code == 200

    # Admin resets doctor password with explicit null
    reset_resp = client.post(
        f"/api/admin/users/{doctor_id}/reset-password",
        headers=admin_headers,
        json={"new_password": None},
    )
    assert reset_resp.status_code == 200, reset_resp.text
    reset_data = reset_resp.json()

    assert reset_data["status"] == "SUCCESS"
    assert reset_data["must_change_password"] is True
    assert "temp_password" in reset_data
    assert reset_data["temp_password"] is not None
    assert len(reset_data["temp_password"]) >= 12

    # Verify doctor token_version incremented in database
    with Session(engine) as db:
        user = db.query(UserModel).filter(UserModel.id == doctor_id).first()
        assert user is not None
        assert user.token_version == 2
        assert user.must_change_password is True

    # Previous doctor session token must now be revoked (401)
    revoked_check = client.get("/api/auth/current-user", headers=doctor_headers)
    assert revoked_check.status_code == 401

    # Doctor can authenticate using newly generated temporary password
    new_login_resp = client.post(
        "/api/auth/login",
        json={"username": "doctor_r3", "password": reset_data["temp_password"]},
    )
    assert new_login_resp.status_code == 200
    new_login_data = new_login_resp.json()
    assert new_login_data["must_change_password"] is True


def test_non_admin_cannot_create_user_or_reset_password(test_env):
    """Non-admin callers must receive 403 Forbidden, unauthenticated callers receive 401."""
    client = test_env["client"]
    doctor_headers = test_env["doctor_headers"]
    doctor_id = test_env["doctor_id"]

    # Doctor role calling admin endpoints
    create_resp = client.post(
        "/api/admin/users",
        headers=doctor_headers,
        json={"username": "unauthorized_user", "full_name": "Test", "role": "DOCTOR"},
    )
    assert create_resp.status_code == 403

    reset_resp = client.post(
        f"/api/admin/users/{doctor_id}/reset-password",
        headers=doctor_headers,
        json={"new_password": None},
    )
    assert reset_resp.status_code == 403

    # Unauthenticated calling admin endpoints
    unauth_create = client.post(
        "/api/admin/users",
        json={"username": "unauth_user", "full_name": "Test", "role": "DOCTOR"},
    )
    assert unauth_create.status_code == 401

    unauth_reset = client.post(
        f"/api/admin/users/{doctor_id}/reset-password",
        json={"new_password": None},
    )
    assert unauth_reset.status_code == 401


def test_admin_create_user_username_length_boundary(test_env):
    """
    Username length constraints:
    - > 50 characters must be rejected with 422 Unprocessable Entity.
    - Exactly 50 characters must be accepted (200 OK).
    - Empty or whitespace username must be rejected with 422.
    """
    client = test_env["client"]
    admin_headers = test_env["admin_headers"]

    # 51 characters -> rejected with 422
    too_long_username = "u" * 51
    resp_too_long = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": too_long_username, "full_name": "Too Long User", "role": "DOCTOR"},
    )
    assert resp_too_long.status_code == 422

    # Exactly 50 characters -> accepted (200)
    valid_50_char_username = "v" * 50
    resp_50 = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": valid_50_char_username, "full_name": "50 Char User", "role": "DOCTOR"},
    )
    assert resp_50.status_code == 200, resp_50.text
    assert resp_50.json()["username"] == valid_50_char_username

    # Empty username -> 422
    resp_empty = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "   ", "full_name": "Empty User", "role": "DOCTOR"},
    )
    assert resp_empty.status_code == 422
