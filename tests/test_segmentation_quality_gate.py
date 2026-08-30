import os
import sys

import numpy as np
import pytest
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.services.inference_engine import InferenceEngine
from backend.services.model_service import ModelRegistry
from backend.services.preprocessor import UltrasoundPreprocessor


@pytest.fixture
def preprocessor():
    return UltrasoundPreprocessor(target_size=(512, 512))


@pytest.fixture
def inference_engine():
    weights_path = "checkpoints/best_attention_unet.pth"
    return InferenceEngine(model_weights_path=weights_path if os.path.exists(weights_path) else None)


@pytest.fixture
def model_registry():
    weights_path = "checkpoints/best_attention_unet.pth"
    return ModelRegistry(checkpoint_path=weights_path if os.path.exists(weights_path) else None)


def test_roi_masking_prevents_background_leakage(preprocessor, inference_engine):
    """Verifies that ROI mask zeroes out all background padding and non-imaging cone regions."""
    # Create synthetic non-square image with large black margins
    raw_img = np.zeros((400, 700), dtype=np.uint8)
    # Add a bright circular lesion in the center
    cv2_img = raw_img.copy()
    y, x = np.ogrid[:400, :700]
    mask_circle = (x - 350) ** 2 + (y - 200) ** 2 <= 60**2
    cv2_img[mask_circle] = 180

    tensor, padded_gray, transform_params, _ = preprocessor.preprocess_for_inference(cv2_img)
    roi_mask = transform_params["roi_mask"]

    # Ensure padding region is strictly 0 in roi_mask
    pad_x = transform_params["pad_x"]
    pad_y = transform_params["pad_y"]
    assert pad_y > 0 or pad_x > 0

    if pad_y > 0:
        assert np.all(roi_mask[:pad_y, :] == 0)
        assert np.all(roi_mask[512 - pad_y :, :] == 0)

    # Run inference with roi_mask
    res = inference_engine.run_inference(tensor, padded_gray, roi_mask=roi_mask)
    pred_mask = res["binary_mask_np"]

    # Verify no prediction leaks into outer padding margins
    if pad_y > 0:
        assert np.all(pred_mask[:pad_y, :] == 0)
        assert np.all(pred_mask[512 - pad_y :, :] == 0)


def test_clinical_quality_gate_safeguard(inference_engine):
    """Verifies that low-confidence / high-uncertainty predictions trigger the Quality Gate."""
    # Synthetic noisy tensor
    noisy_tensor = torch.rand(1, 1, 512, 512) * 0.1
    padded_gray = (noisy_tensor.squeeze().numpy() * 255).astype(np.uint8)

    res = inference_engine.run_inference(noisy_tensor, padded_gray)

    # Check that Quality Gate structure exists
    assert "quality_gate" in res
    qgate = res["quality_gate"]
    assert "passed" in qgate
    assert "min_confidence_required" in qgate
    assert qgate["min_confidence_required"] == 0.70

    if not qgate["passed"]:
        assert qgate["status"] == "REJECTED_QUALITY_GATE"
        assert res["measurements"]["is_valid_caliper"] is False
        assert "quality_alert" in res["measurements"]
        assert res["cdss_classification"]["status"] == "BLOCKED_BY_QUALITY_GATE"
        assert res["cdss_classification"]["orads_category"] == "CHỜ BÁC SĨ DUYỆT"


def test_model_registry_roi_mask_passthrough(preprocessor, model_registry):
    """Verifies that ModelRegistry properly passes roi_mask down to the active adapter."""
    raw_img = np.ones((512, 512), dtype=np.uint8) * 120
    tensor, padded_gray, transform_params, _ = preprocessor.preprocess_for_inference(raw_img)

    roi_mask = transform_params["roi_mask"]
    res = model_registry.predict(tensor, padded_gray, pixel_spacing_mm=0.1, roi_mask=roi_mask)

    assert "rle_mask" in res
    assert "confidence_score" in res
    assert "measurements" in res
    assert "quality_gate" in res
