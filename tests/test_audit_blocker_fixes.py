"""Regression tests for audit fixes - BLOCKER issues."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


def test_be_01_forgot_password_does_not_leak_reset_token(monkeypatch):
    """BE-01: Forgot password endpoint must NOT return reset token in public HTTP response."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    with TestClient(app) as client:
        # Request forgot password for existing user 'admin'
        response = client.post("/api/auth/forgot-password", json={"username": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert "Nếu tài khoản tồn tại" in data["message"]
        # CRITICAL SECURITY CHECK: reset_token must NOT be leaked in public response
        assert "reset_token" not in data or data["reset_token"] is None, (
            f"BE-01 VULNERABILITY DETECTED: reset_token was publicly returned in response: {data.get('reset_token')}"
        )


def test_be_02_reset_token_rejected_as_access_token(monkeypatch):
    """BE-02: Reset password token must NOT be accepted as Bearer access token."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from backend.app.routers.auth import create_reset_token
    reset_token = create_reset_token("admin")

    with TestClient(app) as client:
        # Attempt to access protected clinical/admin profile using a reset token
        response = client.get(
            "/api/auth/current-user",
            headers={"Authorization": f"Bearer {reset_token}"},
        )
        assert response.status_code == 401, (
            f"BE-02 VULNERABILITY DETECTED: Reset token was accepted as valid access token! "
            f"Status: {response.status_code}, Body: {response.text}"
        )


def test_be_04_self_registered_doctor_requires_admin_approval(tmp_path, monkeypatch):
    """BE-04: Self-registered doctor must require admin approval (is_active=False) before receiving clinical access."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.db.database import Base, UserModel, PatientModel, StudyModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'be04.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            UserModel(id="admin-1", username="admin", full_name="Admin", role="ADMIN", is_active=True),
            PatientModel(id="p1", anonymized_pid="PID-BE04"),
            StudyModel(id="s1", patient_id="p1", study_code="STD-BE04", study_date="2026-10-18"),
        ])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            # External person self-registers as DOCTOR
            reg_resp = client.post("/api/auth/register", json={
                "username": "dr_external",
                "password": "externalpassword123",
                "full_name": "BS. External Person",
                "role": "DOCTOR",
            })
            assert reg_resp.status_code == 200
            reg_data = reg_resp.json()

            # VULNERABILITY CHECK:
            # 1. User must NOT be activated immediately
            assert reg_data["user"]["is_active"] is False, (
                "BE-04 VULNERABILITY DETECTED: Self-registered doctor was immediately marked active!"
            )

            # 2. Even if token was returned, clinical case access must be blocked with 401
            token = reg_data.get("access_token")
            if token:
                case_resp = client.get("/api/cases/s1", headers={"Authorization": f"Bearer {token}"})
                assert case_resp.status_code == 401, (
                    f"BE-04 VULNERABILITY DETECTED: Inactive self-registered user accessed clinical case! "
                    f"Status: {case_resp.status_code}"
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_05_admin_and_non_clinical_roles_cannot_export_research_bundle(tmp_path, monkeypatch):
    """BE-05: Admin and non-clinical roles must NOT be allowed to bypass clinical boundaries via research ZIP export."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.db.database import Base, UserModel, PatientModel, StudyModel, get_db
    from backend.app.routers.auth import create_access_token

    engine = create_engine(f"sqlite:///{tmp_path / 'be05.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            UserModel(id="admin-id", username="admin", full_name="Admin", role="ADMIN", is_active=True),
            UserModel(id="sec-id", username="secretary", full_name="Thư ký", role="SECRETARY", is_active=True),
            PatientModel(id="p1", anonymized_pid="PID-BE05"),
            StudyModel(id="s1", patient_id="p1", study_code="STD-BE05", study_date="2026-10-18"),
        ])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    admin_token = create_access_token({"sub": "admin"})
    sec_token = create_access_token({"sub": "secretary"})

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            payload = {"review_ids": ["rev-1"], "expected_revision": 0}

            # 1. Admin attempt
            admin_resp = client.post(
                "/api/cases/s1/research-export",
                json=payload,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert admin_resp.status_code == 403, (
                f"BE-05 VULNERABILITY DETECTED: Admin was allowed to invoke research-export! "
                f"Status: {admin_resp.status_code}, Body: {admin_resp.text}"
            )

            # 2. Secretary attempt
            sec_resp = client.post(
                "/api/cases/s1/research-export",
                json=payload,
                headers={"Authorization": f"Bearer {sec_token}"},
            )
            assert sec_resp.status_code == 403, (
                f"BE-05 VULNERABILITY DETECTED: Secretary was allowed to invoke research-export! "
                f"Status: {sec_resp.status_code}, Body: {sec_resp.text}"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_be_13_concurrent_laterality_upload_race(tmp_path, monkeypatch):
    """BE-13: Concurrent uploads with same laterality must not create two images on the same ovary side."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    import concurrent.futures
    import cv2
    import numpy as np
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.db.database import Base, UserModel, PatientModel, StudyModel, ImageModel, get_db
    from backend.app.routers.auth import create_access_token

    engine = create_engine(
        f"sqlite:///{tmp_path / 'be13.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            UserModel(id="doc-id", username="doctor", full_name="Bác sĩ", role="DOCTOR", is_active=True),
            PatientModel(id="p1", anonymized_pid="PID-BE13"),
            StudyModel(id="s1", patient_id="p1", study_code="STD-BE13", study_date="2026-10-18", ovary_side="BOTH"),
        ])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    doc_token = create_access_token({"sub": "doctor"})
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Generate two distinct valid test ultrasound images
    img1 = np.full((128, 128, 3), 100, dtype=np.uint8)
    img2 = np.full((128, 128, 3), 200, dtype=np.uint8)
    png1 = cv2.imencode(".png", img1)[1].tobytes()
    png2 = cv2.imencode(".png", img2)[1].tobytes()

    try:
        def upload_attempt(png_bytes, filename):
            with TestClient(app) as client:
                return client.post(
                    "/api/upload",
                    headers=headers,
                    data={"study_id": "s1", "laterality": "R"},
                    files={"file": (filename, png_bytes, "image/png")},
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(upload_attempt, png1, "right_1.png")
            fut2 = executor.submit(upload_attempt, png2, "right_2.png")
            r1 = fut1.result()
            r2 = fut2.result()

        with Session(engine) as db:
            right_images = db.query(ImageModel).filter(
                ImageModel.study_id == "s1", ImageModel.laterality == "R"
            ).all()

        assert len(right_images) <= 1, (
            f"BE-13 VULNERABILITY DETECTED: Concurrent upload created {len(right_images)} images with laterality='R'! "
            f"Statuses: {r1.status_code}, {r2.status_code}"
        )
        # Exactly one must succeed, the other must be rejected with 409 Conflict
        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [200, 409], (
            f"BE-13 VULNERABILITY DETECTED: Expected statuses [200, 409] but got: {statuses}. "
            f"r1: {r1.text}, r2: {r2.text}"
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_ai_01_dicom_rejects_time_unit_physical_units_4(tmp_path):
    """AI-01: DICOM Sequence of Ultrasound Regions with time units (PhysicalUnits=4) must NOT be calibrated as mm."""
    import pydicom
    from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
    from backend.app.routers.inference import extract_dicom_calibration_spacing

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dcm = FileDataset("test_ai01.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dcm.SOPClassUID = meta.MediaStorageSOPClassUID
    dcm.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dcm.Modality = "US"
    dcm.Rows = 128
    dcm.Columns = 128

    # Create Ultrasound Region Sequence with time units (seconds: PhysicalUnits=4)
    region = Dataset()
    region.RegionSpatialFormat = 1
    region.PhysicalUnitsXDirection = 4  # Seconds (time)
    region.PhysicalUnitsYDirection = 4  # Seconds (time)
    region.PhysicalDeltaX = 0.05
    region.PhysicalDeltaY = 0.05
    dcm.SequenceOfUltrasoundRegions = Sequence([region])

    file_path = tmp_path / "time_unit.dcm"
    dcm.save_as(str(file_path))

    # Calibration spacing must be rejected (None), NOT interpreted as 0.05 mm!
    spacing = extract_dicom_calibration_spacing(str(file_path))
    assert spacing is None, (
        f"AI-01 VULNERABILITY DETECTED: Time unit (PhysicalUnits=4) was accepted as physical mm spacing: {spacing}!"
    )


def test_ai_02_dicom_rejects_non_2d_region_or_picks_correct_2d_region(tmp_path):
    """AI-02: DICOM calibration must ignore non-2D regions (e.g. M-mode / Doppler) and require valid 2D spatial format."""
    import pydicom
    from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
    from pydicom.sequence import Sequence
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
    from backend.app.routers.inference import extract_dicom_calibration_spacing

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dcm = FileDataset("test_ai02.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dcm.SOPClassUID = meta.MediaStorageSOPClassUID
    dcm.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dcm.Modality = "US"
    dcm.Rows = 128
    dcm.Columns = 128

    # Region 0: M-mode waveform (SpatialFormat=2) - INVALID for 2D tissue calibration
    mmode_region = Dataset()
    mmode_region.RegionSpatialFormat = 2  # M-mode
    mmode_region.PhysicalUnitsXDirection = 3  # cm
    mmode_region.PhysicalUnitsYDirection = 3  # cm
    mmode_region.PhysicalDeltaX = 0.01
    mmode_region.PhysicalDeltaY = 0.01

    dcm.SequenceOfUltrasoundRegions = Sequence([mmode_region])
    file_path = tmp_path / "mmode_only.dcm"
    dcm.save_as(str(file_path))

    # Must NOT blindly take us_regions[0] and use M-mode calibration!
    spacing = extract_dicom_calibration_spacing(str(file_path))
    assert spacing is None, (
        f"AI-02 VULNERABILITY DETECTED: Non-2D M-mode region was used for 2D calibration: {spacing} mm!"
    )






