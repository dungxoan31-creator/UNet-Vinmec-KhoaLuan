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
import logging
import math
import os
import tempfile
import time
import uuid
from datetime import datetime
from io import BytesIO
from typing import Literal
from uuid import UUID

import cv2
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import (
    SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256,
    SYNTHETIC_DEMO_MODE,
    UPLOAD_DIR,
    model_registry,
    preprocessor,
)
from backend.app.security import get_current_user, require_clinical
from backend.core.image_utils import MAX_DECODED_IMAGE_PIXELS, MAX_UPLOAD_BYTES
from backend.core.prediction_idempotency import prediction_idempotency_digests
from backend.core.upload_idempotency import upload_idempotency_digests
from backend.db.database import (
    AuditLogModel,
    ImageModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    VisitNumberCapacityExceeded,
    get_db,
)
from backend.schemas.schemas import (
    ImageValidationResult,
    InteractivePromptRequest,
    MaskMeasurementsRequest,
    PredictionResponse,
)
from backend.services.calibration_service import get_automatic_calibration
from backend.services.case_lease_service import (
    _FINAL_STATUSES,
    require_active_case_lease,
    verify_active_case_lease_readonly,
)
from backend.services.dicom_privacy import minimize_dicom_patient_metadata
from backend.services.file_deletion_service import enqueue_upload_deletions, retry_pending_file_deletions
from backend.services.image_service import (
    decode_ultrasound_image,
    extract_dicom_calibration_spacing,
    get_image_calibration,
    is_single_frame_ultrasound_dicom,
)
from backend.services.image_service import (
    validate_pixel_spacing as _validate_pixel_spacing,
)
from backend.services.inference_engine import InferenceEngine
from backend.services.measurement_safety import (
    prediction_measurements_match_calibration,
    strip_unverified_physical_measurements,
)
from backend.services.metadata_extractor import extract_file_metadata
from backend.services.patient_identity import get_or_create_patient
from backend.services.source_measurements import measure_source_mask

router = APIRouter(tags=["Image & Inference"], dependencies=[Depends(require_clinical)])
logger = logging.getLogger(__name__)


def _reject_oversized_decoded_dimensions(width, height) -> None:
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError, OverflowError):
        return
    if width > 0 and height > 0 and width * height > MAX_DECODED_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Kích thước ảnh giải mã vượt giới hạn (> 25 triệu pixels).",
        )


def _preflight_raster_dimensions(contents: bytes) -> None:
    """Reject oversized raster headers before file writes or full pixel decode."""
    try:
        with Image.open(BytesIO(contents)) as image_header:
            width, height = image_header.size
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=413,
            detail="Kích thước ảnh giải mã vượt giới hạn (> 25 triệu pixels).",
        ) from exc
    except Exception:
        return
    _reject_oversized_decoded_dimensions(width, height)


def _preflight_dicom_dimensions(dicom_dataset) -> None:
    _reject_oversized_decoded_dimensions(
        dicom_dataset.get("Columns"), dicom_dataset.get("Rows")
    )


def _verify_upload_commit(bind, image_id: str, file_path: str, uploaded_hash: str) -> bool | None:
    """Return True/False for a confirmed commit outcome, or None when it is uncertain."""
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            image_record = verify_db.get(ImageModel, image_id)
            if image_record is None:
                return False
            if (
                image_record.raw_path != file_path
                or image_record.filename != os.path.basename(file_path)
                or image_record.file_hash != uploaded_hash
            ):
                return None
            audit_exists = (
                verify_db.query(AuditLogModel.id)
                .filter_by(entity_name="image", entity_id=image_id, action_type="UPLOAD_IMAGE")
                .first()
                is not None
            )
            if not audit_exists or not os.path.isfile(file_path):
                return None
            return True
    except Exception:
        return None


