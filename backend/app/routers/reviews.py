"""
Doctor Review, Ground Truth Sign-Off, and Medical PDF Report Generation endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.config import model_registry, report_generator
from backend.db.database import AuditLogModel, ImageModel, ReviewModel, get_db
from backend.schemas.schemas import DoctorReviewRequest, DoctorReviewResponse
router = APIRouter(tags=["Doctor Review & Reports"])


@router.post("/api/review", response_model=DoctorReviewResponse)
def submit_doctor_review(review_req: DoctorReviewRequest, db: Session = Depends(get_db)):
    """
    Submits Doctor Review, stores final verified Ground Truth mask and audit logs.
    """
    review_id = str(uuid.uuid4())
    engine_inst = model_registry.get_primary_adapter().engine

    img_rec = db.query(ImageModel).filter(ImageModel.id == review_req.image_id).first()
    if not img_rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh y tế tương ứng.")

    pixel_spacing = getattr(img_rec, "pixel_spacing_mm", 0.1) or 0.1

    # Decode mask to get exact doctor-verified measurements
    verified_mask = engine_inst.rle_to_mask(review_req.verified_mask_rle)
    meas = engine_inst.extract_calipers_and_measurements(verified_mask, pixel_spacing_mm=pixel_spacing)

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
        is_official_ground_truth=True,
    )
    db.add(review_record)

    # Update Study status to REVIEWED
    if img_rec.study:
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
        "message": "Kết quả đã được Bác sĩ ký duyệt và lưu trữ Ground Truth thành công.",
        "is_ground_truth": True,
    }


@router.post("/api/generate-report")
def generate_report_pdf(report_payload: dict):
    """
    Generates and downloads a standardized PDF Medical Ultrasound Report.
    """
    try:
        pdf_bytes = report_generator.generate_pdf_report(report_payload)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Phieu_Ket_Qua_Sieu_Am_Buong_Trung.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo báo cáo PDF: {e!s}")
