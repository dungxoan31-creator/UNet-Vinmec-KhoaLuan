"""Materialize declared M1 empty controls without treating them as clinical ground truth."""

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SPLITS = ("train", "val", "test")
EMPTY_DIR = Path("dataset/vinmec_ovarian/empty_masks")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _native_mask(root: Path, image_path: str) -> Path:
    image = Path(image_path)
    if "/Vinmec_CEUS/image/" in f"/{image_path}":
        folder = "dataset/Vinmec_CEUS/label"
    elif "/Vinmec_2D/train/train_image/" in f"/{image_path}":
        folder = "dataset/Vinmec_2D/train/train_label/label"
    elif "/Vinmec_2D/test/image/" in f"/{image_path}":
        folder = "dataset/Vinmec_2D/test/label/black_write"
    else:
        raise ValueError(f"Unknown source image layout: {image_path}")
    return root / folder / f"{image.stem}.PNG"


def _read_both(path: Path) -> np.ndarray:
    image_cv = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image_cv is None:
        raise ValueError(f"OpenCV cannot read {path}")
    with Image.open(path) as image_pil:
        image_pil.load()
        if image_pil.size != (image_cv.shape[1], image_cv.shape[0]):
            raise ValueError(f"PIL/OpenCV dimensions differ: {path}")
    return image_cv


def generate_empty_masks(root: Path, expected_count: int = 35) -> dict:
    root = root.resolve()
    rows = [
        row
        for split in SPLITS
        for row in _read_rows(root / "ai_training/splits" / f"{split}.csv")
    ]
    empty = [row for row in rows if row["is_empty_mask"].lower() == "true"]
    if len(empty) != expected_count:
        raise ValueError(f"Expected {expected_count} declared empty records; found {len(empty)}")

    expected_dir = (root / EMPTY_DIR).resolve()
    targets = [
        (root / row["mask_path"].replace("\\", "/")).resolve()
        for row in empty
    ]
    if len(set(targets)) != len(targets) or any(path.parent != expected_dir for path in targets):
        raise ValueError("Empty mask paths must be distinct and inside the declared control directory")

    # Check source images and any existing targets before writing a file.
    for row, target in zip(empty, targets, strict=True):
        _read_both(root / row["image_path"])
        if target.exists():
            mask = _read_both(target)
            if mask.shape != (512, 512) or mask.dtype != np.uint8 or np.any(mask):
                raise ValueError(f"Existing control mask is not a 512x512 zero image: {target}")

    expected_dir.mkdir(parents=True, exist_ok=True)
    zero_png = cv2.imencode(".png", np.zeros((512, 512), dtype=np.uint8))[1].tobytes()
    created = 0
    records = []
    for row, target in zip(empty, targets, strict=True):
        if not target.exists():
            target.write_bytes(zero_png)
            created += 1
        mask = _read_both(target)
        if mask.shape != (512, 512) or mask.dtype != np.uint8 or np.any(mask):
            raise ValueError(f"Written control mask failed validation: {target}")
        native_path = _native_mask(root, row["image_path"])
        native = cv2.imread(str(native_path), cv2.IMREAD_GRAYSCALE)
        records.append({
            "case_id": row["case_id"],
            "split": row["split"],
            "image_path": row["image_path"],
            "mask_path": row["mask_path"],
            "mask_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "source_mask_path": str(native_path.relative_to(root)).replace("\\", "/"),
            "source_mask_positive_pixels": None if native is None else int(np.count_nonzero(native)),
        })

    verified_pairs = 0
    for row in rows:
        _read_both(root / row["image_path"])
        _read_both(root / row["mask_path"])
        verified_pairs += 1

    summary = {
        "source_split_csvs": [f"ai_training/splits/{split}.csv" for split in SPLITS],
        "split_counts": {split: sum(row["split"].lower() == split for row in rows) for split in SPLITS},
        "record_count": len(empty),
        "files_created": created,
        "verified_image_mask_pairs": verified_pairs,
        "mask_shape": [512, 512],
        "mask_dtype": "uint8",
        "mask_pixel_values": [0],
        "provenance": "derived_zero_mask_for_pipeline_compatibility",
        "clinical_negative_verified": False,
        "source_positive_count": sum(
            record["source_mask_positive_pixels"] is not None
            and record["source_mask_positive_pixels"] > 0
            for record in records
        ),
        "records": records,
    }
    (expected_dir / "PROVENANCE.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    result = generate_empty_masks(project_root)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
