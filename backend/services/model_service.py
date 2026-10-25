"""
Model abstraction and registry for the RUO ovarian ultrasound segmentation prototype.
The primary checkpoint and architecture are selected by the hash-verified model manifest.
"""
import json
import os
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import numpy as np
import torch

from backend.services.inference_engine import InferenceEngine


class BaseModelAdapter(ABC):
    """Abstract Base Class for all ultrasound segmentation model adapters."""

    def __init__(self, name: str, version: str, architecture: str):
        self.name = name
        self.version = version
        self.architecture = architecture
        self.is_loaded = False

    @abstractmethod
    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        pass

    @abstractmethod
    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        pass

    def get_info(self) -> dict[str, Any]:
        engine = getattr(self, "engine", None) if self.is_loaded else None
        return {
            "name": self.name,
            "version": self.version,
            "architecture": self.architecture,
            "is_loaded": self.is_loaded,
            "checksum": getattr(engine, "model_checksum", None),
            "threshold": getattr(engine, "threshold", None),
        }

    def _record_primary_fallback(self, result: dict[str, Any]) -> dict[str, Any]:
        provenance = result.get("provenance")
        if not isinstance(provenance, dict):
            raise RuntimeError("Primary fallback did not return model provenance.")
        provenance["requested_model_name"] = self.name
        provenance["adapter_mode"] = self.ADAPTER_MODE
        return result

    def _fallback_status(self) -> str:
        engine = getattr(self, "fallback_engine", None)
        architecture = getattr(engine, "architecture_name", None)
        if architecture:
            return f"NOT_LOADED — using manifest-selected primary model: {architecture}"
        return "NOT_LOADED — no manifest-selected primary model is available"


class AttentionUNetAdapter(BaseModelAdapter):
    """
    Compatibility adapter for the manifest-selected segmentation checkpoint.
    """

    def __init__(
        self,
        weights_path: str | None = None,
        device: str | None = None,
        architecture: str = "auto",
        input_normalization: dict | None = None,
        threshold: float | None = None,
        horizontal_flip_tta: bool = False,
        expected_checkpoint_sha256: str | None = None,
        model_version: str | None = None,
    ):
        super().__init__(
            name="Attention U-Net Ovarian Engine",
            version="1.2.0",
            architecture="Attention U-Net (Deep Encoder-Decoder + Dual Attention Gates)",
        )
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = weights_path
        self.model_architecture = architecture
        self.input_normalization = input_normalization
        self.threshold = threshold
        self.horizontal_flip_tta = bool(horizontal_flip_tta)
        self.expected_checkpoint_sha256 = expected_checkpoint_sha256
        self.model_version = model_version
        engine_kwargs = dict(
            model_weights_path=weights_path,
            device=self.device,
            architecture=architecture,
            input_normalization=input_normalization,
            horizontal_flip_tta=self.horizontal_flip_tta,
            expected_checkpoint_sha256=expected_checkpoint_sha256,
            model_version=model_version,
        )
        if threshold is not None:
            engine_kwargs["threshold"] = threshold
        self.engine = InferenceEngine(**engine_kwargs)
        self.device = self.engine.device
        self.name = self.engine.model_name
        self.architecture = self.engine.architecture_name
        self.is_loaded = self.engine.is_model_ready

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        self.weights_path = weights_path
        self.device = device
        engine_kwargs = dict(
            model_weights_path=weights_path,
            device=device,
            architecture=self.model_architecture,
            input_normalization=self.input_normalization,
            horizontal_flip_tta=self.horizontal_flip_tta,
            expected_checkpoint_sha256=self.expected_checkpoint_sha256,
            model_version=self.model_version,
        )
        if getattr(self, "threshold", None) is not None:
            engine_kwargs["threshold"] = self.threshold
        elif hasattr(self, "engine") and getattr(self.engine, "threshold", None) is not None:
            engine_kwargs["threshold"] = self.engine.threshold
        self.engine = InferenceEngine(**engine_kwargs)
        self.device = self.engine.device
        self.name = self.engine.model_name
        self.architecture = self.engine.architecture_name
        self.is_loaded = self.engine.is_model_ready
        return self.is_loaded

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        result = self.engine.run_inference(
            tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
        )
        self.device = self.engine.device
        return result


