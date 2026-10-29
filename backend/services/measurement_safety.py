"""Fail-closed guards for physical measurements crossing API boundaries."""

import math

TRUSTED_CALIBRATION_SOURCES = frozenset({"MANUAL", "DICOM"})


def is_finite_physical_value(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def strip_unverified_physical_measurements(value):
    if isinstance(value, list):
        return [strip_unverified_physical_measurements(item) for item in value]
    if not isinstance(value, dict):
        return value
    sanitized = {}
    for key, item in value.items():
        if key.endswith(("_mm", "_mm2", "_cm2")) or key == "pixel_spacing_mm":
            sanitized[key] = None
        elif key == "calibrated":
            sanitized[key] = False
        elif key == "calibration_source":
            sanitized[key] = item if item in ("NONE", "UNKNOWN") else "UNKNOWN"
        else:
            sanitized[key] = strip_unverified_physical_measurements(item)
    return sanitized


def prediction_measurements_match_calibration(measurements, calibration, provenance) -> bool:
    """Trust prediction millimetres only when image, result and provenance agree."""
    if not isinstance(measurements, dict) or not isinstance(calibration, dict):
        return False
    provenance = provenance if isinstance(provenance, dict) else {}
    source = calibration.get("calibration_source")
    expected_spacing = calibration.get("pixel_spacing_mm")
    recorded_spacing = provenance.get("pixel_spacing_mm")
    if (
        calibration.get("calibrated") is not True
        or source not in TRUSTED_CALIBRATION_SOURCES
        or measurements.get("calibrated") is not True
        or measurements.get("calibration_source") != source
        or not is_finite_physical_value(expected_spacing)
        or not is_finite_physical_value(recorded_spacing)
    ):
        return False
    if provenance.get("calibration_source") not in (None, source):
        return False
    try:
        if not math.isclose(
            float(expected_spacing), float(recorded_spacing), rel_tol=0.001, abs_tol=0.00005
        ):
            return False
        measurement_spacing = measurements.get("pixel_spacing_mm")
        if measurement_spacing is not None and (
            not is_finite_physical_value(measurement_spacing)
            or not math.isclose(
                float(expected_spacing), float(measurement_spacing), rel_tol=0.001, abs_tol=0.00005
            )
        ):
            return False
    except (OverflowError, TypeError, ValueError):
        return False
    return True
