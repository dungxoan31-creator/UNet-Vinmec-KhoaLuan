import pytest


def test_pixel_spacing_rejects_numbers_that_cannot_be_safely_scaled():
    from backend.services.image_service import validate_pixel_spacing

    for spacing in (10**10000, 1e200):
        with pytest.raises(ValueError):
            validate_pixel_spacing(spacing)


def test_measurement_spacing_normalizers_fail_closed_on_overflowing_integer():
    from backend.services.inference_engine import InferenceEngine
    from backend.services.morphology_extractor import MorphologicalFeatureExtractor

    spacing = 10**10000
    assert InferenceEngine._normalize_pixel_spacing(spacing) is None
    assert MorphologicalFeatureExtractor._normalize_spacing(spacing) is None


def test_stored_calibration_with_overflowing_value_is_not_trusted():
    from backend.services.source_measurements import calibration_metadata

    metadata = calibration_metadata(10**10000)

    assert metadata == {
        "pixel_spacing_mm": None,
        "calibrated": False,
        "calibration_source": "NONE",
    }
