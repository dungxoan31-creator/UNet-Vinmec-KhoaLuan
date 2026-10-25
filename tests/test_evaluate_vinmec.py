import csv
import hashlib
import json

import cv2
import numpy as np
import pytest
import torch

from backend.models.unet import StandardUNet
from evaluation import evaluate_vinmec as evaluator


@pytest.mark.parametrize("split", ["val", "test"])
def test_evaluation_restores_original_size_and_writes_review_artifacts(tmp_path, monkeypatch, split):
    image = np.full((32, 48), 90, dtype=np.uint8)
    mask = np.zeros_like(image)
    mask[8:20, 12:30] = 255
    image_path = tmp_path / "scan.png"
    mask_path = tmp_path / "label.png"
    assert cv2.imwrite(str(image_path), image)
    assert cv2.imwrite(str(mask_path), mask)
    splits = tmp_path / "splits"
    splits.mkdir()
    with (splits / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "image_path", "mask_path"])
        writer.writeheader()
        writer.writerow({"case_id": "case_1", "image_path": str(image_path), "mask_path": str(mask_path)})

    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    checkpoint = tmp_path / "model.pth"
    torch.save(model.state_dict(), checkpoint)
    output = tmp_path / "evaluation"

    expected_sha256 = None
    if split == "test":
        monkeypatch.setattr(
            evaluator,
            "validate_training_split_identity",
            lambda _path: "patient_level_verified",
            raising=False,
        )
        expected_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    summary = evaluator.evaluate(splits, checkpoint, output, split=split, expected_sha256=expected_sha256)

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
    assert summary["split"] == split
    assert summary["patient_level_independence_verified"] is (split == "test")
    assert summary["test_inference_performed"] is (split == "test")
    assert summary["independent_test_performance_claim_supported"] is False
    if split == "test":
        assert summary["test_split_used_for_model_selection"] is None
        assert summary["label_provenance_verified"] is False
    assert summary["threshold"] == 0.5
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["count"] == 1


def test_pair_reader_rejects_mismatched_image_and_mask(tmp_path):
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
        evaluator._read_pairs(splits, "test")


def test_test_evaluation_rejects_checkpoint_outside_locked_selection(tmp_path, monkeypatch):
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
    monkeypatch.setattr(
        evaluator,
        "_read_pairs",
        lambda *_args: pytest.fail("Test data read before checkpoint hash verification"),
    )
    with pytest.raises(ValueError, match="checksum"):
        monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "patient_level_verified", raising=False)
        evaluator.evaluate(splits, checkpoint, tmp_path / "out", split="test", expected_sha256="0" * 64)
    assert not (tmp_path / "out").exists()


def test_test_evaluation_blocks_unverified_patient_split_before_reading_data(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"locked checkpoint")
    monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "image_level_only", raising=False)
    monkeypatch.setattr(evaluator, "_read_pairs", lambda *_args: pytest.fail("Test data read before identity gate"))

    with pytest.raises(ValueError, match="(?i)patient-level"):
        evaluator.evaluate(
            tmp_path / "splits",
            checkpoint,
            tmp_path / "out",
            split="test",
            expected_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        )

    assert not (tmp_path / "out").exists()


def test_test_evaluation_requires_locked_checkpoint_hash_before_reading_data(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "patient_level_verified", raising=False)
    monkeypatch.setattr(evaluator, "_read_pairs", lambda *_args: pytest.fail("Test data read without a locked checkpoint hash"))

    with pytest.raises(ValueError, match="(?i)locked checkpoint hash"):
        evaluator.evaluate(tmp_path / "splits", tmp_path / "model.pth", tmp_path / "out", split="test")


@pytest.mark.parametrize("threshold", [None, "bad", float("nan"), float("inf"), -0.1, 0.0, 1.0, 1.1, True])
def test_evaluator_rejects_invalid_threshold_before_reading_data(tmp_path, monkeypatch, threshold):
    monkeypatch.setattr(evaluator, "_read_pairs", lambda *_args: pytest.fail("Data read before threshold validation"))

    with pytest.raises(ValueError, match="(?i)threshold"):
        evaluator.evaluate(tmp_path / "splits", tmp_path / "model.pth", tmp_path / "out", threshold=threshold)


def test_evaluator_refuses_to_overwrite_existing_artifacts(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"checkpoint")
    output = tmp_path / "out"
    output.mkdir()
    artifact = output / "summary.json"
    artifact.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(evaluator, "_read_pairs", lambda *_args: pytest.fail("Data read before overwrite guard"))

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        evaluator.evaluate(tmp_path / "splits", checkpoint, output)

    assert artifact.read_text(encoding="utf-8") == "preserve"
