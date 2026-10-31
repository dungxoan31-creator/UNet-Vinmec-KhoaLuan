import pytest
from fastapi import HTTPException
from backend.services.facility_service import check_facility_access
from backend.db.database import UserModel


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
