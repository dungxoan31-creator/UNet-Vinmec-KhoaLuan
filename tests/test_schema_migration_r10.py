import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC
import pytest
from pydantic import ValidationError
from sqlalchemy import inspect

from backend.db.database import (
    Base,
    CorrectionRequestModel,
    FacilityModel,
    NotificationModel,
    SessionLocal,
    StudyModel,
    UserModel,
    engine,
    init_db,
)
from backend.schemas.schemas import (
    CaseAssignRequest,
    CaseClaimResponse,
    CorrectionCreateRequest,
    CorrectionSaveRequest,
    NotificationListResponse,
    NotificationReadRequest,
    NotificationResponseItem,
)


def test_schema_models_and_migration():
    """Verify StudyModel assignee_id, CorrectionRequestModel, NotificationModel and idempotent init_db."""
    init_db()

    inspector = inspect(engine)

    # 1. Check studies table has assignee_id
    study_cols = {col["name"]: col for col in inspector.get_columns("studies")}
    assert "assignee_id" in study_cols, "studies table must have assignee_id column"
    assert study_cols["assignee_id"]["nullable"] is True

    # 2. Check correction_requests table exists and has proper columns
    assert "correction_requests" in inspector.get_table_names()
    corr_cols = {col["name"]: col for col in inspector.get_columns("correction_requests")}
    for required_col in ["id", "study_id", "review_revision", "reason", "doctor_id", "technician_id", "status", "draft_payload", "created_at", "updated_at"]:
        assert required_col in corr_cols, f"correction_requests missing {required_col}"

    # 3. Check notifications table exists and has proper columns
    assert "notifications" in inspector.get_table_names()
    notif_cols = {col["name"]: col for col in inspector.get_columns("notifications")}
    for required_col in ["id", "recipient_id", "facility_id", "study_id", "event_type", "title", "message", "is_read", "read_at", "created_at", "dedup_key"]:
        assert required_col in notif_cols, f"notifications missing {required_col}"

    # 4. Idempotency of init_db
    init_db()


def test_pydantic_schemas_validation():
    """Verify new Pydantic DTOs for assignment, correction and notification."""
    # CaseAssignRequest
    assign_req = CaseAssignRequest(assignee_id="doc-123")
    assert assign_req.assignee_id == "doc-123"

    with pytest.raises(ValidationError):
        CaseAssignRequest()

    # CaseClaimResponse
    claim_resp = CaseClaimResponse(status="CLAIMED", study_id="study-1", assignee_id="doc-123")
    assert claim_resp.status == "CLAIMED"

    # CorrectionCreateRequest
    corr_create = CorrectionCreateRequest(technician_id="tech-456", reason="Ovary boundary unclear")
    assert corr_create.technician_id == "tech-456"

    # CorrectionSaveRequest
    valid_mask = {"shape": [512, 512], "counts": [262144], "first_val": 0}
    corr_save = CorrectionSaveRequest(
        correction_id="corr-123",
        base_revision=0,
        lease_token="a" * 32,
        page_instance_id="b" * 16,
        draft_payload={
            "images": [
                {
                    "image_id": "img-1",
                    "verified_mask_rle": valid_mask,
                    "notes": "Adjusted margin",
                    "morphology": "unilocular",
                }
            ]
        },
    )
    assert corr_save.draft_payload["images"][0]["notes"] == "Adjusted margin"

    # NotificationResponseItem & NotificationListResponse
    now_iso = datetime.now(UTC).isoformat()
    notif_item = NotificationResponseItem(
        id="notif-1",
        recipient_id="doc-123",
        facility_id="FAC-001",
        study_id="study-1",
        case_id="study-1",
        event_type="CASE_ASSIGNED",
        title="New Case Assigned",
        message="You have been assigned study-1",
        is_read=False,
        read_at=None,
        created_at=now_iso,
    )
    assert notif_item.id == "notif-1"

    notif_list = NotificationListResponse(items=[notif_item], total=1)
    assert notif_list.total == 1
    assert len(notif_list.items) == 1

    # NotificationReadRequest
    read_req = NotificationReadRequest(ids=["notif-1", "notif-2"])
    assert len(read_req.ids) == 2
