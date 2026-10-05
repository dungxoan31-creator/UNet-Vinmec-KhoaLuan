"""
RESTful API v1 Endpoints for Ovarian Ultrasound AI System:
- POST /api/v1/segment: Image -> Preprocessing (Letterbox 512x512) -> PyTorch Inference -> Binary Mask & RLE
- POST /api/v1/cdss/evaluate: Clinical & Morphological Features -> CDSS Reasoning Engine -> O-RADS / IOTA Evaluation
- POST /api/v1/cases/confirm: Doctor Review Sign-off (HITL Ground Truth Persistence)
"""

import base64
import os
import uuid

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import model_registry, preprocessor
from backend.app.routers.reviews import submit_doctor_review
from backend.core.image_utils import cv2_imread_unicode
from backend.db.database import ImageModel, get_db
from backend.schemas.schemas import (
    CaseConfirmRequest,
    CDSSEvaluateRequest,
    SegmentAPIResponse,
)

router = APIRouter(prefix="/api/v1", tags=["RESTful API v1 Core Endpoints"])


@router.post("/segment", response_model=SegmentAPIResponse)
async def segment_image_v1(
    file: UploadFile | None = File(None),
    image_id: str | None = None,
    pixel_spacing_mm: float = 0.1,
    db: Session = Depends(get_db),
):
    """
    POST /api/v1/segment:
    Accepts ultrasound image file or existing image_id -> Letterbox 512x512 Preprocessing (Bilinear for image) ->
    PyTorch Attention U-Net inference -> Binary Mask (RLE & Base64 PNG) + Caliper Measurements.
    """
    img_np = None
    target_image_id = image_id or str(uuid.uuid4())

    if file:
        contents = await file.read()
        if len(contents) < 64:
            raise HTTPException(status_code=400, detail="File ảnh rỗng hoặc quá nhỏ.")
        arr = np.frombuffer(contents, dtype=np.uint8)
        img_np = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_np is None:
            raise HTTPException(status_code=400, detail="Không thể giải mã dữ liệu file ảnh.")
    elif image_id:
        img_rec = db.query(ImageModel).filter(ImageModel.id == image_id).first()
        if not img_rec or not os.path.exists(img_rec.raw_path):
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế.")
        img_np = cv2_imread_unicode(img_rec.raw_path)
        pixel_spacing_mm = getattr(img_rec, "pixel_spacing_mm", pixel_spacing_mm) or pixel_spacing_mm
    else:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp file ảnh (file) hoặc image_id.")

    # 1. Quality & Suitability Check
    if not (image_id and image_id.startswith("sample_")):
        validation = preprocessor.validate_ultrasound_suitability(img_np)
        if not validation["is_suitable"]:
            raise HTTPException(
                status_code=422,
                detail=f"Hình ảnh không đạt tiêu chuẩn siêu âm y tế: {validation['error_message']}",
            )

    # 2. Letterbox 512x512 Preprocessing (Aspect Ratio preserved, Bilinear interpolation)
    tensor, padded_gray, transform_params, iqa_report = preprocessor.preprocess_for_inference(img_np)

    # 3. PyTorch Model Inference
    roi_mask = transform_params.get("roi_mask")
    inference_result = model_registry.predict(
        tensor, padded_gray, pixel_spacing_mm=pixel_spacing_mm, roi_mask=roi_mask
    )

    clean_mask = inference_result["binary_mask_np"]  # 512x512 uint8 binary mask (0 or 1)
    mask_255 = (clean_mask * 255).astype(np.uint8)

    # Encode binary mask to Base64 PNG
    _, mask_buf = cv2.imencode(".png", mask_255)
    binary_mask_base64 = f"data:image/png;base64,{base64.b64encode(mask_buf).decode('utf-8')}"

    return {
        "success": True,
        "image_id": target_image_id,
        "rle_mask": inference_result["rle_mask"],
        "binary_mask_base64": binary_mask_base64,
        "confidence_score": inference_result["confidence_score"],
        "measurements": inference_result["measurements"],
        "quality_gate": inference_result.get("quality_gate"),
        "uncertainty": inference_result.get("uncertainty"),
        "provenance": inference_result.get("provenance"),
    }


@router.post("/cdss/evaluate")
def evaluate_cdss_v1(req: CDSSEvaluateRequest):
    """
    POST /api/v1/cdss/evaluate:
    Accepts imaging findings & patient context -> Calls CDSS Reasoning Engine ->
    Returns evidence-supported O-RADS risk category, IOTA Simple Rules verdict, management recommendation, and citations.
    """
    try:
        from knowledge.retrieval.cdss_reasoning_layer import CDSSReasoningEngine
    except ModuleNotFoundError as error:
        raise HTTPException(status_code=503, detail="CDSS reasoning engine chưa được cài đặt.") from error

    try:
        cdss_engine = CDSSReasoningEngine()
        evaluation = cdss_engine.evaluate_case(
            vision_findings=req.vision_findings,
            patient_context=req.patient_context,
        )
        return {
            "success": True,
            "iota_evaluation": evaluation.get("iota_evaluation", {}),
            "orads_stratification": evaluation.get("orads_stratification", {}),
            "uncertainty_evaluation": evaluation.get("uncertainty_evaluation", {}),
            "measurements_summary": evaluation.get("measurements_summary", {}),
            "citations": evaluation.get("citations", []),
            "evidence_status": evaluation.get("evidence_status", "EVIDENCE_SUPPORTED_TIER_1"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi đánh giá CDSS: {e!s}")


@router.post("/cases/confirm")
def confirm_case_v1(req: CaseConfirmRequest, db: Session = Depends(get_db)):
    """Use the same validation and audit flow as /api/review."""
    review = submit_doctor_review(req, db)
    return {
        "success": True,
        "review_id": review["review_id"],
        "image_id": req.image_id,
        "study_id": req.study_id,
        "status": "REVIEWED",
        "message": review["message"],
        "is_ground_truth": review["is_ground_truth"],
    }
