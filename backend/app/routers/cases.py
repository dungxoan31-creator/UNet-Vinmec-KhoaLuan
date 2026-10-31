"""
Clinical Cases CRUD and Sample Cases endpoints.
"""

import base64
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import cv2
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.config import SYNTHETIC_DEMO_MODE, UPLOAD_DIR
from backend.app.security import require_admin, require_clinical
from backend.core.case_idempotency import (
    case_create_idempotency_digest,
    case_create_payload_digest,
)
from backend.core.patient_identity import patient_id_digest
from backend.db.database import (
    ActiveLearningQueueModel,
    AuditLogModel,
    HITLEventModel,
    HITLSessionModel,
    ImageModel,
    PatientModel,
    PendingFileDeletionModel,
    ReviewBatchModel,
    ReviewModel,
    StudyModel,
    UIEventModel,
    UserModel,
    VisitNumberCapacityExceeded,
    get_db,
)
from backend.schemas.schemas import (
    CaseLeaseReleaseRequest,
    CaseLeaseRequest,
    CaseSearchRequest,
    CreateCaseRequest,
)
from backend.services.case_lease_service import acquire_case_lease, release_case_lease
from backend.services.facility_service import check_facility_access
from backend.services.file_deletion_service import (
    enqueue_upload_deletions,
    retry_pending_file_deletions,
)
from backend.services.image_service import (
    decode_ultrasound_image,
    get_image_calibration,
)
from backend.services.measurement_safety import (
    TRUSTED_CALIBRATION_SOURCES,
    prediction_measurements_match_calibration,
)
from backend.services.measurement_safety import (
    is_finite_physical_value as _finite_physical_value,
)
from backend.services.measurement_safety import (
    strip_unverified_physical_measurements as _strip_unverified_physical_measurements,
)
from backend.services.patient_identity import get_or_create_patient
from backend.services.review_service import (
    prepare_legacy_active_learning_cleanup,
    remove_legacy_active_learning_samples,
)

router = APIRouter(tags=["Clinical Cases"])
logger = logging.getLogger(__name__)
def _verified_review_calibration_source(review):
    feedback = review.hitl_feedback if isinstance(review.hitl_feedback, dict) else {}
    context = feedback.get("measurement_context")
    if (
        isinstance(context, dict)
        and context.get("version") == 1
        and context.get("status") == "AVAILABLE"
        and context.get("calibration_source") in TRUSTED_CALIBRATION_SOURCES
    ):
        return context["calibration_source"]
    return None

def _safe_review_feedback(review, verified_source):
    feedback = review.hitl_feedback if isinstance(review.hitl_feedback, dict) else {}
    safe_feedback = dict(feedback)
    manual = feedback.get("manual_measurements")
    if not isinstance(manual, dict):
        return safe_feedback
    safe_manual = {}
    for label, measurement in manual.items():
        if not isinstance(measurement, dict):
            safe_manual[label] = measurement
            continue
        source_matches = (
            verified_source is not None
            and measurement.get("calibrated") is True
            and measurement.get("calibration_source") == verified_source
            and _finite_physical_value(measurement.get("diameter_mm"))
        )
        safe_manual[label] = (
            dict(measurement)
            if source_matches
            else _strip_unverified_physical_measurements(measurement)
        )
    safe_feedback["manual_measurements"] = safe_manual
    return safe_feedback

def _verify_case_delete_commit(bind, study_id: str, actor_id: str, deletion_ids: list[str]) -> bool | None:
    """Return True/False for a confirmed delete outcome, or None when uncertain."""
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            if verify_db.get(StudyModel, study_id) is not None:
                return False
            audit_exists = (
                verify_db.query(AuditLogModel.id)
                .filter_by(
                    entity_name="study",
                    entity_id=study_id,
                    action_type="CLINICAL_CASE_DELETE",
                    actor_id=actor_id,
                )
                .first()
                is not None
            )
            if not audit_exists:
                return None
            if deletion_ids:
                persisted_deletions = (
                    verify_db.query(PendingFileDeletionModel.id)
                    .filter(PendingFileDeletionModel.id.in_(deletion_ids))
                    .count()
                )
                if persisted_deletions != len(deletion_ids):
                    return None
            return True
    except Exception:
        return None


