import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    ImageModel,
    PatientModel,
    SessionLocal,
    StudyModel,
    UserModel,
)
from backend.services.facility_service import check_facility_access


class TestFacilityIsolationP0:
    """Test suite for fail-closed facility tenant access control (R1 P0)."""

    def test_same_facility_access_allowed(self):
        """User accessing entity in the same facility is permitted."""
        doctor = UserModel(
            id="doc-1",
            username="doctor_alpha",
            full_name="Dr. Alpha",
            role="DOCTOR",
            facility_id="FAC-001",
        )
        # Should not raise any exception
        check_facility_access(doctor, "FAC-001")

    def test_different_facility_access_forbidden(self):
        """User accessing entity in a different facility raises 403."""
        doctor = UserModel(
            id="doc-1",
            username="doctor_alpha",
            full_name="Dr. Alpha",
            role="DOCTOR",
            facility_id="FAC-001",
        )
        with pytest.raises(HTTPException) as exc_info:
            check_facility_access(doctor, "FAC-002")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Không có quyền truy cập dữ liệu của cơ sở khác."

    def test_user_without_facility_forbidden(self):
        """User without facility assignment (facility_id is None) raises 403."""
        doctor = UserModel(
            id="doc-unassigned",
            username="doctor_floating",
            full_name="Dr. Floating",
            role="DOCTOR",
            facility_id=None,
        )
        # Even if entity has facility_id
        with pytest.raises(HTTPException) as exc_info:
            check_facility_access(doctor, "FAC-001")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên."

        # Even if entity facility_id is also None
        with pytest.raises(HTTPException) as exc_info_null:
            check_facility_access(doctor, None)

        assert exc_info_null.value.status_code == 403
        assert exc_info_null.value.detail == "Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên."

    def test_entity_without_facility_forbidden(self):
        """Entity without facility (entity_facility_id is None) raises 403 for scoped doctor."""
        doctor = UserModel(
            id="doc-1",
            username="doctor_alpha",
            full_name="Dr. Alpha",
            role="DOCTOR",
            facility_id="FAC-001",
        )
        with pytest.raises(HTTPException) as exc_info:
            check_facility_access(doctor, None)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Bản ghi không thuộc cơ sở y tế hợp lệ hoặc chưa được định danh cơ sở."

    def test_global_admin_allowed_everywhere(self):
        """Global Admin (role == 'ADMIN' and facility_id is None) can access any facility and unassigned entities."""
        global_admin = UserModel(
            id="admin-1",
            username="super_admin",
            full_name="Super Admin",
            role="ADMIN",
            facility_id=None,
        )
        # Access facility Alpha
        check_facility_access(global_admin, "FAC-001")
        # Access facility Beta
        check_facility_access(global_admin, "FAC-002")
        # Access unassigned record (entity_facility_id is None)
        check_facility_access(global_admin, None)

    def test_facility_scoped_admin_restricted_to_own_facility(self):
        """Facility Admin (role == 'ADMIN' and facility_id == 'FAC-001') is confined to their facility."""
        facility_admin = UserModel(
            id="admin-fac1",
            username="fac1_admin",
            full_name="Facility 1 Admin",
            role="ADMIN",
            facility_id="FAC-001",
        )
        # Can access own facility
        check_facility_access(facility_admin, "FAC-001")

        # Cannot access another facility
        with pytest.raises(HTTPException) as exc_diff:
            check_facility_access(facility_admin, "FAC-002")
        assert exc_diff.value.status_code == 403
        assert exc_diff.value.detail == "Không có quyền truy cập dữ liệu của cơ sở khác."

        # Cannot access entity with None facility
        with pytest.raises(HTTPException) as exc_null:
            check_facility_access(facility_admin, None)
        assert exc_null.value.status_code == 403
        assert exc_null.value.detail == "Bản ghi không thuộc cơ sở y tế hợp lệ hoặc chưa được định danh cơ sở."


# --- Integration Tests for End-to-End Tenant Isolation (R1 P0) ---


