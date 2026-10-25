"""
Unit tests for model evaluation metrics and script (scripts/eval_model.py).
"""

import numpy as np
import pytest

from scripts.eval_model import (
    calculate_dice,
    calculate_hd95,
    calculate_iou,
    calculate_lesion_detection_metrics,
    calculate_morphology_errors,
)


def test_calculate_dice_and_iou_perfect():
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask1[20:60, 20:60] = 1
    mask2 = mask1.copy()

    dice = calculate_dice(mask1, mask2)
    iou = calculate_iou(mask1, mask2)
    assert dice == pytest.approx(1.0)
    assert iou == pytest.approx(1.0)


def test_calculate_dice_and_iou_disjoint():
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask1[10:30, 10:30] = 1
    mask2 = np.zeros((100, 100), dtype=np.uint8)
    mask2[50:70, 50:70] = 1

    dice = calculate_dice(mask1, mask2)
    iou = calculate_iou(mask1, mask2)
    assert dice == pytest.approx(0.0)
    assert iou == pytest.approx(0.0)


def test_calculate_dice_both_empty():
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask2 = np.zeros((100, 100), dtype=np.uint8)

    dice = calculate_dice(mask1, mask2)
    iou = calculate_iou(mask1, mask2)
    assert dice == pytest.approx(1.0)
    assert iou == pytest.approx(1.0)


def test_calculate_hd95_identical_and_shifted():
    mask1 = np.zeros((100, 100), dtype=np.uint8)
    mask1[30:70, 30:70] = 1
    mask2 = mask1.copy()

    hd95 = calculate_hd95(mask1, mask2)
    assert hd95 == pytest.approx(0.0, abs=1e-2)

    # Shifted by 5 pixels
    mask3 = np.zeros((100, 100), dtype=np.uint8)
    mask3[35:75, 30:70] = 1
    hd95_shifted = calculate_hd95(mask1, mask3)
    assert hd95_shifted > 0.0


def test_calculate_morphology_errors():
    mask_gt = np.zeros((200, 200), dtype=np.uint8)
    mask_gt[50:150, 50:100] = 1  # 100 x 50
    mask_pred = np.zeros((200, 200), dtype=np.uint8)
    mask_pred[50:150, 50:104] = 1  # 100 x 54

    errors = calculate_morphology_errors(mask_gt, mask_pred)
    assert "d1_error_px" in errors
    assert "d2_error_px" in errors
    assert "area_error_px" in errors
    assert errors["d1_error_px"] == pytest.approx(0.0, abs=2.0)
    assert errors["d2_error_px"] == pytest.approx(4.0, abs=2.0)


def test_calculate_lesion_detection_metrics():
    # 4 cases: 2 TP, 1 FP, 1 TN
    gt_presence = [True, True, False, False]
    pred_presence = [True, True, True, False]

    metrics = calculate_lesion_detection_metrics(gt_presence, pred_presence)
    assert metrics["sensitivity"] == pytest.approx(1.0)
    assert metrics["specificity"] == pytest.approx(0.5)
    assert metrics["accuracy"] == pytest.approx(0.75)
