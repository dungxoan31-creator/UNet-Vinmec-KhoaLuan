"""Encounter and Facility Management Router (Block 7 & Block 9).

Provides first-class Visit management with high-entropy visit_code (VIS-YYYYMMDD-XXXXXXXX),
tenant isolation across facilities, atomic locking, and comprehensive audit trails.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.core.patient_identity import (
    normalize_source_patient_id,
    patient_id_digest,
    patient_pid_secret,
)
from backend.services.patient_identity import get_or_create_patient

from backend.app.security import get_current_user, require_admin, require_clinical
from backend.db.database import (
    AuditLogModel,
    FacilityModel,
    ImageModel,
    PatientModel,
    StudyModel,
    UserModel,
    VisitModel,
    generate_visit_code,
    get_db,
)
from backend.services.facility_service import check_facility_access
from backend.schemas.schemas import (
    FacilityCreateRequest,
    FacilityResponse,
    VisitCreateRequest,
    VisitListResponse,
    VisitResponse,
    VisitStudySummary,
)

logger = logging.getLogger("workstation.visits")

router = APIRouter(tags=["Visits & Multi-Facility Management"])


def _format_visit_response(visit: VisitModel, db: Session) -> VisitResponse:
    studies = (
        db.query(StudyModel)
        .filter(StudyModel.visit_id == visit.id)
        .order_by(StudyModel.created_at.desc())
        .all()
    )
    study_summaries = []
    for s in studies:
        img_count = db.query(ImageModel).filter(ImageModel.study_id == s.id).count()
        study_summaries.append(
            VisitStudySummary(
                id=s.id,
                study_date=s.study_date or "",
                status=s.status,
                ovary_side=s.ovary_side,
                images_count=img_count,
            )
        )

    patient_pid = None
    if visit.patient:
        patient_pid = visit.patient.anonymized_pid
    elif visit.patient_id:
        patient_pid = visit.patient_id

    return VisitResponse(
        id=visit.id,
        visit_code=visit.visit_code,
        facility_id=visit.facility_id,
        patient_id=patient_pid,
        status=visit.status,
        is_locked=visit.is_locked,
        created_at=visit.created_at,
        updated_at=visit.updated_at or visit.created_at,
        studies=study_summaries,
    )


# --- Visit Endpoints ---


@router.post("/api/v1/visits", response_model=VisitResponse, status_code=201)
@router.post("/visits", response_model=VisitResponse, status_code=201)
def create_visit(
    req: VisitCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """Create a new clinical encounter with high-entropy unique visit_code."""
    facility_id = req.facility_id or current_user.facility_id
    if not (current_user.role == "ADMIN" and not current_user.facility_id) and not current_user.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên.",
        )
    if current_user.facility_id and facility_id != current_user.facility_id:
        raise HTTPException(status_code=403, detail="Không thể tạo lượt khám ngoài cơ sở của bạn.")

    # Generate unique visit code with collision retry
    for _ in range(5):
        code = generate_visit_code()
        if not db.query(VisitModel).filter(VisitModel.visit_code == code).first():
            break
    else:
        raise HTTPException(status_code=500, detail="Không thể sinh mã lượt khám duy nhất.")

    # If linked study provided, validate access and existence
    study = None
    if req.study_id:
        study = (
            db.query(StudyModel)
            .options(joinedload(StudyModel.patient))
            .filter(StudyModel.id == req.study_id)
            .first()
        )
        if not study:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy ca khám để liên kết lượt khám.",
            )
        check_facility_access(current_user, study.facility_id)
        if not facility_id:
            facility_id = study.facility_id
        elif study.facility_id and facility_id != study.facility_id:
            raise HTTPException(status_code=403, detail="Cơ sở của ca khám không khớp với lượt khám.")

        study_pid_values = set()
        if study.patient_id:
            study_pid_values.add(study.patient_id)
        if study.patient and study.patient.anonymized_pid:
            study_pid_values.add(study.patient.anonymized_pid)

        if req.patient_id and study.patient:
            secret = patient_pid_secret()
            req_norm = normalize_source_patient_id(req.patient_id)
            req_digest = patient_id_digest(req_norm, secret, facility_id=facility_id)
            legacy_digest = patient_id_digest(req_norm, secret)
            is_match = (
                req.patient_id in study_pid_values
                or req_digest == study.patient.source_pid_hmac
                or legacy_digest == study.patient.legacy_source_pid_hmac
            )
            if not is_match:
                raise HTTPException(
                    status_code=422,
                    detail="Mã bệnh nhân của lượt khám không khớp với ca khám được liên kết.",
                )

    if not facility_id:
        raise HTTPException(
            status_code=422,
            detail="Vui lòng chỉ định cơ sở y tế (facility_id) cho lượt khám.",
        )

    # Determine patient synchronization between study and visit
    target_patient = None
    if study:
        if study.patient:
            target_patient = study.patient
        elif req.patient_id:
            target_patient = get_or_create_patient(db, req.patient_id, facility_id=facility_id)
            study.patient_id = target_patient.id
            study.patient = target_patient
        else:
            target_patient = None
    else:
        if req.patient_id:
            target_patient = get_or_create_patient(db, req.patient_id, facility_id=facility_id)
        else:
            target_patient = None

    is_locked = True if req.status == "LOCKED" else False
    now = datetime.now(UTC)

    visit = VisitModel(
        id=str(uuid.uuid4()),
        visit_code=code,
        facility_id=facility_id,
        patient_id=target_patient.id if target_patient else None,
        patient=target_patient,
        status=req.status or "ACTIVE",
        is_locked=is_locked,
        created_at=now,
        updated_at=now,
    )
    db.add(visit)

    # If linked study provided, associate it
    if study:
        study.visit_id = visit.id
        if facility_id:
            study.facility_id = facility_id

    # Audit log
    audit = AuditLogModel(
        entity_name="Visit",
        entity_id=visit.id,
        action_type="VISIT_CREATED",
        actor_id=current_user.id,
        details={"visit_code": code, "facility_id": facility_id},
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(visit)
    logger.info("Created visit %s by user %s", code, current_user.username)
    return _format_visit_response(visit, db)


@router.get("/api/v1/visits", response_model=VisitListResponse)
@router.get("/visits", response_model=VisitListResponse)
def list_visits(
    status: str | None = Query(None, description="Filter by status: ACTIVE, COMPLETED, LOCKED"),
    search: str | None = Query(None, description="Search visit_code"),
    facility_id: str | None = Query(None, description="Filter by facility"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """List clinical encounters scoped to user's facility with search and pagination."""
    query = db.query(VisitModel)

    # Facility scoping
    if current_user.role == "ADMIN" and not current_user.facility_id:
        if facility_id:
            query = query.filter(VisitModel.facility_id == facility_id)
    elif current_user.facility_id:
        query = query.filter(VisitModel.facility_id == current_user.facility_id)
    else:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên.",
        )

    if status:
        query = query.filter(VisitModel.status == status)
    if search:
        query = query.filter(VisitModel.visit_code.ilike(f"%{search}%"))

    total = query.count()
    visits = (
        query.order_by(VisitModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_format_visit_response(v, db) for v in visits]
    return VisitListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/api/v1/visits/{visit_code}", response_model=VisitResponse)
@router.get("/visits/{visit_code}", response_model=VisitResponse)
def get_visit_by_code(
    visit_code: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Retrieve visit details and linked studies, enforcing tenant boundaries."""
    visit = db.query(VisitModel).filter(VisitModel.visit_code == visit_code).first()
    if not visit:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lượt khám với mã {visit_code}")

    check_facility_access(current_user, visit.facility_id)
    return _format_visit_response(visit, db)


@router.post("/api/v1/visits/{visit_code}/lock", response_model=VisitResponse)
@router.post("/visits/{visit_code}/lock", response_model=VisitResponse)
def lock_visit(
    visit_code: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """Lock visit to prevent subsequent modifications or reassignment."""
    visit = db.query(VisitModel).filter(VisitModel.visit_code == visit_code).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Lượt khám không tồn tại.")

    check_facility_access(current_user, visit.facility_id)
    if visit.is_locked:
        return _format_visit_response(visit, db)

    now = datetime.now(UTC)
    visit.is_locked = True
    visit.status = "LOCKED"
    visit.updated_at = now

    audit = AuditLogModel(
        entity_name="Visit",
        entity_id=visit.id,
        action_type="VISIT_LOCKED",
        actor_id=current_user.id,
        details={"visit_code": visit_code},
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(visit)
    logger.info("Locked visit %s by user %s", visit_code, current_user.username)
    return _format_visit_response(visit, db)


# --- Multi-facility Endpoints (Block 9) ---


@router.post("/api/v1/facilities", response_model=FacilityResponse, status_code=201)
def create_facility(
    req: FacilityCreateRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Create a new healthcare facility tenant (System Administrator only)."""
    existing = db.query(FacilityModel).filter(FacilityModel.facility_code == req.facility_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Mã cơ sở '{req.facility_code}' đã tồn tại.")

    now = datetime.now(UTC)
    facility = FacilityModel(
        id=str(uuid.uuid4()),
        facility_code=req.facility_code.strip().upper(),
        name=req.name.strip(),
        is_active=True,
        config=req.config,
        created_at=now,
    )
    db.add(facility)

    audit = AuditLogModel(
        entity_name="Facility",
        entity_id=facility.id,
        action_type="FACILITY_CREATED",
        actor_id=current_user.id,
        details={"facility_code": facility.facility_code, "name": facility.name},
        timestamp=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(facility)
    return FacilityResponse(
        id=facility.id,
        facility_code=facility.facility_code,
        name=facility.name,
        is_active=facility.is_active,
        created_at=facility.created_at,
    )


@router.get("/api/v1/facilities", response_model=list[FacilityResponse])
def list_facilities(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """List all registered facilities."""
    facilities = db.query(FacilityModel).filter(FacilityModel.is_active == True).order_by(FacilityModel.facility_code).all()
    return [
        FacilityResponse(
            id=f.id,
            facility_code=f.facility_code,
            name=f.name,
            is_active=f.is_active,
            created_at=f.created_at,
        )
        for f in facilities
    ]
