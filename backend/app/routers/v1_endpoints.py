"""
Research API endpoints for the ovarian ultrasound prototype:
- POST /api/v1/segment: Image -> Preprocessing (Letterbox 512x512) -> Manifest-selected model -> Binary Mask & RLE
- POST /api/v1/cdss/evaluate: Explicit clinician-entered descriptors -> RUO rule probe
- POST /api/v1/cases/confirm: Persist clinician review through the HITL workflow
"""

import base64
import hashlib
import os
import uuid
from io import BytesIO

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.config import (
    SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256,
    SYNTHETIC_DEMO_MODE,
    model_registry,
    preprocessor,
)
from backend.app.security import get_current_user, require_clinical
from backend.core.image_utils import (
    MAX_DECODED_IMAGE_PIXELS,
    MAX_UPLOAD_BYTES,
    is_within_decoded_image_limit,
)
from backend.db.database import ImageModel, PredictionModel, StudyModel, UserModel, get_db
from backend.schemas.schemas import (
    ApplyClinicalTemplateRequest,
    CaseConfirmRequest,
    CDSSEvaluateRequest,
    CDSSMultiLesionEvaluateRequest,
    SegmentAPIResponse,
    SegmentationCandidateRequest,
    SegmentationCandidateResponse,
)
from backend.services.case_lease_service import require_active_case_lease
from backend.services.image_service import (
    decode_ultrasound_image,
    get_image_calibration,
    validate_pixel_spacing,
)
from backend.services.facility_service import check_facility_access
from backend.services.inference_engine import InferenceEngine
from backend.services.review_service import persist_single_review
from backend.services.segmentation_candidates import build_mask_candidate

router = APIRouter(
    prefix="/api/v1",
    tags=["RESTful API v1 Core Endpoints"],
    dependencies=[Depends(require_clinical)],
)


@router.post("/segment/candidate", response_model=SegmentationCandidateResponse)
def create_segmentation_candidate_v1(
    req: SegmentationCandidateRequest,
    current_user: UserModel = Depends(require_clinical),
    db: Session = Depends(get_db),
):
    """Return an explicit research candidate without changing clinical state."""
    study = db.query(StudyModel).filter(StudyModel.id == req.study_id).first()
    image = (
        db.query(ImageModel)
        .filter(ImageModel.id == req.image_id, ImageModel.study_id == req.study_id)
        .first()
    )
    prediction = (
        db.query(PredictionModel)
        .filter(
            PredictionModel.id == req.prediction_id,
            PredictionModel.image_id == req.image_id,
        )
        .first()
    )
    if study is None or image is None or prediction is None:
        raise HTTPException(status_code=404, detail="Candidate source not found.")
    check_facility_access(current_user, study.facility_id)

    try:
        baseline_mask = InferenceEngine.rle_to_mask(prediction.raw_mask_rle)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Stored prediction mask is invalid.") from exc
    if baseline_mask.shape != (512, 512):
        raise HTTPException(status_code=422, detail="Stored prediction mask must be 512x512.")

    try:
        candidate_mask = build_mask_candidate(
            baseline_mask,
            min_component_area=req.min_component_area,
            closing_kernel_size=req.closing_kernel_size,
            fill_holes=req.fill_holes,
            smoothing_kernel_size=req.smoothing_kernel_size,
        )
    except ValueError as exc:
        # Keep request validation and helper validation in parity; malformed source
        # masks/parameters must never be silently transformed.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    source_provenance = prediction.provenance_json
    checkpoint_sha256 = None
    if isinstance(source_provenance, dict):
        candidate_digest = source_provenance.get("checkpoint_sha256")
        if (
            isinstance(candidate_digest, str)
            and len(candidate_digest) == 64
            and all(char in "0123456789abcdefABCDEF" for char in candidate_digest)
        ):
            checkpoint_sha256 = candidate_digest.lower()

    return {
        "success": True,
        "baseline_mask_rle": prediction.raw_mask_rle,
        "candidate_mask_rle": InferenceEngine.mask_to_rle(candidate_mask),
        "candidate_parameters": {
            "min_component_area": req.min_component_area,
            "closing_kernel_size": req.closing_kernel_size,
            "fill_holes": req.fill_holes,
            "smoothing_kernel_size": req.smoothing_kernel_size,
        },
        "provenance": {
            "prediction_id": prediction.id,
            "model_version": prediction.model_version,
            "checkpoint_sha256": checkpoint_sha256,
            "algorithm": "explicit_morphology_candidate",
            "algorithm_version": "1.0.0",
        },
    }


