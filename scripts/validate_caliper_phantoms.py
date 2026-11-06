"""Synthetic Phantom Caliper Validation Script.

Validates automated 2D caliper measurement accuracy (Dmax, Dorth) on 50 synthetic
ovarian lesion phantoms across 5 repeated measurement perturbation iterations.
Evaluates bias, MAE, ICC(2,1), and Bland-Altman Limits of Agreement under Assumption A2.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cv2
import numpy as np

from backend.services.inference_engine import InferenceEngine


def calculate_icc_2_1(data: np.ndarray) -> float:
    """Calculate Two-Way Random, Single Measure, Absolute Agreement ICC(2,1).

    Args:
        data: np.ndarray of shape (n_targets, k_raters/repetitions)
    Returns:
        float: ICC(2,1) value between -1.0 and 1.0
    """
    n, k = data.shape
    if n < 2 or k < 2:
        return 1.0

    # Overall mean
    grand_mean = np.mean(data)

    # Row means (target means)
    row_means = np.mean(data, axis=1)

    # Column means (rater / repetition means)
    col_means = np.mean(data, axis=0)

    # Sum of squares
    sst = np.sum((data - grand_mean) ** 2)
    ssr = k * np.sum((row_means - grand_mean) ** 2)
    ssc = n * np.sum((col_means - grand_mean) ** 2)
    sse = sst - ssr - ssc

    # Mean squares
    msr = ssr / (n - 1)
    msc = ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1))

    # ICC(2,1) formula (McGraw & Wong 1996 / Shrout & Fleiss 1979)
    denominator = msr + (k - 1) * mse + (k / n) * (msc - mse)
    if denominator == 0:
        return 1.0
    icc = (msr - mse) / denominator
    return float(np.clip(icc, -1.0, 1.0))


def calculate_bland_altman(measured: np.ndarray, ground_truth: np.ndarray) -> Dict[str, float]:
    """Compute Bland-Altman bias, limits of agreement, and confidence intervals."""
    diff = measured - ground_truth
    mean_bias = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1))
    loa_upper = float(mean_bias + 1.96 * sd_diff)
    loa_lower = float(mean_bias - 1.96 * sd_diff)
    se_bias = sd_diff / math.sqrt(len(diff))
    ci95_bias = [float(mean_bias - 1.96 * se_bias), float(mean_bias + 1.96 * se_bias)]

    return {
        "mean_bias_mm": round(mean_bias, 4),
        "sd_bias_mm": round(sd_diff, 4),
        "loa_upper_mm": round(loa_upper, 4),
        "loa_lower_mm": round(loa_lower, 4),
        "ci95_bias_lower_mm": round(ci95_bias[0], 4),
        "ci95_bias_upper_mm": round(ci95_bias[1], 4),
    }


def generate_synthetic_phantoms(n: int = 50, seed: int = 20261030) -> List[Dict[str, Any]]:
    """Generate 50 synthetic lesion phantoms with known ground-truth major & minor axes."""
    rng = np.random.RandomState(seed)
    phantoms = []

    for i in range(n):
        # Spacing in typical transvaginal ultrasound range [0.12, 0.28] mm/pixel
        spacing = float(rng.uniform(0.15, 0.25))

        # Size category
        if i < 15:
            # Small follicle/cyst: Dmax 10-25 mm
            d_max_mm = float(rng.uniform(10.0, 25.0))
            ratio = float(rng.uniform(0.60, 0.95))
            d_orth_mm = d_max_mm * ratio
            shape_type = "ellipse"
        elif i < 35:
            # Medium cyst: Dmax 26-55 mm
            d_max_mm = float(rng.uniform(26.0, 55.0))
            ratio = float(rng.uniform(0.45, 0.85))
            d_orth_mm = d_max_mm * ratio
            shape_type = rng.choice(["ellipse", "rounded_rect", "lobulated"])
        else:
            # Large complex cyst: Dmax 56-85 mm
            d_max_mm = float(rng.uniform(56.0, 85.0))
            ratio = float(rng.uniform(0.40, 0.80))
            d_orth_mm = d_max_mm * ratio
            shape_type = rng.choice(["ellipse", "lobulated", "irregular"])

        angle_deg = float(rng.uniform(0.0, 180.0))
        center = (256, 256)

        # Convert target mm to target pixels
        target_max_px = d_max_mm / spacing
        target_orth_px = d_orth_mm / spacing

        mask = np.zeros((512, 512), dtype=np.uint8)

        if shape_type == "ellipse":
            # Semi-axes in pixels
            axis_major = target_max_px / 2.0
            axis_minor = target_orth_px / 2.0
            cv2.ellipse(
                mask,
                (int(center[0]), int(center[1])),
                (int(round(axis_major)), int(round(axis_minor))),
                int(round(angle_deg)),
                0,
                360,
                255,
                -1,
            )
        elif shape_type == "rounded_rect":
            # Oriented rectangle
            rect = (center, (target_max_px, target_orth_px), angle_deg)
            box = cv2.boxPoints(rect).astype(np.int32)
            cv2.drawContours(mask, [box], 0, 255, -1)
            # Smooth corners slightly with morphology
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        elif shape_type == "lobulated":
            # Primary lobe + secondary overlapping lobe
            axis_major = (target_max_px * 0.85) / 2.0
            axis_minor = target_orth_px / 2.0
            cv2.ellipse(
                mask,
                (int(center[0] - target_max_px * 0.08), int(center[1])),
                (int(round(axis_major)), int(round(axis_minor))),
                int(round(angle_deg)),
                0,
                360,
                255,
                -1,
            )
            cv2.ellipse(
                mask,
                (int(center[0] + target_max_px * 0.12), int(center[1])),
                (int(round(axis_major * 0.7)), int(round(axis_minor * 0.8))),
                int(round(angle_deg + 15)),
                0,
                360,
                255,
                -1,
            )
        else:  # irregular
            axis_major = target_max_px / 2.0
            axis_minor = target_orth_px / 2.0
            cv2.ellipse(
                mask,
                (int(center[0]), int(center[1])),
                (int(round(axis_major)), int(round(axis_minor))),
                int(round(angle_deg)),
                0,
                360,
                255,
                -1,
            )
            # Add small perturbation bump
            bump_rad = int(round(axis_minor * 0.3))
            cv2.circle(
                mask,
                (int(center[0] + axis_major * 0.4), int(center[1] + axis_minor * 0.4)),
                bump_rad,
                255,
                -1,
            )

        # Retrieve exact minimum area bounding box of generated ground truth mask
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            rect = cv2.minAreaRect(cnts[0])
            gt_max_px = float(max(rect[1]))
            gt_orth_px = float(min(rect[1]))
            gt_max_mm = gt_max_px * spacing
            gt_orth_mm = gt_orth_px * spacing
        else:
            gt_max_mm = d_max_mm
            gt_orth_mm = d_orth_mm

        phantoms.append({
            "id": f"PHANTOM-{i+1:03d}",
            "shape_type": shape_type,
            "pixel_spacing_mm": spacing,
            "gt_max_mm": gt_max_mm,
            "gt_orth_mm": gt_orth_mm,
            "mask": mask,
        })

    return phantoms


def perturb_mask(mask: np.ndarray, iteration: int, rng: np.random.RandomState) -> np.ndarray:
    """Apply realistic measurement perturbations (shift, rotation, boundary noise, scale)."""
    if iteration == 0:
        return mask.copy()

    h, w = mask.shape
    if iteration == 1:
        # Subtle translation jitter: +/- 1-2 pixels
        dx = int(rng.choice([-2, -1, 1, 2]))
        dy = int(rng.choice([-2, -1, 1, 2]))
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(mask, m, (w, h), flags=cv2.INTER_NEAREST)

    if iteration == 2:
        # Subtle rotation: +/- 1-3 degrees
        angle = float(rng.uniform(-3.0, 3.0))
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(mask, m, (w, h), flags=cv2.INTER_NEAREST)

    if iteration == 3:
        # Ultrasound boundary speckle simulation (morphological edge ripple)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        op = rng.choice(["dilate", "erode"])
        if op == "dilate":
            return cv2.dilate(mask, kernel, iterations=1)
        return cv2.erode(mask, kernel, iterations=1)

    # Iteration 4: Small scale variation (0.99 - 1.01) + translation
    scale = float(rng.uniform(0.99, 1.01))
    dx = float(rng.uniform(-1.0, 1.0))
    dy = float(rng.uniform(-1.0, 1.0))
    m = cv2.getRotationMatrix2D((w / 2 + dx, h / 2 + dy), 0.0, scale)
    return cv2.warpAffine(mask, m, (w, h), flags=cv2.INTER_NEAREST)


def run_phantom_validation(n_phantoms: int = 50, n_iterations: int = 5) -> Dict[str, Any]:
    """Execute complete validation across all phantoms and repetitions."""
    engine = InferenceEngine(device="cpu")
    phantoms = generate_synthetic_phantoms(n=n_phantoms)
    rng = np.random.RandomState(42)

    dmax_gt_list = []
    dorth_gt_list = []
    dmax_meas_matrix = np.zeros((n_phantoms, n_iterations), dtype=np.float64)
    dorth_meas_matrix = np.zeros((n_phantoms, n_iterations), dtype=np.float64)

    phantom_records = []

    for i, p in enumerate(phantoms):
        gt_max = p["gt_max_mm"]
        gt_orth = p["gt_orth_mm"]
        spacing = p["pixel_spacing_mm"]
        base_mask = p["mask"]

        dmax_gt_list.append(gt_max)
        dorth_gt_list.append(gt_orth)

        iter_dmax = []
        iter_dorth = []

        for rep in range(n_iterations):
            pert_mask = perturb_mask(base_mask, rep, rng)
            res = engine.extract_calipers_and_measurements(pert_mask, pixel_spacing_mm=spacing)

            if res.get("lesions"):
                m_max = res["lesions"][0]["max_diameter_mm"] or 0.0
                m_orth = res["lesions"][0]["ortho_diameter_mm"] or 0.0
            else:
                m_max = 0.0
                m_orth = 0.0

            dmax_meas_matrix[i, rep] = m_max
            dorth_meas_matrix[i, rep] = m_orth
            iter_dmax.append(m_max)
            iter_dorth.append(m_orth)

        phantom_records.append({
            "id": p["id"],
            "shape_type": p["shape_type"],
            "gt_max_mm": round(gt_max, 2),
            "gt_orth_mm": round(gt_orth, 2),
            "measured_max_mean_mm": round(float(np.mean(iter_dmax)), 2),
            "measured_orth_mean_mm": round(float(np.mean(iter_dorth)), 2),
            "max_error_mm": round(float(abs(np.mean(iter_dmax) - gt_max)), 3),
            "orth_error_mm": round(float(abs(np.mean(iter_dorth) - gt_orth)), 3),
        })

    gt_max_arr = np.array(dmax_gt_list)
    gt_orth_arr = np.array(dorth_gt_list)

    # Use repetition 0 (nominal) for primary accuracy metrics
    meas_max_nom = dmax_meas_matrix[:, 0]
    meas_orth_nom = dorth_meas_matrix[:, 0]

    # Bias and MAE
    mae_dmax = float(np.mean(np.abs(meas_max_nom - gt_max_arr)))
    mae_dorth = float(np.mean(np.abs(meas_orth_nom - gt_orth_arr)))
    mean_mae = (mae_dmax + mae_dorth) / 2.0

    pct_mae_dmax = float(np.mean(np.abs(meas_max_nom - gt_max_arr) / gt_max_arr) * 100)
    pct_mae_dorth = float(np.mean(np.abs(meas_orth_nom - gt_orth_arr) / gt_orth_arr) * 100)
    mean_pct_mae = (pct_mae_dmax + pct_mae_dorth) / 2.0

    # ICC across 5 repetitions
    icc_dmax = calculate_icc_2_1(dmax_meas_matrix)
    icc_dorth = calculate_icc_2_1(dorth_meas_matrix)

    # Bland-Altman
    ba_dmax = calculate_bland_altman(meas_max_nom, gt_max_arr)
    ba_dorth = calculate_bland_altman(meas_orth_nom, gt_orth_arr)

    # Threshold checks
    passes_mae = mean_mae <= 1.0 or mean_pct_mae <= 2.0
    passes_icc = icc_dmax >= 0.90 and icc_dorth >= 0.90

    results = {
        "status": "PASS" if (passes_mae and passes_icc) else "FAIL",
        "assumption": "A2",
        "n_phantoms": n_phantoms,
        "n_iterations": n_iterations,
        "metrics": {
            "dmax_mae_mm": round(mae_dmax, 3),
            "dmax_mae_pct": round(pct_mae_dmax, 2),
            "dorth_mae_mm": round(mae_dorth, 3),
            "dorth_mae_pct": round(pct_mae_dorth, 2),
            "mean_mae_mm": round(mean_mae, 3),
            "mean_mae_pct": round(mean_pct_mae, 2),
            "icc_dmax": round(icc_dmax, 4),
            "icc_dorth": round(icc_dorth, 4),
        },
        "bland_altman": {
            "dmax": ba_dmax,
            "dorth": ba_dorth,
        },
        "thresholds": {
            "target_mae_mm": 1.0,
            "target_mae_pct": 2.0,
            "target_icc": 0.90,
            "passes_mae": passes_mae,
            "passes_icc": passes_icc,
        },
        "phantoms_sample": phantom_records[:10],
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic Caliper Phantom Validation")
    parser.add_argument("--phantoms", type=int, default=50, help="Number of synthetic phantoms")
    parser.add_argument("--iterations", type=int, default=5, help="Number of measurement iterations")
    parser.add_argument("--output", type=str, default="docs/evaluation/caliper_validation_results.json")
    args = parser.parse_args()

    print(f"[*] Running Caliper Phantom Validation ({args.phantoms} phantoms, {args.iterations} iterations)...")
    res = run_phantom_validation(args.phantoms, args.iterations)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"[+] Saved results to {out_path}")
    print(f"[*] Status: {res['status']}")
    print(f"[*] Mean MAE: {res['metrics']['mean_mae_mm']} mm ({res['metrics']['mean_mae_pct']}%)")
    print(f"[*] ICC(2,1): Dmax = {res['metrics']['icc_dmax']}, Dorth = {res['metrics']['icc_dorth']}")
    print(f"[*] Bland-Altman Dmax: Bias = {res['bland_altman']['dmax']['mean_bias_mm']} mm, LoA = [{res['bland_altman']['dmax']['loa_lower_mm']}, {res['bland_altman']['dmax']['loa_upper_mm']}] mm")


if __name__ == "__main__":
    main()