def validate_pixel_spacing(spacing: float | None) -> float | None:
    """Translate service validation errors into the API's 422 response contract."""
    try:
        return _validate_pixel_spacing(spacing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validated_prediction_letterbox_scale(transform, image_record) -> float | None:
    """Return the saved 512x512 letterbox scale only when it matches the source image."""
    if not isinstance(transform, dict):
        return None

    width = getattr(image_record, "width", None)
    height = getattr(image_record, "height", None)
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        return None

    for key, expected in (("orig_w", width), ("orig_h", height)):
        value = transform.get(key)
        if type(value) is not int or value != expected:
            return None

    scale_value = transform.get("scale")
    if isinstance(scale_value, bool) or not isinstance(scale_value, (int, float)):
        return None
    try:
        scale = float(scale_value)
    except (OverflowError, TypeError, ValueError):
        return None
    expected_scale = min(512 / width, 512 / height)
    if not math.isfinite(scale) or scale <= 0 or not math.isclose(
        scale, expected_scale, rel_tol=1e-12, abs_tol=1e-12
    ):
        return None

    expected_new_w = int(width * expected_scale)
    expected_new_h = int(height * expected_scale)
    expected_pad_w = (512 - expected_new_w) // 2
    expected_pad_h = (512 - expected_new_h) // 2
    for key, expected in (
        ("new_w", expected_new_w),
        ("new_h", expected_new_h),
        ("pad_w", expected_pad_w),
        ("pad_h", expected_pad_h),
    ):
        value = transform.get(key)
        if type(value) is not int or value != expected:
            return None
    return scale


def _stored_upload_replay_response(
    db: Session,
    image_record: ImageModel,
    *,
    dicom_metadata: dict | None,
    raw_filename: str | None,
) -> dict:
    """Rebuild the successful upload response from the committed image row."""
    upload_root = os.path.realpath(UPLOAD_DIR)
    stored_path = os.path.realpath(image_record.raw_path)
    try:
        path_is_owned = os.path.commonpath((upload_root, stored_path)) == upload_root
    except ValueError:
        path_is_owned = False
    if not path_is_owned or not os.path.isfile(stored_path):
        raise HTTPException(
            status_code=503,
            detail="Ảnh đã được ghi nhận nhưng tệp nguồn chưa sẵn sàng để phát lại. Cần quản trị viên đối soát.",
        )

    study = db.query(StudyModel).filter(StudyModel.id == image_record.study_id).first()
    if study is None:
        raise HTTPException(
            status_code=503,
            detail="Ảnh đã được ghi nhận nhưng ca khảo sát không khả dụng để phát lại.",
        )
    image_np = decode_ultrasound_image(stored_path)
    if image_np is None:
        raise HTTPException(
            status_code=503,
            detail="Ảnh đã được ghi nhận nhưng không thể đọc lại tệp nguồn an toàn.",
        )

    return {
        "image_id": image_record.id,
        "study_id": image_record.study_id,
        "visit_no": study.visit_no,
        "laterality": image_record.laterality,
        "filename": image_record.filename,
        "dimensions": [image_record.width, image_record.height],
        "size_kb": round(os.path.getsize(stored_path) / 1024, 1),
        "dicom_metadata": dicom_metadata,
        "autofill_metadata": extract_file_metadata(stored_path, raw_filename),
        "calibration": get_automatic_calibration(stored_path, image_np),
        "message": "Ảnh đã được tải lên trước đó; dùng lại ảnh đã ghi nhận.",
        "idempotent_replay": True,
    }


def _stored_prediction_replay_response(prediction: PredictionModel, image_record: ImageModel) -> dict:
    """Rebuild a committed inference response without running the model a second time."""
    if not os.path.isfile(image_record.raw_path):
        raise HTTPException(
            status_code=503,
            detail="Dự đoán đã được lưu nhưng ảnh nguồn không khả dụng để phát lại an toàn.",
        )
    img_np = decode_ultrasound_image(image_record.raw_path, grayscale=True)
    if img_np is None:
        raise HTTPException(
            status_code=503,
            detail="Dự đoán đã được lưu nhưng ảnh nguồn không thể giải mã để phát lại an toàn.",
        )
    stored_measurements = prediction.measurements if isinstance(prediction.measurements, dict) else {}
    stored_provenance = prediction.provenance_json
    trusted_measurements = prediction_measurements_match_calibration(
        stored_measurements,
        get_image_calibration(image_record),
        stored_provenance,
    )
    safe_measurements = (
        stored_measurements
        if trusted_measurements
        else strip_unverified_physical_measurements(stored_measurements)
    )
    safe_provenance = (
        stored_provenance
        if trusted_measurements
        else strip_unverified_physical_measurements(stored_provenance)
    )
    try:
        _, padded_gray, _, iqa_report = preprocessor.preprocess_for_inference(img_np)
        binary_mask = InferenceEngine.rle_to_mask(prediction.raw_mask_rle)
        overlay = InferenceEngine.generate_overlay_base64(padded_gray, binary_mask, safe_measurements)
    except (KeyError, TypeError, ValueError, cv2.error) as exc:
        raise HTTPException(
            status_code=503,
            detail="Dự đoán đã được lưu nhưng bản ghi không thể dựng lại an toàn.",
        ) from exc

    original_encoded, original_buffer = cv2.imencode(".png", padded_gray)
    if not original_encoded:
        raise HTTPException(status_code=503, detail="Không thể dựng lại ảnh nguồn đã lưu.")
    uncertainty_map_base64 = (
        "data:image/png;base64," + base64.b64encode(prediction.uncertainty_map_png).decode("ascii")
        if prediction.uncertainty_map_png
        else None
    )
    extras = prediction.response_extras_json or {}
    return {
        "image_id": image_record.id,
        "prediction_id": prediction.id,
        "study_id": image_record.study_id,
        "filename": image_record.filename,
        "confidence_score": prediction.confidence_score,
        "inference_time_ms": prediction.inference_time_ms,
        "iqa": extras.get("iqa") or iqa_report,
        "measurements": safe_measurements,
        "acoustic_profile": extras.get("acoustic_profile"),
        "cdss_classification": extras.get("cdss_classification"),
        "rle_mask": prediction.raw_mask_rle,
        "overlay_base64": overlay,
        "original_image_base64": "data:image/png;base64," + base64.b64encode(original_buffer).decode("ascii"),
        "uncertainty_map_base64": uncertainty_map_base64,
        "uncertainty": extras.get("uncertainty"),
        "quality_gate": extras.get("quality_gate"),
        "provenance": safe_provenance,
        "timings": extras.get("timings"),
        "ai_diagnosis": extras.get("ai_diagnosis"),
        "unified_findings": extras.get("unified_findings"),
        "idempotent_replay": True,
    }


@router.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    study_id: str | None = Form(None),
    laterality: str | None = Form(None),
    anonymized_pid: str | None = Form(None, max_length=64),
    patient_age: str | None = Form(None, max_length=20),
    pixel_spacing_mm: float | None = Form(None),
    idempotency_key: UUID | None = Header(None, alias="Idempotency-Key"),
    lease_token: str | None = Header(None, alias="X-Case-Lease-Token"),
    page_instance_id: str | None = Header(None, alias="X-Case-Page-Instance-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """
    Upload an ultrasound image, validate format & size, store securely, and attach to a study.
    """
    if anonymized_pid is not None:
        anonymized_pid = anonymized_pid.strip()
        if not anonymized_pid:
            raise HTTPException(status_code=422, detail="PID must not be blank.")
    validate_pixel_spacing(pixel_spacing_mm)
    if laterality is not None and laterality not in {"R", "L"}:
        raise HTTPException(status_code=422, detail="Bên khảo sát phải là R hoặc L.")
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first() if study_id else None
    if study_id and study is None:
        raise HTTPException(status_code=404, detail="Mã ca khám không tồn tại.")
    if SYNTHETIC_DEMO_MODE and study is None:
        raise HTTPException(
            status_code=422,
            detail="Chế độ demo yêu cầu ca DEMO-SYNTHETIC-* đã được tạo trước khi tải ảnh.",
        )
    existing_study_id = study.id if study else None
    if existing_study_id:
        verify_active_case_lease_readonly(
            db,
            existing_study_id,
            current_user,
            lease_token,
            page_instance_id,
        )
    if laterality and study:
        allowed_lateralities = {
            "BOTH": {"L", "R"},
            "LEFT": {"L"},
            "RIGHT": {"R"},
        }.get(study.ovary_side)
        if allowed_lateralities is not None and laterality not in allowed_lateralities:
            raise HTTPException(status_code=422, detail="Bên ảnh không khớp với phạm vi bên đã khai báo cho ca khảo sát.")
    ext = os.path.splitext(file.filename or "uploaded_image.png")[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".dcm"]:
        raise HTTPException(
            status_code=400, detail="Định dạng file không hợp lệ. Vui lòng chọn ảnh PNG, JPG, JPEG hoặc DICOM (.dcm)."
        )

    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="Dung lượng file quá lớn (> 20MB). Vui lòng nén hoặc chọn file nhỏ hơn."
        )

    if len(contents) < 64:
        raise HTTPException(status_code=400, detail="File ảnh rỗng hoặc kích thước quá nhỏ (< 64 bytes).")
    uploaded_hash = hashlib.sha256(contents).hexdigest()
    if SYNTHETIC_DEMO_MODE and uploaded_hash not in SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256:
        raise HTTPException(
            status_code=422,
            detail="Chế độ demo chỉ chấp nhận fixture tổng hợp đã được cấu hình.",
        )
    source_content_sha256 = uploaded_hash
    upload_key_digest = None
    upload_request_digest = None
    if isinstance(idempotency_key, UUID):
        upload_key_digest, upload_request_digest = upload_idempotency_digests(
            idempotency_key,
            current_user.id,
            {
                "study_id": study_id,
                "laterality": laterality,
                "source_content_sha256": source_content_sha256,
                "extension": ext,
                "pixel_spacing_mm": pixel_spacing_mm,
                "anonymized_pid": anonymized_pid,
                "patient_age": patient_age,
            },
        )

    dicom_metadata = None
    image_id = str(uuid.uuid4())
    if ext == ".dcm":
        try:
            import pydicom

            dicom_dataset = pydicom.dcmread(BytesIO(contents))
            supported_dicom = is_single_frame_ultrasound_dicom(dicom_dataset)
        except Exception:
            supported_dicom = False
        if not supported_dicom:
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ DICOM siêu âm 2D một frame có Modality US.")
        _preflight_dicom_dimensions(dicom_dataset)
        burned_in_annotation = str(dicom_dataset.get("BurnedInAnnotation", "UNKNOWN")).strip().upper()
        if burned_in_annotation != "NO":
            raise HTTPException(
                status_code=422,
                detail=(
                    "DICOM có chữ định danh trong pixel hoặc chưa xác nhận trạng thái. "
                    "Hãy rà soát và loại bỏ thông tin định danh trước khi tải lên."
                ),
            )
        dicom_study_key = study.id if study else image_id
        dicom_series_key = f"{dicom_study_key}:{laterality or image_id}"
        minimize_dicom_patient_metadata(
            dicom_dataset,
            study_key=dicom_study_key,
            series_key=dicom_series_key,
            instance_key=image_id,
        )
        sanitized = BytesIO()
        try:
            dicom_dataset.save_as(sanitized)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="DICOM cannot be safely normalized.") from exc
        contents = sanitized.getvalue()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Processed DICOM exceeds the upload size limit.")
        uploaded_hash = hashlib.sha256(contents).hexdigest()
        dicom_metadata = {
            "modality": "US",
            "number_of_frames": 1,
            "privacy_processing": {
                "status": "partial_metadata_minimization",
                "pixel_data_reviewed": False,
                "burned_in_annotation": str(dicom_dataset.get("BurnedInAnnotation", "UNKNOWN")),
            },
        }
    else:
        # Corrupt or unsupported raster bytes continue through the normal 400 path.
        _preflight_raster_dimensions(contents)

    if upload_key_digest is not None:
        previous_upload = (
            db.query(ImageModel)
            .filter(ImageModel.upload_idempotency_key_digest == upload_key_digest)
            .first()
        )
        if previous_upload is not None:
            if previous_upload.upload_idempotency_request_digest != upload_request_digest:
                raise HTTPException(
                    status_code=409,
                    detail="Khóa thử lại đã được dùng cho một yêu cầu tải ảnh khác.",
                )
            return _stored_upload_replay_response(
                db,
                previous_upload,
                dicom_metadata=dicom_metadata,
                raw_filename=file.filename,
            )

    if study:
        for existing_image in db.query(ImageModel).filter(ImageModel.study_id == study.id):
            if existing_image.source_content_sha256 == source_content_sha256:
                raise HTTPException(status_code=409, detail="Ảnh này đã tồn tại trong ca khảo sát.")
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

    save_filename = f"{image_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, save_filename)
    response_payload = None

    try:
        # Release SQLite's preflight read snapshot before slow decode. The lease
        # is checked again after decode, then renewed in the write transaction.
        db.close()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Extract DICOM calibration spacing if available
        calibrated_spacing = extract_dicom_calibration_spacing(file_path)
        if dicom_metadata is not None:
            dicom_metadata["calibrated_spacing_mm"] = calibrated_spacing

        # Read image with OpenCV to get dimensions and verify validity
        img_np = decode_ultrasound_image(file_path)

        if img_np is None:
            raise HTTPException(status_code=400, detail="Không thể đọc nội dung file ảnh y tế. File có thể bị hỏng.")

        h, w = img_np.shape[:2]
        if h * w > MAX_DECODED_IMAGE_PIXELS:
            raise HTTPException(status_code=413, detail="Kích thước điểm ảnh giải mã quá lớn (> 25 triệu pixels).")

        if existing_study_id:
            # This is the transaction boundary for lease semantics: expiry at
            # this checkpoint returns 423; after renewal, the lease update and
            # image/audit writes remain held together through commit or rollback.
            require_active_case_lease(
                db,
                existing_study_id,
                current_user,
                lease_token,
                page_instance_id,
            )
            study = db.query(StudyModel).filter(StudyModel.id == existing_study_id).first()
            if not study:
                raise HTTPException(status_code=404, detail="Mã ca khám không tồn tại hoặc đã bị xóa.")

        target_study_id = study.id if study else None
        if study is not None and laterality in {"L", "R"}:
            existing_side_count = (
                db.query(ImageModel.id)
                .filter(ImageModel.study_id == study.id, ImageModel.laterality == laterality)
                .count()
            )
            if existing_side_count >= 20:
                raise HTTPException(
                    status_code=413,
                    detail="Mỗi bên chỉ được lưu tối đa 20 ảnh tĩnh trong một ca nghiên cứu.",
                )
        if not study_id:
            source_patient_id = anonymized_pid or f"ANON-UPLOAD-{uuid.uuid4().hex[:12].upper()}"
            patient = get_or_create_patient(db, source_patient_id, patient_age)
            db.flush()

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
            db.flush()
            target_study_id = study_id

        image_record = ImageModel(
            id=image_id,
            study_id=target_study_id,
            filename=save_filename,
            laterality=laterality,
            raw_path=file_path,
            file_hash=uploaded_hash,
            source_content_sha256=source_content_sha256,
            upload_idempotency_key_digest=upload_key_digest,
            upload_idempotency_request_digest=upload_request_digest,
            width=w,
            height=h,
            pixel_spacing_mm=pixel_spacing_mm if pixel_spacing_mm is not None else calibrated_spacing,
            calibration_source=("MANUAL" if pixel_spacing_mm is not None else "DICOM" if calibrated_spacing is not None else None),
        )
        db.add(image_record)

        # Log Clinical Audit Trail
        audit_log = AuditLogModel(
            entity_name="image",
            entity_id=image_id,
            action_type="UPLOAD_IMAGE",
            actor_id=current_user.username,
            details={
                "dimensions": [w, h],
                "size_kb": round(len(contents) / 1024, 1),
                "study_id": target_study_id,
                "laterality": laterality,
            },
        )
        db.add(audit_log)

        autofill_meta = extract_file_metadata(file_path, file.filename)
        autofill_calib = get_automatic_calibration(file_path, img_np)

        response_payload = {
            "image_id": image_id,
            "study_id": target_study_id,
            "visit_no": study.visit_no if study is not None else None,
            "laterality": laterality,
            "filename": save_filename,
            "dimensions": [w, h],
            "size_kb": round(len(contents) / 1024, 1),
            "dicom_metadata": dicom_metadata,
            "autofill_metadata": autofill_meta,
            "calibration": autofill_calib,
            "message": "Upload và kiểm tra file thành công.",
            "idempotent_replay": False,
        }

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if upload_key_digest is not None:
                committed_upload = (
                    db.query(ImageModel)
                    .filter(ImageModel.upload_idempotency_key_digest == upload_key_digest)
                    .first()
                )
                if committed_upload is not None:
                    if committed_upload.upload_idempotency_request_digest != upload_request_digest:
                        raise HTTPException(
                            status_code=409,
                            detail="Khóa thử lại đã được dùng cho một yêu cầu tải ảnh khác.",
                        ) from exc
                    try:
                        os.remove(file_path)
                    except FileNotFoundError:
                        pass
                    return _stored_upload_replay_response(
                        db,
                        committed_upload,
                        dicom_metadata=dicom_metadata,
                        raw_filename=file.filename,
                    )
            orig_str = str(getattr(exc, "orig", exc))
            if ("uq_study_file_hash" in orig_str or "images.study_id, images.file_hash" in orig_str
                    or "uq_study_source_content_sha256" in orig_str
                    or "images.study_id, images.source_content_sha256" in orig_str):
                raise HTTPException(status_code=409, detail="Ảnh này đã tồn tại trong ca khảo sát.") from exc
            if "FOREIGN KEY" in orig_str.upper() or "foreign key" in orig_str.lower():
                raise HTTPException(status_code=404, detail="Mã ca khám không tồn tại hoặc đã bị xóa.") from exc
            raise
    except VisitNumberCapacityExceeded as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Đã hết dải Visit No 6 chữ số. Cần quản trị viên xử lý trước khi tạo lượt mới.",
        ) from exc
    except Exception:
        rollback_error_type = None
        try:
            db.rollback()
        except Exception as rollback_error:
            rollback_error_type = type(rollback_error).__name__
            logger.critical(
                "Upload transaction rollback failed; reconciling durable state.",
                extra={
                    "upload_rollback_failure": True,
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
                "Upload session close failed during transaction reconciliation.",
                extra={
                    "upload_session_close_failure": True,
                    "close_error_type": type(close_error).__name__,
                },
            )

        commit_state = _verify_upload_commit(bind, image_id, file_path, uploaded_hash)
        if commit_state is True and response_payload is not None:
            logger.critical(
                "Upload commit raised after the image and audit record were persisted; returning verified result.",
                extra={"upload_commit_error_after_persist": True},
            )
            return response_payload
        if commit_state is None:
            logger.critical(
                "Upload commit outcome is uncertain; staged file retained for database safety.",
                extra={
                    "upload_commit_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
            raise

        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass
        except OSError:
            cleanup_db = None
            try:
                if bind is None:
                    raise RuntimeError("Could not obtain database bind for cleanup outbox")
                cleanup_db = Session(bind=bind)
                pending_ids = enqueue_upload_deletions(cleanup_db, [file_path], UPLOAD_DIR)
                cleanup_db.commit()
                retry_pending_file_deletions(cleanup_db, UPLOAD_DIR, pending_ids)
            except Exception as cleanup_error:
                cleanup_rollback_error_type = None
                if cleanup_db is not None:
                    try:
                        cleanup_db.rollback()
                    except Exception as rollback_error:
                        cleanup_rollback_error_type = type(rollback_error).__name__
                logger.critical(
                    "Upload cleanup and cleanup-outbox persistence both failed; orphan may remain.",
                    extra={
                        "upload_cleanup_double_failure": True,
                        "cleanup_error_type": type(cleanup_error).__name__,
                        "cleanup_rollback_error_type": cleanup_rollback_error_type,
                    },
                )
            finally:
                if cleanup_db is not None:
                    try:
                        cleanup_db.close()
                    except Exception as close_error:
                        logger.critical(
                            "Upload cleanup session close failed.",
                            extra={
                                "upload_cleanup_session_close_failure": True,
                                "close_error_type": type(close_error).__name__,
                            },
                        )
        raise

    return response_payload


@router.post("/api/intake/extract-metadata", dependencies=[Depends(require_clinical)])
async def extract_intake_metadata(file: UploadFile = File(...)):
    """
    Extracts intake metadata, laterality, and calibration preview from an ultrasound file
    before committing to a study.
    """
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File quá lớn (> 20MB).")
    if len(contents) < 64:
        raise HTTPException(status_code=400, detail="File rỗng hoặc quá nhỏ (< 64 bytes).")
    if SYNTHETIC_DEMO_MODE and hashlib.sha256(contents).hexdigest() not in SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256:
        raise HTTPException(
            status_code=422,
            detail="Chế độ demo chỉ chấp nhận fixture tổng hợp đã được cấu hình.",
        )

    filename = file.filename or "unknown.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".png", ".jpg", ".jpeg", ".dcm"]:
        raise HTTPException(status_code=400, detail="Định dạng file không hợp lệ. Vui lòng chọn PNG, JPG, JPEG hoặc DICOM (.dcm).")

    if ext == ".dcm":
        try:
            import pydicom

            dicom_header = pydicom.dcmread(BytesIO(contents), stop_before_pixels=True)
        except Exception:
            dicom_header = None
        if dicom_header is not None:
            _preflight_dicom_dimensions(dicom_header)
    else:
        _preflight_raster_dimensions(contents)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        meta = extract_file_metadata(tmp_path, filename)
        decoded = decode_ultrasound_image(tmp_path)
        if decoded is None:
            raise HTTPException(status_code=400, detail="Không thể đọc nội dung file ảnh y tế.")
        calib = get_automatic_calibration(tmp_path, decoded)
        return {
            "filename": filename,
            "metadata": meta,
            "calibration": calib,
        }
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@router.get("/api/images/{image_id}/viewer-source", dependencies=[Depends(require_clinical)])
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


@router.get("/api/images/{image_id}/mask.png", dependencies=[Depends(require_clinical)])
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


@router.get("/api/images/{image_id}/source.png", dependencies=[Depends(require_clinical)])
def export_decoded_source(image_id: str, db: Session = Depends(get_db)):
    """Return the full decoded raster, without CLAHE, letterboxing or viewer filters."""
    record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    decoded = load_decoded_source(record)
    encoded, buffer = cv2.imencode(".png", decoded)
    if not encoded:
        raise HTTPException(status_code=500, detail="Source export failed.")
    return Response(content=buffer.tobytes(), media_type="image/png", headers={
        "X-Image-Coordinate-Space": "decoded-source-image",
        "X-Source-Width": str(decoded.shape[1]), "X-Source-Height": str(decoded.shape[0]),
    })


@router.post("/api/images/{image_id}/measurements", dependencies=[Depends(require_clinical)])
def source_mask_measurements(image_id: str, req: MaskMeasurementsRequest, db: Session = Depends(get_db)):
    """Measure the supplied editable mask in actual source pixels; do not persist it."""
    record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    decoded = load_decoded_source(record)
    return measure_source_mask(
        decoded, req.rle_mask, preprocessor, model_registry.get_primary_adapter().engine,
        get_image_calibration(record),
    )


@router.post("/api/validate-image", response_model=ImageValidationResult)
def validate_image_quality(
    image_id: str,
    lease_token: str | None = Header(None, alias="X-Case-Lease-Token"),
    page_instance_id: str | None = Header(None, alias="X-Case-Page-Instance-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Performs pre-inference Image Quality Assessment (IQA) & Modality Validation.
    Verifies ultrasound format, resolution, blur, saturation, and exposure.
    """
    img_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not img_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế trên hệ thống.")
    if not img_record.study_id:
        raise HTTPException(status_code=409, detail="Ảnh chưa thuộc một ca khảo sát có thể chỉnh sửa.")
    require_active_case_lease(
        db,
        img_record.study_id,
        current_user,
        lease_token,
        page_instance_id,
        allow_reviewed=True,
    )
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
        actor_id=current_user.username,
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
def run_ai_prediction(
    image_id: str,
    pixel_spacing_mm: float | None = None,
    lease_token: str | None = Header(None, alias="X-Case-Lease-Token"),
    page_instance_id: str | None = Header(None, alias="X-Case-Page-Instance-Id"),
    idempotency_key: UUID | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Executes end-to-end preprocessing and manifest-selected model inference via ModelRegistry,
    uncertainty estimation, and automated caliper measurement.
    Rejects unsuitable images with HTTP 422.
    """
    img_record = db.query(ImageModel).filter(ImageModel.id == image_id).first()
    if not img_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi ảnh y tế trên hệ thống.")
    file_path = img_record.raw_path
    filename = img_record.filename
    study_id = img_record.study_id

    if study_id:
        study_status = db.query(StudyModel.status).filter(StudyModel.id == study_id).scalar()
        if (study_status or "").upper() in _FINAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Ca khám đã hoàn tất rà soát hoặc đã khóa, không thể chạy lại dự đoán AI.",
            )

    if not image_id.startswith("sample_"):
        if not study_id:
            raise HTTPException(status_code=409, detail="Ảnh chưa thuộc một ca khảo sát có thể chỉnh sửa.")
        require_active_case_lease(
            db,
            study_id,
            current_user,
            lease_token,
            page_instance_id,
            allow_reviewed=True,
        )

    validate_pixel_spacing(pixel_spacing_mm)
    stored_calibration = get_image_calibration(img_record)
    pixel_spacing = (
        pixel_spacing_mm
        if pixel_spacing_mm is not None
        else stored_calibration["pixel_spacing_mm"]
    )
    calibration_source = (
        "MANUAL" if pixel_spacing_mm is not None
        else stored_calibration["calibration_source"]
    )
    prediction_key_digest = None
    prediction_request_digest = None
    if isinstance(idempotency_key, UUID):
        prediction_key_digest, prediction_request_digest = prediction_idempotency_digests(
            idempotency_key,
            current_user.id,
            {
                "image_id": image_id,
                "source_sha256": img_record.source_content_sha256 or img_record.file_hash,
                "pixel_spacing_mm": pixel_spacing,
                "calibration_source": calibration_source,
            },
        )
        previous_prediction = (
            db.query(PredictionModel)
            .filter(PredictionModel.idempotency_key_digest == prediction_key_digest)
            .first()
        )
        if previous_prediction is not None:
            if previous_prediction.idempotency_request_digest != prediction_request_digest:
                raise HTTPException(
                    status_code=409,
                    detail="Khóa thử lại đã được dùng cho một yêu cầu phân tích ảnh khác.",
                )
            return _stored_prediction_replay_response(previous_prediction, img_record)

    if not model_registry.get_primary_adapter().is_loaded:
        raise HTTPException(status_code=503, detail="Checkpoint mô hình chưa được nạp hoặc không khớp SHA-256 đã chọn.")

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

    pipeline_start = time.perf_counter()
    start_time = datetime.now()

    # 1. Preprocess & IQA
    tensor, padded_gray, transform_params, iqa_report = preprocessor.preprocess_for_inference(img_np)

    # 2. Run Pure Neural Network Inference via ModelRegistry
    scale = float(transform_params.get("scale", 1.0))
    inference_result = model_registry.predict(
        tensor, padded_gray, pixel_spacing_mm=pixel_spacing, scale=scale
    )
    if isinstance(inference_result.get("measurements"), dict):
        inference_result["measurements"]["calibration_source"] = calibration_source

    inference_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    # Encode original 512x512 gray to base64
    _, orig_buffer = cv2.imencode(".png", padded_gray)
    orig_b64 = f"data:image/png;base64,{base64.b64encode(orig_buffer).decode('utf-8')}"

    clean_transform = {
        "scale": float(transform_params.get("scale", 1.0)),
        "pad_w": int(transform_params.get("pad_w", transform_params.get("pad_x", 0))),
        "pad_h": int(transform_params.get("pad_h", transform_params.get("pad_y", 0))),
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

    chk_sum = inference_result.get("provenance", {}).get("model_checksum") or getattr(engine_obj, "model_checksum", None)
    arch_name = inference_result.get("provenance", {}).get("architecture") or getattr(primary_ad, "architecture", "Standard U-Net")
    provenance_payload = {
        "checkpoint_sha256": chk_sum,
        "model_checksum": chk_sum,
        "serving_config_sha256": serving_config_sha256,
        "architecture": arch_name,
        "model_name": arch_name,
        "threshold": float(getattr(engine_obj, "threshold", 0.5)),
        "native_shape": [int(img_np.shape[0]), int(img_np.shape[1])],
        "transform": clean_transform,
        "model_version": inference_result.get("provenance", {}).get("model_version", "unspecified"),
        "pixel_spacing_mm": inference_result.get("provenance", {}).get("pixel_spacing_mm"),
        "calibration_source": calibration_source,
        "created_at": datetime.now(UTC).isoformat(),
    }

    pipeline_duration_ms = (time.perf_counter() - pipeline_start) * 1000.0
    forward_ms = inference_result.get("timings", {}).get("model_forward_ms")
    timings = {
        "model_forward_ms": round(float(forward_ms), 2) if forward_ms is not None else None,
        "server_pipeline_ms": round(float(pipeline_duration_ms), 2),
    }
    response_extras = {
        "iqa": iqa_report,
        "uncertainty": inference_result.get("uncertainty"),
        "quality_gate": inference_result.get("quality_gate"),
        "timings": timings,
        "acoustic_profile": inference_result.get("acoustic_profile"),
        "cdss_classification": inference_result.get("cdss_classification"),
        "ai_diagnosis": None,
        "unified_findings": None,
    }

    prediction_id = None
    # If real DB record, save prediction and update study status
    if not image_id.startswith("sample_"):
        if pixel_spacing_mm is not None:
            img_record.pixel_spacing_mm = pixel_spacing_mm
            img_record.calibration_source = "MANUAL"
        prediction_id = str(uuid.uuid4())
        pred_record = PredictionModel(
            id=prediction_id,
            image_id=image_id,
            model_version=inference_result.get("provenance", {}).get("model_version", "unspecified"),
            inference_time_ms=inference_duration_ms,
            confidence_score=inference_result["confidence_score"],
            iqa_score=iqa_report["iqa_score"],
            raw_mask_rle=inference_result["rle_mask"],
            measurements=inference_result["measurements"],
            provenance_json=provenance_payload,
            uncertainty_map_png=inference_result.get("uncertainty_map_png"),
            idempotency_key_digest=prediction_key_digest,
            idempotency_request_digest=prediction_request_digest,
            response_extras_json=response_extras,
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
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if prediction_key_digest is not None:
                committed_prediction = (
                    db.query(PredictionModel)
                    .filter(PredictionModel.idempotency_key_digest == prediction_key_digest)
                    .first()
                )
                if committed_prediction is not None:
                    if committed_prediction.idempotency_request_digest != prediction_request_digest:
                        raise HTTPException(
                            status_code=409,
                            detail="Khóa thử lại đã được dùng cho một yêu cầu phân tích ảnh khác.",
                        ) from exc
                    return _stored_prediction_replay_response(committed_prediction, img_record)
            raise

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
        "uncertainty_map_base64": (
            "data:image/png;base64,"
            + base64.b64encode(inference_result["uncertainty_map_png"]).decode("ascii")
            if inference_result.get("uncertainty_map_png")
            else None
        ),
        "uncertainty": inference_result.get("uncertainty"),
        "quality_gate": inference_result.get("quality_gate"),
        "provenance": provenance_payload,
        "timings": timings,
        # The deployed checkpoint is segmentation-only. Do not synthesize
        # histology, malignancy risk, or side-specific findings from its mask.
        "ai_diagnosis": None,
        "unified_findings": None,
        "idempotent_replay": False,
    }



@router.post("/api/images/{image_id}/calibrate")
def calibrate_image_spacing(
    image_id: str,
    pixel_spacing_mm: float | None = None,
    distance_mm: float | None = None,
    distance_pixels: float | None = None,
    lease_token: str | None = Header(None, alias="X-Case-Lease-Token"),
    page_instance_id: str | None = Header(None, alias="X-Case-Page-Instance-Id"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
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
    require_active_case_lease(
        db,
        img_record.study_id,
        current_user,
        lease_token,
        page_instance_id,
        allow_reviewed=True,
    )

    # If prediction exists, update measurements with calibrated spacing
    prediction = (
        db.query(PredictionModel)
        .filter(PredictionModel.image_id == image_id)
        .order_by(PredictionModel.created_at.desc())
        .first()
    )
    updated_measurements = None
    updated_provenance = None
    if prediction and prediction.raw_mask_rle:
        prov = dict(prediction.provenance_json) if isinstance(prediction.provenance_json, dict) else {}
        calib_scale = _validated_prediction_letterbox_scale(prov.get("transform"), img_record)
        if calib_scale is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Không thể cập nhật số đo vì provenance letterbox của dự đoán không hợp lệ; "
                    "hãy chạy lại phân tích ảnh trước."
                ),
            )
        engine = model_registry.get_primary_adapter().engine
        mask = engine.rle_to_mask(prediction.raw_mask_rle)
        if mask.shape != (512, 512):
            raise HTTPException(
                status_code=409,
                detail="Không thể cập nhật số đo vì kích thước mặt nạ dự đoán không hợp lệ; hãy chạy lại phân tích ảnh.",
            )
        effective_spacing = validate_pixel_spacing(spacing / calib_scale)
        updated_measurements = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=effective_spacing)
        if updated_measurements.get("calibrated") is not True:
            raise HTTPException(
                status_code=422,
                detail="Tỷ lệ hiệu chuẩn không an toàn để tính lại số đo; không có dữ liệu nào được cập nhật.",
            )
        updated_measurements["calibrated"] = True
        updated_measurements["pixel_spacing_mm"] = spacing
        updated_measurements["calibration_source"] = "MANUAL"

        # AI-09: Synchronize provenance_json and preserve original inference provenance separately
        from datetime import UTC
        calib_history = list(prov.get("calibration_history") or [])
        old_spacing = prov.get("pixel_spacing_mm")
        calib_history.append({
            "calibrated_at": datetime.now(UTC).isoformat(),
            "actor": current_user.username,
            "previous_pixel_spacing_mm": old_spacing,
            "new_pixel_spacing_mm": spacing,
            "calibration_source": "MANUAL",
        })
        if "original_inference_pixel_spacing_mm" not in prov:
            prov["original_inference_pixel_spacing_mm"] = old_spacing
        prov["pixel_spacing_mm"] = spacing
        prov["calibration_source"] = "MANUAL"
        prov["calibration_history"] = calib_history
        prov["last_calibrated_at"] = datetime.now(UTC).isoformat()
        prov["calibrated_by"] = current_user.username
        updated_provenance = prov

    img_record.pixel_spacing_mm = spacing
    img_record.calibration_source = "MANUAL"
    if updated_measurements is not None:
        prediction.measurements = updated_measurements
        prediction.provenance_json = updated_provenance

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



@router.post("/api/v1/inference/interactive-prompt", include_in_schema=False)
def run_interactive_prompt_segmentation(_req: InteractivePromptRequest):
    """Fail closed until a validated, reviewed interactive-segmentation workflow exists."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Interactive prompt segmentation is disabled in this RUO build because no validated model implementation is available."
        ),
    )
