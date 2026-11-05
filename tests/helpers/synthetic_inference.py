"""Deterministic segmentation stub for isolated API-contract tests only.

This helper does not load a checkpoint or model weights and must never be used
to claim inference accuracy, clinical performance, or production readiness.
"""

import base64

import cv2
import numpy as np

from backend.services.inference_engine import InferenceEngine


def enable_synthetic_inference(monkeypatch, registry):
    """Replace inference with a fixed, explicitly non-clinical test mask."""
    adapter = registry.get_primary_adapter()
    monkeypatch.setattr(adapter, "is_loaded", True)

    def predict(_tensor, _padded_gray, *, pixel_spacing_mm=None, generate_overlay=False, **_kwargs):
        mask = np.zeros((512, 512), dtype=np.uint8)
        mask[224:288, 224:288] = 1
        encoded, png = cv2.imencode(".png", mask * 255)
        overlay = (
            "data:image/png;base64," + base64.b64encode(png).decode("ascii")
            if generate_overlay and encoded
            else None
        )
        measurements = {
            "has_lesion": True,
            "calibrated": pixel_spacing_mm is not None,
            "max_diameter_px": 64.0,
            "max_diameter_mm": 64.0 * pixel_spacing_mm if pixel_spacing_mm is not None else None,
            "ortho_diameter_mm": None,
            "d3_mm": None,
            "total_area_cm2": None,
            "total_area_px": 4096.0,
            "total_volume_cm3": None,
            "total_lesions": 1,
            "lesions": [{
                "lesion_id": 1,
                "center": [256.0, 256.0],
                "max_diameter_mm": 64.0 * pixel_spacing_mm if pixel_spacing_mm is not None else None,
                "ortho_diameter_mm": None,
                "area_cm2": None,
                "perimeter_mm": None,
                "max_diameter_px": 64.0,
                "area_px": 4096.0,
            }],
            "follicles": {
                "count": 0,
                "count_in_range": None if pixel_spacing_mm is None else 0,
                "diameters_px": [],
                "diameters_mm": None if pixel_spacing_mm is None else [],
            },
        }
        return {
            "rle_mask": InferenceEngine.mask_to_rle(mask),
            "binary_mask_np": mask,
            "confidence_score": 0.5,
            "mask_pixel_confidence": 0.5,
            "score_type": "synthetic_test_stub_no_model",
            "measurements": measurements,
            "uncertainty": {"is_uncertain": True, "uncertainty_level": "HIGH"},
            "quality_gate": {
                "passed": False,
                "validated": False,
                "status": "TEST_STUB_ONLY",
                "score_type": "synthetic_test_stub_no_model",
            },
            "acoustic_profile": {},
            "cdss_classification": {},
            "ai_diagnosis": None,
            "overlay_base64": overlay,
            "uncertainty_map_png": None,
            "provenance": {
                "model_name": "Synthetic deterministic test stub",
                "architecture": "Synthetic deterministic test stub (no weights)",
                "model_version": "test-only",
                "model_checksum": None,
                "threshold": 0.5,
                "pixel_spacing_mm": pixel_spacing_mm,
            },
            "timings": {"model_forward_ms": 0.0},
        }

    monkeypatch.setattr(registry, "predict", predict)
    return adapter
