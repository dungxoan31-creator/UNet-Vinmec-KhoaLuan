import csv
import json

import cv2
import numpy as np
import pytest
import torch

from backend.models.unet import StandardUNet
from evaluation.evaluate_vinmec import evaluate


def test_evaluation_restores_original_size_and_writes_review_artifacts(tmp_path):
    image = np.full((32, 48), 90, dtype=np.uint8)
    mask = np.zeros_like(image)
    mask[8:20, 12:30] = 255
    image_path = tmp_path / "scan.png"
    mask_path = tmp_path / "label.png"
    assert cv2.imwrite(str(image_path), image)
    assert cv2.imwrite(str(mask_path), mask)
    splits = tmp_path / "splits"
    splits.mkdir()
    with (splits / "val.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "image_path", "mask_path"])
        writer.writeheader()
        writer.writerow({"case_id": "case_1", "image_path": str(image_path), "mask_path": str(mask_path)})

    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    checkpoint = tmp_path / "model.pth"
    torch.save(model.state_dict(), checkpoint)
    output = tmp_path / "evaluation"

    summary = evaluate(splits, checkpoint, output, split="val")

    prediction = cv2.imread(str(output / "prediction_masks" / "case_1.png"), cv2.IMREAD_GRAYSCALE)
    overlay = cv2.imread(str(output / "overlays" / "case_1.png"), cv2.IMREAD_UNCHANGED)
    assert prediction.shape == image.shape
    assert set(np.unique(prediction)).issubset({0, 255})
    assert overlay.shape == (32, 48, 4)
    assert (output / "samples" / "case_1.png").is_file()
    with (output / "per_image.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert all(key in rows[0] for key in ("dice", "iou", "recall"))
    assert summary["split"] == "val"
    assert summary["threshold"] == 0.5
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["count"] == 1


def test_evaluation_rejects_mismatched_image_and_mask(tmp_path):
    image_path = tmp_path / "scan.png"
    mask_path = tmp_path / "label.png"
    cv2.imwrite(str(image_path), np.zeros((20, 30), dtype=np.uint8))
    cv2.imwrite(str(mask_path), np.zeros((21, 30), dtype=np.uint8))
    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "test.csv").write_text(
        f"case_id,image_path,mask_path\ncase_1,{image_path},{mask_path}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="shape"):
        evaluate(splits, tmp_path / "unused.pth", tmp_path / "out", split="test")


def test_evaluation_rejects_checkpoint_outside_locked_selection(tmp_path):
    image_path = tmp_path / "scan.png"
    mask_path = tmp_path / "label.png"
    cv2.imwrite(str(image_path), np.zeros((32, 32), dtype=np.uint8))
    cv2.imwrite(str(mask_path), np.zeros((32, 32), dtype=np.uint8))
    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "test.csv").write_text(
        f"case_id,image_path,mask_path\ncase_1,{image_path},{mask_path}\n", encoding="utf-8"
    )
    checkpoint = tmp_path / "model.pth"
    torch.save(StandardUNet(in_channels=1, num_classes=1, base_filters=32).state_dict(), checkpoint)
    with pytest.raises(ValueError, match="checksum"):
        evaluate(splits, checkpoint, tmp_path / "out", split="test", expected_sha256="0" * 64)
    assert not (tmp_path / "out").exists()
