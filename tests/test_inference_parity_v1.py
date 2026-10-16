"""Tests for Inference Parity and Serving/Evaluation forward sharing."""

import numpy as np
import pytest
import torch
import torch.nn as nn

from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor


class DummyModel(nn.Module):
    def __init__(self, logits_value: float = 0.0):
        super().__init__()
        self.logits_value = logits_value
        self.forward_count = 0

    def forward(self, x):
        self.forward_count += 1
        # Return constant logits of shape (B, 1, 512, 512)
        out = torch.full((x.shape[0], 1, 512, 512), self.logits_value, dtype=torch.float32, device=x.device)
        return out


def test_threshold_includes_half():
    # Sigmoid(0.0) == 0.5. With threshold=0.5 and operator >=, it must be included (value 1)
    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=0.0)
    engine.is_model_ready = True

    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    binary_mask = engine.predict_binary(dummy_tensor)

    assert binary_mask.shape == (512, 512)
    assert np.all(binary_mask == 1), "Probability 0.5 must be included in binary mask (threshold >= 0.5)"

    # Test probability slightly below 0.5 -> logits < 0 -> output 0
    engine.model = DummyModel(logits_value=-0.05)
    binary_mask_below = engine.predict_binary(dummy_tensor)
    assert np.all(binary_mask_below == 0), "Probability below 0.5 must not be included"


def test_prediction_uses_one_forward():
    engine = InferenceEngine(architecture="standard_unet")
    dummy_model = DummyModel(logits_value=1.0)
    engine.model = dummy_model
    engine.is_model_ready = True

    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    padded_gray = np.zeros((512, 512), dtype=np.uint8)

    # Calling run_inference should trigger forward exactly once
    res = engine.run_inference(dummy_tensor, padded_gray)
    assert dummy_model.forward_count == 1, f"Expected 1 forward pass, got {dummy_model.forward_count}"
    assert "binary_mask_np" in res
    assert res["binary_mask_np"].shape == (512, 512)


def test_unloaded_model_fails_closed():
    engine = InferenceEngine(architecture="standard_unet")
    engine.is_model_ready = False
    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)

    with pytest.raises(RuntimeError, match="not ready|unloaded"):
        engine.predict_binary(dummy_tensor)


def test_native_mask_and_service_parity():
    # Nonsquare image 640x479
    raw_img = np.zeros((479, 640), dtype=np.uint8)
    # Put a small rectangle
    raw_img[100:200, 150:250] = 200

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    tensor_512, padded_gray, transform, _ = preprocessor.preprocess_for_inference(raw_img)

    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=1.5)  # sigmoid > 0.5 -> all 1 in padded area
    engine.is_model_ready = True

    binary_512 = engine.predict_binary(tensor_512)
    native_mask = preprocessor.inverse_letterbox_mask(binary_512, transform)

    # Must match original image shape
    assert native_mask.shape == (479, 640)
    assert set(np.unique(native_mask).tolist()).issubset({0, 1})
    # Non-zero in valid region
    assert np.count_nonzero(native_mask) > 0


def test_monotonic_timing_fields(monkeypatch):
    import time
    engine = InferenceEngine(architecture="standard_unet")
    engine.model = DummyModel(logits_value=0.5)
    engine.is_model_ready = True

    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    padded_gray = np.zeros((512, 512), dtype=np.uint8)

    # Monotonic timing test with fake perf_counter:
    # forward: 0.0 -> 0.100 (100 ms)
    # pipeline: 0.0 -> 0.150 (150 ms)
    time_seq = [0.0, 0.100]
    monkeypatch.setattr(time, "perf_counter", lambda: time_seq.pop(0) if time_seq else 0.100)

    res = engine.run_inference(dummy_tensor, padded_gray)
    assert "timings" in res
    assert res["timings"]["model_forward_ms"] == 100.0

