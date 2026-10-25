from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.db.database import (
    AuditLogModel,
    Base,
    ConsumedPasswordResetTokenModel,
    UserModel,
    get_db,
)
from backend.services import email_service


def _use_test_database(app, path):
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    return engine


def test_forgot_password_emails_reset_token_without_leaking_it(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-password-reset-123456")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_FROM", "support@example.org")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://research.example.org")
    from backend.app.main import app
    from backend.app.routers import auth

    sent = []
    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        lambda recipient, token: sent.append((recipient, token)),
        raising=False,
    )
    engine = _use_test_database(app, tmp_path / "password-reset.db")
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=True,
                is_active=True,
                token_version=3,
            )
        )
        db.commit()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/forgot-password", json={"username": "doctor"}
            )
            unknown = client.post(
                "/api/auth/forgot-password", json={"username": "unknown"}
            )
            assert response.status_code == unknown.status_code == 200
            assert response.json() == unknown.json()
            assert response.json().get("reset_token") is None
            assert len(sent) == 1
            assert sent[0][0] == "doctor@example.org"

            token = sent[0][1]
            decoded = auth.jwt.decode(
                token, auth._signing_key(), algorithms=[auth.JWT_ALGORITHM]
            )
            assert decoded["purpose"] == "reset_password"
            assert decoded["token_version"] == 3

            reset = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "new-secure-password"},
            )
            assert reset.status_code == 200, reset.text
            with Session(engine) as db:
                user = db.query(UserModel).filter_by(username="doctor").one()
                assert auth.verify_password("new-secure-password", user.password_hash)
                assert user.token_version == 4

            reused = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "another-password"},
            )
            assert reused.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_reset_password_commit_acknowledgement_failure_returns_verified_success(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-password-reset-123456")
    from backend.app.main import app
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'password-reset-commit-acknowledgement.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=True,
                is_active=True,
                password_hash=auth.hash_password("old-secure-password"),
                token_version=3,
            )
        )
        db.commit()
    token = auth.create_reset_token("doctor", token_version=3)
    token_id = auth.jwt.decode(token, auth._signing_key(), algorithms=[auth.JWT_ALGORITHM])["jti"]

    def temporary_db():
        with Session(engine) as db:
            real_commit = db.commit

            def commit_then_lose_acknowledgement():
                real_commit()
                raise OperationalError("COMMIT", {}, RuntimeError("lost reset commit acknowledgement"))

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.commit = commit_then_lose_acknowledgement
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "new-secure-password"},
            )

        assert response.status_code == 200, response.text
        with Session(engine) as db:
            user = db.query(UserModel).filter_by(username="doctor").one()
            assert auth.verify_password("new-secure-password", user.password_hash)
            assert user.token_version == 4
            assert db.get(ConsumedPasswordResetTokenModel, token_id) is not None
            assert db.query(AuditLogModel).filter_by(
                entity_name="consumed_reset_token",
                entity_id=token_id,
                action_type="TOKEN_CONSUMED",
            ).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_forgot_password_reports_email_delivery_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-password-reset-123456")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_FROM", "support@example.org")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://research.example.org")
    from backend.app.main import app
    from backend.app.routers import auth
    from backend.services.email_service import EmailDeliveryError

    def fail_delivery(*_):
        raise EmailDeliveryError("email delivery unavailable")

    monkeypatch.setattr(auth, "send_password_reset_email", fail_delivery, raising=False)
    engine = _use_test_database(app, tmp_path / "password-reset-email-failure.db")
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=True,
                is_active=True,
            )
        )
        db.commit()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/forgot-password", json={"username": "doctor"}
            )
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_password_reset_email_uses_configured_https_app_url(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_FROM", "support@example.org")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://research.example.org/workstation")
    captured = {}

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, **_kwargs):
            pass

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    email_service.send_password_reset_email("doctor@example.org", "signed.token+value")

    body = captured["message"].get_content()
    assert "https://research.example.org/workstation/#reset?token=signed.token%2Bvalue" in body


def test_password_reset_email_rejects_non_https_public_origin(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_FROM", "support@example.org")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://research.example.org")

    from backend.services.email_service import EmailDeliveryError

    try:
        email_service.ensure_password_reset_delivery_configured()
    except EmailDeliveryError:
        pass
    else:
        raise AssertionError("A non-local HTTP reset URL must be rejected.")
