"""Narrow access rules for technician correction sessions."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.db.database import CorrectionRequestModel, StudyModel, UserModel
from backend.services.facility_service import check_facility_access

CORRECTION_TECHNICIAN_ROLES = {"SENIOR", "TK"}


def pending_correction(db: Session, study_id: str) -> CorrectionRequestModel | None:
    return (
        db.query(CorrectionRequestModel)
        .filter(
            CorrectionRequestModel.study_id == study_id,
            CorrectionRequestModel.status == "PENDING",
        )
        .order_by(CorrectionRequestModel.created_at.desc(), CorrectionRequestModel.id.desc())
        .first()
    )


def is_assigned_correction_technician(
    db: Session, user: UserModel, study_id: str
) -> bool:
    if user.role not in CORRECTION_TECHNICIAN_ROLES or not user.is_active:
        return False
    correction = pending_correction(db, study_id)
    return bool(correction and correction.technician_id == user.id)


def require_case_read_access(db: Session, user: UserModel, study: StudyModel) -> None:
    check_facility_access(user, study.facility_id)
    if user.role == "DOCTOR":
        return
    if user.role in CORRECTION_TECHNICIAN_ROLES and study.status == "SIGNED_PRELIM":
        return
    if is_assigned_correction_technician(db, user, study.id):
        return
    raise HTTPException(status_code=403, detail="Không có quyền xem ca này.")


def require_case_edit_access(db: Session, user: UserModel, study: StudyModel) -> None:
    require_case_read_access(db, user, study)
