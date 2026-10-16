"""Standardized Segmentation Metrics v1 and Statistical Aggregation."""

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy import ndimage


def score_masks(pred: np.ndarray, gt: np.ndarray) -> Dict[str, Any]:
    """Score a pair of predicted and ground truth 2D binary masks."""
    if pred.ndim != 2 or gt.ndim != 2:
        raise ValueError(f"Both masks must be 2D, got pred {pred.shape} and gt {gt.shape}")
    if pred.size == 0 or gt.size == 0:
        raise ValueError("Masks cannot have size 0")
    if pred.shape != gt.shape:
        raise ValueError(f"Mask shape mismatch: pred {pred.shape} vs gt {gt.shape}")
    if not np.all(np.isfinite(pred)) or not np.all(np.isfinite(gt)):
        raise ValueError("Mask values must be finite")

    unique_p = set(np.unique(pred).tolist())
    unique_g = set(np.unique(gt).tolist())
    allowed = {0, 1, 0.0, 1.0, False, True}
    if not unique_p.issubset(allowed):
        raise ValueError(f"Predicted mask must be binary {0, 1}, got {unique_p}")
    if not unique_g.issubset(allowed):
        raise ValueError(f"Ground truth mask must be binary {0, 1}, got {unique_g}")

    p = (pred > 0).astype(bool)
    g = (gt > 0).astype(bool)

    tp = int(np.count_nonzero(p & g))
    fp = int(np.count_nonzero(p & ~g))
    fn = int(np.count_nonzero(~p & g))
    tn = int(np.count_nonzero(~p & ~g))

    gt_empty = bool(tp + fn == 0)
    pred_empty = bool(tp + fp == 0)

    # Dice & IoU
    if gt_empty and pred_empty:
        dice = 1.0
        iou = 1.0
    elif gt_empty or pred_empty:
        dice = 0.0
        iou = 0.0
    else:
        dice = float(2.0 * tp / (2.0 * tp + fp + fn))
        iou = float(tp / (tp + fp + fn))

    # Recall
    recall_null_reason = None
    if gt_empty:
        recall = None
        recall_null_reason = "no_gt_foreground"
    else:
        recall = float(tp / (tp + fn))

    # Precision
    precision_null_reason = None
    if pred_empty:
        precision = None
        precision_null_reason = "no_pred_foreground"
    else:
        precision = float(tp / (tp + fp))

    # Specificity
    specificity_null_reason = None
    bg_denom = tn + fp
    if bg_denom == 0:
        specificity = None
        specificity_null_reason = "no_background"
    else:
        specificity = float(tn / bg_denom)

    # Fractions & Areas
    fp_area_px = int(fp)
    fn_area_px = int(fn)
    gt_area = tp + fn
    under_fraction = float(fn / gt_area) if gt_area > 0 else None
    over_fraction = float(fp / gt_area) if gt_area > 0 else None

    # HD95
    hd95_px = None
    hd95_null_reason = None
    if gt_empty or pred_empty:
        hd95_null_reason = "empty_surface"
    elif np.array_equal(p, g):
        hd95_px = 0.0
    else:
        surface_g = g ^ ndimage.binary_erosion(g)
        if not np.any(surface_g):
            surface_g = g
        surface_p = p ^ ndimage.binary_erosion(p)
        if not np.any(surface_p):
            surface_p = p

        dt_g = ndimage.distance_transform_edt(~surface_g)
        dt_p = ndimage.distance_transform_edt(~surface_p)

        d_p_to_g = dt_g[surface_p]
        d_g_to_p = dt_p[surface_g]

        all_dists = np.concatenate([d_p_to_g, d_g_to_p])
        hd95_px = float(np.percentile(all_dists, 95))

    return {
        "dice": dice,
        "iou": iou,
        "recall": recall,
        "recall_null_reason": recall_null_reason,
        "precision": precision,
        "precision_null_reason": precision_null_reason,
        "specificity": specificity,
        "specificity_null_reason": specificity_null_reason,
        "hd95_px": hd95_px,
        "hd95_null_reason": hd95_null_reason,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "fp_area_px": fp_area_px,
        "fn_area_px": fn_area_px,
        "under_fraction": under_fraction,
        "over_fraction": over_fraction,
        "gt_empty": gt_empty,
        "pred_empty": pred_empty
    }


