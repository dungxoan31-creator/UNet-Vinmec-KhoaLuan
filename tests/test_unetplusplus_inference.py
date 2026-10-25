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


def test_horizontal_flip_tta_unflips_and_averages_probabilities(monkeypatch):
    class SequentialLogitModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(()))
            self.calls = 0

        def forward(self, images):
            self.calls += 1
            logits = torch.tensor([[-4.0, 4.0] if self.calls == 1 else [-2.0, 2.0]])
            return logits.reshape(1, 1, 1, 2)

    import segmentation_models_pytorch as smp

    model = SequentialLogitModel()
    monkeypatch.setattr(smp, "UnetPlusPlus", lambda **_kwargs: model)
    engine = InferenceEngine(device="cpu", architecture="unetplusplus_resnet34", horizontal_flip_tta=True)
    engine.is_model_ready = True

    probabilities = engine.forward_probabilities(torch.zeros((1, 1, 1, 2)))

    expected = (torch.tensor([0.018, 0.982]) + torch.tensor([0.881, 0.119])) / 2
    assert model.calls == 2
    torch.testing.assert_close(torch.from_numpy(probabilities).flatten(), expected, atol=0.001, rtol=0)


def test_horizontal_flip_tta_defaults_off(monkeypatch):
    class CaptureModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(()))
            self.calls = 0

        def forward(self, images):
            self.calls += 1
            return images

    import segmentation_models_pytorch as smp

    model = CaptureModel()
    monkeypatch.setattr(smp, "UnetPlusPlus", lambda **_kwargs: model)
    engine = InferenceEngine(device="cpu", architecture="unetplusplus_resnet34")
    engine.is_model_ready = True
    engine.forward_probabilities(torch.zeros((1, 1, 1, 2)))

    assert model.calls == 1
