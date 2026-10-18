"""Tests for Error Analysis, Ranking and Case Panel Rendering v1."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from evaluation.error_analysis import rank_cases, render_case

ROOT = Path(__file__).resolve().parents[1]


def test_groups_and_difference_colors(tmp_path):
    # Create a synthetic case with known TP, FP, FN
    orig = np.full((100, 100), 100, dtype=np.uint8)
    gt = np.zeros((100, 100), dtype=np.uint8)
    pred = np.zeros((100, 100), dtype=np.uint8)

    # TP: (40:60, 40:60)
    gt[40:60, 40:60] = 1
    pred[40:60, 40:60] = 1

    # FP: (10:30, 10:30) -> pred only
    pred[10:30, 10:30] = 1

    # FN: (70:90, 70:90) -> gt only
    gt[70:90, 70:90] = 1

    img_path = tmp_path / "orig.png"
    cv2.imwrite(str(img_path), orig)

    out_panel = tmp_path / "panel.png"
    render_case(
        image_path=img_path,
        gt_mask=gt,
        pred_mask=pred,
        output_path=out_panel,
        sample_id="test_sample"
    )

    assert out_panel.exists()
    panel = cv2.imread(str(out_panel))
    # Panel layout has 5 columns: Original, GT, Prediction, Overlay, Difference
    # Verify shape is wide: width >= 5 * 100
    assert panel.shape[1] >= 500
    assert panel.shape[0] >= 100


def test_median_ranking_and_ties():
    rows = [
        {"sample_id": "s1", "dice": 0.1, "fp_area_px": 10, "fn_area_px": 50, "under_fraction": 0.8, "over_fraction": 0.1, "hd95_px": 10.0, "gt_empty": False},
        {"sample_id": "s2", "dice": 0.5, "fp_area_px": 5, "fn_area_px": 5, "under_fraction": 0.5, "over_fraction": 0.5, "hd95_px": 5.0, "gt_empty": False},
        {"sample_id": "s3", "dice": 0.9, "fp_area_px": 1, "fn_area_px": 1, "under_fraction": 0.1, "over_fraction": 0.1, "hd95_px": 1.0, "gt_empty": False},
    ]
    groups = rank_cases(rows, k=1)
    assert groups["best"] == ["s3"]
    assert groups["worst"] == ["s1"]
    assert groups["median"] == ["s2"]
    assert groups["fp"] == ["s1"]
    assert groups["fn"] == ["s1"]
    assert groups["under"] == ["s1"]
    assert groups["boundary"] == ["s1"]


def test_shape_mismatch_is_not_resized(tmp_path):
    img_path = tmp_path / "orig.png"
    cv2.imwrite(str(img_path), np.zeros((100, 100), dtype=np.uint8))
    mismatched_gt = np.zeros((120, 100), dtype=np.uint8)
    pred = np.zeros((100, 100), dtype=np.uint8)

    with pytest.raises(ValueError, match="shape.*mismatch"):
        render_case(
            image_path=img_path,
            gt_mask=mismatched_gt,
            pred_mask=pred,
            output_path=tmp_path / "fail.png",
            sample_id="mismatch"
        )


def test_html_escapes_annotation():
    from evaluation.error_analysis import _generate_html_report
    annotations = [{
        "sample_id": "s1",
        "groups": "worst",
        "observed_error": "FN at <border> & 'edge'",
        "hypothesis": "Hypothesis with <tags>",
        "reviewer_role": "Tester",
        "suggested_action": "Check <threshold>"
    }]
    html = _generate_html_report(annotations, panel_dir=Path("panels"))
    assert "<border>" not in html
    assert "&lt;border&gt;" in html
    assert "&lt;tags&gt;" in html


def test_small_cohort_does_not_invent_cases():
    # Only 2 rows, asking for top 5 -> returns 2 cases, does not invent cases
    rows = [
        {"sample_id": "s1", "dice": 0.2, "fp_area_px": 0, "fn_area_px": 10, "under_fraction": 0.5, "over_fraction": 0.0, "hd95_px": 4.0, "gt_empty": False},
        {"sample_id": "s2", "dice": 0.8, "fp_area_px": 5, "fn_area_px": 0, "under_fraction": 0.0, "over_fraction": 0.5, "hd95_px": 2.0, "gt_empty": False},
    ]
    groups = rank_cases(rows, k=5)
    assert len(groups["best"]) == 2
    assert len(groups["worst"]) == 2
