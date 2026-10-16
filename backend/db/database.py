"""
Database Engine & ORM Models for Ovarian Ultrasound AI System (SQLAlchemy + SQLite).
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import hashlib
import os
import sqlite3
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

_env_db_path = os.environ.get("APP_DB_PATH")
if _env_db_path:
    DB_PATH = os.path.abspath(_env_db_path) if os.path.isabs(_env_db_path) else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", _env_db_path))
else:
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ovarian_ai.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PatientModel(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True)
    anonymized_pid = Column(String(64), unique=True, nullable=False)
    age_bucket = Column(String(20), nullable=True)
    menopausal_status = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    studies = relationship("StudyModel", back_populates="patient", cascade="all, delete-orphan")


class StudyModel(Base):
    __tablename__ = "studies"

    id = Column(String(36), primary_key=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    study_code = Column(String(64), nullable=True)
    study_date = Column(String(20), nullable=False)
    status = Column(String(30), default="PENDING")  # PENDING, ANALYZED, REVIEWED
    device_vendor = Column(String(50), nullable=True)
    probe_type = Column(String(50), nullable=True)
    ovary_side = Column(String(10), default="RIGHT")
    contralateral_status = Column(String(30), default="NOT_VISUALIZED")
    clinical_indication = Column(Text, nullable=True)
    review_revision = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    patient = relationship("PatientModel", back_populates="studies")
    images = relationship("ImageModel", back_populates="study", cascade="all, delete-orphan")


class ImageModel(Base):
    __tablename__ = "images"
    __table_args__ = (UniqueConstraint("study_id", "file_hash", name="uq_study_file_hash"),)

    id = Column(String(36), primary_key=True)
    study_id = Column(String(36), ForeignKey("studies.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    laterality = Column(String(1), nullable=True)  # R/L; null for legacy single-image studies
    raw_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)
    width = Column(Integer, default=512)
    height = Column(Integer, default=512)
    pixel_spacing_mm = Column(Float, nullable=True)
    is_empty_mask = Column(Boolean, default=False)
    dataset_split = Column(String(20), default="TRAIN")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    study = relationship("StudyModel", back_populates="images")
    predictions = relationship("PredictionModel", back_populates="image", cascade="all, delete-orphan")
    reviews = relationship("ReviewModel", back_populates="image", cascade="all, delete-orphan")


class PredictionModel(Base):
    __tablename__ = "predictions"

    id = Column(String(36), primary_key=True)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False)
    model_version = Column(String(50), nullable=True)
    inference_time_ms = Column(Integer, default=450)
    confidence_score = Column(Float, default=0.85)
    iqa_score = Column(Float, default=0.90)
    raw_mask_rle = Column(JSON, nullable=False)
    measurements = Column(JSON, nullable=False)
    provenance_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    image = relationship("ImageModel", back_populates="predictions")


class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False)
    prediction_id = Column(String(36), nullable=True)
    doctor_id = Column(String(64), default="UNVERIFIED_REVIEWER")
    doctor_action = Column(String(30), default="ACCEPTED_RAW")  # ACCEPTED_RAW, MODIFIED, REJECTED
    verified_mask_rle = Column(JSON, nullable=False)
    max_diameter_mm = Column(Float().evaluates_none(), default=0.0)
    ortho_diameter_mm = Column(Float().evaluates_none(), default=0.0)
    total_area_cm2 = Column(Float().evaluates_none(), default=0.0)
    lesion_type = Column(String(100), default="UNSPECIFIED")
    clinical_notes = Column(Text, default="")
    time_spent_seconds = Column(Integer, default=15)
    hitl_feedback = Column(JSON, nullable=True)
    is_official_ground_truth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    image = relationship("ImageModel", back_populates="reviews")


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

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default="DOCTOR")  # DOCTOR, ADMIN
    department = Column(String(100), default="Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa")
    title = Column(String(50), default="BS.CKI")
    hospital = Column(String(100), default="Bệnh viện ĐKQT Vinmec Times City")
    avatar = Column(String(255), default="doctor_avatar.png")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        print("[Database] Schema create notice:", e)

    # Auto-migration check for SQLite columns in case existing DB was created with older schema
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(studies);")
            columns = [col[1] for col in cursor.fetchall()]
            if "study_code" not in columns:
                cursor.execute("ALTER TABLE studies ADD COLUMN study_code VARCHAR(64);")
            if "status" not in columns:
                cursor.execute("ALTER TABLE studies ADD COLUMN status VARCHAR(30) DEFAULT 'PENDING';")
            if "ovary_side" not in columns:
                cursor.execute("ALTER TABLE studies ADD COLUMN ovary_side VARCHAR(10) DEFAULT 'RIGHT';")
            if "contralateral_status" not in columns:
                cursor.execute("ALTER TABLE studies ADD COLUMN contralateral_status VARCHAR(30) DEFAULT 'NOT_VISUALIZED';")
            if "review_revision" not in columns:
                cursor.execute("ALTER TABLE studies ADD COLUMN review_revision INTEGER DEFAULT 0;")
            cursor.execute("PRAGMA table_info(images);")
            image_columns = [col[1] for col in cursor.fetchall()]
            if "laterality" not in image_columns:
                cursor.execute("ALTER TABLE images ADD COLUMN laterality VARCHAR(1);")
            if "file_hash" not in image_columns:
                cursor.execute("ALTER TABLE images ADD COLUMN file_hash VARCHAR(64);")
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
            cursor.execute("PRAGMA table_info(reviews);")
            review_columns = [col[1] for col in cursor.fetchall()]
            if "hitl_feedback" not in review_columns:
                cursor.execute("ALTER TABLE reviews ADD COLUMN hitl_feedback JSON;")
            cursor.execute("PRAGMA table_info(predictions);")
            pred_columns = [col[1] for col in cursor.fetchall()]
            if "provenance_json" not in pred_columns:
                cursor.execute("ALTER TABLE predictions ADD COLUMN provenance_json JSON;")
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        raise RuntimeError("SQLite schema migration failed") from exc

    # Seed default user accounts if not exist
    try:
        db = SessionLocal()
        if not db.query(UserModel).filter(UserModel.username == "doctor").first():
            doc_user_alt = UserModel(
                id=str(uuid.uuid4()),
                username="doctor",
                full_name="BS.CKI Nguyễn Văn A",
                role="DOCTOR",
                department="Khoa Chẩn đoán Hình ảnh & Phụ sản",
                title="Bác Sĩ Khám & Ký Duyệt",
                hospital="Vinmec Times City (Hà Nội)",
                avatar="doctor_a",
            )
            db.add(doc_user_alt)
        if not db.query(UserModel).filter(UserModel.username == "bacsi").first():
            doc_user = UserModel(
                id=str(uuid.uuid4()),
                username="bacsi",
                full_name="BS.CKI Nguyễn Văn A",
                role="DOCTOR",
                department="Khoa Chẩn đoán Hình ảnh & Phụ sản",
                title="Bác Sĩ Khám & Ký Duyệt",
                hospital="Vinmec Times City (Hà Nội)",
                avatar="doctor_a",
            )
            db.add(doc_user)
        if not db.query(UserModel).filter(UserModel.username == "admin").first():
            admin_user = UserModel(
                id=str(uuid.uuid4()),
                username="admin",
                full_name="BS.CKII Trần Quản Trị",
                role="ADMIN",
                department="Ban Giám Đốc & Trung Tâm AI Y Tế",
                title="Quản Trị Viên Hệ Thống AI",
                hospital="Vinmec Healthcare System",
                avatar="admin_avatar",
            )
            db.add(admin_user)
        db.commit()
        db.close()

    except Exception as e:
        print("[Database] Seed users notice:", e)

    try:
        print("[Database] SQLite DB initialized and verified.")
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
