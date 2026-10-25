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
    assert set(sample["mask"].unique().tolist()) <= {0.0, 1.0}
    mask.unlink()
    with pytest.raises(FileNotFoundError, match="Mask not found"):
        OvarianUltrasoundDataset(manifest)[0]


def test_dataset_rejects_image_mask_dimension_mismatch(tmp_path):
    _pair(tmp_path, "train", "1")
    manifest = tmp_path / "pairs.csv"
    image = tmp_path / "train" / "train_image" / "1.JPG"
    mask = tmp_path / "train" / "train_label" / "label" / "1.PNG"
    assert cv2.imwrite(str(mask), np.zeros((16, 20), dtype=np.uint8))
    manifest.write_text(f"case_id,image_path,mask_path\n1,{image},{mask}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)image/mask dimensions differ"):
        OvarianUltrasoundDataset(manifest)[0]


def test_dataset_rejects_nonbinary_source_mask_values(tmp_path):
    _pair(tmp_path, "train", "1")
    manifest = tmp_path / "pairs.csv"
    image = tmp_path / "train" / "train_image" / "1.JPG"
    mask = tmp_path / "train" / "train_label" / "label" / "1.PNG"
    assert cv2.imwrite(str(mask), np.full((32, 40), 42, dtype=np.uint8))
    manifest.write_text(f"case_id,image_path,mask_path\n1,{image},{mask}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)non-binary source values"):
        OvarianUltrasoundDataset(manifest)[0]


def test_dataset_reader_rejects_oversized_raster_before_opencv_decode(tmp_path, monkeypatch):
    from PIL import Image

    import ai_training.dataset_loader as dataset_loader

    path = tmp_path / "oversized.png"
    path.write_bytes(b"header only")

    class ImageHeader:
        size = (5001, 5000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(Image, "open", lambda _path: ImageHeader())
    monkeypatch.setattr(
        dataset_loader.cv2,
        "imdecode",
        lambda *_args: pytest.fail("Oversized raster reached OpenCV decode"),
    )

    with pytest.raises(ValueError, match="(?i)decoded image exceeds the pixel limit"):
        dataset_loader.cv2_imread_unicode(str(path))


def test_dataset_reader_checks_decoded_size_against_the_header(tmp_path, monkeypatch):
    from PIL import Image

    import ai_training.dataset_loader as dataset_loader

    path = tmp_path / "header-mismatch.png"
    path.write_bytes(b"fixture")

    class ImageHeader:
        size = (32, 24)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class DecodedImage:
        ndim = 2
        shape = (5000, 5001)

    monkeypatch.setattr(Image, "open", lambda _path: ImageHeader())
    monkeypatch.setattr(dataset_loader.cv2, "imdecode", lambda *_args: DecodedImage())

    with pytest.raises(ValueError, match="(?i)decoded image exceeds the pixel limit"):
        dataset_loader.cv2_imread_unicode(str(path))
