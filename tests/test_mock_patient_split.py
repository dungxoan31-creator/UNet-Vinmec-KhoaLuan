import csv
import json

import cv2
import numpy as np

from scripts.prepare_mock_patient_split import prepare_mock_splits


def _pair(root, split, case_number, has_lesion=True):
    image_dir = root / split / ("train_image" if split == "train" else "image")
    mask_dir = root / split / ("train_label/label" if split == "train" else "label/black_write")
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    image = np.full((32, 40), case_number + 80, dtype=np.uint8)
    mask = np.zeros_like(image)
    if has_lesion:
        mask[5:20, 7:25] = 255
    assert cv2.imwrite(str(image_dir / f"{case_number}.JPG"), image)
    assert cv2.imwrite(str(mask_dir / f"{case_number}.PNG"), mask)


def test_mock_groups_are_disjoint_and_explicitly_synthetic(tmp_path):
    for case_number in range(30):
        _pair(tmp_path, "train", case_number, has_lesion=case_number != 0)
    for case_number in range(30, 40):
        _pair(tmp_path, "test", case_number)

    output = tmp_path / "mock_splits"
    summary = prepare_mock_splits(tmp_path, output, val_fraction=0.2, seed=42)
    rows = {}
    for split in ("train", "val", "test"):
        with (output / f"{split}.csv").open(newline="", encoding="utf-8") as stream:
            rows[split] = list(csv.DictReader(stream))

    assert len(rows["train"]) + len(rows["val"]) == 30
    assert len(rows["test"]) == 10
    assert {row["case_id"] for row in rows["test"]} == {str(case_number) for case_number in range(30, 40)}
    groups = [{row["patient_id"] for row in rows[split]} for split in ("train", "val", "test")]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
    assert all(row["patient_id"].startswith("SIM-") for split in rows.values() for row in split)
    group_sizes = {}
    for split in rows.values():
        for row in split:
            group_sizes[row["patient_id"]] = group_sizes.get(row["patient_id"], 0) + 1
    assert len(set(group_sizes.values())) > 1
    assert max(group_sizes.values()) <= 4
    with (output / "synthetic_patient_mapping.csv").open(newline="", encoding="utf-8") as stream:
        mapping_reader = csv.DictReader(stream)
        assert mapping_reader.fieldnames == ["image_id", "patient_id", "label"]
        mapping = list(mapping_reader)
    assert len(mapping) == 40
    assert {row["image_id"] for row in mapping} == {str(case_number) for case_number in range(40)}
    assert {row["image_id"]: row["label"] for row in mapping}["0"] == "0"
    assert all(row["label"] == "1" for row in mapping if row["image_id"] != "0")
    assert {row["image_id"]: row["patient_id"] for row in mapping} == {
        row["case_id"]: row["patient_id"] for split in rows.values() for row in split
    }
    assert summary["split_level"] == "synthetic_group_demo"
    assert summary["patient_ids_verified"] is False
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == summary
