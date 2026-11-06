"""Safe, retryable cleanup of uploaded files after durable database changes."""

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.db.database import PendingFileDeletionModel


def enqueue_upload_deletions(db: Session, raw_paths: list[str], upload_root: str | Path) -> list[str]:
    """Add in-root uploads to the same transaction as their owning case deletion."""
    root = Path(upload_root).resolve()
    deletion_ids = []
    for raw_path in raw_paths:
        if not raw_path:
            continue
        source = Path(raw_path)
        parent = source.parent.resolve()
        if not parent.is_relative_to(root) or source.name.startswith("sample_"):
            continue
        candidate = parent / source.name
        deletion_id = str(uuid.uuid4())
        db.add(
            PendingFileDeletionModel(
                id=deletion_id,
                relative_path=candidate.relative_to(root).as_posix(),
            )
        )
        deletion_ids.append(deletion_id)
    return deletion_ids


def _resolve_pending_path(relative_path: str, upload_root: str | Path) -> Path | None:
    if not relative_path:
        return None
    root = Path(upload_root).resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    source = root / relative
    parent = source.parent.resolve()
    if not parent.is_relative_to(root) or source.name.startswith("sample_"):
        return None
    return parent / source.name


def retry_pending_file_deletions(
    db: Session,
    upload_root: str | Path,
    deletion_ids: list[str] | None = None,
) -> bool:
    """Delete queued uploads idempotently; return whether any requested work remains."""
    query = db.query(PendingFileDeletionModel).order_by(PendingFileDeletionModel.created_at)
    if deletion_ids is not None:
        if not deletion_ids:
            return False
        query = query.filter(PendingFileDeletionModel.id.in_(deletion_ids))

    completed_ids = []
    for pending in query.all():
        path = _resolve_pending_path(pending.relative_path, upload_root)
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except (OSError, RuntimeError):
            continue
        completed_ids.append(pending.id)

    if completed_ids:
        for pending_id in completed_ids:
            db.query(PendingFileDeletionModel).filter(
                PendingFileDeletionModel.id == pending_id
            ).delete(synchronize_session=False)
        try:
            db.commit()
        except Exception:
            # The unlink is idempotent; leaving the durable row allows a later retry.
            db.rollback()
            return True

    remaining = db.query(PendingFileDeletionModel)
    if deletion_ids is not None:
        remaining = remaining.filter(PendingFileDeletionModel.id.in_(deletion_ids))
    return remaining.first() is not None
