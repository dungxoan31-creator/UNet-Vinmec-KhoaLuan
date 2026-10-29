"""Bounded inference admission with synthetic threads; no GPU required."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.services.model_service import InferenceAdmission, InferenceBusyError


def test_admission_rejects_excess_and_releases_after_failure():
    admission = InferenceAdmission(max_running=1, max_waiting=0, timeout_seconds=0.1)
    entered = threading.Event()
    release = threading.Event()

    def running():
        with admission.slot():
            entered.set()
            assert release.wait(3)
            raise RuntimeError("synthetic model error")

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(running)
        assert entered.wait(3)
        with pytest.raises(InferenceBusyError):
            with admission.slot():
                pytest.fail("capacity must be rejected")
        release.set()
        with pytest.raises(RuntimeError, match="synthetic model error"):
            first.result(timeout=3)
    with admission.slot():
        pass


def test_waiting_request_times_out_without_leaking_capacity():
    admission = InferenceAdmission(max_running=1, max_waiting=1, timeout_seconds=0.05)
    with admission.slot():
        with ThreadPoolExecutor(max_workers=1) as executor:
            def waiter():
                with admission.slot():
                    pass
            with pytest.raises(InferenceBusyError):
                executor.submit(waiter).result(timeout=3)
    with admission.slot():
        pass


def test_registry_applies_admission_to_adapter():
    from backend.services.model_service import ModelRegistry

    entered = threading.Event()
    release = threading.Event()
    class BlockingAdapter:
        def predict(self, *_args, **_kwargs):
            entered.set()
            assert release.wait(3)
            return {"ok": True}

    registry = ModelRegistry.__new__(ModelRegistry)
    registry._admission = InferenceAdmission(max_running=1, max_waiting=0, timeout_seconds=0.1)
    registry.primary_model_key = "primary"
    registry.adapters = {"primary": BlockingAdapter()}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(registry.predict, None, None)
        assert entered.wait(3)
        with pytest.raises(InferenceBusyError):
            registry.predict(None, None)
        release.set()
        assert first.result(timeout=3) == {"ok": True}


@pytest.mark.parametrize("running,waiting,timeout", [(0, 1, 1), (1, -1, 1), (1, 1, 0), (1, 1, float('nan'))])
def test_invalid_limits_fail_closed(running, waiting, timeout):
    with pytest.raises(ValueError):
        InferenceAdmission(running, waiting, timeout)


def test_segment_returns_503_when_queue_full_without_blocking_event_loop(monkeypatch, doctor_access):
    import asyncio
    from io import BytesIO

    import numpy as np
    from fastapi.testclient import TestClient
    from PIL import Image

    from backend.app.main import app
    from backend.app.routers import v1_endpoints

    monkeypatch.setattr(v1_endpoints.preprocessor, "validate_ultrasound_suitability", lambda _image: {
        "is_suitable": True, "iqa_score": 1.0, "laplacian_variance": 0.0,
        "contrast_std": 0.0, "error_reasons": [], "error_message": "",
    })
    def busy(*_args, **_kwargs):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        raise InferenceBusyError("synthetic queue full")
    monkeypatch.setattr(v1_endpoints.model_registry, "predict", busy)
    output = BytesIO()
    Image.fromarray(np.full((128, 128), 64, dtype=np.uint8)).save(output, format="PNG")
    with TestClient(app) as client:
        response = client.post("/api/v1/segment", files={"file": ("synthetic.png", output.getvalue(), "image/png")})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert "synthetic queue full" not in response.text
