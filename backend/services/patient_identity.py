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


def get_or_create_patient(
    db: Session,
    source_patient_id: str,
    age_bucket: str | None = None,
    *,
    facility_id: str,
) -> PatientModel:
    """Store only a random display ID and keyed digest of the supplied identifier."""
    facility_id = str(facility_id or "").strip()
    if not facility_id:
        raise ValueError("A facility is required to resolve a patient identity.")
    source_id = normalize_source_patient_id(source_patient_id)
    if is_synthetic_patient_id(source_id):
        existing_synthetic = db.query(PatientModel).filter_by(anonymized_pid=source_id, facility_id=facility_id).first()
        if existing_synthetic is not None:
            return existing_synthetic

    secret = patient_pid_secret()
    digest = patient_id_digest(source_id, secret, facility_id=facility_id)
    key_id = patient_pid_key_id(secret)
    patient = db.query(PatientModel).filter_by(facility_id=facility_id, source_pid_hmac=digest).first()
    if patient is not None:
        if patient.pid_hmac_key_id != key_id:
            raise RuntimeError("Could not resolve the patient identity mapping.")
        return patient

    legacy_digest = patient_id_digest(source_id, secret)
    patient = db.query(PatientModel).filter_by(
        facility_id=facility_id,
        legacy_source_pid_hmac=legacy_digest,
    ).first()
    if patient is not None:
        if patient.pid_hmac_key_id != key_id:
            raise RuntimeError("Could not resolve the legacy patient identity mapping.")
        patient.source_pid_hmac = digest
        patient.pid_hmac_scope_version = 1
        patient.age_bucket = age_bucket or patient.age_bucket
        db.flush()
        return patient

    db.execute(
        sqlite_insert(PatientModel)
        .values(
            id=str(uuid.uuid4()),
            anonymized_pid=new_synthetic_patient_id(),
            source_pid_hmac=digest,
            legacy_source_pid_hmac=None,
            pid_hmac_key_id=key_id,
            pid_hmac_scope_version=1,
            facility_id=facility_id,
            age_bucket=age_bucket or None,
        )
        .on_conflict_do_nothing(index_elements=[PatientModel.source_pid_hmac])
    )
    patient = db.query(PatientModel).filter_by(facility_id=facility_id, source_pid_hmac=digest).first()
    if patient is None or patient.pid_hmac_key_id != key_id:
        raise RuntimeError("Could not resolve the patient identity mapping.")
    return patient
