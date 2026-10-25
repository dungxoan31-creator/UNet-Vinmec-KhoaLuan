"""Keyed patient-ID pseudonyms for stable case linkage without storing source IDs."""

import hashlib
import hmac
import os
import re
import uuid

_SYNTHETIC_PID_RE = re.compile(r"^SYN-[0-9A-F]{32}$")
_PATIENT_PID_CONTEXT = b"ovarian-ultrasound:patient-id:v1\0"
_KEY_ID_CONTEXT = b"ovarian-ultrasound:patient-id-key-id:v1"


def patient_pid_secret() -> bytes:
    """Return the dedicated HMAC key; do not reuse the JWT signing secret."""
    value = os.environ.get("APP_PATIENT_PID_HMAC_SECRET", "")
    key = value.encode("utf-8")
    if len(key) < 32:
        raise RuntimeError("APP_PATIENT_PID_HMAC_SECRET must contain at least 32 bytes.")
    return key


def patient_pid_key_id(secret: bytes | None = None) -> str:
    key = secret if secret is not None else patient_pid_secret()
    return hmac.new(key, _KEY_ID_CONTEXT, hashlib.sha256).hexdigest()


def normalize_source_patient_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Source patient ID must be text.")
    normalized = value.strip()
    if not normalized:
        raise ValueError("Source patient ID must not be blank.")
    if len(normalized) > 64:
        raise ValueError("Source patient ID must not exceed 64 characters.")
    return normalized


def patient_id_digest(value: str, secret: bytes | None = None) -> str:
    key = secret if secret is not None else patient_pid_secret()
    source_id = normalize_source_patient_id(value)
    return hmac.new(key, _PATIENT_PID_CONTEXT + source_id.encode("utf-8"), hashlib.sha256).hexdigest()


def new_synthetic_patient_id() -> str:
    return f"SYN-{uuid.uuid4().hex.upper()}"


def is_synthetic_patient_id(value: str | None) -> bool:
    return isinstance(value, str) and _SYNTHETIC_PID_RE.fullmatch(value) is not None
