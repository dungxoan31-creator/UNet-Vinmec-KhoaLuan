"""Regression tests for audit fixes - MAJOR issues."""
import io
import json

import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.image_utils import cv2_imwrite_unicode


def test_fe_03_research_export_metadata_includes_orads_and_morphology(tmp_path, monkeypatch):
    """FE-03: Exported research bundle metadata.json must explicitly include orads and morphology_description from saved review."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token
    from backend.db.database import (
        Base,
        ImageModel,
        PatientModel,
        PredictionModel,
        ReviewModel,
        StudyModel,
        UserModel,
        get_db,
    )
    from backend.services.inference_engine import InferenceEngine

    engine = create_engine(f"sqlite:///{tmp_path / 'fe03.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    img_path = tmp_path / "img1.png"
    cv2_imwrite_unicode(str(img_path), np.zeros((100, 100, 3), dtype=np.uint8))

    rle_512 = InferenceEngine.mask_to_rle(np.zeros((512, 512), dtype=np.uint8))

    from datetime import UTC, datetime
    with Session(engine) as db:
        db.add(UserModel(id="u_doc", username="doctor1", full_name="BS. One", role="DOCTOR", is_active=True))
        p = PatientModel(id="p1", anonymized_pid="PID-001")
        s = StudyModel(id="s1", patient_id="p1", study_code="ST-001", study_date=datetime.now(UTC), review_revision=1)
        im = ImageModel(
            id="im1",
            study_id="s1",
            filename="img1.png",
            raw_path=str(img_path),
            laterality="R",
            width=100,
            height=100,
        )
        pred = PredictionModel(
            id="pr1",
            image_id="im1",
            raw_mask_rle=rle_512,
            measurements={},
            provenance_json={"model_name": "U-Net"},
        )
        rev = ReviewModel(
            id="rev1",
            image_id="im1",
            prediction_id="pr1",
            doctor_id="doctor1",
            doctor_action="MODIFIED",
            verified_mask_rle=rle_512,
            max_diameter_mm=25.0,
            ortho_diameter_mm=18.0,
            total_area_cm2=3.5,
            lesion_type="CYST",
            clinical_notes="Nang buồng trứng phải",
            hitl_feedback={
                "orads": "O-RADS 3",
                "orads_score": "O-RADS 3",
                "morphology_description": "U nang đơn thùy, thành mỏng",
            },
        )
        db.add_all([p, s, im, pred, rev])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        import zipfile
        with TestClient(app) as client:
            token = create_access_token({"sub": "doctor1", "uid": "u_doc"})
            headers = {"Authorization": f"Bearer {token}"}

            resp = client.post(
                "/api/cases/s1/research-export",
                headers=headers,
                json={"review_ids": ["rev1"], "expected_revision": 1},
            )
            assert resp.status_code == 200

            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                assert "metadata.json" in zf.namelist()
                metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
                images = metadata.get("images", [])
                assert len(images) == 1
                img_meta = images[0]

                # FE-03: Assert orads and morphology_description are present in exported metadata
                assert "orads" in img_meta, "FE-03 VULNERABILITY: 'orads' missing from exported image metadata!"
                assert img_meta["orads"] == "O-RADS 3"
                assert "morphology_description" in img_meta, "FE-03 VULNERABILITY: 'morphology_description' missing from exported image metadata!"
                assert img_meta["morphology_description"] == "U nang đơn thùy, thành mỏng"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_ai_04_erased_hole_reduces_mask_area():
    """AI-04: Mask area calculation must account for erased internal holes instead of returning filled outer envelope."""
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 1.0

    # Create a 200x200 mask with a 101x101 outer square and an erased 61x61 inner square
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[50:151, 50:151] = 1  # 101x101 outer square = 10,000 px contour area
    mask[70:131, 70:131] = 0  # 61x61 inner hole erased = ~3,600-3,800 px erased

    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=1.0)
    assert res["has_lesion"] is True
    lesion = res["lesions"][0]

    # Without fix, area_px is 10000.0 (ignoring the erased hole). With fix, hole is subtracted.
    assert lesion["area_px"] < 8000.0, (
        f"AI-04 VULNERABILITY: Internal hole ignored in lesion area calculation! Reported area_px: {lesion['area_px']}"
    )
    assert res["total_area_cm2"] < 80.0, (
        f"AI-04 VULNERABILITY: Internal hole ignored in total_area_cm2! Reported: {res['total_area_cm2']}"
    )


def test_ai_06_summary_diameters_belong_to_same_dominant_lesion():
    """AI-06: Summary max_diameter and ortho_diameter must belong to the same dominant lesion, not mixed across disjoint lesions."""
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 1.0

    # Create mask with two separate components:
    # Component 1 (dominant, area = 2000px): 100 wide x 20 high -> Dmax ~ 100, Dorth ~ 20
    # Component 2 (area = 1600px): 40 wide x 40 high -> Dmax ~ 40, Dorth ~ 40
    mask = np.zeros((300, 300), dtype=np.uint8)
    mask[20:40, 50:150] = 1   # 20x100
    mask[100:140, 50:90] = 1  # 40x40

    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=1.0)
    assert res["total_lesions"] == 2

    # The dominant lesion (index 0) is the 20x100 rectangle
    dominant = res["lesions"][0]
    assert np.isclose(dominant["max_diameter_mm"], 100.0, atol=2.0)
    assert np.isclose(dominant["ortho_diameter_mm"], 20.0, atol=2.0)

    # In AI-06 vulnerability: res["ortho_diameter_mm"] was taken from Component 2 (40mm),
    # resulting in a phantom lesion of 100mm x 40mm!
    assert res["ortho_diameter_mm"] < 30.0, (
        f"AI-06 VULNERABILITY: Summary dimensions mixed axes across different lesions! Reported Dmax={res['max_diameter_mm']}, Dorth={res['ortho_diameter_mm']}"
    )
    assert res["max_diameter_mm"] == dominant["max_diameter_mm"]
    assert res["ortho_diameter_mm"] == dominant["ortho_diameter_mm"]


def test_ai_08_cannot_overwrite_serving_model_key(tmp_path, monkeypatch):
    """AI-08: Registering a model candidate with an existing or reserved key must be rejected to prevent overwriting active serving models."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.config import model_registry
    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'ai08.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="u_adm",
                username="admin1",
                full_name="Admin",
                role="ADMIN",
                is_active=True,
                password_hash=hash_password("adminpass123"),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            admin_token = create_access_token({"sub": "admin1", "uid": "u_adm"})
            ah = {"Authorization": f"Bearer {admin_token}"}

            original_adapter = model_registry.get_adapter("attention_unet")
            original_is_loaded = original_adapter.is_loaded if original_adapter else False

            # Attempt to register candidate model using active serving key "attention_unet"
            resp = client.post(
                "/api/admin/models/register",
                headers=ah,
                json={"model_id": "attention_unet", "name": "Fake Model", "checkpoint": "dummy.pt"},
            )
            # Must be rejected with 409 Conflict (or 400), NEVER 200 SUCCESS
            assert resp.status_code == 409, (
                f"AI-08 VULNERABILITY: Registered candidate overwritten serving model! Status={resp.status_code}, Body={resp.text}"
            )

            # Active serving model must remain intact
            current_adapter = model_registry.get_adapter("attention_unet")
            assert current_adapter is original_adapter
            assert current_adapter.is_loaded == original_is_loaded
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_ai_07_monochrome1_polarity_inversion(tmp_path):
    """AI-07: MONOCHROME1 DICOM images must have their polarity inverted (0=White, 255=Black) to match ultrasound standards."""
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

    from backend.app.routers.inference import decode_ultrasound_image

    # Pixel array: [0] should be rendered as bright (255), [255] should be rendered as dark (0)
    raw_pixels = np.array([[0, 255], [0, 255]], dtype=np.uint8)

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dcm = FileDataset("test_mono1.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dcm.SOPClassUID = meta.MediaStorageSOPClassUID
    dcm.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dcm.Modality = "US"
    dcm.StudyInstanceUID = generate_uid()
    dcm.SeriesInstanceUID = generate_uid()
    dcm.Rows = 2
    dcm.Columns = 2
    dcm.SamplesPerPixel = 1
    dcm.PhotometricInterpretation = "MONOCHROME1"
    dcm.BitsAllocated = 8
    dcm.BitsStored = 8
    dcm.HighBit = 7
    dcm.PixelRepresentation = 0
    dcm.NumberOfFrames = 1
    dcm.PixelData = raw_pixels.tobytes()

    dcm_path = tmp_path / "mono1.dcm"
    dcm.save_as(str(dcm_path))

    decoded = decode_ultrasound_image(str(dcm_path), grayscale=True)
    assert decoded is not None, "Failed to decode valid MONOCHROME1 DICOM"

    # In MONOCHROME1, minimum sample 0 is White (255) and maximum sample 255 is Black (0)
    assert decoded[0, 0] == 255, (
        f"AI-07 VULNERABILITY: MONOCHROME1 polarity was not inverted! Expected 255 at [0,0], got {decoded[0, 0]}"
    )
    assert decoded[0, 1] == 0, (
        f"AI-07 VULNERABILITY: MONOCHROME1 polarity was not inverted! Expected 0 at [0,1], got {decoded[0, 1]}"
    )


def test_ai_05_nonempty_subthreshold_mask_retains_measurements_and_warns():
    """AI-05: Nonempty masks with small components (<50px) must retain measurements and expose warning/reason instead of silently reporting 0 findings."""
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 1.0

    # Create a nonempty mask with 33 pixels (11 wide x 3 high)
    # Physical extent: 10mm length at 1.0 mm/px
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[100:103, 100:111] = 1
    assert int(mask.sum()) == 33

    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=1.0)

    # In AI-05 vulnerability: has_lesion was False, max_diameter_mm was 0.0, total_area_cm2 was 0.0, and no warning/filtered_components existed
    assert res["has_lesion"] is True, (
        f"AI-05 VULNERABILITY: Nonempty mask was silently discarded as having no lesion! res={res}"
    )
    assert res["max_diameter_mm"] >= 9.0, (
        f"AI-05 VULNERABILITY: Nonempty 10mm lesion was reported with diameter {res['max_diameter_mm']}mm"
    )
    assert "filtered_components" in res and len(res["filtered_components"]) > 0
    assert res.get("warning") is not None

    # Test measure_source_mask retains non-zero findings and warning as well
    from backend.services.preprocessor import UltrasoundPreprocessor
    from backend.services.source_measurements import calibration_metadata, measure_source_mask

    preprocessor = UltrasoundPreprocessor()
    source_img = np.zeros((200, 200), dtype=np.uint8)
    rle = engine.mask_to_rle(mask)
    calib = calibration_metadata(1.0)
    source_res = measure_source_mask(source_img, rle, preprocessor, engine, calib)

    assert source_res["has_lesion"] is True
    assert source_res["max_diameter_mm"] >= 9.0
    assert source_res["total_area_px"] > 0
    assert source_res.get("warning") is not None

    # Verify true empty mask still returns no lesion
    empty_mask = np.zeros((200, 200), dtype=np.uint8)
    empty_res = engine.extract_calipers_and_measurements(empty_mask, pixel_spacing_mm=1.0)
    assert empty_res["has_lesion"] is False
    assert empty_res["max_diameter_mm"] == 0.0
    assert empty_res["total_area_cm2"] == 0.0


