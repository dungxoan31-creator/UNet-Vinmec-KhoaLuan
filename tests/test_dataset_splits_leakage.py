"""
Unit tests for Protocol 1 Zero-Leakage Dataset Splitting & File Integrity.
"""

import os
import pandas as pd
import pytest

def test_protocol_1_file_exists():
    assert os.path.exists("ai_training/splits/train.csv"), "train.csv must exist"
    assert os.path.exists("ai_training/splits/val.csv"), "val.csv must exist"
    assert os.path.exists("ai_training/splits/test.csv"), "test.csv must exist"

def test_protocol_1_counts_and_zero_leakage():
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")

    assert len(train_df) == 700, f"Expected 700 train, got {len(train_df)}"
    assert len(val_df) == 120, f"Expected 120 val, got {len(val_df)}"
    assert len(test_df) == 382, f"Expected 382 test, got {len(test_df)}"

    train_set = set(train_df["image_path"].apply(os.path.normpath))
    val_set = set(val_df["image_path"].apply(os.path.normpath))
    test_set = set(test_df["image_path"].apply(os.path.normpath))

    # Strict Zero-Leakage assertions
    train_val_leak = train_set.intersection(val_set)
    train_test_leak = train_set.intersection(test_set)
    val_test_leak = val_set.intersection(test_set)

    assert len(train_val_leak) == 0, f"Data Leakage detected between Train and Val: {len(train_val_leak)} cases"
    assert len(train_test_leak) == 0, f"Data Leakage detected between Train and Test: {len(train_test_leak)} cases"
    assert len(val_test_leak) == 0, f"Data Leakage detected between Val and Test: {len(val_test_leak)} cases"

def test_disk_image_and_mask_pairs_exist():
    for split_file in ["train.csv", "val.csv", "test.csv"]:
        df = pd.read_csv(f"ai_training/splits/{split_file}")
        for idx in range(min(15, len(df))):
            row = df.iloc[idx]
            assert os.path.exists(row["image_path"]), f"Image missing: {row['image_path']}"
            assert os.path.exists(row["mask_path"]), f"Mask missing: {row['mask_path']}"
