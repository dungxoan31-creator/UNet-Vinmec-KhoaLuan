"""PostgreSQL and SQLite database URL configuration and dialect safety tests."""

import os
import subprocess
import sys


def test_database_url_uses_postgresql_and_never_falls_back_to_sqlite(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://testuser:testpass@localhost:5432/test_ovarian_pg"
    env["APP_DB_PATH"] = str(tmp_path / "must-not-fallback.sqlite3")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import backend.db.database as db; "
            "assert db.engine.dialect.name == 'postgresql', f'Expected postgresql dialect, got {db.engine.dialect.name}'; "
            "assert 'test_ovarian_pg' in db.DATABASE_URL; "
            "assert not str(db.DATABASE_URL).startswith('sqlite:'); "
            "print('POSTGRESQL_DIALECT_VERIFIED')",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"Stderr: {result.stderr}\nStdout: {result.stdout}"
    assert "POSTGRESQL_DIALECT_VERIFIED" in result.stdout


def test_database_url_unsupported_scheme_rejected():
    env = os.environ.copy()
    env["DATABASE_URL"] = "mysql://localhost:3306/unsupported_db"
    result = subprocess.run(
        [sys.executable, "-c", "import backend.db.database"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "Unsupported database scheme" in result.stderr
