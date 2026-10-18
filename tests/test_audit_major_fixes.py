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
