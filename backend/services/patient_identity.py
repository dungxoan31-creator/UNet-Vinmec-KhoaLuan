"""Resolve incoming source IDs to stable server-generated patient pseudonyms."""

import uuid

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.core.patient_identity import (
    is_synthetic_patient_id,
    new_synthetic_patient_id,
    normalize_source_patient_id,
    patient_id_digest,
    patient_pid_key_id,
    patient_pid_secret,
)
from backend.db.database import PatientModel


def get_or_create_patient(db: Session, source_patient_id: str, age_bucket: str | None = None) -> PatientModel:
    """Store only a random display ID and keyed digest of the supplied identifier."""
    source_id = normalize_source_patient_id(source_patient_id)
    if is_synthetic_patient_id(source_id):
        existing_synthetic = db.query(PatientModel).filter_by(anonymized_pid=source_id).first()
        if existing_synthetic is not None:
            return existing_synthetic

    secret = patient_pid_secret()
    digest = patient_id_digest(source_id, secret)
    key_id = patient_pid_key_id(secret)
    db.execute(
        sqlite_insert(PatientModel)
        .values(
            id=str(uuid.uuid4()),
            anonymized_pid=new_synthetic_patient_id(),
            source_pid_hmac=digest,
            pid_hmac_key_id=key_id,
            age_bucket=age_bucket or None,
        )
        .on_conflict_do_nothing(index_elements=[PatientModel.source_pid_hmac])
    )
    patient = db.query(PatientModel).filter_by(source_pid_hmac=digest).first()
    if patient is None or patient.pid_hmac_key_id != key_id:
        raise RuntimeError("Could not resolve the patient identity mapping.")
    return patient