@pytest.fixture
def facility_env(tmp_path):
    test_db = SessionLocal()
    prefix = uuid.uuid4().hex[:6]

    fac_a = FacilityModel(
        id=str(uuid.uuid4()),
        facility_code=f"FA-{prefix}".upper(),
        name=f"Hospital Alpha {prefix}",
        is_active=True,
    )
    fac_b = FacilityModel(
        id=str(uuid.uuid4()),
        facility_code=f"FB-{prefix}".upper(),
        name=f"Hospital Beta {prefix}",
        is_active=True,
    )
    test_db.add_all([fac_a, fac_b])

    doc_a = UserModel(
        id=str(uuid.uuid4()),
        username=f"doc_a_{prefix}",
        full_name="Dr. Alpha",
        role="DOCTOR",
        facility_id=fac_a.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    doc_b = UserModel(
        id=str(uuid.uuid4()),
        username=f"doc_b_{prefix}",
        full_name="Dr. Beta",
        role="DOCTOR",
        facility_id=fac_b.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    doc_unassigned = UserModel(
        id=str(uuid.uuid4()),
        username=f"doc_none_{prefix}",
        full_name="Dr. Floating",
        role="DOCTOR",
        facility_id=None,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    admin_global = UserModel(
        id=str(uuid.uuid4()),
        username=f"admin_glob_{prefix}",
        full_name="Global Administrator",
        role="ADMIN",
        facility_id=None,
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
    )
    test_db.add_all([doc_a, doc_b, doc_unassigned, admin_global])
    test_db.commit()

    token_a = create_access_token({"sub": doc_a.username, "uid": doc_a.id})
    token_b = create_access_token({"sub": doc_b.username, "uid": doc_b.id})
    token_none = create_access_token({"sub": doc_unassigned.username, "uid": doc_unassigned.id})
    token_admin = create_access_token({"sub": admin_global.username, "uid": admin_global.id})

    # Prepare dummy image file
    img_file = tmp_path / f"test_{prefix}.png"
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    dummy_img[20:80, 20:80] = 200
    cv2.imwrite(str(img_file), dummy_img)

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "fac_a": fac_a,
            "fac_b": fac_b,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "doc_unassigned": doc_unassigned,
            "admin_global": admin_global,
            "token_a": token_a,
            "token_b": token_b,
            "token_none": token_none,
            "token_admin": token_admin,
            "db": test_db,
            "prefix": prefix,
            "img_path": str(img_file),
        }
    finally:
        test_db.close()


def test_post_case_facility_assignment(facility_env):
    """POST /api/cases automatically assigns facility and blocks unassigned/mismatched users."""
    client = facility_env["client"]
    token_a = facility_env["token_a"]
    token_none = facility_env["token_none"]
    fac_a = facility_env["fac_a"]
    fac_b = facility_env["fac_b"]
    db = facility_env["db"]

    # 1. Doctor A creates a case -> automatically assigned fac_a.id
    resp = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-1",
            "study_date": "2026-10-31",
            "active_ovary_side": "RIGHT",
        },
    )
    assert resp.status_code == 200, resp.text
    study_id = resp.json()["study_id"]

    study = db.get(StudyModel, study_id)
    assert study is not None
    assert study.facility_id == fac_a.id

    # 2. Doctor without facility tries to create a case -> 403 Forbidden
    resp_unassigned = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_none}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-2",
            "study_date": "2026-10-31",
            "active_ovary_side": "LEFT",
        },
    )
    assert resp_unassigned.status_code == 403
    assert "chưa được gán cơ sở" in resp_unassigned.json()["detail"]

    # 3. Doctor A passes a different facility_id -> 403 Forbidden
    resp_mismatch = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-3",
            "study_date": "2026-10-31",
            "active_ovary_side": "BOTH",
            "facility_id": fac_b.id,
        },
    )
    assert resp_mismatch.status_code == 403