class S4MAdapter(BaseModelAdapter):
    """
    Adapter for S4M / MMOTU multi-organ ultrasound segmentation framework.
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native S4M loading and inference are not implemented.
    Uses the manifest-selected primary engine when called directly.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="S4M Ultrasound Foundation Model",
            version="1.0.0",
            architecture="S4M Multi-Scale Cross-Attention Transformer",
        )
        self.fallback_engine = fallback_engine
        # is_loaded reflects whether a NATIVE checkpoint is present, not fallback availability
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        """S4M loading is unsupported; an existing path is not evidence of loaded weights."""
        self.is_loaded = False
        return False

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["adapter_mode"] = self.ADAPTER_MODE
        info["checkpoint_status"] = self._fallback_status()
        return info

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native S4M inference is not implemented."
        )


class UltraSAMAdapter(BaseModelAdapter):
    """
    Adapter for UltraSAM / UltraSAM3 zero-shot promptable segmentation.
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native UltraSAM loading and inference are not implemented.
    Uses the manifest-selected primary engine when called directly.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="UltraSAM Foundation Model", version="3.0.0", architecture="UltraSAM Segment Anything for Ultrasound"
        )
        self.fallback_engine = fallback_engine
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        """UltraSAM loading is unsupported; an existing path is not evidence of loaded weights."""
        self.is_loaded = False
        return False

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["adapter_mode"] = self.ADAPTER_MODE
        info["checkpoint_status"] = self._fallback_status()
        return info

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native UltraSAM inference is not implemented."
        )


class DS2NetAdapter(BaseModelAdapter):
    """
    Adapter for DS²Net dual-stream ultrasound network.
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native DS²Net loading and inference are not implemented.
    Reference: cv516Buaa/MMOTU_DS2Net (Apache-2.0). Dual-stream for OTU-2D + OTU-CEUS.
    Uses the manifest-selected primary engine when called directly.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="DS²Net Dual-Stream Lesion Network",
            version="1.1.0",
            architecture="DS²Net (Dual Spatial & Spectral Stream Architecture)",
        )
        self.fallback_engine = fallback_engine
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        """DS2Net loading is unsupported; an existing path is not evidence of loaded weights."""
        self.is_loaded = False
        return False

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["adapter_mode"] = self.ADAPTER_MODE
        info["checkpoint_status"] = self._fallback_status()
        return info

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native DS2Net inference is not implemented."
        )


class SovaSegAdapter(BaseModelAdapter):
    """
    Adapter for SovaSeg specialized ovarian follicle and cyst segmentation.
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native SovaSeg loading and inference are not implemented.
    Uses the manifest-selected primary engine when called directly.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="SovaSeg-Net Specialized Ovarian Engine",
            version="1.0.5",
            architecture="SovaSeg Boundary-Aware ResU-Net",
        )
        self.fallback_engine = fallback_engine
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        """SovaSeg loading is unsupported; an existing path is not evidence of loaded weights."""
        self.is_loaded = False
        return False

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["adapter_mode"] = self.ADAPTER_MODE
        info["checkpoint_status"] = self._fallback_status()
        return info

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native SovaSeg inference is not implemented."
        )


