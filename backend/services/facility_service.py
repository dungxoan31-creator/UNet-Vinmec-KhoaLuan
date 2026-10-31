"""Facility tenant isolation service for multi-tenant medical access control (R1 P0).

Provides fail-closed authorization checks ensuring users can only access records
belonging to their explicitly assigned healthcare facility, unless operating as a
Global Administrator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from fastapi import HTTPException

if TYPE_CHECKING:
    from backend.db.database import UserModel


def check_facility_access(user: UserModel, entity_facility_id: str | None) -> None:
    """Enforce fail-closed tenant isolation.

    Rules:
    1. Global Admin (`role == "ADMIN"` and `user.facility_id is None`):
       Full global access allowed across all facilities and unassigned records.
    2. Any non-global user without an assigned facility (`user.facility_id is None`):
       Fail-closed 403 error.
    3. Any entity without an assigned facility (`entity_facility_id is None`):
       Fail-closed 403 error for facility-scoped users.
    4. Facility mismatch (`user.facility_id != entity_facility_id`):
       Fail-closed 403 error.
    """
    if getattr(user, "role", None) == "ADMIN" and not getattr(user, "facility_id", None):
        return

    user_facility_id = getattr(user, "facility_id", None)
    if not user_facility_id:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên.",
        )

    if not entity_facility_id:
        raise HTTPException(
            status_code=403,
            detail="Bản ghi không thuộc cơ sở y tế hợp lệ hoặc chưa được định danh cơ sở.",
        )

    if user_facility_id != entity_facility_id:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập dữ liệu của cơ sở khác.",
        )
