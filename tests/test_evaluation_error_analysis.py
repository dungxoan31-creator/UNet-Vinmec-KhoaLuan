import csv

import cv2
import numpy as np

from evaluation.error_analysis import build_error_analysis


def test_error_analysis_resolves_repo_root_and_writes_case_panel(tmp_path):
    run_dir = tmp_path / "evaluation" / "milestone_3_final" / "validation_run"
    prediction_dir = run_dir / "predictions"
    image_path = tmp_path / "dataset" / "images" / "sample.png"
    mask_path = tmp_path / "dataset" / "masks" / "sample.png"
    manifest_path = tmp_path / "evaluation" / "manifests" / "validation_v1.csv"
    legacy_manifest_path = tmp_path / "evaluation" / "manifests" / "legacy_test_v1.csv"
    sample_id = "sample-1"

    prediction_dir.mkdir(parents=True)
    image_path.parent.mkdir(parents=True)
    mask_path.parent.mkdir(parents=True)
    manifest_path.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    image = np.full((24, 32), 96, dtype=np.uint8)
    mask = np.zeros_like(image)
    mask[6:18, 8:20] = 255
    prediction = (mask > 0).astype(np.uint8) * 255
    assert cv2.imwrite(str(image_path), image)
    assert cv2.imwrite(str(mask_path), mask)
    assert cv2.imwrite(str(prediction_dir / f"{sample_id}.png"), prediction)

    with manifest_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sample_id", "image_path", "mask_path"])
        writer.writeheader()
        writer.writerow({
            "sample_id": sample_id,
            "image_path": "dataset/images/sample.png",
            "mask_path": "dataset/masks/sample.png",
        })

    with legacy_manifest_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sample_id", "image_path", "mask_path"])
        writer.writeheader()
        writer.writerow({
            "sample_id": "not-in-this-run",
            "image_path": "dataset/images/sample.png",
            "mask_path": "dataset/masks/sample.png",
        })

    with (run_dir / "per_image_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "sample_id", "dice", "iou", "recall", "precision", "specificity", "hd95_px",
            "tp", "fp", "fn", "tn", "fp_area_px", "fn_area_px", "under_fraction", "over_fraction",
            "gt_empty", "pred_empty",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "sample_id": sample_id, "dice": 1, "iou": 1, "recall": 1, "precision": 1,
            "specificity": 1, "hd95_px": 0, "tp": 144, "fp": 0, "fn": 0, "tn": 624,
            "fp_area_px": 0, "fn_area_px": 0, "under_fraction": 0, "over_fraction": 0,
            "gt_empty": "false", "pred_empty": "false",
        })

    result = build_error_analysis(run_dir, k=1)

    assert result["total_analyzed_cases"] == 1
    assert (run_dir / "error_analysis" / "panels" / f"{sample_id}.png").is_file()