def _retry_case_file_deletions(bind, upload_root: Path, deletion_ids: list[str]) -> bool:
    """Retry committed file deletions independently of the case transaction session."""
    if not deletion_ids:
        return False
    if bind is None:
        logger.error(
            "Case was deleted but its file cleanup could not obtain a database bind.",
            extra={"case_delete_cleanup_pending": True},
        )
        return True
    try:
        with Session(bind=bind) as cleanup_db:
            return retry_pending_file_deletions(cleanup_db, upload_root, deletion_ids)
    except Exception as exc:
        logger.error(
            "Case was deleted but outbox retry did not complete; startup will retry.",
            extra={
                "case_delete_cleanup_pending": True,
                "cleanup_error_type": type(exc).__name__,
            },
        )
        return True


@router.post("/api/workspace/cases/{study_id}/lease")
def post_case_lease(
    study_id: str,
    request: CaseLeaseRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    return acquire_case_lease(
        db,
        study_id,
        current_user,
        request.tab_id,
        request.page_instance_id,
        request.lease_token,
    )


@router.delete("/api/workspace/cases/{study_id}/lease")
def delete_case_lease(
    study_id: str,
    request: CaseLeaseReleaseRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    return release_case_lease(
        db,
        study_id,
        current_user,
        request.lease_token,
        request.page_instance_id,
    )


def _case_create_matches_request(study: StudyModel, payload_digest: str) -> bool:
    return study.idempotency_request_digest == payload_digest


def _case_create_response(study: StudyModel, *, replayed: bool = False) -> dict:
    return {
        "study_id": study.id,
        "study_code": study.study_code,
        "visit_no": study.visit_no,
        "patient_id": study.patient.anonymized_pid,
        "study_date": study.study_date,
        "status": study.status,
        "ovary_side": study.ovary_side,
        "contralateral_status": study.contralateral_status,
        "message": (
            "Ca đã được khởi tạo trước đó; tiếp tục dùng ca này."
            if replayed
            else "Khởi tạo ca khám mới thành công."
        ),
    }


def _idempotent_study(db: Session, digest: str) -> StudyModel | None:
    return (
        db.query(StudyModel)
        .options(joinedload(StudyModel.patient))
        .filter(StudyModel.idempotency_key_digest == digest)
        .first()
    )


@router.post("/api/cases")
def create_new_case(
    req: CreateCaseRequest,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """
    Create a new clinical study case.
    """
    clean_pid = req.patient_id.strip() if req.patient_id else ""
    if not clean_pid:
        raise HTTPException(status_code=422, detail="Mã định danh bệnh nhân (PID) không được để trống.")
    if SYNTHETIC_DEMO_MODE and not clean_pid.upper().startswith("DEMO-SYNTHETIC-"):
        raise HTTPException(
            status_code=422,
            detail="Chế độ demo chỉ cho phép mã ca DEMO-SYNTHETIC-*; không nhập thông tin bệnh nhân.",
        )
    if SYNTHETIC_DEMO_MODE and (req.patient_age or req.clinical_notes):
        raise HTTPException(
            status_code=422,
            detail="Sandbox demo không nhận tuổi hoặc ghi chú lâm sàng có thể chứa thông tin bệnh nhân.",
        )

    is_global_admin = current_user.role == "ADMIN" and not current_user.facility_id
    if not is_global_admin and not current_user.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên.",
        )
    if not is_global_admin and req.facility_id and req.facility_id != current_user.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền tạo ca khám cho cơ sở khác.",
        )
    assigned_facility_id = req.facility_id if is_global_admin else current_user.facility_id

    idempotency_digest = case_create_idempotency_digest(idempotency_key, current_user.id)
    request_digest = case_create_payload_digest(req.model_dump(mode="json"), current_user.id)
    existing = _idempotent_study(db, idempotency_digest)
    if existing:
        check_facility_access(current_user, existing.facility_id)
        if not _case_create_matches_request(existing, request_digest):
            raise HTTPException(
                status_code=409,
                detail="Khóa thử lại đã được dùng cho dữ liệu intake khác. Mở intake mới trước khi tạo ca khác.",
            )
        return _case_create_response(existing, replayed=True)

    try:
        patient = get_or_create_patient(db, clean_pid, req.patient_age)

        study_id = str(uuid.uuid4())
        study_code = (
            req.study_code.strip()
            if req.study_code
            else f"STD-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        )
        study = StudyModel(
            id=study_id,
            patient_id=patient.id,
            study_code=study_code,
            study_date=req.study_date,
            idempotency_key_digest=idempotency_digest,
            idempotency_request_digest=request_digest,
            status="PENDING",
            probe_type=req.probe_type or None,
            ovary_side=req.active_ovary_side,
            contralateral_status=req.contralateral_status,
            clinical_indication=req.clinical_notes or None,
            facility_id=assigned_facility_id,
        )
        db.add(study)
        db.commit()
    except VisitNumberCapacityExceeded as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Đã hết dải Visit No 6 chữ số. Cần quản trị viên xử lý trước khi tạo lượt mới.",
        ) from exc
    except IntegrityError:
        db.rollback()
        existing = _idempotent_study(db, idempotency_digest)
        if existing:
            check_facility_access(current_user, existing.facility_id)
            if not _case_create_matches_request(existing, request_digest):
                raise HTTPException(
                    status_code=409,
                    detail="Khóa thử lại đã được dùng cho dữ liệu intake khác. Mở intake mới trước khi tạo ca khác.",
                )
            return _case_create_response(existing, replayed=True)
        raise
    except Exception:
        db.rollback()
        raise

    return _case_create_response(study)


@router.get("/api/cases")
def list_cases(
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    return _query_cases(
        search, status, date, limit, offset, db, allow_source_pid=False, current_user=current_user
    )


@router.post("/api/cases/search")
def search_cases(
    request: CaseSearchRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Search cases without placing a potentially identifying PID in the URL."""
    return _query_cases(
        request.search,
        request.status,
        request.date,
        request.limit,
        request.offset,
        db,
        allow_source_pid=True,
        patient_id=request.patient_id,
        statuses=request.statuses,
        sort=request.sort,
        direction=request.direction,
        current_user=current_user,
    )


def _filtered_cases_query(
    search,
    status,
    date,
    db,
    allow_source_pid,
    *,
    patient_id=None,
    statuses=None,
    current_user=None,
):
    query = db.query(StudyModel).join(PatientModel)
    if current_user is not None:
        if getattr(current_user, "role", None) == "ADMIN" and not getattr(current_user, "facility_id", None):
            pass
        elif getattr(current_user, "facility_id", None):
            query = query.filter(StudyModel.facility_id == current_user.facility_id)
        else:
            query = query.filter(StudyModel.id.is_(None))
    if status and status.upper() != "ALL":
        query = query.filter(StudyModel.status == status.upper())
    if statuses:
        query = query.filter(StudyModel.status.in_([value.upper() for value in statuses]))
    if patient_id is not None:
        query = query.filter(PatientModel.anonymized_pid == patient_id)
    if date:
        query = query.filter(StudyModel.study_date.startswith(date))
    if search:
        search_value = search.strip()
        if search_value:
            search_fmt = f"%{search_value}%"
            search_conditions = [
                PatientModel.anonymized_pid.ilike(search_fmt),
                StudyModel.study_code.ilike(search_fmt),
                StudyModel.clinical_indication.ilike(search_fmt),
            ]
            if allow_source_pid and len(search_value) <= 64:
                search_conditions.append(PatientModel.source_pid_hmac == patient_id_digest(search_value))
            query = query.filter(or_(*search_conditions))
    return query


def _query_cases(
    search,
    status,
    date,
    limit,
    offset,
    db,
    allow_source_pid,
    *,
    sort="created_at",
    direction="desc",
    include_total=False,
    patient_id=None,
    statuses=None,
    current_user=None,
):
    """
    List all cases with search and filtering for Dashboard & History.
    """
    filtered_query = _filtered_cases_query(
        search,
        status,
        date,
        db,
        allow_source_pid,
        patient_id=patient_id,
        statuses=statuses,
        current_user=current_user,
    )
    total = filtered_query.order_by(None).count() if include_total else None
    query = filtered_query.options(
        joinedload(StudyModel.patient),
        selectinload(StudyModel.images).selectinload(ImageModel.predictions),
        selectinload(StudyModel.images).selectinload(ImageModel.reviews),
    )
    sort_columns = {
        "study_code": StudyModel.study_code,
        "status": StudyModel.status,
        "study_date": StudyModel.study_date,
        "created_at": StudyModel.created_at,
    }
    sort_column = sort_columns.get(sort, StudyModel.created_at)
    order = asc if direction == "asc" else desc
    query = query.order_by(order(sort_column), order(StudyModel.id))
    if offset:
        query = query.offset(offset)
    query = query.limit(limit)

    studies = query.all()

    cases_list = []
    for s in studies:
        first_img = s.images[0] if s.images else None
        last_review = first_img.reviews[-1] if (first_img and first_img.reviews) else None
        pred = first_img.predictions[-1] if (first_img and first_img.predictions) else None
        verified_review_source = _verified_review_calibration_source(last_review) if last_review else None
        prediction_measurements = pred.measurements if pred and isinstance(pred.measurements, dict) else {}
        image_calibration = (
            get_image_calibration(first_img)
            if first_img and pred and not last_review
            else None
        )
        verified_prediction = prediction_measurements_match_calibration(
            prediction_measurements,
            image_calibration,
            pred.provenance_json if pred else None,
        )
        worklist_diameter_mm = None
        if last_review and verified_review_source and _finite_physical_value(last_review.max_diameter_mm):
            worklist_diameter_mm = last_review.max_diameter_mm
        elif (
            not last_review
            and verified_prediction
            and _finite_physical_value(prediction_measurements.get("max_diameter_mm"))
        ):
            worklist_diameter_mm = prediction_measurements["max_diameter_mm"]

        cases_list.append(
            {
                "id": s.id,
                "study_id": s.id,
                "study_code": s.study_code or s.id[:8],
                "visit_no": s.visit_no,
                "patient_id": s.patient.anonymized_pid,
                "patient_age": s.patient.age_bucket,
                "study_date": s.study_date,
                "status": s.status,
                "ovary_side": s.ovary_side,
                "contralateral_status": s.contralateral_status,
                "images": [
                    {
                        "id": img.id,
                        "filename": img.filename,
                        "laterality": getattr(img, "laterality", None),
                    }
                    for img in s.images
                ],
                "image_id": first_img.id if first_img else None,
                "image_filename": first_img.filename if first_img else None,
                "lesion_type": last_review.lesion_type
                if last_review
                else (
                    (pred.measurements.get("lesions", [{}])[0].get("lesion_type", "Chưa phân tích")
                     if (pred.measurements.get("lesions") and len(pred.measurements.get("lesions")) > 0 and isinstance(pred.measurements.get("lesions")[0], dict))
                     else "Chưa phân tích")
                    if (pred and isinstance(pred.measurements, dict))
                    else "Chưa phân tích"
                ),
                "max_diameter_mm": worklist_diameter_mm,
                "doctor_action": last_review.doctor_action if last_review else None,
                "created_at": s.created_at.strftime("%d/%m/%Y %H:%M"),
            }
        )

    return {"items": cases_list, "total": total} if include_total else cases_list


@router.post("/api/workspace/cases/search")
def search_workspace_cases(
    request: CaseSearchRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Return a bounded, sortable clinical worklist page and its filtered total."""
    return _query_cases(
        request.search,
        request.status,
        request.date,
        request.limit,
        request.offset,
        db,
        allow_source_pid=True,
        patient_id=request.patient_id,
        statuses=request.statuses,
        sort=request.sort,
        direction=request.direction,
        include_total=True,
        current_user=current_user,
    )


@router.get("/api/workspace/dashboard/summary")
def get_workspace_dashboard_summary(
    date: Annotated[str, Query(max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")],
    queue: Literal["doctor", "reviewer"] = "doctor",
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Return dashboard counters and five queue rows without downloading case history."""
    doctor_queue_statuses = (
        "PENDING",
        "ANALYZED",
        "PARTIALLY_REVIEWED",
        "REVIEWED",
    )
    reviewer_queue_statuses = ("SIGNED_PRELIM",)
    queue_statuses = (
        reviewer_queue_statuses if queue == "reviewer" else doctor_queue_statuses
    )
    pending_statuses = doctor_queue_statuses

    def count_statuses(statuses):
        q = db.query(StudyModel).filter(StudyModel.status.in_(statuses))
        if getattr(current_user, "role", None) == "ADMIN" and not getattr(current_user, "facility_id", None):
            pass
        elif getattr(current_user, "facility_id", None):
            q = q.filter(StudyModel.facility_id == current_user.facility_id)
        else:
            return 0
        return q.count()

    today_q = db.query(StudyModel).filter(StudyModel.study_date == date)
    if getattr(current_user, "role", None) == "ADMIN" and not getattr(current_user, "facility_id", None):
        pass
    elif getattr(current_user, "facility_id", None):
        today_q = today_q.filter(StudyModel.facility_id == current_user.facility_id)
    else:
        today_q = today_q.filter(StudyModel.id.is_(None))

    rows = _query_cases(
        None,
        None,
        None,
        5,
        0,
        db,
        allow_source_pid=False,
        statuses=queue_statuses,
        current_user=current_user,
    )
    return {
        "counts": {
            "today": today_q.count(),
            "pending": count_statuses(pending_statuses),
            "waiting": count_statuses(reviewer_queue_statuses),
        },
        "items": rows,
    }


@router.get("/api/workspace/cases")
def get_workspace_cases(
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Alias for /api/cases used by workstation case manager."""
    return list_cases(
        search=search,
        status=status,
        date=date,
        limit=limit,
        offset=offset,
        current_user=current_user,
        db=db,
    )


@router.get("/api/cases/{study_id}")
def get_case_detail(
    study_id: str,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """
    Retrieve full case details for viewing/reopening.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin ca khám.")

    check_facility_access(current_user, study.facility_id)

    db.add(
        AuditLogModel(
            entity_name="study",
            entity_id=study.id,
            action_type="CLINICAL_CASE_READ",
            actor_id=current_user.username,
            details={"patient_id": study.patient_id, "laterality": study.ovary_side},
            timestamp=datetime.now(UTC),
        )
    )
    db.commit()

    latest_batch = (
        db.query(ReviewBatchModel)
        .filter(ReviewBatchModel.study_id == study_id)
        .order_by(ReviewBatchModel.created_at.desc(), ReviewBatchModel.id.desc())
        .first()
    )
    batch_review_ids = set()
    if latest_batch and isinstance(latest_batch.response_json, dict):
        batch_review_ids = {
            item["review_id"]
            for item in latest_batch.response_json.get("reviews", [])
            if isinstance(item, dict) and "review_id" in item
        }

    images_data = []
    for img in study.images:
        image_calibration = get_image_calibration(img)
        last_r = None
        if batch_review_ids and img.reviews:
            last_r = next((review for review in img.reviews if review.id in batch_review_ids), None)
        if not last_r and img.reviews:
            last_r = max(img.reviews, key=lambda review: (review.created_at, review.id))
        pred_data = None
        if img.predictions:
            last_p = next((prediction for prediction in img.predictions if last_r and prediction.id == last_r.prediction_id), None)
            last_p = last_p or max(img.predictions, key=lambda prediction: (prediction.created_at, prediction.id))
            prediction_measurements = last_p.measurements if isinstance(last_p.measurements, dict) else {}
            prov = (
                last_p.provenance_json
                if getattr(last_p, "provenance_json", None) is not None
                else {"model_version": last_p.model_version, "checkpoint_sha256": None, "status": "UNKNOWN"}
            )
            prediction_measurements_trusted = prediction_measurements_match_calibration(
                prediction_measurements, image_calibration, prov
            )
            safe_prediction_measurements = (
                prediction_measurements
                if prediction_measurements_trusted
                else _strip_unverified_physical_measurements(prediction_measurements)
            )
            safe_prediction_provenance = (
                prov
                if prediction_measurements_trusted
                else _strip_unverified_physical_measurements(prov)
            )
            pred_data = {
                "prediction_id": last_p.id,
                "confidence_score": last_p.confidence_score,
                "inference_time_ms": last_p.inference_time_ms,
                "iqa_score": last_p.iqa_score,
                "measurements": safe_prediction_measurements,
                "rle_mask": last_p.raw_mask_rle,
                "provenance": safe_prediction_provenance,
                "model_version": last_p.model_version,
                "uncertainty_map_base64": (
                    "data:image/png;base64," + base64.b64encode(last_p.uncertainty_map_png).decode("ascii")
                    if last_p.uncertainty_map_png
                    else None
                ),
            }

        review_data = None
        if last_r:
            verified_source = _verified_review_calibration_source(last_r)
            fb = _safe_review_feedback(last_r, verified_source)
            review_data = {
                "review_id": last_r.id,
                "prediction_id": last_r.prediction_id,
                "doctor_id": last_r.doctor_id,
                "doctor_action": last_r.doctor_action,
                "time_spent_seconds": last_r.time_spent_seconds,
                "lesion_type": last_r.lesion_type,
                "orads": fb.get("orads"),
                "orads_score": fb.get("orads_score") or fb.get("orads"),
                "morphology_description": fb.get("morphologyDesc") or fb.get("morphology_description"),
                "clinical_notes": last_r.clinical_notes,
                "hitl_feedback": fb,
                "reviewed_at": last_r.created_at.replace(tzinfo=UTC).isoformat(),
                "reviewer_id": last_r.doctor_id,
                "max_diameter_mm": (
                    last_r.max_diameter_mm
                    if verified_source and _finite_physical_value(last_r.max_diameter_mm)
                    else None
                ),
                "ortho_diameter_mm": (
                    last_r.ortho_diameter_mm
                    if verified_source and _finite_physical_value(last_r.ortho_diameter_mm)
                    else None
                ),
                "total_area_cm2": (
                    last_r.total_area_cm2
                    if verified_source and _finite_physical_value(last_r.total_area_cm2)
                    else None
                ),
                "verified_mask_rle": last_r.verified_mask_rle,
                "created_at": last_r.created_at.strftime("%d/%m/%Y %H:%M"),
            }

        images_data.append(
            {
                "image_id": img.id,
                "laterality": img.laterality,
                "filename": img.filename,
                "width": img.width,
                "height": img.height,
                **image_calibration,
                "prediction": pred_data,
                "review": review_data,
            }
        )

    return {
        "study_id": study.id,
        "study_code": study.study_code,
        "visit_no": study.visit_no,
        "patient_id": study.patient.anonymized_pid,
        "patient_age": study.patient.age_bucket,
        "study_date": study.study_date,
        "status": study.status,
        "review_revision": getattr(study, "review_revision", 0),
        "latest_review_request_id": latest_batch.request_id if latest_batch else None,
        "ovary_side": study.ovary_side,
        "contralateral_status": study.contralateral_status,
        "probe_type": study.probe_type,
        "clinical_indication": study.clinical_indication,
        "images": images_data,
        "created_at": study.created_at.strftime("%d/%m/%Y %H:%M"),
    }


@router.get("/api/samples")
def get_sample_cases(db: Session = Depends(get_db)):
    """Retained compatibility endpoint; clinical images must be uploaded."""
    return []


@router.get("/api/samples/{sample_id}/image")
def get_sample_image(sample_id: str):
    raise HTTPException(status_code=404, detail="Image unavailable.")


@router.delete("/api/cases/{study_id}")
def delete_case(
    study_id: str,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a case record and clean up associated image files.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khám để xóa.")

    check_facility_access(current_user, study.facility_id)

    upload_root = Path(UPLOAD_DIR).resolve()
    actor_username = current_user.username
    case_images = list(study.images)
    image_ids = [img.id for img in case_images]
    uploaded_paths = [img.raw_path for img in case_images if img.raw_path]
    pending_deletion_ids = []
    active_learning_transaction = None
    active_learning_cleanup_pending = False
    try:
        pending_deletion_ids = enqueue_upload_deletions(db, uploaded_paths, upload_root)

        # Clean up associated HITL sessions, events, and review batches to avoid orphan records.
        session_query = db.query(HITLSessionModel).filter(HITLSessionModel.study_id == study_id)
        for session in session_query.all():
            event_query = db.query(HITLEventModel).filter(HITLEventModel.session_id == session.id)
            event_query.delete(synchronize_session=False)
            db.delete(session)
        # SessionLocal disables autoflush, so remove HITL sessions that hold
        # review_batch_id foreign keys before issuing the bulk batch delete.
        db.flush()
        db.query(ReviewBatchModel).filter(ReviewBatchModel.study_id == study_id).delete(
            synchronize_session=False
        )

        # UI telemetry is retained only while its case exists. Remove it before
        # deleting the study so buffered interaction events cannot block cleanup
        # or leave event payloads linked to a deleted clinical record.
        db.query(UIEventModel).filter(UIEventModel.case_id == study_id).delete(
            synchronize_session=False
        )

        # Reviews reference predictions through a composite foreign key. Delete
        # those references before the study/image cascade removes predictions.
        if image_ids:
            db.query(ActiveLearningQueueModel).filter(
                ActiveLearningQueueModel.image_id.in_(image_ids)
            ).delete(synchronize_session=False)
            db.query(ReviewModel).filter(ReviewModel.image_id.in_(image_ids)).delete(
                synchronize_session=False
            )
            db.flush()

        db.delete(study)
        db.add(
            AuditLogModel(
                entity_name="study",
                entity_id=study_id,
                action_type="CLINICAL_CASE_DELETE",
                actor_id=actor_username,
                details={"images_associated": len(uploaded_paths)},
                timestamp=datetime.now(UTC),
            )
        )
        active_learning_transaction = prepare_legacy_active_learning_cleanup(image_ids)
        if not active_learning_transaction.complete:
            active_learning_transaction.rollback()
            active_learning_transaction = None
            raise HTTPException(
                status_code=503,
                detail=(
                    "Case deletion was not committed because linked review export cleanup "
                    "could not be confirmed. Retry after storage is available."
                ),
            )
        db.commit()
        active_learning_cleanup_pending = not active_learning_transaction.finalize()
        active_learning_transaction = None
    except Exception:
        rollback_error_type = None
        try:
            db.rollback()
        except Exception as rollback_error:
            rollback_error_type = type(rollback_error).__name__
            logger.critical(
                "Case-delete transaction rollback failed; reconciling durable state.",
                extra={
                    "case_delete_rollback_failure": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        try:
            bind = db.get_bind()
        except Exception:
            bind = None
        try:
            db.close()
        except Exception as close_error:
            logger.critical(
                "Case-delete session close failed during transaction reconciliation.",
                extra={
                    "case_delete_session_close_failure": True,
                    "close_error_type": type(close_error).__name__,
                },
            )

        delete_committed = _verify_case_delete_commit(
            bind, study_id, actor_username, pending_deletion_ids
        )
        if active_learning_transaction is not None:
            if delete_committed is True:
                active_learning_cleanup_pending = not active_learning_transaction.finalize()
            elif not active_learning_transaction.rollback():
                logger.critical(
                    "Could not restore active-learning exports after an uncommitted case deletion.",
                    extra={"legacy_queue_cleanup_rollback_failure": True},
                )
            active_learning_transaction = None
        if delete_committed is True:
            logger.critical(
                "Case-delete commit raised after deletion and audit were persisted; returning verified result.",
                extra={"case_delete_commit_error_after_persist": True},
            )
            active_learning_cleanup = remove_legacy_active_learning_samples(image_ids)
            cleanup_pending = _retry_case_file_deletions(bind, upload_root, pending_deletion_ids)
            return {
                "status": "SUCCESS",
                "message": "Đã xóa ca khám thành công.",
                "file_cleanup": "PENDING" if cleanup_pending else "COMPLETE",
                "active_learning_cleanup": (
                    "PENDING" if active_learning_cleanup_pending or not active_learning_cleanup.complete else "COMPLETE"
                ),
            }
        if delete_committed is None:
            logger.critical(
                "Case-delete commit outcome is uncertain; staged export cleanup was rolled back where possible.",
                extra={
                    "case_delete_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        raise

    try:
        bind = db.get_bind()
    except Exception:
        bind = None
    cleanup_pending = _retry_case_file_deletions(bind, upload_root, pending_deletion_ids)
    return {
        "status": "SUCCESS",
        "message": "Đã xóa ca khám thành công.",
        "file_cleanup": "PENDING" if cleanup_pending else "COMPLETE",
        "active_learning_cleanup": "PENDING" if active_learning_cleanup_pending else "COMPLETE",
    }


@router.get("/api/cases/{study_id}/images/{image_id}")
def get_case_image(
    study_id: str,
    image_id: str,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Retrieve an image file belonging to a specific study case with facility check."""
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin ca khám.")
    check_facility_access(current_user, study.facility_id)

    image_record = (
        db.query(ImageModel)
        .filter(ImageModel.id == image_id, ImageModel.study_id == study_id)
        .first()
    )
    if not image_record or not image_record.raw_path or not os.path.isfile(image_record.raw_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp ảnh.")
    return FileResponse(image_record.raw_path, media_type="image/png")


@router.get("/api/images/{image_id}/source.png")
def get_image_source_png(
    image_id: str,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Return decoded raw source image with facility tenant isolation."""
    image_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail="Source image unavailable.")
    if image_record.study_id:
        study = db.query(StudyModel).filter(StudyModel.id == image_record.study_id).first()
        if study:
            check_facility_access(current_user, study.facility_id)
        else:
            check_facility_access(current_user, None)
    else:
        check_facility_access(current_user, None)

    if not image_record.raw_path or not os.path.isfile(image_record.raw_path):
        raise HTTPException(status_code=404, detail="Source image unavailable.")

    decoded = decode_ultrasound_image(image_record.raw_path)
    if decoded is None:
        raise HTTPException(status_code=422, detail="Source image cannot be decoded.")
    encoded, buffer = cv2.imencode(".png", decoded)
    if not encoded:
        raise HTTPException(status_code=500, detail="Source export failed.")
    return Response(
        content=buffer.tobytes(),
        media_type="image/png",
        headers={
            "X-Image-Coordinate-Space": "decoded-source-image",
            "X-Source-Width": str(decoded.shape[1]),
            "X-Source-Height": str(decoded.shape[0]),
        },
    )
