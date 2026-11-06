"""Test suite for Task 7: R5 (P2) - Visit constraints and unhandled exception logging."""

import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import logging
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    SessionLocal,
    StudyModel,
    UserModel,
    VisitModel,
)


@pytest.fixture
def r5_setup():
    test_db = SessionLocal()
    prefix = uuid.uuid4().hex[:6]
    fac_a_code = f"FA-{prefix}".upper()
    fac_b_code = f"FB-{prefix}".upper()
    doc_a_user = f"doc_a_{prefix}"
    doc_b_user = f"doc_b_{prefix}"

    fac1 = FacilityModel(
        id=str(uuid.uuid4()),
        facility_code=fac_a_code,
        name=f"Facility Alpha {prefix}",
        is_active=True,
    )
    fac2 = FacilityModel(
        id=str(uuid.uuid4()),
        facility_code=fac_b_code,
        name=f"Facility Beta {prefix}",
        is_active=True,
    )
    test_db.add_all([fac1, fac2])

    # Doctor A in Facility A
    doc_a = UserModel(
        id=str(uuid.uuid4()),
        username=doc_a_user,
        full_name="Doctor Alpha",
        role="DOCTOR",
        facility_id=fac1.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    # Doctor B in Facility B
    doc_b = UserModel(
        id=str(uuid.uuid4()),
        username=doc_b_user,
        full_name="Doctor Beta",
        role="DOCTOR",
        facility_id=fac2.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    test_db.add_all([doc_a, doc_b])

    # Study in Facility B
    study_b = StudyModel(
        id=str(uuid.uuid4()),
        study_date="2026-10-31",
        status="PENDING",
        ovary_side="LEFT",
        contralateral_status="NORMAL",
        facility_id=fac2.id,
    )
    test_db.add(study_b)
    test_db.commit()

    token_a = create_access_token({"sub": doc_a_user, "uid": doc_a.id})
    token_b = create_access_token({"sub": doc_b_user, "uid": doc_b.id})

    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield {
            "client": client,
            "token_a": token_a,
            "token_b": token_b,
            "fac_a": fac1,
            "fac_b": fac2,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "study_b": study_b,
            "db": test_db,
        }
    finally:
        test_db.close()


def test_create_visit_with_nonexistent_study_id_returns_404(r5_setup):
    client = r5_setup["client"]
    token_a = r5_setup["token_a"]

    non_existent_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE", "study_id": non_existent_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Không tìm thấy ca khám để liên kết lượt khám."


def test_create_visit_with_cross_facility_study_returns_403(r5_setup):
    client = r5_setup["client"]
    token_a = r5_setup["token_a"]
    study_b = r5_setup["study_b"]

    resp = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE", "study_id": study_b.id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "Không có quyền truy cập dữ liệu của cơ sở khác." in resp.json()["detail"]


def test_create_visit_status_locked_synchronizes_is_locked(r5_setup):
    client = r5_setup["client"]
    token_a = r5_setup["token_a"]
    db = r5_setup["db"]

    resp = client.post(
        "/api/v1/visits",
        json={"status": "LOCKED"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "LOCKED"
    assert data["is_locked"] is True

    # Check database model directly
    visit_in_db = db.query(VisitModel).filter(VisitModel.id == data["id"]).first()
    assert visit_in_db is not None
    assert visit_in_db.status == "LOCKED"
    assert visit_in_db.is_locked is True


def test_unhandled_error_handler_logs_request_id(caplog):
    route_path = "/api/test-r5-crash"
    if not any(getattr(r, "path", None) == route_path for r in app.routes):
        @app.get(route_path)
        def _route_that_crashes():
            raise RuntimeError("Simulated unhandled exception for R5")

    client = TestClient(app, raise_server_exceptions=False)

    # 1. With X-Request-ID header
    custom_request_id = "req-" + uuid.uuid4().hex
    with caplog.at_level(logging.ERROR):
        resp = client.get(route_path, headers={"X-Request-ID": custom_request_id})

    assert resp.status_code == 500
    data = resp.json()
    assert data["detail"] == "Lỗi hệ thống nội bộ."
    assert data["request_id"] == custom_request_id
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert any(
        f"Unhandled server exception [request_id={custom_request_id}]: Simulated unhandled exception for R5" in record.getMessage()
        for record in caplog.records
    )

    # 2. Without X-Request-ID header (auto-generated UUID)
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        resp_no_header = client.get(route_path)

    assert resp_no_header.status_code == 500
    data_no_header = resp_no_header.json()
    assert data_no_header["detail"] == "Lỗi hệ thống nội bộ."
    generated_id = data_no_header["request_id"]
    assert uuid.UUID(generated_id)
    assert any(
        f"Unhandled server exception [request_id={generated_id}]: Simulated unhandled exception for R5" in record.getMessage()
        for record in caplog.records
    )