def test_get_case_detail_isolation(facility_env):
    """GET /api/cases/{study_id} enforces tenant isolation."""
    client = facility_env["client"]
    token_a = facility_env["token_a"]
    token_b = facility_env["token_b"]
    token_admin = facility_env["token_admin"]

    # Doctor A creates case
    resp_create = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-10",
            "study_date": "2026-10-31",
            "active_ovary_side": "RIGHT",
        },
    )
    assert resp_create.status_code == 200
    study_id = resp_create.json()["study_id"]

    # Doctor B reads Doctor A's case -> 403 Forbidden
    resp_b = client.get(
        f"/api/cases/{study_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 403
    assert "cơ sở khác" in resp_b.json()["detail"]

    # Doctor A reads own case -> 200 OK
    resp_a = client.get(
        f"/api/cases/{study_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["study_id"] == study_id


def test_case_search_isolation(facility_env):
    """POST /api/workspace/cases/search and GET /api/cases filter cases by tenant."""
    client = facility_env["client"]
    token_a = facility_env["token_a"]
    token_b = facility_env["token_b"]
    token_admin = facility_env["token_admin"]

    # Doctor A creates case
    resp_create = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-20",
            "study_date": "2026-10-31",
            "active_ovary_side": "RIGHT",
        },
    )
    assert resp_create.status_code == 200
    study_id = resp_create.json()["study_id"]

    # Doctor B searches workspace cases -> Does NOT see Doctor A's study
    resp_b_search = client.post(
        "/api/workspace/cases/search",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"limit": 50, "offset": 0},
    )
    assert resp_b_search.status_code == 200
    study_ids_b = [item["study_id"] for item in resp_b_search.json().get("items", [])]
    assert study_id not in study_ids_b

    # Doctor B searches via /api/cases/search -> Does NOT see Doctor A's study
    resp_b_cases_search = client.post(
        "/api/cases/search",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"limit": 50, "offset": 0},
    )
    assert resp_b_cases_search.status_code == 200
    study_ids_b_cases = [item["study_id"] for item in resp_b_cases_search.json()]
    assert study_id not in study_ids_b_cases

    # Doctor B lists cases via GET /api/cases -> Does NOT see Doctor A's study
    resp_b_list = client.get(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b_list.status_code == 200
    study_ids_b_list = [item["study_id"] for item in resp_b_list.json()]
    assert study_id not in study_ids_b_list

    # Doctor A searches -> Sees own study
    resp_a_search = client.post(
        "/api/workspace/cases/search",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"limit": 50, "offset": 0},
    )
    assert resp_a_search.status_code == 200
    study_ids_a = [item["study_id"] for item in resp_a_search.json().get("items", [])]
    assert study_id in study_ids_a


def test_case_lease_isolation(facility_env):
    """POST /api/workspace/cases/{id}/lease restricts edit lease to the owning facility."""
    client = facility_env["client"]
    token_a = facility_env["token_a"]
    token_b = facility_env["token_b"]

    # Doctor A creates case
    resp_create = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-30",
            "study_date": "2026-10-31",
            "active_ovary_side": "RIGHT",
        },
    )
    assert resp_create.status_code == 200
    study_id = resp_create.json()["study_id"]

    lease_payload = {
        "tab_id": "tab-test-1234567890",
        "page_instance_id": "page-instance-1234567890",
        "lease_token": None,
    }

    # Doctor B attempts to acquire lease -> 403 Forbidden
    resp_b_lease = client.post(
        f"/api/workspace/cases/{study_id}/lease",
        headers={"Authorization": f"Bearer {token_b}"},
        json=lease_payload,
    )
    assert resp_b_lease.status_code == 403
    assert "cơ sở khác" in resp_b_lease.json()["detail"]

    # Doctor A acquires lease -> 200 OK
    resp_a_lease = client.post(
        f"/api/workspace/cases/{study_id}/lease",
        headers={"Authorization": f"Bearer {token_a}"},
        json=lease_payload,
    )
    assert resp_a_lease.status_code == 200
    assert resp_a_lease.json()["granted"] is True


def test_case_image_endpoints_isolation(facility_env):
    """Image endpoints prevent cross-facility image retrieval."""
    client = facility_env["client"]
    token_a = facility_env["token_a"]
    token_b = facility_env["token_b"]
    db = facility_env["db"]

    # Doctor A creates case
    resp_create = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": f"P-{facility_env['prefix']}-40",
            "study_date": "2026-10-31",
            "active_ovary_side": "LEFT",
        },
    )
    assert resp_create.status_code == 200
    study_id = resp_create.json()["study_id"]

    # Link an image to this study
    image_id = f"img-{uuid.uuid4().hex[:8]}"
    img_record = ImageModel(
        id=image_id,
        study_id=study_id,
        filename="test.png",
        raw_path=facility_env["img_path"],
        width=100,
        height=100,
        pixel_spacing_mm=0.2,
    )
    db.add(img_record)
    db.commit()

    # Doctor B calls /api/images/{image_id}/source.png -> 403 Forbidden
    resp_b_img = client.get(
        f"/api/images/{image_id}/source.png",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b_img.status_code == 403
    assert "cơ sở khác" in resp_b_img.json()["detail"]

    # Doctor B calls /api/cases/{study_id}/images/{image_id} -> 403 Forbidden
    resp_b_case_img = client.get(
        f"/api/cases/{study_id}/images/{image_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b_case_img.status_code == 403

    # Doctor A calls /api/images/{image_id}/source.png -> 200 OK
    resp_a_img = client.get(
        f"/api/images/{image_id}/source.png",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a_img.status_code == 200

    # Doctor A calls /api/cases/{study_id}/images/{image_id} -> 200 OK
    resp_a_case_img = client.get(
        f"/api/cases/{study_id}/images/{image_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a_case_img.status_code == 200
