"""Tests for Versioned Segmentation Metrics v1 and Statistical Aggregation."""

import math
import numpy as np
import pytest

from evaluation.segmentation_metrics import score_masks, aggregate_metrics


def test_hand_computed_overlap():
    g = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    p = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    r = score_masks(p, g)

    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (1, 1, 1, 1)
    assert r["dice"] == 0.5
    assert r["iou"] == pytest.approx(1 / 3, abs=1e-12)
    assert r["recall"] == 0.5
    assert r["precision"] == 0.5
    assert r["specificity"] == 0.5
    assert r["under_fraction"] == 0.5
    assert r["over_fraction"] == 0.5
    assert r["fp_area_px"] == 1
    assert r["fn_area_px"] == 1


def test_perfect_and_disjoint():
    g = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    p = np.array([[1, 1], [1, 1]], dtype=np.uint8)
    r_perf = score_masks(p, g)
    assert (r_perf["dice"], r_perf["iou"], r_perf["recall"], r_perf["precision"]) == (1.0, 1.0, 1.0, 1.0)
    assert r_perf["under_fraction"] == 0.0
    assert r_perf["over_fraction"] == 0.0

    p_disjoint = np.zeros_like(g)
    r_disj = score_masks(p_disjoint, g)
    assert (r_disj["dice"], r_disj["iou"], r_disj["recall"]) == (0.0, 0.0, 0.0)
    assert r_disj["precision"] is None
    assert r_disj["precision_null_reason"] == "no_pred_foreground"


@pytest.mark.parametrize("g_empty,p_empty,exp_dice,exp_recall,exp_prec,exp_hd95_reason", [
    (True, True, 1.0, None, None, "empty_surface"),
    (False, True, 0.0, 0.0, None, "empty_surface"),
    (True, False, 0.0, None, 0.0, "empty_surface")
])
def test_empty_contract(g_empty, p_empty, exp_dice, exp_recall, exp_prec, exp_hd95_reason):
    g = np.zeros((4, 4), dtype=np.uint8) if g_empty else np.eye(4, dtype=np.uint8)
    p = np.zeros((4, 4), dtype=np.uint8) if p_empty else np.eye(4, dtype=np.uint8)

    r = score_masks(p, g)
    assert r["dice"] == exp_dice
    assert r["recall"] == exp_recall
    assert r["precision"] == exp_prec
    assert r["hd95_px"] is None
    assert r["hd95_null_reason"] == exp_hd95_reason


def test_rejects_broadcast_nan_multiclass():
    # Shape mismatch (2, 1) vs (2, 2)
    with pytest.raises(ValueError, match="shape.*mismatch"):
        score_masks(np.ones((2, 1)), np.ones((2, 2)))

    # NaN input
    nan_arr = np.array([[np.nan, 0], [0, 1]])
    with pytest.raises(ValueError, match="finite"):
        score_masks(nan_arr, np.zeros((2, 2)))

    # Multiclass label 2
    with pytest.raises(ValueError, match="binary"):
        score_masks(np.array([[2, 0], [0, 1]]), np.zeros((2, 2)))

    # 3D array
    with pytest.raises(ValueError, match="2D"):
        score_masks(np.zeros((2, 2, 2)), np.zeros((2, 2, 2)))

    # Zero size
    with pytest.raises(ValueError, match="size 0"):
        score_masks(np.zeros((0, 0)), np.zeros((0, 0)))


def test_surface_hd95_one_pixel_shift():
    # Single pixel at (2, 2) vs (2, 3) -> distance is 1.0 pixel
    g = np.zeros((6, 6), dtype=np.uint8)
    p = np.zeros((6, 6), dtype=np.uint8)
    g[2, 2] = 1
    p[2, 3] = 1

    r = score_masks(p, g)
    assert r["hd95_px"] == pytest.approx(1.0, abs=1e-6)

    # Identical surface -> distance 0.0
    r_same = score_masks(g, g)
    assert r_same["hd95_px"] == pytest.approx(0.0, abs=1e-6)


def test_auxiliary_counts_and_fractions():
    g = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    p = np.array([[1, 0], [1, 0]], dtype=np.uint8)
    r = score_masks(p, g)
    assert r["fp_area_px"] == 1
    assert r["fn_area_px"] == 1
    assert r["under_fraction"] == 0.5
    assert r["over_fraction"] == 0.5


