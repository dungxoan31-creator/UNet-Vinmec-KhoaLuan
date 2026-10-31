"""Atomic, expiring edit leases for one clinical study at a time."""

import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.db.database import CaseLeaseModel, StudyModel, UserModel
from backend.services.facility_service import check_facility_access

LEASE_SECONDS = 45
_FINAL_STATUSES = {"REVIEWED", "SIGNED_PRELIM", "APPROVED", "LOCKED"}
_NON_REVIEWED_FINAL_STATUSES = _FINAL_STATUSES - {"REVIEWED"}
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_lease_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _lease_response(token: str, expires_at: datetime) -> dict:
    return {
        "granted": True,
        "lease_token": token,
        "expires_at": expires_at.replace(tzinfo=UTC).isoformat(),
        "lease_seconds": LEASE_SECONDS,
    }


def _deny() -> dict:
    return {"granted": False, "lease_token": None, "expires_at": None, "lease_seconds": LEASE_SECONDS}


def _abort_transaction(db: Session, operation: str):
    """Rollback and close without allowing cleanup failures to replace the operation error."""
    try:
        bind = db.get_bind()
    except Exception:
        bind = None
    rollback_error_type = None
    try:
        db.rollback()
    except Exception as exc:
        rollback_error_type = type(exc).__name__
        logger.critical(
            "Lease transaction rollback failed.",
            extra={
                "lease_rollback_failure": True,
                "lease_operation": operation,
                "rollback_error_type": rollback_error_type,
            },
        )
    try:
        db.close()
    except Exception as exc:
        logger.critical(
            "Lease transaction session close failed.",
            extra={
                "lease_session_close_failure": True,
                "lease_operation": operation,
                "close_error_type": type(exc).__name__,
            },
        )
    return bind, rollback_error_type


def _verify_active_lease(bind, study_id, user_id, tab_id, page_instance_id, token):
    if not token:
        return False
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            lease = (
                verify_db.query(CaseLeaseModel)
                .filter_by(
                    study_id=study_id,
                    owner_user_id=user_id,
                    tab_id=tab_id,
                    page_instance_id=page_instance_id,
                    token_hash=hash_lease_token(token),
                )
                .first()
            )
            if lease is None or lease.expires_at <= _now():
                return False
            return lease.expires_at
    except Exception:
        return None


def _verify_lease_absent(bind, study_id, user_id, page_instance_id, token):
    if bind is None or not token:
        return None
    try:
        with Session(bind=bind) as verify_db:
            lease = (
                verify_db.query(CaseLeaseModel.study_id)
                .filter_by(
                    study_id=study_id,
                    owner_user_id=user_id,
                    page_instance_id=page_instance_id,
                    token_hash=hash_lease_token(token),
                )
                .first()
            )
            return lease is None
    except Exception:
        return None


def require_active_case_lease(
    db: Session,
    study_id: str,
    user: UserModel,
    lease_token: str | None,
    page_instance_id: str | None,
    allow_reviewed: bool = False,
) -> None:
    """Validate and transactionally renew the lease before a clinical write."""
    valid_token = (
        isinstance(lease_token, str)
        and 32 <= len(lease_token) <= 256
        and lease_token.isascii()
        and re.fullmatch(r"[A-Za-z0-9_-]+", lease_token) is not None
    )
    valid_page = (
        isinstance(page_instance_id, str)
        and 16 <= len(page_instance_id) <= 128
        and page_instance_id.isascii()
        and re.fullmatch(r"[A-Za-z0-9_-]+", page_instance_id) is not None
    )
    if not valid_token or not valid_page:
        _abort_transaction(db, "validate")
        raise HTTPException(status_code=423, detail="An active case-edit lease is required.")

    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        _abort_transaction(db, "validate")
        raise HTTPException(status_code=404, detail="Case not found.")
    check_facility_access(user, study.facility_id)
    blocked_statuses = _NON_REVIEWED_FINAL_STATUSES if allow_reviewed else _FINAL_STATUSES
    if (study.status or "").upper() in blocked_statuses:
        _abort_transaction(db, "validate")
        raise HTTPException(status_code=409, detail="Finalized cases are read-only.")

    now = _now()
    expires_at = now + timedelta(seconds=LEASE_SECONDS)
    result = db.execute(
        update(CaseLeaseModel)
        .where(
            CaseLeaseModel.study_id == study_id,
            CaseLeaseModel.owner_user_id == user.id,
            CaseLeaseModel.page_instance_id == page_instance_id,
            CaseLeaseModel.token_hash == hash_lease_token(lease_token),
            CaseLeaseModel.expires_at > now,
        )
        .values(expires_at=expires_at)
    )
    if result.rowcount != 1:
        _abort_transaction(db, "renew")
        raise HTTPException(status_code=423, detail="An active case-edit lease is required.")


