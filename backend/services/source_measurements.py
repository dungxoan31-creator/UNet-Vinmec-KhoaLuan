"""Calipers in decoded source coordinates; no assumed physical pixel spacing."""

import math

from backend.services.inference_engine import InferenceEngine


def calibration_metadata(stored_spacing, dicom_spacing=None):
    spacing = stored_spacing
    if spacing is None or not math.isfinite(spacing) or spacing <= 0:
        return {"pixel_spacing_mm": None, "calibrated": False, "calibration_source": "NONE"}
    is_dicom = (
        dicom_spacing is not None and math.isfinite(dicom_spacing) and dicom_spacing > 0
        and math.isclose(spacing, dicom_spacing, rel_tol=.001, abs_tol=.00005)
    )
    return {
        "pixel_spacing_mm": float(spacing), "calibrated": True,
        "calibration_source": "DICOM" if is_dicom else "MANUAL",
    }


def measure_source_mask(decoded, rle_mask, preprocessor, engine, calibration):
    """Reuse the existing contour/min-area-rectangle algorithm after inverse letterbox.

    Diameters refer to the largest-area contour; total area sums retained contours.
    The existing algorithm excludes contours smaller than 50 source pixels².
    Unit spacing is used only to extract geometry, never presented as calibration.
    """
    _, transform = preprocessor.letterbox_resize(decoded)
    source_mask = preprocessor.inverse_letterbox_mask(InferenceEngine.rle_to_mask(rle_mask), transform)
    measurements = engine.extract_calipers_and_measurements(source_mask, pixel_spacing_mm=1.0)
    spacing = calibration["pixel_spacing_mm"]
    scale_x = int(transform["orig_w"] * transform["scale"]) / transform["orig_w"]
    scale_y = int(transform["orig_h"] * transform["scale"]) / transform["orig_h"]
    components_to_scale = list(measurements.get("lesions", [])) + list(measurements.get("filtered_components", []))
    for lesion in components_to_scale:
        # Normalize the existing engine's endpoint labels to the actual major/minor
        # axes, without changing its inference overlay or contour calculation.
        if math.dist(*lesion["caliper_dmax_points"]) < math.dist(*lesion["caliper_dorth_points"]):
            lesion["caliper_dmax_points"], lesion["caliper_dorth_points"] = (
                lesion["caliper_dorth_points"], lesion["caliper_dmax_points"]
            )
        for key in ("caliper_dmax_points", "caliper_dorth_points"):
            lesion[f"viewer_{key}"] = [
                [x * scale_x + transform["pad_x"], y * scale_y + transform["pad_y"]]
                for x, y in lesion[key]
            ]
        if spacing is None:
            for key in ("max_diameter_mm", "ortho_diameter_mm", "area_cm2", "perimeter_mm"):
                lesion[key] = None
        else:
            for name, points in (("max_diameter_mm", "caliper_dmax_points"), ("ortho_diameter_mm", "caliper_dorth_points")):
                a, b = lesion[points]
                lesion[name] = round(math.dist(a, b) * spacing, 2)
            lesion["area_cm2"] = round(lesion["area_px"] * spacing**2 / 100, 3)
            lesion["perimeter_mm"] = round(lesion["perimeter_mm"] * spacing, 2)
    dominant = (
        measurements["lesions"][0]
        if measurements.get("lesions")
        else (measurements.get("filtered_components", [{}])[0] if measurements.get("filtered_components") else {})
    )
    total_area = sum(lesion["area_px"] for lesion in measurements.get("lesions", [])) or sum(
        comp["area_px"] for comp in measurements.get("filtered_components", [])
    )
    measurements.update({
        **calibration,
        "coordinate_space": "decoded-source-image",
        "source_dimensions": [transform["orig_w"], transform["orig_h"]],
        "max_diameter_px": dominant.get("max_diameter_px", 0.0),
        "ortho_diameter_px": dominant.get("ortho_diameter_px", 0.0),
        "total_area_px": total_area,
        "max_diameter_mm": dominant.get("max_diameter_mm", 0.0) if spacing is not None else None,
        "ortho_diameter_mm": dominant.get("ortho_diameter_mm", 0.0) if spacing is not None else None,
        "total_area_cm2": round(total_area * spacing**2 / 100, 3) if spacing is not None else None,
        "measurement_method": "external_contour_min_area_rectangle",
        "diameter_reference": "largest_area_contour",
        "min_contour_area_px": 50,
    })
    return measurements
