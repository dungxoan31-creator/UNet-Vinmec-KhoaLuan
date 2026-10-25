"""Isolated runtime and test-only identities for endpoint behavior tests."""

import os
import tempfile
import uuid
from pathlib import Path

# Test fixtures must never be written into the application's default database.
_runtime = tempfile.TemporaryDirectory(prefix="ova-pytest-")
os.environ.setdefault("APP_DB_PATH", str(Path(_runtime.name) / "tests.sqlite3"))
os.environ.setdefault("APP_DATA_DIR", str(Path(_runtime.name) / "data"))
os.environ.setdefault("APP_PATIENT_PID_HMAC_SECRET", "test-only-patient-id-hmac-key-2026-10-21")
os.environ.setdefault("APP_DOCTOR_PASSWORD", "doctor-local-test-2026")
os.environ.setdefault("APP_ADMIN_PASSWORD", "admin-local-test-2026")

import pytest

from backend.app.main import app
from backend.app.routers.auth import get_current_user
from backend.db import database
from backend.db.database import UserModel

_test_engine = database.engine


def pytest_sessionfinish(session, exitstatus):
    """Release pooled SQLite handles before Windows removes the test runtime."""
    from sqlalchemy.orm import close_all_sessions

    close_all_sessions()
    _test_engine.dispose()
    database.engine.dispose()
    assert Path(_runtime.name).resolve().parent == Path(tempfile.gettempdir()).resolve()
    _runtime.cleanup()


@pytest.fixture
def doctor_access():
    """Exercise route logic under a doctor identity; auth itself has separate JWT tests."""
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def active_case_lease():
    """Acquire a real server lease for tests that exercise clinical writes."""

    def acquire(client, study_id, headers=None):
        tab_id = f"test-tab-{uuid.uuid4().hex}"
        page_instance_id = f"test-page-{uuid.uuid4().hex}"
        response = client.post(
            f"/api/workspace/cases/{study_id}/lease",
            json={"tab_id": tab_id, "page_instance_id": page_instance_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        lease = response.json()
        assert lease["granted"] is True, response.text
        return {
            "lease_token": lease["lease_token"],
            "page_instance_id": page_instance_id,
        }

    return acquire
