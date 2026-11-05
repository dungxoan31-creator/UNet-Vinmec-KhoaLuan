"""Tenant-scoped, minimal patient directory for intake workflows."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.security import require_clinical
from backend.db.database import AuditLogModel, PatientDirectoryModel, UserModel, get_db
from backend.schemas.schemas import PatientDirectoryCreateRequest, PatientDirectoryItem, PatientDirectoryUpdateRequest

router = APIRouter(tags=["Patient Directory"])


def _facility_id(current_user: UserModel) -> str:
    if not current_user.facility_id:
        raise HTTPException(status_code=403, detail="Tài khoản chưa được gán cơ sở y tế.")
    return current_user.facility_id


def _item(row: PatientDirectoryModel) -> PatientDirectoryItem:
    return PatientDirectoryItem(
        id=row.id,
        display_name=row.display_name,
        birth_year=row.birth_year,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _record_audit(db: Session, row: PatientDirectoryModel, action: str, user: UserModel, fields: list[str]) -> None:
    db.add(
        AuditLogModel(
            entity_name="patient_directory",
            entity_id=row.id,
            action_type=action,
            actor_id=user.id,
            details={"fields": fields},
            timestamp=datetime.now(UTC),
        )
    )


@router.get("/api/patient-directory")
def list_patient_directory(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=120),
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    facility_id = _facility_id(current_user)
    query = db.query(PatientDirectoryModel).filter(
        PatientDirectoryModel.facility_id == facility_id,
        PatientDirectoryModel.is_active.is_(True),
    )
    if search and search.strip():
        query = query.filter(PatientDirectoryModel.display_name.ilike(f"%{search.strip()}%"))
    total = query.count()
    rows = query.order_by(PatientDirectoryModel.display_name, PatientDirectoryModel.id).offset(offset).limit(limit).all()
    return {"items": [_item(row).model_dump(mode="json") for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("/api/patient-directory", response_model=PatientDirectoryItem, status_code=201)
def create_patient_directory_entry(
    payload: PatientDirectoryCreateRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    facility_id = _facility_id(current_user)
    now = datetime.now(UTC)
    row = PatientDirectoryModel(
        id=str(uuid.uuid4()),
        facility_id=facility_id,
        display_name=payload.display_name,
        birth_year=payload.birth_year,
        version=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _record_audit(db, row, "PATIENT_DIRECTORY_CREATED", current_user, ["display_name", "birth_year"])
    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể lưu hồ sơ trong danh bạ cơ sở.") from exc
    return _item(row)


@router.get("/api/patient-directory/{patient_id}", response_model=PatientDirectoryItem)
def get_patient_directory_entry(
    patient_id: str,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    row = db.query(PatientDirectoryModel).filter(
        PatientDirectoryModel.id == patient_id,
        PatientDirectoryModel.facility_id == _facility_id(current_user),
        PatientDirectoryModel.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ trong cơ sở hiện tại.")
    return _item(row)


@router.put("/api/patient-directory/{patient_id}", response_model=PatientDirectoryItem)
def update_patient_directory_entry(
    patient_id: str,
    payload: PatientDirectoryUpdateRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    facility_id = _facility_id(current_user)
    now = datetime.now(UTC)
    changes = {
        "display_name": payload.display_name,
        "version": payload.expected_version + 1,
        "updated_at": now,
    }
    fields = ["display_name"]
    if "birth_year" in payload.model_fields_set:
        changes["birth_year"] = payload.birth_year
        fields.append("birth_year")
    try:
        updated = db.query(PatientDirectoryModel).filter(
            PatientDirectoryModel.id == patient_id,
            PatientDirectoryModel.facility_id == facility_id,
            PatientDirectoryModel.is_active.is_(True),
            PatientDirectoryModel.version == payload.expected_version,
        ).update(changes, synchronize_session=False)
    except OperationalError as exc:
        db.rollback()
        latest = db.query(PatientDirectoryModel).filter(
            PatientDirectoryModel.id == patient_id,
            PatientDirectoryModel.facility_id == facility_id,
            PatientDirectoryModel.is_active.is_(True),
        ).first()
        if latest is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ trong cơ sở hiện tại.") from exc
        if latest.version != payload.expected_version:
            raise HTTPException(status_code=409, detail="Hồ sơ đã được cập nhật ở phiên khác. Tải lại trước khi lưu.") from exc
        raise HTTPException(status_code=503, detail="Danh bạ đang được cập nhật. Vui lòng thử lại.") from exc
    if updated != 1:
        db.rollback()
        latest = db.query(PatientDirectoryModel).filter(
            PatientDirectoryModel.id == patient_id,
            PatientDirectoryModel.facility_id == facility_id,
            PatientDirectoryModel.is_active.is_(True),
        ).first()
        if latest is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ trong cơ sở hiện tại.")
        raise HTTPException(status_code=409, detail="Hồ sơ đã được cập nhật ở phiên khác. Tải lại trước khi lưu.")
    row = db.query(PatientDirectoryModel).filter(
        PatientDirectoryModel.id == patient_id,
        PatientDirectoryModel.facility_id == facility_id,
        PatientDirectoryModel.is_active.is_(True),
    ).first()
    if row is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ trong cơ sở hiện tại.")
    _record_audit(db, row, "PATIENT_DIRECTORY_UPDATED", current_user, fields)
    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể lưu thay đổi hồ sơ.") from exc
    return _item(row)


@router.delete("/api/patient-directory/{patient_id}", status_code=204)
def deactivate_patient_directory_entry(
    patient_id: str,
    expected_version: int = Query(..., ge=1),
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    facility_id = _facility_id(current_user)
    row = db.query(PatientDirectoryModel).filter(
        PatientDirectoryModel.id == patient_id,
        PatientDirectoryModel.facility_id == facility_id,
        PatientDirectoryModel.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ trong cơ sở hiện tại.")
    if row.version != expected_version:
        raise HTTPException(status_code=409, detail="Hồ sơ đã được cập nhật ở phiên khác. Tải lại trước khi xóa.")
    now = datetime.now(UTC)
    updated = db.query(PatientDirectoryModel).filter(
        PatientDirectoryModel.id == patient_id,
        PatientDirectoryModel.facility_id == facility_id,
        PatientDirectoryModel.is_active.is_(True),
        PatientDirectoryModel.version == expected_version,
    ).update(
        {"is_active": False, "version": expected_version + 1, "updated_at": now},
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Hồ sơ đã được cập nhật ở phiên khác. Tải lại trước khi xóa.")
    row.is_active = False
    row.version = expected_version + 1
    row.updated_at = now
    _record_audit(db, row, "PATIENT_DIRECTORY_DEACTIVATED", current_user, ["is_active"])
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể xóa hồ sơ khỏi danh bạ.") from exc
    return Response(status_code=204)
