import csv
import hashlib
import json

import cv2
import numpy as np

from evaluation import finalize_selected_test as finalizer


def test_partial_patient_evidence_does_not_attach_replay_to_official_selection(tmp_path, monkeypatch):
    checkpoint = tmp_path / "checkpoints" / "model.pth"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"selected checkpoint")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    selection_path = tmp_path / "evaluation" / "selected_model.json"
    selection_path.parent.mkdir()
    selection = {
        "checkpoint": "checkpoints/model.pth",
        "checkpoint_sha256": checkpoint_hash,
        "threshold": 0.4,
        "selection_split": "val",
        "independent_test_status": "BLOCKED",
        "independent_gate_status": "BLOCKED",
        "test_evaluation": None,
    }
    original_selection = json.dumps(selection, indent=2).encode("utf-8")
    selection_path.write_bytes(original_selection)

    result_dir = tmp_path / "evaluation" / "retrain_2d_2026-10-03"
    test_dir = result_dir / "test"
    for directory in (test_dir / "prediction_masks", test_dir / "comparison_panels"):
        directory.mkdir(parents=True)
    (test_dir / "summary.json").write_text(
        json.dumps(
            {
                "checkpoint_sha256": checkpoint_hash,
                "threshold": 0.4,
                "split": "test",
                "count": 1,
                "dice_mean_all_cases": 0.7,
                "iou_mean_all_cases": 0.6,
                "recall_mean_all_cases": 0.8,
                "clinical_summary": {
                    "normal_cases_count": 0,
                    "precision_mean": 0.7,
                    "specificity_all_cases": 0.9,
                    "specificity_normal_cases": None,
                },
            }
        ),
        encoding="utf-8",
    )
    split_dir = tmp_path / "ai_training" / "splits" / "legacy"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        json.dumps({"counts": {"test": 1}, "source_test_preserved": True, "patient_id_status": "synthetic"}),
        encoding="utf-8",
    )

    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    for name in ("image.png", "mask.png"):
        assert cv2.imwrite(str(dataset_dir / name), np.zeros((8, 8), dtype=np.uint8))
    for folder in (test_dir / "prediction_masks", test_dir / "comparison_panels"):
        assert cv2.imwrite(str(folder / "CASE-1.png"), np.zeros((8, 8), dtype=np.uint8))
    with (test_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["case_id", "dice", "iou", "fp", "fn", "image_path", "mask_path"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "case_id": "CASE-1",
                "dice": 0.7,
                "iou": 0.6,
                "fp": 2,
                "fn": 3,
                "image_path": "dataset/image.png",
                "mask_path": "dataset/mask.png",
            }
        )

    monkeypatch.setattr(finalizer, "ROOT", tmp_path)
    monkeypatch.setattr(finalizer, "RESULT_DIR", result_dir)
    monkeypatch.setattr(finalizer, "SPLIT_DIR", split_dir)
    monkeypatch.setattr(finalizer, "SELECTION_PATH", selection_path)

    finalizer.main()

    assert json.loads(selection_path.read_text(encoding="utf-8")) == json.loads(original_selection)
    report = json.loads((result_dir / "test_summary.json").read_text(encoding="utf-8"))
    assert report["patient_level_independence_verified"] is False
