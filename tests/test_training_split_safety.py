import json

import pandas as pd
import pytest

from ai_training.train_baseline_unet import validate_training_split_identity


def _write_splits(root, patient_ids, manifest):
    root.mkdir(parents=True)
    for split, ids in patient_ids.items():
        pd.DataFrame({"patient_id": ids, "case_id": [f"{split}-{i}" for i in range(len(ids))]}).to_csv(root / f"{split}.csv", index=False)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_unverified_image_split_is_blocked_unless_explicitly_opted_in(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": [""], "val": [""], "test": [""]},
        {"identity_limit": "No verified source Patient/Case IDs; split is image-level only"},
    )

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        validate_training_split_identity(splits)

    assert validate_training_split_identity(splits, allow_image_level=True) == "image_level_only"


def test_verified_patient_split_rejects_patient_overlap(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-1"]},
        {"patient_ids_verified": True},
    )

    with pytest.raises(ValueError, match="overlap"):
        validate_training_split_identity(splits)


def test_verified_patient_split_accepts_disjoint_patients(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )

    assert validate_training_split_identity(splits) == "patient_level_verified"
