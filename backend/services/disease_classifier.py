"""Compatibility facade for the single verified, image-level research classifier.

Images use OpenCV BGR channel order, as at training time. Masks describe geometry
only: they never crop the classifier input or establish a clinical risk category.
"""

from pathlib import Path

import cv2
import numpy as np

from backend.core.calibration import normalize_pixel_spacing
from backend.core.mmotu_labels import MMOTU_8_CLASSES
from backend.services.diagnostic_engine import LESION_VI_MAP
from backend.services.image_classifier import ResearchImageClassifier, image_classifier


class DiseaseClassifierService:
    def __init__(self, checkpoint_path: str | Path | None = None, device: str | None = None):
        # Reuse one bounded CPU model across API and CLI calls. The device argument
        # remains accepted for older callers; classification does not compete for VRAM.
        self.classifier = image_classifier if checkpoint_path is None else ResearchImageClassifier(checkpoint_path)
        self.class_names = list(MMOTU_8_CLASSES)
        self.device = "cpu"

    @property
    def is_loaded(self):
        return self.classifier.model is not None

    def predict_disease(self, image, mask=None, pixel_spacing_mm=None):
        if (not isinstance(image, np.ndarray) or image.size == 0 or image.dtype != np.uint8
                or image.ndim not in (2, 3)
                or (image.ndim == 3 and image.shape[2] not in (1, 3, 4))
                or min(image.shape[:2]) < 8):
            raise ValueError("Hợp lệ: Cần ảnh uint8 không rỗng, ít nhất 8×8 pixel.")
        if image.ndim == 3 and image.shape[2] == 1:
            image = image[:, :, 0]

        measurements = {
            "lesion_detected": False, "area_px": 0,
            "equivalent_diameter_px": 0.0, "equivalent_diameter_mm": None,
            "max_diameter_mm": None, "area_cm2": None,
            "coordinate_space": "decoded-source-image",
            "measurement_method": "foreground_area_and_min_area_rectangle",
        }
        if mask is not None:
            if (not isinstance(mask, np.ndarray) or mask.ndim != 2
                    or mask.shape != image.shape[:2] or not np.isfinite(mask).all()):
                raise ValueError("Mask must be finite, 2D and match decoded source image dimensions.")
            binary = (mask > 0).astype(np.uint8)
            area = int(binary.sum())
            spacing = normalize_pixel_spacing(pixel_spacing_mm)
            equivalent = float(np.sqrt(4 * area / np.pi))
            measurements.update(lesion_detected=area > 0, area_px=area, equivalent_diameter_px=round(equivalent, 2))
            if spacing is not None and area > 0:
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                dominant = max(contours, key=cv2.contourArea)
                dimensions = cv2.minAreaRect(dominant)[1]
                measurements.update(
                    equivalent_diameter_mm=round(equivalent * spacing, 2),
                    max_diameter_mm=round(max(dimensions) * spacing, 2),
                    area_cm2=round(area * spacing**2 / 100, 3),
                )

        result = self.classifier.predict(image)
        ranked = sorted(result.get("probabilities", {}).items(), key=lambda item: item[1], reverse=True)
        label = result.get("suggested_label")
        return {
            **result,
            "suggested_label_vi": LESION_VI_MAP.get(label) if label else None,
            "confidence": ranked[0][1] if ranked else 0.0,
            "top3": [(key, LESION_VI_MAP.get(key, key), value) for key, value in ranked[:3]],
            "abstain": result["status"] != "PREDICTED",
            "abstain_reason": result.get("reason") or (
                "LOW_CONFIDENCE_OR_MARGIN" if result["status"] == "ABSTAIN" else None
            ),
            "pathology_category": None,
            "is_malignant_suspected": None,
            "mask_measurements": measurements,
        }
