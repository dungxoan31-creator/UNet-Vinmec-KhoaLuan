"""A single 2D image cannot provide a third diameter or lesion volume."""

import numpy as np

from backend.services.inference_engine import InferenceEngine


def test_calibrated_2d_mask_does_not_report_unobserved_volume():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 0.1
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[100:200, 150:250] = 1
    result = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=0.2)
    assert result["max_diameter_mm"] > 0
    assert result["total_area_cm2"] > 0
    assert result["d3_mm"] is None
    assert result["total_volume_cm3"] is None
    assert result["lesions"][0]["d3_mm"] is None
    assert result["lesions"][0]["volume_cm3"] is None
