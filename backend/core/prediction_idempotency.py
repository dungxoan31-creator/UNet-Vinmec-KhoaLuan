"""Keyed, actor-scoped idempotency digests for persisted inference requests."""

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

from backend.core.patient_identity import patient_pid_secret

_PREDICTION_KEY_CONTEXT = b"ovarian-ultrasound:prediction-idempotency:v1\0"
_PREDICTION_REQUEST_CONTEXT = b"ovarian-ultrasound:prediction-request:v1\0"


def prediction_idempotency_digests(key: UUID, actor_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Return a retry-key digest and a digest binding it to an image/calibration snapshot."""
    if not actor_id:
        raise ValueError("Prediction idempotency keys require an authenticated actor.")
    secret = patient_pid_secret()
    actor = actor_id.encode("utf-8")
    key_message = _PREDICTION_KEY_CONTEXT + actor + b"\0" + key.bytes
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    request_message = _PREDICTION_REQUEST_CONTEXT + actor + b"\0" + canonical.encode("utf-8")
    return (
        hmac.new(secret, key_message, hashlib.sha256).hexdigest(),
        hmac.new(secret, request_message, hashlib.sha256).hexdigest(),
    )
