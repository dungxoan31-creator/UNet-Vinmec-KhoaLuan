"""
Advanced Clinical Edge-Case Tests for Inference Engine & Morphology Extractor.
Tests:
- Vectorized connected component filtering and faint lesion safety retention.
- Morphological closing kernel caching and hole-filling.
- Multi-focal lesions (dominant lesion identification & composite area).
- Anomalous, zero, negative, NaN, Inf pixel spacing safety handling.
- Borderline probability thresholding precision.
- Extreme aspect ratio letterbox preservation.
"""

import numpy as np
import pytest

from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor


class DummyEngine(InferenceEngine):
    """Subclass without model loading for unit testing pure geometric & post-processing logic."""

    def __init__(self, threshold=0.4, min_area_px=30, apply_morphology=False):
        self.threshold = threshold
        self.min_area_px = min_area_px
        self.apply_morphology = apply_morphology
        self.device = "cpu"
        self.model = None


def test_postprocess_multiple_disconnected_components_vectorized():
    engine = DummyEngine(threshold=0.4, min_area_px=50, apply_morphology=False)

    # 512x512 blank canvas
    prob_map = np.zeros((512, 512), dtype=np.float32)

    # Dominant lesion: 100 px x 100 px = 10,000 px
    prob_map[50:150, 50:150] = 0.85

    # Secondary lesion: 10 px x 10 px = 100 px (> min_area_px 50)
    prob_map[200:210, 200:210] = 0.75

    # 5 tiny speckles of size 3x3 = 9 px (< min_area_px 50)
    prob_map[300:303, 300:303] = 0.9
    prob_map[350:353, 350:353] = 0.9
    prob_map[400:403, 400:403] = 0.9
    prob_map[450:453, 450:453] = 0.9
    prob_map[480:483, 480:483] = 0.9

    clean_mask = engine.post_process_mask(prob_map, min_area_px=50)

    # Dominant lesion and secondary lesion must be kept
    assert clean_mask[100, 100] == 1
    assert clean_mask[205, 205] == 1

    # All speckles must be eliminated
    assert clean_mask[301, 301] == 0
    assert clean_mask[351, 351] == 0
    assert clean_mask[401, 401] == 0
    assert clean_mask[451, 451] == 0
    assert clean_mask[481, 481] == 0


def test_postprocess_safety_fallback_when_all_below_threshold():
    engine = DummyEngine(threshold=0.4, min_area_px=500, apply_morphology=False)

    prob_map = np.zeros((512, 512), dtype=np.float32)

    # Component A: 10x10 = 100 px (< 500)
    prob_map[50:60, 50:60] = 0.8

    # Component B: 15x15 = 225 px (< 500, but largest)
    prob_map[200:215, 200:215] = 0.85

    clean_mask = engine.post_process_mask(prob_map, min_area_px=500)

    # Clinical safety rule: If all components fall below min_area_px,
    # the largest component is retained so faint lesions are never lost.
    assert clean_mask.sum() == 225
    assert clean_mask[205, 205] == 1
    assert clean_mask[55, 55] == 0


def test_morphology_kernel_caching_and_hole_closing():
    engine = DummyEngine(threshold=0.4, min_area_px=0, apply_morphology=True)

    prob_map = np.zeros((100, 100), dtype=np.float32)
    # 20x20 solid block with a 1-pixel hole in center
    prob_map[40:60, 40:60] = 0.9
    prob_map[50, 50] = 0.0  # hole

    assert not hasattr(engine, "_morph_kernel_3")
    mask1 = engine.post_process_mask(prob_map, apply_morphology=True, morph_kernel_size=3)
    assert hasattr(engine, "_morph_kernel_3")
    kernel_ref = engine._morph_kernel_3

    # The 1-pixel hole must be closed
    assert mask1[50, 50] == 1

    # Second call should reuse the same cached kernel object
    mask2 = engine.post_process_mask(prob_map, apply_morphology=True, morph_kernel_size=3)
    assert engine._morph_kernel_3 is kernel_ref
    assert np.array_equal(mask1, mask2)


