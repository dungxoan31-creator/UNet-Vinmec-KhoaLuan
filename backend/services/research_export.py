"""
Service for generating traceable research export ZIP bundles pinning exact review snapshots.
"""

from datetime import UTC, datetime
import hashlib
import io
import json
import os
import zipfile
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.config import preprocessor
from backend.app.routers.inference import decode_ultrasound_image
from backend.db.database import (
    AuditLogModel,
    ImageModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
)
from backend.services.inference_engine import InferenceEngine


def build_research_bundle(
    db: Session,
    study_id: str,
    review_ids: list[str],
    expected_revision: int,
    actor: UserModel,
) -> bytes:
    # 1. Study existence check
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khảo sát.")

    # 2. Revision guard
    if study.review_revision != expected_revision:
        raise HTTPException(
            status_code=409,
            detail=f"Xung đột phiên bản: máy chủ đang ở bản {study.review_revision}, yêu cầu xuất bản {expected_revision}.",
        )

    # 3. Review validation
    if not review_ids:
        raise HTTPException(status_code=422, detail="Danh sách review_ids rỗng.")

    reviews = db.query(ReviewModel).filter(ReviewModel.id.in_(review_ids)).all()
    if len(reviews) != len(set(review_ids)):
        raise HTTPException(status_code=404, detail="Không tìm thấy đầy đủ các bản rà soát yêu cầu.")

    study_img_ids = {img.id for img in study.images}
    for rev in reviews:
        if rev.image_id not in study_img_ids:
            raise HTTPException(status_code=422, detail="Bản rà soát không thuộc ca khảo sát này.")

    # 4. Construct ZIP archive in-memory
    buf = io.BytesIO()
    images_metadata = []

    image_review_counts = {}
    for r in reviews:
        image_review_counts[r.image_id] = image_review_counts.get(r.image_id, 0) + 1

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rev in reviews:
            image = db.query(ImageModel).filter(ImageModel.id == rev.image_id).first()
            if not image or not image.raw_path or not os.path.isfile(image.raw_path):
                raise HTTPException(status_code=404, detail=f"File ảnh gốc của {rev.image_id} không khả dụng.")

            decoded = decode_ultrasound_image(image.raw_path)
            if decoded is None:
                raise HTTPException(status_code=422, detail=f"Không thể giải mã file ảnh gốc của {rev.image_id}.")
            h, w = decoded.shape[:2]

            if not rev.prediction_id:
                raise HTTPException(status_code=422, detail=f"Bản rà soát {rev.id} thiếu liên kết prediction_id.")

            prediction = db.query(PredictionModel).filter(PredictionModel.id == rev.prediction_id).first()
            if not prediction:
                raise HTTPException(
                    status_code=404, detail=f"Không tìm thấy bản dự đoán {rev.prediction_id} gắn với rà soát."
                )

            # Native-space mask transformations
            _, transform = preprocessor.letterbox_resize(decoded)

            # AI mask in native space
            ai_model_mask = InferenceEngine.rle_to_mask(prediction.raw_mask_rle)
            ai_native_mask = preprocessor.inverse_letterbox_mask(ai_model_mask, transform)
            ai_png_bytes = cv2.imencode(".png", ((ai_native_mask > 0) * 255).astype(np.uint8))[1].tobytes()

            # Reviewed mask in native space
            rev_model_mask = InferenceEngine.rle_to_mask(rev.verified_mask_rle)
            rev_native_mask = preprocessor.inverse_letterbox_mask(rev_model_mask, transform)
            rev_png_bytes = cv2.imencode(".png", ((rev_native_mask > 0) * 255).astype(np.uint8))[1].tobytes()

            # Overlay in native space
            overlay_bgr = decoded.copy() if len(decoded.shape) == 3 else cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGR)
            mask_bool = rev_native_mask > 0
            overlay_bgr[mask_bool] = (
                overlay_bgr[mask_bool].astype(float) * 0.6 + np.array([0, 255, 0], dtype=float) * 0.4
            ).astype(np.uint8)
            contours, _ = cv2.findContours(rev_native_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay_bgr, contours, -1, (0, 255, 0), 2)
            overlay_png_bytes = cv2.imencode(".png", overlay_bgr)[1].tobytes()

            # Compute SHA-256 for each output
            ai_sha256 = hashlib.sha256(ai_png_bytes).hexdigest()
            rev_sha256 = hashlib.sha256(rev_png_bytes).hexdigest()
            overlay_sha256 = hashlib.sha256(overlay_png_bytes).hexdigest()

            # Write PNGs into ZIP under unique folder if multiple reviews for same image
            dir_name = f"{image.id}_{rev.id}" if image_review_counts[image.id] > 1 else str(image.id)
            ai_path = f"{dir_name}/ai_mask.png"
            rev_path = f"{dir_name}/reviewed_mask.png"
            overlay_path = f"{dir_name}/overlay.png"

            zf.writestr(ai_path, ai_png_bytes)
            zf.writestr(rev_path, rev_png_bytes)
            zf.writestr(overlay_path, overlay_png_bytes)

            images_metadata.append({
                "image_id": image.id,
                "laterality": image.laterality,
                "review_id": rev.id,
                "prediction_id": prediction.id,
                "doctor_action": rev.doctor_action,
                "doctor_id": rev.doctor_id,
                "lesion_type": rev.lesion_type,
                "clinical_notes": rev.clinical_notes,
                "measurements": {
                    "max_diameter_mm": rev.max_diameter_mm,
                    "ortho_diameter_mm": rev.ortho_diameter_mm,
                    "total_area_cm2": rev.total_area_cm2,
                },
                "physical_units": "mm" if rev.max_diameter_mm is not None else None,
                "geometry": {
                    "native_shape": [int(h), int(w)],
                },
                "provenance": prediction.provenance_json or {},
                "files": {
                    "ai_mask": {
                        "path": ai_path,
                        "sha256": ai_sha256,
                    },
                    "reviewed_mask": {
                        "path": rev_path,
                        "sha256": rev_sha256,
                    },
                    "overlay": {
                        "path": overlay_path,
                        "sha256": overlay_sha256,
                    },
                },
            })

        # Top-level metadata
        metadata_payload = {
            "schema_version": "1.0",
            "study_id": study.id,
            "study_code": study.study_code,
            "review_revision": study.review_revision,
            "exported_at": datetime.now(UTC).isoformat(),
            "disclaimer": "Kết quả xuất phục vụ nghiên cứu khoa học và kiểm thử thuật toán. Không sử dụng làm kết luận chẩn đoán lâm sàng độc lập.",
            "images": images_metadata,
        }
        zf.writestr("metadata.json", json.dumps(metadata_payload, indent=2, ensure_ascii=False))

    # Audit log (only logged on complete successful build)
    audit = AuditLogModel(
        entity_name="study",
        entity_id=study.id,
        action_type="RESEARCH_EXPORT_ZIP",
        actor_id=actor.username,
        details={
            "study_id": study.id,
            "review_revision": study.review_revision,
            "review_ids": review_ids,
            "image_count": len(images_metadata),
        },
        timestamp=datetime.now(UTC),
    )
    db.add(audit)
    db.commit()

    return buf.getvalue()