def test_aggregate_oracles_and_nulls():
    # scalar [0, 0.5, 1.0] and one row where dice is null
    rows = [
        {"dice": 0.0, "iou": 0.0, "gt_empty": False},
        {"dice": 0.5, "iou": 0.333333333333, "gt_empty": False},
        {"dice": 1.0, "iou": 1.0, "gt_empty": False},
        {"dice": None, "iou": None, "gt_empty": False}
    ]
    agg = aggregate_metrics(rows, bootstrap_seed=42)
    dice_stats = agg["primary"]["dice"]
    assert dice_stats["n_valid"] == 3
    assert dice_stats["n_null"] == 1
    assert dice_stats["mean"] == pytest.approx(0.5, abs=1e-12)
    assert dice_stats["median"] == pytest.approx(0.5, abs=1e-12)
    # std with ddof=0 on [0, 0.5, 1.0]: variance is ((0-0.5)^2 + 0^2 + (1-0.5)^2)/3 = 0.5/3 = 1/6
    assert dice_stats["std"] == pytest.approx(math.sqrt(1 / 6), abs=1e-12)
    assert dice_stats["min"] == 0.0
    assert dice_stats["max"] == 1.0
    assert dice_stats["p25"] == pytest.approx(0.25, abs=1e-12)
    assert dice_stats["p75"] == pytest.approx(0.75, abs=1e-12)
    assert dice_stats["p95"] == pytest.approx(0.95, abs=1e-12)


def test_macro_micro_and_patient_weighting():
    # Patient 1 has 1 image with dice 1.0
    # Patient 2 has 3 images with dice 0.0
    rows = [
        {"sample_id": "s1", "case_id": "c1", "patient_id": "p1", "dice": 1.0, "tp": 10, "fp": 0, "fn": 0, "tn": 10, "gt_empty": False},
        {"sample_id": "s2", "case_id": "c2", "patient_id": "p2", "dice": 0.0, "tp": 0, "fp": 5, "fn": 5, "tn": 10, "gt_empty": False},
        {"sample_id": "s3", "case_id": "c3", "patient_id": "p2", "dice": 0.0, "tp": 0, "fp": 5, "fn": 5, "tn": 10, "gt_empty": False},
        {"sample_id": "s4", "case_id": "c4", "patient_id": "p2", "dice": 0.0, "tp": 0, "fp": 5, "fn": 5, "tn": 10, "gt_empty": False},
    ]
    agg = aggregate_metrics(rows, bootstrap_seed=42)
    
    # Image macro mean: (1.0 + 0 + 0 + 0)/4 = 0.25
    assert agg["primary"]["dice"]["mean"] == pytest.approx(0.25, abs=1e-12)
    # Patient macro mean: (p1=1.0, p2=0.0) -> mean 0.5
    assert agg["patient_macro"]["dice"]["mean"] == pytest.approx(0.5, abs=1e-12)
    # Micro dice: total TP=10, FP=15, FN=15 -> 2*10 / (20 + 15 + 15) = 20/50 = 0.4
    assert agg["secondary"]["micro_dice"] == pytest.approx(0.4, abs=1e-12)


def test_bootstrap_seed_and_unit():
    rows = [
        {"sample_id": "s1", "case_id": "c1", "patient_id": "p1", "dice": 0.8, "gt_empty": False},
        {"sample_id": "s2", "case_id": "c2", "patient_id": "p2", "dice": 0.9, "gt_empty": False},
        {"sample_id": "s3", "case_id": "c3", "patient_id": "p3", "dice": 0.7, "gt_empty": False},
    ]
    agg1 = aggregate_metrics(rows, bootstrap_seed=42)
    agg2 = aggregate_metrics(rows, bootstrap_seed=42)
    assert agg1["patient_macro"]["dice"]["ci_95"] == agg2["patient_macro"]["dice"]["ci_95"]

    # Single patient -> CI unavailable
    single_p_rows = [
        {"sample_id": "s1", "case_id": "c1", "patient_id": "p1", "dice": 0.8, "gt_empty": False}
    ]
    agg_single = aggregate_metrics(single_p_rows, bootstrap_seed=42)
    assert agg_single["patient_macro"]["dice"]["ci_95"] is None
    assert agg_single["patient_macro"]["dice"]["ci_reason"] == "insufficient_clusters"
