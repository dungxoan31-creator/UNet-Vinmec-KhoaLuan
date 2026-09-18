"""
Clinical Metrics Engine for Ovarian Lesion Segmentation.
Standard medical metrics: Dice (DSC), IoU, Recall (Sensitivity), Precision, Specificity.
Properly handles empty masks (normal/control ovaries) without division by zero.
"""

import numpy as np


def compute_sample_clinical_metrics(pred_binary: np.ndarray, gt_binary: np.ndarray, smooth: float = 1e-6) -> dict:
    """
    Computes clinical segmentation metrics for a single sample.
    Both inputs must be binary numpy arrays with values in {0, 1}.
    """
    p = (pred_binary > 0).astype(np.uint8)
    g = (gt_binary > 0).astype(np.uint8)

    tp = np.logical_and(p == 1, g == 1).sum()
    fp = np.logical_and(p == 1, g == 0).sum()
    fn = np.logical_and(p == 0, g == 1).sum()
    tn = np.logical_and(p == 0, g == 0).sum()

    gt_area = g.sum()
    pred_area = p.sum()

    is_empty_case = (gt_area == 0)

    if is_empty_case:
        # True negative evaluation (normal ovary without lesion)
        if pred_area == 0:
            dice = 1.0
            iou = 1.0
            recall = 1.0
            precision = 1.0
            specificity = 1.0
        else:
            dice = 0.0
            iou = 0.0
            recall = 1.0  # No actual lesion was missed
            precision = 0.0
            specificity = float(tn / (tn + fp + smooth))
    else:
        # Lesion case
        intersection = tp
        union = tp + fp + fn
        dice = float((2.0 * intersection) / (pred_area + gt_area + smooth))
        iou = float(intersection / (union + smooth))
        recall = float(tp / (tp + fn + smooth))
        precision = float(tp / (tp + fp + smooth))
        specificity = float(tn / (tn + fp + smooth))

    return {
        "dice": float(np.clip(dice, 0.0, 1.0)),
        "iou": float(np.clip(iou, 0.0, 1.0)),
        "recall": float(np.clip(recall, 0.0, 1.0)),
        "precision": float(np.clip(precision, 0.0, 1.0)),
        "specificity": float(np.clip(specificity, 0.0, 1.0)),
        "is_empty": bool(is_empty_case),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn)
    }


def compute_dataset_clinical_summary(sample_results: list) -> dict:
    """
    Computes dataset-level summary statistics across all samples.
    Differentiates foreground metrics on lesion cases and specificity on all cases.
    """
    if not sample_results:
        return {}

    total_cases = len(sample_results)
    lesion_cases = [r for r in sample_results if not r.get("is_empty", False)]
    empty_cases = [r for r in sample_results if r.get("is_empty", False)]

    # Lesion cases foreground metrics
    if lesion_cases:
        fg_dice = [r["dice"] for r in lesion_cases]
        fg_iou = [r["iou"] for r in lesion_cases]
        fg_recall = [r["recall"] for r in lesion_cases]
        fg_precision = [r["precision"] for r in lesion_cases]

        dice_mean = float(np.mean(fg_dice))
        dice_std = float(np.std(fg_dice))
        iou_mean = float(np.mean(fg_iou))
        iou_std = float(np.std(fg_iou))
        recall_mean = float(np.mean(fg_recall))
        precision_mean = float(np.mean(fg_precision))
    else:
        dice_mean = dice_std = iou_mean = iou_std = recall_mean = precision_mean = 0.0

    # Specificity across all cases
    all_spec = [r["specificity"] for r in sample_results]
    spec_mean = float(np.mean(all_spec))

    # Specificity on empty cases (true control rate)
    if empty_cases:
        empty_spec = [r["specificity"] for r in empty_cases]
        empty_spec_mean = float(np.mean(empty_spec))
    else:
        empty_spec_mean = 1.0

    return {
        "total_cases_evaluated": total_cases,
        "lesion_cases_count": len(lesion_cases),
        "normal_cases_count": len(empty_cases),
        "foreground_dice_mean": dice_mean,
        "foreground_dice_std": dice_std,
        "foreground_iou_mean": iou_mean,
        "foreground_iou_std": iou_std,
        "recall_sensitivity_mean": recall_mean,
        "precision_mean": precision_mean,
        "specificity_normal_cases": empty_spec_mean,
        "specificity_all_cases": spec_mean
    }
