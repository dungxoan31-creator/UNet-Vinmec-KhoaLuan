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


def test_missing_calibration_does_not_fall_back_to_default_spacing():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 0.1
    mask = np.zeros((128, 128), dtype=np.uint8)
    mask[20:80, 30:90] = 1

    result = engine.extract_calipers_and_measurements(mask)

    assert result["max_diameter_mm"] is None
    assert result["ortho_diameter_mm"] is None
    assert result["total_area_cm2"] is None
    assert result["lesions"][0]["max_diameter_mm"] is None
    assert result["lesions"][0]["area_cm2"] is None
    assert result["lesions"][0]["perimeter_mm"] is None
    assert result["lesions"][0]["max_diameter_px"] > 0


def test_empty_mask_has_no_zero_mm_measurements_without_calibration():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 0.1

    result = engine.extract_calipers_and_measurements(np.zeros((64, 64), dtype=np.uint8))

    assert result["max_diameter_mm"] is None
    assert result["ortho_diameter_mm"] is None
    assert result["total_area_cm2"] is None


def test_mixed_size_regions_expose_filtered_region_warning():
    import cv2
    mask = np.zeros((128, 128), dtype=np.uint8)
    cv2.rectangle(mask, (10, 10), (40, 40), 1, -1)
    cv2.rectangle(mask, (80, 80), (84, 84), 1, -1)
    result = InferenceEngine.__new__(InferenceEngine).extract_calipers_and_measurements(mask, 0.2)
    assert len(result["lesions"]) == 1
    assert len(result["filtered_components"]) == 1
    assert result["warning"] and "dưới ngưỡng" in result["warning"]


def test_mixed_size_source_measurement_retains_warning():
    import cv2

    from backend.services.preprocessor import UltrasoundPreprocessor
    from backend.services.source_measurements import measure_source_mask
    mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.rectangle(mask, (10, 10), (40, 40), 1, -1)
    cv2.rectangle(mask, (80, 80), (84, 84), 1, -1)
    engine = InferenceEngine.__new__(InferenceEngine)
    result = measure_source_mask(mask, engine.mask_to_rle(mask), UltrasoundPreprocessor(), engine,
        {"pixel_spacing_mm": 0.2, "calibrated": True, "calibration_source": "MANUAL"})
    assert result["exclusion_reason"] == "some_components_below_min_area"
    assert "dưới ngưỡng" in result["warning"]
