"""Keyed, user-scoped idempotency keys for case intake retries."""

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

from backend.core.patient_identity import patient_pid_secret

_CASE_CREATE_CONTEXT = b"ovarian-ultrasound:case-create-idempotency:v1\0"
_CASE_CREATE_PAYLOAD_CONTEXT = b"ovarian-ultrasound:case-create-payload:v1\0"


def case_create_idempotency_digest(key: UUID, actor_id: str) -> str:
    """Return a stable digest without persisting the caller's raw retry key."""
    if not actor_id:
        raise ValueError("Case idempotency keys require an authenticated actor.")
    message = _CASE_CREATE_CONTEXT + actor_id.encode("utf-8") + b"\0" + key.bytes
    return hmac.new(patient_pid_secret(), message, hashlib.sha256).hexdigest()


def case_create_payload_digest(payload: dict[str, Any], actor_id: str) -> str:
    """Bind a retry key to one canonical intake payload without storing PHI."""
    if not actor_id:
        raise ValueError("Case idempotency payloads require an authenticated actor.")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    message = _CASE_CREATE_PAYLOAD_CONTEXT + actor_id.encode("utf-8") + b"\0" + canonical.encode("utf-8")
    return hmac.new(patient_pid_secret(), message, hashlib.sha256).hexdigest()
