"""
Unit tests for Thesis Outline (Đề cương sơ bộ) Patient-Level Zero-Leakage Dataset Splitting & File Integrity.
Strictly verifies metrics defined in Table 1 & Section 6.2:
- Total collected images: 1,387
- Images with preliminary masks: 417 (30.1%)
- Ground Truth images (verified by specialists): 307 (22.1%) across 185 unique patients
  * Train (70%): 215 images (130 patients, 25 empty masks)
  * Val (15%): 46 images (27 patients, 5 empty masks)
  * Test (15%): 46 images (28 patients, 5 empty masks)
  * Total empty masks in Ground Truth: 35 (11.4%)
- Pending review images: 110 (13 empty masks, total 48 empty masks in 417 = 11.5%)
- Raw unannotated images: 970 (69.9%)
- Patient-Level Zero Leakage: 0 overlap between Train, Val, Test.
"""

import os
import json
import pandas as pd
import pytest


def test_kltn_de_cuong_split_files_exist():
    """Verify all official thesis split files and manifest exist."""
    files = [
        "ai_training/splits/train.csv",
        "ai_training/splits/val.csv",
        "ai_training/splits/test.csv",
        "ai_training/splits/kltn_train_307.csv",
        "ai_training/splits/kltn_val_307.csv",
        "ai_training/splits/kltn_test_307.csv",
        "ai_training/splits/kltn_ground_truth_307.csv",
        "ai_training/splits/kltn_pending_110.csv",
        "ai_training/splits/kltn_raw_unannotated_970.csv",
        "ai_training/splits/de_cuong_split_manifest.json",
        "dataset/vinmec_ovarian/vinmec_dataset_manifest.json"
    ]
    for f in files:
        assert os.path.exists(f), f"Required file missing: {f}"


def test_kltn_ground_truth_counts_and_zero_patient_leakage():
    """Verify exact counts (215/46/46) and zero patient leakage across 185 unique patients."""
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")

    # Image count checks (70% - 15% - 15%)
    assert len(train_df) == 215, f"Expected 215 train images, got {len(train_df)}"
    assert len(val_df) == 46, f"Expected 46 val images, got {len(val_df)}"
    assert len(test_df) == 46, f"Expected 46 test images, got {len(test_df)}"
    assert len(train_df) + len(val_df) + len(test_df) == 307, "Total Ground Truth images must equal 307"

    # Patient count checks (130 / 27 / 28 = 185 unique patients)
    assert train_df["patient_id"].nunique() == 130, f"Expected 130 train patients, got {train_df['patient_id'].nunique()}"
    assert val_df["patient_id"].nunique() == 27, f"Expected 27 val patients, got {val_df['patient_id'].nunique()}"
    assert test_df["patient_id"].nunique() == 28, f"Expected 28 test patients, got {test_df['patient_id'].nunique()}"

    train_pids = set(train_df["patient_id"])
    val_pids = set(val_df["patient_id"])
    test_pids = set(test_df["patient_id"])

    total_unique_pids = len(train_pids.union(val_pids).union(test_pids))
    assert total_unique_pids == 185, f"Expected 185 unique patients in Ground Truth, got {total_unique_pids}"

    # Strict Patient-Level Zero Leakage
    train_val_pid_leak = train_pids.intersection(val_pids)
    train_test_pid_leak = train_pids.intersection(test_pids)
    val_test_pid_leak = val_pids.intersection(test_pids)

    assert len(train_val_pid_leak) == 0, f"Patient leakage between Train and Val: {train_val_pid_leak}"
    assert len(train_test_pid_leak) == 0, f"Patient leakage between Train and Test: {train_test_pid_leak}"
    assert len(val_test_pid_leak) == 0, f"Patient leakage between Val and Test: {val_test_pid_leak}"

    # Strict Image-Level Zero Leakage
    train_imgs = set(train_df["image_path"].apply(os.path.normpath))
    val_imgs = set(val_df["image_path"].apply(os.path.normpath))
    test_imgs = set(test_df["image_path"].apply(os.path.normpath))

    assert len(train_imgs.intersection(val_imgs)) == 0, "Image leakage between Train and Val"
    assert len(train_imgs.intersection(test_imgs)) == 0, "Image leakage between Train and Test"
    assert len(val_imgs.intersection(test_imgs)) == 0, "Image leakage between Val and Test"


def test_kltn_empty_masks_and_table_1_metrics():
    """Verify empty mask distribution (35 in GT, 13 in Pending, 48 total in 417)."""
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")
    pending_df = pd.read_csv("ai_training/splits/kltn_pending_110.csv")
    raw_df = pd.read_csv("ai_training/splits/kltn_raw_unannotated_970.csv")

    train_empty = (train_df["is_empty_mask"] == True).sum()
    val_empty = (val_df["is_empty_mask"] == True).sum()
    test_empty = (test_df["is_empty_mask"] == True).sum()
    pending_empty = (pending_df["is_empty_mask"] == True).sum()

    assert train_empty == 25, f"Expected 25 empty masks in Train, got {train_empty}"
    assert val_empty == 5, f"Expected 5 empty masks in Val, got {val_empty}"
    assert test_empty == 5, f"Expected 5 empty masks in Test, got {test_empty}"

    total_gt_empty = train_empty + val_empty + test_empty
    assert total_gt_empty == 35, f"Expected 35 empty masks in Ground Truth (11.4%), got {total_gt_empty}"

    assert len(pending_df) == 110, f"Expected 110 pending review images, got {len(pending_df)}"
    assert pending_empty == 13, f"Expected 13 empty masks in Pending, got {pending_empty}"

    total_417_empty = total_gt_empty + pending_empty
    assert total_417_empty == 48, f"Expected 48 empty masks across 417 masks (11.5%), got {total_417_empty}"

    assert len(raw_df) == 970, f"Expected 970 raw unannotated images, got {len(raw_df)}"

    total_repo_images = len(train_df) + len(val_df) + len(test_df) + len(pending_df) + len(raw_df)
    assert total_repo_images == 1387, f"Expected 1,387 total images, got {total_repo_images}"


def test_disk_image_and_mask_pairs_exist():
    """Verify that image and mask files exist on disk for all splits."""
    for split_file in ["train.csv", "val.csv", "test.csv", "kltn_pending_110.csv"]:
        df = pd.read_csv(f"ai_training/splits/{split_file}")
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            img_path = row["image_path"].replace("\\", "/")
            mask_path = row["mask_path"].replace("\\", "/")
            assert os.path.exists(img_path), f"Image missing on disk: {img_path}"
            assert os.path.exists(mask_path), f"Mask missing on disk: {mask_path}"


def test_manifest_consistency():
    """Verify that de_cuong_split_manifest.json reflects exact metrics."""
    with open("ai_training/splits/de_cuong_split_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    metrics = manifest["table_1_metrics"]
    assert metrics["total_images_collected"] == 1387
    assert metrics["images_with_initial_masks"] == 417
    assert metrics["ground_truth_images_verified"] == 307
    assert metrics["pending_review_images"] == 110
    assert metrics["raw_unannotated_images"] == 970
    assert metrics["unique_patients_ground_truth"] == 185
    assert metrics["empty_masks_in_ground_truth"] == 35
    assert metrics["empty_masks_in_417_masks"] == 48
    assert manifest["zero_leakage_verified"] is True
