import sqlite3
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db import database


def _create_legacy_users_table(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                full_name VARCHAR(100) NOT NULL,
                role VARCHAR(20),
                department VARCHAR(100),
                title VARCHAR(50),
                hospital VARCHAR(100),
                avatar VARCHAR(255),
                is_active BOOLEAN,
                must_change_password BOOLEAN NOT NULL DEFAULT 0,
                token_version INTEGER,
                tokens_revoked_at DATETIME,
                created_at DATETIME
            )"""
        )
        connection.execute(
            "INSERT INTO users (id, username, full_name, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ("legacy-id", "legacy-doctor", "Legacy Doctor", "DOCTOR", 1),
        )


def test_legacy_users_survive_email_migration(tmp_path):
    path = tmp_path / "legacy.db"
    _create_legacy_users_table(path)

    migrate = getattr(database, "migrate_auth_email_schema", None)
    assert callable(migrate), "database must expose the auth-email SQLite migration"
    migrate(str(path))

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT id, username, email, email_verified, is_active FROM users WHERE id = ?",
            ("legacy-id",),
        ).fetchone()
    assert row == ("legacy-id", "legacy-doctor", None, 0, 1)


def test_email_unique_index_is_case_insensitive(tmp_path):
    assert hasattr(database.UserModel, "email"), "UserModel must persist registration email"
    engine = create_engine(f"sqlite:///{tmp_path / 'email-index.db'}")
    database.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            database.UserModel(
                id="first", username="first-doctor", full_name="First", email="Doctor@Example.org"
            )
        )
        session.commit()
        session.add(
            database.UserModel(
                id="second", username="second-doctor", full_name="Second", email="doctor@example.org"
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_challenge_schema_stores_expiry_and_resend_state(tmp_path):
    challenge_model = getattr(database, "EmailVerificationChallengeModel", None)
    assert challenge_model is not None, "database must define persistent registration challenges"
    engine = create_engine(f"sqlite:///{tmp_path / 'challenge.db'}")
    database.Base.metadata.create_all(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as session:
        session.add(
            challenge_model(
                id="challenge-id",
                email="doctor@example.org",
                code_digest="digest",
                expires_at=now,
                attempts=2,
                resend_count=1,
                last_sent_at=now,
                created_at=now,
            )
        )
        session.commit()
        saved = session.get(challenge_model, "challenge-id")
        assert saved.email == "doctor@example.org"
        assert saved.code_digest == "digest"
        assert saved.expires_at == now
        assert (saved.attempts, saved.resend_count) == (2, 1)
        assert saved.last_sent_at == now
    engine.dispose()
