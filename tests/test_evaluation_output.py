"""
Unit tests for Task 7: Independent Evaluation on Held-Out Test Set and Visualization Artifacts.
"""

import json
import os
from pathlib import Path
import pytest


def test_evaluation_metrics_file_integrity():
    """Verify that evaluation/baseline_test_metrics.json exists and has valid clinical scores."""
    metrics_path = Path("evaluation/baseline_test_metrics.json")
    assert metrics_path.exists(), "baseline_test_metrics.json does not exist!"
    
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    
    dice = data.get("foreground_dice_mean", data.get("mean_foreground_dice"))
    recall = data.get("recall_sensitivity_mean", data.get("mean_recall"))
    spec = data.get("specificity_all_cases", data.get("mean_specificity"))
    
    assert dice is not None, "Missing foreground_dice_mean or mean_foreground_dice"
    assert recall is not None, "Missing recall_sensitivity_mean or mean_recall"
    assert spec is not None, "Missing specificity_all_cases or mean_specificity"
    
    # Check clinical metrics quality gates
    assert 0.70 <= dice <= 1.0, f"Foreground Dice ({dice}) is below expected baseline range [0.70, 1.0]"
    assert 0.80 <= recall <= 1.0, f"Recall/Sensitivity ({recall}) is below clinical safety target 0.80"
    assert 0.90 <= spec <= 1.0, f"Specificity ({spec}) is below false positive control target 0.90"


def test_visualization_grid_and_curves_exist():
    """Verify that training convergence curve and visual sample grids were exported."""
    curve_path = Path("evaluation/baseline_visualizations/training_convergence_curves.png")
    assert curve_path.exists(), f"Convergence curve missing: {curve_path}"
    assert curve_path.stat().st_size > 1000, "Convergence curve image is empty!"
    
    vis_dir = Path("evaluation/baseline_visualizations")
    png_files = list(vis_dir.glob("*.png"))
    assert len(png_files) >= 1, f"Expected at least 1 visualization figure in {vis_dir}, found {len(png_files)}"