def test_calipers_multi_focal_lesions_and_dominance():
    engine = DummyEngine()

    mask = np.zeros((512, 512), dtype=np.uint8)
    # Lesion 1 (Dominant): 40x80 rectangle at (100, 100) -> 3200 px
    mask[100:180, 100:140] = 1

    # Lesion 2: 20x20 square at (300, 300) -> 400 px
    mask[300:320, 300:320] = 1

    pixel_spacing = 0.1  # 0.1 mm per pixel
    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=pixel_spacing)

    assert res["has_lesion"] is True
    assert res["total_lesions"] == 2
    assert len(res["lesions"]) == 2

    dominant = res["lesions"][0]
    secondary = res["lesions"][1]

    # Dominant must have larger area
    assert dominant["area_px"] > secondary["area_px"]
    assert dominant["area_px"] == pytest.approx(3200, rel=0.05)

    # d_max for dominant should be ~80 px = 8.0 mm
    assert dominant["max_diameter_px"] == pytest.approx(80.0, abs=3.0)
    assert dominant["max_diameter_mm"] == pytest.approx(8.0, abs=0.3)

    # Overall measurements reflect dominant
    assert res["max_diameter_px"] == dominant["max_diameter_px"]
    assert res["max_diameter_mm"] == dominant["max_diameter_mm"]

    # Total area is the sum of both in cm2
    # (3200 + 400) * 0.1^2 / 100 = 3600 * 0.01 / 100 = 0.36 cm2
    assert res["total_area_cm2"] == pytest.approx(0.36, abs=0.02)


def test_numeric_spacing_safety_and_anomalies():
    engine = DummyEngine()
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[30:70, 30:70] = 1

    anomalous_spacings = [None, 0.0, -0.5, float("nan"), float("inf"), -float("inf")]

    for spacing in anomalous_spacings:
        res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=spacing)
        assert res["has_lesion"] is True
        assert res["calibrated"] is False
        assert res["max_diameter_mm"] is None
        assert res["ortho_diameter_mm"] is None
        assert res["total_area_cm2"] is None
        assert res["lesions"][0]["perimeter_mm"] is None
        # Pixel measurements remain available and accurate
        assert res["max_diameter_px"] > 0
        assert res["total_area_px"] == pytest.approx(1600, rel=0.05)


def test_borderline_probability_thresholding():
    engine = DummyEngine(threshold=0.40)

    prob_map = np.full((10, 10), 0.3999, dtype=np.float32)
    mask = engine.post_process_mask(prob_map, min_area_px=0)
    assert mask.sum() == 0

    prob_map[5, 5] = 0.4001
    mask = engine.post_process_mask(prob_map, min_area_px=0)
    assert mask.sum() == 1
    assert mask[5, 5] == 1


def test_extreme_aspect_ratio_letterbox_preservation():
    prep = UltrasoundPreprocessor(target_size=(512, 512))

    # Extreme panorama image (1000 width x 200 height)
    wide_img = np.ones((200, 1000), dtype=np.uint8) * 128
    padded_wide, scale_params_wide = prep.letterbox_resize(wide_img)

    assert padded_wide.shape == (512, 512)
    assert (scale_params_wide["orig_h"], scale_params_wide["orig_w"]) == (200, 1000)

    # Restore to original size
    restored_wide = prep.inverse_letterbox_mask((padded_wide > 0).astype(np.uint8), scale_params_wide)
    assert restored_wide.shape == (200, 1000)

    # Extreme tall image (200 width x 1000 height)
    tall_img = np.ones((1000, 200), dtype=np.uint8) * 128
    padded_tall, scale_params_tall = prep.letterbox_resize(tall_img)

    assert padded_tall.shape == (512, 512)
    assert (scale_params_tall["orig_h"], scale_params_tall["orig_w"]) == (1000, 200)

    restored_tall = prep.inverse_letterbox_mask((padded_tall > 0).astype(np.uint8), scale_params_tall)
    assert restored_tall.shape == (1000, 200)