def _calc_stats(values: List[Optional[float]]) -> Dict[str, Any]:
    valid = [v for v in values if v is not None]
    n_valid = len(valid)
    n_null = len(values) - n_valid

    if n_valid == 0:
        return {
            "n_valid": 0,
            "n_null": n_null,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "p25": None,
            "p75": None,
            "p95": None
        }

    arr = np.array(valid, dtype=np.float64)
    return {
        "n_valid": n_valid,
        "n_null": n_null,
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=0)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95))
    }


def aggregate_metrics(rows: List[Dict[str, Any]], bootstrap_seed: int = 42) -> Dict[str, Any]:
    """Aggregate per-image metric rows into primary, secondary and patient-level statistics."""
    # 1. Primary: macro on non-empty GT
    nonempty_rows = [r for r in rows if not r.get("gt_empty", False)]
    primary_dice = _calc_stats([r.get("dice") for r in nonempty_rows])
    primary_iou = _calc_stats([r.get("iou") for r in nonempty_rows])
    primary_recall = _calc_stats([r.get("recall") for r in nonempty_rows])
    primary_precision = _calc_stats([r.get("precision") for r in nonempty_rows])
    primary_specificity = _calc_stats([r.get("specificity") for r in nonempty_rows])
    primary_hd95 = _calc_stats([r.get("hd95_px") for r in nonempty_rows])

    # 2. Secondary: Micro sums across all rows
    sum_tp = sum(int(r.get("tp", 0)) for r in rows)
    sum_fp = sum(int(r.get("fp", 0)) for r in rows)
    sum_fn = sum(int(r.get("fn", 0)) for r in rows)
    sum_tn = sum(int(r.get("tn", 0)) for r in rows)

    dice_denom = 2 * sum_tp + sum_fp + sum_fn
    micro_dice = float(2.0 * sum_tp / dice_denom) if dice_denom > 0 else 1.0

    iou_denom = sum_tp + sum_fp + sum_fn
    micro_iou = float(sum_tp / iou_denom) if iou_denom > 0 else 1.0

    # 3. Patient-level macro and bootstrap CI
    patient_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in nonempty_rows:
        pid = (r.get("patient_id") or "").strip()
        if pid:
            patient_groups.setdefault(pid, []).append(r)

    patient_macro_dice: Dict[str, Any] = {}
    if patient_groups:
        patient_dice_means = [
            float(np.mean([item["dice"] for item in items if item.get("dice") is not None]))
            for items in patient_groups.values()
        ]
        patient_macro_dice = _calc_stats(patient_dice_means)

        # Bootstrap CI
        unique_patients = list(patient_groups.keys())
        if len(unique_patients) >= 2:
            rng = np.random.RandomState(bootstrap_seed)
            boot_means = []
            for _ in range(2000):
                boot_pids = rng.choice(unique_patients, size=len(unique_patients), replace=True)
                sample_means = [
                    float(np.mean([item["dice"] for item in patient_groups[pid] if item.get("dice") is not None]))
                    for pid in boot_pids
                ]
                boot_means.append(float(np.mean(sample_means)))
            patient_macro_dice["ci_95"] = [
                float(np.percentile(boot_means, 2.5)),
                float(np.percentile(boot_means, 97.5))
            ]
            patient_macro_dice["ci_reason"] = None
        else:
            patient_macro_dice["ci_95"] = None
            patient_macro_dice["ci_reason"] = "insufficient_clusters"
    else:
        patient_macro_dice = _calc_stats([])
        patient_macro_dice["ci_95"] = None
        patient_macro_dice["ci_reason"] = "no_patient_mapping"

    return {
        "primary": {
            "dice": primary_dice,
            "iou": primary_iou,
            "recall": primary_recall,
            "precision": primary_precision,
            "specificity": primary_specificity,
            "hd95_px": primary_hd95
        },
        "secondary": {
            "all_images_agreement_dice": _calc_stats([r.get("dice") for r in rows]),
            "micro_dice": micro_dice,
            "micro_iou": micro_iou,
            "total_tp": sum_tp,
            "total_fp": sum_fp,
            "total_fn": sum_fn,
            "total_tn": sum_tn
        },
        "patient_macro": {
            "dice": patient_macro_dice
        }
    }
