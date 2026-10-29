"""
Service for atomic batch review persistence, revision validation, and idempotency tracking.
"""

import errno
import hashlib
import json
import logging
import math
import os
import stat
import tempfile
import time
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.db.database import (
    ActiveLearningQueueModel,
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
from backend.schemas.schemas import BatchReviewRequest, DoctorReviewRequest
from backend.services.case_lease_service import require_active_case_lease
from backend.services.image_service import decode_ultrasound_image, get_image_calibration
from backend.services.review_validation import validate_review_mask
from backend.services.source_measurements import measure_source_mask

_FINAL_REVIEW_STATUSES = {"SIGNED_PRELIM", "APPROVED", "LOCKED"}

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_ACTIVE_LEARNING_QUEUE_PATH = (
    _PROJECT_ROOT / "metadata" / "active_learning_queue.jsonl"
)


def _resolve_active_learning_queue_path(
    *, project_root: Path | str | None = None, data_dir: Path | str | None = None
) -> Path:
    """Place legacy review exports with runtime data, never in source metadata."""
    root = Path(project_root) if project_root is not None else _PROJECT_ROOT
    configured_data_dir = data_dir if data_dir is not None else os.environ.get("APP_DATA_DIR")
    if configured_data_dir is None:
        runtime_dir = root / "data"
    else:
        runtime_dir = Path(configured_data_dir)
        if not runtime_dir.is_absolute():
            runtime_dir = root / runtime_dir
    return runtime_dir / "active_learning_queue.jsonl"


ACTIVE_LEARNING_QUEUE_PATH = _resolve_active_learning_queue_path()
_LEGACY_QUEUE_LOCK = RLock()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LegacyActiveLearningCleanupResult:
    removed_count: int
    complete: bool


class LegacyActiveLearningCleanupTransaction:
    """Hold queue locks and backups until the caller's database transaction settles."""

    def __init__(self, result, lock_stack, updates):
        self.result = result
        self._lock_stack = lock_stack
        self._updates = updates
        self._closed = False

    @property
    def complete(self):
        return self.result.complete

    def finalize(self):
        if self._closed:
            return True
        cleanup_complete = True
        for update in self._updates:
            for key in ("replacement_path", "backup_path"):
                temporary_path = update.get(key)
                if temporary_path is None:
                    continue
                try:
                    temporary_path.unlink()
                    update[key] = None
                except FileNotFoundError:
                    update[key] = None
                except OSError as exc:
                    cleanup_complete = False
                    logger.critical(
                        "Could not remove active-learning cleanup backup after database commit.",
                        extra={
                            "legacy_queue_cleanup_failure": True,
                            "error_type": type(exc).__name__,
                        },
                    )
        self._close()
        return cleanup_complete

    def rollback(self):
        if self._closed:
            return True
        rollback_complete = True
        for update in reversed(self._updates):
            if not update.get("applied"):
                continue
            backup_path = update.get("backup_path")
            if backup_path is None:
                rollback_complete = False
                continue
            try:
                os.replace(backup_path, update["queue_path"])
                update["backup_path"] = None
                update["applied"] = False
            except OSError as exc:
                rollback_complete = False
                logger.critical(
                    "Could not restore active-learning export after an uncommitted case deletion.",
                    extra={
                        "legacy_queue_cleanup_rollback_failure": True,
                        "error_type": type(exc).__name__,
                    },
                )
        self.result = LegacyActiveLearningCleanupResult(
            removed_count=(
                sum(update["removed"] for update in self._updates if update.get("applied"))
                if not rollback_complete else 0
            ),
            complete=False,
        )
        self._remove_temporary_files(preserve_applied_backups=True)
        self._close()
        return rollback_complete

    def _remove_temporary_files(self, *, preserve_applied_backups):
        for update in self._updates:
            temporary_paths = [update.get("replacement_path")]
            if not (preserve_applied_backups and update.get("applied")):
                temporary_paths.append(update.get("backup_path"))
            for temporary_path in temporary_paths:
                if temporary_path is None:
                    continue
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.error(
                        "Could not remove a temporary active-learning export file.",
                        extra={
                            "legacy_queue_cleanup_failure": True,
                            "error_type": type(exc).__name__,
                        },
                    )

    def _close(self):
        if self._closed:
            return
        self._closed = True
        self._lock_stack.close()


@contextmanager
def _legacy_queue_file_lock(queue_path: Path):
    """Coordinate legacy JSONL append/rewrite operations across worker processes."""
    lock_path = queue_path.with_name(f"{queue_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _LEGACY_QUEUE_LOCK, open(lock_path, "a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            # The byte-range lock works on an empty file; initialize no bytes
            # before acquiring it, so competing processes cannot race the setup.
            deadline = time.monotonic() + 5.0
            while True:
                lock_file.seek(0)
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.025)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _review_diagnosis_overrides(db: Session, review_request: DoctorReviewRequest) -> dict[str, Any]:
    """Capture new or changed clinician descriptors relative to the prior saved review."""
    previous = (
        db.query(ReviewModel)
        .filter(ReviewModel.image_id == review_request.image_id)
        .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc())
        .first()
    )

    def clinical_value(value: Any, *, lesion_type: bool = False) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if lesion_type and normalized.casefold() in {"chưa đánh giá", "unspecified"}:
            return None
        return normalized

    previous_feedback = previous.hitl_feedback if previous and isinstance(previous.hitl_feedback, dict) else {}
    current_values = {
        "lesion_type": clinical_value(review_request.lesion_type, lesion_type=True),
        "orads": clinical_value(review_request.orads or review_request.orads_score),
        "morphology_description": clinical_value(review_request.morphology_description),
    }
    previous_values = {
        "lesion_type": clinical_value(previous.lesion_type, lesion_type=True) if previous else None,
        "orads": clinical_value(
            previous_feedback.get("orads") or previous_feedback.get("orads_score")
            if previous else None
        ),
        "morphology_description": clinical_value(
            previous_feedback.get("morphologyDesc") or previous_feedback.get("morphology_description")
            if previous else None
        ),
    }
    changed = {
        key: value
        for key, value in current_values.items()
        if value != previous_values[key] and (value is not None or previous_values[key] is not None)
    }
    changed.update(getattr(review_request, "clinician_overrides", None) or {})
    return changed


