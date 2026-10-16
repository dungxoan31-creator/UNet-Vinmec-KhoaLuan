"""
Service for atomic batch review persistence, revision validation, and idempotency tracking.
"""

from datetime import UTC, datetime
import hashlib
import json
import os
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.config import model_registry, preprocessor
from backend.app.routers.inference import decode_ultrasound_image, get_image_calibration
from backend.db.database import (
    AuditLogModel,
    HITLEventModel,
    HITLSessionModel,
    ImageModel,
    PredictionModel,
    ReviewBatchModel,
    ReviewModel,
    StudyModel,
    UserModel,
)
from backend.schemas.schemas import BatchReviewRequest
from backend.services.review_validation import validate_review_mask
from backend.services.source_measurements import measure_source_mask


def compute_request_hash(request: BatchReviewRequest) -> str:
    reviews_data = []
    for r in request.reviews:
        reviews_data.append({
            "image_id": r.image_id,
            "prediction_id": r.prediction_id,
            "doctor_action": r.doctor_action,
            "verified_mask_rle": r.verified_mask_rle,
            "clinical_notes": r.clinical_notes,
            "lesion_type": r.lesion_type,
            "time_spent_seconds": r.time_spent_seconds,
            "hitl_feedback": r.hitl_feedback.model_dump() if r.hitl_feedback else None,
        })
    reviews_data.sort(key=lambda x: x["image_id"])
    canonical = {
        "study_id": request.study_id,
        "expected_revision": request.expected_revision,
        "reviews": reviews_data,
    }
    raw = json.dumps(canonical, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persist_review_batch(
    db: Session,
    request: BatchReviewRequest,
    user: UserModel,
    allow_partial: bool = False,
) -> dict[str, Any]:
    if user.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Chỉ bác sĩ (DOCTOR) mới có quyền lưu rà soát.")

    current_hash = compute_request_hash(request)
    req_id_str = str(request.request_id)

    # 1. Idempotency Check
    existing_batch = db.query(ReviewBatchModel).filter(ReviewBatchModel.request_id == req_id_str).first()
    if existing_batch:
        if existing_batch.actor_id != user.username:
            raise HTTPException(status_code=409, detail="Request ID đã được sử dụng bởi người dùng khác.")
        if existing_batch.request_hash != current_hash:
            raise HTTPException(status_code=409, detail="Request ID đã tồn tại với nội dung khác.")
        return existing_batch.response_json

    # 2. Study Existence Check
    study = db.query(StudyModel).filter(StudyModel.id == request.study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khảo sát.")

    # 3. Optimistic Revision Guard
    if study.review_revision != request.expected_revision:
        raise HTTPException(
            status_code=409,
            detail=f"Xung đột phiên bản rà soát: máy chủ đang ở bản {study.review_revision}, yêu cầu gửi {request.expected_revision}.",
        )

    # 3b. Optional HITL Session Validation
    hitl_sess = None
    if request.hitl_session_id:
        hitl_sess = db.query(HITLSessionModel).filter(HITLSessionModel.id == request.hitl_session_id).first()
        if not hitl_sess:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên HITL.")
        if hitl_sess.study_id != request.study_id:
            raise HTTPException(status_code=422, detail="Phiên HITL không thuộc ca khảo sát.")
        if hitl_sess.actor_id != user.username and user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Chỉ người tạo phiên HITL mới có quyền liên kết rà soát.")

    # 4. Review Set & Image Membership Validation
    if not request.reviews:
        raise HTTPException(status_code=422, detail="Danh sách rà soát rỗng.")

    image_ids = [r.image_id for r in request.reviews]
    if len(image_ids) != len(set(image_ids)):
        raise HTTPException(status_code=422, detail="Trùng lặp ảnh trong yêu cầu rà soát.")

    study_images = {img.id: img for img in study.images}
    for r in request.reviews:
        if r.image_id not in study_images:
            raise HTTPException(status_code=422, detail="Ảnh không thuộc ca khảo sát.")

    # 5. Laterality Guard
    if study.ovary_side == "UNKNOWN" and len(request.reviews) > 1:
        raise HTTPException(status_code=422, detail="Không thể xác nhận hai bên cho ca có vị trí buồng trứng không xác định.")

    if study.ovary_side == "BOTH" and not allow_partial:
        reviewed_lateralities = {study_images[r.image_id].laterality for r in request.reviews}
        if not {"L", "R"}.issubset(reviewed_lateralities):
            raise HTTPException(status_code=422, detail="Ca hai bên yêu cầu rà soát đầy đủ cả hai ảnh (trái và phải).")

    # 6. Predictions & Mask Validation
    engine_inst = model_registry.get_primary_adapter().engine
    validated_items = []
    for r in request.reviews:
        pred = db.query(PredictionModel).filter(PredictionModel.id == r.prediction_id).first()
        if not pred:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy bản dự đoán {r.prediction_id}.")
        if pred.image_id != r.image_id:
            raise HTTPException(status_code=422, detail="Dự đoán không thuộc ảnh tương ứng.")

        verified_mask = engine_inst.rle_to_mask(r.verified_mask_rle)
        predicted_mask = engine_inst.rle_to_mask(pred.raw_mask_rle)
        validate_review_mask(r.doctor_action, verified_mask, predicted_mask)

        img_rec = study_images[r.image_id]
        validated_items.append((r, img_rec, pred))

    # 7. Atomic Execution
    try:
        now_utc = datetime.now(UTC)
        review_summaries = []

        for r, img_rec, pred in validated_items:
            decoded = decode_ultrasound_image(img_rec.raw_path) if (img_rec.raw_path and os.path.isfile(img_rec.raw_path)) else None
            if decoded is not None:
                meas = measure_source_mask(
                    decoded, r.verified_mask_rle, preprocessor, engine_inst, get_image_calibration(img_rec)
                )
            else:
                meas = {"max_diameter_mm": None, "ortho_diameter_mm": None, "total_area_cm2": None}

            feedback = r.hitl_feedback.model_dump() if r.hitl_feedback is not None else None
            review_id = str(uuid.uuid4())

            review_record = ReviewModel(
                id=review_id,
                image_id=r.image_id,
                prediction_id=r.prediction_id,
                doctor_id=user.username,
                doctor_action=r.doctor_action,
                verified_mask_rle=r.verified_mask_rle,
                max_diameter_mm=meas["max_diameter_mm"],
                ortho_diameter_mm=meas["ortho_diameter_mm"],
                total_area_cm2=meas["total_area_cm2"],
                lesion_type=r.lesion_type,
                clinical_notes=r.clinical_notes,
                time_spent_seconds=r.time_spent_seconds,
                hitl_feedback=feedback,
                is_official_ground_truth=False,
                created_at=now_utc,
            )
            db.add(review_record)

            audit = AuditLogModel(
                entity_name="doctor_reviews",
                entity_id=review_id,
                action_type=f"DOCTOR_{r.doctor_action}",
                actor_id=user.username,
                details={
                    "image_id": r.image_id,
                    "time_spent_s": r.time_spent_seconds,
                    "lesion_type": r.lesion_type,
                    "dmax_mm": meas["max_diameter_mm"],
                    "hitl_feedback": feedback,
                    "study_id": study.id,
                    "prediction_id": r.prediction_id,
                    "batch_request_id": req_id_str,
                },
                timestamp=now_utc,
            )
            db.add(audit)

            review_summaries.append({
                "review_id": review_id,
                "image_id": r.image_id,
                "prediction_id": r.prediction_id,
                "doctor_action": r.doctor_action,
                "reviewed_at": now_utc.isoformat(),
            })

        new_revision = study.review_revision + 1
        study.review_revision = new_revision

        if study.ovary_side == "BOTH":
            all_reviewed_lateralities = {
                img.laterality for img in study.images
                if img.reviews or img.id in {r.image_id for r in request.reviews}
            }
            study.status = "REVIEWED" if {"L", "R"}.issubset(all_reviewed_lateralities) else "PARTIALLY_REVIEWED"
        else:
            study.status = "REVIEWED"

        response_data = {
            "status": "SUCCESS",
            "study_id": study.id,
            "review_revision": new_revision,
            "reviews": review_summaries,
            "message": "Đã lưu rà soát nghiên cứu thành công.",
        }

        batch_record = ReviewBatchModel(
            id=str(uuid.uuid4()),
            request_id=req_id_str,
            actor_id=user.username,
            study_id=study.id,
            request_hash=current_hash,
            response_json=response_data,
            created_at=now_utc,
        )
        db.add(batch_record)

        if hitl_sess:
            hitl_sess.review_batch_id = batch_record.id
            if hitl_sess.status != "COMPLETED":
                hitl_sess.status = "INCOMPLETE"

            session_tasks = (
                db.query(HITLEventModel.task_id, HITLEventModel.image_id, func.max(HITLEventModel.seq))
                .filter(HITLEventModel.session_id == hitl_sess.id)
                .group_by(HITLEventModel.task_id, HITLEventModel.image_id)
                .all()
            )
            for t_id, img_id, _ in session_tasks:
                ev = HITLEventModel(
                    id=str(uuid.uuid4()),
                    event_id=str(uuid.uuid4()),
                    session_id=hitl_sess.id,
                    task_id=t_id,
                    image_id=img_id,
                    seq=0,
                    event_type="CONFIRM_SUCCEEDED",
                    client_utc=now_utc.isoformat(),
                    elapsed_ms=0.0,
                    session_elapsed_ms=0.0,
                    payload_hash=hashlib.sha256(
                        json.dumps({
                            "batch_request_id": req_id_str,
                            "review_revision": new_revision,
                        }, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    payload={
                        "batch_request_id": req_id_str,
                        "review_revision": new_revision,
                    },
                    actor_id=user.username,
                    received_at=now_utc,
                )
                db.add(ev)

        db.commit()
        return response_data
    except Exception:
        db.rollback()
        raise