@router.post("/segment", response_model=SegmentAPIResponse)
async def segment_image_v1(
    file: UploadFile | None = File(None),
    image_id: str | None = None,
    pixel_spacing_mm: float | None = None,
    lease_token: str | None = Header(None, alias="X-Case-Lease-Token"),
    page_instance_id: str | None = Header(None, alias="X-Case-Page-Instance-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """
    POST /api/v1/segment:
    Accepts ultrasound image file or existing image_id -> Letterbox 512x512 Preprocessing (Bilinear for image) ->
    Manifest-selected PyTorch model inference -> Binary Mask (RLE & Base64 PNG) + Caliper Measurements.
    """
    if file is None and (image_id is None or not image_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Cung cấp file hoặc image_id hợp lệ.",
        )
    if file is not None and image_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Cung cấp file hoặc image_id, không gửi đồng thời cả hai.",
        )
    try:
        validate_pixel_spacing(pixel_spacing_mm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    img_np = None
    target_image_id = image_id or str(uuid.uuid4())
    calibration_source = "MANUAL" if pixel_spacing_mm is not None else "NONE"

    if file:
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Dung lượng file vượt quá giới hạn 20 MiB.")
        if len(contents) < 64:
            raise HTTPException(status_code=400, detail="File ảnh rỗng hoặc quá nhỏ.")
        if SYNTHETIC_DEMO_MODE and hashlib.sha256(contents).hexdigest() not in SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256:
            raise HTTPException(
                status_code=422,
                detail="Chế độ demo chỉ chấp nhận fixture tổng hợp đã được cấu hình.",
            )
        try:
            with Image.open(BytesIO(contents)) as image_header:
                if not is_within_decoded_image_limit(*image_header.size):
                    raise HTTPException(
                        status_code=413,
                        detail=f"Kích thước ảnh giải mã vượt quá {MAX_DECODED_IMAGE_PIXELS} điểm ảnh.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Không thể đọc dữ liệu ảnh.") from exc
        arr = np.frombuffer(contents, dtype=np.uint8)
        img_np = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_np is None:
            raise HTTPException(status_code=400, detail="Không thể giải mã dữ liệu file ảnh.")
        if not is_within_decoded_image_limit(img_np.shape[1], img_np.shape[0]):
            raise HTTPException(
                status_code=413,
                detail=f"Kích thước ảnh giải mã vượt quá {MAX_DECODED_IMAGE_PIXELS} điểm ảnh.",
            )
    elif image_id:
        img_rec = db.query(ImageModel).filter(ImageModel.id == image_id).first()
        if not img_rec or not os.path.exists(img_rec.raw_path):
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế.")
        if not image_id.startswith("sample_"):
            if not img_rec.study_id:
                raise HTTPException(status_code=409, detail="Ảnh chưa thuộc một ca khảo sát có thể chỉnh sửa.")
            require_active_case_lease(
                db,
                img_rec.study_id,
                current_user,
                lease_token,
                page_instance_id,
                allow_reviewed=True,
            )
        img_np = decode_ultrasound_image(img_rec.raw_path)
        if img_np is None:
            raise HTTPException(status_code=400, detail="Không thể đọc nội dung file ảnh y tế.")
        if pixel_spacing_mm is None:
            calibration = get_image_calibration(img_rec)
            pixel_spacing_mm = calibration["pixel_spacing_mm"]
            calibration_source = calibration["calibration_source"]
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

    if not model_registry.get_primary_adapter().is_loaded:
        raise HTTPException(status_code=503, detail="Checkpoint mô hình chưa được nạp hoặc không khớp SHA-256 đã chọn.")

    # 2. Letterbox 512x512 Preprocessing (Aspect Ratio preserved, Bilinear interpolation)
    tensor, padded_gray, transform_params, iqa_report = preprocessor.preprocess_for_inference(img_np)

    # 3. PyTorch Model Inference
    v1_scale = float(transform_params.get("scale", 1.0))
    inference_result = await run_in_threadpool(
        model_registry.predict,
        tensor, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=v1_scale
    )
    measurements = inference_result["measurements"]
    if isinstance(measurements, dict):
        measurements["calibration_source"] = calibration_source
        measurements["pixel_spacing_mm"] = pixel_spacing_mm
    provenance = dict(inference_result.get("provenance") or {})
    provenance["pixel_spacing_mm"] = pixel_spacing_mm
    provenance["calibration_source"] = calibration_source

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
        "measurements": measurements,
        "quality_gate": inference_result.get("quality_gate"),
        "uncertainty": inference_result.get("uncertainty"),
        "provenance": provenance,
    }


@router.post("/cdss/evaluate")
def evaluate_cdss_v1(req: CDSSEvaluateRequest):
    """
    Research-only rule probe for explicitly entered clinician data.
    """
    from backend.services.cdss_engine import CDSSReasoningEngine

    # Omitted request fields must not be interpreted as observed findings.
    return CDSSReasoningEngine().evaluate_case(
        vision_findings=req.vision_findings if "vision_findings" in req.model_fields_set else {},
        patient_context=req.patient_context if "patient_context" in req.model_fields_set else {},
        adnex_inputs=(
            req.adnex_inputs.model_dump(exclude_unset=True)
            if req.adnex_inputs is not None
            else None
        ),
    )


@router.post("/cdss/evaluate-multi")
def evaluate_cdss_multi_v1(req: CDSSMultiLesionEvaluateRequest):
    """Multi-lesion aggregation evaluated with worst-case semantics (F13)."""
    from backend.services.cdss_engine import CDSSReasoningEngine

    return CDSSReasoningEngine().evaluate_multi_lesions(
        lesions=req.lesions,
        patient_context=req.patient_context,
        adnex_inputs=(
            req.adnex_inputs.model_dump(exclude_unset=True)
            if req.adnex_inputs is not None
            else None
        ),
    )


@router.post("/cases/confirm")
def confirm_case_v1(
    req: CaseConfirmRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Use the same validation and audit flow as /api/review."""
    review = persist_single_review(
        db,
        req,
        current_user,
        inference_engine=model_registry.get_primary_adapter().engine,
        image_preprocessor=preprocessor,
    )
    return {
        "success": True,
        "review_id": review["review_id"],
        "image_id": req.image_id,
        "study_id": req.study_id,
        "status": "REVIEWED",
        "message": review["message"],
        "is_ground_truth": review["is_ground_truth"],
    }


@router.get("/clinical-templates")
def list_clinical_templates_v1():
    """Danh sách các Smart Macro Chips mẫu lâm sàng nhanh chuẩn O-RADS/IOTA."""
    from backend.services.clinical_templates import get_clinical_templates_list

    return {"templates": get_clinical_templates_list()}


@router.post("/clinical-templates/apply")
def apply_clinical_template_v1(req: ApplyClinicalTemplateRequest):
    """Áp dụng 1 mẫu lâm sàng nhanh và tự động tính toán CDSS."""
    from backend.services.clinical_templates import apply_clinical_template

    try:
        return apply_clinical_template(
            template_id=req.template_id,
            max_diameter_mm=req.max_diameter_mm,
            patient_context=req.patient_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
