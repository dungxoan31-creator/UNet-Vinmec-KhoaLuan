import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

from ai_training.metrics_clinical import compute_dataset_clinical_summary
from evaluation import evaluate_external_vinmec as evaluator
from evaluation.evaluate_external_vinmec import binary_prediction, select_unseen_pairs
from tests.patient_split_fixture import attach_source_identity_evidence


def _write_verified_checkpoint(checkpoint_dir: Path, root: Path) -> Path:
    split_dir = root / "verified-split"
    split_dir.mkdir()
    development_images = root / "development"
    development_images.mkdir()
    manifest = {
        "source_patient_identity_verified": True,
        "patient_ids_verified": True,
        "identity_level": "patient_verified",
        "split_counts": {name: 1 for name in ("train", "val", "test")},
    }
    manifest_path = split_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for name in ("train", "val", "test"):
        image_path = development_images / f"{name}.JPG"
        mask_path = development_images / f"{name}.PNG"
        assert cv2.imwrite(str(image_path), np.full((12, 16), 20 + len(name), dtype=np.uint8))
        assert cv2.imwrite(str(mask_path), np.zeros((12, 16), dtype=np.uint8))
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        mask_hash = hashlib.sha256(mask_path.read_bytes()).hexdigest()
        (split_dir / f"{name}.csv").write_text(
            f"case_id,patient_id,image_sha256,mask_sha256,image_path,mask_path\n"
            f"case-{name},P-{name},{image_hash},{mask_hash},{image_path},{mask_path}\n",
            encoding="utf-8",
        )

    attach_source_identity_evidence(split_dir)

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / "full_unet_final.pth"
    torch.save({}, checkpoint)
    run_config = {
        "architecture": "Standard U-Net (base_filters=32)",
        "identity_status": "patient_level_verified",
        "split_dir": str(split_dir.resolve()),
        "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "test_split_image_data_used": False,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    }
    (checkpoint_dir / "full_unet_run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
    return checkpoint


def test_select_unseen_pairs_excludes_renamed_training_image(tmp_path: Path):
    source_images = tmp_path / "source/images"
    source_masks = tmp_path / "source/labels"
    training_images = tmp_path / "training"
    for folder in (source_images, source_masks, training_images):
        folder.mkdir(parents=True)

    seen = np.full((12, 16), 40, dtype=np.uint8)
    unseen = np.full((12, 16), 90, dtype=np.uint8)
    cv2.imwrite(str(training_images / "renamed.JPG"), seen)
    cv2.imwrite(str(source_images / "1.JPG"), seen)
    cv2.imwrite(str(source_images / "2.JPG"), unseen)
    for name in ("1", "2"):
        cv2.imwrite(str(source_masks / f"{name}.PNG"), np.full((12, 16), 255, dtype=np.uint8))

    pairs = select_unseen_pairs(source_images, source_masks, [training_images])

    assert [image.name for image, _ in pairs] == ["2.JPG"]


def test_empty_mask_specificity_is_unavailable_without_empty_cases():
    metrics = compute_dataset_clinical_summary(
        [{"is_empty": False, "dice": 0.5, "iou": 0.333, "recall": 0.5, "precision": 0.5, "specificity": 0.9}]
    )

    assert metrics["normal_cases_count"] == 0
    assert metrics["specificity_normal_cases"] is None


def test_binary_prediction_threshold_controls_false_positives():
    probability = np.array([[0.2, 0.6, 0.9]], dtype=np.float32)
    assert binary_prediction(probability, 0.5).tolist() == [[0, 1, 1]]
    assert binary_prediction(probability, 0.7).tolist() == [[0, 0, 1]]


def test_external_evaluation_requires_verified_checkpoint_provenance(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    images = source_dir / "images"
    masks = source_dir / "labels"
    images.mkdir(parents=True)
    masks.mkdir()
    assert cv2.imwrite(str(images / "1.JPG"), np.full((12, 16), 80, dtype=np.uint8))
    assert cv2.imwrite(str(masks / "1.PNG"), np.zeros((12, 16), dtype=np.uint8))
    checkpoint = tmp_path / "unverified.pth"
    torch.save({}, checkpoint)

    class EmptyModel(torch.nn.Module):
        def forward(self, inputs):
            return torch.zeros(
                (inputs.shape[0], 1, inputs.shape[-2], inputs.shape[-1]),
                dtype=inputs.dtype,
                device=inputs.device,
            )

    monkeypatch.setattr(evaluator, "StandardUNet", lambda **kwargs: EmptyModel())
    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        evaluator.evaluate(source_dir, checkpoint, output_dir, [])

    assert not output_dir.exists()


def test_external_evaluation_rejects_non_binary_reference_mask(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    images = source_dir / "images"
    masks = source_dir / "labels"
    images.mkdir(parents=True)
    masks.mkdir()
    assert cv2.imwrite(str(images / "1.JPG"), np.full((12, 16), 80, dtype=np.uint8))
    assert cv2.imwrite(str(masks / "1.PNG"), np.full((12, 16), 42, dtype=np.uint8))
    checkpoint = _write_verified_checkpoint(tmp_path / "checkpoint", tmp_path)

    class EmptyModel(torch.nn.Module):
        def forward(self, inputs):
            return torch.zeros(
                (inputs.shape[0], 1, inputs.shape[-2], inputs.shape[-1]),
                dtype=inputs.dtype,
                device=inputs.device,
            )

    monkeypatch.setattr(evaluator, "StandardUNet", lambda **kwargs: EmptyModel())
    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="mask"):
        evaluator.evaluate(source_dir, checkpoint, output_dir, [])

    assert not output_dir.exists()


def test_external_evaluation_marks_scope_as_image_level_only(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    images = source_dir / "images"
    masks = source_dir / "labels"
    images.mkdir(parents=True)
    masks.mkdir()
    assert cv2.imwrite(str(images / "1.JPG"), np.full((12, 16), 80, dtype=np.uint8))
    assert cv2.imwrite(str(masks / "1.PNG"), np.full((12, 16), 255, dtype=np.uint8))
    checkpoint = _write_verified_checkpoint(tmp_path / "checkpoint", tmp_path)

    class EmptyModel(torch.nn.Module):
        def forward(self, inputs):
            return torch.zeros(
                (inputs.shape[0], 1, inputs.shape[-2], inputs.shape[-1]),
                dtype=inputs.dtype,
                device=inputs.device,
            )

    monkeypatch.setattr(evaluator, "StandardUNet", lambda **kwargs: EmptyModel())
    output_dir = tmp_path / "output"

    summary = evaluator.evaluate(source_dir, checkpoint, output_dir, [])

    assert summary["evaluation_scope"] == "image_level_external_screening"
    assert summary["patient_independence_verified"] is False
    assert summary["training_patient_identity_verified"] is True
    with (output_dir / "external_vinmec_per_image.csv").open(encoding="utf-8") as stream:
        assert "1.JPG" not in stream.read()
