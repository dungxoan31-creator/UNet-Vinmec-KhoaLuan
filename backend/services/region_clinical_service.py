"""Persist clinician-controlled RUO measurements and rule assessments per region."""

import base64
import hashlib
import json
import math
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.database import (
    AuditLogModel,
    ImageModel,
    RegionAssignmentBatchModel,
    RegionCaliperEventModel,
    RegionCDSSAssessmentModel,
    ReviewModel,
    StudyModel,
    UserModel,
)
from backend.schemas.schemas import RegionCaliperWriteRequest, RegionCDSSAssessmentRequest
from backend.services.case_lease_service import require_active_case_lease
from backend.services.image_service import get_image_calibration
from backend.services.inference_engine import InferenceEngine
from backend.services.lesion_reconciliation import review_component_candidates
from backend.services.measurement_safety import is_finite_physical_value
from backend.services.region_assignment_service import verified_previous_regions


def _json_hash(value: dict) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _encode_history_cursor(kind: str, values: dict) -> str:
    payload = {"v": 1, "kind": kind, **values}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_history_cursor(cursor: str | None, kind: str) -> dict | None:
    if cursor is None:
        return None
    if not cursor or len(cursor) > 512:
        raise HTTPException(422, "Cursor lịch sử không hợp lệ.")
    try:
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(422, "Cursor lịch sử không hợp lệ.") from None
    if not isinstance(payload, dict) or payload.get("v") != 1 or payload.get("kind") != kind:
        raise HTTPException(422, "Cursor lịch sử không hợp lệ.")
    return payload


def _normalize_cursor_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _parse_cursor_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise HTTPException(422, "Cursor thời gian lịch sử không hợp lệ.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Cursor thời gian lịch sử không hợp lệ.") from None
    return _normalize_cursor_datetime(parsed)


def _calibration_snapshot(image: ImageModel) -> dict:
    calibration = get_image_calibration(image)
    spacing = calibration.get("pixel_spacing_mm")
    source = calibration.get("calibration_source") or "NONE"
    return {
        "pixel_spacing_mm": float(spacing) if spacing is not None else None,
        "calibration_source": source,
        "calibration_hash": _json_hash({
            "image_id": image.id,
            "width": image.width,
            "height": image.height,
            "pixel_spacing_mm": float(spacing) if spacing is not None else None,
            "calibration_source": source,
        }),
    }


def _latest_review(db: Session, image_id: str):
    return (
        db.query(ReviewModel)
        .filter_by(image_id=image_id)
        .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc())
        .first()
    )


def _latest_assignment(db: Session, study_id: str, image_id: str):
    return (
        db.query(RegionAssignmentBatchModel)
        .filter_by(study_id=study_id, image_id=image_id)
        .order_by(RegionAssignmentBatchModel.review_revision.desc(), RegionAssignmentBatchModel.created_at.desc())
        .first()
    )


def _region_context(
    db: Session,
    study_id: str,
    image_id: str,
    assignment_request_id: str,
    review_id: str,
    region_id: str,
    mask_sha256: str,
):
    image = db.query(ImageModel).filter_by(id=image_id, study_id=study_id).first()
    study = db.get(StudyModel, study_id)
    assignment = db.get(RegionAssignmentBatchModel, assignment_request_id)
    if image is None or study is None or assignment is None or assignment.study_id != study_id or assignment.image_id != image_id:
        raise HTTPException(404, "Không tìm thấy ảnh hoặc snapshot vùng trong ca.")
    if assignment.review_id != review_id:
        raise HTTPException(409, "Snapshot vùng không thuộc bản review được chọn.")

    old_regions = verified_previous_regions(db, assignment, image_id)
    if region_id not in old_regions:
        raise HTTPException(404, "Region ID không tồn tại trong snapshot ảnh này.")
    snapshot = assignment.response_json
    if snapshot.get("mask_sha256") != mask_sha256:
        raise HTTPException(409, "Mask hash không khớp snapshot vùng đã xác nhận.")
    candidates = review_component_candidates(
        InferenceEngine.rle_to_mask(
            db.query(ReviewModel).filter_by(id=review_id, image_id=image_id).one().verified_mask_rle
        )
    )
    if candidates.get("mask_sha256") != mask_sha256:
        raise HTTPException(409, "Không thể xác minh mask nguồn của snapshot vùng.")

    latest_review = _latest_review(db, image_id)
    latest_assignment = _latest_assignment(db, study_id, image_id)
    current = bool(
        latest_review is not None
        and latest_review.id == review_id
        and latest_assignment is not None
        and latest_assignment.request_id == assignment.request_id
    )
    return {
        "study": study,
        "image": image,
        "assignment": assignment,
        "region_id": region_id,
        "review_id": review_id,
        "review_revision": assignment.review_revision,
        "mask_sha256": mask_sha256,
        "region_mask": old_regions[region_id],
        "current": current,
        "stale_reason": None if current else "Review hoặc snapshot vùng mới hơn đã được lưu.",
        "calibration": _calibration_snapshot(image),
    }