def verify_active_case_lease_readonly(
    db: Session,
    study_id: str,
    user: UserModel,
    lease_token: str | None,
    page_instance_id: str | None,
) -> None:
    """Preflight a lease without taking a SQLite write lock during file decoding."""
    valid_token = (
        isinstance(lease_token, str)
        and 32 <= len(lease_token) <= 256
        and lease_token.isascii()
        and re.fullmatch(r"[A-Za-z0-9_-]+", lease_token) is not None
    )
    valid_page = (
        isinstance(page_instance_id, str)
        and 16 <= len(page_instance_id) <= 128
        and page_instance_id.isascii()
        and re.fullmatch(r"[A-Za-z0-9_-]+", page_instance_id) is not None
    )
    if not valid_token or not valid_page:
        raise HTTPException(status_code=423, detail="An active case-edit lease is required.")

    bind = db.get_bind()
    with Session(bind=bind) as read_db:
        study = read_db.query(StudyModel).filter(StudyModel.id == study_id).first()
        if not study:
            raise HTTPException(status_code=404, detail="Case not found.")
        check_facility_access(user, study.facility_id)
        if (study.status or "").upper() in _FINAL_STATUSES:
            raise HTTPException(status_code=409, detail="Finalized cases are read-only.")

        lease = (
            read_db.query(CaseLeaseModel.study_id)
            .filter(
                CaseLeaseModel.study_id == study_id,
                CaseLeaseModel.owner_user_id == user.id,
                CaseLeaseModel.page_instance_id == page_instance_id,
                CaseLeaseModel.token_hash == hash_lease_token(lease_token),
                CaseLeaseModel.expires_at > _now(),
            )
            .first()
        )
        if lease is None:
            raise HTTPException(status_code=423, detail="An active case-edit lease is required.")


