"""
Database Engine & ORM Models for Ovarian Ultrasound AI System (SQLAlchemy + SQLite).
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    func,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.core.hitl_event_types import HITL_EVENT_TYPES
from backend.core.hitl_session_domains import (
    HITL_SESSION_DATA_ORIGINS,
    HITL_SESSION_ROLES,
    HITL_SESSION_STATUSES,
)
from backend.core.study_domains import (
    CONTRALATERAL_STATUSES,
    STUDY_OVARY_SIDES,
    STUDY_STATUSES,
)


def _sql_string_values(values: frozenset[str]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in sorted(values))


_HITL_EVENT_TYPE_SQL = _sql_string_values(HITL_EVENT_TYPES)
_HITL_SESSION_ROLE_SQL = _sql_string_values(HITL_SESSION_ROLES)
_HITL_SESSION_DATA_ORIGIN_SQL = _sql_string_values(HITL_SESSION_DATA_ORIGINS)
_HITL_SESSION_STATUS_SQL = _sql_string_values(HITL_SESSION_STATUSES)
_STUDY_STATUS_SQL = _sql_string_values(STUDY_STATUSES)
_STUDY_OVARY_SIDE_SQL = _sql_string_values(STUDY_OVARY_SIDES)
_CONTRALATERAL_STATUS_SQL = _sql_string_values(CONTRALATERAL_STATUSES)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


_env_db_path = os.environ.get("APP_DB_PATH")
if _env_db_path:
    DB_PATH = os.path.abspath(_env_db_path) if os.path.isabs(_env_db_path) else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", _env_db_path))
else:
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ovarian_ai.db"))

_env_database_url = os.environ.get("DATABASE_URL")
if _env_database_url:
    if _env_database_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        if _env_database_url.startswith("postgres://"):
            DATABASE_URL = "postgresql+psycopg://" + _env_database_url[len("postgres://"):]
        elif _env_database_url.startswith("postgresql://"):
            DATABASE_URL = "postgresql+psycopg://" + _env_database_url[len("postgresql://"):]
        else:
            DATABASE_URL = _env_database_url
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    elif _env_database_url.startswith("sqlite://"):
        DATABASE_URL = _env_database_url
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})
    else:
        raise ValueError(
            f"Unsupported database scheme in DATABASE_URL: {_env_database_url}. "
            "Supported schemes: postgresql://, postgresql+psycopg://, sqlite://."
        )
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def connect_sqlite(path: str, **kwargs) -> sqlite3.Connection:
    """Open a raw SQLite connection with the same foreign-key policy as ORM connections."""
    connection = sqlite3.connect(path, **kwargs)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def generate_visit_code() -> str:
    """Generate high-entropy unique visit code: VIS-YYYYMMDD-XXXXXXXX"""
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()
    return f"VIS-{date_part}-{random_part}"


class FacilityModel(Base):
    __tablename__ = "facilities"

    id = Column(String(36), primary_key=True)
    facility_code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    users = relationship("UserModel", back_populates="facility")
    visits = relationship("VisitModel", back_populates="facility")


class VisitModel(Base):
    __tablename__ = "visits"

    id = Column(String(36), primary_key=True)
    visit_code = Column(String(32), unique=True, nullable=False, index=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    facility = relationship("FacilityModel", back_populates="visits")
    patient = relationship("PatientModel")
    studies = relationship("StudyModel", back_populates="visit")


class PatientModel(Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("uq_patient_facility_source_pid_hmac", "facility_id", "source_pid_hmac", unique=True),
        Index("uq_patient_facility_legacy_source_pid_hmac", "facility_id", "legacy_source_pid_hmac", unique=True),
    )

    id = Column(String(36), primary_key=True)
    anonymized_pid = Column(String(64), unique=True, nullable=False)
    source_pid_hmac = Column(String(64), unique=True, nullable=True)
    legacy_source_pid_hmac = Column(String(64), nullable=True)
    pid_hmac_key_id = Column(String(64), nullable=True)
    pid_hmac_scope_version = Column(Integer, default=0, server_default="0", nullable=False)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True, index=True)
    age_bucket = Column(String(20), nullable=True)
    menopausal_status = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    studies = relationship("StudyModel", back_populates="patient", cascade="all, delete-orphan")


class PatientDirectoryModel(Base):
    """Facility-scoped intake directory with only the minimum review-facing demographics."""

    __tablename__ = "patient_directory"

    id = Column(String(36), primary_key=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    birth_year = Column(Integer, nullable=True)
    version = Column(Integer, default=1, server_default="1", nullable=False)
    is_active = Column(Boolean, default=True, server_default="true", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    studies = relationship("StudyModel", back_populates="directory_patient")


class StudyModel(Base):
    __tablename__ = "studies"
    __table_args__ = (
        Index("uq_studies_idempotency_key_digest", "idempotency_key_digest", unique=True),
        Index("uq_studies_visit_no", "visit_no", unique=True),
        Index("ix_studies_facility_status_created", "facility_id", "status", "created_at"),
        CheckConstraint(
            f"status IS NOT NULL AND status IN ({_STUDY_STATUS_SQL})",
            name="ck_studies_status",
        ),
        CheckConstraint(
            f"ovary_side IS NOT NULL AND ovary_side IN ({_STUDY_OVARY_SIDE_SQL})",
            name="ck_studies_ovary_side",
        ),
        CheckConstraint(
            f"contralateral_status IS NOT NULL AND contralateral_status IN ({_CONTRALATERAL_STATUS_SQL})",
            name="ck_studies_contralateral_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    patient_directory_id = Column(String(36), ForeignKey("patient_directory.id"), nullable=True, index=True)
    patient_age = Column(String(20), nullable=True)
    study_code = Column(String(64), nullable=True)
    visit_no = Column(String(6), nullable=True)
    idempotency_key_digest = Column(String(64), nullable=True)
    idempotency_request_digest = Column(String(64), nullable=True)
    study_date = Column(String(20), nullable=False)
    status = Column(String(30), default="PENDING", nullable=False)
    device_vendor = Column(String(50), nullable=True)
    probe_type = Column(String(50), nullable=True)
    ovary_side = Column(String(10), default="UNKNOWN", nullable=False)
    contralateral_status = Column(String(30), default="UNKNOWN", nullable=False)
    clinical_indication = Column(Text, nullable=True)
    review_revision = Column(Integer, default=0, nullable=False)
    visit_id = Column(String(36), ForeignKey("visits.id"), nullable=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)
    assignee_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    patient = relationship("PatientModel", back_populates="studies")
    directory_patient = relationship("PatientDirectoryModel", back_populates="studies")
    visit = relationship("VisitModel", back_populates="studies")
    facility = relationship("FacilityModel")
    images = relationship("ImageModel", back_populates="study", cascade="all, delete-orphan")


class VisitNumberSequenceModel(Base):
    __tablename__ = "visit_number_sequences"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_visit_number_sequence_singleton"),
        CheckConstraint(
            "next_value BETWEEN 1 AND 1000000",
            name="ck_visit_number_sequence_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    next_value = Column(Integer, nullable=False)


class VisitNumberCapacityExceeded(RuntimeError):
    """Raised after all six-digit Visit No values have been issued."""


def _allocate_visit_no_from_connection(connection) -> str:
    sequence = connection.execute(
        text("SELECT next_value FROM visit_number_sequences WHERE id = 1")
    ).scalar_one_or_none()
    if sequence is None:
        current_max = connection.execute(
            text("SELECT COALESCE(MAX(CAST(visit_no AS INTEGER)), 0) FROM studies")
        ).scalar_one()
        connection.execute(
            text("INSERT OR IGNORE INTO visit_number_sequences (id, next_value) VALUES (1, :next_value)"),
            {"next_value": int(current_max or 0) + 1},
        )

    issued = connection.execute(
        text(
            "UPDATE visit_number_sequences "
            "SET next_value = next_value + 1 "
            "WHERE id = 1 AND next_value <= 999999 "
            "RETURNING next_value - 1"
        )
    ).scalar_one_or_none()
    if issued is None:
        raise VisitNumberCapacityExceeded("The six-digit Visit No range has been exhausted.")
    return f"{int(issued):06d}"


@event.listens_for(StudyModel, "before_insert")
def _assign_server_visit_no(_mapper, connection, target) -> None:
    if target.visit_no is not None:
        raise ValueError("Visit No is generated by the server and cannot be supplied by callers.")
    target.visit_no = _allocate_visit_no_from_connection(connection)


class CaseLeaseModel(Base):
    __tablename__ = "case_leases"

    study_id = Column(String(36), ForeignKey("studies.id", ondelete="CASCADE"), primary_key=True)
    owner_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tab_id = Column(String(128), nullable=False)
    page_instance_id = Column(String(128), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    acquired_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class ImageModel(Base):
    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint(
            "laterality IS NULL OR laterality IN ('R', 'L')",
            name="ck_images_laterality_lr",
        ),
        UniqueConstraint("study_id", "file_hash", name="uq_study_file_hash"),
        UniqueConstraint("study_id", "source_content_sha256", name="uq_study_source_content_sha256"),
        Index("uq_images_upload_idempotency_key_digest", "upload_idempotency_key_digest", unique=True),
    )

    id = Column(String(36), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    laterality = Column(String(1), nullable=True)  # R/L; null for legacy single-image studies
    raw_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)
    source_content_sha256 = Column(String(64), nullable=True)
    upload_idempotency_key_digest = Column(String(64), nullable=True)
    upload_idempotency_request_digest = Column(String(64), nullable=True)
    width = Column(Integer, default=512)
    height = Column(Integer, default=512)
    pixel_spacing_mm = Column(Float, nullable=True)
    calibration_source = Column(String(16), nullable=True)
    is_empty_mask = Column(Boolean, default=False)
    dataset_split = Column(String(20), default="TRAIN")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    study = relationship("StudyModel", back_populates="images")
    predictions = relationship("PredictionModel", back_populates="image", cascade="all, delete-orphan")
    reviews = relationship("ReviewModel", back_populates="image", cascade="all, delete-orphan")


class PendingFileDeletionModel(Base):
    """Durable retry record for uploaded files whose case was deleted."""

    __tablename__ = "pending_file_deletions"

    id = Column(String(36), primary_key=True)
    relative_path = Column(String(500), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class PredictionModel(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("id", "image_id", name="uq_prediction_id_image"),
        Index("uq_predictions_idempotency_key_digest", "idempotency_key_digest", unique=True),
    )

    id = Column(String(36), primary_key=True)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False)
    model_version = Column(String(100), nullable=True)
    inference_time_ms = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)
    iqa_score = Column(Float, nullable=True)
    raw_mask_rle = Column(JSON, nullable=False)
    measurements = Column(JSON, nullable=False)
    provenance_json = Column(JSON, nullable=True)
    uncertainty_map_png = Column(LargeBinary, nullable=True)
    idempotency_key_digest = Column(String(64), nullable=True)
    idempotency_request_digest = Column(String(64), nullable=True)
    response_extras_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    image = relationship("ImageModel", back_populates="predictions")


class ReviewModel(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "doctor_action IS NOT NULL AND doctor_action IN ('ACCEPTED_RAW', 'MODIFIED', 'REJECTED_ALL')",
            name="ck_reviews_doctor_action",
        ),
        ForeignKeyConstraint(
            ["prediction_id", "image_id"],
            ["predictions.id", "predictions.image_id"],
            name="fk_reviews_prediction_image",
        ),
    )

    id = Column(String(36), primary_key=True)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False)
    prediction_id = Column(String(36), nullable=True)
    doctor_id = Column(String(64), default="UNVERIFIED_REVIEWER")
    doctor_action = Column(String(30), default="ACCEPTED_RAW", nullable=True)
    verified_mask_rle = Column(JSON, nullable=False)
    max_diameter_mm = Column(Float().evaluates_none(), default=0.0)
    ortho_diameter_mm = Column(Float().evaluates_none(), default=0.0)
    total_area_cm2 = Column(Float().evaluates_none(), default=0.0)
    lesion_type = Column(String(100), default="UNSPECIFIED")
    clinical_notes = Column(Text, default="")
    time_spent_seconds = Column(Integer, nullable=True, default=None)
    hitl_feedback = Column(JSON, nullable=True)
    is_official_ground_truth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    image = relationship("ImageModel", back_populates="reviews")


class ActiveLearningQueueModel(Base):
    """Transactional queue entries derived from clinician-confirmed reviews."""

    __tablename__ = "active_learning_queue"
    __table_args__ = (
        Index("ix_active_learning_queue_study_id", "study_id"),
        Index("ix_active_learning_queue_image_id", "image_id"),
    )

    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    prediction_id = Column(String(36), nullable=True)
    sample = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_name = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)
    action_type = Column(String(50), nullable=False)
    actor_id = Column(String(64), nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_email_lower",
            func.lower("email"),
            unique=True,
            sqlite_where=text("email IS NOT NULL"),
        ),
    )

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(254), nullable=True)
    email_verified = Column(Boolean, default=False, server_default="0", nullable=False)
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default="DOCTOR")  # DOCTOR, ADMIN
    department = Column(String(100), default="Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa")
    title = Column(String(50), default="")
    hospital = Column(String(100), default="Chưa cấu hình")
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)
    is_global_admin = Column(Boolean, default=False, server_default="0", nullable=False)
    avatar = Column(String(255), default="doctor_avatar.png")
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False, nullable=False)
    token_version = Column(Integer, default=1)
    tokens_revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    facility = relationship("FacilityModel", back_populates="users")


class EmailVerificationChallengeModel(Base):
    __tablename__ = "email_verification_challenges"
    __table_args__ = (UniqueConstraint("email", name="uq_email_verification_challenge_email"),)

    id = Column(String(36), primary_key=True)
    email = Column(String(254), nullable=False)
    code_digest = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    resend_count = Column(Integer, default=0, nullable=False)
    last_sent_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class ConsumedPasswordResetTokenModel(Base):
    __tablename__ = "consumed_password_reset_tokens"

    token_id = Column(String(64), primary_key=True)
    username = Column(String(50), nullable=False)
    consumed_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class AuthRateLimitModel(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (Index("ix_auth_rate_limits_window", "window_started_at"),)

    subject_key = Column(String(64), primary_key=True)
    window_started_at = Column(DateTime, nullable=False)
    attempt_count = Column(Integer, nullable=False)


class RegionAssignmentBatchModel(Base):
    """Immutable clinician-confirmed geometric identities for one review."""
    __tablename__ = "region_assignment_batches"

    request_id = Column(String(36), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    review_revision = Column(Integer, nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class RegionCaliperEventModel(Base):
    """Immutable, image-source-coordinate caliper measurements for one confirmed region snapshot."""

    __tablename__ = "region_caliper_events"
    __table_args__ = (
        CheckConstraint("label IN ('D1', 'D2')", name="ck_region_caliper_label"),
        CheckConstraint("measurement_revision >= 1", name="ck_region_caliper_revision"),
        CheckConstraint(
            "calibration_source IN ('NONE', 'UNKNOWN', 'MANUAL', 'DICOM')",
            name="ck_region_caliper_calibration_source",
        ),
        UniqueConstraint(
            "assignment_request_id", "region_id", "label", "measurement_revision",
            name="uq_region_caliper_snapshot_revision",
        ),
        Index(
            "ix_region_caliper_latest",
            "study_id", "image_id", "assignment_request_id", "region_id", "label", "measurement_revision",
        ),
    )

    request_id = Column(String(36), primary_key=True)
    assignment_request_id = Column(
        String(36), ForeignKey("region_assignment_batches.request_id", ondelete="CASCADE"), nullable=False,
    )
    study_id = Column(String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    region_id = Column(String(36), nullable=False)
    review_revision = Column(Integer, nullable=False)
    mask_sha256 = Column(String(64), nullable=False)
    label = Column(String(2), nullable=False)
    measurement_revision = Column(Integer, nullable=False)
    coordinate_space = Column(String(40), nullable=False)
    points_json = Column(JSON, nullable=False)
    source_width = Column(Integer, nullable=False)
    source_height = Column(Integer, nullable=False)
    diameter_px = Column(Float, nullable=False)
    diameter_mm = Column(Float, nullable=True)
    pixel_spacing_mm = Column(Float, nullable=True)
    calibration_source = Column(String(16), nullable=False)
    calibration_hash = Column(String(64), nullable=False)
    actor_id = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class RegionCDSSAssessmentModel(Base):
    """Immutable RUO rule assessment tied to one region, mask review and optional caliper event."""

    __tablename__ = "region_cdss_assessments"
    __table_args__ = (
        CheckConstraint("assessment_revision >= 1", name="ck_region_cdss_revision"),
        UniqueConstraint(
            "assignment_request_id", "region_id", "assessment_revision",
            name="uq_region_cdss_snapshot_revision",
        ),
        Index(
            "ix_region_cdss_history",
            "study_id", "image_id", "region_id", "assessment_revision",
        ),
    )

    request_id = Column(String(36), primary_key=True)
    assignment_request_id = Column(
        String(36), ForeignKey("region_assignment_batches.request_id", ondelete="CASCADE"), nullable=False,
    )
    study_id = Column(String(36), ForeignKey("studies.id", ondelete="CASCADE"), nullable=False)
    image_id = Column(String(36), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    review_id = Column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    region_id = Column(String(36), nullable=False)
    review_revision = Column(Integer, nullable=False)
    mask_sha256 = Column(String(64), nullable=False)
    assessment_revision = Column(Integer, nullable=False)
    vision_findings_json = Column(JSON, nullable=False)
    patient_context_json = Column(JSON, nullable=False)
    source_caliper_event_id = Column(
        String(36), ForeignKey("region_caliper_events.request_id", ondelete="SET NULL"), nullable=True,
    )
    source_caliper_revision = Column(Integer, nullable=True)
    result_json = Column(JSON, nullable=False)
    actor_id = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class ReviewBatchModel(Base):
    __tablename__ = "review_batches"

    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), unique=True, nullable=False, index=True)
    actor_id = Column(String(64), nullable=False)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class HITLSessionModel(Base):
    __tablename__ = "hitl_sessions"
    __table_args__ = (
        CheckConstraint(
            f"participant_role IN ({_HITL_SESSION_ROLE_SQL})",
            name="ck_hitl_sessions_participant_role",
        ),
        CheckConstraint(
            f"data_origin IN ({_HITL_SESSION_DATA_ORIGIN_SQL})",
            name="ck_hitl_sessions_data_origin",
        ),
        CheckConstraint(
            f"status IS NOT NULL AND status IN ({_HITL_SESSION_STATUS_SQL})",
            name="ck_hitl_sessions_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=False, index=True)
    actor_id = Column(String(64), nullable=False)
    participant_code = Column(String(64), nullable=False)
    participant_role = Column(String(30), nullable=False)  # clinician, technical_tester
    data_origin = Column(String(30), nullable=False)  # live, technical_fixture, demo
    status = Column(String(30), default="IN_PROGRESS", nullable=False)
    review_batch_id = Column(String(36), ForeignKey("review_batches.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    study = relationship("StudyModel")
    review_batch = relationship("ReviewBatchModel")
    events = relationship("HITLEventModel", back_populates="session", cascade="all, delete-orphan")


class HITLEventModel(Base):
    __tablename__ = "hitl_events"

    id = Column(String(36), primary_key=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("hitl_sessions.id"), nullable=False, index=True)
    task_id = Column(String(36), nullable=False, index=True)
    image_id = Column(String(36), nullable=False)
    prediction_id = Column(String(36), nullable=True)
    seq = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    client_utc = Column(String(50), nullable=False)
    elapsed_ms = Column(Float, nullable=False)
    session_elapsed_ms = Column(Float, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=True)
    actor_id = Column(String(64), nullable=False)
    received_at = Column(DateTime, default=lambda: datetime.now(UTC))

    session = relationship("HITLSessionModel", back_populates="events")

    __table_args__ = (
        UniqueConstraint("session_id", "task_id", "seq", name="uq_session_task_seq"),
        CheckConstraint(
            f"event_type IN ({_HITL_EVENT_TYPE_SQL})",
            name="ck_hitl_events_event_type",
        ),
        ForeignKeyConstraint(["image_id"], ["images.id"], name="fk_hitl_events_image"),
        ForeignKeyConstraint(
            ["prediction_id", "image_id"],
            ["predictions.id", "predictions.image_id"],
            name="fk_hitl_events_prediction_image",
        ),
    )


class UIEventModel(Base):
    __tablename__ = "ui_events"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(36), ForeignKey("studies.id"), nullable=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    payload_json = Column(JSON, nullable=True)
    t_ms = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    study = relationship("StudyModel")


class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True)
    recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=True)
    event_type = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    dedup_key = Column(String(128), unique=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)


class CorrectionRequestModel(Base):
    __tablename__ = "correction_requests"

    id = Column(String(36), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=False, index=True)
    doctor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    technician_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    status = Column(String(32), default="PENDING", nullable=False, index=True)
    review_revision = Column(Integer, default=0, nullable=False)
    reason = Column(Text, nullable=True)
    draft_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


def _ensure_audit_immutability_postgres(engine_or_conn) -> None:
    """Enforce append-only immutability for audit_logs in PostgreSQL (FDA 21 CFR Part 11 / ISO 27799)."""
    trigger_func_sql = (
        "CREATE OR REPLACE FUNCTION trg_audit_logs_immutable() "
        "RETURNS TRIGGER AS $$ "
        "BEGIN "
        "    RAISE EXCEPTION 'Audit log is append-only and immutable; UPDATE and DELETE are forbidden under FDA 21 CFR Part 11 / ISO 27799.'; "
        "END; "
        "$$ LANGUAGE plpgsql;"
    )
    do_block_sql = (
        "DO $$ "
        "BEGIN "
        "    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_logs_no_update') THEN "
        "        CREATE TRIGGER trg_audit_logs_no_update "
        "        BEFORE UPDATE ON audit_logs "
        "        FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable(); "
        "    END IF; "
        "    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_logs_no_delete') THEN "
        "        CREATE TRIGGER trg_audit_logs_no_delete "
        "        BEFORE DELETE ON audit_logs "
        "        FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable(); "
        "    END IF; "
        "END $$;"
    )
    with engine_or_conn.begin() as tx_conn:
        tx_conn.execute(text(trigger_func_sql))
        tx_conn.execute(text(do_block_sql))


def _ensure_audit_immutability(connection: sqlite3.Connection) -> None:
    """Enforce append-only immutability for audit_logs (F06: FDA 21 CFR Part 11 / ISO 27799)."""
    triggers = (
        "CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_update "
        "BEFORE UPDATE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT, 'Audit log is append-only and immutable; UPDATE is forbidden.'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_delete "
        "BEFORE DELETE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT, 'Audit log is append-only and immutable; DELETE is forbidden.'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _run_sqlite_schema_migrations(conn) -> None:
    try:
        raw_conn = conn.connection.driver_connection
        _migrate_auth_email_schema_on_connection(raw_conn)
        cursor = raw_conn.cursor()
        _migrate_patient_identity_on_connection(cursor)
        cursor.execute("PRAGMA table_info(studies);")
        columns = [col[1] for col in cursor.fetchall()]
        if "study_code" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN study_code VARCHAR(64);")
        if "status" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN status VARCHAR(30);")
        if "ovary_side" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN ovary_side VARCHAR(10);")
        if "contralateral_status" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN contralateral_status VARCHAR(30);")
        if "review_revision" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN review_revision INTEGER DEFAULT 0;")
        if "assignee_id" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN assignee_id VARCHAR(36) REFERENCES users(id);")
        if "patient_directory_id" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN patient_directory_id VARCHAR(36) REFERENCES patient_directory(id);")
        if "patient_age" not in columns:
            cursor.execute("ALTER TABLE studies ADD COLUMN patient_age VARCHAR(20);")
        _migrate_case_idempotency_on_connection(cursor)
        _migrate_visit_numbers_on_connection(cursor)
        _migrate_visits_on_connection(cursor)
        _ensure_study_domains(raw_conn)
        cursor.execute("PRAGMA table_info(images);")
        image_columns = [col[1] for col in cursor.fetchall()]
        if "laterality" not in image_columns:
            cursor.execute("ALTER TABLE images ADD COLUMN laterality VARCHAR(1);")
        if "file_hash" not in image_columns:
            cursor.execute("ALTER TABLE images ADD COLUMN file_hash VARCHAR(64);")
        if "source_content_sha256" not in image_columns:
            cursor.execute("ALTER TABLE images ADD COLUMN source_content_sha256 VARCHAR(64);")
        _migrate_image_upload_idempotency_on_connection(cursor)
        if "calibration_source" not in image_columns:
            cursor.execute("ALTER TABLE images ADD COLUMN calibration_source VARCHAR(16);")
        _ensure_image_laterality_domain(raw_conn)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_study_source_content_sha256 ON images(study_id, source_content_sha256)")
        _scrub_client_upload_filenames(cursor)
        indexes = cursor.execute("PRAGMA index_list(images)").fetchall()
        has_hash_constraint = False
        for index in indexes:
            if index[2]:
                index_name = index[1].replace('"', '""')
                indexed_columns = [column[2] for column in cursor.execute(f'PRAGMA index_info("{index_name}")')]
                if indexed_columns == ["study_id", "file_hash"]:
                    has_hash_constraint = True
                    break
        if not has_hash_constraint:
            images = cursor.execute("SELECT id, study_id, raw_path, file_hash FROM images ORDER BY id").fetchall()
            claimed = {(study_id, file_hash) for _, study_id, _, file_hash in images if file_hash}
            for image_id, study_id, raw_path, file_hash in images:
                if file_hash or not raw_path:
                    continue
                try:
                    with open(raw_path, "rb") as image_file:
                        digest = hashlib.file_digest(image_file, "sha256").hexdigest()
                except OSError:
                    continue
                if (study_id, digest) not in claimed:
                    cursor.execute("UPDATE images SET file_hash = ? WHERE id = ?", (digest, image_id))
                    claimed.add((study_id, digest))
            cursor.execute("CREATE UNIQUE INDEX uq_study_file_hash ON images(study_id, file_hash)")
        cursor.execute("DROP INDEX IF EXISTS uq_study_laterality;")
        cursor.execute("PRAGMA table_info(reviews);")
        review_columns = [col[1] for col in cursor.fetchall()]
        if "hitl_feedback" not in review_columns:
            cursor.execute("ALTER TABLE reviews ADD COLUMN hitl_feedback JSON;")
        cursor.execute("PRAGMA table_info(predictions);")
        pred_columns = [col[1] for col in cursor.fetchall()]
        if "provenance_json" not in pred_columns:
            cursor.execute("ALTER TABLE predictions ADD COLUMN provenance_json JSON;")
        if "uncertainty_map_png" not in pred_columns:
            cursor.execute("ALTER TABLE predictions ADD COLUMN uncertainty_map_png BLOB;")
        _migrate_prediction_idempotency_on_connection(cursor)
        cursor.execute("PRAGMA table_info(users);")
        user_columns = [col[1] for col in cursor.fetchall()]
        if user_columns and "password_hash" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);")
        if user_columns and "token_version" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1;")
        if user_columns and "must_change_password" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0;")
        if user_columns and "tokens_revoked_at" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN tokens_revoked_at DATETIME;")
        if user_columns and "facility_id" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN facility_id VARCHAR(36);")
        if user_columns and "is_global_admin" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_global_admin BOOLEAN DEFAULT 0;")
        _migrate_reference_integrity_on_connection(conn)
        _ensure_review_action_domain(raw_conn)
        _ensure_hitl_event_type_domain(raw_conn)
        _ensure_hitl_session_domains(raw_conn)
        _ensure_audit_immutability(raw_conn)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_studies_facility_status_created ON studies(facility_id, status, created_at);")
        conn.commit()
        _migrate_study_contralateral_constraint(raw_conn)
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        raise RuntimeError("SQLite schema migration failed") from exc
    finally:
        if conn is not None:
            conn.close()


def init_db():
    conn = None
    try:
        if engine.dialect.name == "sqlite":
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = engine.connect()
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            Base.metadata.create_all(bind=conn, checkfirst=True)
            _run_sqlite_schema_migrations(conn)
        else:
            Base.metadata.create_all(bind=engine, checkfirst=True)
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE studies ADD COLUMN IF NOT EXISTS "
                    "patient_directory_id VARCHAR(36) REFERENCES patient_directory(id)"
                ))
                connection.execute(text(
                    "ALTER TABLE studies ADD COLUMN IF NOT EXISTS patient_age VARCHAR(20)"
                ))
            _ensure_postgres_patient_identity_columns(engine)
            _ensure_audit_immutability_postgres(engine)
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()
        if "SQLite schema migration failed" in str(exc):
            raise
        raise RuntimeError("Database schema creation failed") from exc

    _migrate_patient_facility_scope(engine)

    # Bootstrap only accounts whose credentials have been configured by the operator.
    from backend.app.security import hash_password
    with SessionLocal() as db:
        default_facility = db.query(FacilityModel).first()
        if not default_facility:
            default_facility = FacilityModel(
                id="fac-vinmec-times-city",
                facility_code="FAC-VINMEC-TC",
                name="Vinmec Times City (Cơ sở Chính)",
                is_active=True,
            )
            db.add(default_facility)
            db.commit()
            db.refresh(default_facility)

        for username, role, password_key, name_key, label in [
            ("doctor", "DOCTOR", "APP_DOCTOR_PASSWORD", "APP_DOCTOR_FULL_NAME", "Bác sĩ"),
            ("bacsi", "DOCTOR", "APP_DOCTOR_PASSWORD", "APP_DOCTOR_FULL_NAME", "Bác sĩ"),
            ("admin", "ADMIN", "APP_ADMIN_PASSWORD", "APP_ADMIN_FULL_NAME", "Quản trị viên"),
        ]:
            user = db.query(UserModel).filter(UserModel.username == username).first()
            if user:
                if user.full_name in ("BS.CKI Nguyễn Văn A", "BS.CKII Trần Quản Trị"):
                    user.full_name = os.environ.get(name_key) or label
                    user.title = ""
                if role == "ADMIN" and user.facility_id is None:
                    user.is_global_admin = True
                # DO NOT automatically guess or backfill facility_id for existing legacy accounts
            elif not user and os.environ.get(password_key):
                db.add(UserModel(
                    id=str(uuid.uuid4()), username=username, role=role,
                    full_name=os.environ.get(name_key) or label, title="",
                    facility_id=os.environ.get("APP_DOCTOR_FACILITY_ID") if role == "DOCTOR" else None,
                    is_global_admin=True if role == "ADMIN" and not os.environ.get("APP_DOCTOR_FACILITY_ID") else False,
                    password_hash=hash_password(os.environ[password_key]),
                    is_active=True,
                ))
        db.commit()

    try:
        dialect_name = "PostgreSQL" if engine.dialect.name == "postgresql" else "SQLite"
        print(f"[Database] {dialect_name} DB initialized and verified.")
    except Exception:
        pass

def migrate_auth_email_schema(db_path: str) -> None:
    """Add registration email fields to existing SQLite databases without losing users."""
    conn = connect_sqlite(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _migrate_auth_email_schema_on_connection(conn)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise RuntimeError("SQLite auth email migration failed") from exc
    finally:
        conn.close()


def _migrate_auth_email_schema_on_connection(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users);")
    columns = {column[1] for column in cursor.fetchall()}
    if columns:
        if "email" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(254);")
        if "email_verified" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0;")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower "
            "ON users(lower(email)) WHERE email IS NOT NULL;"
        )


def _migrate_patient_identity_on_connection(cursor: sqlite3.Cursor) -> None:
    """Pseudonymize legacy patient IDs and bind their lookup digests to one key."""
    from backend.core.patient_identity import (
        is_synthetic_patient_id,
        new_synthetic_patient_id,
        normalize_source_patient_id,
        patient_id_digest,
        patient_pid_key_id,
        patient_pid_secret,
    )

    columns = {row[1] for row in cursor.execute("PRAGMA table_info(patients)").fetchall()}
    if "source_pid_hmac" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN source_pid_hmac VARCHAR(64);")
    if "pid_hmac_key_id" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN pid_hmac_key_id VARCHAR(64);")
    if "legacy_source_pid_hmac" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN legacy_source_pid_hmac VARCHAR(64);")
    if "pid_hmac_scope_version" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN pid_hmac_scope_version INTEGER NOT NULL DEFAULT 0;")
    if "facility_id" not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN facility_id VARCHAR(36) REFERENCES facilities(id);")

    indexes = cursor.execute("PRAGMA index_list(patients)").fetchall()
    has_digest_index = False
    for index in indexes:
        if index[2]:
            name = index[1].replace('"', '""')
            indexed_columns = [row[2] for row in cursor.execute(f'PRAGMA index_info("{name}")')]
            if indexed_columns == ["source_pid_hmac"]:
                has_digest_index = True
                break
    if not has_digest_index:
        cursor.execute("CREATE UNIQUE INDEX uq_patients_source_pid_hmac ON patients(source_pid_hmac)")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_facility_source_pid_hmac "
        "ON patients(facility_id, source_pid_hmac)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_facility_legacy_source_pid_hmac "
        "ON patients(facility_id, legacy_source_pid_hmac)"
    )

    secret = patient_pid_secret()
    key_id = patient_pid_key_id(secret)
    rows = cursor.execute(
        "SELECT id, anonymized_pid, source_pid_hmac, pid_hmac_key_id, legacy_source_pid_hmac FROM patients ORDER BY id"
    ).fetchall()
    for patient_id, stored_pid, stored_digest, stored_key_id, legacy_digest in rows:
        if stored_digest is not None:
            if stored_key_id != key_id or not is_synthetic_patient_id(stored_pid):
                raise RuntimeError("Stored patient pseudonyms do not match the configured HMAC key.")
            continue
        if legacy_digest is not None:
            if stored_key_id != key_id or not is_synthetic_patient_id(stored_pid):
                raise RuntimeError("Stored legacy patient mappings do not match the configured HMAC key.")
            continue
        if stored_key_id is not None:
            raise RuntimeError("Patient identity mapping is incomplete; refusing to continue.")
        source_id = normalize_source_patient_id(stored_pid)
        cursor.execute(
            "UPDATE patients SET anonymized_pid = ?, source_pid_hmac = ?, pid_hmac_key_id = ? WHERE id = ?",
            (new_synthetic_patient_id(), patient_id_digest(source_id, secret), key_id, patient_id),
        )


def _ensure_postgres_patient_identity_columns(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS facility_id VARCHAR(36)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_facility_id ON patients(facility_id)"))
        connection.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS legacy_source_pid_hmac VARCHAR(64)"))
        connection.execute(
            text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS pid_hmac_scope_version INTEGER NOT NULL DEFAULT 0")
        )
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_facility_source_pid_hmac ON patients(facility_id, source_pid_hmac)")
        )
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_facility_legacy_source_pid_hmac ON patients(facility_id, legacy_source_pid_hmac)")
        )
        connection.execute(text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_patients_facility_id_facilities') THEN "
            "ALTER TABLE patients ADD CONSTRAINT fk_patients_facility_id_facilities "
            "FOREIGN KEY (facility_id) REFERENCES facilities(id); "
            "END IF; END $$;"
        ))


def _migrate_patient_facility_scope(engine) -> None:
    """Backfill single-facility legacy identities; stop on ambiguous cross-facility links."""
    from backend.core.patient_identity import (
        is_synthetic_patient_id,
        new_synthetic_patient_id,
        normalize_source_patient_id,
        patient_id_digest,
        patient_pid_key_id,
        patient_pid_secret,
    )

    secret = patient_pid_secret()
    key_id = patient_pid_key_id(secret)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with session_factory() as db:
        try:
            patients = db.query(PatientModel).order_by(PatientModel.id).all()
            for patient in patients:
                linked_facilities = {
                    value
                    for (value,) in db.query(StudyModel.facility_id)
                    .filter(StudyModel.patient_id == patient.id)
                    .distinct()
                    .all()
                    if value
                }
                linked_facilities.update(
                    value
                    for (value,) in db.query(VisitModel.facility_id)
                    .filter(VisitModel.patient_id == patient.id)
                    .distinct()
                    .all()
                    if value
                )
                if patient.facility_id:
                    linked_facilities.add(patient.facility_id)
                if len(linked_facilities) > 1:
                    raise RuntimeError(
                        "A legacy patient identity is linked to multiple facilities; reviewed reconciliation is required."
                    )
                if linked_facilities:
                    patient.facility_id = next(iter(linked_facilities))

                if patient.pid_hmac_scope_version == 0:
                    if patient.source_pid_hmac:
                        if patient.pid_hmac_key_id != key_id or not is_synthetic_patient_id(patient.anonymized_pid):
                            raise RuntimeError("Stored legacy patient pseudonyms do not match the configured HMAC key.")
                        if patient.legacy_source_pid_hmac not in (None, patient.source_pid_hmac):
                            raise RuntimeError("Legacy patient identity mapping is inconsistent.")
                        patient.legacy_source_pid_hmac = patient.source_pid_hmac
                        patient.source_pid_hmac = None
                    elif patient.legacy_source_pid_hmac is None and not is_synthetic_patient_id(patient.anonymized_pid):
                        source_id = normalize_source_patient_id(patient.anonymized_pid)
                        patient.anonymized_pid = new_synthetic_patient_id()
                        patient.legacy_source_pid_hmac = patient_id_digest(source_id, secret)
                        patient.pid_hmac_key_id = key_id
                    if patient.legacy_source_pid_hmac and patient.pid_hmac_key_id != key_id:
                        raise RuntimeError("Stored legacy patient mappings do not match the configured HMAC key.")
                elif patient.pid_hmac_scope_version == 1:
                    if patient.source_pid_hmac and (
                        patient.pid_hmac_key_id != key_id
                        or not is_synthetic_patient_id(patient.anonymized_pid)
                        or not patient.facility_id
                    ):
                        raise RuntimeError("Stored facility-scoped patient pseudonyms are incomplete or use a different key.")
                    if patient.legacy_source_pid_hmac and patient.pid_hmac_key_id != key_id:
                        raise RuntimeError("Stored legacy patient mappings do not match the configured HMAC key.")
                else:
                    raise RuntimeError("Unknown patient identity scope version; refusing to continue.")
            db.commit()
        except Exception as exc:
            db.rollback()
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError("Patient facility identity migration failed") from exc


def _migrate_visit_numbers_on_connection(cursor: sqlite3.Cursor) -> None:
    """Backfill persistent six-digit encounter numbers and install uniqueness."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS visit_number_sequences ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "next_value INTEGER NOT NULL CHECK (next_value BETWEEN 1 AND 1000000)"
        ")"
    )
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(studies)").fetchall()}
    if "visit_no" not in columns:
        cursor.execute("ALTER TABLE studies ADD COLUMN visit_no VARCHAR(6);")

    rows = cursor.execute("SELECT id, visit_no FROM studies ORDER BY id").fetchall()
    used: set[str] = set()
    missing: list[str] = []
    for study_id, raw_visit_no in rows:
        if raw_visit_no in (None, ""):
            missing.append(study_id)
            continue
        visit_no = str(raw_visit_no)
        if len(visit_no) != 6 or not visit_no.isascii() or not visit_no.isdigit():
            raise RuntimeError("Stored Visit No is not a six-digit ASCII number; refusing to migrate.")
        if visit_no in used:
            raise RuntimeError("Duplicate Visit No exists; refusing to migrate silently.")
        used.add(visit_no)

    counter = cursor.execute(
        "SELECT next_value FROM visit_number_sequences WHERE id = 1"
    ).fetchone()
    largest_used = max((int(value) for value in used), default=0)
    next_value = max(int(counter[0]) if counter else 1, largest_used + 1)
    for study_id in missing:
        if next_value > 999999:
            raise RuntimeError("The six-digit Visit No range cannot cover existing studies.")
        visit_no = f"{next_value:06d}"
        cursor.execute("UPDATE studies SET visit_no = ? WHERE id = ?", (visit_no, study_id))
        used.add(visit_no)
        next_value += 1

    if next_value > 1000000:
        raise RuntimeError("Visit No sequence state is outside the supported six-digit range.")
    if counter:
        cursor.execute(
            "UPDATE visit_number_sequences SET next_value = ? WHERE id = 1",
            (next_value,),
        )
    else:
        cursor.execute(
            "INSERT INTO visit_number_sequences (id, next_value) VALUES (1, ?)",
            (next_value,),
        )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_studies_visit_no ON studies(visit_no)"
    )


