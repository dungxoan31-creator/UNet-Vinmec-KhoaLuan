"""Extract geometric and pixel-level features from an ultrasound mask.

These features do not establish lesion morphology, diagnosis, or risk category.
"""

import cv2
import numpy as np

from backend.core.calibration import normalize_pixel_spacing


class MorphologicalFeatureExtractor:
    @staticmethod
    def _normalize_spacing(value):
        return normalize_pixel_spacing(value)

    def extract_features(self, img_gray: np.ndarray, binary_mask: np.ndarray, pixel_spacing_mm: float = None) -> dict:
        """
        Extracts comprehensive geometric, textural, and acoustic biomarkers from ultrasound image and lesion mask.
        """
        if not isinstance(img_gray, np.ndarray) or not isinstance(binary_mask, np.ndarray):
            raise ValueError("image and mask must be NumPy arrays.")
        if img_gray.ndim != 2 or binary_mask.ndim != 2:
            raise ValueError("image and mask must be two-dimensional grayscale arrays.")
        if img_gray.size == 0 or binary_mask.size == 0:
            raise ValueError("image and mask must not be empty.")
        if img_gray.shape != binary_mask.shape:
            raise ValueError("image and mask dimensions must match.")
        for name, array in (("image", img_gray), ("mask", binary_mask)):
            numeric = (
                np.issubdtype(array.dtype, np.integer)
                or np.issubdtype(array.dtype, np.floating)
                or np.issubdtype(array.dtype, np.bool_)
            )
            if not numeric or not np.isfinite(array).all():
                raise ValueError(f"{name} must contain finite numeric values.")

        spacing = self._normalize_spacing(pixel_spacing_mm)
        mask = (binary_mask > 0).astype(np.uint8)

        # An empty mask means only that no region was segmented; it does not
        # establish that the ovary is normal.
        if mask.sum() == 0:
            return {
                "has_lesion": False,
                "lesion_count": 0,
                "measurements": {
                    "max_diameter_mm": None,
                    "ortho_diameter_mm": None,
                    "max_diameter_px": 0.0,
                    "ortho_diameter_px": 0.0,
                    "depth_d3_mm": None,
                    "total_area_cm2": None,
                    "area_px": 0.0,
                    "perimeter_mm": None,
                    "perimeter_px": 0.0,
                    "volume_cm3": None,
                    "circularity": None,
                    "solidity": None,
                    "calibrated": spacing is not None,
                },
                "acoustic_profile": {
                    "internal_mean_intensity": 0.0,
                    "internal_std_intensity": 0.0,
                    "echogenicity_class": None,
                    "echogenicity_label": None,
                    "posterior_shadow_index": None,
                    "acoustic_pattern": None,
                },
                "cdss_classification": self._not_evaluated_cdss(),
            }

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self._empty_response()

        # Primary lesion contour
        main_cnt = max(contours, key=cv2.contourArea)
        area_px = float(cv2.contourArea(main_cnt))
        if area_px == 0:
            return self._empty_response()

        # Calipers & Geometry
        rect = cv2.minAreaRect(main_cnt)
        (center_x, center_y), (dim_w, dim_h), angle = rect
        d1_px = max(dim_w, dim_h)
        d2_px = min(dim_w, dim_h)
        d1_mm = round(d1_px * spacing, 1) if spacing is not None else None
        d2_mm = round(d2_px * spacing, 1) if spacing is not None else None
        area_cm2 = round(area_px * (spacing ** 2) / 100.0, 2) if spacing is not None else None
        perimeter_px = cv2.arcLength(main_cnt, True)
        perimeter_mm = round(perimeter_px * spacing, 1) if spacing is not None else None

        circularity = round((4 * np.pi * area_px) / (perimeter_px ** 2), 3) if perimeter_px > 0 else 0.0
        hull = cv2.convexHull(main_cnt)
        hull_area = cv2.contourArea(hull)
        solidity = round(area_px / hull_area, 3) if hull_area > 0 else 0.0

        # Pixel Intensity Statistics inside Lesion
        lesion_pixels = img_gray[mask > 0]
        mean_val = float(np.mean(lesion_pixels))
        std_val = float(np.std(lesion_pixels))
        median_val = float(np.median(lesion_pixels))

        # Posterior Acoustic Shadowing/Enhancement Index
        # Compare 30px region directly below the lesion vs lateral background
        h, w = img_gray.shape[:2]
        x, y, bw, bh = cv2.boundingRect(main_cnt)
        below_y_start = min(h - 1, y + bh)
        below_y_end = min(h, below_y_start + 40)
        below_x_start = max(0, x)
        below_x_end = min(w, x + bw)

        shadow_index = None
        if below_y_end > below_y_start and below_x_end > below_x_start:
            below_region = img_gray[below_y_start:below_y_end, below_x_start:below_x_end]
            lateral_left = img_gray[below_y_start:below_y_end, max(0, x - 30):x] if x > 30 else np.array([])
            lateral_right = img_gray[below_y_start:below_y_end, x + bw:min(w, x + bw + 30)] if x + bw + 30 < w else np.array([])

            lat_pixels = []
            if lateral_left.size > 0:
                lat_pixels.append(np.mean(lateral_left))
            if lateral_right.size > 0:
                lat_pixels.append(np.mean(lateral_right))

            if lat_pixels and np.mean(lat_pixels) > 0:
                shadow_index = round(float(np.mean(below_region)) / float(np.mean(lat_pixels)), 2)

        cdss = self._not_evaluated_cdss()

        return {
            "has_lesion": True,
            "lesion_count": len(contours),
            "measurements": {
                "max_diameter_mm": d1_mm,
                "ortho_diameter_mm": d2_mm,
                "max_diameter_px": round(float(d1_px), 2),
                "ortho_diameter_px": round(float(d2_px), 2),
                "depth_d3_mm": None,
                "total_area_cm2": area_cm2,
                "area_px": round(area_px, 2),
                "perimeter_mm": perimeter_mm,
                "perimeter_px": round(float(perimeter_px), 2),
                "volume_cm3": None,
                "circularity": circularity,
                "solidity": solidity,
                "calibrated": spacing is not None,
            },
            "acoustic_profile": {
                "internal_mean_intensity": round(mean_val, 1),
                "internal_std_intensity": round(std_val, 1),
                "internal_median_intensity": round(median_val, 1),
                "posterior_shadow_index": shadow_index,
                "echogenicity_class": None,
                "echogenicity_label": None,
                "acoustic_pattern": None,
            },
            "cdss_classification": cdss
        }

    @staticmethod
    def _not_evaluated_cdss() -> dict:
        """Mask and pixel statistics cannot supply clinician-entered descriptors."""
        return {
            "status": "NOT_EVALUATED",
            "primary_suspicion": None,
            "differential_diagnoses": [],
            "orads_category": None,
            "orads_label": None,
            "malignancy_risk": None,
            "iota_rule": "NOT_EVALUATED",
            "confidence_score": None,
            "clinical_alert": None,
            "management": None,
            "requires_clinician_confirmation": True,
        }

    def _empty_response(self):
        return {
            "has_lesion": False,
            "lesion_count": 0,
            "measurements": {
                "max_diameter_mm": None,
                "ortho_diameter_mm": None,
                "max_diameter_px": 0.0,
                "ortho_diameter_px": 0.0,
                "depth_d3_mm": None,
                "total_area_cm2": None,
                "area_px": 0.0,
                "perimeter_mm": None,
                "perimeter_px": 0.0,
                "volume_cm3": None,
                "circularity": None,
                "solidity": None,
                "calibrated": False,
            },
            "acoustic_profile": {
                "internal_mean_intensity": 0.0,
                "internal_std_intensity": 0.0,
                "echogenicity_class": None,
                "echogenicity_label": None,
                "posterior_shadow_index": None,
                "acoustic_pattern": None,
            },
            "cdss_classification": self._not_evaluated_cdss(),
        }
