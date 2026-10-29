"""A PostgreSQL URL must never be silently ignored in favor of SQLite."""

import os
import subprocess
import sys


def test_database_url_fails_closed_until_postgresql_is_implemented(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://localhost:5432/not-a-test-database"
    env["APP_DB_PATH"] = str(tmp_path / "must-not-fallback.sqlite3")
    result = subprocess.run(
        [sys.executable, "-c", "import backend.db.database"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "does not implement PostgreSQL" in result.stderr
    assert "Refusing to silently use SQLite" in result.stderr
