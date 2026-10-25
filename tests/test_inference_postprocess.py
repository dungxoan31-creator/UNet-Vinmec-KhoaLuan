"""
Unit tests for InferenceEngine clinical post-processing:
- Morphological closing to seal internal lesion micro-holes
- Connected components speckle filtering
- Clinical safety guardrail: Never completely wipe out faint small lesions
"""

import numpy as np

from backend.services.inference_engine import InferenceEngine


def test_post_process_mask_backward_compatibility():
    """Default post_process_mask must preserve raw thresholding."""
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.min_area_px = 0
    engine.apply_morphology = False

    prob_map = np.zeros((16, 16), dtype=np.float32)
    prob_map[2, 3] = 0.8
    prob_map[10, 10] = 0.6
    prob_map[10, 11] = 0.2

    # Without extra parameters, behaves identically to raw threshold
    raw_pred = engine.post_process_mask(prob_map)
    assert raw_pred[2, 3] == 1
    assert raw_pred[10, 10] == 1
    assert raw_pred[10, 11] == 0
    assert raw_pred.sum() == 2


def test_post_process_mask_speckle_removal():
    """Removes speckles below min_area_px when a main lesion is present."""
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.min_area_px = 0
    engine.apply_morphology = False

    prob_map = np.zeros((100, 100), dtype=np.float32)
    # Main lesion of 400 pixels (20x20)
    prob_map[20:40, 20:40] = 0.9
    # Noise speckle 1: 3 pixels
    prob_map[80, 80:83] = 0.85
    # Noise speckle 2: 8 pixels
    prob_map[5, 5:13] = 0.75

    cleaned = engine.post_process_mask(prob_map, min_area_px=50)

    # Main lesion is preserved
    assert cleaned[20:40, 20:40].sum() == 400
    # Speckles are removed
    assert cleaned[80, 80:83].sum() == 0
    assert cleaned[5, 5:13].sum() == 0
    assert cleaned.sum() == 400


def test_post_process_mask_clinical_fallback_retains_largest():
    """If all lesions are smaller than min_area_px, retain the largest component."""
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.min_area_px = 0
    engine.apply_morphology = False

    prob_map = np.zeros((100, 100), dtype=np.float32)
    # Small lesion 1: 15 pixels
    prob_map[10:13, 10:15] = 0.8
    # Smaller noise 2: 2 pixels
    prob_map[70, 70:72] = 0.75

    # Threshold is 50 px, but fallback must keep the 15 px lesion
    cleaned = engine.post_process_mask(prob_map, min_area_px=50)

    assert cleaned[10:13, 10:15].sum() == 15
    assert cleaned[70, 70:72].sum() == 0
    assert cleaned.sum() == 15


def test_post_process_mask_morphology_closing():
    """Morphology closing seals small interior holes in a solid lesion."""
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.threshold = 0.5
    engine.min_area_px = 0
    engine.apply_morphology = False

    prob_map = np.zeros((50, 50), dtype=np.float32)
    # Create a 15x15 solid lesion
    prob_map[15:30, 15:30] = 0.95
    # Punch a 1x1 micro-hole in the center
    prob_map[22, 22] = 0.0

    raw_mask = engine.post_process_mask(prob_map, apply_morphology=False)
    assert raw_mask[22, 22] == 0

    closed_mask = engine.post_process_mask(prob_map, apply_morphology=True, morph_kernel_size=3)
    # The 1x1 micro-hole is sealed
    assert closed_mask[22, 22] == 1
