"""
Unit & integration tests for Task 11 (R9 P3): Payload Pruning & Optional overlay_base64.
Verifies:
1. InferenceResponse / PredictionResponse accepts None for overlay_base64 and original_image_base64.
2. InferenceEngine.run_inference respects generate_overlay=False (bypasses CPU-heavy PNG rendering).
3. Backward compatibility is preserved (defaults to generate_overlay=True).
4. Router endpoint supports optional overlay generation via query parameters.
"""

from unittest.mock import MagicMock
import numpy as np
import pytest
import torch
import torch.nn as nn

from backend.schemas.schemas import InferenceResponse, PredictionResponse
from backend.services.inference_engine import InferenceEngine


class DummyModel(nn.Module):
    def __init__(self, logits_value: float = 0.0):
        super().__init__()
        self.logits_value = logits_value

    def forward(self, x):
        return torch.full((x.shape[0], 1, 512, 512), self.logits_value, dtype=torch.float32, device=x.device)


def _minimal_prediction_dict(**overrides):
    base = {
        "image_id": "test-img-001",
        "filename": "test_image.png",
        "confidence_score": 0.95,
        "inference_time_ms": 42,
        "iqa": {
            "iqa_score": 0.88,
            "laplacian_variance": 100.0,
            "contrast_std": 45.0,
            "shadow_ratio": 0.05,
            "flags": [],
            "is_acceptable": True,
            "message": "Ảnh đủ điều kiện phân tích.",
        },
        "measurements": {
            "has_lesion": False,
            "lesions": [],
            "max_diameter_mm": None,
            "ortho_diameter_mm": None,
            "d3_mm": None,
            "total_volume_cm3": None,
            "total_area_cm2": None,
            "total_lesions": 0,
            "calibrated": False,
        },
        "rle_mask": {"shape": [512, 512], "first_val": 0, "counts": [262144]},
        "overlay_base64": None,
        "original_image_base64": None,
    }
    base.update(overrides)
    return base


def test_schema_allows_none_overlay_and_original_image():
    """Verify InferenceResponse allows overlay_base64=None and original_image_base64=None."""
    payload = _minimal_prediction_dict(overlay_base64=None, original_image_base64=None)
    response = InferenceResponse.model_validate(payload)
    assert response.overlay_base64 is None
    assert response.original_image_base64 is None

    # Defaults should be None if omitted
    omitted = _minimal_prediction_dict()
    omitted.pop("overlay_base64")
    omitted.pop("original_image_base64")
    response_omitted = InferenceResponse.model_validate(omitted)
    assert response_omitted.overlay_base64 is None
    assert response_omitted.original_image_base64 is None


def test_schema_backward_compatibility_with_string_base64():
    """Verify backward compatibility when base64 strings are provided."""
    payload = _minimal_prediction_dict(
        overlay_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
        original_image_base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
    )
    response = InferenceResponse.model_validate(payload)
    assert response.overlay_base64 == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="
    assert response.original_image_base64 == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="


def test_inference_engine_allows_omitting_overlay_base64():
    """When generate_overlay=False, run_inference returns overlay_base64=None and skips PNG render."""
    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=0.5)
    engine.is_model_ready = True

    tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    padded_gray = np.zeros((512, 512), dtype=np.uint8)

    # Calling with generate_overlay=False
    result = engine.run_inference(tensor, padded_gray, generate_overlay=False)

    assert result["overlay_base64"] is None
    assert "rle_mask" in result
    assert "confidence_score" in result
    assert "cdss_classification" in result
    assert "measurements" in result
    assert "uncertainty" in result
    assert "quality_gate" in result


def test_inference_engine_skips_generate_overlay_call(monkeypatch):
    """Verify generate_overlay_base64 is not called when generate_overlay=False."""
    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=0.5)
    engine.is_model_ready = True

    mock_overlay = MagicMock()
    monkeypatch.setattr(engine, "generate_overlay_base64", mock_overlay)

    tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    padded_gray = np.zeros((512, 512), dtype=np.uint8)

    # 1. With generate_overlay=False -> should NOT call
    res_false = engine.run_inference(tensor, padded_gray, generate_overlay=False)
    assert res_false["overlay_base64"] is None
    mock_overlay.assert_not_called()

    # 2. With generate_overlay=True -> SHOULD call
    mock_overlay.return_value = "data:image/png;base64,mocked"
    res_true = engine.run_inference(tensor, padded_gray, generate_overlay=True)
    assert res_true["overlay_base64"] == "data:image/png;base64,mocked"
    assert mock_overlay.call_count == 1


