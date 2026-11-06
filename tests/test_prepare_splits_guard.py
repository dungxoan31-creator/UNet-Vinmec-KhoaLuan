import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

from scripts import prepare_splits


def _metadata(root: Path, count_per_class: int = 12) -> pd.DataFrame:
    rows = []
    image_dir = root / "images"
    mask_dir = root / "masks"
    image_dir.mkdir(parents=True)
    mask_dir.mkdir(parents=True)
    index = 0
    for is_empty in (True, False):
        for sample in range(count_per_class):
            index += 1
            image = np.full((32, 40), index, dtype=np.uint8)
            mask = np.zeros((32, 40), dtype=np.uint8)
            if not is_empty:
                mask[8:20, 10:24] = 255
            image_path = image_dir / f"{index}.png"
            mask_path = mask_dir / f"{index}.png"
            assert cv2.imwrite(str(image_path), image)
            assert cv2.imwrite(str(mask_path), mask)
            rows.append(
                {
                    "case_id": f"case-{index}",
                    "image_path": image_path.relative_to(root).as_posix(),
                    "mask_path": mask_path.relative_to(root).as_posix(),
                    "is_empty_mask": is_empty,
                    "patient_id": f"synthetic-{index}",
                    "status": "EMPTY_MASK_CONTROL" if is_empty else "VALID_LESION_MASK",
                }
            )
    return pd.DataFrame(rows)


def test_image_level_split_ignores_and_removes_patient_ids(tmp_path):
    data = _metadata(tmp_path)
    validated, evidence = prepare_splits.validate_image_split_metadata(data, root=tmp_path)

    assert "patient_id" not in validated
    assert evidence["patient_identity_used"] is False
    assert evidence["patient_level_independence_verified"] is False
    assert validated["image_sha256"].is_unique

    split, split_evidence = prepare_splits.create_image_level_splits(validated, seed=17)
    assert set(split["split"]) == {"TRAIN", "VAL", "TEST"}
    assert sum(split_evidence["split_counts"].values()) == len(data)
    for counts in split_evidence["mask_presence_counts"].values():
        assert counts["empty_mask"] > 0
        assert counts["lesion_mask"] > 0


def test_image_split_rejects_duplicate_content(tmp_path):
    data = _metadata(tmp_path)
    data.loc[1, "image_path"] = data.loc[0, "image_path"]

    with pytest.raises(ValueError, match="Duplicate image content"):
        prepare_splits.validate_image_split_metadata(data, root=tmp_path)


def test_image_split_rejects_misaligned_image_and_mask(tmp_path):
    data = _metadata(tmp_path)
    first_mask = tmp_path / data.loc[0, "mask_path"]
    assert cv2.imwrite(str(first_mask), np.zeros((16, 20), dtype=np.uint8))

    with pytest.raises(ValueError, match="dimensions differ"):
        prepare_splits.validate_image_split_metadata(data, root=tmp_path)


def test_image_split_builder_writes_three_partitions_and_never_patient_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_splits, "ROOT", tmp_path)
    source_csv = tmp_path / "ground_truth.csv"
    _metadata(tmp_path).to_csv(source_csv, index=False)
    output_dir = tmp_path / "splits"

    manifest = prepare_splits.main(source_csv, output_dir, seed=42)

    assert manifest["split_level"] == "image-level"
    assert manifest["patient_level_independence_verified"] is False
    for split in ("train", "val", "test"):
        csv_path = output_dir / f"{split}.csv"
        frame = pd.read_csv(csv_path)
        assert not frame.empty
        assert "patient_id" not in frame
    saved_manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert saved_manifest["test_partition_used_for_training_or_selection"] is False


def test_create_image_level_splits_requires_valid_fractions(tmp_path):
    data = _metadata(tmp_path)
    validated, _ = prepare_splits.validate_image_split_metadata(data, root=tmp_path)

    with pytest.raises(ValueError, match="sum to less than 1"):
        prepare_splits.create_image_level_splits(validated, val_fraction=0.5, test_fraction=0.5)
