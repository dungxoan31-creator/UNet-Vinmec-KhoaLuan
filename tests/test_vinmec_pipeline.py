import csv
from pathlib import Path

import cv2
import numpy as np
import pytest

from ai_training.dataset_loader import OvarianUltrasoundDataset
from scripts.prepare_vinmec import prepare_splits


def _pair(root: Path, group: str, stem: str, value: int = 255) -> None:
    image_dir = root / group / ("train_image" if group == "train" else "image")
    mask_dir = root / group / ("train_label/label" if group == "train" else "label/black_write")
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    image = np.full((32, 40), int(stem) + 80, dtype=np.uint8)
    mask = np.zeros_like(image)
    mask[5:20, 7:25] = value
    assert cv2.imwrite(str(image_dir / f"{stem}.JPG"), image)
    assert cv2.imwrite(str(mask_dir / f"{stem}.PNG"), mask)


def test_prepare_splits_preserves_source_test_and_declares_unknown_patient_ids(tmp_path):
    for i in range(10):
        _pair(tmp_path, "train", str(i))
    for i in range(3):
        _pair(tmp_path, "test", str(i + 10))
    output = tmp_path / "splits"
    prepare_splits(tmp_path, output, val_fraction=0.2, seed=42)
    rows = {}
    for name in ("train", "val", "test"):
        with (output / f"{name}.csv").open(newline="", encoding="utf-8") as stream:
            rows[name] = list(csv.DictReader(stream))
    assert [len(rows[name]) for name in ("train", "val", "test")] == [8, 2, 3]
    assert {r["case_id"] for r in rows["test"]} == {"10", "11", "12"}
    assert all(not r["patient_id"] for group in rows.values() for r in group)
    assert len({r["image_path"] for group in rows.values() for r in group}) == 13


def test_dataset_preserves_binary_zero_one_mask_and_rejects_missing_mask(tmp_path):
    _pair(tmp_path, "train", "1", value=1)
    manifest = tmp_path / "pairs.csv"
    image = tmp_path / "train" / "train_image" / "1.JPG"
    mask = tmp_path / "train" / "train_label" / "label" / "1.PNG"
    manifest.write_text(f"case_id,image_path,mask_path\n1,{image},{mask}\n", encoding="utf-8")
    sample = OvarianUltrasoundDataset(manifest)[0]
    assert sample["mask"].sum().item() > 0
    mask.unlink()
    with pytest.raises(FileNotFoundError, match="Mask not found"):
        OvarianUltrasoundDataset(manifest)[0]
