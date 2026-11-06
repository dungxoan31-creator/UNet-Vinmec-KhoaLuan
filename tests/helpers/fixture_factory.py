"""
Shared Fixture Factory for Tests.
Ensures 100% valid relational integrity, foreign key consistency, and tenant isolation.
"""

from datetime import date, datetime, UTC
import os
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

from backend.db.database import (
    FacilityModel,
    UserModel,
    PatientModel,
    StudyModel,
    ImageModel,
    CaseLeaseModel,
    CorrectionRequestModel,
    ReviewModel,
)


def create_test_facility(
    db: Session,
    facility_id: str | None = None,
    name: str = "Test Facility",
    facility_code: str | None = None,
) -> FacilityModel:
    fac_id = facility_id or f"FAC-{uuid.uuid4().hex[:8].upper()}"
    code = facility_code or f"FC-{uuid.uuid4().hex[:6].upper()}"
    facility = db.query(FacilityModel).filter_by(id=fac_id).first()
    if not facility:
        facility = FacilityModel(id=fac_id, name=name, facility_code=code, is_active=True)
        db.add(facility)
        db.commit()
    return facility


def create_test_user(
    db: Session,
    facility_id: str | None = None,
    username: str | None = None,
    role: str = "DOCTOR",
    full_name: str = "Dr. Test User",
    is_global_admin: bool = False,
) -> UserModel:
    usr_id = f"USR-{uuid.uuid4().hex[:8]}"
    uname = username or f"user_{uuid.uuid4().hex[:6]}"

    # If not global admin and no facility specified, ensure default facility exists
    fac_id = facility_id
    if not is_global_admin and not fac_id:
        default_fac = create_test_facility(db, "FAC-DEFAULT-TEST", "Default Facility", "FAC-DEF-TEST")
        fac_id = default_fac.id

    user = db.query(UserModel).filter_by(username=uname).first()
    if not user:
        user = UserModel(
            id=usr_id,
            username=uname,
            role=role,
            full_name=full_name,
            facility_id=fac_id,
            is_active=True,
            must_change_password=False,
            token_version=1,
        )
        if hasattr(user, "is_global_admin"):
            setattr(user, "is_global_admin", is_global_admin)
        db.add(user)
        db.commit()
    return user


def create_test_patient(
    db: Session,
    patient_id: str | None = None,
    anonymized_pid: str | None = None,
) -> PatientModel:
    pat_id = patient_id or f"PAT-{uuid.uuid4().hex[:8]}"
    anon_pid = anonymized_pid or f"ANON-{uuid.uuid4().hex[:6].upper()}"
    patient = db.query(PatientModel).filter_by(id=pat_id).first()
    if not patient:
        patient = PatientModel(id=pat_id, anonymized_pid=anon_pid)
        db.add(patient)
        db.commit()
    return patient


def create_test_study(
    db: Session,
    facility_id: str | None = None,
    patient_id: str | None = None,
    study_id: str | None = None,
    study_code: str | None = None,
    assignee_id: str | None = None,
    status: str = "PENDING",
) -> StudyModel:
    std_id = study_id or str(uuid.uuid4())
    code = study_code or f"STD-{uuid.uuid4().hex[:8].upper()}"
    fac_id = facility_id
    if not fac_id:
        default_fac = create_test_facility(db, "FAC-DEFAULT-TEST")
        fac_id = default_fac.id

    study = StudyModel(
        id=std_id,
        study_code=code,
        study_date=str(date.today()),
        status=status,
        facility_id=fac_id,
        patient_id=patient_id,
        assignee_id=assignee_id,
        ovary_side="UNKNOWN",
        contralateral_status="UNKNOWN",
    )
    db.add(study)
    db.commit()
    return study


def create_test_image(
    db: Session,
    study_id: str,
    image_id: str | None = None,
    filename: str = "ultrasound_test.png",
    raw_path: str | None = None,
) -> ImageModel:
    img_id = image_id or f"IMG-{uuid.uuid4().hex[:8]}"
    img_path = raw_path or f"/tmp/uploads/{img_id}_{filename}"
    img = ImageModel(
        id=img_id,
        study_id=study_id,
        filename=filename,
        raw_path=str(img_path),
        file_hash=f"hash-{uuid.uuid4().hex[:12]}",
        source_content_sha256=f"sha256-{uuid.uuid4().hex[:16]}",
        laterality="R",
    )
    db.add(img)
    db.commit()
    return img


def create_test_case_hierarchy(db: Session, facility_code: str = "FAC-TEST") -> dict:
    """Creates a complete, mutually consistent study-user-facility-patient-image hierarchy."""
    facility = create_test_facility(db, facility_code=facility_code)
    doctor = create_test_user(db, facility_id=facility.id, role="DOCTOR")
    patient = create_test_patient(db)
    study = create_test_study(db, facility_id=facility.id, patient_id=patient.id, assignee_id=doctor.id)
    image = create_test_image(db, study_id=study.id)
    return {
        "facility": facility,
        "doctor": doctor,
        "patient": patient,
        "study": study,
        "image": image,
    }
