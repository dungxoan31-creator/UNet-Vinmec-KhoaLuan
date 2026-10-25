import hashlib
import json
from pathlib import Path

from backend.app.config import selected_checkpoint_path


def test_selected_checkpoint_requires_matching_checksum(tmp_path):
    checkpoint = tmp_path / "vinmec_unet_best.pth"
    checkpoint.write_bytes(b"selected weights")
    manifest = tmp_path / "selected_model.json"
    manifest.write_text(
        json.dumps(
            {
                "checkpoint": str(checkpoint),
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "threshold": 0.5,
            }
        ),
        encoding="utf-8",
    )

    assert selected_checkpoint_path(manifest) == str(checkpoint)
    checkpoint.write_bytes(b"changed weights")
    assert selected_checkpoint_path(manifest) is None


def test_prototype_uses_validation_selected_research_checkpoint_without_stale_test_claim():
    root = Path(__file__).resolve().parents[1]
    manifest = root / "evaluation/selected_model.json"
    selection = json.loads(manifest.read_text(encoding="utf-8"))
    checkpoint = root / selection["checkpoint"]

    assert selection["selection_split"] == "val"
    assert selection["selection_count"] == 541
    assert selection["threshold"] == 0.4
    assert selection["horizontal_flip_tta"] is True
    assert selection["selection_is_validation_tuned"] is True
    assert selection["architecture"] == "unetplusplus_resnet34"
    assert selection["source_patient_identity_verified"] is False
    assert selection["independent_test_status"] == "BLOCKED"
    assert selection["independent_gate_status"] == "BLOCKED"
    assert selection["test_evaluation"] is None
    benchmark = selection["synthetic_test_benchmark"]
    assert benchmark["benchmark_tag"] == "[SIMULATED - TECHNICAL BENCHMARK ONLY]"
    assert benchmark["patient_independence_verified"] is False
    assert benchmark["source_patient_identity_verified"] is False
    assert benchmark["label_provenance_verified"] is False
    assert checkpoint.is_file()
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == selection["checkpoint_sha256"]
    assert selected_checkpoint_path(manifest) == str(checkpoint)


def test_model_registry_passes_selected_flip_tta_to_inference_engine(monkeypatch):
    from backend.services import model_service

    captured = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.device = kwargs.get("device", "cpu")
            self.model_name = "U-Net++ test"
            self.architecture_name = "U-Net++ test"
            self.is_model_ready = False

    monkeypatch.setattr(model_service, "InferenceEngine", FakeEngine)
    model_service.AttentionUNetAdapter(
        architecture="unetplusplus_resnet34",
        input_normalization={"mean": 0.449, "std": 0.226},
        threshold=0.4,
        horizontal_flip_tta=True,
    )

    assert captured["horizontal_flip_tta"] is True
    assert captured["threshold"] == 0.4


def test_model_registry_passes_manifest_hash_to_inference_engine(monkeypatch, tmp_path):
    from backend.services import model_service

    captured = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.device = kwargs.get("device", "cpu")
            self.model_name = "U-Net test"
            self.architecture_name = "U-Net test"
            self.is_model_ready = False

    monkeypatch.setattr(model_service, "InferenceEngine", FakeEngine)
    model_service.ModelRegistry(
        checkpoint_path=str(tmp_path / "selected.pth"),
        model_selection={"checkpoint_sha256": "a" * 64},
    )

    assert captured["expected_checkpoint_sha256"] == "a" * 64


def test_model_registry_passes_manifest_version_to_inference_engine(monkeypatch):
    from backend.services import model_service

    captured = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.device = kwargs.get("device", "cpu")
            self.model_name = "U-Net++ test"
            self.architecture_name = "U-Net++ test"
            self.is_model_ready = False

    monkeypatch.setattr(model_service, "InferenceEngine", FakeEngine)
    model_service.ModelRegistry(
        model_selection={"architecture": "unetplusplus_resnet34", "model_version": "candidate-build-2026-10-19"}
    )

    assert captured["model_version"] == "candidate-build-2026-10-19"


def test_inference_provenance_uses_selected_model_version(monkeypatch):
    import numpy as np
    import torch

    from backend.services import inference_engine

    monkeypatch.setattr(inference_engine, "_build_model", lambda _kind, _device: torch.nn.Identity())
    engine = inference_engine.InferenceEngine(device="cpu", model_version="candidate-build-2026-10-19")
    monkeypatch.setattr(engine, "forward_probabilities", lambda _tensor: np.zeros((512, 512), dtype=np.float32))
    monkeypatch.setattr(
        engine,
        "calculate_uncertainty",
        lambda _probs, _mask: {"is_uncertain": False, "uncertainty_level": "LOW"},
    )
    monkeypatch.setattr(
        engine,
        "extract_calipers_and_measurements",
        lambda *_args, **_kwargs: {"lesions": [], "filtered_components": []},
    )
    monkeypatch.setattr(engine, "generate_overlay_base64", lambda *_args, **_kwargs: "data:image/png;base64,test")

    result = engine.run_inference(torch.zeros((1, 1, 512, 512)), np.zeros((512, 512), dtype=np.uint8))

    assert result["provenance"]["model_version"] == "candidate-build-2026-10-19"


def test_inference_engine_does_not_construct_unused_morphology_extractor(monkeypatch):
    import torch

    from backend.services import inference_engine

    def unused_extractor_must_not_be_constructed():
        raise AssertionError("The serving path must not construct an unused extractor")

    monkeypatch.setattr(
        inference_engine,
        "MorphologicalFeatureExtractor",
        unused_extractor_must_not_be_constructed,
        raising=False,
    )
    monkeypatch.setattr(inference_engine.InferenceEngine, "_build_on_selected_device", lambda *_args: torch.nn.Identity())

    engine = inference_engine.InferenceEngine(device="cpu")

    assert engine.is_model_ready is False
