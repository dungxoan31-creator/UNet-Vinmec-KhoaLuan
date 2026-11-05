"""Shared test fixture factory for multi-tenant and relational integrity testing.

Provides consistent factory methods to create Facility, User, Patient, Study,
Image, Prediction, Lease, and Correction entities with valid foreign keys and
proper tenant isolation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Any
from sqlalchemy.orm import Session

from backend.db.database import (
    FacilityModel,
    UserModel,
    PatientModel,
    StudyModel,
    ImageModel,
    PredictionModel,
    ReviewModel,
    CaseLeaseModel,
    AuditLogModel,
)
from backend.services.case_lease_service import acquire_case_lease


def ensure_test_facility(
    db: Session,
    facility_id: str = "FAC-DEFAULT-TEST",
    facility_code: str = "FAC-DEF-TEST",
    name: str = "Default Test Facility",
    is_active: bool = True,
) -> FacilityModel:
    """Ensure a default test facility exists in the given database session."""
    fac = db.query(FacilityModel).filter_by(id=facility_id).first()
    if not fac:
        fac = FacilityModel(
            id=facility_id,
            facility_code=facility_code,
            name=name,
            is_active=is_active,
        )
        db.add(fac)
        db.flush()
    return fac


def create_user(
    db: Session,
    username: str = "test-doctor",
    role: str = "DOCTOR",
    facility_id: str | None = "FAC-DEFAULT-TEST",
    is_global_admin: bool = False,
    is_active: bool = True,
    full_name: str = "Test User",
    user_id: str | None = None,
) -> UserModel:
    """Create or update a test user with correct tenant facility assignment."""
    if facility_id:
        ensure_test_facility(db, facility_id=facility_id)

    user = db.query(UserModel).filter_by(username=username).first()
    if not user:
        user = UserModel(
            id=user_id or str(uuid.uuid4()),
            username=username,
            full_name=full_name,
            role=role,
            facility_id=facility_id,
            is_global_admin=is_global_admin,
            is_active=is_active,
        )
        db.add(user)
    else:
        user.role = role
        user.facility_id = facility_id
        user.is_global_admin = is_global_admin
        user.is_active = is_active
    db.flush()
    return user


def create_patient(
    db: Session,
    patient_id: str | None = None,
    anonymized_pid: str | None = None,
    age_bucket: str | None = "30-39",
) -> PatientModel:
    """Create a test patient with valid anonymized PID."""
    pid = anonymized_pid or f"TEST_PID_{uuid.uuid4().hex[:8]}"
    patient = PatientModel(
        id=patient_id or str(uuid.uuid4()),
        anonymized_pid=pid,
        age_bucket=age_bucket,
    )
    db.add(patient)
    db.flush()
    return patient


def create_study(
    db: Session,
    patient: PatientModel | None = None,
    facility_id: str = "FAC-DEFAULT-TEST",
    study_id: str | None = None,
    study_code: str | None = None,
    study_date: str = "2026-10-28",
    status: str = "ANALYZED",
    ovary_side: str = "BOTH",
    review_revision: int = 0,
) -> StudyModel:
    """Create a test study bound to a valid facility and patient."""
    ensure_test_facility(db, facility_id=facility_id)
    if patient is None:
        patient = create_patient(db)

    study = StudyModel(
        id=study_id or str(uuid.uuid4()),
        patient_id=patient.id,
        study_code=study_code or f"STUDY_{uuid.uuid4().hex[:8].upper()}",
        study_date=study_date,
        status=status,
        ovary_side=ovary_side,
        review_revision=review_revision,
        facility_id=facility_id,
    )
    db.add(study)
    db.flush()
    return study


def create_image(
    db: Session,
    study: StudyModel,
    image_id: str | None = None,
    filename: str = "test_image.png",
    laterality: str = "L",
    raw_path: str = "test_image.png",
    width: int = 512,
    height: int = 512,
    pixel_spacing_mm: float = 0.1,
) -> ImageModel:
    """Create an image record attached to a study."""
    image = ImageModel(
        id=image_id or str(uuid.uuid4()),
        study_id=study.id,
        filename=filename,
        laterality=laterality,
        raw_path=raw_path,
        width=width,
        height=height,
        pixel_spacing_mm=pixel_spacing_mm,
    )
    db.add(image)
    db.flush()
    return image


def create_prediction(
    db: Session,
    image: ImageModel,
    prediction_id: str | None = None,
    model_version: str = "AttentionUNet-v1.2",
    raw_mask_rle: dict | None = None,
    measurements: dict | None = None,
) -> PredictionModel:
    """Create a prediction record attached to an image."""
    rle = raw_mask_rle or {"shape": [512, 512], "first_val": 0, "counts": [262144]}
    meas = measurements or {}
    pred = PredictionModel(
        id=prediction_id or str(uuid.uuid4()),
        image_id=image.id,
        model_version=model_version,
        raw_mask_rle=rle,
        measurements=meas,
    )
    db.add(pred)
    db.flush()
    return pred


def create_lease(
    db: Session,
    study: StudyModel,
    user: UserModel,
    tab_id: str | None = None,
    page_instance_id: str | None = None,
) -> dict[str, Any]:
    """Acquire an active case lease for a study under a specific user."""
    tid = tab_id or f"tab-{uuid.uuid4().hex[:8]}"
    pid = page_instance_id or f"page-{uuid.uuid4().hex[:8]}"
    return acquire_case_lease(db, study.id, user, tid, pid, None)