class CandidateModelAdapter(BaseModelAdapter):
    """
    Metadata-only entry for candidate or external checkpoints; no inference loader is implemented.
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        architecture: str = "Candidate Checkpoint",
        checkpoint: str | None = None,
    ):
        super().__init__(name=name, version=version, architecture=architecture)
        self.checkpoint = checkpoint
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
        self.is_loaded = False
        return False

    def predict(self, *args, **kwargs):
        raise RuntimeError(f"Candidate model {self.name} is not loaded for inference.")


def _get_candidate_models_file() -> str:
    env_dir = os.environ.get("APP_DATA_DIR")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if env_dir:
        data_dir = os.path.abspath(env_dir) if os.path.isabs(env_dir) else os.path.abspath(os.path.join(project_root, env_dir))
    else:
        data_dir = os.path.join(project_root, "data")
    return os.path.join(data_dir, "candidate_models.json")


class ModelRegistry:
    """
    Central registry for the manifest-selected serving model and metadata-only candidates.
    """

    def __init__(self, checkpoint_path: str | None = None, model_selection: dict | None = None):
        self.adapters: dict[str, BaseModelAdapter] = {}
        self.primary_model_key = "attention_unet"
        self.ensemble_enabled = False

        # Register all supported model architectures
        self.model_selection = model_selection or {}
        model_selection = self.model_selection
        primary_adapter = AttentionUNetAdapter(
            weights_path=checkpoint_path,
            architecture=model_selection.get("architecture", "auto"),
            input_normalization=model_selection.get("input_normalization"),
            threshold=model_selection.get("threshold"),
            horizontal_flip_tta=model_selection.get("horizontal_flip_tta", False),
            expected_checkpoint_sha256=model_selection.get("checkpoint_sha256"),
            model_version=model_selection.get("model_version"),
        )
        primary_engine = primary_adapter.engine

        self.register_adapter("attention_unet", primary_adapter)
        self.register_adapter("s4m", S4MAdapter(fallback_engine=primary_engine))
        self.register_adapter("ultrasam", UltraSAMAdapter(fallback_engine=primary_engine))
        self.register_adapter("ds2net", DS2NetAdapter(fallback_engine=primary_engine))
        self.register_adapter("sovaseg", SovaSegAdapter(fallback_engine=primary_engine))
        self.load_persisted_candidates()

    def load_persisted_candidates(self) -> None:
        filepath = _get_candidate_models_file()
        if os.path.isfile(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    candidates = json.load(f)
                    if isinstance(candidates, list):
                        for c in candidates:
                            k = c.get("key")
                            if k and k not in self.adapters:
                                self.adapters[k] = CandidateModelAdapter(
                                    name=c.get("name", k),
                                    version=c.get("version", "1.0.0"),
                                    architecture=c.get("architecture", "Candidate Checkpoint"),
                                    checkpoint=c.get("checkpoint"),
                                )
            except Exception:
                pass

    def save_persisted_candidates(self) -> None:
        filepath = _get_candidate_models_file()
        candidates = []
        for k, v in self.adapters.items():
            if isinstance(v, CandidateModelAdapter):
                candidates.append({
                    "key": k,
                    "name": v.name,
                    "version": v.version,
                    "architecture": v.architecture,
                    "checkpoint": getattr(v, "checkpoint", None),
                })
        directory = os.path.dirname(filepath)
        os.makedirs(directory, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, prefix=".candidate-models-", suffix=".tmp", delete=False
            ) as stream:
                temporary_path = stream.name
                json.dump(candidates, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, filepath)
        except Exception:
            if temporary_path:
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
            raise

    def register_adapter(self, key: str, adapter: BaseModelAdapter, allow_overwrite: bool = False):
        if not allow_overwrite and key in self.adapters:
            raise ValueError(f"Model key '{key}' is already registered and cannot be overwritten.")
        self.adapters[key] = adapter

    def get_adapter(self, key: str) -> BaseModelAdapter | None:
        return self.adapters.get(key)

    def get_primary_adapter(self) -> BaseModelAdapter:
        adapter = self.adapters.get(self.primary_model_key)
        if adapter is None:
            return self.adapters["attention_unet"]
        return adapter

    def predict(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float = 0.1,
        model_key: str | None = None,
        scale: float = 1.0,
    ) -> dict[str, Any]:
        if model_key is None:
            adapter = self.get_primary_adapter()
        else:
            adapter = self.adapters.get(model_key)
            if adapter is None:
                raise ValueError(f"Unknown model key '{model_key}'.")

        return adapter.predict(
            tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale
        )

    def get_admin_overview(self) -> dict[str, Any]:
        """Provides operational metrics for Admin / Engineering view."""
        self.load_persisted_candidates()
        primary = self.adapters.get(self.primary_model_key)
        engine = getattr(primary, "engine", None)
        selected_device = getattr(engine, "device", None)
        if selected_device is None:
            uses_cuda = torch.cuda.is_available()
        else:
            uses_cuda = str(selected_device).startswith("cuda")
        device_name = "CUDA (NVIDIA GPU)" if uses_cuda else "CPU Execution Provider"
        models_info = []
        for model_id, adapter in self.adapters.items():
            model_info = adapter.get_info()
            model_info["model_id"] = model_id
            model_info["is_candidate"] = isinstance(adapter, CandidateModelAdapter)
            models_info.append(model_info)
        architecture = primary.engine.architecture_name if primary and primary.is_loaded else None
        if architecture and models_info:
            models_info[0]["name"] = architecture
            models_info[0]["architecture"] = architecture

        return {
            "active_primary_model": architecture,
            "fallback_model": architecture,
            "ensemble_enabled": self.ensemble_enabled,
            "execution_device": device_name,
            "registered_models": models_info,
            "test_set_dsc": None,
            "test_set_iou": None,
            "mean_inference_latency_ms": None,
            "last_updated": datetime.now(UTC).isoformat(),
        }
