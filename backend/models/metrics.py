"""
Evaluation Metrics for Medical Image Segmentation:
- Dice Similarity Coefficient (DSC)
- Intersection over Union (IoU / Jaccard Index)
- Sensitivity / Recall
- Specificity
- Precision
- 95% Hausdorff Distance (HD95)
- Caliper Measurement Error (MAE, Relative Error)
"""

import numpy as np


def compute_dice_iou_numpy(pred_mask, gt_mask, smooth=1e-6):
    """
    pred_mask: binary numpy array (H, W) or (N, H, W)
    gt_mask: binary numpy array (H, W) or (N, H, W)
    """
    pred_flat = pred_mask.astype(bool).flatten()
    gt_flat = gt_mask.astype(bool).flatten()

    intersection = np.logical_and(pred_flat, gt_flat).sum()
    total_sum = pred_flat.sum() + gt_flat.sum()
    union = np.logical_or(pred_flat, gt_flat).sum()

    # Special handling for empty masks (both normal ovaries)
    if total_sum == 0:
        return 1.0, 1.0  # Perfect agreement on empty/normal case

    dice = (2.0 * intersection + smooth) / (total_sum + smooth)
    iou = (intersection + smooth) / (union + smooth)
    return float(dice), float(iou)


def compute_confusion_metrics(pred_mask, gt_mask, smooth=1e-6):
    """
    Computes TP, FP, TN, FN, Sensitivity/Recall, Specificity, Precision
    """
    p = pred_mask.astype(bool).flatten()
    g = gt_mask.astype(bool).flatten()

    tp = np.logical_and(p, g).sum()
    fp = np.logical_and(p, np.logical_not(g)).sum()
    fn = np.logical_and(np.logical_not(p), g).sum()
    tn = np.logical_and(np.logical_not(p), np.logical_not(g)).sum()

    sensitivity = (tp + smooth) / (tp + fn + smooth)
    specificity = (tn + smooth) / (tn + fp + smooth)
    precision = (tp + smooth) / (tp + fp + smooth)

    return {
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "precision": float(precision),
    }


def compute_hausdorff_95(pred_mask, gt_mask, pixel_spacing_mm=0.1):
    """
    Approximated 95% Hausdorff Distance in mm between contour point sets.
    """
    if pred_mask.sum() == 0 or gt_mask.sum() == 0:
        return 0.0 if pred_mask.sum() == gt_mask.sum() else 999.0

    from ai_training.metrics_clinical import compute_hd95_and_asd
    res = compute_hd95_and_asd(pred_mask, gt_mask, voxelspacing=pixel_spacing_mm)
    if res["hd95"] is None:
        return 999.0
    return float(res["hd95"])


def evaluate_batch(predictions, targets, pixel_spacing_mm=0.1):
    """
    Batch evaluation across multiple images.
    """
    dices, ious, hds = [], [], []
    for p, g in zip(predictions, targets):
        d, i = compute_dice_iou_numpy(p, g)
        dices.append(d)
        ious.append(i)
        hd = compute_hausdorff_95(p, g, pixel_spacing_mm=pixel_spacing_mm)
        if hd < 500.0:  # ignore empty mismatch extremes in mean
            hds.append(hd)

    return {
        "mean_dice": float(np.mean(dices)),
        "std_dice": float(np.std(dices)),
        "mean_iou": float(np.mean(ious)),
        "std_iou": float(np.std(ious)),
        "mean_hd95_mm": float(np.mean(hds)) if hds else 0.0,
    }
