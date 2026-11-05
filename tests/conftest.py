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
from sqlalchemy import event, text

from backend.app.main import app
from backend.app.routers.auth import get_current_user
from backend.db import database
from backend.db.database import FacilityModel, SessionLocal, StudyModel, UserModel

_test_engine = database.engine


from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute", retval=True)
def intercept_facilities_insert(conn, cursor, statement, parameters, context, executemany):
    if statement.startswith("INSERT INTO facilities "):
        if conn.dialect.name == "sqlite":
            statement = statement.replace("INSERT INTO facilities ", "INSERT OR REPLACE INTO facilities ", 1)
    return statement, parameters

@event.listens_for(FacilityModel.__table__, "after_create")
def auto_seed_default_test_facility(target, connection, **kw):
    try:
        connection.execute(
            text(
                "INSERT INTO facilities (id, facility_code, name, is_active) "
                "VALUES ('FAC-DEFAULT-TEST', 'FAC-DEF-TEST', 'Default Test Facility', 1) "
                "ON CONFLICT(id) DO NOTHING"
            )
        )
    except Exception:
        pass


@event.listens_for(StudyModel, "init")
def auto_default_test_study_facility(target, args, kwargs):
    if "facility_id" not in kwargs:
        kwargs["facility_id"] = "FAC-DEFAULT-TEST"


@event.listens_for(UserModel, "init")
def auto_default_test_user_facility(target, args, kwargs):
    # If caller explicitly passed facility_id (even if None), do not override
    if "facility_id" in kwargs:
        if kwargs.get("facility_id") is None and kwargs.get("role") == "ADMIN" and "is_global_admin" not in kwargs:
            kwargs["is_global_admin"] = True
        return

    # Only default when facility_id was completely omitted
    if not kwargs.get("is_global_admin", False):
        if kwargs.get("role") == "ADMIN":
            kwargs["is_global_admin"] = True
        else:
            kwargs["facility_id"] = "FAC-DEFAULT-TEST"


def pytest_sessionfinish(session, exitstatus):
    """Release pooled SQLite handles before Windows removes the test runtime."""
    from sqlalchemy.orm import close_all_sessions

    close_all_sessions()
    _test_engine.dispose()
    database.engine.dispose()
    assert Path(_runtime.name).resolve().parent == Path(tempfile.gettempdir()).resolve()
    _runtime.cleanup()


@pytest.fixture(autouse=True, scope="function")
def ensure_default_test_tenants():
    with SessionLocal() as db:
        if not db.query(FacilityModel).filter_by(id="FAC-DEFAULT-TEST").first():
            db.add(
                FacilityModel(
                    id="FAC-DEFAULT-TEST",
                    facility_code="FAC-DEF-TEST",
                    name="Default Test Facility",
                    is_active=True,
                )
            )
            db.commit()

        doctor = db.query(UserModel).filter_by(username="doctor").first()
        if doctor and doctor.facility_id != "FAC-DEFAULT-TEST":
            doctor.facility_id = "FAC-DEFAULT-TEST"
            db.commit()

        bacsi = db.query(UserModel).filter_by(username="bacsi").first()
        if bacsi and bacsi.facility_id != "FAC-DEFAULT-TEST":
            bacsi.facility_id = "FAC-DEFAULT-TEST"
            db.commit()

        admin = db.query(UserModel).filter_by(username="admin").first()
        if admin and not admin.is_global_admin:
            admin.is_global_admin = True
            db.commit()
    yield


@pytest.fixture
def doctor_access():
    """Exercise route logic under a doctor identity; auth itself has separate JWT tests."""
    with SessionLocal() as db:
        if not db.query(FacilityModel).filter_by(id="FAC-DEFAULT-TEST").first():
            db.add(FacilityModel(id="FAC-DEFAULT-TEST", facility_code="FAC-DEF-TEST", name="Default Test Facility", is_active=True))
            db.commit()
        db.execute(
            text(
                "INSERT INTO users (id, username, full_name, role, facility_id, is_active, must_change_password) "
                "VALUES ('test-doctor', 'doctor', 'Test Doctor', 'DOCTOR', 'FAC-DEFAULT-TEST', 1, 0) "
                "ON CONFLICT(username) DO UPDATE SET id='test-doctor', facility_id='FAC-DEFAULT-TEST'"
            )
        )
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR", facility_id="FAC-DEFAULT-TEST"
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def evaluation_reviewer_access():
    """Use the SENIOR role required by the current evaluation router contract."""
    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id="test-evaluation-reviewer",
        username="evaluation_reviewer",
        full_name="Synthetic Evaluation Reviewer",
        role="SENIOR",
        facility_id="FAC-DEFAULT-TEST",
    )
    try:
        yield
    finally:
        if original is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original


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