def _migrate_visits_on_connection(cursor: sqlite3.Cursor) -> None:
    """Backfill first-class Visit records (VIS-YYYYMMDD-XXXXXXXX) for existing studies."""
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(studies)").fetchall()}
    if "visit_id" not in columns:
        cursor.execute("ALTER TABLE studies ADD COLUMN visit_id VARCHAR(36);")
    if "facility_id" not in columns:
        cursor.execute("ALTER TABLE studies ADD COLUMN facility_id VARCHAR(36);")

    studies = cursor.execute("SELECT id, patient_id, study_date, created_at, visit_id, facility_id FROM studies").fetchall()
    for study_id, patient_id, study_date, created_at, visit_id, facility_id in studies:
        if not visit_id:
            date_clean = (str(study_date) if study_date else "").replace("-", "")[:8]
            if len(date_clean) != 8 or not date_clean.isdigit():
                date_clean = datetime.now(UTC).strftime("%Y%m%d")
            suffix = hashlib.sha256(f"study_visit_{study_id}".encode("ascii")).hexdigest()[:8].upper()
            new_visit_code = f"VIS-{date_clean}-{suffix}"
            new_visit_id = str(uuid.uuid4())
            now_iso = datetime.now(UTC).isoformat()
            cursor.execute(
                "INSERT OR IGNORE INTO visits (id, visit_code, facility_id, patient_id, status, is_locked, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'ACTIVE', 0, ?, ?)",
                (new_visit_id, new_visit_code, facility_id, patient_id, created_at or now_iso, now_iso),
            )
            row = cursor.execute("SELECT id FROM visits WHERE visit_code = ?", (new_visit_code,)).fetchone()
            actual_visit_id = row[0] if row else new_visit_id
            cursor.execute("UPDATE studies SET visit_id = ? WHERE id = ?", (actual_visit_id, study_id))



