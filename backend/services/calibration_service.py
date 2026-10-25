"""
Automatic Ultrasound Calibration Service (Phase 1.3).
Extracts physical calibration (mm/pixel) via:
1. DICOM header (PixelSpacing / SequenceOfUltrasoundRegions)
2. Computer vision ruler tick detection on image margin
3. Fallback to default (0.1 mm/px) with uncalibrated flag
"""

from typing import Any

import cv2
import numpy as np

from backend.core.calibration import normalize_pixel_spacing
from backend.services.image_service import extract_dicom_calibration_spacing


def detect_ruler_spacing_from_raster(image_np: np.ndarray) -> tuple[float | None, float]:
    """
    Detects periodic depth ruler tick marks in the image margins (left or right 12% strip).
    Returns (spacing_mm_per_px, confidence) or (None, 0.0).
    """
    if image_np is None or len(image_np.shape) < 2:
        return None, 0.0

    gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY) if len(image_np.shape) == 3 else image_np
    h, w = gray.shape[:2]
    if h < 100 or w < 100:
        return None, 0.0

    # Inspect left strip (0 to 12% width) and right strip (88% to 100% width)
    margin_w = max(15, int(w * 0.12))
    strips = [
        gray[:, :margin_w],
        gray[:, w - margin_w:],
    ]

    best_spacing = None
    best_conf = 0.0

    for strip in strips:
        # Detect bright horizontal tick lines using a horizontal morphological filter
        # e.g., kernel 1x7
        thresh = cv2.adaptiveThreshold(
            strip, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -5
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
        ticks = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Horizontal projection profile (sum along rows)
        row_energy = np.sum(ticks > 0, axis=1)

        # Find peaks where row energy exceeds threshold
        peak_thresh = max(3, np.percentile(row_energy, 90))
        peaks = np.where(row_energy > peak_thresh)[0]

        if len(peaks) < 5:
            continue

        # Group contiguous peak pixels to single centroid per tick
        tick_centroids = []
        cluster = [peaks[0]]
        for p in peaks[1:]:
            if p == cluster[-1] + 1:
                cluster.append(p)
            else:
                tick_centroids.append(float(np.mean(cluster)))
                cluster = [p]
        if cluster:
            tick_centroids.append(float(np.mean(cluster)))

        if len(tick_centroids) < 5:
            continue

        diffs = np.diff(tick_centroids)
        # Filter reasonable diffs (e.g. between 10px and 120px)
        valid_diffs = diffs[(diffs >= 10) & (diffs <= 120)]
        if len(valid_diffs) < 4:
            continue

        median_delta = float(np.median(valid_diffs))
        std_delta = float(np.std(valid_diffs))

        # Check for regularity: low coefficient of variation
        cv = std_delta / median_delta if median_delta > 0 else 1.0
        if cv < 0.15 and median_delta >= 10:
            # 1 major tick spacing corresponds to 10 mm (1 cm) or 5 mm
            # In typical 500-1000px depth scans, 10mm tick is ~20-80px.
            candidate_spacing = 10.0 / median_delta
            conf = max(0.0, min(1.0, 1.0 - cv * 3.0))
            if conf > best_conf:
                best_spacing = candidate_spacing
                best_conf = conf

    if best_spacing is not None and best_conf >= 0.7:
        try:
            norm_spacing = normalize_pixel_spacing(round(best_spacing, 4))
            return norm_spacing, round(best_conf, 2)
        except Exception:
            return None, 0.0

    return None, 0.0


def get_automatic_calibration(
    file_path: str,
    image_np: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Returns automated calibration dictionary with source, confidence, and calibrated flag.
    """
    # 1. Try DICOM
    if file_path.lower().endswith(".dcm"):
        dcm_spacing = extract_dicom_calibration_spacing(file_path)
        if dcm_spacing is not None:
            return {
                "pixel_spacing_mm": dcm_spacing,
                "calibrated": True,
                "source": "dicom",
                "confidence": 1.0,
            }

    # 2. Try Ruler Detection from Raster
    if image_np is not None:
        ruler_spacing, conf = detect_ruler_spacing_from_raster(image_np)
        if ruler_spacing is not None and conf >= 0.7:
            return {
                "pixel_spacing_mm": ruler_spacing,
                "calibrated": True,
                "source": "ruler_detection",
                "confidence": conf,
            }

    # 3. Fallback Default (Uncalibrated)
    return {
        "pixel_spacing_mm": 0.1,
        "calibrated": False,
        "source": "default_uncalibrated",
        "confidence": 0.0,
    }