def test_ai_09_calibration_updates_provenance_spacing(tmp_path):
    """AI-09: Recalibrating image scale must synchronize provenance_json with new spacing and keep calibration history."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.config import model_registry
    from backend.app.routers.inference import calibrate_image_spacing
    from backend.db.database import Base, ImageModel, PatientModel, PredictionModel, StudyModel, UserModel

    engine_db = create_engine(f"sqlite:///{tmp_path / 'ai09.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine_db)

    adapter = model_registry.get_primary_adapter()
    engine_ai = adapter.engine

    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[50:150, 50:150] = 1  # 100x100
    rle = engine_ai.mask_to_rle(mask)

    with Session(engine_db) as db:
        pat = PatientModel(id="p1", anonymized_pid="TEST_AI09")
        db.add(pat)
        std = StudyModel(id="s1", patient_id="p1", study_date="2026-10-18")
        db.add(std)
        img = ImageModel(id="img1", study_id="s1", filename="img1.png", raw_path="dummy.png", width=200, height=200, pixel_spacing_mm=0.2)
        db.add(img)
        pred = PredictionModel(
            id="pred1",
            image_id="img1",
            raw_mask_rle=rle,
            measurements=engine_ai.extract_calipers_and_measurements(mask, pixel_spacing_mm=0.2),
            provenance_json={"pixel_spacing_mm": 0.2, "transform": {"scale": 1.0}},
        )
        db.add(pred)
        user = UserModel(id="u1", username="doctor1", full_name="Doctor One", role="DOCTOR", is_active=True)
        db.add(user)
        db.commit()

        # Recalibrate image spacing from 0.2 to 0.4 mm/px
        res = calibrate_image_spacing("img1", pixel_spacing_mm=0.4, db=db, current_user=user)
        assert res["success"] is True

        # Refresh prediction from DB
        pred_after = db.query(PredictionModel).filter(PredictionModel.id == "pred1").first()

        # In AI-09 vulnerability: pred_after.provenance_json["pixel_spacing_mm"] remained 0.2
        assert pred_after.provenance_json.get("pixel_spacing_mm") == 0.4, (
            f"AI-09 VULNERABILITY: provenance_json was not updated! provenance_json={pred_after.provenance_json}"
        )
        assert pred_after.provenance_json.get("original_inference_pixel_spacing_mm") == 0.2
        assert "calibration_history" in pred_after.provenance_json


def test_be_10_audit_events_date_range_filtering(tmp_path, monkeypatch):
    """BE-10: get_audit_events must parse and apply 'from' and 'to' date filters to query results."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import AuditLogModel, Base, UserModel, get_db

    engine_db = create_engine(f"sqlite:///{tmp_path / 'be10.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine_db)

    with Session(engine_db) as db:
        admin_u = UserModel(
            id="u_adm",
            username="admin_audit",
            full_name="Admin Audit",
            role="ADMIN",
            is_active=True,
            password_hash=hash_password("adminpass123"),
        )
        db.add(admin_u)

        # Add 3 audit logs with distinct dates
        log1 = AuditLogModel(
            entity_name="test",
            entity_id="1",
            action_type="LOGIN",
            actor_id="user1",
            timestamp=datetime(2026, 1, 15, 10, 0, 0),
        )
        log2 = AuditLogModel(
            entity_name="test",
            entity_id="2",
            action_type="READ",
            actor_id="user2",
            timestamp=datetime(2026, 5, 20, 12, 0, 0),
        )
        log3 = AuditLogModel(
            entity_name="test",
            entity_id="3",
            action_type="UPDATE",
            actor_id="user3",
            timestamp=datetime(2026, 10, 18, 14, 0, 0),
        )
        db.add_all([log1, log2, log3])
        db.commit()

    def temporary_db():
        with Session(engine_db) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            token = create_access_token({"sub": "admin_audit", "uid": "u_adm"})
            headers = {"Authorization": f"Bearer {token}"}

            # Filter for future dates (should return 0 results)
            res_future = client.get("/api/admin/audit-events?from=2099-01-01&to=2099-01-02", headers=headers)
            assert res_future.status_code == 200
            data_future = res_future.json()
            assert data_future["total"] == 0, (
                f"BE-10 VULNERABILITY: Future date filter ignored! Expected 0, got total={data_future['total']}"
            )

            # Filter for May 2026 only
            res_may = client.get("/api/admin/audit-events?from=2026-05-01&to=2026-05-31", headers=headers)
            assert res_may.status_code == 200
            data_may = res_may.json()
            assert data_may["total"] == 1
            assert data_may["items"][0]["action_type"] == "READ"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine_db.dispose()


def test_be_14_upload_db_failure_rolls_back_atomically(tmp_path, monkeypatch):
    """BE-14: If database commit fails during upload, newly added patient/study must rollback and file must be removed."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    import cv2
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    import backend.app.routers.inference as inf_router
    from backend.app.main import app
    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, ImageModel, PatientModel, StudyModel, UserModel, get_db

    monkeypatch.setattr(inf_router, "UPLOAD_DIR", str(upload_dir))

    engine_db = create_engine(f"sqlite:///{tmp_path / 'be14.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine_db)

    with Session(engine_db) as db:
        doc = UserModel(
            id="u_doc14",
            username="doc14",
            full_name="Doctor 14",
            role="DOCTOR",
            is_active=True,
            password_hash=hash_password("docpass123"),
        )
        db.add(doc)
        db.commit()

    class FailingCommitSession(Session):
        def commit(self):
            # Fail when ImageModel is being committed
            if any(isinstance(x, ImageModel) for x in self.new):
                raise OperationalError("synthetic final image commit", {}, Exception("injected temporary database failure"))
            return super().commit()

    def failing_db():
        with FailingCommitSession(engine_db, autoflush=False) as db:
            yield db

    app.dependency_overrides[get_db] = failing_db
    try:
        with TestClient(app) as client:
            token = create_access_token({"sub": "doc14", "uid": "u_doc14"})
            headers = {"Authorization": f"Bearer {token}"}

            raw_png = cv2.imencode(".png", np.full((64, 64, 3), 77, np.uint8))[1].tobytes()

            with pytest.raises(Exception):
                client.post(
                    "/api/upload",
                    headers=headers,
                    files={"file": ("test_fail.png", raw_png, "image/png")},
                    data={"anonymized_pid": "ANON_FAIL_PID_14"},
                )

            # Check that patient and study were NOT committed
            with Session(engine_db) as db:
                patients_count = db.query(PatientModel).filter(PatientModel.anonymized_pid == "ANON_FAIL_PID_14").count()
                assert patients_count == 0, (
                    f"BE-14 VULNERABILITY: Patient was committed despite upload failure! count={patients_count}"
                )
                studies_count = db.query(StudyModel).count()
                assert studies_count == 0, (
                    f"BE-14 VULNERABILITY: Study was committed despite upload failure! count={studies_count}"
                )

            # Check that no file was left on disk in upload directory
            files_left = list(upload_dir.iterdir())
            assert len(files_left) == 0, (
                f"BE-14 VULNERABILITY: Uploaded file was left on disk after failure! files={files_left}"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine_db.dispose()


def test_be_15_sqlite_foreign_keys_enforced():
    """BE-15: SQLite connections must enforce PRAGMA foreign_keys=ON to prevent orphan records."""
    import uuid

    import pytest
    from sqlalchemy.exc import IntegrityError

    from backend.db.database import ImageModel, SessionLocal, engine

    # 1. Direct engine PRAGMA check
    with engine.connect() as conn:
        fk_status = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
        assert fk_status == 1, f"BE-15 VULNERABILITY: SQLite PRAGMA foreign_keys is {fk_status}, expected 1 (ON)!"

    # 2. Orphan record insertion check
    with SessionLocal() as db:
        orphan_img = ImageModel(
            id=f"orphan-{uuid.uuid4().hex[:8]}",
            study_id="non-existent-study-id-9999",
            filename="orphan.png",
            raw_path="dummy.png",
        )
        db.add(orphan_img)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_be_16_create_case_rejects_blank_pid(monkeypatch):
    """BE-16: Case creation must reject blank or whitespace-only patient_id with HTTP 422."""
    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    with SessionLocal() as db:
        if not db.query(UserModel).filter(UserModel.username == "doc16").first():
            db.add(UserModel(id="u_doc16", username="doc16", full_name="Doctor 16", role="DOCTOR", is_active=True))
            db.commit()

    with TestClient(app) as client:
        token = create_access_token({"sub": "doc16", "uid": "u_doc16", "role": "DOCTOR"})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Blank string
        resp1 = client.post("/api/cases", headers=headers, json={"patient_id": ""})
        assert resp1.status_code == 422, (
            f"BE-16 VULNERABILITY: Empty patient_id accepted! Status={resp1.status_code}, Body={resp1.text}"
        )

        # 2. Whitespace-only string
        resp2 = client.post("/api/cases", headers=headers, json={"patient_id": "    "})
        assert resp2.status_code == 422, (
            f"BE-16 VULNERABILITY: Whitespace-only patient_id accepted! Status={resp2.status_code}, Body={resp2.text}"
        )


def test_be_17_create_case_rejects_invalid_study_date(monkeypatch):
    """BE-17: Case creation must reject invalid study_date with HTTP 422 instead of storing invalid date."""
    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    with SessionLocal() as db:
        if not db.query(UserModel).filter(UserModel.username == "doc17").first():
            db.add(UserModel(id="u_doc17", username="doc17", full_name="Doctor 17", role="DOCTOR", is_active=True))
            db.commit()

    with TestClient(app) as client:
        token = create_access_token({"sub": "doc17", "uid": "u_doc17", "role": "DOCTOR"})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Non-date text
        resp1 = client.post("/api/cases", headers=headers, json={"patient_id": "PID-VALID-17A", "study_date": "invalid-date"})
        assert resp1.status_code == 422, (
            f"BE-17 VULNERABILITY: Non-date text accepted! Status={resp1.status_code}, Body={resp1.text}"
        )

        # 2. Out-of-bounds calendar date (e.g. Feb 31)
        resp2 = client.post("/api/cases", headers=headers, json={"patient_id": "PID-VALID-17B", "study_date": "2026-02-31"})
        assert resp2.status_code == 422, (
            f"BE-17 VULNERABILITY: Calendar-invalid date accepted! Status={resp2.status_code}, Body={resp2.text}"
        )

        # 3. Valid date succeeds
        resp3 = client.post("/api/cases", headers=headers, json={"patient_id": "PID-VALID-17C", "study_date": "2026-10-18"})
        assert resp3.status_code == 200
        assert resp3.json()["study_date"] == "2026-10-18"


def test_be_18_admin_settings_persist_across_restart(tmp_path, monkeypatch):
    """BE-18: Admin settings updated via PUT /api/admin/settings must persist across process restart."""
    import subprocess
    import sys

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

    with TestClient(app) as client:
        token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        headers = {"Authorization": f"Bearer {token}"}

        # Update setting
        update_resp = client.put(
            "/api/admin/settings",
            headers=headers,
            json={"report_header": "persisted-header-audit-be18"},
        )
        assert update_resp.status_code == 200

        # Simulate fresh process / restart
        import os
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["APP_DATA_DIR"] = str(tmp_path)

        code = (
            "from backend.app.routers import admin; "
            "print('PERSISTED:' + str(admin._ADMIN_SETTINGS.get('report_header')))"
        )
        child = subprocess.run([sys.executable, "-c", code], env=child_env, capture_output=True, encoding="utf-8", timeout=30)
        assert child.returncode == 0, f"Child process failed: {child.stderr}"
        output = child.stdout
        assert "PERSISTED:persisted-header-audit-be18" in output, (
            f"BE-18 VULNERABILITY: Settings lost across process restart! Output: {output}"
        )


def test_be_19_admin_departments_persist_across_restart(tmp_path, monkeypatch):
    """BE-19: Departments created/updated via admin API must persist across process restart."""
    import subprocess
    import sys

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

    with TestClient(app) as client:
        token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        headers = {"Authorization": f"Bearer {token}"}

        # Create department
        create_resp = client.post(
            "/api/admin/departments",
            headers=headers,
            json={"id": "dep-synthetic-19", "name": "Khoa Ung bướu Phụ khoa", "code": "UBPK"},
        )
        assert create_resp.status_code == 200

        # Verify member calculation with user in department
        with SessionLocal() as db:
            if not db.query(UserModel).filter(UserModel.username == "doc_ubpk").first():
                db.add(
                    UserModel(
                        id="u_doc_ubpk",
                        username="doc_ubpk",
                        full_name="Doctor UBPK",
                        role="DOCTOR",
                        department="Khoa Ung bướu Phụ khoa",
                        is_active=True,
                    )
                )
                db.commit()

        list_resp = client.get("/api/admin/departments", headers=headers)
        assert list_resp.status_code == 200
        depts = list_resp.json()
        target = next((d for d in depts if d["id"] == "dep-synthetic-19"), None)
        assert target is not None
        assert target["members"] == 1

        # Simulate fresh process / restart
        import os
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["APP_DATA_DIR"] = str(tmp_path)

        code = (
            "from backend.app.routers import admin; "
            "found = any(x.get('id') == 'dep-synthetic-19' for x in admin._DEPARTMENTS); "
            "print('PERSISTED:' + str(found))"
        )
        child = subprocess.run([sys.executable, "-c", code], env=child_env, capture_output=True, encoding="utf-8", timeout=30)
        assert child.returncode == 0, f"Child process failed: {child.stderr}"
        output = child.stdout
        assert "PERSISTED:True" in output, (
            f"BE-19 VULNERABILITY: Department lost across process restart! Output: {output}"
        )


def test_be_20_admin_candidate_models_persist_across_restart(tmp_path, monkeypatch):
    """BE-20: Candidate models registered via admin API must persist across process restart."""
    import subprocess
    import sys

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

    with TestClient(app) as client:
        token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        headers = {"Authorization": f"Bearer {token}"}

        # Register candidate model
        reg_resp = client.post(
            "/api/admin/models/register",
            headers=headers,
            json={
                "model_id": "candidate_resunet_v2",
                "name": "ResUNet Plus Plus Research",
                "version": "2.1.0",
                "architecture": "ResUNet++",
                "checkpoint": "checkpoints/resunet_v2.pth",
            },
        )
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
        assert reg_resp.json()["model_id"] == "candidate_resunet_v2"

        # Verify it appears in GET /api/admin/models
        overview_resp = client.get("/api/admin/models", headers=headers)
        assert overview_resp.status_code == 200
        overview = overview_resp.json()
        registered_keys = [m.get("name") for m in overview.get("registered_models", [])]
        assert any("ResUNet" in k for k in registered_keys)

        # Simulate fresh process / restart
        import os
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["APP_DATA_DIR"] = str(tmp_path)

        code = (
            "from backend.app.config import model_registry; "
            "found = 'candidate_resunet_v2' in model_registry.adapters; "
            "print('PERSISTED:' + str(found))"
        )
        child = subprocess.run([sys.executable, "-c", code], env=child_env, capture_output=True, encoding="utf-8", timeout=30)
        assert child.returncode == 0, f"Child process failed: {child.stderr}"
        output = child.stdout
        assert "PERSISTED:True" in output, (
            f"BE-20 VULNERABILITY: Candidate model lost across process restart! Output: {output}"
        )


def test_be_21_consecutive_failed_logins_are_throttled_with_429():
    """BE-21: Consecutive failed logins against an account must be throttled with HTTP 429."""
    import uuid

    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        target_user = f"brute_target_{uuid.uuid4().hex[:8]}"
        statuses = []
        for _ in range(12):
            resp = client.post("/api/auth/login", json={"username": target_user, "password": "wrong-password"})
            statuses.append(resp.status_code)

        assert statuses[:5] == [401, 401, 401, 401, 401], f"Expected first 5 attempts to be 401: {statuses[:5]}"
        assert all(s == 429 for s in statuses[5:]), f"Expected attempts 6..12 to be 429: {statuses[5:]}"

        # Ensure different user is not blocked (preventing cross-user DoS)
        other_user = f"other_user_{uuid.uuid4().hex[:8]}"
        other_resp = client.post("/api/auth/login", json={"username": other_user, "password": "wrong-password"})
        assert other_resp.status_code == 401, "Different user should not be locked out by attacker"


def test_be_22_admin_create_user_canonicalizes_role_aliases(monkeypatch):
    """BE-22: POST /api/admin/users must canonicalize role aliases BS->DOCTOR and QT->ADMIN."""
    import uuid

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

    with TestClient(app) as client:
        token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create doctor with alias 'BS'
        bs_username = f"dr_bs_{uuid.uuid4().hex[:6]}"
        resp_bs = client.post(
            "/api/admin/users",
            headers=headers,
            json={"username": bs_username, "full_name": "BS Nguyen", "role": "BS", "password": "pass-doctor-123"},
        )
        assert resp_bs.status_code == 200, f"Create BS user failed: {resp_bs.text}"

        # 2. Create admin with alias 'QT'
        qt_username = f"admin_qt_{uuid.uuid4().hex[:6]}"
        resp_qt = client.post(
            "/api/admin/users",
            headers=headers,
            json={"username": qt_username, "full_name": "QT Tran", "role": "QT", "password": "pass-admin-123"},
        )
        assert resp_qt.status_code == 200, f"Create QT user failed: {resp_qt.text}"

        # Check stored roles in database
        with SessionLocal() as db:
            user_bs = db.query(UserModel).filter(UserModel.username == bs_username).first()
            assert user_bs is not None
            assert user_bs.role == "DOCTOR", (
                f"BE-22 VULNERABILITY: Stored role for BS is '{user_bs.role}', expected 'DOCTOR'!"
            )

            user_qt = db.query(UserModel).filter(UserModel.username == qt_username).first()
            assert user_qt is not None
            assert user_qt.role == "ADMIN", (
                f"BE-22 VULNERABILITY: Stored role for QT is '{user_qt.role}', expected 'ADMIN'!"
            )


def test_be_23_admin_create_user_normalizes_username_lowercase(monkeypatch):
    """BE-23: Admin user creation must normalize username to lowercase so the user can log in."""
    import uuid

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

    with TestClient(app) as client:
        token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create user with mixed case username
        mixed_username = f"Dr_MixedCase_{uuid.uuid4().hex[:6]}"
        create_resp = client.post(
            "/api/admin/users",
            headers=headers,
            json={"username": mixed_username, "password": "Password123!", "role": "DOCTOR"},
        )
        assert create_resp.status_code == 200, f"Create user failed: {create_resp.text}"

        # 2. Attempt login with the exact username used during creation
        login_resp = client.post(
            "/api/auth/login",
            json={"username": mixed_username, "password": "Password123!"},
        )
        assert login_resp.status_code == 200, (
            f"BE-23 VULNERABILITY: User created with mixed-case username cannot log in! Status={login_resp.status_code}, Body={login_resp.text}"
        )


def test_be_26_patch_is_active_strict_validation_and_revocation(monkeypatch):
    """BE-26: PATCH /api/admin/users must strictly validate is_active and revoke active session when deactivated."""
    import uuid

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import SessionLocal, UserModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    with SessionLocal() as db:
        admin_user = db.query(UserModel).filter(UserModel.username == "admin").first()
        if not admin_user:
            admin_user = UserModel(id="u_admin", username="admin", full_name="Admin", role="ADMIN", is_active=True)
            db.add(admin_user)
            db.commit()
        admin_uid = admin_user.id

        test_uid = f"u_test_26_{uuid.uuid4().hex[:6]}"
        test_uname = f"doc_26_{uuid.uuid4().hex[:6]}"
        db.add(UserModel(id=test_uid, username=test_uname, full_name="Doc 26", role="DOCTOR", is_active=True))
        db.commit()

    with TestClient(app) as client:
        admin_token = create_access_token({"sub": "admin", "uid": admin_uid, "role": "ADMIN"})
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        doc_token = create_access_token({"sub": test_uname, "uid": test_uid, "role": "DOCTOR"})
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # 1. Reject invalid string values with HTTP 422
        invalid_resp = client.patch(
            f"/api/admin/users/{test_uid}",
            headers=admin_headers,
            json={"is_active": "unrecognized_bool_value"},
        )
        assert invalid_resp.status_code == 422, (
            f"BE-26 VULNERABILITY: Invalid is_active string accepted! Status={invalid_resp.status_code}"
        )

        # 2. String 'false' must successfully deactivate the user
        deact_resp = client.patch(
            f"/api/admin/users/{test_uid}",
            headers=admin_headers,
            json={"is_active": "false"},
        )
        assert deact_resp.status_code == 200

        with SessionLocal() as db:
            refreshed = db.query(UserModel).filter(UserModel.id == test_uid).first()
            assert refreshed is not None
            assert refreshed.is_active is False, (
                f"BE-26 VULNERABILITY: String 'false' did not set is_active=False! Stored={refreshed.is_active}"
            )

        # 3. Session revocation: deactivated user's existing token must be rejected with 401
        check_resp = client.get("/api/cases", headers=doc_headers)
        assert check_resp.status_code == 401, (
            f"BE-26 VULNERABILITY: Deactivated user token still active! Status={check_resp.status_code}"
        )


def test_be_27_legacy_and_intermediate_telemetry_hash_timing_integrity(monkeypatch):
    """BE-27: Legacy and intermediate telemetry event hashes must enforce timing integrity on replay."""
    import hashlib
    import json
    import uuid

    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import (
        HITLEventModel,
        HITLSessionModel,
        ImageModel,
        PatientModel,
        SessionLocal,
        StudyModel,
        UserModel,
    )

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    doc_uname = f"doc_27_{uuid.uuid4().hex[:6]}"
    doc_uid = f"u_doc_27_{uuid.uuid4().hex[:6]}"
    study_id = f"st_27_{uuid.uuid4().hex[:6]}"
    img_id = f"img_27_{uuid.uuid4().hex[:6]}"
    session_id = f"hs_27_{uuid.uuid4().hex[:6]}"

    pt_id = f"pt_27_{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        db.add(UserModel(id=doc_uid, username=doc_uname, full_name="Doc 27", role="DOCTOR", is_active=True))
        db.add(PatientModel(id=pt_id, anonymized_pid=f"ANON_27_{uuid.uuid4().hex[:6]}"))
        db.add(StudyModel(id=study_id, patient_id=pt_id, study_date="2026-10-18"))
        db.add(ImageModel(id=img_id, study_id=study_id, filename="test.png", raw_path="data/test.png"))
        db.add(
            HITLSessionModel(
                id=session_id,
                study_id=study_id,
                actor_id=doc_uname,
                participant_code="tester27",
                participant_role="clinician",
                data_origin="live",
            )
        )
        db.commit()

    with TestClient(app) as client:
        doc_token = create_access_token({"sub": doc_uname, "uid": doc_uid, "role": "DOCTOR"})
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # Case 1: Legacy payload-only hash stored in DB
        leg_event_id = str(uuid.uuid4())
        leg_event = {
            "event_id": leg_event_id,
            "task_id": "task-legacy",
            "image_id": img_id,
            "prediction_id": None,
            "seq": 1,
            "event_type": "PREDICTION_VIEWED",
            "client_utc": "2026-10-18T10:00:00Z",
            "elapsed_ms": 1500.0,
            "session_elapsed_ms": 2000.0,
            "payload": {"view_mode": "overlay"},
        }
        legacy_hash = hashlib.sha256(json.dumps(leg_event["payload"], sort_keys=True).encode("utf-8")).hexdigest()
        with SessionLocal() as db:
            db.add(
                HITLEventModel(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    actor_id=doc_uname,
                    payload_hash=legacy_hash,
                    **leg_event,
                )
            )
            db.commit()

        # 1a: Exact same replay must succeed (200, duplicate_count=1)
        resp_exact = client.post(
            f"/api/hitl/sessions/{session_id}/events",
            headers=doc_headers,
            json={"events": [leg_event]},
        )
        assert resp_exact.status_code == 200
        assert resp_exact.json()["duplicate_count"] == 1

        # 1b: Replay with mutated timing (elapsed_ms changed) MUST return 409 Conflict
        mutated_timing_event = dict(leg_event, elapsed_ms=9999.0, client_utc="2099-01-01T00:00:00Z")
        resp_mutated = client.post(
            f"/api/hitl/sessions/{session_id}/events",
            headers=doc_headers,
            json={"events": [mutated_timing_event]},
        )
        assert resp_mutated.status_code == 409, (
            f"BE-27 VULNERABILITY: Mutated timing accepted under legacy hash! Status={resp_mutated.status_code}"
        )

        # Case 2: Intermediate format hash stored in DB
        mid_event_id = str(uuid.uuid4())
        mid_event = {
            "event_id": mid_event_id,
            "task_id": "task-intermediate",
            "image_id": img_id,
            "prediction_id": None,
            "seq": 2,
            "event_type": "CORRECTION_START",
            "client_utc": "2026-10-18T10:05:00Z",
            "elapsed_ms": 3200.0,
            "session_elapsed_ms": 5200.0,
            "payload": {"tool": "brush"},
        }
        mid_identity = {
            k: mid_event[k]
            for k in ("event_type", "task_id", "image_id", "seq", "elapsed_ms", "payload")
        }
        mid_hash = hashlib.sha256(json.dumps(mid_identity, sort_keys=True).encode("utf-8")).hexdigest()
        with SessionLocal() as db:
            db.add(
                HITLEventModel(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    actor_id=doc_uname,
                    payload_hash=mid_hash,
                    **mid_event,
                )
            )
            db.commit()

        # 2a: Exact replay of intermediate format event MUST succeed (200, duplicate_count=1)
        resp_mid_exact = client.post(
            f"/api/hitl/sessions/{session_id}/events",
            headers=doc_headers,
            json={"events": [mid_event]},
        )
        assert resp_mid_exact.status_code == 200, (
            f"BE-27 REGRESSION: Intermediate format replay rejected with 409! Status={resp_mid_exact.status_code}"
        )
        assert resp_mid_exact.json()["duplicate_count"] == 1


def test_be_28_concurrent_event_append_idempotency(monkeypatch):
    """BE-28: Concurrent append of identical HITL events must be idempotent (both return 200, not 500)."""
    import uuid
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient
    from sqlalchemy import event as sa_event
    from sqlalchemy.orm import Session

    from backend.app.main import app
    from backend.app.routers.auth import create_access_token
    from backend.db.database import (
        HITLEventModel,
        HITLSessionModel,
        ImageModel,
        PatientModel,
        SessionLocal,
        StudyModel,
        UserModel,
    )

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

    doc_uname = f"doc_28_{uuid.uuid4().hex[:6]}"
    doc_uid = f"u_doc_28_{uuid.uuid4().hex[:6]}"
    study_id = f"st_28_{uuid.uuid4().hex[:6]}"
    img_id = f"img_28_{uuid.uuid4().hex[:6]}"
    session_id = f"hs_28_{uuid.uuid4().hex[:6]}"
    pt_id = f"pt_28_{uuid.uuid4().hex[:6]}"

    with SessionLocal() as db:
        db.add(UserModel(id=doc_uid, username=doc_uname, full_name="Doc 28", role="DOCTOR", is_active=True))
        db.add(PatientModel(id=pt_id, anonymized_pid=f"ANON_28_{uuid.uuid4().hex[:6]}"))
        db.add(StudyModel(id=study_id, patient_id=pt_id, study_date="2026-10-18"))
        db.add(ImageModel(id=img_id, study_id=study_id, filename="test.png", raw_path="data/test.png"))
        db.add(
            HITLSessionModel(
                id=session_id,
                study_id=study_id,
                actor_id=doc_uname,
                participant_code="tester28",
                participant_role="clinician",
                data_origin="live",
            )
        )
        db.commit()

    with TestClient(app) as client:
        doc_token = create_access_token({"sub": doc_uname, "uid": doc_uid, "role": "DOCTOR"})
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        race_event = {
            "event_id": str(uuid.uuid4()),
            "task_id": "task-race-28",
            "image_id": img_id,
            "prediction_id": None,
            "seq": 1,
            "event_type": "PREDICTION_VIEWED",
            "client_utc": "2026-10-18T12:00:00Z",
            "elapsed_ms": 100.0,
            "session_elapsed_ms": 100.0,
            "payload": {"view": "split"},
        }

        barrier = Barrier(2)

        def sync_flush(session_obj, *_args):
            if any(
                isinstance(x, HITLEventModel) and x.event_id == race_event["event_id"]
                for x in session_obj.new
            ):
                barrier.wait(timeout=10)

        sa_event.listen(Session, "before_flush", sync_flush)
        try:
            def send_append(_):
                return client.post(
                    f"/api/hitl/sessions/{session_id}/events",
                    headers=doc_headers,
                    json={"events": [race_event]},
                ).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                status_codes = list(pool.map(send_append, range(2)))
        finally:
            sa_event.remove(Session, "before_flush", sync_flush)

        assert status_codes == [200, 200], (
            f"BE-28 VULNERABILITY: Concurrent event append failed with 500! Status codes: {status_codes}"
        )







