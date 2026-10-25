import cv2
import numpy as np


def test_heatmap_encodes_entropy_as_alpha_on_512_canvas():
    from backend.services.inference_engine import InferenceEngine

    probabilities = np.zeros((512, 512), dtype=np.float32)
    probabilities[:, 256:] = 0.5

    encoded = InferenceEngine.encode_uncertainty_heatmap_png(probabilities)

    assert isinstance(encoded, bytes)
    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert image.shape == (512, 512, 4)
    assert image[100, 100, 3] == 0
    assert image[100, 300, 3] == 255
    blue, green, red, _alpha = image[100, 300]
    assert red > green > blue


def test_heatmap_omits_wrong_shape_and_non_finite_probability_maps():
    from backend.services.inference_engine import InferenceEngine

    wrong_shape = np.zeros((256, 256), dtype=np.float32)
    non_finite = np.zeros((512, 512), dtype=np.float32)
    non_finite[0, 0] = np.nan

    assert InferenceEngine.encode_uncertainty_heatmap_png(wrong_shape) is None
    assert InferenceEngine.encode_uncertainty_heatmap_png(non_finite) is None


def test_heatmap_omits_png_when_opencv_encoding_fails(monkeypatch):
    from backend.services import inference_engine

    monkeypatch.setattr(inference_engine.cv2, "imencode", lambda *_args, **_kwargs: (False, None))

    assert inference_engine.InferenceEngine.encode_uncertainty_heatmap_png(
        np.full((512, 512), 0.5, dtype=np.float32)
    ) is None


def test_run_inference_returns_the_uncertainty_heatmap(monkeypatch):
    from backend.services.inference_engine import InferenceEngine

    engine = object.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.device = "cpu"
    engine.model_checksum = None
    probabilities = np.full((512, 512), 0.1, dtype=np.float32)
    empty_mask = np.zeros((512, 512), dtype=np.uint8)

    monkeypatch.setattr(InferenceEngine, "forward_probabilities", lambda self, _tensor: probabilities)
    monkeypatch.setattr(InferenceEngine, "post_process_mask", lambda self, _probs: empty_mask)
    monkeypatch.setattr(
        InferenceEngine,
        "calculate_uncertainty",
        lambda self, _probs, _mask: {
            "entropy_score": 0.0,
            "uncertainty_level": "LOW",
            "is_uncertain": False,
        },
    )
    monkeypatch.setattr(InferenceEngine, "_normalize_pixel_spacing", staticmethod(lambda _spacing: None))
    monkeypatch.setattr(
        InferenceEngine,
        "extract_calipers_and_measurements",
        lambda self, _mask, pixel_spacing_mm=None: {"has_lesion": False, "lesions": []},
    )
    monkeypatch.setattr(InferenceEngine, "mask_to_rle", lambda self, _mask: {"counts": [512 * 512]})
    monkeypatch.setattr(InferenceEngine, "generate_overlay_base64", lambda self, *_args: None)

    result = engine.run_inference(None, np.zeros((512, 512), dtype=np.uint8))

    assert isinstance(result["uncertainty_map_png"], bytes)
