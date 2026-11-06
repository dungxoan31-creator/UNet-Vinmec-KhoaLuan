"""Test suite for Visit Management (Block 7) & Multi-Facility Isolation (Block 9)."""

import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    AuditLogModel,
    FacilityModel,
    PatientModel,
    SessionLocal,
    StudyModel,
    UserModel,
    VisitModel,
    get_db,
)


@pytest.fixture
def auth_client():
    test_db = SessionLocal()
    prefix = uuid.uuid4().hex[:6]
    fac_a_code = f"FA-{prefix}".upper()
    fac_b_code = f"FB-{prefix}".upper()
    doc_a_user = f"doc_a_{prefix}"
    doc_b_user = f"doc_b_{prefix}"
    admin_user_name = f"admin_{prefix}"

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

    # Setup doctor in Facility A
    doc_a = UserModel(
        id=str(uuid.uuid4()),
        username=doc_a_user,
        full_name="Doctor Alpha",
        role="DOCTOR",
        facility_id=fac1.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    # Setup doctor in Facility B
    doc_b = UserModel(
        id=str(uuid.uuid4()),
        username=doc_b_user,
        full_name="Doctor Beta",
        role="DOCTOR",
        facility_id=fac2.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    # Setup global admin (facility_id = None)
    admin_user = UserModel(
        id=str(uuid.uuid4()),
        username=admin_user_name,
        full_name="System Admin",
        role="ADMIN",
        facility_id=None,
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
    )
    test_db.add_all([doc_a, doc_b, admin_user])
    test_db.commit()

    token_a = create_access_token({"sub": doc_a_user, "uid": doc_a.id})
    token_b = create_access_token({"sub": doc_b_user, "uid": doc_b.id})
    token_admin = create_access_token({"sub": admin_user_name, "uid": admin_user.id})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "token_a": token_a,
            "token_b": token_b,
            "token_admin": token_admin,
            "fac_a": fac1,
            "fac_b": fac2,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_create_and_get_visit(auth_client):
    client = auth_client["client"]
    token = auth_client["token_a"]

    # 1. Create visit
    resp = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["visit_code"].startswith("VIS-")
    assert len(data["visit_code"].split("-")) == 3
    visit_code = data["visit_code"]
    assert data["status"] == "ACTIVE"
    assert data["is_locked"] is False
    assert data["facility_id"] == auth_client["fac_a"].id

    # 2. Retrieve visit
    resp_get = client.get(
        f"/api/v1/visits/{visit_code}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["visit_code"] == visit_code

    # 3. Lock visit
    resp_lock = client.post(
        f"/api/v1/visits/{visit_code}/lock",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["is_locked"] is True
    assert resp_lock.json()["status"] == "LOCKED"


def test_tenant_isolation_between_facilities(auth_client):
    client = auth_client["client"]
    token_a = auth_client["token_a"]
    token_b = auth_client["token_b"]

    # Doctor A creates visit in Facility A
    resp_create = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code == 201
    visit_code = resp_create.json()["visit_code"]

    # Doctor B (Facility B) attempts to read Facility A visit -> Must be blocked (403)
    resp_cross = client.get(
        f"/api/v1/visits/{visit_code}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_cross.status_code == 403
    assert "cơ sở" in resp_cross.json()["detail"].lower()

    # Doctor B attempts to lock Facility A visit -> Must be blocked (403)
    resp_lock_cross = client.post(
        f"/api/v1/visits/{visit_code}/lock",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_lock_cross.status_code == 403


def test_global_admin_can_access_all_facilities(auth_client):
    client = auth_client["client"]
    token_a = auth_client["token_a"]
    token_admin = auth_client["token_admin"]

    # Doctor A creates visit in Facility A
    resp_create = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code == 201
    visit_code = resp_create.json()["visit_code"]

    # Global admin reads visit in Facility A -> Allowed
    resp_admin = client.get(
        f"/api/v1/visits/{visit_code}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["visit_code"] == visit_code


def test_facility_creation_and_listing(auth_client):
    client = auth_client["client"]
    token_admin = auth_client["token_admin"]
    token_doctor = auth_client["token_a"]

    # Doctor cannot create facility (403)
    resp_forbidden = client.post(
        "/api/v1/facilities",
        json={"facility_code": "FAC-TEST", "name": "Test Facility"},
        headers={"Authorization": f"Bearer {token_doctor}"},
    )
    assert resp_forbidden.status_code == 403

    # Admin creates new facility
    resp_ok = client.post(
        "/api/v1/facilities",
        json={"facility_code": "FAC-C", "name": "Facility Gamma"},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_ok.status_code == 201
    assert resp_ok.json()["facility_code"] == "FAC-C"

    # List facilities
    resp_list = client.get(
        "/api/v1/facilities",
        headers={"Authorization": f"Bearer {token_doctor}"},
    )
    assert resp_list.status_code == 200
    codes = [f["facility_code"] for f in resp_list.json()]
    assert auth_client["fac_a"].facility_code in codes
    assert "FAC-C" in codes
