import pytest
from pydantic import ValidationError

from backend.schemas.schemas import CaseConfirmRequest, DoctorReviewRequest
from backend.services.preprocessor import UltrasoundPreprocessor


def test_review_rejects_incomplete_mask():
    with pytest.raises(ValidationError):
        DoctorReviewRequest(
            image_id="image-1",
            prediction_id="prediction-1",
            verified_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [10]},
        )


def test_unvalidated_clinical_pdf_export_is_unavailable():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        response = client.post("/api/generate-report", json={})
    assert response.status_code == 501


def test_review_requires_prediction_id():
    with pytest.raises(ValidationError):
        DoctorReviewRequest(
            image_id="image-1",
            verified_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [512 * 512]},
        )


def test_v1_confirmation_reuses_mask_validation():
    with pytest.raises(ValidationError):
        CaseConfirmRequest(
            image_id="image-1",
            prediction_id="prediction-1",
            verified_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [10]},
        )


def test_baseline_threshold_keeps_small_regions():
    import numpy as np

    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.architecture_name = "Standard U-Net (Baseline)"
    probability = np.zeros((16, 16), dtype=np.float32)
    probability[2, 3] = 0.8
    prediction = engine.post_process_mask(probability)
    assert prediction.sum() == 1
    assert prediction[2, 3] == 1


def test_admin_overview_has_no_fabricated_benchmark():
    from backend.services.model_service import ModelRegistry

    registry = ModelRegistry.__new__(ModelRegistry)
    registry.adapters = {}
    registry.primary_model_key = "attention_unet"
    registry.fallback_model_key = "attention_unet"
    registry.ensemble_enabled = False
    overview = registry.get_admin_overview()
    assert overview["active_primary_model"] is None
    assert overview["fallback_model"] is None
    assert overview["test_set_dsc"] is None
    assert overview["test_set_iou"] is None
    assert overview["mean_inference_latency_ms"] is None


def test_admin_overview_reports_loaded_architecture_not_internal_key():
    from backend.app.config import model_registry

    adapter = model_registry.get_primary_adapter()
    assert adapter.is_loaded
    overview = model_registry.get_admin_overview()
    actual_architecture = adapter.engine.architecture_name
    assert overview["active_primary_model"] == actual_architecture
    assert overview["fallback_model"] == actual_architecture
    assert overview["registered_models"][0]["name"] == actual_architecture
    assert overview["registered_models"][0]["architecture"] == actual_architecture


def test_deployed_baseline_uses_one_forward_pass_and_no_roi_filter():
    import numpy as np
    import torch

    from backend.services.inference_engine import InferenceEngine

    class ConstantModel:
        calls = 0

        def __call__(self, tensor):
            self.calls += 1
            return torch.full_like(tensor, 2.0)

    class EmptyMorphology:
        def extract_features(self, *_args, **_kwargs):
            return {}

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.device = "cpu"
    engine.threshold = 0.5
    engine.architecture_name = "Standard U-Net (Baseline)"
    engine.model = ConstantModel()
    engine.morph_extractor = EmptyMorphology()
    engine.model_checksum = "test"
    engine.calculate_uncertainty = lambda *_args: {"is_uncertain": False, "uncertainty_level": "LOW"}
    engine.extract_calipers_and_measurements = lambda *_args, **_kwargs: {}
    engine.generate_overlay_base64 = lambda *_args: ""

    result = engine.run_inference(
        torch.zeros((1, 1, 8, 8)), np.zeros((8, 8), dtype=np.uint8), roi_mask=np.zeros((8, 8), dtype=np.uint8)
    )
    assert engine.model.calls == 1
    assert result["binary_mask_np"].sum() == 64


def test_dashboard_counts_only_database_records():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.health import get_dashboard_statistics
    from backend.db.database import Base, ImageModel, PatientModel, ReviewModel, StudyModel

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        empty = get_dashboard_statistics(db)
        assert empty["total_cases_received"] == 0
        assert empty["doctor_approved_cases"] == 0
        db.add(PatientModel(id="patient-1", anonymized_pid="test-patient"))
        study = StudyModel(id="study-1", patient_id="patient-1", study_date="2026-09-29")
        db.add(study)
        db.commit()
        one_case = get_dashboard_statistics(db)
        assert one_case["total_cases_received"] == 1
        assert one_case["pending_evaluation_cases"] == 1
        study.status = "REVIEWED"
        db.add(ImageModel(id="image-1", study_id="study-1", filename="sample.png", raw_path="sample.png"))
        db.add(
            ReviewModel(
                id="review-1",
                image_id="image-1",
                doctor_id="UNVERIFIED_REVIEWER",
                doctor_action="ACCEPTED_RAW",
                verified_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [512 * 512]},
                time_spent_seconds=17,
                is_official_ground_truth=False,
            )
        )
        db.commit()
        simulated = get_dashboard_statistics(db)
        assert simulated["doctor_approved_cases"] == 0
        assert simulated["ground_truth_confirmed"] == 0
        assert simulated["ai_consensus_rate_pct"] == 0.0
        assert simulated["average_review_time_seconds"] == 0.0
        db.get(ReviewModel, "review-1").is_official_ground_truth = True
        db.commit()
        official_fixture = get_dashboard_statistics(db)
        assert official_fixture["doctor_approved_cases"] == 1
        assert official_fixture["ground_truth_confirmed"] == 1
        assert official_fixture["ai_consensus_rate_pct"] == 100.0
        assert official_fixture["average_review_time_seconds"] == 17.0


def test_inference_uses_training_clahe_pipeline():
    import numpy as np

    image = np.arange(512 * 512, dtype=np.uint8).reshape(512, 512)
    preprocessor = UltrasoundPreprocessor()
    tensor, _, _, _ = preprocessor.preprocess_for_inference(image)
    expected = preprocessor.clahe.apply(image).astype(np.float32) / 255.0
    np.testing.assert_array_equal(tensor.squeeze().numpy(), expected)


def test_predict_rejects_missing_checkpoint(monkeypatch):
    from fastapi import HTTPException

    from backend.app.config import model_registry
    from backend.app.routers.inference import run_ai_prediction

    adapter = model_registry.get_primary_adapter()
    monkeypatch.setattr(adapter, "is_loaded", False)
    with pytest.raises(HTTPException) as error:
        run_ai_prediction("image-1", db=None)
    assert error.value.status_code == 503


def test_review_stores_final_mask_and_prediction_link():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.reviews import submit_doctor_review
    from backend.db.database import Base, ImageModel, PatientModel, PredictionModel, ReviewModel, StudyModel

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    mask = {"shape": [512, 512], "first_val": 0, "counts": [512 * 512]}
    with Session(engine) as db:
        db.add(PatientModel(id="patient-1", anonymized_pid="test-patient"))
        db.add(StudyModel(id="study-1", patient_id="patient-1", study_date="2026-09-29"))
        db.add(ImageModel(id="image-1", study_id="study-1", filename="test.png", raw_path="test.png"))
        db.add(PredictionModel(id="prediction-1", image_id="image-1", raw_mask_rle=mask, measurements={}))
        db.commit()

        request = DoctorReviewRequest(image_id="image-1", prediction_id="prediction-1", verified_mask_rle=mask)
        result = submit_doctor_review(request, db)
        saved = db.query(ReviewModel).filter(ReviewModel.id == result["review_id"]).one()
        assert saved.prediction_id == "prediction-1"
        assert saved.verified_mask_rle == mask

        request.prediction_id = "another-prediction"
        with pytest.raises(Exception) as error:
            submit_doctor_review(request, db)
        assert error.value.status_code == 404
