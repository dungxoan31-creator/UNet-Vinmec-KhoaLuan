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


@pytest.mark.parametrize(
    ("stored_spacing", "dicom_spacing", "source"),
    [
        (0.2, None, None),
        (0.3, 0.2, "DICOM"),
        (0.2, 0.2, "UNKNOWN"),
    ],
)
def test_unverified_calibration_never_exposes_physical_spacing(
    stored_spacing, dicom_spacing, source,
):
    from backend.services.source_measurements import calibration_metadata

    assert calibration_metadata(stored_spacing, dicom_spacing, source) == {
        "pixel_spacing_mm": None,
        "calibrated": False,
        "calibration_source": "UNKNOWN",
    }


def test_case_egress_numeric_guard_rejects_extremely_large_integer():
    from backend.app.routers.cases import _finite_physical_value

    assert _finite_physical_value(10**10000) is False


def test_unverified_measurement_egress_preserves_explicit_no_calibration_state():
    from backend.services.measurement_safety import strip_unverified_physical_measurements

    assert strip_unverified_physical_measurements({
        "calibrated": False,
        "calibration_source": "NONE",
        "pixel_spacing_mm": None,
        "diameter_mm": None,
    }) == {
        "calibrated": False,
        "calibration_source": "NONE",
        "pixel_spacing_mm": None,
        "diameter_mm": None,
    }