def _migrate_case_idempotency_on_connection(cursor: sqlite3.Cursor) -> None:
    """Add durable, unique intake retry identifiers to existing SQLite databases."""
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(studies)").fetchall()}
    if "idempotency_key_digest" not in columns:
        cursor.execute("ALTER TABLE studies ADD COLUMN idempotency_key_digest VARCHAR(64);")
    if "idempotency_request_digest" not in columns:
        cursor.execute("ALTER TABLE studies ADD COLUMN idempotency_request_digest VARCHAR(64);")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_studies_idempotency_key_digest "
        "ON studies(idempotency_key_digest)"
    )


def _migrate_image_upload_idempotency_on_connection(cursor: sqlite3.Cursor) -> None:
    """Add durable, unique upload retry identifiers to existing SQLite databases."""
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(images)").fetchall()}
    if "upload_idempotency_key_digest" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN upload_idempotency_key_digest VARCHAR(64);")
    if "upload_idempotency_request_digest" not in columns:
        cursor.execute("ALTER TABLE images ADD COLUMN upload_idempotency_request_digest VARCHAR(64);")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_images_upload_idempotency_key_digest "
        "ON images(upload_idempotency_key_digest)"
    )


def _migrate_prediction_idempotency_on_connection(cursor: sqlite3.Cursor) -> None:
    """Add durable, unique prediction retry identifiers to existing SQLite databases."""
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(predictions)").fetchall()}
    if "idempotency_key_digest" not in columns:
        cursor.execute("ALTER TABLE predictions ADD COLUMN idempotency_key_digest VARCHAR(64);")
    if "idempotency_request_digest" not in columns:
        cursor.execute("ALTER TABLE predictions ADD COLUMN idempotency_request_digest VARCHAR(64);")
    if "response_extras_json" not in columns:
        cursor.execute("ALTER TABLE predictions ADD COLUMN response_extras_json JSON;")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions_idempotency_key_digest "
        "ON predictions(idempotency_key_digest)"
    )


