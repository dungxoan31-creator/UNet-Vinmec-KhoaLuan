"""
Correction workflow router for technician-assisted mask revisions.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.security import get_current_user, require_clinical
from backend.db.database import (
    AuditLogModel,
    CorrectionRequestModel,
    ImageModel,
    NotificationModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import CorrectionCreateRequest, CorrectionSaveRequest
from backend.services.case_lease_service import require_active_case_lease
from backend.services.correction_access import CORRECTION_TECHNICIAN_ROLES
from backend.services.facility_service import check_facility_access

router = APIRouter(tags=["Correction Workflow"])


@router.get("/api/workspace/cases/{study_id}/correction-technicians")
def list_correction_technicians(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khám.")
    check_facility_access(current_user, study.facility_id)
    users = (
        db.query(UserModel)
        .filter(
            UserModel.facility_id == study.facility_id,
            UserModel.role.in_(CORRECTION_TECHNICIAN_ROLES),
            UserModel.is_active.is_(True),
        )
        .order_by(UserModel.full_name, UserModel.username)
        .all()
    )
    return [
        {"id": user.id, "name": user.full_name or user.username, "role": user.role}
        for user in users
    ]


@router.post("/api/workspace/cases/{study_id}/corrections")
@router.post("/api/cases/{study_id}/corrections")
def create_correction_request(
    study_id: str,
    payload: CorrectionCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """
    Doctor creates a correction request for a technician within the same facility.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khám.")

    # Doctor must have access to this study's facility
    check_facility_access(current_user, study.facility_id)
    if (study.status or "").upper() in {"SIGNED_PRELIM", "APPROVED", "LOCKED"}:
        raise HTTPException(status_code=409, detail="Ca đã khóa hoặc ký; không thể tạo yêu cầu hiệu chỉnh.")

    # Validate technician
    technician = db.query(UserModel).filter(UserModel.id == payload.technician_id).first()
    if not technician:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỹ thuật viên.")

    # Check technician facility and active account.
    if not study.facility_id or technician.facility_id != study.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Kỹ thuật viên phải thuộc cùng cơ sở y tế với ca khám.",
        )

    # Check technician role
    if not technician.is_active or technician.role not in CORRECTION_TECHNICIAN_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Người dùng được chọn không phải là Kỹ thuật viên (TK).",
        )

    open_correction = (
        db.query(CorrectionRequestModel.id)
        .filter(
            CorrectionRequestModel.study_id == study.id,
            CorrectionRequestModel.status.in_(["PENDING", "SUBMITTED"]),
        )
        .first()
    )
    if open_correction:
        raise HTTPException(status_code=409, detail="Ca đang có yêu cầu hiệu chỉnh chưa được bác sĩ rà soát.")

    now_utc = datetime.now(UTC)
    corr = CorrectionRequestModel(
        id=str(uuid.uuid4()),
        study_id=study.id,
        review_revision=study.review_revision,
        reason=payload.reason,
        doctor_id=current_user.id,
        technician_id=technician.id,
        status="PENDING",
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(corr)

    # Notification in same transaction
    notif = NotificationModel(
        id=str(uuid.uuid4()),
        recipient_id=technician.id,
        facility_id=study.facility_id,
        study_id=study.id,
        event_type="CORRECTION_REQUESTED",
        title="Yêu cầu hiệu chỉnh ca khám",
        message=f"Bác sĩ {current_user.full_name or current_user.username} yêu cầu hiệu chỉnh ca khám {study.study_code or study.id}: {payload.reason}",
        is_read=False,
        created_at=now_utc,
        dedup_key=f"CORRECTION_REQUESTED:{corr.id}",
    )
    db.add(notif)
    audit_entry = AuditLogModel(
        entity_name="correction_request",
        entity_id=corr.id,
        action_type="CORRECTION_REQUESTED",
        actor_id=current_user.id,
        details={
            "study_id": study.id,
            "technician_id": technician.id,
            "reason": payload.reason,
            "review_revision": study.review_revision,
        },
    )
    db.add(audit_entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ca đã có yêu cầu hiệu chỉnh đang chờ xử lý.") from exc

    return {
        "status": "SUCCESS",
        "correction_id": corr.id,
        "technician_id": technician.id,
        "study_id": study.id,
    }


@router.put("/api/workspace/cases/{study_id}/corrections")
@router.put("/api/cases/{study_id}/corrections")
def save_draft_correction(
    study_id: str,
    payload: CorrectionSaveRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Assigned technician saves draft corrections and submits revision.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khám.")

    check_facility_access(current_user, study.facility_id)

    # Identify exactly the correction that was displayed in the viewer.
    corr = (
        db.query(CorrectionRequestModel)
        .filter(
            CorrectionRequestModel.id == payload.correction_id,
            CorrectionRequestModel.study_id == study.id,
            CorrectionRequestModel.status == "PENDING",
        )
        .first()
    )
    if not corr:
        raise HTTPException(
            status_code=404,
            detail="Không có yêu cầu hiệu chỉnh nào đang chờ xử lý cho ca khám này.",
        )

    # Caller must be the assigned technician
    if current_user.role not in CORRECTION_TECHNICIAN_ROLES or corr.technician_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Chỉ kỹ thuật viên được giao mới có quyền cập nhật bản sửa dự thảo.",
        )

    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản kỹ thuật viên không còn hoạt động.")
    if corr.review_revision != payload.base_revision or study.review_revision != payload.base_revision:
        raise HTTPException(status_code=409, detail="Phiên bản ca đã thay đổi; hãy tải lại trước khi gửi.")

    expected_image_ids = {
        row[0] for row in db.query(ImageModel.id).filter(ImageModel.study_id == study.id).all()
    }
    submitted_image_ids = {row["image_id"] for row in payload.draft_payload["images"]}
    if not (1 <= len(expected_image_ids) <= 20) or submitted_image_ids != expected_image_ids:
        raise HTTPException(status_code=422, detail="Bản sửa phải chứa chính xác ảnh thuộc ca này (từ 1 đến 20 ảnh).")

    require_active_case_lease(
        db,
        study.id,
        current_user,
        payload.lease_token,
        payload.page_instance_id,
        allow_reviewed=True,
    )

    now_utc = datetime.now(UTC)
    updated_correction = (
        db.query(CorrectionRequestModel)
        .filter(
            CorrectionRequestModel.id == corr.id,
            CorrectionRequestModel.status == "PENDING",
            CorrectionRequestModel.review_revision == payload.base_revision,
        )
        .update(
            {
                CorrectionRequestModel.draft_payload: payload.draft_payload,
                CorrectionRequestModel.status: "SUBMITTED",
                CorrectionRequestModel.updated_at: now_utc,
            },
            synchronize_session=False,
        )
    )
    updated_study = (
        db.query(StudyModel)
        .filter(StudyModel.id == study.id, StudyModel.review_revision == payload.base_revision)
        .update({StudyModel.review_revision: payload.base_revision + 1}, synchronize_session=False)
    )
    if updated_correction != 1 or updated_study != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Yêu cầu hiệu chỉnh đã được gửi hoặc revision đã thay đổi.")
    audit_entry = AuditLogModel(
        entity_name="correction_request",
        entity_id=corr.id,
        action_type="CORRECTION_SUBMITTED",
        actor_id=current_user.id,
        details={
            "study_id": study.id,
            "base_revision": payload.base_revision,
            "image_count": len(payload.draft_payload["images"]),
        },
    )
    db.add(audit_entry)
    db.commit()

    return {
        "status": "SUBMITTED",
        "correction_id": corr.id,
        "study_id": study.id,
        "review_revision": payload.base_revision + 1,
    }
