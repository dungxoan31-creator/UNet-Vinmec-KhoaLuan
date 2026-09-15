"""
Unit tests for Clinical & MICCAI Metrics Module.
Verifies proper handling of positive lesion cases and elimination of false Dice=1.0000 on empty masks.
"""

import numpy as np
import pytest
from ai_training.metrics_clinical import compute_sample_clinical_metrics, compute_dataset_clinical_summary

def test_perfect_match_lesion():
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[30:70, 30:70] = 1
    pred = gt.copy()

    m = compute_sample_clinical_metrics(pred, gt)
    assert m["dice"] == pytest.approx(1.0, 1e-4)
    assert m["iou"] == pytest.approx(1.0, 1e-4)
    assert m["recall"] == pytest.approx(1.0, 1e-4)

def test_missed_lesion_returns_zero_not_one():
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[30:70, 30:70] = 1
    pred = np.zeros((100, 100), dtype=np.uint8) # Missed lesion completely

    m = compute_sample_clinical_metrics(pred, gt)
    assert m["dice"] == pytest.approx(0.0, 1e-4), "Missed lesion MUST yield Dice=0.0, never 1.0"
    assert m["recall"] == pytest.approx(0.0, 1e-4)

def test_normal_case_isolated_from_foreground_dice():
    gt = np.zeros((100, 100), dtype=np.uint8) # No lesion
    pred = np.zeros((100, 100), dtype=np.uint8) # Predicted no lesion

    m = compute_sample_clinical_metrics(pred, gt)
    assert m["is_normal_case"] is True
    assert np.isnan(m["dice"]), "Normal case should return NaN for foreground dice, not 1.0"
    assert m["specificity"] == 1.0, "Normal case with empty prediction has 100% Specificity"

def test_dataset_aggregation_robustness():
    # 2 positive cases (1 perfect, 1 50% overlap) and 1 normal case
    results = [
        {"dice": 1.0, "iou": 1.0, "recall": 1.0, "precision": 1.0, "specificity": 0.99, "is_normal_case": False},
        {"dice": 0.6, "iou": 0.43, "recall": 0.7, "precision": 0.55, "specificity": 0.95, "is_normal_case": False},
        {"dice": np.nan, "iou": np.nan, "recall": np.nan, "precision": np.nan, "specificity": 1.0, "is_normal_case": True}
    ]
    summary = compute_dataset_clinical_summary(results)
    assert summary["lesion_cases_count"] == 2
    assert summary["normal_cases_count"] == 1
    assert summary["foreground_dice_mean"] == pytest.approx(0.8, 1e-3)
    assert summary["specificity_normal_cases"] == pytest.approx(1.0, 1e-3)