def test_inference_engine_defaults_to_generating_overlay():
    """Verify backward compatibility: generate_overlay defaults to True when unspecified."""
    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=0.5)
    engine.is_model_ready = True

    tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    padded_gray = np.zeros((512, 512), dtype=np.uint8)

    result = engine.run_inference(tensor, padded_gray)
    assert result["overlay_base64"] is not None
    assert result["overlay_base64"].startswith("data:image/png;base64,")


def test_router_run_ai_prediction_parameter_signature():
    """Verify inference router has parameter support for skipping overlay generation."""
    import inspect
    from backend.app.routers import inference

    sig = inspect.signature(inference.run_ai_prediction)
    assert "generate_overlay" in sig.parameters or "include_overlay" in sig.parameters


def test_router_predict_with_generate_overlay_false(tmp_path, monkeypatch, active_case_lease):
    """End-to-end integration test: router respects generate_overlay=false and defaults to true."""
    from fastapi import Depends
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.app import security
    from backend.app.main import app
    from backend.app.routers import auth, inference
    from backend.db.database import Base, FacilityModel, UserModel, get_db
    from tests.test_vinmec_api_smoke import synthetic_fixture_image

    image_path = synthetic_fixture_image()
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'r9_test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(db_engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    fac = FacilityModel(id="fac-r9", facility_code="FAC-R9", name="Hospital R9", is_active=True)
    doc = UserModel(
        id="test-doctor-r9",
        username="doctor_r9",
        full_name="Test Doctor R9",
        role="DOCTOR",
        facility_id="fac-r9",
        is_active=True,
    )
    with Session(db_engine) as db:
        db.add(fac)
        db.add(doc)
        db.commit()

    def temporary_db():
        with Session(db_engine) as db:
            yield db

    def mock_current_user(db: Session = Depends(get_db)):
        return db.query(UserModel).filter(UserModel.id == "test-doctor-r9").first()

    app.dependency_overrides[get_db] = temporary_db
    app.dependency_overrides[auth.get_current_user] = mock_current_user
    app.dependency_overrides[inference.get_current_user] = mock_current_user
    app.dependency_overrides[security.get_current_user] = mock_current_user
    try:
        with TestClient(app) as client:
            with image_path.open("rb") as image:
                uploaded = client.post("/api/upload", files={"file": (image_path.name, image, "image/png")})
            assert uploaded.status_code == 200, uploaded.text
            image_id = uploaded.json()["image_id"]
            study_id = uploaded.json()["study_id"]
            with Session(db_engine) as db:
                s = db.get(inference.StudyModel, study_id)
                if s:
                    s.facility_id = "fac-r9"
                    db.commit()
            lease = active_case_lease(client, study_id)
            lease_headers = {
                "X-Case-Lease-Token": lease["lease_token"],
                "X-Case-Page-Instance-Id": lease["page_instance_id"],
            }

            # 1. When generate_overlay=false -> overlay_base64 is None
            predicted = client.post(f"/api/predict/{image_id}?generate_overlay=false", headers=lease_headers)
            assert predicted.status_code == 200, predicted.text
            prediction = predicted.json()
            assert prediction["overlay_base64"] is None
            assert prediction["rle_mask"] is not None

            # 2. Upload a second image to test default generate_overlay=true
            with image_path.open("rb") as image:
                uploaded2 = client.post("/api/upload", files={"file": (image_path.name, image, "image/png")})
            image_id2 = uploaded2.json()["image_id"]
            study_id2 = uploaded2.json()["study_id"]
            with Session(db_engine) as db:
                s2 = db.get(inference.StudyModel, study_id2)
                if s2:
                    s2.facility_id = "fac-r9"
                    db.commit()
            lease2 = active_case_lease(client, study_id2)
            lease_headers2 = {
                "X-Case-Lease-Token": lease2["lease_token"],
                "X-Case-Page-Instance-Id": lease2["page_instance_id"],
            }

            predicted2 = client.post(f"/api/predict/{image_id2}", headers=lease_headers2)
            assert predicted2.status_code == 200, predicted2.text
            prediction2 = predicted2.json()
            assert prediction2["overlay_base64"] is not None
            assert prediction2["overlay_base64"].startswith("data:image/png;base64,")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth.get_current_user, None)
        app.dependency_overrides.pop(inference.get_current_user, None)
        app.dependency_overrides.pop(security.get_current_user, None)
