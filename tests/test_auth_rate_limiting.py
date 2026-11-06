from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.db.database import AuthRateLimitModel, Base, UserModel, get_db


def test_login_rate_limit_persists_and_expires_after_window(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-auth-rate-limit-123456")
    from backend.app.routers import auth

    now = [datetime(2026, 10, 21, 0, 0, tzinfo=UTC).replace(tzinfo=None)]
    monkeypatch.setattr(auth, "_utc_now_naive", lambda: now[0])
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-rate-limit.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(
            AuthRateLimitModel(
                subject_key="e" * 64,
                window_started_at=now[0] - timedelta(seconds=120),
                attempt_count=2,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    payload = {"username": "unknown-rate-limit", "password": "wrong-password"}
    try:
        with TestClient(app) as first_client:
            for _ in range(5):
                assert first_client.post("/api/auth/login", json=payload).status_code == 401

        with TestClient(app) as second_client:
            assert second_client.post("/api/auth/login", json=payload).status_code == 429

        with Session(engine) as db:
            rate_records = db.query(AuthRateLimitModel).all()
            assert len(rate_records) == 2
            assert all(len(record.subject_key) == 64 for record in rate_records)
            assert all(record.subject_key != payload["username"] for record in rate_records)
            assert sorted(record.attempt_count for record in rate_records) == [5, 6]

        now[0] += timedelta(seconds=61)
        with TestClient(app) as client_after_window:
            assert client_after_window.post("/api/auth/login", json=payload).status_code == 401
        with Session(engine) as db:
            assert sorted(record.attempt_count for record in db.query(AuthRateLimitModel)) == [1, 1]
            assert db.query(AuthRateLimitModel).count() == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_successful_login_clears_persistent_failure_window(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-auth-rate-limit-123456")
    from backend.app.routers.auth import hash_password

    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-rate-limit-reset.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-1",
                username="doctor",
                full_name="Research Clinician",
                role="DOCTOR",
                password_hash=hash_password("secure-password"),
                is_active=True,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            for _ in range(4):
                assert (
                    client.post(
                        "/api/auth/login",
                        json={"username": "doctor", "password": "wrong-password"},
                    ).status_code
                    == 401
                )
            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "doctor", "password": "secure-password"},
                ).status_code
                == 200
            )
            with Session(engine) as db:
                assert [record.attempt_count for record in db.query(AuthRateLimitModel)] == [5]
            assert (
                client.post(
                    "/api/auth/login",
                    json={"username": "doctor", "password": "wrong-password"},
                ).status_code
                == 401
            )
            with Session(engine) as db:
                assert sorted(record.attempt_count for record in db.query(AuthRateLimitModel)) == [1, 6]
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_forgot_password_rate_limit_is_separate_from_login_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-password-recovery-limit-123456")
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'password-recovery-rate-limit.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="doctor-recovery-id",
                username="doctor-recovery",
                full_name="Doctor Recovery",
                role="DOCTOR",
                email="doctor@example.org",
                email_verified=True,
                is_active=True,
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    sent_emails = []
    monkeypatch.setattr(auth, "ensure_password_reset_delivery_configured", lambda: None)
    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        lambda email, token: sent_emails.append((email, token)),
    )
    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            login_payload = {"username": "doctor-recovery", "password": "wrong-password"}
            for _ in range(5):
                assert client.post("/api/auth/login", json=login_payload).status_code == 401
            assert client.post("/api/auth/login", json=login_payload).status_code == 429

            recovery_payload = {"username": "doctor-recovery"}
            for _ in range(5):
                response = client.post("/api/auth/forgot-password", json=recovery_payload)
                assert response.status_code == 200
                assert "doctor@example.org" not in response.text
            assert client.post("/api/auth/forgot-password", json=recovery_payload).status_code == 429

        assert len(sent_emails) == 5
        assert all(email == "doctor@example.org" for email, _token in sent_emails)
        with Session(engine) as db:
            limits = db.query(AuthRateLimitModel).all()
            assert len(limits) == 3
            assert sorted(limit.attempt_count for limit in limits) == [5, 5, 12]
            assert all("doctor-recovery" not in limit.subject_key for limit in limits)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_concurrent_login_attempts_are_counted_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-concurrent-rate-limit-123456")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-auth-rate-limit.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db

    def attempt_login():
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post(
                "/api/auth/login",
                json={"username": "parallel-unknown", "password": "wrong-password"},
            ).status_code

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(executor.map(lambda _index: attempt_login(), range(8)))

        assert all(status in {401, 429} for status in statuses)
        assert statuses.count(429) >= 3
        with Session(engine) as db:
            limits = db.query(AuthRateLimitModel).all()
            assert len(limits) == 2
            assert sorted(limit.attempt_count for limit in limits) == [5, 8]
            assert all(limit.subject_key != "parallel-unknown" for limit in limits)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_public_auth_rate_limit_uses_socket_peer_across_routes_and_ignores_forwarded_headers(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-auth-ip-limit-123456")
    from backend.app.routers import auth

    monkeypatch.setattr(auth, "ensure_password_reset_delivery_configured", lambda: None)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-ip-rate-limit.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    peer = ("192.0.2.10", 55100)
    try:
        with TestClient(app, client=peer) as client:
            for index in range(30):
                response = client.post(
                    "/api/auth/login",
                    headers={"X-Forwarded-For": f"198.51.100.{index + 1}"},
                    json={"username": f"unknown-user-{index}", "password": "wrong-password"},
                )
                assert response.status_code == 401

            # The same source must be throttled across auth endpoints even when
            # the caller changes X-Forwarded-For on every request.
            throttled = client.post(
                "/api/auth/forgot-password",
                headers={"X-Forwarded-For": "203.0.113.44"},
                json={"username": "unknown-recovery-user"},
            )
            assert throttled.status_code == 429
            repeated_throttle = client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": "203.0.113.45"},
                json={"username": "another-unknown-user", "password": "wrong-password"},
            )
            assert repeated_throttle.status_code == 429

        # A different socket peer is independent even when it claims the
        # throttled address in an untrusted forwarding header.
        with TestClient(app, client=("192.0.2.11", 55101)) as other_client:
            response = other_client.post(
                "/api/auth/forgot-password",
                headers={"X-Forwarded-For": "192.0.2.10"},
                json={"username": "unknown-recovery-user"},
            )
            assert response.status_code == 200

        with Session(engine) as db:
            records = db.query(AuthRateLimitModel).all()
            assert any(record.attempt_count == 30 for record in records)
            assert all(record.attempt_count <= 30 for record in records)
            assert all(len(record.subject_key) == 64 for record in records)
            assert all("192.0.2." not in record.subject_key for record in records)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_public_auth_socket_limit_can_be_disabled_when_edge_proxy_enforces_it(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("APP_AUTH_IP_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-auth-ip-limit-toggle-123456")
    from backend.app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-ip-rate-limit-disabled.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [],
            "client": ("192.0.2.12", 55102),
            "server": ("testserver", 443),
            "scheme": "https",
            "query_string": b"",
        }
    )
    try:
        with Session(engine) as db:
            auth._reserve_public_auth_attempt(request, db)
        with Session(engine) as db:
            assert db.query(AuthRateLimitModel).count() == 0
    finally:
        engine.dispose()


def test_public_auth_rate_limit_storage_failure_returns_503(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_AUTH_IP_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-auth-ip-limit-storage-123456")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-ip-rate-limit-storage-error.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    app_tables = [table for table in Base.metadata.sorted_tables if table.name != "auth_rate_limits"]
    Base.metadata.create_all(engine, tables=app_tables)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/auth/login",
                json={"username": "unknown-user", "password": "wrong-password"},
            )
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication is temporarily unavailable."}
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
