"""Keyed, actor-scoped idempotency digests for image upload retries."""

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

from backend.core.patient_identity import patient_pid_secret

_UPLOAD_KEY_CONTEXT = b"ovarian-ultrasound:image-upload-idempotency:v1\0"
_UPLOAD_REQUEST_CONTEXT = b"ovarian-ultrasound:image-upload-request:v1\0"


def upload_idempotency_digests(key: UUID, actor_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Return a unique retry-key digest and a digest binding it to one upload request."""
    if not actor_id:
        raise ValueError("Upload idempotency keys require an authenticated actor.")
    secret = patient_pid_secret()
    actor = actor_id.encode("utf-8")
    key_message = _UPLOAD_KEY_CONTEXT + actor + b"\0" + key.bytes
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    request_message = _UPLOAD_REQUEST_CONTEXT + actor + b"\0" + canonical.encode("utf-8")
    return (
        hmac.new(secret, key_message, hashlib.sha256).hexdigest(),
        hmac.new(secret, request_message, hashlib.sha256).hexdigest(),
    )
