"""Audit local Vinmec_2D pairs and make reproducible image-level splits."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

import cv2
import numpy as np


def _pairs(image_dir: Path, mask_dir: Path) -> list[dict[str, str]]:
    images = {p.stem: p for p in image_dir.glob("*.JPG")}
    masks = {p.stem: p for p in mask_dir.glob("*.PNG")}
    if not images or images.keys() != masks.keys():
        raise ValueError(f"Image/mask stems differ: {image_dir} ({len(images)}), {mask_dir} ({len(masks)})")
    rows = []
    for stem in sorted(images):
        image = cv2.imread(str(images[stem]), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(masks[stem]), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None or image.shape != mask.shape:
            raise ValueError(f"Unreadable or shape-mismatched pair: {stem}")
        if not set(np.unique(mask)).issubset({0, 255}):
            raise ValueError(f"Non-binary mask: {masks[stem]}")
        rows.append({
            "case_id": stem,
            "image_path": images[stem].as_posix(),
            "mask_path": masks[stem].as_posix(),
            "patient_id": "",
            "image_sha256": hashlib.sha256(image.shape.__repr__().encode() + image.tobytes()).hexdigest(),
        })
    return rows


def prepare_splits(data_dir: Path, output_dir: Path, val_fraction: float = 0.15, seed: int = 42) -> dict:
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between zero and one")
    train_pool = _pairs(data_dir / "train/train_image", data_dir / "train/train_label/label")
    test = _pairs(data_dir / "test/image", data_dir / "test/label/black_write")
    hashes = [r["image_sha256"] for r in train_pool + test]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Exact duplicate image across the source train/test pool")
    rng = random.Random(seed)
    rng.shuffle(train_pool)
    n_val = max(1, round(len(train_pool) * val_fraction))
    val, train = train_pool[:n_val], train_pool[n_val:]
    if not train:
        raise ValueError("No training images remain")
    output_dir.mkdir(parents=True, exist_ok=True)
    for split, rows in (("train", train), ("val", val), ("test", test)):
        with (output_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "source": str(data_dir), "seed": seed, "val_fraction": val_fraction,
        "counts": {"train": len(train), "val": len(val), "test": len(test)},
        "split_level": "image",
        "patient_id_status": "Unavailable in local files; patient-level separation cannot be verified",
        "patient_split_status": "unverified; source patient IDs unavailable",
        "patient_id_format_required": "^[1-9][0-9]{8}$",
        "records_with_patient_id": {"train": 0, "val": 0, "test": 0},
        "unique_patients_per_split": {"train": None, "val": None, "test": None},
        "source_test_preserved": True,
        "exact_decoded_image_duplicates": 0,
    }
    (output_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("dataset/Vinmec_2D"))
    parser.add_argument("--output-dir", type=Path, default=Path("ai_training/splits/vinmec_2d"))
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(prepare_splits(args.data_dir, args.output_dir, args.val_fraction, args.seed), indent=2))
