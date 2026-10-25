import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest
import torch


class _CudaUnavailableModel(torch.nn.Module):
    def to(self, device):
        if str(device) == "cuda":
            raise RuntimeError("CUDA device unavailable")
        return super().to(device)


def test_model_initialization_falls_back_to_cpu_when_cuda_allocation_fails(monkeypatch):
    from backend.services import inference_engine

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(inference_engine, "AttentionUNet", lambda **_: _CudaUnavailableModel())

    engine = inference_engine.InferenceEngine(architecture="attention_unet")

    assert engine.device == "cpu"
    assert "CUDA" in engine.device_fallback_reason


def test_checkpoint_transfer_falls_back_to_cpu_on_cuda_oom(monkeypatch, tmp_path):
    from backend.services import inference_engine

    class OomOnCudaModel(torch.nn.Module):
        def load_state_dict(self, _state_dict, strict=True):
            if self.target_device == "cuda":
                raise RuntimeError("CUDA out of memory while loading weights")
            return None

        def to(self, device):
            self.target_device = str(device)
            return self

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(inference_engine, "AttentionUNet", lambda **_: OomOnCudaModel())
    monkeypatch.setattr(
        inference_engine,
        "_load_verified_checkpoint",
        lambda *_args, **_kwargs: ("a" * 64, {"weight": torch.tensor(1.0)}),
    )
    checkpoint = tmp_path / "weights.pth"
    checkpoint.write_bytes(b"test checkpoint")

    engine = inference_engine.InferenceEngine(
        model_weights_path=checkpoint,
        architecture="attention_unet",
        expected_checkpoint_sha256="a" * 64,
    )

    assert engine.device == "cpu"
    assert engine.is_model_ready is True
    assert engine.model.target_device == "cpu"


class _FailsOnceOnCuda(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def forward(self, tensor):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("CUDA out of memory")
        return torch.zeros_like(tensor)


def _fake_engine(model):
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.device = "cuda"
    engine.is_model_ready = True
    engine.horizontal_flip_tta = False
    engine.model = model
    engine._device_condition = threading.Condition()
    engine._active_cuda_inferences = 0
    engine._device_transition = False
    engine.prepare_model_input = lambda tensor: tensor
    engine.device_fallback_reason = None
    return engine


def test_cuda_inference_failure_retries_same_model_on_cpu(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    model = _FailsOnceOnCuda()
    engine = _fake_engine(model)

    probabilities = engine.forward_probabilities(torch.ones((1, 1, 2, 2)))

    assert engine.device == "cpu"
    assert engine.device_fallback_reason == "CUDA out of memory"
    assert model.calls == 2
    np.testing.assert_allclose(probabilities, np.full((2, 2), 0.5, dtype=np.float32))


def test_concurrent_requests_observe_one_sticky_cpu_transition(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    engine = _fake_engine(_FailsOnceOnCuda())
    tensor = torch.ones((1, 1, 2, 2))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(engine.forward_probabilities, (tensor, tensor)))

    assert engine.device == "cpu"
    assert len(results) == 2
    for probabilities in results:
        np.testing.assert_allclose(probabilities, np.full((2, 2), 0.5, dtype=np.float32))


def test_cuda_forward_requests_can_run_concurrently(monkeypatch):
    class ConcurrentModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.barrier = threading.Barrier(2)

        def forward(self, tensor):
            self.barrier.wait(timeout=2)
            return torch.zeros_like(tensor)

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    engine = _fake_engine(ConcurrentModel())
    tensor = torch.ones((1, 1, 2, 2))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(engine.forward_probabilities, (tensor, tensor)))

    assert len(results) == 2


def test_cpu_transition_waits_for_other_inflight_cuda_request(monkeypatch):
    from backend.services.inference_engine import InferenceEngine

    class OneCudaFailureModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.barrier = threading.Barrier(2)
            self.release_second = threading.Event()
            self.calls = 0
            self.calls_lock = threading.Lock()

        def forward(self, tensor):
            with self.calls_lock:
                self.calls += 1
                call = self.calls
            if call <= 2:
                self.barrier.wait(timeout=3)
            if call == 1:
                raise RuntimeError("CUDA out of memory")
            if call == 2:
                self.release_second.wait(timeout=3)
            return torch.zeros_like(tensor)

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    model = OneCudaFailureModel()
    engine = _fake_engine(model)
    transition_started = threading.Event()
    original_switch = InferenceEngine._switch_to_cpu_after_cuda_error

    def observe_transition(self, reason):
        transition_started.set()
        return original_switch(self, reason)

    monkeypatch.setattr(InferenceEngine, "_switch_to_cpu_after_cuda_error", observe_transition)
    tensor = torch.ones((1, 1, 2, 2))

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(engine.forward_probabilities, tensor) for _ in range(2)]
        assert transition_started.wait(timeout=3)
        assert engine.device == "cuda"
        model.release_second.set()
        results = [request.result(timeout=3) for request in requests]

    assert engine.device == "cpu"
    assert len(results) == 2


def test_model_admin_reports_selected_device_instead_of_available_hardware(monkeypatch, tmp_path):
    from backend.services import model_service

    class LoadedAdapter:
        is_loaded = True
        engine = SimpleNamespace(device="cpu", architecture_name="Test U-Net")

        def get_info(self):
            return {"name": "Test U-Net", "architecture": "Test U-Net", "is_loaded": True}

    registry = model_service.ModelRegistry.__new__(model_service.ModelRegistry)
    registry.adapters = {"attention_unet": LoadedAdapter()}
    registry.primary_model_key = "attention_unet"
    registry.ensemble_enabled = False
    monkeypatch.setattr(model_service, "_get_candidate_models_file", lambda: str(tmp_path / "missing.json"))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    overview = registry.get_admin_overview()

    assert overview["execution_device"] == "CPU Execution Provider"


def test_adapter_tracks_engine_device_after_runtime_fallback():
    from backend.services.model_service import AttentionUNetAdapter

    class Engine:
        device = "cuda"

        def run_inference(self, *_args, **_kwargs):
            self.device = "cpu"
            return {"provenance": {"device": "cpu"}}

    adapter = AttentionUNetAdapter.__new__(AttentionUNetAdapter)
    adapter.device = "cuda"
    adapter.engine = Engine()

    result = adapter.predict(torch.zeros((1, 1, 2, 2)), np.zeros((2, 2), dtype=np.uint8))

    assert result["provenance"]["device"] == "cpu"
    assert adapter.device == "cpu"


def test_non_cuda_inference_error_does_not_trigger_device_fallback(monkeypatch):
    class BrokenModel(torch.nn.Module):
        def forward(self, _tensor):
            raise RuntimeError("invalid model tensor shape")

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: None)
    engine = _fake_engine(BrokenModel())

    with pytest.raises(RuntimeError, match="invalid model tensor shape"):
        engine.forward_probabilities(torch.ones((1, 1, 2, 2)))

    assert engine.device == "cuda"
