"""Persist explicit geometric region confirmations, scoped to an image and review."""
import hashlib
import json
import uuid

import cv2
from fastapi import HTTPException
from pydantic import BaseModel, Field, StrictBool, StrictInt
from sqlalchemy.exc import IntegrityError

from backend.db.database import AuditLogModel, ImageModel, RegionAssignmentBatchModel, ReviewModel, StudyModel
from backend.services.case_lease_service import require_active_case_lease
from backend.services.inference_engine import InferenceEngine
from backend.services.lesion_reconciliation import MAX_TRACKS, propose_component_links, review_component_candidates


class RegionAssignment(BaseModel):
    component_index: StrictInt = Field(ge=1, le=MAX_TRACKS)
    previous_region_id: uuid.UUID | None = None


class RegionAssignmentRequest(BaseModel):
    request_id: uuid.UUID
    expected_revision: StrictInt = Field(ge=0)
    mask_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed: StrictBool
    assignments: list[RegionAssignment] = Field(max_length=MAX_TRACKS)
    retired_region_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_TRACKS)
    lease_token: str | None = None
    page_instance_id: str | None = None


def verified_previous_regions(db, batch, image_id):
    previous_review = db.query(ReviewModel).filter_by(id=batch.review_id, image_id=image_id).first()
    snapshot = batch.response_json
    try:
        if previous_review is None or not isinstance(snapshot, dict):
            raise ValueError("Missing source review or snapshot")
        if (batch.image_id != image_id or snapshot.get("study_id") != batch.study_id
                or snapshot.get("image_id") != image_id or snapshot.get("review_id") != batch.review_id
                or type(snapshot.get("review_revision")) is not int
                or snapshot["review_revision"] != batch.review_revision):
            raise ValueError("Snapshot scope mismatch")
        previous_mask = InferenceEngine.rle_to_mask(previous_review.verified_mask_rle)
        previous = review_component_candidates(previous_mask)
        if (snapshot.get("algorithm") != previous["algorithm"]
                or snapshot.get("mask_sha256") != previous["mask_sha256"]
                or snapshot.get("components") != previous["components"]):
            raise ValueError("Unverifiable snapshot")
        assignments = snapshot["assignments"]
        if not isinstance(assignments, list) or len(assignments) != len(previous["components"]):
            raise ValueError("Incomplete snapshot")
        _count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(previous_mask, connectivity=8)
        old_regions, indices = {}, set()
        for row in assignments:
            index = row["component_index"]
            region_id = str(uuid.UUID(row["region_id"]))
            if type(index) is not int or index in indices or region_id in old_regions:
                raise ValueError("Duplicate component or region")
            indices.add(index)
            old_regions[region_id] = (labels == index).astype("uint8")
        if indices != {item["component_index"] for item in previous["components"]}:
            raise ValueError("Component mismatch")
        return old_regions
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError) as exc:
        raise HTTPException(409, "Không thể xác minh snapshot vùng trước đó; cần rà soát lại.") from exc


