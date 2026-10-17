"""Source-coordinate calipers, real demo assets and optional persisted HITL feedback."""

import asyncio
import math
import sqlite3
import uuid
from io import BytesIO

import cv2
import numpy as np
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.main import app
from backend.db.database import (
    AuditLogModel,
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
from backend.services.preprocessor import UltrasoundPreprocessor


@pytest.fixture
def source_case(tmp_path, doctor_access):
    engine = create_engine(f"sqlite:///{tmp_path / 'extensions.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    source = np.zeros((300, 800), dtype=np.uint8)
    source[20:280, 20:780] = 110
    path = tmp_path / "source.png"
    assert cv2.imwrite(str(path), source)
    # Build the test rectangle in viewer space so nearest-neighbour inversion is deterministic.
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[220:280, 160:300] = 1
    rle = InferenceEngine.mask_to_rle(mask)
    with Session(engine) as db:
        db.add(PatientModel(id="patient", anonymized_pid="TEST-EXTENSIONS"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-08"))
        db.add(ImageModel(id="image", study_id="study", raw_path=str(path), filename="source.png", width=800, height=300))
        db.add(PredictionModel(id="prediction", image_id="image", model_version="test-checkpoint", raw_mask_rle=rle, measurements={}))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            yield client, engine, rle, source
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_source_png_and_uncalibrated_calipers_use_decoded_dimensions(source_case):
    client, _, rle, source = source_case
    image = client.get("/api/images/image/source.png")
    assert image.status_code == 200, image.text
    decoded = cv2.imdecode(np.frombuffer(image.content, np.uint8), cv2.IMREAD_GRAYSCALE)
    np.testing.assert_array_equal(decoded, source)
    result = client.post("/api/images/image/measurements", json={"rle_mask": rle})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["source_dimensions"] == [800, 300]
    assert data["coordinate_space"] == "decoded-source-image"
    assert data["calibrated"] is False and data["calibration_source"] == "NONE"
    assert data["pixel_spacing_mm"] is None
    assert all(data[key] is None for key in ("max_diameter_mm", "ortho_diameter_mm", "total_area_cm2"))
    pp = UltrasoundPreprocessor()
    _, transform = pp.letterbox_resize(source)
    original_mask = pp.inverse_letterbox_mask(InferenceEngine.rle_to_mask(rle), transform)
    contours, _ = cv2.findContours(original_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    dimensions = sorted(cv2.minAreaRect(contours[0])[1], reverse=True)
    assert data["max_diameter_px"] == pytest.approx(dimensions[0], abs=.01)
    assert data["ortho_diameter_px"] == pytest.approx(dimensions[1], abs=.01)
    assert data["total_area_px"] == cv2.contourArea(contours[0])
    lesion = data["lesions"][0]
    assert lesion["area_cm2"] is None and lesion["perimeter_mm"] is None
    assert math.dist(*lesion["caliper_dmax_points"]) == pytest.approx(data["max_diameter_px"], abs=.01)
    assert math.dist(*lesion["caliper_dorth_points"]) == pytest.approx(data["ortho_diameter_px"], abs=.01)
    for key in ("caliper_dmax_points", "caliper_dorth_points"):
        for original, viewer in zip(lesion[key], lesion[f"viewer_{key}"]):
            assert viewer[0] == pytest.approx(original[0] * 512 / 800)
            assert viewer[1] == pytest.approx(original[1] * 192 / 300 + 160)


def test_manual_spacing_scales_source_calipers_and_review(source_case):
    client, engine, rle, _ = source_case
    with Session(engine) as db:
        db.get(ImageModel, "image").pixel_spacing_mm = .2
        db.commit()
    data = client.post("/api/images/image/measurements", json={"rle_mask": rle}).json()
    assert data["calibrated"] is True and data["calibration_source"] == "MANUAL"
    assert data["max_diameter_mm"] == pytest.approx(data["max_diameter_px"] * .2, abs=.01)
    assert data["total_area_cm2"] == pytest.approx(data["total_area_px"] * .2**2 / 100, abs=.001)
    saved = client.post("/api/review", json={
        "study_id": "study",
        "image_id": "image",
        "prediction_id": "prediction",
        "verified_mask_rle": rle,
        "expected_revision": 0,
        "request_id": f"req-ext-{uuid.uuid4()}",
    })
    assert saved.status_code == 200, saved.text
    with Session(engine) as db:
        assert db.get(ReviewModel, saved.json()["review_id"]).max_diameter_mm == data["max_diameter_mm"]


@pytest.mark.parametrize(("tags", "stored", "expected"), [
    ((.2, .2), .2, "DICOM"), ((.2, .4), None, "NONE"), ((.2, .2), .3, "MANUAL"),
])
def test_dicom_calibration_badge_requires_actual_isotropic_tags(source_case, tmp_path, tags, stored, expected):
    client, engine, rle, source = source_case
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    path = tmp_path / "source.dcm"
    dicom = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dicom.Modality = "US"
    dicom.Rows, dicom.Columns = source.shape
    dicom.PixelSpacing = list(tags)
    dicom.SamplesPerPixel = 1
    dicom.PhotometricInterpretation = "MONOCHROME2"
    dicom.BitsAllocated = dicom.BitsStored = 8
    dicom.HighBit = 7
    dicom.PixelRepresentation = 0
    dicom.PixelData = source.tobytes()
    dicom.save_as(path)
    with Session(engine) as db:
        image = db.get(ImageModel, "image")
        image.raw_path = str(path)
        image.pixel_spacing_mm = stored
        db.commit()
    result = client.post("/api/images/image/measurements", json={"rle_mask": rle})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["calibration_source"] == expected
    assert data["calibrated"] is (stored is not None)
    assert data["pixel_spacing_mm"] == stored
    source_png = client.get("/api/images/image/source.png")
    assert source_png.status_code == 200
    np.testing.assert_array_equal(cv2.imdecode(np.frombuffer(source_png.content, np.uint8), cv2.IMREAD_GRAYSCALE), source)
    reopened = client.get("/api/cases/study").json()["images"][0]
    assert reopened["calibration_source"] == expected


def test_empty_mask_has_zero_source_pixels_without_assumed_mm(source_case):
    client, _, _, _ = source_case
    result = client.post("/api/images/image/measurements", json={"rle_mask": {
        "shape": [512, 512], "counts": [262144], "first_val": 0,
    }})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["has_lesion"] is False and data["lesions"] == []
    assert data["max_diameter_px"] == data["ortho_diameter_px"] == data["total_area_px"] == 0
    assert data["max_diameter_mm"] is None and data["total_area_cm2"] is None


@pytest.mark.parametrize("spacing", [0, -1, float("nan"), float("inf")])
def test_invalid_stored_spacing_does_not_claim_calibration(source_case, spacing):
    client, engine, rle, _ = source_case
    with Session(engine) as db:
        db.get(ImageModel, "image").pixel_spacing_mm = spacing
        db.commit()
    result = client.post("/api/images/image/measurements", json={"rle_mask": rle})
    assert result.status_code == 200, result.text
    assert result.json()["calibration_source"] == "NONE"
    assert result.json()["max_diameter_mm"] is None


@pytest.mark.parametrize("mask", [
    {"shape": [512, 512], "first_val": 0, "counts": [3]},
    {"shape": [2, 2], "first_val": 0, "counts": [4]},
    {"shape": [512, 512], "first_val": 0, "counts": [0, 262144]},
    {"shape": [512, 512], "first_val": 2, "counts": [262144]},
])
def test_measurement_rejects_invalid_rle(source_case, mask):
    client, _, _, _ = source_case
    assert client.post("/api/images/image/measurements", json={"rle_mask": mask}).status_code == 422


def test_source_missing_records_and_missing_files_fail_closed(source_case):
    client, engine, rle, _ = source_case
    assert client.get("/api/images/missing/source.png").status_code == 404
    with Session(engine) as db:
        db.get(ImageModel, "image").raw_path = "does-not-exist.png"
        db.commit()
    assert client.get("/api/images/image/source.png").status_code == 404
    assert client.post("/api/images/image/measurements", json={"rle_mask": rle}).status_code == 404
    # Legacy records without an on-disk source still accept the old review payload.
    saved = client.post("/api/review", json={
        "image_id": "image",
        "prediction_id": "prediction",
        "verified_mask_rle": rle,
        "expected_revision": 0,
        "request_id": f"req-ext-{uuid.uuid4()}",
    })
    assert saved.status_code == 200, saved.text
    with Session(engine) as db:
        review = db.get(ReviewModel, saved.json()["review_id"])
        assert review.hitl_feedback is None and review.max_diameter_mm is None


def test_survey_persistence_actor_timestamp_and_reopen(source_case):
    client, engine, rle, _ = source_case
    feedback = {"usability_rating": 4, "issues": ["BOUNDARY_MISMATCH", "FALSE_NEGATIVE"]}
    result = client.post("/api/review", json={
        "study_id": "study", "image_id": "image", "prediction_id": "prediction",
        "doctor_id": "spoofed", "verified_mask_rle": rle,
        "hitl_feedback": feedback, "time_spent_seconds": 32,
        "expected_revision": 0, "request_id": f"req-ext-{uuid.uuid4()}",
    })
    assert result.status_code == 200, result.text
    assert result.json()["reviewer_id"] == "doctor"
    assert result.json()["reviewed_at"]
    with Session(engine) as db:
        saved = db.get(ReviewModel, result.json()["review_id"])
        assert saved.hitl_feedback == feedback and saved.time_spent_seconds == 32
        audit = db.query(AuditLogModel).filter(AuditLogModel.entity_id == saved.id).one()
        assert audit.details["hitl_feedback"] == feedback
    image = client.get("/api/cases/study").json()["images"][0]
    assert image["review"]["hitl_feedback"] == feedback
    assert image["review"]["reviewer_id"] == "doctor"
    assert image["review"]["reviewed_at"] == result.json()["reviewed_at"]
    assert image["prediction"]["provenance"]["model_version"] == "test-checkpoint"
    assert image["pixel_spacing_mm"] is None


@pytest.mark.parametrize("feedback", [
    {"usability_rating": 0}, {"usability_rating": 6}, {"usability_rating": True},
    {"usability_rating": 1.5}, {"issues": ["NO_ERROR", "FALSE_POSITIVE"]},
    {"issues": ["UNSUPPORTED"]}, {"issues": ["NO_ERROR", "NO_ERROR"]},
])
def test_invalid_survey_is_rejected(source_case, feedback):
    client, _, rle, _ = source_case
    result = client.post("/api/review", json={
        "image_id": "image", "prediction_id": "prediction", "verified_mask_rle": rle,
        "hitl_feedback": feedback, "expected_revision": 0, "request_id": f"req-ext-{uuid.uuid4()}",
    })
    assert result.status_code == 422


def test_demo_catalog_has_readable_assets_and_no_invented_clinical_facts(doctor_access):
    with TestClient(app) as client:
        result = client.get("/api/samples")
        assert result.status_code == 200
        samples = result.json()
        assert samples
        for sample in samples:
            assert sample["pathology"] is None and sample["patient_id"] is None
            assert sample["ovary_side"] == "UNKNOWN" and sample["dataset_split"] == "Validation"
            assert "max_diameter_mm" not in sample and "patient_age" not in sample
            image = client.get(sample["image_url"])
            assert image.status_code == 200
            assert cv2.imdecode(np.frombuffer(image.content, np.uint8), cv2.IMREAD_GRAYSCALE) is not None
        assert client.get("/api/samples/unknown/image").status_code == 404
        assert client.get("/api/samples/%2e%2e%2fsecret/image").status_code == 404


def test_new_endpoints_require_authentication():
    with TestClient(app) as client:
        assert client.get("/api/samples").status_code == 401
        assert client.get("/api/samples/demo/image").status_code == 401
        assert client.get("/api/images/image/source.png").status_code == 401
        assert client.post("/api/images/image/measurements", json={"rle_mask": {}}).status_code == 401


def test_registry_exposes_only_loaded_engine_checksum_and_threshold():
    from backend.app.config import model_registry

    adapter = model_registry.get_primary_adapter()
    info = adapter.get_info()
    assert adapter.is_loaded
    assert info["checksum"] == adapter.engine.model_checksum and len(info["checksum"]) == 64
    assert info["threshold"] == adapter.engine.threshold
    for adapter in model_registry.adapters.values():
        if not adapter.is_loaded:
            assert adapter.get_info()["checksum"] is None
            assert adapter.get_info()["threshold"] is None


def test_admin_latency_uses_only_positive_database_observations(source_case, monkeypatch):
    from backend.app.routers.auth import get_current_user

    client, engine, rle, _ = source_case
    assert client.get("/api/admin/models").status_code == 403
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: UserModel(
        id="test-admin", username="admin", full_name="Test Admin", role="ADMIN",
    ))
    with Session(engine) as db:
        db.get(PredictionModel, "prediction").inference_time_ms = 120
        for prediction_id, duration in (("another", 240), ("not-measured", 0), ("invalid", -30)):
            db.add(PredictionModel(id=prediction_id, image_id="image", raw_mask_rle=rle,
                                   measurements={}, inference_time_ms=duration))
        db.commit()
    result = client.get("/api/admin/models")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["mean_inference_latency_ms"] == 180.0 and data["latency_sample_count"] == 2
    assert data["latency_scope"] == "all_recorded_predictions"
    assert data["latency_filter"] == "inference_time_ms > 0"
    assert data["latency_model_version"] is None
    assert data["registered_models"][0]["checksum"]
    with Session(engine) as db:
        db.query(PredictionModel).update({PredictionModel.inference_time_ms: 0})
        db.commit()
    data = client.get("/api/admin/models").json()
    assert data["mean_inference_latency_ms"] is None and data["latency_sample_count"] == 0


def test_feedback_migration_is_idempotent_and_preserves_old_rows(tmp_path, monkeypatch):
    from backend.db import database

    path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE reviews DROP COLUMN hitl_feedback")
        db.execute("INSERT INTO reviews(id, image_id, verified_mask_rle) VALUES ('legacy', 'image', '{}')")
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    database.init_db()
    database.init_db()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT hitl_feedback FROM reviews WHERE id='legacy'").fetchone() == (None,)
        columns = [row[1] for row in db.execute("PRAGMA table_info(reviews)")]
        assert columns.count("hitl_feedback") == 1
    engine.dispose()


def test_review_rejects_mismatched_study_even_for_single_image(source_case):
    client, engine, rle, _ = source_case
    with Session(engine) as db:
        db.add(StudyModel(id="another-study", patient_id="patient", study_date="2026-10-08", review_revision=0))
        db.commit()
    response = client.post("/api/review", json={
        "study_id": "another-study", "image_id": "image", "prediction_id": "prediction",
        "verified_mask_rle": rle, "expected_revision": 0, "request_id": f"req-ext-{uuid.uuid4()}",
    })
    assert response.status_code == 422
    assert response.json()["detail"] == "Ảnh không thuộc ca khảo sát."
    with Session(engine) as db:
        assert db.query(ReviewModel).count() == 0


@pytest.mark.parametrize("spacing", ["0", "-0.2", "nan", "inf"])
def test_calibration_rejects_nonpositive_or_nonfinite_spacing(source_case, spacing):
    client, engine, _, _ = source_case
    response = client.post(f"/api/images/image/calibrate?pixel_spacing_mm={spacing}")
    assert response.status_code == 422
    with Session(engine) as db:
        assert db.get(ImageModel, "image").pixel_spacing_mm is None


@pytest.mark.parametrize("spacing", ["0", "-0.2", "nan", "inf"])
def test_prediction_rejects_invalid_spacing_before_inference(source_case, spacing, monkeypatch):
    from backend.app.routers import inference

    _, engine, _, _ = source_case
    monkeypatch.setattr(inference.preprocessor, "validate_ultrasound_suitability", lambda _image: {"is_suitable": True})
    def unexpected_preprocessing(_image):
        raise RuntimeError("preprocessing ran")
    monkeypatch.setattr(inference.preprocessor, "preprocess_for_inference", unexpected_preprocessing)
    with Session(engine) as db:
        with pytest.raises(HTTPException) as error:
            inference.run_ai_prediction("image", pixel_spacing_mm=float(spacing), db=db)
        assert error.value.status_code == 422
    with Session(engine) as db:
        assert db.get(ImageModel, "image").pixel_spacing_mm is None
        assert db.query(PredictionModel).count() == 1


@pytest.mark.parametrize("spacing", ["0", "-0.2", "nan", "inf"])
def test_upload_rejects_invalid_spacing_before_writing(source_case, spacing):
    client, engine, _, source = source_case
    new_source = source.copy()
    new_source[30, 30] = 111
    encoded, image = cv2.imencode(".png", new_source)
    assert encoded
    response = client.post("/api/upload", data={"study_id": "study", "pixel_spacing_mm": spacing},
                           files={"file": ("new.png", image.tobytes(), "image/png")})
    assert response.status_code == 422
    with Session(engine) as db:
        assert db.query(ImageModel).count() == 1


@pytest.mark.parametrize("spacing", [0.0, float("inf")])
def test_v1_segmentation_rejects_invalid_manual_spacing(source_case, spacing, monkeypatch):
    from backend.app.routers import v1_endpoints

    _, engine, _, source = source_case
    encoded, image = cv2.imencode(".png", source)
    assert encoded
    monkeypatch.setattr(v1_endpoints.preprocessor, "validate_ultrasound_suitability", lambda _image: {"is_suitable": True})
    def unexpected_preprocessing(_image):
        raise RuntimeError("preprocessing ran")
    monkeypatch.setattr(v1_endpoints.preprocessor, "preprocess_for_inference", unexpected_preprocessing)
    with Session(engine) as db:
        with pytest.raises(HTTPException) as error:
            asyncio.run(v1_endpoints.segment_image_v1(
                file=UploadFile(filename="source.png", file=BytesIO(image.tobytes())),
                pixel_spacing_mm=spacing, db=db,
            ))
        assert error.value.status_code == 422


@pytest.mark.parametrize("stored", [0.0, -1.0, float("nan"), float("inf")])
def test_prediction_treats_legacy_invalid_spacing_as_uncalibrated(source_case, stored, monkeypatch):
    from backend.app.routers import inference

    _, engine, _, _ = source_case
    with Session(engine) as db:
        db.get(ImageModel, "image").pixel_spacing_mm = stored
        db.commit()
    monkeypatch.setattr(inference.preprocessor, "validate_ultrasound_suitability", lambda _image: {"is_suitable": True})
    monkeypatch.setattr(inference.preprocessor, "preprocess_for_inference",
                        lambda _image: (None, np.zeros((512, 512), np.uint8), {}, {"iqa_score": 0.9}))
    received = []
    def capture_spacing(*_args, **kwargs):
        received.append(kwargs["pixel_spacing_mm"])
        raise RuntimeError("captured")
    monkeypatch.setattr(inference.model_registry, "predict", capture_spacing)
    with Session(engine) as db:
        with pytest.raises(RuntimeError, match="captured"):
            inference.run_ai_prediction("image", db=db)
    assert received == [None]