def acquire_case_lease(
    db: Session,
    study_id: str,
    user: UserModel,
    tab_id: str,
    page_instance_id: str,
    lease_token: str | None,
) -> dict:
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Case not found.")
    check_facility_access(user, study.facility_id)
    if (study.status or "").upper() in _NON_REVIEWED_FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Finalized cases are read-only.")

    now = _now()
    expires_at = now + timedelta(seconds=LEASE_SECONDS)
    candidate_token = None
    try:
        if lease_token:
            token_hash = hash_lease_token(lease_token)
            candidate_token = lease_token
            renewed = db.execute(
                update(CaseLeaseModel)
                .where(
                    CaseLeaseModel.study_id == study_id,
                    CaseLeaseModel.owner_user_id == user.id,
                    CaseLeaseModel.tab_id == tab_id,
                    CaseLeaseModel.page_instance_id == page_instance_id,
                    CaseLeaseModel.token_hash == token_hash,
                    CaseLeaseModel.expires_at > now,
                )
                .values(expires_at=expires_at)
            )
            if renewed.rowcount == 1:
                db.commit()
                return _lease_response(lease_token, expires_at)
            # A heartbeat is renewal-only. It must not recreate a released or
            # expired lease after a delayed request arrives.
            _abort_transaction(db, "renew")
            return _deny()

        new_token = secrets.token_urlsafe(32)
        candidate_token = new_token
        statement = sqlite_insert(CaseLeaseModel).values(
            study_id=study_id,
            owner_user_id=user.id,
            tab_id=tab_id,
            page_instance_id=page_instance_id,
            token_hash=hash_lease_token(new_token),
            acquired_at=now,
            expires_at=expires_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[CaseLeaseModel.study_id],
            set_={
                "owner_user_id": user.id,
                "tab_id": tab_id,
                "page_instance_id": page_instance_id,
                "token_hash": hash_lease_token(new_token),
                "acquired_at": now,
                "expires_at": expires_at,
            },
            where=CaseLeaseModel.expires_at <= now,
        )
        acquired = db.execute(statement)
        if acquired.rowcount != 1:
            _abort_transaction(db, "acquire")
            return _deny()
        db.commit()
        return _lease_response(new_token, expires_at)
    except OperationalError as exc:
        bind, rollback_error_type = _abort_transaction(db, "acquire")
        persisted_expiry = _verify_active_lease(
            bind, study_id, user.id, tab_id, page_instance_id, candidate_token
        )
        if isinstance(persisted_expiry, datetime):
            logger.critical(
                "Lease commit raised after the active token was persisted; returning verified lease.",
                extra={"lease_commit_error_after_persist": True},
            )
            return _lease_response(candidate_token, persisted_expiry)
        if persisted_expiry is None:
            logger.critical(
                "Lease commit outcome is uncertain.",
                extra={
                    "lease_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        raise HTTPException(status_code=503, detail="Lease storage is busy; retry shortly.") from exc
    except Exception:
        bind, rollback_error_type = _abort_transaction(db, "acquire")
        persisted_expiry = _verify_active_lease(
            bind, study_id, user.id, tab_id, page_instance_id, candidate_token
        )
        if isinstance(persisted_expiry, datetime):
            logger.critical(
                "Lease commit raised after the active token was persisted; returning verified lease.",
                extra={"lease_commit_error_after_persist": True},
            )
            return _lease_response(candidate_token, persisted_expiry)
        if persisted_expiry is None:
            logger.critical(
                "Lease commit outcome is uncertain.",
                extra={
                    "lease_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        raise


def release_case_lease(
    db: Session,
    study_id: str,
    user: UserModel,
    lease_token: str,
    page_instance_id: str,
) -> dict:
    study = db.query(StudyModel).filter(StudyModel.id == study_id).first()
    if study:
        check_facility_access(user, study.facility_id)
    released = False
    try:
        result = db.execute(
            delete(CaseLeaseModel).where(
                CaseLeaseModel.study_id == study_id,
                CaseLeaseModel.owner_user_id == user.id,
                CaseLeaseModel.page_instance_id == page_instance_id,
                CaseLeaseModel.token_hash == hash_lease_token(lease_token),
            )
        )
        released = result.rowcount == 1
        db.commit()
        return {"released": released}
    except OperationalError as exc:
        bind, rollback_error_type = _abort_transaction(db, "release")
        is_released = _verify_lease_absent(
            bind, study_id, user.id, page_instance_id, lease_token
        )
        if is_released is True:
            logger.critical(
                "Lease release commit raised after the requested lease was removed; returning verified result.",
                extra={"lease_release_commit_error_after_persist": True},
            )
            return {"released": released}
        if is_released is None:
            logger.critical(
                "Lease release commit outcome is uncertain.",
                extra={
                    "lease_release_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        raise HTTPException(status_code=503, detail="Lease storage is busy; retry shortly.") from exc
    except Exception:
        bind, rollback_error_type = _abort_transaction(db, "release")
        is_released = _verify_lease_absent(
            bind, study_id, user.id, page_instance_id, lease_token
        )
        if is_released is True:
            logger.critical(
                "Lease release commit raised after the requested lease was removed; returning verified result.",
                extra={"lease_release_commit_error_after_persist": True},
            )
            return {"released": released}
        if is_released is None:
            logger.critical(
                "Lease release commit outcome is uncertain.",
                extra={
                    "lease_release_state_unknown": True,
                    "rollback_error_type": rollback_error_type,
                },
            )
        raise
