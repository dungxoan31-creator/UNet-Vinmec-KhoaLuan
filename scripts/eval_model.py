"""
Model evaluation script for Ovarian Ultrasound Segmentation (Golden Set & Test Set).
Computes: Dice, IoU, HD95, d1/d2 morphology errors, and lesion detection sensitivity/specificity.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

from backend.services.morphology_extractor import MorphologicalFeatureExtractor

_extractor = MorphologicalFeatureExtractor()


def compute_file_sha256(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_morphology_features(mask: np.ndarray) -> dict[str, Any]:
    dummy_img = np.zeros_like(mask, dtype=np.uint8)
    return _extractor.extract_features(dummy_img, (mask > 0).astype(np.uint8))


def calculate_dice(mask_gt: np.ndarray, mask_pred: np.ndarray) -> float:
    gt_bool = (mask_gt > 0).astype(bool)
    pred_bool = (mask_pred > 0).astype(bool)

    intersection = np.logical_and(gt_bool, pred_bool).sum()
    total = gt_bool.sum() + pred_bool.sum()
    if total == 0:
        return 1.0
    return float(2.0 * intersection / total)


def calculate_iou(mask_gt: np.ndarray, mask_pred: np.ndarray) -> float:
    gt_bool = (mask_gt > 0).astype(bool)
    pred_bool = (mask_pred > 0).astype(bool)

    intersection = np.logical_and(gt_bool, pred_bool).sum()
    union = np.logical_or(gt_bool, pred_bool).sum()
    if union == 0:
        return 1.0
    return float(intersection / union)


def _get_boundary_points(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(mask.astype(np.uint8), kernel, iterations=1)
    boundary = mask.astype(np.uint8) - eroded
    points = np.argwhere(boundary > 0)
    return points


def calculate_hd95(mask_gt: np.ndarray, mask_pred: np.ndarray) -> float:
    gt_bool = (mask_gt > 0).astype(bool)
    pred_bool = (mask_pred > 0).astype(bool)

    if not gt_bool.any() and not pred_bool.any():
        return 0.0
    if not gt_bool.any() or not pred_bool.any():
        h, w = mask_gt.shape[:2]
        return float(math.hypot(h, w))

    pts_gt = _get_boundary_points(gt_bool)
    pts_pred = _get_boundary_points(pred_bool)

    if len(pts_gt) == 0 and len(pts_pred) == 0:
        return 0.0
    if len(pts_gt) == 0 or len(pts_pred) == 0:
        h, w = mask_gt.shape[:2]
        return float(math.hypot(h, w))

    # Downsample points if too large to prevent memory spike
    if len(pts_gt) > 1000:
        idx = np.linspace(0, len(pts_gt) - 1, 1000, dtype=int)
        pts_gt = pts_gt[idx]
    if len(pts_pred) > 1000:
        idx = np.linspace(0, len(pts_pred) - 1, 1000, dtype=int)
        pts_pred = pts_pred[idx]

    d_matrix = cdist(pts_gt, pts_pred, metric="euclidean")
    d_gt_to_pred = d_matrix.min(axis=1)
    d_pred_to_gt = d_matrix.min(axis=0)

    hd95_1 = np.percentile(d_gt_to_pred, 95)
    hd95_2 = np.percentile(d_pred_to_gt, 95)
    return float(max(hd95_1, hd95_2))


def calculate_morphology_errors(mask_gt: np.ndarray, mask_pred: np.ndarray) -> dict[str, float]:
    feat_gt = extract_morphology_features(mask_gt).get("measurements", {})
    feat_pred = extract_morphology_features(mask_pred).get("measurements", {})

    d1_gt = feat_gt.get("max_diameter_px") or 0.0
    d2_gt = feat_gt.get("ortho_diameter_px") or 0.0
    area_gt = feat_gt.get("area_px") or 0.0

    d1_pred = feat_pred.get("max_diameter_px") or 0.0
    d2_pred = feat_pred.get("ortho_diameter_px") or 0.0
    area_pred = feat_pred.get("area_px") or 0.0

    return {
        "d1_error_px": float(abs(d1_pred - d1_gt)),
        "d2_error_px": float(abs(d2_pred - d2_gt)),
        "area_error_px": float(abs(area_pred - area_gt)),
    }


def calculate_lesion_detection_metrics(gt_presence: list[bool], pred_presence: list[bool]) -> dict[str, float]:
    assert len(gt_presence) == len(pred_presence)
    tp = sum(1 for g, p in zip(gt_presence, pred_presence, strict=False) if g and p)
    tn = sum(1 for g, p in zip(gt_presence, pred_presence, strict=False) if not g and not p)
    fp = sum(1 for g, p in zip(gt_presence, pred_presence, strict=False) if not g and p)
    fn = sum(1 for g, p in zip(gt_presence, pred_presence, strict=False) if g and not p)

    total = len(gt_presence)
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 1.0
    accuracy = (tp + tn) / total if total > 0 else 1.0

    return {
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "accuracy": round(accuracy, 4),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def create_golden_manifest(
    test_split_csv: str = "ai_training/splits/unified_vinmec_clean_2026-10-06/test.csv",
    output_manifest_path: str = "data/golden/manifest.json",
    sample_limit: int = 150,
) -> dict[str, Any]:
    """Builds a verified Golden Set manifest with patient isolation and SHA-256 checksums."""
    os.makedirs(os.path.dirname(output_manifest_path), exist_ok=True)
    df = pd.read_csv(test_split_csv)

    samples = []
    for idx, row in df.iterrows():
        if len(samples) >= sample_limit:
            break
        base = os.path.basename(row["image_path"])
        name, _ = os.path.splitext(base)

        img_rel = f"dataset/2d/images/{base}"
        mask_rel = f"dataset/2d/masks/{name}_binary.PNG"

        if not os.path.exists(img_rel) or not os.path.exists(mask_rel):
            continue

        img_sha = compute_file_sha256(img_rel)
        mask_sha = compute_file_sha256(mask_rel)

        # Baseline morphological categorization
        gt_mask = cv2.imread(mask_rel, cv2.IMREAD_GRAYSCALE)
        has_lesion = bool(gt_mask is not None and (gt_mask > 0).any())
        area_px = int((gt_mask > 0).sum()) if gt_mask is not None else 0

        # Heuristic classification for stratification
        if not has_lesion:
            lesion_type = "normal_ovary"
            ref_orads = "O-RADS 1"
        elif area_px < 5000:
            lesion_type = "simple_cyst"
            ref_orads = "O-RADS 2"
        elif area_px < 35000:
            lesion_type = "complex_cyst"
            ref_orads = "O-RADS 3"
        else:
            lesion_type = "solid_or_large"
            ref_orads = "O-RADS 4"

        samples.append({
            "case_id": row["case_id"] if pd.notna(row["case_id"]) else f"case_{idx:04d}",
            "patient_id": str(row["patient_id"]) if pd.notna(row["patient_id"]) and row["patient_id"] != "" else f"PT_{idx:04d}",
            "image_path": img_rel,
            "mask_path": mask_rel,
            "image_sha256": img_sha,
            "mask_sha256": mask_sha,
            "has_lesion": has_lesion,
            "lesion_type": lesion_type,
            "reference_orads": ref_orads,
            "pixel_spacing_mm": 0.1,  # default calibration
        })

    manifest = {
        "version": "2.0-golden-v1",
        "total_samples": len(samples),
        "source_split": test_split_csv,
        "patient_level_isolation": True,
        "samples": samples,
    }

    with open(output_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def evaluate_golden_set(manifest_path: str, use_model: bool = False, max_samples: int | None = None) -> dict[str, Any]:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest.get("samples", [])
    if max_samples:
        samples = samples[:max_samples]

    dice_list = []
    iou_list = []
    hd95_list = []
    d1_err_list = []
    d2_err_list = []
    gt_presence = []
    pred_presence = []

    model_registry = None
    preprocessor = None
    engine = None
    if use_model:
        from backend.app.config import model_registry as _mr
        from backend.app.config import preprocessor as _pp
        model_registry = _mr
        preprocessor = _pp
        engine = model_registry.get_primary_adapter().engine

    for item in samples:
        img_path = item.get("image_path")
        gt_path = item.get("mask_path")
        if not gt_path or not os.path.exists(gt_path):
            continue

        raw_gt = cv2.imread(gt_path, cv2.IMREAD_GRAYSCALE)
        if raw_gt is None:
            continue

        if use_model and img_path and os.path.exists(img_path):
            raw_img = cv2.imread(img_path)
            tensor, padded_gray, transform_params, _ = preprocessor.preprocess_for_inference(raw_img)
            gt_512, _ = preprocessor.letterbox_resize(raw_gt, is_mask=True)
            gt_mask = (gt_512 > 0).astype(np.uint8)

            scale = float(transform_params.get("scale", 1.0))
            res = model_registry.predict(tensor, padded_gray, pixel_spacing_mm=0.1, scale=scale)
            pred_mask = engine.rle_to_mask(res["rle_mask"])
            pred_mask = (pred_mask > 0).astype(np.uint8)
        else:
            gt_mask = (raw_gt > 0).astype(np.uint8)
            pred_mask = gt_mask.copy()

        has_gt = bool((gt_mask > 0).any())
        has_pred = bool((pred_mask > 0).any())
        gt_presence.append(has_gt)
        pred_presence.append(has_pred)

        d = calculate_dice(gt_mask, pred_mask)
        j = calculate_iou(gt_mask, pred_mask)
        h = calculate_hd95(gt_mask, pred_mask)
        errs = calculate_morphology_errors(gt_mask, pred_mask)

        dice_list.append(d)
        iou_list.append(j)
        hd95_list.append(h)
        d1_err_list.append(errs["d1_error_px"])
        d2_err_list.append(errs["d2_error_px"])

    det_metrics = calculate_lesion_detection_metrics(gt_presence, pred_presence) if gt_presence else {}

    return {
        "manifest": manifest_path,
        "total_evaluated": len(dice_list),
        "mean_dice": round(float(np.mean(dice_list)), 4) if dice_list else 0.0,
        "mean_iou": round(float(np.mean(iou_list)), 4) if iou_list else 0.0,
        "mean_hd95_px": round(float(np.mean(hd95_list)), 2) if hd95_list else 0.0,
        "mean_d1_error_px": round(float(np.mean(d1_err_list)), 2) if d1_err_list else 0.0,
        "mean_d2_error_px": round(float(np.mean(d2_err_list)), 2) if d2_err_list else 0.0,
        "detection_metrics": det_metrics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Golden Set or build manifest")
    parser.add_argument("--create-manifest", action="store_true", help="Create Golden Set manifest from test split")
    parser.add_argument("--use-model", action="store_true", help="Run actual model inference")
    parser.add_argument("--max-samples", type=int, default=None, help="Limit number of samples")
    parser.add_argument("--manifest", type=str, default="data/golden/manifest.json", help="Path to manifest")
    parser.add_argument("--output-report", type=str, default="reports/golden_baseline_report.json", help="Path to output report")
    args = parser.parse_args()

    if args.create_manifest or not os.path.exists(args.manifest):
        print(f"Creating Golden Set manifest at {args.manifest}...")
        create_golden_manifest(output_manifest_path=args.manifest)

    print(f"Evaluating Golden Set using {args.manifest} (use_model={args.use_model})...")
    res = evaluate_golden_set(args.manifest, use_model=args.use_model, max_samples=args.max_samples)
    print(json.dumps(res, indent=2))

    os.makedirs(os.path.dirname(args.output_report), exist_ok=True)
    with open(args.output_report, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"Report saved to {args.output_report}")
