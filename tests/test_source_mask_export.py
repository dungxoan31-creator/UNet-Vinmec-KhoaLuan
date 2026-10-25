"""Exported AI and reviewed masks use the decoded source image coordinates."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, ImageModel, PatientModel, PredictionModel, ReviewModel, StudyModel, get_db
from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor

pytestmark = pytest.mark.usefixtures("doctor_access")


def test_export_reviewed_mask_at_original_resolution(tmp_path):
    from backend.app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'masks.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    source = np.zeros((300, 500), dtype=np.uint8)
    source[30:270, 40:460] = 100
    image_path = tmp_path / "source.png"
    assert cv2.imwrite(str(image_path), source)
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    raw_mask = np.zeros_like(source)
    raw_mask[100:150, 100:150] = 1
    reviewed_mask = np.zeros_like(source)
    reviewed_mask[100:150, 300:350] = 1
    raw_512, _ = preprocessor.letterbox_resize(raw_mask, is_mask=True)
    reviewed_512, _ = preprocessor.letterbox_resize(reviewed_mask, is_mask=True)

    with Session(engine) as db:
        db.add(PatientModel(id="patient", anonymized_pid="TEST-MASK-EXPORT"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-08"))
        db.add(ImageModel(id="image", study_id="study", filename="source.png", raw_path=str(image_path), width=500, height=300))
        db.add(PredictionModel(id="prediction", image_id="image", raw_mask_rle=InferenceEngine.mask_to_rle(raw_512), measurements={}))
        db.add(ReviewModel(id="review", image_id="image", prediction_id="prediction", verified_mask_rle=InferenceEngine.mask_to_rle(reviewed_512)))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            reviewed = client.get("/api/images/image/mask.png?kind=reviewed")
            raw = client.get("/api/images/image/mask.png?kind=ai")
            uncalibrated = client.post("/api/v1/segment?image_id=image")
        assert reviewed.status_code == 200
        assert raw.status_code == 200
        assert uncalibrated.status_code == 200, uncalibrated.text
        assert uncalibrated.json()["provenance"]["pixel_spacing_mm"] is None
        assert uncalibrated.json()["measurements"]["max_diameter_mm"] is None
        reviewed_png = cv2.imdecode(np.frombuffer(reviewed.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        raw_png = cv2.imdecode(np.frombuffer(raw.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        assert reviewed_png.shape == raw_png.shape == source.shape
        assert reviewed_png[125, 325] == 255 and reviewed_png[125, 125] == 0
        assert raw_png[125, 125] == 255 and raw_png[125, 325] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
