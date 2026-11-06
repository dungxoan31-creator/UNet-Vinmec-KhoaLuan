"""Ultrasound Preprocessing Enhancement Module:
Advanced Speckle Reduction (SRAD & Lee Filter),
Acoustic Caliper / Marker Detection & Inpainting (Telea / Navier-Stokes),
and Pipeline Normalization (Letterbox 512x512 + CLAHE).

Designed for Transvaginal/Pelvic Ovarian Ultrasound Analysis with
Clinical Edge Preservation for thin cyst walls (<2-3 mm) and septations.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ultrasound_preprocessing_enhancement")


# ==============================================================================
# 1. SPECKLE NOISE REDUCTION FILTERS (SRAD & LEE)
# ==============================================================================

from backend.services.ultrasound_enhancement import (  # noqa: E402 -- standalone CLI bootstraps the repository path
    CaliperInpainter,
    SpeckleFilter,
    UltrasoundEnhancer,
    UltrasoundMetrics,
)

__all__ = ["CaliperInpainter", "SpeckleFilter", "UltrasoundEnhancer", "UltrasoundMetrics", "run_benchmark"]


def run_benchmark(sample_path: str | None = None, output_report_dir: str | None = None) -> dict[str, Any]:
    """Execute validation benchmark on a sample ultrasound image or synthetic lesion phantom."""
    report_dir = Path(output_report_dir or "data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    if sample_path and Path(sample_path).exists():
        logger.info("Loading clinical ultrasound image: %s", sample_path)
        image = cv2.imread(sample_path)
    else:
        logger.info("Generating synthetic ovarian lesion phantom with caliper markers...")
        image = np.random.normal(55, 12, (500, 700)).clip(10, 240).astype(np.uint8)
        # Add simulated ovary with thin-walled unilocular cyst (60 px radius)
        cv2.circle(image, (350, 250), 110, 195, thickness=2)  # Thin cyst wall
        cv2.circle(image, (350, 250), 108, 18, thickness=-1)  # Anechoic fluid interior
        # Add simulated internal papillary projection (height 4 px, width 6 px)
        cv2.circle(image, (350, 142), 6, 170, thickness=-1)
        # Add sonographer measurement calipers ('+' crosshairs at diameter ends)
        cv2.drawMarker(image, (350, 140), 255, markerType=cv2.MARKER_CROSS, markerSize=14, thickness=1)
        cv2.drawMarker(image, (350, 360), 255, markerType=cv2.MARKER_CROSS, markerSize=14, thickness=1)
        # Dotted measurement line
        for y in range(148, 355, 6):
            cv2.circle(image, (350, y), 1, 255, -1)
        # Text annotation
        cv2.putText(image, "D1: 44.0mm", (360, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 255, 1)

    enhancer_lee = UltrasoundEnhancer(denoise_method="lee", enable_caliper_removal=True)
    enhancer_srad = UltrasoundEnhancer(denoise_method="srad", enable_caliper_removal=True, srad_iterations=8)

    res_lee = enhancer_lee.enhance_and_preprocess(image)
    res_srad = enhancer_srad.enhance_and_preprocess(image)

    # Save visualization montage
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    h_vis, w_vis = 256, 350
    v1 = cv2.resize(gray, (w_vis, h_vis))
    v2 = cv2.resize(res_lee["inpainted_gray"], (w_vis, h_vis))
    v3 = cv2.resize(res_lee["denoised_gray"], (w_vis, h_vis))
    v4 = cv2.resize(res_srad["denoised_gray"], (w_vis, h_vis))

    top_row = np.hstack([v1, v2])
    bottom_row = np.hstack([v3, v4])
    montage = np.vstack([top_row, bottom_row])

    montage_path = report_dir / "ultrasound_enhancement_comparison.png"
    cv2.imwrite(str(montage_path), montage)
    logger.info("Visual comparison saved to: %s", montage_path)

    results = {
        "image_shape": image.shape,
        "caliper_pixels_detected": res_lee["metrics"]["caliper_pixels_detected"],
        "lee_metrics": res_lee["metrics"],
        "srad_metrics": res_srad["metrics"],
        "montage_path": str(montage_path),
    }

    print("\n" + "=" * 70)
    print("ULTRASOUND PREPROCESSING ENHANCEMENT BENCHMARK REPORT")
    print("=" * 70)
    print(f"Input Shape: {image.shape}")
    print(f"Caliper Pixels Detected & Inpainted: {results['caliper_pixels_detected']}")
    print("-" * 70)
    print("Lee Filter Performance:")
    print(f"  - Edge Preservation Index (EPI): {res_lee['metrics']['edge_preservation_index']:.4f}")
    print(f"  - SNR Gain:                      +{res_lee['metrics']['snr_gain_db']:.2f} dB")
    print(f"  - ENL Improvement:               {res_lee['metrics']['enl_improvement_ratio']:.2f}x")
    print(f"  - PSNR / SSIM:                   {res_lee['metrics']['psnr_db']:.2f} dB / {res_lee['metrics']['ssim']:.4f}")
    print("-" * 70)
    print("SRAD Filter Performance:")
    print(f"  - Edge Preservation Index (EPI): {res_srad['metrics']['edge_preservation_index']:.4f}")
    print(f"  - SNR Gain:                      +{res_srad['metrics']['snr_gain_db']:.2f} dB")
    print(f"  - ENL Improvement:               {res_srad['metrics']['enl_improvement_ratio']:.2f}x")
    print(f"  - PSNR / SSIM:                   {res_srad['metrics']['psnr_db']:.2f} dB / {res_srad['metrics']['ssim']:.4f}")
    print("=" * 70 + "\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ultrasound Preprocessing Enhancement Demo")
    parser.add_argument("--image", type=str, default="dataset/2d/images/1.JPG", help="Path to test ultrasound image")
    parser.add_argument("--outdir", type=str, default="data/reports", help="Output directory for reports")
    args = parser.parse_args()

    sample_img = args.image if Path(args.image).exists() else None
    run_benchmark(sample_path=sample_img, output_report_dir=args.outdir)
