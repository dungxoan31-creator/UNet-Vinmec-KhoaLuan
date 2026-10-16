"""
Authenticated HITL session and event ingestion endpoints (Task 12).
"""

from datetime import UTC, datetime
import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from backend.app.routers.auth import get_current_user
from backend.db.database import (
    HITLEventModel,
    HITLSessionModel,
    ReviewBatchModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import (
    HITLEventBatch,
    HITLSessionRequest,
    HITLSessionResponse,
)

router = APIRouter(prefix="/api/hitl", tags=["HITL Telemetry & Sessions"])


@router.post("/sessions", response_model=HITLSessionResponse)
def create_hitl_session(
    req: HITLSessionRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    study = db.query(StudyModel).filter(StudyModel.id == req.study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca khảo sát.")

    session_id = str(uuid.uuid4())
    now_utc = datetime.now(UTC)

    sess = HITLSessionModel(
        id=session_id,
        study_id=req.study_id,
        actor_id=current_user.username,
        participant_code=req.participant_code,
        participant_role=req.participant_role,
        data_origin=req.data_origin,
        status="IN_PROGRESS",
        created_at=now_utc,
    )
    db.add(sess)
    db.commit()

    return {
        "id": sess.id,
        "study_id": sess.study_id,
        "actor_id": sess.actor_id,
        "participant_code": sess.participant_code,
        "participant_role": sess.participant_role,
        "data_origin": sess.data_origin,
        "status": sess.status,
        "created_at": sess.created_at.isoformat(),
        "completed_at": None,
        "review_batch_id": None,
    }


@router.post("/sessions/{session_id}/events")
def append_hitl_events(
    session_id: str,
    batch: HITLEventBatch,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    sess = db.query(HITLSessionModel).filter(HITLSessionModel.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên HITL.")

    # Only owner or admin can append events
    if sess.actor_id != current_user.username and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Chỉ người tạo phiên mới có thể ghi nhận sự kiện.")

    # Event count boundary check: max 10,000 events per session
    existing_count = db.query(HITLEventModel).filter(HITLEventModel.session_id == session_id).count()
    if existing_count + len(batch.events) > 10000:
        raise HTTPException(status_code=422, detail="Vượt quá giới hạn 10.000 sự kiện cho một phiên HITL.")

    study_img_ids = {img.id for img in sess.study.images}
    accepted_count = 0
    duplicate_count = 0
    now_utc = datetime.now(UTC)

    for event in batch.events:
        # Check image membership
        if event.image_id not in study_img_ids:
            raise HTTPException(status_code=422, detail=f"Ảnh {event.image_id} không thuộc ca khảo sát của phiên này.")

        payload_bytes = json.dumps(event.payload or {}, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Check event_id idempotency
        existing_ev = db.query(HITLEventModel).filter(HITLEventModel.event_id == event.event_id).first()
        if existing_ev:
            if existing_ev.session_id != session_id or existing_ev.payload_hash != payload_hash:
                raise HTTPException(status_code=409, detail=f"Xung đột event_id {event.event_id} với payload khác.")
            duplicate_count += 1
            continue

        # Check (session_id, task_id, seq) uniqueness
        existing_seq = (
            db.query(HITLEventModel)
            .filter(
                HITLEventModel.session_id == session_id,
                HITLEventModel.task_id == event.task_id,
                HITLEventModel.seq == event.seq,
            )
            .first()
        )
        if existing_seq and existing_seq.event_id != event.event_id:
            raise HTTPException(status_code=409, detail=f"Xung đột sequence {event.seq} của task {event.task_id}.")

        ev = HITLEventModel(
            id=str(uuid.uuid4()),
            event_id=event.event_id,
            session_id=session_id,
            task_id=event.task_id,
            image_id=event.image_id,
            prediction_id=event.prediction_id,
            seq=event.seq,
            event_type=event.event_type,
            client_utc=event.client_utc,
            elapsed_ms=event.elapsed_ms,
            session_elapsed_ms=event.session_elapsed_ms,
            payload_hash=payload_hash,
            payload=event.payload,
            actor_id=current_user.username,
            received_at=now_utc,
        )
        db.add(ev)
        accepted_count += 1

    # Check session completion criteria
    if sess.review_batch_id:
        batch_rec = db.query(ReviewBatchModel).filter(ReviewBatchModel.id == sess.review_batch_id).first()
        if batch_rec:
            # Query all distinct task_ids in session
            all_tasks = (
                db.query(HITLEventModel.task_id)
                .filter(HITLEventModel.session_id == session_id)
                .distinct()
                .all()
            )
            task_ids = {t[0] for t in all_tasks}

            # Check matching CONFIRM_ACK events for all tasks
            ack_events = (
                db.query(HITLEventModel)
                .filter(
                    HITLEventModel.session_id == session_id,
                    HITLEventModel.event_type == "CONFIRM_ACK",
                )
                .all()
            )
            ack_task_ids = {
                a.task_id
                for a in ack_events
                if a.payload and a.payload.get("batch_request_id") == batch_rec.request_id
            }

            # Include incoming events in batch
            for item in batch.events:
                if (
                    item.event_type == "CONFIRM_ACK"
                    and item.payload
                    and item.payload.get("batch_request_id") == batch_rec.request_id
                ):
                    ack_task_ids.add(item.task_id)

            if task_ids and task_ids.issubset(ack_task_ids):
                sess.status = "COMPLETED"
                sess.completed_at = now_utc

    db.commit()
    return {
        "status": "SUCCESS",
        "accepted_count": accepted_count,
        "duplicate_count": duplicate_count,
    }


@router.get("/sessions/{session_id}", response_model=HITLSessionResponse)
def get_hitl_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    sess = db.query(HITLSessionModel).filter(HITLSessionModel.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên HITL.")

    if sess.actor_id != current_user.username and current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Chỉ người tạo phiên mới có thể xem thông tin phiên.")

    status = sess.status
    if sess.review_batch_id and status != "COMPLETED":
        status = "INCOMPLETE"

    return {
        "id": sess.id,
        "study_id": sess.study_id,
        "actor_id": sess.actor_id,
        "participant_code": sess.participant_code,
        "participant_role": sess.participant_role,
        "data_origin": sess.data_origin,
        "status": status,
        "created_at": sess.created_at.isoformat(),
        "completed_at": sess.completed_at.isoformat() if sess.completed_at else None,
        "review_batch_id": sess.review_batch_id,
    }
