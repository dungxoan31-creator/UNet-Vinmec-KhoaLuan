"""Tests for MMOTU to nnU-Net v2 dataset conversion pipeline.

Verifies:
1. Structure of dataset.json against nnU-Net v2 official specifications.
2. Custom splits_final.json formatting for 5-fold cross-validation / manual splits.
3. Integrity of image conversion (1-channel grayscale PNG) and mask binarization (0/1).
4. Direct verification with nnunetv2.experiment_planning.verify_dataset_integrity.
5. Preservation of image-level splits without synthetic patient IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import cv2
import numpy as np
import pytest

from scripts.prepare_mmotu_for_nnunet import (
    ROOT,
    generate_nnunet_dataset_json,
    generate_splits_final_json,
    load_split_records,
    prepare_mmotu_dataset,
)


@pytest.fixture
def sample_splits() -> tuple[Path, Path]:
    train_csv = ROOT / "ai_training/splits/mmotu_2d_official_2026-10-27/train.csv"
    val_csv = ROOT / "ai_training/splits/mmotu_2d_official_2026-10-27/val.csv"
    assert train_csv.exists(), f"train.csv missing at {train_csv}"
    assert val_csv.exists(), f"val.csv missing at {val_csv}"
    return train_csv, val_csv


def test_dataset_json_specification(tmp_path: Path):
    """Test that generated dataset.json satisfies all nnU-Net v2 requirements."""
    dataset_dir = tmp_path / "Dataset101_MMOTU"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    dataset_json = generate_nnunet_dataset_json(
        output_folder=dataset_dir,
        num_training_cases=1000,
        dataset_name="MMOTU",
        channel_name="US",
        file_ending=".png",
    )

    json_file = dataset_dir / "dataset.json"
    assert json_file.exists()

    loaded = json.loads(json_file.read_text(encoding="utf-8"))
    assert loaded == dataset_json

    # nnU-Net v2 required fields
    assert "channel_names" in loaded
    assert "labels" in loaded
    assert "numTraining" in loaded
    assert "file_ending" in loaded

    # Channel names keys must be string representations of ints
    for key, val in loaded["channel_names"].items():
        assert isinstance(key, str)
        assert key.isdigit()
        assert val == "US"

    # Labels background must be 0 and lesion 1
    assert loaded["labels"]["background"] == 0
    assert loaded["labels"]["lesion"] == 1
    assert loaded["file_ending"] == ".png"
    assert loaded["numTraining"] == 1000


def test_splits_final_json_structure(tmp_path: Path):
    """Test that generated splits_final.json adheres to nnU-Net manual split contract."""
    train_ids = [f"case_{i}" for i in range(10)]
    val_ids = [f"case_{i}" for i in range(10, 15)]

    splits = generate_splits_final_json(
        train_ids=train_ids,
        val_ids=val_ids,
        output_folder=tmp_path,
        num_folds=5,
    )

    splits_file = tmp_path / "splits_final.json"
    assert splits_file.exists()

    loaded = json.loads(splits_file.read_text(encoding="utf-8"))
    assert len(loaded) == 5

    # Fold 0 must strictly match official train and val IDs
    fold_0 = loaded[0]
    assert set(fold_0["train"]) == set(train_ids)
    assert set(fold_0["val"]) == set(val_ids)
    assert len(set(fold_0["train"]) & set(fold_0["val"])) == 0

    # Every fold must be a dict with 'train' and 'val' without mutual leakage
    all_cases = set(train_ids) | set(val_ids)
    for fold in loaded:
        assert "train" in fold
        assert "val" in fold
        assert len(set(fold["train"]) & set(fold["val"])) == 0
        assert set(fold["train"]) | set(fold["val"]) == all_cases


def test_dry_run_manifest(sample_splits: tuple[Path, Path], tmp_path: Path):
    """Test dry-run mode without modifying filesystem."""
    train_csv, val_csv = sample_splits
    output_dir = tmp_path / "Dataset101_MMOTU"

    manifest = prepare_mmotu_dataset(
        train_csv=train_csv,
        val_csv=val_csv,
        output_dir=output_dir,
        dry_run=True,
    )

    assert manifest["dry_run"] is True
    assert manifest["split_level"] == "image-level"
    assert manifest["patient_identity_available"] is False
    assert manifest["patient_level_independence_verified"] is False
    assert manifest["num_training_cases"] == 1469
    assert manifest["train_cases_count"] == 1000
    assert manifest["val_cases_count"] == 469
    assert not output_dir.exists()


def test_sample_dataset_conversion_and_nnunet_integrity(
    sample_splits: tuple[Path, Path], tmp_path: Path
):
    """Test end-to-end dataset generation on 8 sample cases and verify with nnU-Net v2."""
    from nnunetv2.experiment_planning.verify_dataset_integrity import verify_dataset_integrity

    train_csv, val_csv = sample_splits
    output_dir = tmp_path / "Dataset101_MMOTU"

    manifest = prepare_mmotu_dataset(
        train_csv=train_csv,
        val_csv=val_csv,
        output_dir=output_dir,
        limit=8,
        file_mode="copy",
        dry_run=False,
    )

    assert output_dir.exists()
    images_tr = output_dir / "imagesTr"
    labels_tr = output_dir / "labelsTr"
    assert images_tr.exists()
    assert labels_tr.exists()

    image_files = list(images_tr.glob("*.png"))
    label_files = list(labels_tr.glob("*.png"))
    assert len(image_files) == 8
    assert len(label_files) == 8

    # Verify each image and label properties
    for img_p in image_files:
        assert img_p.name.endswith("_0000.png")
        case_id = img_p.name[:-9]
        lbl_p = labels_tr / f"{case_id}.png"
        assert lbl_p.exists(), f"Missing label for {case_id}"

        # Read image with cv2 to verify 1-channel grayscale
        img = cv2.imread(str(img_p), cv2.IMREAD_UNCHANGED)
        assert img.ndim == 2, f"Expected 1-channel 2D image, got shape {img.shape}"

        # Read mask to verify binary values {0, 1}
        lbl = cv2.imread(str(lbl_p), cv2.IMREAD_UNCHANGED)
        assert lbl.ndim == 2, f"Expected 1-channel 2D mask, got shape {lbl.shape}"
        assert img.shape == lbl.shape, f"Shape mismatch: img={img.shape}, lbl={lbl.shape}"
        unique_vals = set(np.unique(lbl).tolist())
        assert unique_vals.issubset({0, 1}), f"Mask has unexpected values: {unique_vals}"

    # Verify using nnU-Net v2's official integrity verifier
    # Should complete without error
    verify_dataset_integrity(str(output_dir), num_processes=2)


def test_val_as_test_mode(sample_splits: tuple[Path, Path], tmp_path: Path):
    """Test validation mode 'test' correctly isolates imagesTs / labelsTs."""
    train_csv, val_csv = sample_splits
    output_dir = tmp_path / "Dataset101_MMOTU_TestMode"

    manifest = prepare_mmotu_dataset(
        train_csv=train_csv,
        val_csv=val_csv,
        output_dir=output_dir,
        limit=8,
        val_mode="test",
        file_mode="copy",
        dry_run=False,
    )

    assert manifest["val_mode"] == "test"
    assert (output_dir / "imagesTr").exists()
    assert (output_dir / "labelsTr").exists()
    assert (output_dir / "imagesTs").exists()
    assert (output_dir / "labelsTs").exists()

    tr_imgs = list((output_dir / "imagesTr").glob("*.png"))
    ts_imgs = list((output_dir / "imagesTs").glob("*.png"))
    assert len(tr_imgs) + len(ts_imgs) == 8
    assert manifest["num_training_cases"] == len(tr_imgs)
    assert manifest["num_testing_cases"] == len(ts_imgs)
