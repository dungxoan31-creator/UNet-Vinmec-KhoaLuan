"""Unit and validation tests for automated caliper measurement on synthetic phantoms.

Verifies bias, MAE, ICC(2,1), and Bland-Altman Limits of Agreement under Assumption A2.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.validate_caliper_phantoms import (
    calculate_bland_altman,
    calculate_icc_2_1,
    generate_synthetic_phantoms,
    run_phantom_validation,
)


def test_calculate_icc_2_1_known_values():
    """Verify ICC(2,1) produces near 1.0 for highly consistent data and near 0.0 for uncorrelated noise."""
    rng = np.random.RandomState(42)
    # 20 subjects with true values 10 to 50, small measurement noise (+/- 0.1)
    true_vals = np.linspace(10, 50, 20)[:, None]
    high_agreement = true_vals + rng.normal(0, 0.05, size=(20, 5))
    icc_high = calculate_icc_2_1(high_agreement)
    assert icc_high >= 0.95, f"Expected high ICC, got {icc_high}"

    # Pure random noise with no between-subject variance
    pure_noise = rng.normal(10, 1.0, size=(20, 5))
    icc_noise = calculate_icc_2_1(pure_noise)
    assert icc_noise < 0.30, f"Expected low ICC for noise, got {icc_noise}"


def test_calculate_bland_altman_metrics():
    """Verify Bland-Altman returns correct bias, limits of agreement, and confidence intervals."""
    gt = np.array([20.0, 30.0, 40.0, 50.0, 60.0])
    meas = np.array([20.5, 30.5, 40.5, 50.5, 60.5])
    ba = calculate_bland_altman(meas, gt)

    assert ba["mean_bias_mm"] == pytest.approx(0.5, abs=0.01)
    assert ba["sd_bias_mm"] == pytest.approx(0.0, abs=0.01)
    assert ba["loa_upper_mm"] == pytest.approx(0.5, abs=0.01)
    assert ba["loa_lower_mm"] == pytest.approx(0.5, abs=0.01)


def test_generate_synthetic_phantoms_attributes():
    """Verify generated phantoms have expected shapes, valid masks, and ground-truth axes."""
    phantoms = generate_synthetic_phantoms(n=10, seed=123)
    assert len(phantoms) == 10
    for p in phantoms:
        assert "id" in p
        assert p["shape_type"] in {"ellipse", "rounded_rect", "lobulated", "irregular"}
        assert p["pixel_spacing_mm"] > 0
        assert p["gt_max_mm"] >= p["gt_orth_mm"] > 0
        assert p["mask"].shape == (512, 512)
        assert np.sum(p["mask"]) > 0


def test_caliper_phantom_accuracy_and_icc_pass_criteria():
    """Verify that caliper measurement meets academic thresholds (MAE <= 1 mm or <= 2%, ICC >= 0.90)."""
    results = run_phantom_validation(n_phantoms=50, n_iterations=5)

    assert results["status"] == "PASS"
    metrics = results["metrics"]
    thresholds = results["thresholds"]

    # Criterion 1: MAE <= 1.0 mm OR MAE % <= 2.0%
    assert thresholds["passes_mae"] is True
    assert (metrics["mean_mae_mm"] <= 1.0) or (metrics["mean_mae_pct"] <= 2.0)

    # Criterion 2: ICC(2,1) >= 0.90 for both axes
    assert thresholds["passes_icc"] is True
    assert metrics["icc_dmax"] >= 0.90
    assert metrics["icc_dorth"] >= 0.90

    # Criterion 3: Bland-Altman mean bias is close to zero
    ba_dmax = results["bland_altman"]["dmax"]
    assert abs(ba_dmax["mean_bias_mm"]) < 1.0