def log_active_learning_sample(
    image_id: str,
    prediction_id: str,
    doctor_action: str,
    verified_mask_rle: dict[str, Any],
    lesion_type: str,
    clinician_overrides: dict[str, Any] | None = None,
    actor_id: str = "UNVERIFIED_REVIEWER",
) -> dict[str, Any]:
    """Write a legacy JSONL export; review persistence uses the transactional DB queue."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "image_id": image_id,
        "prediction_id": prediction_id,
        "doctor_action": doctor_action,
        "lesion_type": lesion_type,
        "clinician_overrides": clinician_overrides or {},
        "verified_mask_rle": verified_mask_rle,
        "actor_id": actor_id,
    }
    queue_path = Path(ACTIVE_LEARNING_QUEUE_PATH)
    with _legacy_queue_file_lock(queue_path):
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    return record


def prepare_legacy_active_learning_cleanup(
    image_ids: list[str],
) -> LegacyActiveLearningCleanupTransaction:
    """Stage JSONL cleanup and retain backups/locks until DB commit or rollback."""
    target_image_ids = set(image_ids)
    if not target_image_ids:
        return LegacyActiveLearningCleanupTransaction(
            LegacyActiveLearningCleanupResult(removed_count=0, complete=True),
            ExitStack(),
            [],
        )

    queue_paths = [
        Path(ACTIVE_LEARNING_QUEUE_PATH),
        Path(_LEGACY_ACTIVE_LEARNING_QUEUE_PATH),
    ]
    unique_paths = []
    seen_paths = set()
    for queue_path in queue_paths:
        normalized_path = os.path.normcase(str(queue_path.resolve(strict=False)))
        if normalized_path not in seen_paths:
            seen_paths.add(normalized_path)
            unique_paths.append(queue_path)

    lock_stack = ExitStack()
    updates = []
    cleanup_complete = True
    try:
        for queue_path in sorted(unique_paths, key=lambda item: os.path.normcase(str(item.resolve(strict=False)))):
            lock_stack.enter_context(_legacy_queue_file_lock(queue_path))

        for queue_path in unique_paths:
            if not _active_learning_queue_file_exists(queue_path):
                continue
            original_bytes = queue_path.read_bytes()
            kept_lines = []
            removed = 0
            malformed_records = False
            for line in original_bytes.splitlines(keepends=True):
                if not line.strip():
                    kept_lines.append(line)
                    continue
                try:
                    record = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    malformed_records = True
                    kept_lines.append(line)
                    continue
                if (
                    not isinstance(record, dict)
                    or not isinstance(record.get("image_id"), str)
                    or not record["image_id"].strip()
                ):
                    malformed_records = True
                    kept_lines.append(line)
                    continue
                if record["image_id"] in target_image_ids:
                    removed += 1
                else:
                    kept_lines.append(line)

            if malformed_records:
                cleanup_complete = False
                logger.error(
                    "Cannot safely prune active-learning export with unidentified rows.",
                    extra={
                        "legacy_queue_cleanup_failure": True,
                        "error_type": "UnidentifiedQueueRow",
                    },
                )
            elif removed:
                updates.append({
                    "queue_path": queue_path,
                    "original_bytes": original_bytes,
                    "replacement_bytes": b"".join(kept_lines),
                    "removed": removed,
                    "replacement_path": None,
                    "backup_path": None,
                    "applied": False,
                })

        if cleanup_complete:
            for update in updates:
                for key, contents, suffix in (
                    ("replacement_path", update["replacement_bytes"], ".tmp"),
                    ("backup_path", update["original_bytes"], ".bak"),
                ):
                    descriptor, temporary_name = tempfile.mkstemp(
                        prefix=f"{update['queue_path'].name}.",
                        suffix=suffix,
                        dir=update["queue_path"].parent,
                    )
                    update[key] = Path(temporary_name)
                    with os.fdopen(descriptor, "wb") as temporary_file:
                        temporary_file.write(contents)
                        temporary_file.flush()
                        os.fsync(temporary_file.fileno())
            try:
                for update in updates:
                    os.replace(update["replacement_path"], update["queue_path"])
                    update["replacement_path"] = None
                    update["applied"] = True
            except OSError as exc:
                cleanup_complete = False
                logger.error(
                    "Could not atomically prune all active-learning exports.",
                    extra={
                        "legacy_queue_cleanup_failure": True,
                        "error_type": type(exc).__name__,
                    },
                )
    except OSError as exc:
        cleanup_complete = False
        logger.error(
            "Could not prepare active-learning export cleanup.",
            extra={"legacy_queue_cleanup_failure": True, "error_type": type(exc).__name__},
        )

    result = LegacyActiveLearningCleanupResult(
        removed_count=sum(update["removed"] for update in updates) if cleanup_complete else 0,
        complete=cleanup_complete,
    )
    return LegacyActiveLearningCleanupTransaction(result, lock_stack, updates)


def remove_legacy_active_learning_samples(
    image_ids: list[str],
) -> LegacyActiveLearningCleanupResult:
    """Remove samples immediately, rolling back every export if any file fails."""
    transaction = prepare_legacy_active_learning_cleanup(image_ids)
    if not transaction.complete:
        transaction.rollback()
        return transaction.result
    if not transaction.finalize():
        return LegacyActiveLearningCleanupResult(
            removed_count=transaction.result.removed_count,
            complete=False,
        )
    return transaction.result


def _active_learning_queue_file_exists(queue_path: Path) -> bool:
    try:
        queue_stat = os.stat(queue_path)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(queue_stat.st_mode):
        raise OSError(errno.EINVAL, "Active-learning queue path is not a regular file")
    return True



def compute_request_hash(request: BatchReviewRequest) -> str:
    reviews_data = []
    for r in request.reviews:
        fb = r.hitl_feedback.model_dump() if r.hitl_feedback else {}
        orads_val = getattr(r, "orads", None) or getattr(r, "orads_score", None)
        morph_desc = getattr(r, "morphology_description", None)
        if orads_val:
            fb["orads"] = orads_val
            fb["orads_score"] = orads_val
        if morph_desc:
            fb["morphology_description"] = morph_desc
            fb["morphologyDesc"] = morph_desc

        reviews_data.append({
            "image_id": r.image_id,
            "prediction_id": r.prediction_id,
            "doctor_action": r.doctor_action,
            "verified_mask_rle": r.verified_mask_rle,
            "manual_calipers": [item.model_dump() for item in r.manual_calipers],
            "clinical_notes": r.clinical_notes,
            "lesion_type": r.lesion_type,
            "orads": orads_val,
            "morphology_description": morph_desc,
            "time_spent_seconds": r.time_spent_seconds,
            "clinician_overrides": getattr(r, "clinician_overrides", None),
            "hitl_feedback": fb if fb else None,
        })
    reviews_data.sort(key=lambda x: x["image_id"])
    canonical = {
        "study_id": request.study_id,
        "expected_revision": request.expected_revision,
        "hitl_session_id": getattr(request, "hitl_session_id", None),
        "reviews": reviews_data,
    }
    raw = json.dumps(canonical, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _claim_hitl_session_for_review(db: Session, sess: HITLSessionModel, review_batch_id: str) -> None:
    rows_updated = (
        db.query(HITLSessionModel)
        .filter(
            HITLSessionModel.id == sess.id,
            HITLSessionModel.status.notin_(("COMPLETED", "ABORTED")),
            HITLSessionModel.review_batch_id.is_(None),
        )
        .update(
            {
                HITLSessionModel.review_batch_id: review_batch_id,
                HITLSessionModel.status: "INCOMPLETE",
            },
            synchronize_session=False,
        )
    )
    if rows_updated == 0:
        raise HTTPException(status_code=409, detail="HITL session changed or was linked by another request.")
    db.refresh(sess, attribute_names=["status", "review_batch_id"])


def persist_single_review(
    db: Session,
    review_req: DoctorReviewRequest,
    user: UserModel,
    *,
    inference_engine,
    image_preprocessor,
) -> dict[str, Any]:
    """Adapt the single-review contract to the same atomic persistence service."""
    if review_req.expected_revision is None:
        raise HTTPException(status_code=422, detail="Yêu cầu cung cấp expected_revision cho phiên rà soát.")
    if not review_req.request_id:
        raise HTTPException(status_code=422, detail="Yêu cầu cung cấp request_id cho phiên rà soát.")

    study_id = review_req.study_id
    if not study_id:
        image = db.query(ImageModel).filter(ImageModel.id == review_req.image_id).first()
        if not image:
            raise HTTPException(status_code=404, detail="Không tìm thấy ảnh y tế tương ứng.")
        study_id = image.study_id

    batch_request = BatchReviewRequest(
        study_id=study_id,
        expected_revision=review_req.expected_revision,
        request_id=review_req.request_id,
        reviews=[review_req],
        lease_token=review_req.lease_token,
        page_instance_id=review_req.page_instance_id,
    )
    result = persist_review_batch(
        db,
        batch_request,
        user,
        allow_partial=True,
        inference_engine=inference_engine,
        image_preprocessor=image_preprocessor,
    )
    first_review = result["reviews"][0]
    return {
        "review_id": first_review["review_id"],
        "image_id": first_review["image_id"],
        "status": "SUCCESS",
        "message": "Đã lưu mask rà soát và nhật ký thao tác.",
        "is_ground_truth": False,
        "reviewed_at": first_review.get("reviewed_at"),
        "reviewer_id": user.username,
    }


def persist_review_batch(
    db: Session,
    request: BatchReviewRequest,
    user: UserModel,
    allow_partial: bool = False,
    *,
    inference_engine,
    image_preprocessor,
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
    if study.status in _FINAL_REVIEW_STATUSES:
        raise HTTPException(status_code=409, detail="Ca đã ký hoặc khóa, không thể thay đổi rà soát.")

    require_active_case_lease(
        db,
        request.study_id,
        user,
        request.lease_token,
        request.page_instance_id,
        allow_reviewed=True,
    )

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

    if hitl_sess and hitl_sess.status in {"COMPLETED", "ABORTED"}:
        raise HTTPException(status_code=409, detail="A terminal HITL session cannot be linked to a new review batch.")
    if hitl_sess and hitl_sess.review_batch_id:
        raise HTTPException(status_code=409, detail="A HITL session can be linked to only one review batch.")

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
        study_lateralities = {img.laterality for img in study.images}
        if None in study_lateralities or len(study_lateralities) > 1:
            raise HTTPException(status_code=422, detail="Không thể xác nhận hai bên cho ca có vị trí buồng trứng không xác định.")

    if not allow_partial and set(image_ids) != set(study_images):
        raise HTTPException(status_code=422, detail="Cần rà soát từng ảnh của ca trước khi xác nhận toàn bộ khảo sát.")

    if study.ovary_side == "BOTH" and not allow_partial:
        reviewed_lateralities = {study_images[r.image_id].laterality for r in request.reviews}
        if not {"L", "R"}.issubset(reviewed_lateralities):
            raise HTTPException(status_code=422, detail="Ca hai bên yêu cầu rà soát đầy đủ cả hai ảnh (trái và phải).")

    # 6. Predictions & Mask Validation
    engine_inst = inference_engine
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
        source_width = img_rec.width or 512
        source_height = img_rec.height or 512
        for caliper in r.manual_calipers:
            if any(
                x >= source_width or y >= source_height
                for x, y in caliper.points
            ):
                raise HTTPException(status_code=422, detail="Caliper points must lie within the source image.")
        validated_items.append((r, img_rec, pred))

    # 7. Atomic Execution
    try:
        now_utc = datetime.now(UTC)
        review_summaries = []

        for r, img_rec, pred in validated_items:
            calibration = get_image_calibration(img_rec)
            decoded = decode_ultrasound_image(img_rec.raw_path) if (img_rec.raw_path and os.path.isfile(img_rec.raw_path)) else None
            if decoded is not None:
                meas = measure_source_mask(
                    decoded,
                    r.verified_mask_rle,
                    image_preprocessor,
                    engine_inst,
                    calibration,
                )
            else:
                meas = {"max_diameter_mm": None, "ortho_diameter_mm": None, "total_area_cm2": None}

            feedback = r.hitl_feedback.model_dump() if r.hitl_feedback is not None else {}
            # Snapshot only server-derived measurement context with the reviewed mask.
            # Older reviews lacking this field remain explicitly unknown.
            feedback["measurement_context"] = {
                "version": 1,
                "status": "AVAILABLE" if meas.get("measurement_method") else "UNAVAILABLE",
                "warning": meas.get("warning"),
                "exclusion_reason": meas.get("exclusion_reason"),
                "measurement_method": meas.get("measurement_method"),
                "diameter_reference": meas.get("diameter_reference"),
                "calibration_source": calibration["calibration_source"],
            }
            manual_measurements = {}
            if r.manual_calipers:
                for caliper in r.manual_calipers:
                    (x1, y1), (x2, y2) = caliper.points
                    distance_px = math.dist((x1, y1), (x2, y2))
                    spacing = calibration["pixel_spacing_mm"]
                    distance_mm = distance_px * spacing if spacing is not None else None
                    manual_measurements[caliper.label] = {
                        "points": [list(caliper.points[0]), list(caliper.points[1])],
                        "diameter_px": round(distance_px, 2),
                        "diameter_mm": round(distance_mm, 2) if distance_mm is not None else None,
                        "calibrated": distance_mm is not None,
                        "calibration_source": calibration["calibration_source"] if distance_mm is not None else "NONE",
                    }
                feedback["manual_measurements"] = manual_measurements
                feedback["manual_calipers"] = [item.model_dump() for item in r.manual_calipers]
            orads_val = getattr(r, "orads", None) or getattr(r, "orads_score", None)
            morph_desc = getattr(r, "morphology_description", None)
            if orads_val:
                feedback["orads"] = orads_val
                feedback["orads_score"] = orads_val
            if morph_desc:
                feedback["morphologyDesc"] = morph_desc
                feedback["morphology_description"] = morph_desc
            clinician_overrides = _review_diagnosis_overrides(db, r)
            if clinician_overrides:
                feedback["clinician_overrides"] = clinician_overrides
            review_id = str(uuid.uuid4())

            review_record = ReviewModel(
                id=review_id,
                image_id=r.image_id,
                prediction_id=r.prediction_id,
                doctor_id=user.username,
                doctor_action=r.doctor_action,
                verified_mask_rle=r.verified_mask_rle,
                max_diameter_mm=(manual_measurements.get("D1", {}).get("diameter_mm")
                                 if "D1" in manual_measurements else meas["max_diameter_mm"]),
                ortho_diameter_mm=(manual_measurements.get("D2", {}).get("diameter_mm")
                                   if "D2" in manual_measurements else meas["ortho_diameter_mm"]),
                total_area_cm2=meas["total_area_cm2"],
                lesion_type=r.lesion_type,
                clinical_notes=r.clinical_notes,
                time_spent_seconds=r.time_spent_seconds,
                hitl_feedback=feedback if feedback else None,
                is_official_ground_truth=False,
                created_at=now_utc,
            )
            db.add(review_record)
            # The queue row has a database FK to this review; flush the parent
            # before inserting its child while keeping both in the same transaction.
            db.flush()
            has_diag_override = bool(clinician_overrides)
            if r.doctor_action == "MODIFIED" or has_diag_override:
                db.add(
                    ActiveLearningQueueModel(
                        review_id=review_id,
                        study_id=study.id,
                        image_id=r.image_id,
                        prediction_id=r.prediction_id,
                        sample={
                            "timestamp": now_utc.isoformat(),
                            "study_id": study.id,
                            "image_id": r.image_id,
                            "prediction_id": r.prediction_id,
                            "doctor_action": r.doctor_action,
                            "lesion_type": r.lesion_type,
                            "clinician_overrides": clinician_overrides,
                            "verified_mask_rle": r.verified_mask_rle,
                            "actor_id": user.username,
                        },
                        created_at=now_utc,
                    )
                )

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
                    "hitl_feedback": feedback if feedback else None,
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

        new_revision = request.expected_revision + 1

        submitted_ids = {r.image_id for r in request.reviews}
        reviewed_ids = {img.id for img in study.images if img.reviews} | submitted_ids
        all_images_reviewed = bool(study_images) and set(study_images).issubset(reviewed_ids)
        reviewed_lateralities = {
            img.laterality for img in study.images if img.id in reviewed_ids
        }
        sides_complete = study.ovary_side != "BOTH" or {"L", "R"}.issubset(reviewed_lateralities)
        new_status = "REVIEWED" if all_images_reviewed and sides_complete else "PARTIALLY_REVIEWED"

        # Atomic conditional update claiming the expected revision
        rows_updated = db.query(StudyModel).filter(
            StudyModel.id == study.id,
            StudyModel.review_revision == request.expected_revision,
            StudyModel.status.notin_(_FINAL_REVIEW_STATUSES),
        ).update(
            {
                StudyModel.review_revision: new_revision,
                StudyModel.status: new_status,
            },
            synchronize_session=False,
        )

        if rows_updated == 0:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Xung đột phiên bản rà soát: ca đã được chỉnh sửa bởi phiên khác (kỳ vọng bản {request.expected_revision}).",
            )

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
        db.flush()

        if hitl_sess:
            _claim_hitl_session_for_review(db, hitl_sess, batch_record.id)

            session_tasks = (
                db.query(HITLEventModel.task_id, HITLEventModel.image_id)
                .filter(HITLEventModel.session_id == hitl_sess.id)
                .distinct()
                .all()
            )
            for t_id, img_id in session_tasks:
                prior_confirms = (
                    db.query(func.count(HITLEventModel.id))
                    .filter(
                        HITLEventModel.session_id == hitl_sess.id,
                        HITLEventModel.task_id == t_id,
                        HITLEventModel.seq <= 0,
                    )
                    .scalar()
                    or 0
                )
                ev = HITLEventModel(
                    id=str(uuid.uuid4()),
                    event_id=str(uuid.uuid4()),
                    session_id=hitl_sess.id,
                    task_id=t_id,
                    image_id=img_id,
                    seq=-prior_confirms,
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
    except HTTPException:
        db.rollback()
        raise
    except (IntegrityError, OperationalError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Xung đột phiên bản rà soát hoặc xung đột khóa dữ liệu đồng thời.",
        ) from exc
    except Exception:
        db.rollback()
        raise