def _scrub_client_upload_filenames(cursor: sqlite3.Cursor) -> None:
    """Replace legacy client filenames and remove them from upload audit details."""
    image_columns = {row[1] for row in cursor.execute("PRAGMA table_info(images)")}
    if {"id", "filename"} <= image_columns:
        rows = cursor.execute("SELECT id, filename FROM images").fetchall()
        for image_id, filename in rows:
            extension = os.path.splitext(str(filename or ""))[1].lower()
            if extension not in {".png", ".jpg", ".jpeg", ".dcm"}:
                extension = ""
            try:
                filename_stem = str(uuid.UUID(str(image_id)))
            except (AttributeError, TypeError, ValueError):
                filename_stem = hashlib.sha256(str(image_id).encode("utf-8")).hexdigest()
            sanitized_filename = f"{filename_stem}{extension}"
            if filename != sanitized_filename:
                cursor.execute(
                    "UPDATE images SET filename = ? WHERE id = ?",
                    (sanitized_filename, image_id),
                )

    audit_columns = {row[1] for row in cursor.execute("PRAGMA table_info(audit_logs)")}
    if not {"id", "action_type", "details"} <= audit_columns:
        return
    audit_rows = cursor.execute(
        "SELECT id, details FROM audit_logs WHERE action_type = 'UPLOAD_IMAGE' AND details IS NOT NULL"
    ).fetchall()
    for audit_id, raw_details in audit_rows:
        try:
            details = json.loads(raw_details)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            # Keep the audit event envelope, but clear an opaque payload that cannot
            # be inspected for a legacy client-supplied filename.
            cursor.execute("UPDATE audit_logs SET details = NULL WHERE id = ?", (audit_id,))
            continue
        if isinstance(details, dict) and "filename" in details:
            details.pop("filename")
            cursor.execute(
                "UPDATE audit_logs SET details = ? WHERE id = ?",
                (json.dumps(details, ensure_ascii=False), audit_id),
            )


