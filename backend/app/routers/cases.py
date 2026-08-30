"""
Clinical Cases CRUD and Sample Cases endpoints.
"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from backend.db.database import PatientModel, StudyModel, get_db
from backend.schemas.schemas import CreateCaseRequest

router = APIRouter(tags=["Clinical Cases"])


@router.post("/api/cases")
def create_new_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    """
    Create a new clinical study case.
    """
    patient = db.query(PatientModel).filter(PatientModel.anonymized_pid == req.patient_id.strip()).first()
    if not patient:
        patient = PatientModel(
            id=str(uuid.uuid4()), anonymized_pid=req.patient_id.strip(), age_bucket=req.patient_age or "30-39"
        )
        db.add(patient)
        db.commit()

    study_id = str(uuid.uuid4())
    study_code = (
        req.study_code.strip()
        if req.study_code
        else f"STD-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    )
    study_date = req.study_date or datetime.now().strftime("%Y-%m-%d")

    study = StudyModel(
        id=study_id,
        patient_id=patient.id,
        study_code=study_code,
        study_date=study_date,
        status="PENDING",
        probe_type=req.probe_type or "TRANSVAGINAL_2D",
        clinical_indication=req.clinical_notes or "Khám phụ khoa định kỳ",
    )
    db.add(study)
    db.commit()

    return {
        "study_id": study.id,
        "study_code": study.study_code,
        "patient_id": patient.anonymized_pid,
        "study_date": study.study_date,
        "status": study.status,
        "message": "Khởi tạo ca khám mới thành công.",
    }


@router.get("/api/cases")
def list_cases(
    search: str | None = None, status: str | None = None, date: str | None = None, db: Session = Depends(get_db)
):
    """
    List all cases with search and filtering for Dashboard & History.
    """
    query = db.query(StudyModel).join(PatientModel)

    if status and status.upper() != "ALL":
        query = query.filter(StudyModel.status == status.upper())

    if date:
        query = query.filter(StudyModel.study_date == date)

    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                PatientModel.anonymized_pid.ilike(search_fmt),
                StudyModel.study_code.ilike(search_fmt),
                StudyModel.clinical_indication.ilike(search_fmt),
            )
        )

    studies = query.order_by(desc(StudyModel.created_at)).limit(50).all()

    cases_list = []
    for s in studies:
        first_img = s.images[0] if s.images else None
        last_review = first_img.reviews[-1] if (first_img and first_img.reviews) else None
        pred = first_img.predictions[-1] if (first_img and first_img.predictions) else None

        cases_list.append(
            {
                "id": s.id,
                "study_code": s.study_code or s.id[:8],
                "patient_id": s.patient.anonymized_pid,
                "patient_age": s.patient.age_bucket,
                "study_date": s.study_date,
                "status": s.status,
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


@router.get("/api/cases/{study_id}")
def get_case_detail(study_id: str, db: Session = Depends(get_db)):
    """
    Retrieve full case details for viewing/reopening.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin ca khám.")

    images_data = []
    for img in study.images:
        pred_data = None
        if img.predictions:
            last_p = img.predictions[-1]
            pred_data = {
                "confidence_score": last_p.confidence_score,
                "inference_time_ms": last_p.inference_time_ms,
                "iqa_score": last_p.iqa_score,
                "measurements": last_p.measurements,
                "rle_mask": last_p.raw_mask_rle,
            }

        review_data = None
        if img.reviews:
            last_r = img.reviews[-1]
            review_data = {
                "doctor_id": last_r.doctor_id,
                "doctor_action": last_r.doctor_action,
                "lesion_type": last_r.lesion_type,
                "clinical_notes": last_r.clinical_notes,
                "max_diameter_mm": last_r.max_diameter_mm,
                "ortho_diameter_mm": last_r.ortho_diameter_mm,
                "total_area_cm2": last_r.total_area_cm2,
                "verified_mask_rle": last_r.verified_mask_rle,
                "created_at": last_r.created_at.strftime("%d/%m/%Y %H:%M"),
            }

        images_data.append(
            {
                "image_id": img.id,
                "filename": img.filename,
                "width": img.width,
                "height": img.height,
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
        "probe_type": study.probe_type,
        "clinical_indication": study.clinical_indication,
        "images": images_data,
        "created_at": study.created_at.strftime("%d/%m/%Y %H:%M"),
    }


@router.get("/api/samples")
def get_sample_cases(db: Session = Depends(get_db)):
    """
    Returns curated clinical sample cases across major pathology categories for demo and testing.
    """
    return [
        {
            "id": "SAMPLE-01",
            "patient_id": "BN-VINMEC-8899",
            "study_code": "STD-SAMPLE-SEROUS",
            "study_date": "2026-08-25",
            "patient_age": "28 (Tuổi sinh sản)",
            "pathology": "Serous Cystadenoma (U nang thanh dịch)",
            "clinical_notes": "Siêu âm tầm soát u buồng trứng phải. Vùng echo trống, vỏ mỏng đều.",
            "status": "APPROVED",
            "max_diameter_mm": 42.5,
            "ortho_diameter_mm": 35.2,
            "image_filename": "sample_serous.png",
        },
        {
            "id": "SAMPLE-02",
            "patient_id": "BN-VINMEC-4421",
            "study_code": "STD-SAMPLE-DERMOID",
            "study_date": "2026-08-26",
            "patient_age": "34 (Tuổi sinh sản)",
            "pathology": "Dermoid Cyst (U quái bì buồng trứng)",
            "clinical_notes": "Phát hiện khối hỗn hợp âm, nút Rokitansky tăng âm kèm bóng lưng.",
            "status": "APPROVED",
            "max_diameter_mm": 51.0,
            "ortho_diameter_mm": 38.6,
            "image_filename": "sample_dermoid.png",
        },
        {
            "id": "SAMPLE-03",
            "patient_id": "BN-VINMEC-7712",
            "study_code": "STD-SAMPLE-ENDOMETRIOMA",
            "study_date": "2026-08-27",
            "patient_age": "31 (Tuổi sinh sản)",
            "pathology": "Endometrioma (U lạc nội mạc / Nang sô cô la)",
            "clinical_notes": "Đau bụng kinh mạn tính. Nang phản âm kém dạng kính mờ (Ground glass).",
            "status": "PENDING",
            "max_diameter_mm": 38.2,
            "ortho_diameter_mm": 30.1,
            "image_filename": "sample_endometrioma.png",
        },
        {
            "id": "SAMPLE-04",
            "patient_id": "BN-VINMEC-1205",
            "study_code": "STD-SAMPLE-NORMAL",
            "study_date": "2026-08-28",
            "patient_age": "26 (Tuổi sinh sản)",
            "pathology": "Normal / Follicular Cyst (Nang noãn buồng trứng)",
            "clinical_notes": "Khám sức khỏe tiền hôn nhân. Buồng trứng hai bên kích thước bình thường.",
            "status": "APPROVED",
            "max_diameter_mm": 18.0,
            "ortho_diameter_mm": 14.5,
            "image_filename": "sample_normal.png",
        },
    ]


@router.delete("/api/cases/{study_id}")
def delete_case(study_id: str, db: Session = Depends(get_db)):
    """
    Delete a case record and clean up associated image files.
    """
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khám để xóa.")

    # Clean up physical files from upload directory if not sample assets
    for img in study.images:
        if img.raw_path and os.path.exists(img.raw_path) and not os.path.basename(img.raw_path).startswith("sample_"):
            try:
                os.remove(img.raw_path)
            except Exception:
                pass

    db.delete(study)
    db.commit()
    return {"status": "SUCCESS", "message": "Đã xóa ca khám thành công."}

