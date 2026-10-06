import torch

from backend.services.inference_engine import InferenceEngine


def test_unetplusplus_manifest_selects_architecture_and_grayscale_normalization(monkeypatch):
    class CaptureModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(()))

        def forward(self, images):
            return images

    import segmentation_models_pytorch as smp

    monkeypatch.setattr(smp, "UnetPlusPlus", lambda **_kwargs: CaptureModel())
    engine = InferenceEngine(
        device="cpu",
        architecture="unetplusplus_resnet34",
        input_normalization={"mean": 0.449, "std": 0.226},
    )

    assert engine.architecture_name == "U-Net++ (ResNet34 ImageNet)"
    pixels = torch.tensor([[[[0.449, 0.675]]]])
    torch.testing.assert_close(engine.prepare_model_input(pixels), torch.tensor([[[[0.0, 1.0]]]]))
