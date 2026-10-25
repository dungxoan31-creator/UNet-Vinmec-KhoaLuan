import pytest
from fastapi import HTTPException

from backend.services.model_service import (
    CandidateModelAdapter,
    DS2NetAdapter,
    ModelRegistry,
    S4MAdapter,
    SovaSegAdapter,
    UltraSAMAdapter,
)


@pytest.mark.parametrize(
    "adapter_factory",
    [
        lambda: S4MAdapter(fallback_engine=object()),
        lambda: UltraSAMAdapter(fallback_engine=object()),
        lambda: DS2NetAdapter(fallback_engine=object()),
        lambda: SovaSegAdapter(fallback_engine=object()),
        lambda: CandidateModelAdapter(name="Research candidate", checkpoint="candidate.pth"),
    ],
)
def test_unimplemented_adapter_does_not_claim_existing_file_is_loaded(tmp_path, adapter_factory):
    checkpoint = tmp_path / "placeholder.pth"
    checkpoint.write_bytes(b"not a loaded model")
    adapter = adapter_factory()

    assert adapter.load_weights(str(checkpoint)) is False
    assert adapter.is_loaded is False
    assert adapter.get_info()["is_loaded"] is False


def test_registry_rejects_unknown_explicit_model_key_without_running_primary():
    class PrimaryAdapter:
        is_loaded = True

        def __init__(self):
            self.calls = 0

        def predict(self, *_args, **_kwargs):
            self.calls += 1
            return {"provenance": {"model_name": "selected primary"}}

    primary = PrimaryAdapter()
    registry = ModelRegistry.__new__(ModelRegistry)
    registry.adapters = {"attention_unet": primary}
    registry.primary_model_key = "attention_unet"

    with pytest.raises(ValueError, match="Unknown model key"):
        registry.predict(None, None, model_key="misspelled_candidate")

    assert primary.calls == 0


def test_registry_rejects_metadata_only_candidate_without_running_primary():
    class PrimaryAdapter:
        is_loaded = True

        def __init__(self):
            self.calls = 0

        def predict(self, *_args, **_kwargs):
            self.calls += 1
            return {"provenance": {"model_name": "selected primary"}}

    primary = PrimaryAdapter()
    candidate = CandidateModelAdapter(name="Research candidate", checkpoint="candidate.pth")
    registry = ModelRegistry.__new__(ModelRegistry)
    registry.adapters = {"attention_unet": primary, "candidate": candidate}
    registry.primary_model_key = "attention_unet"

    with pytest.raises(RuntimeError, match="not loaded for inference"):
        registry.predict(None, None, model_key="candidate")

    assert primary.calls == 0


def test_v1_segment_returns_503_when_selected_checkpoint_is_unavailable(monkeypatch):
    import asyncio

    from backend.app.routers import v1_endpoints

    class UnloadedAdapter:
        is_loaded = False

    monkeypatch.setattr(v1_endpoints.model_registry, "get_primary_adapter", lambda: UnloadedAdapter())

    with pytest.raises(HTTPException) as error:
        asyncio.run(v1_endpoints.segment_image_v1(file=None, image_id="image-1", db=None))

    assert error.value.status_code == 503


@pytest.mark.parametrize("adapter_type", [S4MAdapter, UltraSAMAdapter, DS2NetAdapter, SovaSegAdapter])
def test_primary_fallback_preserves_actual_model_provenance(adapter_type):
    actual_provenance = {
        "model_name": "U-Net++ + ResNet34 ImageNet encoder",
        "model_version": "candidate-build-2026-10-19",
    }

    class PrimaryEngine:
        architecture_name = actual_provenance["model_name"]

        def run_inference(self, *_args, **_kwargs):
            return {"provenance": dict(actual_provenance)}

    adapter = adapter_type(fallback_engine=PrimaryEngine())
    result = adapter.predict(None, None)

    assert result["provenance"]["model_name"] == actual_provenance["model_name"]
    assert result["provenance"]["model_version"] == actual_provenance["model_version"]
    assert result["provenance"]["requested_model_name"] == adapter.name
    assert result["provenance"]["adapter_mode"] == "FALLBACK_TO_PRIMARY_MODEL"
    assert adapter.get_info()["checkpoint_status"].endswith(actual_provenance["model_name"])
