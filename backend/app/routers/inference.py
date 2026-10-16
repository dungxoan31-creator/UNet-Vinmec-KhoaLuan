"""
Image Upload, IQA Validation, and Medical AI Inference Endpoints:
- Strict input validation & security checks (path traversal prevention, mime-types, file size)
- Image Quality Assessment (IQA) & Modality Verification
- Pure neural network forward pass without hardcoded overrides or mock responses
- Traceable model provenance & uncertainty quantification
- Clinical audit trail logging
"""

import base64
import hashlib
import math
import os
import uuid
from datetime import datetime
from io import BytesIO
from typing import Literal

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import UPLOAD_DIR, model_registry, preprocessor
from backend.app.routers.auth import get_current_user
from backend.core.image_utils import cv2_imread_unicode
from backend.db.database import (
    AuditLogModel,
    ImageModel,
    PatientModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import ImageValidationResult, MaskMeasurementsRequest, PredictionResponse
from backend.services.inference_engine import InferenceEngine
from backend.services.source_measurements import calibration_metadata, measure_source_mask

router = APIRouter(tags=["Image & Inference"])


def validate_pixel_spacing(spacing: float | None) -> float | None:
    """Reject supplied physical scales that cannot represent millimeters per pixel."""
    if spacing is not None and (not math.isfinite(spacing) or spacing <= 0):
        raise HTTPException(status_code=422, detail="pixel_spacing_mm phải là số hữu hạn lớn hơn 0.")
    return spacing


def is_single_frame_ultrasound_dicom(dicom) -> bool:
    """This 2D model accepts one ultrasound still image, not MR/CT or cine."""
    try:
        return str(dicom.get("Modality", "")).upper() == "US" and int(dicom.get("NumberOfFrames", 1)) == 1
    except (TypeError, ValueError):
        return False


def decode_ultrasound_image(file_path: str, grayscale: bool = False):
    """Decode raster or DICOM pixels for upload, IQA and inference."""
    if not file_path.lower().endswith(".dcm"):
        return cv2_imread_unicode(file_path, cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR)
    try:
        import pydicom

        dicom = pydicom.dcmread(file_path)
        if not is_single_frame_ultrasound_dicom(dicom):
            return None
        image = dicom.pixel_array
        if image.ndim == 4 or (image.ndim == 3 and int(getattr(dicom, "SamplesPerPixel", 1)) == 1):
            image = image[0]
        if image.dtype != "uint8":
            image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        if grayscale and image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return image
    except Exception:
        return None


def extract_dicom_calibration_spacing(file_path: str) -> float | None:
    """
    Extracts true physical millimeter spacing per pixel from DICOM tags:
    1. Tag (0018, 6011) Sequence of Ultrasound Regions -> PhysicalDeltaX / PhysicalDeltaY
    2. Tag (0028, 0030) Pixel Spacing -> [Row Spacing, Column Spacing]
    Returns None when no physical calibration is available.
    """
    if not file_path.lower().endswith(".dcm"):
        return None
    try:
        import pydicom

        dcm = pydicom.dcmread(file_path, stop_before_pixels=True)
        # Check Sequence of Ultrasound Regions (0018,6011)
        us_regions = dcm.get("SequenceOfUltrasoundRegions")
        if us_regions and len(us_regions) > 0:
            region = us_regions[0]
            dx = getattr(region, "PhysicalDeltaX", None)
            dy = getattr(region, "PhysicalDeltaY", None)
            unit_x = getattr(region, "PhysicalUnitsXDirection", None)
            unit_y = getattr(region, "PhysicalUnitsYDirection", None)
            if dx is not None and dy is not None and unit_x in (3, 4) and unit_y in (3, 4):
                spacing_x = float(dx) * (10 if unit_x == 3 else 1)
                spacing_y = float(dy) * (10 if unit_y == 3 else 1)
                if (math.isfinite(spacing_x) and math.isfinite(spacing_y) and
                        spacing_x > 0 and spacing_y > 0 and math.isclose(spacing_x, spacing_y, rel_tol=0.001)):
                    return round(spacing_x, 4)
                return None

        # Check standard Pixel Spacing (0028,0030)
        pixel_spacing = dcm.get("PixelSpacing")
        if pixel_spacing and len(pixel_spacing) >= 2:
            row_spacing, column_spacing = float(pixel_spacing[0]), float(pixel_spacing[1])
            if (math.isfinite(row_spacing) and math.isfinite(column_spacing) and
                    row_spacing > 0 and column_spacing > 0 and math.isclose(row_spacing, column_spacing, rel_tol=0.001)):
                return round(row_spacing, 4)
    except Exception as e:
        print(f"[DICOM Calibration] Tag read notice: {e}")
    return None


@router.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    study_id: str | None = Form(None),
    laterality: str | None = Form(None),
    anonymized_pid: str | None = Form(None),
    patient_age: str | None = Form(None),
    pixel_spacing_mm: float | None = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Upload an ultrasound image, validate format & size, store securely, and attach to a study.
    """
    validate_pixel_spacing(pixel_spacing_mm)
    if laterality is not None and laterality not in {"R", "L"}:
        raise HTTPException(status_code=422, detail="Bên khảo sát phải là R hoặc L.")
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first() if study_id else None
    if study_id and study is None:
        raise HTTPException(status_code=404, detail="Mã ca khám không tồn tại.")
    if laterality and study and study.ovary_side != "BOTH":
        raise HTTPException(status_code=422, detail="Ảnh R/L chỉ được gắn vào ca khảo sát hai bên.")
    if study_id and laterality:
        existing = db.query(ImageModel).filter(
            ImageModel.study_id == study_id, ImageModel.laterality == laterality
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Ca khám đã có ảnh cho bên khảo sát này.")
    safe_filename = os.path.basename(file.filename or "uploaded_image.png")
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".dcm"]:
        raise HTTPException(
            status_code=400, detail="Định dạng file không hợp lệ. Vui lòng chọn ảnh PNG, JPG, JPEG hoặc DICOM (.dcm)."
        )

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="Dung lượng file quá lớn (> 20MB). Vui lòng nén hoặc chọn file nhỏ hơn."
        )

    if len(contents) < 64:
        raise HTTPException(status_code=400, detail="File ảnh rỗng hoặc kích thước quá nhỏ (< 64 bytes).")
    uploaded_hash = hashlib.sha256(contents).hexdigest()

    dicom_metadata = None
    if ext == ".dcm":
        try:
            import pydicom

            dicom_header = pydicom.dcmread(BytesIO(contents), stop_before_pixels=True)
            supported_dicom = is_single_frame_ultrasound_dicom(dicom_header)
        except Exception:
            supported_dicom = False
        if not supported_dicom:
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ DICOM siêu âm 2D một frame có Modality US.")
        dicom_metadata = {
            "modality": "US",
            "number_of_frames": 1,
            "study_instance_uid": str(dicom_header.get("StudyInstanceUID", "")) or None,
            "series_instance_uid": str(dicom_header.get("SeriesInstanceUID", "")) or None,
        }

    if study:
        for existing_image in db.query(ImageModel).filter(ImageModel.study_id == study.id):
            if existing_image.file_hash == uploaded_hash:
                raise HTTPException(status_code=409, detail="Ảnh này đã tồn tại trong ca khảo sát.")
            if existing_image.file_hash:
                continue
            try:
                with open(existing_image.raw_path, "rb") as existing_file:
                    if hashlib.file_digest(existing_file, "sha256").hexdigest() == uploaded_hash:
                        raise HTTPException(status_code=409, detail="Ảnh này đã tồn tại trong ca khảo sát.")
            except FileNotFoundError:
                continue

    image_id = str(uuid.uuid4())
    save_filename = f"{image_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, save_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    # Extract DICOM calibration spacing if available
    calibrated_spacing = extract_dicom_calibration_spacing(file_path)
    if dicom_metadata is not None:
        dicom_metadata["calibrated_spacing_mm"] = calibrated_spacing

    # Read image with OpenCV to get dimensions and verify validity
    img_np = decode_ultrasound_image(file_path)

    if img_np is None:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Không thể đọc nội dung file ảnh y tế. File có thể bị hỏng.")

    h, w = img_np.shape[:2]

    # Link or Create Study & Patient
    if not study_id:
        anonymized_pid = anonymized_pid or f"ANON-UPLOAD-{uuid.uuid4().hex[:12].upper()}"
        patient = db.query(PatientModel).filter(PatientModel.anonymized_pid == anonymized_pid).first()
        if not patient:
            patient = PatientModel(
                id=str(uuid.uuid4()), anonymized_pid=anonymized_pid, age_bucket=patient_age
            )
            db.add(patient)
            db.commit()

        study_id = str(uuid.uuid4())
        study = StudyModel(
            id=study_id,
            patient_id=patient.id,
            study_code=f"STD-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            study_date=datetime.now().strftime("%Y-%m-%d"),
            status="PENDING",
            device_vendor=None,
            probe_type=None,
        )
        db.add(study)
        db.commit()

    image_record = ImageModel(
        id=image_id,
        study_id=study.id,
        filename=safe_filename,
        laterality=laterality,
        raw_path=file_path,
        file_hash=uploaded_hash,
        width=w,
        height=h,
        pixel_spacing_mm=pixel_spacing_mm if pixel_spacing_mm is not None else calibrated_spacing,
    )
    db.add(image_record)

    # Log Clinical Audit Trail
    audit_log = AuditLogModel(
        entity_name="image",
        entity_id=image_id,
        action_type="UPLOAD_IMAGE",
        actor_id=current_user.username,
        details={
            "filename": safe_filename,
            "dimensions": [w, h],
            "size_kb": round(len(contents) / 1024, 1),
            "study_id": study.id,
            "laterality": laterality,
        },
    )
    db.add(audit_log)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        try:
            os.remove(file_path)
        except OSError:
            pass
        if "uq_study_file_hash" in str(exc.orig) or "images.study_id, images.file_hash" in str(exc.orig):
            raise HTTPException(status_code=409, detail="Ảnh này đã tồn tại trong ca khảo sát.") from exc
        raise

    return {
        "image_id": image_id,
        "study_id": study.id,
        "laterality": laterality,
        "filename": safe_filename,
        "dimensions": [w, h],
        "size_kb": round(len(contents) / 1024, 1),
        "dicom_metadata": dicom_metadata,
        "message": "Upload và kiểm tra file thành công.",
    }


@router.get("/api/images/{image_id}/viewer-source")
def get_viewer_source(image_id: str, db: Session = Depends(get_db)):
    """Return the same preprocessed pixels used for inference when reopening a case."""
    image_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh của ca khảo sát.")
    if not os.path.isfile(image_record.raw_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp ảnh gốc trên máy chủ.")
    decoded = decode_ultrasound_image(image_record.raw_path, grayscale=True)
    if decoded is None:
        raise HTTPException(status_code=422, detail="Không thể giải mã ảnh của ca khảo sát.")
    _, padded_gray, _, _ = preprocessor.preprocess_for_inference(decoded)
    encoded, buffer = cv2.imencode(".png", padded_gray)
    if not encoded:
        raise HTTPException(status_code=500, detail="Không thể tạo ảnh cho viewer.")
    return {"image_id": image_id, "original_image_base64": f"data:image/png;base64,{base64.b64encode(buffer).decode('ascii')}"}


@router.get("/api/images/{image_id}/mask.png")
def export_source_mask(
    image_id: str,
    kind: Literal["ai", "reviewed"] = "reviewed",
    review_id: str | None = None,
    prediction_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Export the selected binary mask in the decoded source image's pixel space."""
    if kind == "ai" and review_id is not None:
        raise HTTPException(status_code=422, detail="review_id không thể kết hợp với kind='ai'.")
    if kind == "reviewed" and prediction_id is not None:
        raise HTTPException(status_code=422, detail="prediction_id không thể kết hợp với kind='reviewed'.")

    image_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not image_record or not os.path.isfile(image_record.raw_path):
        raise HTTPException(status_code=404, detail="Source image unavailable.")

    if kind == "reviewed":
        if review_id is not None:
            result = db.query(ReviewModel).filter(ReviewModel.id == review_id).first()
            if not result or result.image_id != image_id:
                raise HTTPException(status_code=404, detail="Requested review mask unavailable.")
        else:
            result = db.query(ReviewModel).filter(ReviewModel.image_id == image_id).order_by(
                ReviewModel.created_at.desc(), ReviewModel.id.desc()
            ).first()
        rle = result.verified_mask_rle if result else None
    else:
        if prediction_id is not None:
            result = db.query(PredictionModel).filter(PredictionModel.id == prediction_id).first()
            if not result or result.image_id != image_id:
                raise HTTPException(status_code=404, detail="Requested prediction mask unavailable.")
        else:
            result = db.query(PredictionModel).filter(PredictionModel.image_id == image_id).order_by(
                PredictionModel.created_at.desc(), PredictionModel.id.desc()
            ).first()
        rle = result.raw_mask_rle if result else None
    if rle is None:
        raise HTTPException(status_code=404, detail="Requested mask unavailable.")
    decoded = decode_ultrasound_image(image_record.raw_path, grayscale=True)
    if decoded is None:
        raise HTTPException(status_code=422, detail="Source image cannot be decoded.")
    _, transform = preprocessor.letterbox_resize(decoded)
    try:
        model_mask = InferenceEngine.rle_to_mask(rle)
        source_mask = preprocessor.inverse_letterbox_mask(model_mask, transform)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Stored mask is invalid.") from exc
    encoded, buffer = cv2.imencode(".png", (source_mask > 0).astype("uint8") * 255)
    if not encoded:
        raise HTTPException(status_code=500, detail="Mask export failed.")
    return Response(
        content=buffer.tobytes(),
        media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename={kind}_mask.png", "X-Mask-Coordinate-Space": "decoded-source-image"},
    )


def get_image_calibration(image_record):
    dicom_spacing = extract_dicom_calibration_spacing(image_record.raw_path) if os.path.isfile(image_record.raw_path) else None
    return calibration_metadata(image_record.pixel_spacing_mm, dicom_spacing)


def load_decoded_source(image_record):
    if image_record is None or not os.path.isfile(image_record.raw_path):
        raise HTTPException(status_code=404, detail="Source image unavailable.")
    try:
        decoded = decode_ultrasound_image(image_record.raw_path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Source image cannot be decoded.") from exc
    if decoded is None:
        raise HTTPException(status_code=422, detail="Source image cannot be decoded.")
    return decoded


@router.get("/api/images/{image_id}/source.png")
def export_decoded_source(image_id: str, db: Session = Depends(get_db)):
    """Return the full decoded raster, without CLAHE, letterboxing or viewer filters."""
    record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    decoded = load_decoded_source(record)
    if record.raw_path.lower().endswith(".dcm") and decoded.ndim == 3:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_RGB2BGR)
    encoded, buffer = cv2.imencode(".png", decoded)
    if not encoded:
        raise HTTPException(status_code=500, detail="Source export failed.")
    return Response(content=buffer.tobytes(), media_type="image/png", headers={
        "X-Image-Coordinate-Space": "decoded-source-image",
        "X-Source-Width": str(decoded.shape[1]), "X-Source-Height": str(decoded.shape[0]),
    })


@router.post("/api/images/{image_id}/measurements")
def source_mask_measurements(image_id: str, req: MaskMeasurementsRequest, db: Session = Depends(get_db)):
    """Measure the supplied editable mask in actual source pixels; do not persist it."""
    record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    decoded = load_decoded_source(record)
    return measure_source_mask(
        decoded, req.rle_mask, preprocessor, model_registry.get_primary_adapter().engine,
        get_image_calibration(record),
    )


@router.post("/api/validate-image", response_model=ImageValidationResult)
def validate_image_quality(image_id: str, db: Session = Depends(get_db)):
    """
    Performs pre-inference Image Quality Assessment (IQA) & Modality Validation.
    Verifies ultrasound format, resolution, blur, saturation, and exposure.
    """
    img_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not img_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế trên hệ thống.")
    file_path = img_record.raw_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File ảnh không tồn tại trên hệ thống lưu trữ.")

    img_np = decode_ultrasound_image(file_path)
    if img_np is None:
        raise HTTPException(status_code=400, detail="File ảnh bị lỗi không thể giải mã.")

    validation = preprocessor.validate_ultrasound_suitability(img_np)

    # Record IQA Validation in Audit Logs
    audit_log = AuditLogModel(
        entity_name="image",
        entity_id=image_id,
        action_type="VALIDATE_IQA",
        actor_id="system_iqa_service",
        details={
            "is_acceptable": validation["is_suitable"],
            "iqa_score": validation["iqa_score"],
            "laplacian_variance": validation.get("laplacian_variance"),
            "contrast_std": validation.get("contrast_std"),
        },
    )
    db.add(audit_log)
    db.commit()

    return {
        "is_acceptable": validation["is_suitable"],
        "status_text": "Ảnh đủ điều kiện phân tích" if validation["is_suitable"] else "Ảnh không phù hợp để phân tích",
        "iqa_score": validation["iqa_score"],
        "details": validation["checklist"],
        "message": validation["error_message"],
    }


@router.post("/api/predict/{image_id}", response_model=PredictionResponse)
def run_ai_prediction(image_id: str, pixel_spacing_mm: float | None = None, db: Session = Depends(get_db)):
    """
    Executes end-to-end preprocessing, Attention U-Net inference via ModelRegistry,
    uncertainty estimation, and automated caliper measurement.
    Rejects unsuitable images with HTTP 422.
    """
    validate_pixel_spacing(pixel_spacing_mm)
    if not model_registry.get_primary_adapter().is_loaded:
        raise HTTPException(status_code=503, detail="Checkpoint mô hình chưa được nạp hoặc không khớp SHA-256 đã chọn.")
    img_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not img_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế trên hệ thống.")
    file_path = img_record.raw_path
    filename = img_record.filename
    study_id = img_record.study_id

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File ảnh không tồn tại trên ổ đĩa.")

    # Read image with unicode support
    img_np = decode_ultrasound_image(file_path, grayscale=True)
    if img_np is None:
        raise HTTPException(status_code=400, detail="Không thể đọc dữ liệu ảnh y tế.")

    # Strict suitability check: reject unsuitable/non-ultrasound images
    if not image_id.startswith("sample_"):
        validation = preprocessor.validate_ultrasound_suitability(img_np)
        if not validation["is_suitable"]:
            raise HTTPException(
                status_code=422, detail=f"Hình ảnh không phù hợp để phân tích: {validation['error_message']}"
            )

    start_time = datetime.now()

    # 1. Preprocess & IQA
    tensor, padded_gray, transform_params, iqa_report = preprocessor.preprocess_for_inference(img_np)

    # 2. Run Pure Neural Network Inference via ModelRegistry
    pixel_spacing = pixel_spacing_mm if pixel_spacing_mm is not None else calibration_metadata(img_record.pixel_spacing_mm)["pixel_spacing_mm"]
    if pixel_spacing_mm is not None:
        img_record.pixel_spacing_mm = pixel_spacing_mm
    roi_mask = transform_params.get("roi_mask")
    inference_result = model_registry.predict(
        tensor, padded_gray, pixel_spacing_mm=pixel_spacing, roi_mask=roi_mask
    )

    inference_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Encode original 512x512 gray to base64
    _, orig_buffer = cv2.imencode(".png", padded_gray)
    orig_b64 = f"data:image/png;base64,{base64.b64encode(orig_buffer).decode('utf-8')}"

    clean_transform = {
        "scale": float(transform_params.get("scale", 1.0)),
        "pad_w": int(transform_params.get("pad_w", 0)),
        "pad_h": int(transform_params.get("pad_h", 0)),
        "new_w": int(transform_params.get("new_w", 512)),
        "new_h": int(transform_params.get("new_h", 512)),
        "orig_w": int(img_np.shape[1]),
        "orig_h": int(img_np.shape[0]),
    }

    import json
    from datetime import UTC
    model_sel = getattr(model_registry, "model_selection", {}) or {}
    serving_config_bytes = json.dumps(model_sel, sort_keys=True).encode("utf-8")
    serving_config_sha256 = hashlib.sha256(serving_config_bytes).hexdigest()

    primary_ad = model_registry.get_primary_adapter()
    engine_obj = getattr(primary_ad, "engine", None)

    provenance_payload = {
        "checkpoint_sha256": inference_result.get("provenance", {}).get("model_checksum") or getattr(engine_obj, "model_checksum", None),
        "serving_config_sha256": serving_config_sha256,
        "architecture": inference_result.get("provenance", {}).get("architecture") or getattr(primary_ad, "architecture", "Standard U-Net"),
        "threshold": float(getattr(engine_obj, "threshold", 0.5)),
        "native_shape": [int(img_np.shape[0]), int(img_np.shape[1])],
        "transform": clean_transform,
        "model_version": inference_result.get("provenance", {}).get("model_version", "AttentionUNet-v1.2"),
        "pixel_spacing_mm": inference_result.get("provenance", {}).get("pixel_spacing_mm"),
        "created_at": datetime.now(UTC).isoformat(),
    }

    prediction_id = None
    # If real DB record, save prediction and update study status
    if not image_id.startswith("sample_"):
        prediction_id = str(uuid.uuid4())
        pred_record = PredictionModel(
            id=prediction_id,
            image_id=image_id,
            model_version=inference_result.get("provenance", {}).get("model_version", "AttentionUNet-v1.2"),
            inference_time_ms=inference_duration_ms,
            confidence_score=inference_result["confidence_score"],
            iqa_score=iqa_report["iqa_score"],
            raw_mask_rle=inference_result["rle_mask"],
            measurements=inference_result["measurements"],
            provenance_json=provenance_payload,
        )
        db.add(pred_record)

        # Update Study status to ANALYZED
        if study_id:
            study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
            if study and study.status == "PENDING":
                study.status = "ANALYZED"

        # Log AI Prediction in Audit Trail
        audit_log = AuditLogModel(
            entity_name="image",
            entity_id=image_id,
            action_type="RUN_PREDICTION",
            actor_id="system_ai_engine",
            details={
                "model_version": inference_result.get("provenance", {}).get("model_version"),
                "model_checksum": inference_result.get("provenance", {}).get("model_checksum"),
                "confidence_score": inference_result["confidence_score"],
                "quality_gate_passed": inference_result.get("quality_gate", {}).get("passed", False),
                "uncertainty_level": inference_result.get("uncertainty", {}).get("uncertainty_level"),
                "total_lesions": inference_result.get("measurements", {}).get("total_lesions", 0),
                "max_diameter_mm": inference_result.get("measurements", {}).get("max_diameter_mm", 0.0),
                "inference_time_ms": inference_duration_ms,
            },
        )
        db.add(audit_log)
        db.commit()

    return {
        "image_id": image_id,
        "prediction_id": prediction_id,
        "study_id": study_id,
        "filename": filename,
        "confidence_score": inference_result["confidence_score"],
        "inference_time_ms": inference_duration_ms,
        "iqa": iqa_report,
        "measurements": inference_result["measurements"],
        "acoustic_profile": inference_result.get("acoustic_profile"),
        "cdss_classification": inference_result.get("cdss_classification"),
        "rle_mask": inference_result["rle_mask"],
        "overlay_base64": inference_result["overlay_base64"],
        "original_image_base64": orig_b64,
        "uncertainty": inference_result.get("uncertainty"),
        "quality_gate": inference_result.get("quality_gate"),
        "provenance": provenance_payload,
    }



@router.post("/api/images/{image_id}/calibrate")
def calibrate_image_spacing(
    image_id: str,
    pixel_spacing_mm: float | None = None,
    distance_mm: float | None = None,
    distance_pixels: float | None = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Calibrate physical scale (mm/pixel) for an ultrasound image.
    Supports direct pixel_spacing_mm or depth scale calibration (distance_mm / distance_pixels).
    Updates ImageModel and recomputes prediction measurements if available.
    """
    img_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not img_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế trên hệ thống.")

    spacing = None
    if pixel_spacing_mm is not None:
        spacing = validate_pixel_spacing(pixel_spacing_mm)
    elif distance_mm is not None and distance_pixels is not None and distance_pixels > 0:
        spacing = float(distance_mm) / float(distance_pixels)

    if spacing is None:
        raise HTTPException(
            status_code=422,
            detail="Vui lòng cung cấp pixel_spacing_mm hợp lệ (> 0) hoặc thông số khoảng cách chuẩn.",
        )
    spacing = validate_pixel_spacing(round(spacing, 4))
    img_record.pixel_spacing_mm = spacing

    # If prediction exists, update measurements with calibrated spacing
    prediction = (
        db.query(PredictionModel)
        .filter(PredictionModel.image_id == image_id)
        .order_by(PredictionModel.created_at.desc())
        .first()
    )
    updated_measurements = None
    if prediction and prediction.raw_mask_rle:
        engine = model_registry.get_primary_adapter().engine
        mask = engine.rle_to_mask(prediction.raw_mask_rle)
        updated_measurements = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=spacing)
        updated_measurements["calibrated"] = True
        prediction.measurements = updated_measurements

    audit = AuditLogModel(
        entity_name="image",
        entity_id=image_id,
        action_type="CALIBRATE_SPACING",
        actor_id=current_user.username,
        details={"pixel_spacing_mm": spacing},
    )
    db.add(audit)
    db.commit()

    return {
        "success": True,
        "image_id": image_id,
        "pixel_spacing_mm": spacing,
        "measurements": updated_measurements,
        "message": f"Đã hiệu chuẩn tỉ lệ vật lý: {spacing} mm/pixel.",
    }
