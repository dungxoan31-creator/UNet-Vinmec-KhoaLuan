"""
Clinical Cases CRUD and Sample Cases endpoints.
"""

import base64
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.config import UPLOAD_DIR
from backend.app.security import require_admin, require_clinical
from backend.core.patient_identity import patient_id_digest
from backend.db.database import (
    AuditLogModel,
    HITLEventModel,
    HITLSessionModel,
    ImageModel,
    PatientModel,
    PendingFileDeletionModel,
    ReviewBatchModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import (
    CaseLeaseReleaseRequest,
    CaseLeaseRequest,
    CaseSearchRequest,
    CreateCaseRequest,
)
from backend.services.case_lease_service import acquire_case_lease, release_case_lease
from backend.services.file_deletion_service import (
    enqueue_upload_deletions,
    retry_pending_file_deletions,
)
from backend.services.image_service import get_image_calibration
from backend.services.patient_identity import get_or_create_patient

router = APIRouter(tags=["Clinical Cases"])
logger = logging.getLogger(__name__)


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


@router.post("/api/cases", dependencies=[Depends(require_clinical)])
def create_new_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    """
    Create a new clinical study case.
    """
    clean_pid = req.patient_id.strip() if req.patient_id else ""
    if not clean_pid:
        raise HTTPException(status_code=422, detail="Mã định danh bệnh nhân (PID) không được để trống.")

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
            status="PENDING",
            probe_type=req.probe_type or None,
            ovary_side=req.active_ovary_side,
            contralateral_status=req.contralateral_status,
            clinical_indication=req.clinical_notes or None,
        )
        db.add(study)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "study_id": study.id,
        "study_code": study.study_code,
        "patient_id": patient.anonymized_pid,
        "study_date": study.study_date,
        "status": study.status,
        "ovary_side": study.ovary_side,
        "contralateral_status": study.contralateral_status,
        "message": "Khởi tạo ca khám mới thành công.",
    }


@router.get("/api/cases", dependencies=[Depends(require_clinical)])
def list_cases(
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    db: Session = Depends(get_db),
):
    return _query_cases(search, status, date, limit, offset, db, allow_source_pid=False)


@router.post("/api/cases/search", dependencies=[Depends(require_clinical)])
def search_cases(request: CaseSearchRequest, db: Session = Depends(get_db)):
    """Search cases without placing a potentially identifying PID in the URL."""
    return _query_cases(
        request.search,
        request.status,
        request.date,
        request.limit,
        request.offset,
        db,
        allow_source_pid=True,
    )


def _query_cases(search, status, date, limit, offset, db, allow_source_pid):
    """
    List all cases with search and filtering for Dashboard & History.
    """
    query = db.query(StudyModel).join(PatientModel).options(
        joinedload(StudyModel.patient),
        selectinload(StudyModel.images).selectinload(ImageModel.predictions),
        selectinload(StudyModel.images).selectinload(ImageModel.reviews),
    )

    if status and status.upper() != "ALL":
        query = query.filter(StudyModel.status == status.upper())

    if date:
        query = query.filter(StudyModel.study_date.startswith(date))

    if search:
        search_value = search.strip()
        search_fmt = f"%{search_value}%"
        search_conditions = [
            PatientModel.anonymized_pid.ilike(search_fmt),
            StudyModel.study_code.ilike(search_fmt),
            StudyModel.clinical_indication.ilike(search_fmt),
        ]
        if allow_source_pid and 0 < len(search_value) <= 64:
            search_conditions.append(PatientModel.source_pid_hmac == patient_id_digest(search_value))
        query = query.filter(or_(*search_conditions))

    query = query.order_by(desc(StudyModel.created_at), desc(StudyModel.id))
    if offset:
        query = query.offset(offset)
    query = query.limit(limit)

    studies = query.all()

    cases_list = []
    for s in studies:
        first_img = s.images[0] if s.images else None
        last_review = first_img.reviews[-1] if (first_img and first_img.reviews) else None
        pred = first_img.predictions[-1] if (first_img and first_img.predictions) else None

        cases_list.append(
            {
                "id": s.id,
                "study_id": s.id,
                "study_code": s.study_code or s.id[:8],
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
                "max_diameter_mm": last_review.max_diameter_mm
                if last_review
                else (
                    pred.measurements.get("max_diameter_mm", 0.0)
                    if (pred and isinstance(pred.measurements, dict))
                    else 0.0
                ),
                "doctor_action": last_review.doctor_action if last_review else None,
                "created_at": s.created_at.strftime("%d/%m/%Y %H:%M"),
            }
        )

    return cases_list


