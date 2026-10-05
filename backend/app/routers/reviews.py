"""
Doctor Review, Ground Truth Sign-Off, and Medical PDF Report Generation endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.config import model_registry
from backend.db.database import AuditLogModel, ImageModel, PredictionModel, ReviewModel, get_db
from backend.schemas.schemas import DoctorReviewRequest, DoctorReviewResponse
from backend.services.review_validation import validate_review_mask

router = APIRouter(tags=["Doctor Review & Reports"])


@router.post("/api/review", response_model=DoctorReviewResponse)
def submit_doctor_review(review_req: DoctorReviewRequest, db: Session = Depends(get_db)):
    """Store a reviewed mask and audit record without claiming clinical sign-off."""
    review_id = str(uuid.uuid4())
    engine_inst = model_registry.get_primary_adapter().engine

    img_rec = db.query(ImageModel).filter(ImageModel.id == review_req.image_id).first()
    if not img_rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh y tế tương ứng.")
    if img_rec.laterality and review_req.study_id != img_rec.study_id:
        raise HTTPException(status_code=422, detail="Ca khảo sát không khớp với ảnh đang rà soát.")
    prediction = db.query(PredictionModel).filter(PredictionModel.id == review_req.prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản dự đoán cần rà soát.")
    if prediction.image_id != img_rec.id:
        raise HTTPException(status_code=422, detail="Dự đoán không thuộc ảnh đang rà soát.")

    pixel_spacing = img_rec.pixel_spacing_mm

    # Decode mask to get exact doctor-verified measurements
    verified_mask = engine_inst.rle_to_mask(review_req.verified_mask_rle)
    predicted_mask = engine_inst.rle_to_mask(prediction.raw_mask_rle)
    validate_review_mask(review_req.doctor_action, verified_mask, predicted_mask)
    meas = engine_inst.extract_calipers_and_measurements(verified_mask, pixel_spacing_mm=pixel_spacing)
    if pixel_spacing is None:
        for key in ("max_diameter_mm", "ortho_diameter_mm", "total_area_cm2"):
            meas[key] = None

    review_record = ReviewModel(
        id=review_id,
        image_id=review_req.image_id,
        prediction_id=review_req.prediction_id,
        doctor_id=review_req.doctor_id,
        doctor_action=review_req.doctor_action,
        verified_mask_rle=review_req.verified_mask_rle,
        max_diameter_mm=meas["max_diameter_mm"],
        ortho_diameter_mm=meas["ortho_diameter_mm"],
        total_area_cm2=meas["total_area_cm2"],
        lesion_type=review_req.lesion_type,
        clinical_notes=review_req.clinical_notes,
        time_spent_seconds=review_req.time_spent_seconds,
        is_official_ground_truth=False,
    )
    db.add(review_record)

    # A bilateral study is complete only when each labelled image has a review.
    if img_rec.study:
        if img_rec.study.ovary_side == "BOTH":
            reviewed_sides = {
                image.laterality for image in img_rec.study.images
                if image.reviews or image.id == img_rec.id
            }
            img_rec.study.status = "REVIEWED" if reviewed_sides == {"R", "L"} else "PARTIALLY_REVIEWED"
        else:
            img_rec.study.status = "REVIEWED"

    # Audit log
    audit = AuditLogModel(
        entity_name="doctor_reviews",
        entity_id=review_id,
        action_type=f"DOCTOR_{review_req.doctor_action}",
        actor_id=review_req.doctor_id,
        details={
            "image_id": review_req.image_id,
            "time_spent_s": review_req.time_spent_seconds,
            "lesion_type": review_req.lesion_type,
            "dmax_mm": meas["max_diameter_mm"],
        },
    )
    db.add(audit)
    db.commit()

    return {
        "review_id": review_id,
        "image_id": review_req.image_id,
        "status": "SUCCESS",
        "message": "Đã lưu mask rà soát và nhật ký thao tác.",
        "is_ground_truth": False,
    }


@router.post("/api/generate-report")
def generate_report_pdf(report_payload: dict):
    """Clinical PDF requires a verified reviewer workflow."""
    raise HTTPException(status_code=501, detail="Chưa hỗ trợ xuất báo cáo lâm sàng khi chưa có xác thực chuyên môn.")
