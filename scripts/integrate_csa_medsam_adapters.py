import re

with open('backend/services/model_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

csa_medsam_adapters = '''
class CSASegNetAdapter(BaseModelAdapter):
    """
    Adapter for CSA-SegNet Channel and Spatial Attention Network.
    Reference: phamthiloanhd/CSA-SegNet (Academic RUO).
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native prototype available in scripts/prototype_csa_attention.py.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="CSA-SegNet Attention Network",
            version="1.0.0",
            architecture="CSA-SegNet Dual Attention + SPPF Bottleneck",
        )
        self.fallback_engine = fallback_engine
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
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
        generate_overlay: bool = False,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale, generate_overlay=generate_overlay
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native CSA-SegNet inference is not implemented."
        )


class MedSAMAdapter(BaseModelAdapter):
    """
    Adapter for MedSAM Medical Interactive Foundation Model.
    Reference: bowang-lab/MedSAM (Apache-2.0).
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native prototype available in scripts/prototype_medsam_adapter.py.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="MedSAM Interactive Foundation Model",
            version="1.0.0",
            architecture="MedSAM ViT-B Promptable Segmentation",
        )
        self.fallback_engine = fallback_engine
        self.is_loaded = False

    def load_weights(self, weights_path: str | None = None, device: str = "cpu") -> bool:
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
        generate_overlay: bool = False,
    ) -> dict[str, Any]:
        if self.fallback_engine:
            res = self.fallback_engine.run_inference(
                tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm, scale=scale, generate_overlay=generate_overlay
            )
            return self._record_primary_fallback(res)
        raise RuntimeError(
            f"{self.name}: The manifest-selected primary engine is unavailable; "
            "native MedSAM inference is not implemented."
        )
'''

target = 'class CandidateModelAdapter(BaseModelAdapter):'
if target in content and 'class CSASegNetAdapter' not in content:
    content = content.replace(target, csa_medsam_adapters.strip() + '\n\n\n' + target)

reg_target = 'self.register_adapter("tinyusfm", TinyUSFMAdapter(fallback_engine=primary_engine))'
reg_replacement = '''self.register_adapter("tinyusfm", TinyUSFMAdapter(fallback_engine=primary_engine))
        self.register_adapter("csasegnet", CSASegNetAdapter(fallback_engine=primary_engine))
        self.register_adapter("medsam", MedSAMAdapter(fallback_engine=primary_engine))'''

if reg_target in content and '"csasegnet"' not in content:
    content = content.replace(reg_target, reg_replacement)

with open('backend/services/model_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated model_service.py successfully')
