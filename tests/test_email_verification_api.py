from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.db.database import (
    AuditLogModel,
    Base,
    EmailVerificationChallengeModel,
    UserModel,
    get_db,
)


def test_registration_requires_email_and_email_verification_before_activation(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    delivered = []
    monkeypatch.setattr(
        "backend.app.routers.auth.send_registration_otp",
        lambda recipient, code: delivered.append((recipient, code)),
    )
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'email-verification.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            payload = {
                "username": "new-doctor",
                "password": "secure-password-123",
                "full_name": "New Doctor",
                "email": "Doctor@example.org",
            }
            missing_email = {key: value for key, value in payload.items() if key != "email"}
            assert client.post("/api/auth/register", json=missing_email).status_code == 422

            response = client.post("/api/auth/register", json=payload)
            assert response.status_code == 202, response.text
            body = response.json()
            assert "access_token" not in body
            assert body["email_verification_required"] is True
            assert body["email"] == "doctor@example.org"
            assert delivered and delivered[0][0] == "doctor@example.org"

            with Session(engine) as db:
                user = db.query(UserModel).filter_by(username="new-doctor").one()
                challenge = db.query(EmailVerificationChallengeModel).one()
                assert user.email == "doctor@example.org"
                assert user.email_verified is False
                assert user.is_active is False
                assert challenge.code_digest != delivered[0][1]

            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "new-doctor", "password": "secure-password-123"},
                ).status_code
                == 401
            )

            cooldown = client.post(
                "/api/auth/resend-verification",
                json={"email": "doctor@example.org"},
            )
            assert cooldown.status_code == 200
            assert len(delivered) == 1
            with Session(engine) as db:
                challenge = db.query(EmailVerificationChallengeModel).one()
                challenge.last_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=61)
                db.commit()
            resent = client.post(
                "/api/auth/resend-verification",
                json={"email": "doctor@example.org"},
            )
            assert resent.status_code == 200
            assert len(delivered) == 2

            old_code = client.post(
                "/api/auth/verify-email",
                json={"email": "doctor@example.org", "code": delivered[0][1]},
            )
            assert old_code.status_code == 400
            verified = client.post(
                "/api/auth/verify-email",
                json={"email": "doctor@example.org", "code": delivered[1][1]},
            )
            assert verified.status_code == 200, verified.text
            assert verified.json()["email_verified"] is True

            with Session(engine) as db:
                user = db.query(UserModel).filter_by(username="new-doctor").one()
                assert user.email_verified is True
                assert user.is_active is False
                assert db.query(EmailVerificationChallengeModel).count() == 0

            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "new-doctor", "password": "secure-password-123"},
                ).status_code
                == 401
            )

            with Session(engine) as db:
                user = db.query(UserModel).filter_by(username="new-doctor").one()
                user.is_active = True
                db.commit()

            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "new-doctor", "password": "secure-password-123"},
                ).status_code
                == 200
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_verify_email_commit_acknowledgement_failure_returns_verified_success(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    from backend.app.main import app
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'email-verify-commit-acknowledgement.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=False,
                is_active=False,
            )
        )
        db.add(
            EmailVerificationChallengeModel(
                id="challenge-1",
                email="doctor@example.org",
                code_digest=auth._email_code_digest("doctor@example.org", "123456"),
                expires_at=expires_at,
                attempts=0,
                resend_count=0,
                last_sent_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            real_commit = db.commit

            def commit_then_lose_acknowledgement():
                real_commit()
                raise OperationalError("COMMIT", {}, RuntimeError("lost email verification acknowledgement"))

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.commit = commit_then_lose_acknowledgement
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/verify-email",
                json={"email": "doctor@example.org", "code": "123456"},
            )

        assert response.status_code == 200, response.text
        assert response.json() == {
            "status": "VERIFIED",
            "email_verified": True,
            "activation_pending": True,
        }
        with Session(engine) as db:
            user = db.get(UserModel, "doctor-1")
            assert user.email_verified is True
            assert user.is_active is False
            assert db.get(EmailVerificationChallengeModel, "challenge-1") is None
            assert db.query(AuditLogModel).filter_by(
                entity_name="auth", entity_id="doctor-1", action_type="EMAIL_VERIFIED"
            ).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_email_delivery_failure_rolls_back_pending_registration(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")

    def fail_delivery(*_):
        from backend.services.email_service import EmailDeliveryError

        raise EmailDeliveryError("mail delivery unavailable")

    monkeypatch.setattr("backend.app.routers.auth.send_registration_otp", fail_delivery)
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'email-delivery-failure.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/register",
                json={
                    "username": "mail-down",
                    "password": "secure-password-123",
                    "full_name": "Mail Down",
                    "email": "mail-down@example.org",
                },
            )
            assert response.status_code == 503
            with Session(engine) as db:
                assert db.query(UserModel).count() == 0
                assert db.query(EmailVerificationChallengeModel).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_registration_commit_failure_does_not_send_uncommitted_otp(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    delivered = []
    monkeypatch.setattr(
        "backend.app.routers.auth.send_registration_otp",
        lambda recipient, code: delivered.append((recipient, code)),
    )
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'email-commit-failure.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            def fail_commit():
                raise OperationalError("COMMIT", {}, RuntimeError("simulated database lock"))

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.commit = fail_commit
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/register",
                json={
                    "username": "db-lock-doctor",
                    "password": "secure-password-123",
                    "full_name": "Database Lock",
                    "email": "db-lock@example.org",
                },
            )

        assert response.status_code == 503, response.text
        assert delivered == []
        with Session(engine) as db:
            assert db.query(UserModel).count() == 0
            assert db.query(EmailVerificationChallengeModel).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_registration_commit_acknowledgement_failure_sends_after_persisted_state(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    delivered = []
    monkeypatch.setattr(
        "backend.app.routers.auth.send_registration_otp",
        lambda recipient, code: delivered.append((recipient, code)),
    )
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'email-commit-acknowledgement.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            real_commit = db.commit

            def commit_then_lose_acknowledgement():
                real_commit()
                raise OperationalError("COMMIT", {}, RuntimeError("lost commit acknowledgement"))

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.commit = commit_then_lose_acknowledgement
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/register",
                json={
                    "username": "ack-doctor",
                    "password": "secure-password-123",
                    "full_name": "Acknowledged Doctor",
                    "email": "ack@example.org",
                },
            )

        assert response.status_code == 202, response.text
        assert delivered and delivered[0][0] == "ack@example.org"
        with Session(engine) as db:
            user = db.query(UserModel).filter_by(username="ack-doctor").one()
            challenge = db.query(EmailVerificationChallengeModel).filter_by(email="ack@example.org").one()
            assert user.email_verified is False
            assert user.is_active is False
            assert challenge.expires_at > datetime.now(UTC).replace(tzinfo=None)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.mark.parametrize("commit_persists", [False, True])
def test_resend_otp_sends_only_after_challenge_persistence(
    tmp_path, monkeypatch, commit_persists
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    delivered = []
    monkeypatch.setattr(
        "backend.app.routers.auth.send_registration_otp",
        lambda recipient, code: delivered.append((recipient, code)),
    )
    monkeypatch.setattr("backend.app.routers.auth._new_email_code", lambda: "123456")
    from backend.app.main import app
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / f'resend-otp-{commit_persists}.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    old_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=61)
    old_digest = auth._email_code_digest("doctor@example.org", "654321")
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=False,
                is_active=False,
            )
        )
        db.add(
            EmailVerificationChallengeModel(
                id="challenge-1",
                email="doctor@example.org",
                code_digest=old_digest,
                expires_at=old_sent_at + timedelta(minutes=10),
                attempts=1,
                resend_count=0,
                last_sent_at=old_sent_at,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            real_commit = db.commit

            def fail_or_lose_commit_acknowledgement():
                if commit_persists:
                    real_commit()
                raise OperationalError("COMMIT", {}, RuntimeError("simulated resend commit failure"))

            def fail_rollback():
                raise RuntimeError("simulated resend rollback failure")

            db.commit = fail_or_lose_commit_acknowledgement
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/resend-verification", json={"email": "doctor@example.org"}
            )

        with Session(engine) as db:
            challenge = db.get(EmailVerificationChallengeModel, "challenge-1")
            assert challenge is not None
            if commit_persists:
                assert response.status_code == 200, response.text
                assert delivered == [("doctor@example.org", "123456")]
                assert challenge.code_digest == auth._email_code_digest(
                    "doctor@example.org", "123456"
                )
                assert challenge.resend_count == 1
            else:
                assert response.status_code == 503, response.text
                assert delivered == []
                assert challenge.code_digest == old_digest
                assert challenge.resend_count == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_concurrent_resend_requests_issue_only_one_new_code(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    from backend.app.main import app
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-resend.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    old_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=61)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=False,
                is_active=False,
            )
        )
        db.add(
            EmailVerificationChallengeModel(
                id="challenge-1",
                email="doctor@example.org",
                code_digest=auth._email_code_digest("doctor@example.org", "654321"),
                expires_at=old_sent_at + timedelta(minutes=10),
                attempts=0,
                resend_count=0,
                last_sent_at=old_sent_at,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    barrier = Barrier(2)
    code_lock = Lock()
    codes = iter(("111111", "222222"))
    sent = []

    def synchronized_code():
        with code_lock:
            code = next(codes)
        barrier.wait(timeout=10)
        return code

    monkeypatch.setattr(auth, "_new_email_code", synchronized_code)
    monkeypatch.setattr(
        auth,
        "send_registration_otp",
        lambda recipient, code: sent.append((recipient, code)),
    )

    def resend():
        with TestClient(app) as client:
            return client.post(
                "/api/auth/resend-verification", json={"email": "doctor@example.org"}
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(lambda _index: resend(), range(2)))
        assert [response.status_code for response in responses] == [200, 200]
        assert len(sent) == 1
        assert sent[0][0] == "doctor@example.org"
        with Session(engine) as db:
            challenge = db.get(EmailVerificationChallengeModel, "challenge-1")
            assert challenge.resend_count == 1
            assert challenge.code_digest == auth._email_code_digest(
                "doctor@example.org", sent[0][1]
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_registration_rejects_invalid_email_without_persisting_user(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    monkeypatch.setattr(
        "backend.app.routers.auth.send_registration_otp",
        lambda *_: None,
    )
    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'invalid-email.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/auth/register",
                json={
                    "username": "invalid-email",
                    "password": "secure-password-123",
                    "full_name": "Invalid Email",
                    "email": "not-an-email",
                },
            )
            assert response.status_code == 422
            with Session(engine) as db:
                assert db.query(UserModel).count() == 0
                assert db.query(EmailVerificationChallengeModel).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.mark.parametrize(
    ("initial_attempts", "expected_attempts", "expected_statuses"),
    [(0, 2, [400, 400]), (4, 5, [429, 429])],
)
def test_concurrent_wrong_email_codes_are_counted_without_lost_updates(
    tmp_path, monkeypatch, initial_attempts, expected_attempts, expected_statuses
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-email-verification-123456")
    from backend.app.main import app
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-email-verification-attempts.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    email = "doctor@example.org"
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                email=email,
                email_verified=False,
                is_active=False,
            )
        )
        db.add(
            EmailVerificationChallengeModel(
                id="challenge-1",
                email=email,
                code_digest=auth._email_code_digest(email, "123456"),
                expires_at=now + timedelta(minutes=5),
                attempts=initial_attempts,
                resend_count=0,
                last_sent_at=now,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    both_requests_loaded_challenge = Barrier(2)

    def wrong_digest(_email, _code):
        both_requests_loaded_challenge.wait(timeout=10)
        return "invalid-test-digest"

    monkeypatch.setattr(auth, "_email_code_digest", wrong_digest)

    def submit_wrong_code(code):
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post(
                "/api/auth/verify-email",
                json={"email": email, "code": code},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(submit_wrong_code, ("111111", "222222")))

        assert [response.status_code for response in responses] == expected_statuses
        with Session(engine) as db:
            challenge = db.get(EmailVerificationChallengeModel, "challenge-1")
            assert challenge is not None
            assert challenge.attempts == expected_attempts
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
