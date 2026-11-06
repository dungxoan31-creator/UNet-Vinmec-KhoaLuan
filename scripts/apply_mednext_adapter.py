import os

path = r"backend/services/model_service.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

adapter_code = '''
class MedNeXtAdapter(BaseModelAdapter):
    """
    Adapter for MedNeXt Medical ConvNeXt architecture.
    Reference: MIC-DKFZ/MedNeXt (Apache-2.0).
    Features 7x7 Depthwise Conv, Inverted Bottleneck, and Global Response Normalization (GRN).
    STATUS: FALLBACK_TO_PRIMARY_MODEL — native prototype available in scripts/prototype_mednext_block.py.
    """

    ADAPTER_MODE = "FALLBACK_TO_PRIMARY_MODEL"

    def __init__(self, fallback_engine: InferenceEngine | None = None):
        super().__init__(
            name="MedNeXt Medical ConvNeXt",
            version="1.0.0",
            architecture="MedNeXt 7x7 Depthwise Inverted Bottleneck",
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
            "native MedNeXt inference is not implemented."
        )

'''

target1 = "class CandidateModelAdapter(BaseModelAdapter):"
if target1 in content:
    content = content.replace(target1, adapter_code.lstrip() + "\n" + target1, 1)

target2 = 'self.register_adapter("medsam", MedSAMAdapter(fallback_engine=primary_engine))'
reg_code = 'self.register_adapter("medsam", MedSAMAdapter(fallback_engine=primary_engine))\n        self.register_adapter("mednext", MedNeXtAdapter(fallback_engine=primary_engine))'
if target2 in content:
    content = content.replace(target2, reg_code, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("SUCCESS_MEDNEXT_REGISTERED")
