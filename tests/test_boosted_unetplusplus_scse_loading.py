import os

import pytest
import torch

from backend.services.inference_engine import InferenceEngine


def test_inference_engine_loads_scse_checkpoint():
    ckpt_path = "checkpoints/boosted_unetplusplus_scse_2026-10-27/boosted_resnet34_scse_best.pth"
    if not os.path.exists(ckpt_path):
        pytest.skip(f"Checkpoint not found at {ckpt_path}")

    engine = InferenceEngine(
        model_weights_path=ckpt_path,
        device="cpu",
        architecture="unetplusplus_resnet34_scse",
        horizontal_flip_tta=True,
        threshold=0.40,
        expected_checkpoint_sha256="67624bbb0e50e236df7b5c82736eaadab1ff1fff5547c5e813bca545c2dd2045",
    )

    assert engine.is_model_ready is True
    assert engine.decoder_attention_type == "scse"
    assert "scSE" in engine.architecture_name

    # Check forward pass produces correct dimensions
    dummy_input = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    probs = engine.forward_probabilities(dummy_input)
    assert probs.shape == (512, 512)
    assert float(probs.min()) >= 0.0 and float(probs.max()) <= 1.0


def test_inference_engine_loads_baseline_checkpoint_without_scse():
    ckpt_path = "checkpoints/unetplusplus_resnet34_2026-10-06/unetplusplus_resnet34_best.pth"
    if not os.path.exists(ckpt_path):
        pytest.skip(f"Checkpoint not found at {ckpt_path}")

    engine = InferenceEngine(
        model_weights_path=ckpt_path,
        device="cpu",
        architecture="unetplusplus_resnet34",
        horizontal_flip_tta=True,
        threshold=0.40,
        expected_checkpoint_sha256="ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76",
    )

    assert engine.is_model_ready is True
    assert engine.decoder_attention_type is None
    assert engine.architecture_name == "U-Net++ (ResNet34 ImageNet)"

    dummy_input = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    probs = engine.forward_probabilities(dummy_input)
    assert probs.shape == (512, 512)
    assert float(probs.min()) >= 0.0 and float(probs.max()) <= 1.0