def _require_current(context):
    if not context["current"]:
        raise HTTPException(409, "Review hoặc snapshot vùng đã thay đổi; tải lại trước khi lưu.")


def _is_latest_caliper_revision(db: Session, event: RegionCaliperEventModel) -> bool:
    latest = (
        db.query(RegionCaliperEventModel)
        .filter_by(
            assignment_request_id=event.assignment_request_id,
            region_id=event.region_id,
            label=event.label,
        )
        .order_by(RegionCaliperEventModel.measurement_revision.desc())
        .first()
    )
    return latest is not None and latest.request_id == event.request_id


def _is_latest_assessment_revision(db: Session, assessment: RegionCDSSAssessmentModel) -> bool:
    latest = (
        db.query(RegionCDSSAssessmentModel)
        .filter_by(
            assignment_request_id=assessment.assignment_request_id,
            region_id=assessment.region_id,
        )
        .order_by(RegionCDSSAssessmentModel.assessment_revision.desc())
        .first()
    )
    return latest is not None and latest.request_id == assessment.request_id


def _caliper_event_json(
    event: RegionCaliperEventModel,
    context: dict | None = None,
    *,
    latest_revision: bool = True,
) -> dict:
    calibration_current = None
    if context is not None:
        calibration_current = event.calibration_hash == context["calibration"]["calibration_hash"]
    current = bool(context and context["current"] and calibration_current and latest_revision)
    return {
        "request_id": event.request_id,
        "assignment_request_id": event.assignment_request_id,
        "region_id": event.region_id,
        "review_id": event.review_id,
        "review_revision": event.review_revision,
        "mask_sha256": event.mask_sha256,
        "label": event.label,
        "measurement_revision": event.measurement_revision,
        "coordinate_space": event.coordinate_space,
        "points": event.points_json,
        "source_dimensions": [event.source_width, event.source_height],
        "diameter_px": event.diameter_px,
        "diameter_mm": event.diameter_mm,
        "pixel_spacing_mm": event.pixel_spacing_mm,
        "calibration_source": event.calibration_source,
        "calibration_current": calibration_current,
        "usable_for_cdss": bool(current and event.diameter_mm is not None),
        "current": current,
        "stale_reason": (
            context["stale_reason"] if context and not context["current"]
            else "Hiệu chuẩn ảnh đã thay đổi; không dùng số đo vật lý này cho CDSS."
            if context and not calibration_current
            else "Đã có phép đo mới hơn cho cùng đường kính; bản này chỉ còn trong lịch sử."
            if context and not latest_revision
            else None
        ),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _assessment_json(
    assessment: RegionCDSSAssessmentModel,
    context: dict,
    latest_caliper_ids: set[str],
    *,
    latest_revision: bool = True,
) -> dict:
    current = bool(
        context["current"]
        and latest_revision
        and assessment.assignment_request_id == context["assignment"].request_id
        and assessment.review_id == context["review_id"]
        and (
            assessment.source_caliper_event_id is None
            or assessment.source_caliper_event_id in latest_caliper_ids
        )
    )
    return {
        "request_id": assessment.request_id,
        "assignment_request_id": assessment.assignment_request_id,
        "region_id": assessment.region_id,
        "review_id": assessment.review_id,
        "review_revision": assessment.review_revision,
        "mask_sha256": assessment.mask_sha256,
        "assessment_revision": assessment.assessment_revision,
        "vision_findings": assessment.vision_findings_json,
        "patient_context": assessment.patient_context_json,
        "source_caliper_event_id": assessment.source_caliper_event_id,
        "source_caliper_revision": assessment.source_caliper_revision,
        "result": assessment.result_json,
        "current": current,
        "stale_reason": None if current else (
            "Đã có assessment mới hơn; bản này chỉ còn trong lịch sử."
            if not latest_revision
            else "Dữ liệu nguồn của assessment đã đổi; không dùng kết quả này như assessment hiện hành."
        ),
        "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
    }


def _latest_usable_d1_ids(db: Session, context: dict) -> set[str]:
    events = (
        db.query(RegionCaliperEventModel)
        .filter_by(
            assignment_request_id=context["assignment"].request_id,
            region_id=context["region_id"],
            label="D1",
        )
        .order_by(RegionCaliperEventModel.measurement_revision.desc())
        .limit(100)
        .all()
    )
    if not events:
        return set()
    latest = events[0]
    return {latest.request_id} if _caliper_event_json(latest, context)["usable_for_cdss"] else set()


def get_region_calipers(
    db: Session,
    study_id: str,
    image_id: str,
    assignment_request_id: str,
    review_id: str,
    region_id: str,
    mask_sha256: str,
    *,
    limit: int = 100,
    cursor: str | None = None,
) -> dict:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise HTTPException(422, "Giới hạn trang lịch sử phải từ 1 đến 100.")
    context = _region_context(db, study_id, image_id, assignment_request_id, review_id, region_id, mask_sha256)
    query = db.query(RegionCaliperEventModel).filter_by(
        assignment_request_id=assignment_request_id, region_id=region_id,
    )
    cursor_values = _decode_history_cursor(cursor, "calipers")
    if cursor_values is not None:
        label = cursor_values.get("label")
        revision = cursor_values.get("revision")
        if label not in {"D1", "D2"} or isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise HTTPException(422, "Cursor lịch sử caliper không hợp lệ.")
        after_label = RegionCaliperEventModel.label > label
        same_label_older_revision = and_(
            RegionCaliperEventModel.label == label,
            RegionCaliperEventModel.measurement_revision < revision,
        )
        query = query.filter(or_(after_label, same_label_older_revision))
    events = (
        query.order_by(
            RegionCaliperEventModel.label.asc(),
            RegionCaliperEventModel.measurement_revision.desc(),
            RegionCaliperEventModel.request_id.desc(),
        )
        .limit(limit + 1)
        .all()
    )
    history_has_more = len(events) > limit
    events = events[:limit]
    latest_by_label = {}
    for label in ("D1", "D2"):
        latest = (
            db.query(RegionCaliperEventModel)
            .filter_by(
                assignment_request_id=assignment_request_id,
                region_id=region_id,
                label=label,
            )
            .order_by(RegionCaliperEventModel.measurement_revision.desc())
            .first()
        )
        if latest is not None:
            latest_by_label[label] = _caliper_event_json(
                latest, context, latest_revision=True,
            )
    latest_request_by_label = {
        label: item["request_id"] for label, item in latest_by_label.items()
    }
    history = []
    for event in events:
        item = _caliper_event_json(
            event,
            context,
            latest_revision=latest_request_by_label.get(event.label) == event.request_id,
        )
        history.append(item)
    next_cursor = None
    if history_has_more and events:
        last = events[-1]
        next_cursor = _encode_history_cursor("calipers", {
            "label": last.label,
            "revision": last.measurement_revision,
        })
    return {
        "study_id": study_id,
        "image_id": image_id,
        "assignment_request_id": assignment_request_id,
        "review_id": review_id,
        "review_revision": context["review_revision"],
        "mask_sha256": mask_sha256,
        "region_id": region_id,
        "current": context["current"],
        "stale_reason": context["stale_reason"],
        "calibration": context["calibration"],
        "measurements": latest_by_label,
        "history": history,
        "history_truncated": history_has_more,
        "history_has_more": history_has_more,
        "history_next_cursor": next_cursor,
    }


def save_region_caliper(
    db: Session,
    study_id: str,
    image_id: str,
    request: RegionCaliperWriteRequest,
    user: UserModel,
) -> dict:
    if user.role != "DOCTOR":
        raise HTTPException(403, "Chỉ bác sĩ được lưu caliper RUO theo vùng.")
    payload = request.model_dump(mode="json", exclude={"lease_token", "page_instance_id"})
    digest = _json_hash({"study_id": study_id, "image_id": image_id, **payload})
    existing = db.get(RegionCaliperEventModel, str(request.request_id))
    if existing is not None:
        if existing.actor_id != user.id or existing.request_hash != digest:
            raise HTTPException(409, "Request ID đã được dùng với nội dung khác.")
        context = _region_context(
            db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
            str(request.region_id), request.mask_sha256,
        )
        return _caliper_event_json(
            existing, context, latest_revision=_is_latest_caliper_revision(db, existing),
        )

    context = _region_context(
        db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
        str(request.region_id), request.mask_sha256,
    )
    _require_current(context)
    require_active_case_lease(
        db, study_id, user, request.lease_token, request.page_instance_id, allow_reviewed=True,
    )
    image = context["image"]
    width, height = int(image.width or 0), int(image.height or 0)
    if width <= 0 or height <= 0 or any(
        x >= width or y >= height for x, y in request.points
    ):
        raise HTTPException(422, "Hai đầu caliper phải nằm trong kích thước ảnh nguồn.")

    # Review components are stored in letterbox-512 coordinates; map the exact
    # decoded-source points back using the same integer resize/padding rule.
    scale = min(512 / width, 512 / height)
    resized_width = int(width * scale)
    resized_height = int(height * scale)
    pad_x = (512 - resized_width) // 2
    pad_y = (512 - resized_height) // 2
    model_points = [
        (pad_x + x * resized_width / width, pad_y + y * resized_height / height)
        for x, y in request.points
    ]
    region_mask = context["region_mask"]
    line_length = math.dist(*model_points)
    sample_count = max(1, math.ceil(line_length))
    for step in range(sample_count + 1):
        fraction = step / sample_count
        x = model_points[0][0] + (model_points[1][0] - model_points[0][0]) * fraction
        y = model_points[0][1] + (model_points[1][1] - model_points[0][1]) * fraction
        pixel_x, pixel_y = math.floor(x), math.floor(y)
        if not (0 <= pixel_x < 512 and 0 <= pixel_y < 512) or not region_mask[pixel_y, pixel_x]:
            raise HTTPException(422, "Caliper phải nằm trọn trong đúng vùng mask đã xác nhận.")

    distance_px = math.dist(request.points[0], request.points[1])
    if not math.isfinite(distance_px) or distance_px <= 0:
        raise HTTPException(422, "Khoảng cách caliper không hợp lệ.")
    calibration = context["calibration"]
    spacing = calibration["pixel_spacing_mm"]
    source = calibration["calibration_source"]
    known_calibration = source in {"DICOM", "MANUAL"} and spacing is not None and spacing > 0
    diameter_mm = round(distance_px * spacing, 3) if known_calibration else None

    latest = (
        db.query(RegionCaliperEventModel)
        .filter_by(
            assignment_request_id=str(request.assignment_request_id),
            region_id=str(request.region_id),
            label=request.label,
        )
        .order_by(RegionCaliperEventModel.measurement_revision.desc())
        .first()
    )
    latest_revision = latest.measurement_revision if latest else 0
    if request.expected_revision != latest_revision:
        committed = db.get(RegionCaliperEventModel, str(request.request_id))
        if committed is not None and committed.actor_id == user.id and committed.request_hash == digest:
            return _caliper_event_json(
                committed, context, latest_revision=_is_latest_caliper_revision(db, committed),
            )
        raise HTTPException(409, "Phiên bản caliper đã thay đổi; tải lại phép đo trước khi sửa.")

    event = RegionCaliperEventModel(
        request_id=str(request.request_id),
        assignment_request_id=str(request.assignment_request_id),
        study_id=study_id,
        image_id=image_id,
        review_id=str(request.review_id),
        region_id=str(request.region_id),
        review_revision=context["review_revision"],
        mask_sha256=request.mask_sha256,
        label=request.label,
        measurement_revision=latest_revision + 1,
        coordinate_space=request.coordinate_space,
        points_json=request.points,
        source_width=width,
        source_height=height,
        diameter_px=round(distance_px, 3),
        diameter_mm=diameter_mm,
        pixel_spacing_mm=spacing if known_calibration else None,
        calibration_source=source if known_calibration else (source if source == "UNKNOWN" else "NONE"),
        calibration_hash=calibration["calibration_hash"],
        actor_id=user.id,
        request_hash=digest,
    )
    db.add(event)
    db.add(AuditLogModel(
        entity_name="region_caliper",
        entity_id=str(request.region_id),
        action_type="SAVE",
        actor_id=user.id,
        details={"study_id": study_id, "image_id": image_id, "label": request.label,
                 "revision": latest_revision + 1, "request_id": str(request.request_id)},
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.get(RegionCaliperEventModel, str(request.request_id))
        if replay is not None and replay.actor_id == user.id and replay.request_hash == digest:
            replay_context = _region_context(
                db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
                str(request.region_id), request.mask_sha256,
            )
            return _caliper_event_json(
                replay, replay_context, latest_revision=_is_latest_caliper_revision(db, replay),
            )
        raise HTTPException(409, "Phép đo đã được cập nhật đồng thời; tải lại trước khi thử lại.") from exc
    db.refresh(event)
    response_context = _region_context(
        db,
        study_id,
        image_id,
        str(request.assignment_request_id),
        str(request.review_id),
        str(request.region_id),
        request.mask_sha256,
    )
    return _caliper_event_json(
        event, response_context, latest_revision=_is_latest_caliper_revision(db, event),
    )


def get_region_assessments(
    db: Session,
    study_id: str,
    image_id: str,
    assignment_request_id: str,
    review_id: str,
    region_id: str,
    mask_sha256: str,
    *,
    limit: int = 100,
    cursor: str | None = None,
) -> dict:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise HTTPException(422, "Giới hạn trang lịch sử phải từ 1 đến 100.")
    context = _region_context(db, study_id, image_id, assignment_request_id, review_id, region_id, mask_sha256)
    # Only the selected assignment can be current. Looking up its latest D1
    # directly avoids a global history cap hiding it behind older assignments.
    latest_ids = _latest_usable_d1_ids(db, context)
    query = db.query(RegionCDSSAssessmentModel).filter_by(
        study_id=study_id, image_id=image_id, region_id=region_id,
    )
    cursor_values = _decode_history_cursor(cursor, "assessments")
    if cursor_values is not None:
        revision = cursor_values.get("revision")
        request_id = cursor_values.get("request_id")
        if (
            isinstance(revision, bool) or not isinstance(revision, int) or revision < 1
            or not isinstance(request_id, str) or not request_id or len(request_id) > 64
        ):
            raise HTTPException(422, "Cursor lịch sử assessment không hợp lệ.")
        created_at = _parse_cursor_datetime(cursor_values.get("created_at"))
        same_revision = RegionCDSSAssessmentModel.assessment_revision == revision
        same_timestamp = RegionCDSSAssessmentModel.created_at == created_at
        query = query.filter(or_(
            RegionCDSSAssessmentModel.assessment_revision < revision,
            and_(same_revision, RegionCDSSAssessmentModel.created_at < created_at),
            and_(same_revision, same_timestamp, RegionCDSSAssessmentModel.request_id < request_id),
        ))
    assessments = (
        query.order_by(
            RegionCDSSAssessmentModel.assessment_revision.desc(),
            RegionCDSSAssessmentModel.created_at.desc(),
            RegionCDSSAssessmentModel.request_id.desc(),
        )
        .limit(limit + 1)
        .all()
    )
    history_has_more = len(assessments) > limit
    assessments = assessments[:limit]
    latest_revision_by_assignment = dict(
        db.query(
            RegionCDSSAssessmentModel.assignment_request_id,
            func.max(RegionCDSSAssessmentModel.assessment_revision),
        )
        .filter_by(study_id=study_id, image_id=image_id, region_id=region_id)
        .group_by(RegionCDSSAssessmentModel.assignment_request_id)
        .all()
    )
    history = [
        _assessment_json(
            row,
            context,
            latest_ids,
            latest_revision=(
                row.assessment_revision == latest_revision_by_assignment.get(row.assignment_request_id)
            ),
        )
        for row in assessments
    ]
    latest_for_assignment = (
        db.query(RegionCDSSAssessmentModel)
        .filter_by(assignment_request_id=assignment_request_id, region_id=region_id)
        .order_by(RegionCDSSAssessmentModel.assessment_revision.desc())
        .first()
    )
    latest_revision = latest_for_assignment.assessment_revision if latest_for_assignment else 0
    latest_candidate = (
        _assessment_json(latest_for_assignment, context, latest_ids, latest_revision=True)
        if latest_for_assignment is not None
        else None
    )
    latest = latest_candidate if latest_candidate and latest_candidate["current"] else None
    next_cursor = None
    if history_has_more and assessments:
        last = assessments[-1]
        next_cursor = _encode_history_cursor("assessments", {
            "revision": last.assessment_revision,
            "created_at": _normalize_cursor_datetime(last.created_at).isoformat(timespec="microseconds"),
            "request_id": last.request_id,
        })
    return {
        "study_id": study_id,
        "image_id": image_id,
        "assignment_request_id": assignment_request_id,
        "review_id": review_id,
        "review_revision": context["review_revision"],
        "mask_sha256": mask_sha256,
        "region_id": region_id,
        "current": context["current"],
        "stale_reason": context["stale_reason"],
        "latest_revision": latest_revision,
        "latest": latest,
        "history": history,
        "history_truncated": history_has_more,
        "history_has_more": history_has_more,
        "history_next_cursor": next_cursor,
    }


def save_region_assessment(
    db: Session,
    study_id: str,
    image_id: str,
    request: RegionCDSSAssessmentRequest,
    user: UserModel,
) -> dict:
    if user.role != "DOCTOR":
        raise HTTPException(403, "Chỉ bác sĩ được lưu assessment RUO theo vùng.")
    payload = request.model_dump(mode="json", exclude={"lease_token", "page_instance_id"})
    digest = _json_hash({"study_id": study_id, "image_id": image_id, **payload})
    existing = db.get(RegionCDSSAssessmentModel, str(request.request_id))
    if existing is not None:
        if existing.actor_id != user.id or existing.request_hash != digest:
            raise HTTPException(409, "Request ID đã được dùng với nội dung khác.")
        context = _region_context(
            db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
            str(request.region_id), request.mask_sha256,
        )
        return {
            **_assessment_json(
                existing,
                context,
                _latest_usable_d1_ids(db, context),
                latest_revision=_is_latest_assessment_revision(db, existing),
            ),
            "study_id": study_id,
            "image_id": image_id,
            "status": "SAVED_RUO",
            "replayed": True,
        }

    context = _region_context(
        db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
        str(request.region_id), request.mask_sha256,
    )
    _require_current(context)
    require_active_case_lease(
        db, study_id, user, request.lease_token, request.page_instance_id, allow_reviewed=True,
    )
    source_caliper = None
    if request.source_caliper_event_id is not None:
        source_caliper = db.get(RegionCaliperEventModel, str(request.source_caliper_event_id))
        if (
            source_caliper is None
            or source_caliper.assignment_request_id != str(request.assignment_request_id)
            or source_caliper.region_id != str(request.region_id)
            or source_caliper.label != "D1"
            or source_caliper.diameter_mm is None
            or source_caliper.calibration_hash != context["calibration"]["calibration_hash"]
        ):
            raise HTTPException(409, "Caliper nguồn đã thay đổi hoặc không có hiệu chuẩn hợp lệ.")
        latest_d1 = (
            db.query(RegionCaliperEventModel)
            .filter_by(
                assignment_request_id=str(request.assignment_request_id),
                region_id=str(request.region_id),
                label="D1",
            )
            .order_by(RegionCaliperEventModel.measurement_revision.desc())
            .first()
        )
        submitted_diameter = request.vision_findings.get("max_diameter_mm")
        if latest_d1 is None or latest_d1.request_id != source_caliper.request_id:
            raise HTTPException(409, "Caliper D1 mới hơn đã được lưu; tải lại và đối chiếu lại assessment.")
        if (
            isinstance(submitted_diameter, bool)
            or not isinstance(submitted_diameter, (int, float))
            or not is_finite_physical_value(submitted_diameter)
            or not math.isclose(float(submitted_diameter), source_caliper.diameter_mm, rel_tol=0, abs_tol=0.001)
        ):
            raise HTTPException(422, "Đường kính trong descriptor phải khớp D1 đã chọn; bỏ nguồn caliper nếu nhập lại thủ công.")

    latest = (
        db.query(RegionCDSSAssessmentModel)
        .filter_by(assignment_request_id=str(request.assignment_request_id), region_id=str(request.region_id))
        .order_by(RegionCDSSAssessmentModel.assessment_revision.desc())
        .first()
    )
    latest_revision = latest.assessment_revision if latest else 0
    if request.expected_assessment_revision != latest_revision:
        committed = db.get(RegionCDSSAssessmentModel, str(request.request_id))
        if committed is not None and committed.actor_id == user.id and committed.request_hash == digest:
            source_ids = set()
            if committed.source_caliper_event_id:
                source_d1 = (
                    db.query(RegionCaliperEventModel)
                    .filter_by(assignment_request_id=str(request.assignment_request_id),
                               region_id=str(request.region_id), label="D1")
                    .order_by(RegionCaliperEventModel.measurement_revision.desc())
                    .first()
                )
                if source_d1 and source_d1.request_id == committed.source_caliper_event_id:
                    source_ids.add(source_d1.request_id)
            return {
                "request_id": committed.request_id,
                "study_id": study_id,
                "image_id": image_id,
                "assignment_request_id": committed.assignment_request_id,
                "region_id": committed.region_id,
                "review_id": committed.review_id,
                "review_revision": committed.review_revision,
                "mask_sha256": committed.mask_sha256,
                "assessment_revision": committed.assessment_revision,
                "vision_findings": committed.vision_findings_json,
                "patient_context": committed.patient_context_json,
                "source_caliper_event_id": committed.source_caliper_event_id,
                "source_caliper_revision": committed.source_caliper_revision,
                "result": committed.result_json,
                "current": _assessment_json(
                    committed,
                    context,
                    source_ids,
                    latest_revision=_is_latest_assessment_revision(db, committed),
                )["current"],
                "status": "SAVED_RUO",
                "replayed": True,
            }
        raise HTTPException(409, "Assessment đã đổi; tải lịch sử mới nhất trước khi lưu.")

    from backend.services.cdss_engine import CDSSReasoningEngine

    result = CDSSReasoningEngine().evaluate_case(
        vision_findings=request.vision_findings,
        patient_context=request.patient_context,
        adnex_inputs=None,
    )
    assessment = RegionCDSSAssessmentModel(
        request_id=str(request.request_id),
        assignment_request_id=str(request.assignment_request_id),
        study_id=study_id,
        image_id=image_id,
        review_id=str(request.review_id),
        region_id=str(request.region_id),
        review_revision=context["review_revision"],
        mask_sha256=request.mask_sha256,
        assessment_revision=latest_revision + 1,
        vision_findings_json=request.vision_findings,
        patient_context_json=request.patient_context,
        source_caliper_event_id=source_caliper.request_id if source_caliper else None,
        source_caliper_revision=source_caliper.measurement_revision if source_caliper else None,
        result_json=result,
        actor_id=user.id,
        request_hash=digest,
    )
    db.add(assessment)
    db.add(AuditLogModel(
        entity_name="region_cdss_assessment",
        entity_id=str(request.region_id),
        action_type="SAVE_RUO_ASSESSMENT",
        actor_id=user.id,
        details={"study_id": study_id, "image_id": image_id, "review_id": str(request.review_id),
                 "assessment_revision": latest_revision + 1, "request_id": str(request.request_id)},
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = db.get(RegionCDSSAssessmentModel, str(request.request_id))
        if replay is not None and replay.actor_id == user.id and replay.request_hash == digest:
            replay_context = _region_context(
                db, study_id, image_id, str(request.assignment_request_id), str(request.review_id),
                str(request.region_id), request.mask_sha256,
            )
            return {
                **_assessment_json(
                    replay,
                    replay_context,
                    _latest_usable_d1_ids(db, replay_context),
                    latest_revision=_is_latest_assessment_revision(db, replay),
                ),
                "study_id": study_id,
                "image_id": image_id,
                "status": "SAVED_RUO",
                "replayed": True,
            }
        raise HTTPException(409, "Assessment đã được cập nhật đồng thời; tải lại trước khi thử lại.") from exc

    response_context = _region_context(
        db,
        study_id,
        image_id,
        str(request.assignment_request_id),
        str(request.review_id),
        str(request.region_id),
        request.mask_sha256,
    )
    return {
        **_assessment_json(
            assessment,
            response_context,
            _latest_usable_d1_ids(db, response_context),
            latest_revision=_is_latest_assessment_revision(db, assessment),
        ),
        "study_id": study_id,
        "image_id": image_id,
        "status": "SAVED_RUO",
        "replayed": False,
    }