@router.get("/api/workspace/cases", dependencies=[Depends(require_clinical)])
def get_workspace_cases(
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    db: Session = Depends(get_db),
):
    """Alias for /api/cases used by workstation case manager."""
    return list_cases(search=search, status=status, date=date, limit=limit, offset=offset, db=db)


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
        last_r = None
        if batch_review_ids and img.reviews:
            last_r = next((review for review in img.reviews if review.id in batch_review_ids), None)
        if not last_r and img.reviews:
            last_r = max(img.reviews, key=lambda review: (review.created_at, review.id))
        pred_data = None
        if img.predictions:
            last_p = next((prediction for prediction in img.predictions if last_r and prediction.id == last_r.prediction_id), None)
            last_p = last_p or max(img.predictions, key=lambda prediction: (prediction.created_at, prediction.id))
            prov = (
                last_p.provenance_json
                if getattr(last_p, "provenance_json", None) is not None
                else {"model_version": last_p.model_version, "checkpoint_sha256": None, "status": "UNKNOWN"}
            )
            pred_data = {
                "prediction_id": last_p.id,
                "confidence_score": last_p.confidence_score,
                "inference_time_ms": last_p.inference_time_ms,
                "iqa_score": last_p.iqa_score,
                "measurements": last_p.measurements,
                "rle_mask": last_p.raw_mask_rle,
                "provenance": prov,
                "model_version": last_p.model_version,
                "uncertainty_map_base64": (
                    "data:image/png;base64," + base64.b64encode(last_p.uncertainty_map_png).decode("ascii")
                    if last_p.uncertainty_map_png
                    else None
                ),
            }

        review_data = None
        if last_r:
            fb = last_r.hitl_feedback if isinstance(last_r.hitl_feedback, dict) else {}
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
                "hitl_feedback": last_r.hitl_feedback,
                "reviewed_at": last_r.created_at.replace(tzinfo=UTC).isoformat(),
                "reviewer_id": last_r.doctor_id,
                "max_diameter_mm": last_r.max_diameter_mm,
                "ortho_diameter_mm": last_r.ortho_diameter_mm,
                "total_area_cm2": last_r.total_area_cm2,
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
                **get_image_calibration(img),
                "prediction": pred_data,
                "review": review_data,
            }
        )

    return {
        "study_id": study.id,
        "study_code": study.study_code,
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

    upload_root = Path(UPLOAD_DIR).resolve()
    case_images = list(study.images)
    image_ids = [img.id for img in case_images]
    uploaded_paths = [img.raw_path for img in case_images if img.raw_path]
    pending_deletion_ids = []
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

        # Reviews reference predictions through a composite foreign key. Delete
        # those references before the study/image cascade removes predictions.
        if image_ids:
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
                actor_id=current_user.username,
                details={"images_associated": len(uploaded_paths)},
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
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
            bind, study_id, current_user.username, pending_deletion_ids
        )
        if delete_committed is True:
            logger.critical(
                "Case-delete commit raised after deletion and audit were persisted; returning verified result.",
                extra={"case_delete_commit_error_after_persist": True},
            )
            cleanup_pending = _retry_case_file_deletions(bind, upload_root, pending_deletion_ids)
            return {
                "status": "SUCCESS",
                "message": "Đã xóa ca khám thành công.",
                "file_cleanup": "PENDING" if cleanup_pending else "COMPLETE",
            }
        if delete_committed is None:
            logger.critical(
                "Case-delete commit outcome is uncertain; files were not deleted.",
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
    }