def _ensure_image_laterality_domain(connection: sqlite3.Connection) -> None:
    """Guard legacy SQLite tables where a CHECK constraint cannot be added in place."""
    invalid_row = connection.execute(
        "SELECT id FROM images "
        "WHERE laterality IS NOT NULL AND laterality NOT IN ('R', 'L') "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if invalid_row:
        raise RuntimeError(
            "Image rows contain a laterality other than R, L, or NULL; refusing to migrate."
        )

    triggers = (
        "CREATE TRIGGER IF NOT EXISTS trg_images_laterality_insert "
        "BEFORE INSERT ON images "
        "WHEN NEW.laterality IS NOT NULL AND NEW.laterality NOT IN ('R', 'L') "
        "BEGIN SELECT RAISE(ABORT, 'image laterality must be R or L'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_images_laterality_update "
        "BEFORE UPDATE OF laterality ON images "
        "WHEN NEW.laterality IS NOT NULL AND NEW.laterality NOT IN ('R', 'L') "
        "BEGIN SELECT RAISE(ABORT, 'image laterality must be R or L'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _ensure_study_domains(connection: sqlite3.Connection) -> None:
    """Guard case workflow and ovary assessment values on legacy SQLite tables."""
    invalid_row = connection.execute(
        "SELECT id FROM studies "
        f"WHERE status IS NULL OR status NOT IN ({_STUDY_STATUS_SQL}) "
        f"OR ovary_side IS NULL OR ovary_side NOT IN ({_STUDY_OVARY_SIDE_SQL}) "
        f"OR contralateral_status IS NULL "
        f"OR contralateral_status NOT IN ({_CONTRALATERAL_STATUS_SQL}) "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if invalid_row:
        raise RuntimeError(
            "Study rows contain unsupported study status, side, or contralateral status; "
            "refusing to migrate."
        )

    connection.execute("DROP TRIGGER IF EXISTS trg_studies_domain_insert")
    connection.execute("DROP TRIGGER IF EXISTS trg_studies_domain_update")
    triggers = (
        "CREATE TRIGGER trg_studies_domain_insert "
        "BEFORE INSERT ON studies "
        f"WHEN NEW.status IS NULL OR NEW.status NOT IN ({_STUDY_STATUS_SQL}) "
        f"OR NEW.ovary_side IS NULL OR NEW.ovary_side NOT IN ({_STUDY_OVARY_SIDE_SQL}) "
        f"OR NEW.contralateral_status IS NULL "
        f"OR NEW.contralateral_status NOT IN ({_CONTRALATERAL_STATUS_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'study domain value is not supported'); END",
        "CREATE TRIGGER trg_studies_domain_update "
        "BEFORE UPDATE OF status, ovary_side, contralateral_status ON studies "
        f"WHEN NEW.status IS NULL OR NEW.status NOT IN ({_STUDY_STATUS_SQL}) "
        f"OR NEW.ovary_side IS NULL OR NEW.ovary_side NOT IN ({_STUDY_OVARY_SIDE_SQL}) "
        f"OR NEW.contralateral_status IS NULL "
        f"OR NEW.contralateral_status NOT IN ({_CONTRALATERAL_STATUS_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'study domain value is not supported'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _migrate_study_contralateral_constraint(connection: sqlite3.Connection) -> bool:
    """Rebuild an older SQLite studies table whose CHECK omits surgical absence."""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'studies'"
    ).fetchone()
    table_sql = row[0] if row else None
    if not table_sql or "SURGICALLY_ABSENT" in table_sql.upper():
        return False

    status_check = re.compile(r"(?is)(\bcontralateral_status\s+IN\s*\()([^)]*)(\))")
    if not status_check.search(table_sql):
        return False
    table_name = re.compile(
        r"(?is)^(\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?:\"studies\"|`studies`|\[studies\]|studies)(?=\s|\()"
    )
    migrated_sql, table_matches = table_name.subn(
        lambda match: f'{match.group(1)}"studies__contralateral_migration"',
        table_sql,
        count=1,
    )
    if table_matches != 1:
        raise RuntimeError("Could not prepare the studies table for contralateral status migration.")
    migrated_sql, status_matches = status_check.subn(
        lambda match: f"{match.group(1)}{match.group(2)}, 'SURGICALLY_ABSENT'{match.group(3)}",
        migrated_sql,
        count=1,
    )
    if status_matches != 1:
        raise RuntimeError("Could not extend the studies contralateral status constraint.")

    foreign_keys_enabled = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    indexes = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'studies' "
        "AND sql IS NOT NULL ORDER BY name"
    ).fetchall()
    triggers = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'studies' "
        "AND sql IS NOT NULL ORDER BY name"
    ).fetchall()
    if connection.in_transaction:
        raise RuntimeError("Contralateral status migration requires a committed SQLite connection.")

    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(migrated_sql)
        connection.execute(
            'INSERT INTO "studies__contralateral_migration" SELECT * FROM "studies"'
        )
        connection.execute("DROP TABLE studies")
        connection.execute(
            'ALTER TABLE "studies__contralateral_migration" RENAME TO studies'
        )
        for (index_sql,) in indexes:
            connection.execute(index_sql)
        for trigger_name, trigger_sql in triggers:
            if trigger_name not in {"trg_studies_domain_insert", "trg_studies_domain_update"}:
                connection.execute(trigger_sql)
        _ensure_study_domains(connection)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError("Contralateral status migration would violate existing foreign keys.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if foreign_keys_enabled:
            connection.execute("PRAGMA foreign_keys = ON")

    return True


def _ensure_review_action_domain(connection: sqlite3.Connection) -> None:
    """Guard legacy review tables whose action column predates the API vocabulary."""
    invalid_row = connection.execute(
        "SELECT id FROM reviews "
        "WHERE doctor_action IS NULL "
        "OR doctor_action NOT IN ('ACCEPTED_RAW', 'MODIFIED', 'REJECTED_ALL') "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if invalid_row:
        raise RuntimeError(
            "Review rows contain a missing or unsupported doctor action; refusing to migrate."
        )

    triggers = (
        "CREATE TRIGGER IF NOT EXISTS trg_reviews_doctor_action_insert "
        "BEFORE INSERT ON reviews "
        "WHEN NEW.doctor_action IS NULL "
        "OR NEW.doctor_action NOT IN ('ACCEPTED_RAW', 'MODIFIED', 'REJECTED_ALL') "
        "BEGIN SELECT RAISE(ABORT, 'review doctor_action is not supported'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_reviews_doctor_action_update "
        "BEFORE UPDATE OF doctor_action ON reviews "
        "WHEN NEW.doctor_action IS NULL "
        "OR NEW.doctor_action NOT IN ('ACCEPTED_RAW', 'MODIFIED', 'REJECTED_ALL') "
        "BEGIN SELECT RAISE(ABORT, 'review doctor_action is not supported'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _ensure_hitl_event_type_domain(connection: sqlite3.Connection) -> None:
    """Guard legacy HITL telemetry tables against event names rejected by the API."""
    invalid_row = connection.execute(
        "SELECT id FROM hitl_events "
        f"WHERE event_type IS NULL OR event_type NOT IN ({_HITL_EVENT_TYPE_SQL}) "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if invalid_row:
        raise RuntimeError(
            "HITL event rows contain a missing or unsupported event type; refusing to migrate."
        )

    triggers = (
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_events_event_type_insert "
        "BEFORE INSERT ON hitl_events "
        f"WHEN NEW.event_type IS NULL OR NEW.event_type NOT IN ({_HITL_EVENT_TYPE_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'HITL event type is not supported'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_events_event_type_update "
        "BEFORE UPDATE OF event_type ON hitl_events "
        f"WHEN NEW.event_type IS NULL OR NEW.event_type NOT IN ({_HITL_EVENT_TYPE_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'HITL event type is not supported'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _ensure_hitl_session_domains(connection: sqlite3.Connection) -> None:
    """Guard legacy HITL sessions against unsupported roles, origins, and states."""
    invalid_row = connection.execute(
        "SELECT id FROM hitl_sessions "
        f"WHERE participant_role IS NULL OR participant_role NOT IN ({_HITL_SESSION_ROLE_SQL}) "
        f"OR data_origin IS NULL OR data_origin NOT IN ({_HITL_SESSION_DATA_ORIGIN_SQL}) "
        f"OR status IS NULL OR status NOT IN ({_HITL_SESSION_STATUS_SQL}) "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if invalid_row:
        raise RuntimeError(
            "HITL session rows contain an unsupported role, data origin, or status; refusing to migrate."
        )

    triggers = (
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_sessions_domain_insert "
        "BEFORE INSERT ON hitl_sessions "
        f"WHEN NEW.participant_role IS NULL OR NEW.participant_role NOT IN ({_HITL_SESSION_ROLE_SQL}) "
        f"OR NEW.data_origin IS NULL OR NEW.data_origin NOT IN ({_HITL_SESSION_DATA_ORIGIN_SQL}) "
        f"OR NEW.status IS NULL OR NEW.status NOT IN ({_HITL_SESSION_STATUS_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'HITL session domain value is not supported'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_sessions_domain_update "
        "BEFORE UPDATE OF participant_role, data_origin, status ON hitl_sessions "
        f"WHEN NEW.participant_role IS NULL OR NEW.participant_role NOT IN ({_HITL_SESSION_ROLE_SQL}) "
        f"OR NEW.data_origin IS NULL OR NEW.data_origin NOT IN ({_HITL_SESSION_DATA_ORIGIN_SQL}) "
        f"OR NEW.status IS NULL OR NEW.status NOT IN ({_HITL_SESSION_STATUS_SQL}) "
        "BEGIN SELECT RAISE(ABORT, 'HITL session domain value is not supported'); END",
    )
    for statement in triggers:
        connection.execute(statement)


def _migrate_reference_integrity_on_connection(connection) -> None:
    """Add review/HITL reference constraints without silently discarding legacy rows."""
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
        raise RuntimeError("SQLite foreign key enforcement is disabled")

    prediction_table = PredictionModel.__table__
    _add_missing_nullable_columns(connection, prediction_table)
    if not _has_foreign_key(connection, "predictions", ("image_id",), "images", ("id",)):
        _rebuild_sqlite_table(connection, "predictions", prediction_table)
    if not _has_foreign_key(connection, "predictions", ("image_id",), "images", ("id",)):
        raise RuntimeError("Could not add the prediction-to-image foreign key")

    _ensure_prediction_reference_key(connection)
    prediction_violations = connection.exec_driver_sql(
        "PRAGMA foreign_key_check(predictions)"
    ).all()
    if prediction_violations:
        raise RuntimeError("Prediction rows contain invalid image references")

    child_tables = (
        (
            ReviewModel.__table__,
            (
                (("image_id",), "images", ("id",)),
                (("prediction_id", "image_id"), "predictions", ("id", "image_id")),
            ),
        ),
        (
            HITLEventModel.__table__,
            (
                (("image_id",), "images", ("id",)),
                (("prediction_id", "image_id"), "predictions", ("id", "image_id")),
            ),
        ),
    )

    for table, expected_foreign_keys in child_tables:
        _add_missing_nullable_columns(connection, table)
        missing = [
            foreign_key
            for foreign_key in expected_foreign_keys
            if not _has_foreign_key(connection, table.name, *foreign_key)
        ]
        if missing:
            _rebuild_sqlite_table(connection, table.name, table)
        if any(
            not _has_foreign_key(connection, table.name, *foreign_key)
            for foreign_key in expected_foreign_keys
        ):
            raise RuntimeError(f"Could not add required foreign keys to {table.name}")
        violations = connection.exec_driver_sql(
            f"PRAGMA foreign_key_check({_quote_sqlite_identifier(table.name)})"
        ).all()
        if violations:
            raise RuntimeError(f"{table.name} contains invalid references")

    _ensure_hitl_event_study_guards(connection)


def _ensure_hitl_event_study_guards(connection) -> None:
    mismatch = connection.exec_driver_sql(
        "SELECT event.id FROM hitl_events AS event "
        "JOIN hitl_sessions AS session ON session.id = event.session_id "
        "JOIN images AS image ON image.id = event.image_id "
        "WHERE session.study_id <> image.study_id LIMIT 1"
    ).first()
    if mismatch:
        raise RuntimeError("HITL events contain an image from a different study than their session")

    trigger_statements = (
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_event_study_match_insert "
        "BEFORE INSERT ON hitl_events WHEN NOT EXISTS ("
        "SELECT 1 FROM hitl_sessions AS session "
        "JOIN images AS image ON image.study_id = session.study_id "
        "WHERE session.id = NEW.session_id AND image.id = NEW.image_id) "
        "BEGIN SELECT RAISE(ABORT, 'HITL image must belong to the session study'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_event_study_match_update "
        "BEFORE UPDATE OF session_id, image_id ON hitl_events WHEN NOT EXISTS ("
        "SELECT 1 FROM hitl_sessions AS session "
        "JOIN images AS image ON image.study_id = session.study_id "
        "WHERE session.id = NEW.session_id AND image.id = NEW.image_id) "
        "BEGIN SELECT RAISE(ABORT, 'HITL image must belong to the session study'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_session_study_guard "
        "BEFORE UPDATE OF study_id ON hitl_sessions WHEN EXISTS ("
        "SELECT 1 FROM hitl_events AS event "
        "JOIN images AS image ON image.id = event.image_id "
        "WHERE event.session_id = OLD.id AND image.study_id <> NEW.study_id) "
        "BEGIN SELECT RAISE(ABORT, 'HITL session study is referenced by events'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_hitl_image_study_guard "
        "BEFORE UPDATE OF study_id ON images WHEN EXISTS ("
        "SELECT 1 FROM hitl_events AS event "
        "JOIN hitl_sessions AS session ON session.id = event.session_id "
        "WHERE event.image_id = OLD.id AND session.study_id <> NEW.study_id) "
        "BEGIN SELECT RAISE(ABORT, 'HITL image study is referenced by events'); END",
    )
    for statement in trigger_statements:
        connection.exec_driver_sql(statement)


def _add_missing_nullable_columns(connection, model_table) -> None:
    table_name = model_table.name
    quoted_table = _quote_sqlite_identifier(table_name)
    existing_columns = {
        row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({quoted_table})")
    }
    expected_columns = set(model_table.columns.keys())
    unexpected_columns = existing_columns - expected_columns
    if unexpected_columns:
        names = ", ".join(sorted(unexpected_columns))
        raise RuntimeError(f"Cannot safely migrate {table_name}: unknown columns ({names})")

    for column in model_table.columns:
        if column.name in existing_columns:
            continue
        if column.primary_key or not column.nullable:
            raise RuntimeError(
                f"Cannot safely migrate {table_name}: required column {column.name} is missing"
            )
        quoted_column = _quote_sqlite_identifier(column.name)
        type_name = column.type.compile(dialect=connection.dialect)
        connection.exec_driver_sql(
            f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {type_name}"
        )


def _ensure_prediction_reference_key(connection) -> None:
    index_name = "uq_prediction_id_image"
    index_rows = connection.exec_driver_sql("PRAGMA index_list(predictions)").all()
    for row in index_rows:
        indexed_columns = [
            column[2]
            for column in connection.exec_driver_sql(
                f"PRAGMA index_info({_quote_sqlite_identifier(row[1])})"
            )
        ]
        if row[2] and not row[4] and indexed_columns == ["id", "image_id"]:
            return
        if row[1] == index_name:
            raise RuntimeError(f"Index {index_name} conflicts with the required prediction key")

    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX uq_prediction_id_image ON predictions(id, image_id)"
    )


def _has_foreign_key(connection, table_name, source_columns, target_table, target_columns) -> bool:
    groups = {}
    for row in connection.exec_driver_sql(
        f"PRAGMA foreign_key_list({_quote_sqlite_identifier(table_name)})"
    ):
        groups.setdefault(row[0], []).append(row)

    expected = tuple(zip(source_columns, target_columns, strict=True))
    for rows in groups.values():
        ordered_rows = sorted(rows, key=lambda row: row[1])
        signature = tuple((row[3], row[4]) for row in ordered_rows)
        if ordered_rows[0][2] == target_table and signature == expected:
            return True
    return False


def _rebuild_sqlite_table(connection, table_name, model_table) -> None:
    quoted_table = _quote_sqlite_identifier(table_name)
    existing_columns = {
        row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({quoted_table})")
    }
    expected_columns = set(model_table.columns.keys())
    if existing_columns != expected_columns:
        raise RuntimeError(f"Cannot safely rebuild {table_name}: legacy columns do not match the model")

    _ensure_no_inbound_foreign_keys(connection, table_name)
    saved_objects = connection.exec_driver_sql(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE tbl_name = ? AND type IN ('index', 'trigger') AND sql IS NOT NULL "
        "ORDER BY type, name",
        (table_name,),
    ).all()
    temporary_name = f"_migration_{table_name}_reference_integrity"
    quoted_temporary = _quote_sqlite_identifier(temporary_name)
    if connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (temporary_name,),
    ).first():
        raise RuntimeError(f"Temporary migration table already exists: {temporary_name}")

    migration_metadata = MetaData()
    for source_table in Base.metadata.sorted_tables:
        if source_table is not model_table:
            source_table.to_metadata(migration_metadata)
    migration_table = model_table.to_metadata(migration_metadata, name=temporary_name)
    create_table_sql = str(CreateTable(migration_table).compile(dialect=connection.dialect))
    connection.exec_driver_sql(create_table_sql)

    column_list = ", ".join(_quote_sqlite_identifier(column) for column in model_table.columns.keys())
    connection.exec_driver_sql(
        f"INSERT INTO {quoted_temporary} ({column_list}) SELECT {column_list} FROM {quoted_table}"
    )
    connection.exec_driver_sql(f"DROP TABLE {quoted_table}")
    connection.exec_driver_sql(
        f"ALTER TABLE {quoted_temporary} RENAME TO {_quote_sqlite_identifier(table_name)}"
    )

    migration_table.name = table_name
    expected_indexes = {index.name for index in migration_table.indexes}
    for index in migration_table.indexes:
        connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))
    for object_type, object_name, object_sql in saved_objects:
        if object_type == "index" and object_name in expected_indexes:
            continue
        connection.exec_driver_sql(object_sql)

    violations = connection.exec_driver_sql(
        f"PRAGMA foreign_key_check({quoted_table})"
    ).all()
    if violations:
        raise RuntimeError(f"Foreign-key violations remain after rebuilding {table_name}")


def _ensure_no_inbound_foreign_keys(connection, target_table) -> None:
    tables = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).scalars()
    for table_name in tables:
        if table_name == target_table:
            continue
        groups = {}
        for row in connection.exec_driver_sql(
            f"PRAGMA foreign_key_list({_quote_sqlite_identifier(table_name)})"
        ):
            if row[2] == target_table:
                groups.setdefault(row[0], []).append(row)
        for rows in groups.values():
            source_columns = [row[3] for row in sorted(rows, key=lambda row: row[1])]
            referenced = " AND ".join(
                f"{_quote_sqlite_identifier(column)} IS NOT NULL" for column in source_columns
            )
            if connection.exec_driver_sql(
                f"SELECT 1 FROM {_quote_sqlite_identifier(table_name)} "
                f"WHERE {referenced} LIMIT 1"
            ).first():
                raise RuntimeError(f"Cannot rebuild {target_table}: another table has references")


def _quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
