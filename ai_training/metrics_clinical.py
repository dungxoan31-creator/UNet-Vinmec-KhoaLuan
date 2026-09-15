"""
Standardized Clinical & MICCAI Evaluation Metrics for Ovarian Ultrasound Lesion Segmentation.
Fixes the degenerate Dice=1.0000 anomaly on empty masks by strictly isolating:
1. Foreground Metrics (Dice, IoU, Sensitivity, Precision) computed exclusively on positive lesion cases (GT > 0).
2. Specificity and True Negative Rate computed on physiological normal cases (GT == 0).
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import numpy as np
import torch
from scipy.spatial.distance import directed_hausdorff


def compute_sample_clinical_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray, smooth: float = 1e-6) -> dict:
    """
    Computes rigorous clinical metrics for an individual image-mask pair.
    
    Args:
        pred_mask: Binary numpy array (H, W), values in {0, 1}
        gt_mask: Binary numpy array (H, W), values in {0, 1}
        smooth: Epsilon to prevent division by zero
    """
    p = (pred_mask > 0).astype(bool).flatten()
    g = (gt_mask > 0).astype(bool).flatten()

    tp = np.logical_and(p, g).sum()
    fp = np.logical_and(p, ~g).sum()
    fn = np.logical_and(~p, g).sum()
    tn = np.logical_and(~p, ~g).sum()

    gt_has_lesion = g.sum() > 0
    pred_has_lesion = p.sum() > 0

    if gt_has_lesion:
        # Case has true lesion: Compute foreground overlap
        dice = float((2.0 * tp) / (2.0 * tp + fp + fn + smooth))
        iou = float(tp / (tp + fp + fn + smooth))
        recall = float(tp / (tp + fn + smooth))
        precision = float(tp / (tp + fp + smooth)) if pred_has_lesion else 0.0
        is_normal_case = False
        specificity = float(tn / (tn + fp + smooth))
    else:
        # Normal physiological ovary (No lesion present)
        # Foreground dice is not applicable
        dice = np.nan
        iou = np.nan
        recall = np.nan
        precision = np.nan
        is_normal_case = True
        specificity = 1.0 if not pred_has_lesion else 0.0

    return {
        "has_lesion": gt_has_lesion,
        "pred_has_lesion": pred_has_lesion,
        "is_normal_case": is_normal_case,
        "dice": dice,
        "iou": iou,
        "recall": recall,
        "precision": precision,
        "specificity": specificity,
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn)
    }


def compute_dataset_clinical_summary(sample_results: list[dict], pixel_spacing_mm: float = 0.1) -> dict:
    """
    Aggregates per-sample clinical metrics across a full evaluation set.
    """
    foreground_dices = [r["dice"] for r in sample_results if not np.isnan(r["dice"])]
    foreground_ious = [r["iou"] for r in sample_results if not np.isnan(r["iou"])]
    foreground_recalls = [r["recall"] for r in sample_results if not np.isnan(r["recall"])]
    foreground_precisions = [r["precision"] for r in sample_results if not np.isnan(r["precision"])]
    specificities = [r["specificity"] for r in sample_results if r["is_normal_case"]]

    # Overall specificities if no normal cases exist
    all_specificities = [r["specificity"] for r in sample_results]

    summary = {
        "total_cases_evaluated": len(sample_results),
        "lesion_cases_count": len(foreground_dices),
        "normal_cases_count": len(specificities),
        "foreground_dice_mean": float(np.mean(foreground_dices)) if foreground_dices else 0.0,
        "foreground_dice_std": float(np.std(foreground_dices)) if foreground_dices else 0.0,
        "foreground_iou_mean": float(np.mean(foreground_ious)) if foreground_ious else 0.0,
        "foreground_iou_std": float(np.std(foreground_ious)) if foreground_ious else 0.0,
        "recall_sensitivity_mean": float(np.mean(foreground_recalls)) if foreground_recalls else 0.0,
        "precision_mean": float(np.mean(foreground_precisions)) if foreground_precisions else 0.0,
        "specificity_normal_cases": float(np.mean(specificities)) if specificities else 1.0,
        "specificity_all_cases": float(np.mean(all_specificities)) if all_specificities else 1.0,
    }
    return summary