def confirm_regions(db, study_id, image_id, review_id, request, user):
    if user.role != "DOCTOR":
        raise HTTPException(403, "Chỉ bác sĩ được xác nhận vùng.")
    content = request.model_dump(mode="json", exclude={"lease_token", "page_instance_id"})
    if not content["retired_region_ids"]:
        content.pop("retired_region_ids")  # Preserve idempotent retries created before this field existed.
    content.update(study_id=study_id, image_id=image_id, review_id=review_id)
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def replay(batch):
        if batch.actor_id != user.id or batch.request_hash != digest:
            raise HTTPException(409, "Request ID đã được sử dụng với nội dung hoặc người dùng khác.")
        return batch.response_json

    def revision_conflict():
        db.rollback()
        committed = db.get(RegionAssignmentBatchModel, str(request.request_id))
        if committed:
            return replay(committed)
        raise HTTPException(409, "Phiên bản rà soát đã thay đổi.")

    existing = db.get(RegionAssignmentBatchModel, str(request.request_id))
    if existing:
        return replay(existing)
    if not request.confirmed:
        raise HTTPException(422, "Cần xác nhận của bác sĩ.")
    image = db.query(ImageModel).filter_by(id=image_id, study_id=study_id).first()
    review = db.query(ReviewModel).filter_by(id=review_id, image_id=image_id).first() if image else None
    if review is None:
        raise HTTPException(404, "Không tìm thấy bản rà soát của ảnh trong ca.")
    require_active_case_lease(db, study_id, user, request.lease_token, request.page_instance_id, allow_reviewed=True)
    study = db.get(StudyModel, study_id)
    if study.review_revision != request.expected_revision:
        return revision_conflict()
    latest_review = (db.query(ReviewModel).filter_by(image_id=image_id)
                     .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc()).first())
    if latest_review.id != review_id:
        raise HTTPException(409, "Bản rà soát của ảnh đã thay đổi.")
    try:
        candidates = review_component_candidates(InferenceEngine.rle_to_mask(review.verified_mask_rle))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(422, "Không thể phân tích mask của bản rà soát.") from exc
    if candidates["mask_sha256"] != request.mask_sha256:
        raise HTTPException(409, "Mask đã thay đổi.")
    indices = [row.component_index for row in request.assignments]
    if len(indices) != len(set(indices)) or set(indices) != {row["component_index"] for row in candidates["components"]}:
        raise HTTPException(422, "Phải xác nhận mỗi vùng đúng một lần.")
    previous = (db.query(RegionAssignmentBatchModel).filter_by(image_id=image_id, study_id=study_id)
                .order_by(RegionAssignmentBatchModel.review_revision.desc()).first())
    selected = [str(row.previous_region_id) for row in request.assignments if row.previous_region_id]
    previous_ids = set(verified_previous_regions(db, previous, image_id)) if previous else set()
    if len(selected) != len(set(selected)) or not set(selected).issubset(previous_ids):
        raise HTTPException(422, "ID vùng trước đó không hợp lệ hoặc bị lặp.")
    retired = [str(region_id) for region_id in request.retired_region_ids]
    if len(retired) != len(set(retired)) or set(retired) != previous_ids - set(selected):
        raise HTTPException(422, "Cần xác nhận rõ từng vùng cũ không còn được liên kết.")
    rows = [{"component_index": row.component_index, "region_id": str(row.previous_region_id or uuid.uuid4())}
            for row in sorted(request.assignments, key=lambda item: item.component_index)]
    updated = db.query(StudyModel).filter_by(id=study_id, review_revision=request.expected_revision).update(
        {StudyModel.review_revision: request.expected_revision + 1}, synchronize_session=False)
    if updated != 1:
        return revision_conflict()
    result = {"study_id": study_id, "image_id": image_id, "review_id": review_id,
              "mask_sha256": candidates["mask_sha256"], "review_revision": request.expected_revision + 1,
              "algorithm": candidates["algorithm"], "components": candidates["components"], "assignments": rows,
              "retired_region_ids": sorted(retired),
              "assignment_request_id": str(request.request_id)}
    db.add(RegionAssignmentBatchModel(request_id=str(request.request_id), study_id=study_id, image_id=image_id,
           review_id=review_id, actor_id=user.id, request_hash=digest, review_revision=result["review_revision"],
           response_json=result))
    db.add(AuditLogModel(entity_name="region_assignment", entity_id=image_id, action_type="CONFIRM",
                         actor_id=user.id, details={"review_id": review_id, "request_id": str(request.request_id)}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(RegionAssignmentBatchModel, str(request.request_id))
        if existing:
            return replay(existing)
        raise
    return result


def region_proposals(db, study_id, image_id, review_id):
    """Compare the latest confirmed snapshot to the latest review; never persist links."""
    image = db.query(ImageModel).filter_by(id=image_id, study_id=study_id).first()
    review = db.query(ReviewModel).filter_by(id=review_id, image_id=image_id).first() if image else None
    if review is None:
        raise HTTPException(404, "Không tìm thấy bản rà soát của ảnh trong ca.")
    latest = (db.query(ReviewModel).filter_by(image_id=image_id)
              .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc()).first())
    if latest.id != review_id:
        raise HTTPException(409, "Bản rà soát của ảnh đã thay đổi.")
    try:
        current_mask = InferenceEngine.rle_to_mask(review.verified_mask_rle)
        current = review_component_candidates(current_mask)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(422, "Không thể phân tích mask của bản rà soát.") from exc
    batch = (db.query(RegionAssignmentBatchModel).filter_by(study_id=study_id, image_id=image_id)
             .order_by(RegionAssignmentBatchModel.review_revision.desc()).first())
    old_regions = verified_previous_regions(db, batch, image_id) if batch else {}
    result = propose_component_links(old_regions, current_mask)
    return {"study_id": study_id, "image_id": image_id, "review_id": review_id,
            "mask_sha256": current["mask_sha256"], "algorithm": current["algorithm"],
            "previous_review_id": batch.review_id if batch else None,
            "previous_revision": batch.review_revision if batch else None,
            "review_revision": db.get(StudyModel, study_id).review_revision, **result}
