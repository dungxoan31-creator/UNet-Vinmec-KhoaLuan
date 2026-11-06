"""Create verified image-level splits for the local MMOTU OTU_2d masks.

The upstream classification lists define the official train/validation boundary.
This utility uses those lists only to select segmentation pairs; it does not
interpret global classes as pathology, patient identity, or clinical risk.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_training.dataset_loader import cv2_imread_unicode
from scripts.prepare_external_datasets import load_global_category_labels


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_index(directory: Path, suffix: str) -> dict[str, Path]:
    files = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == suffix]
    index: dict[str, Path] = {}
    for path in files:
        key = path.name.casefold()
        if key in index:
            raise ValueError(f"Case-insensitive duplicate filename in {directory}: {path.name}")
        index[key] = path
    return index


def _mask_for_image(image: Path, masks: dict[str, Path]) -> Path:
    binary = masks.get(f"{image.stem}_binary.png".casefold())
    canonical = masks.get(f"{image.stem}.png".casefold())
    mask = binary or canonical
    if mask is None:
        raise FileNotFoundError(f"No mask found for {image.name}")

    mask_pixels = cv2_imread_unicode(str(mask), cv2.IMREAD_GRAYSCALE)
    if mask_pixels is None:
        raise ValueError(f"Unable to decode mask: {mask}")
    values = set(np.unique(mask_pixels).tolist())
    if values.issubset({0, 1}):
        pass
    elif values.issubset({0, 255}):
        pass
    else:
        raise ValueError(
            f"Mask is not binary ({sorted(values)[:12]}): {mask}. "
            "Use a verified *_binary.PNG mask; do not silently collapse labels."
        )

    if binary is not None and canonical is not None:
        canonical_pixels = cv2_imread_unicode(str(canonical), cv2.IMREAD_GRAYSCALE)
        if canonical_pixels is None:
            raise ValueError(f"Unable to decode canonical mask: {canonical}")
        if canonical_pixels.shape != mask_pixels.shape or not np.array_equal(
            canonical_pixels > 0, mask_pixels > 0
        ):
            raise ValueError(f"Binary and canonical masks disagree for {image.name}")
    return mask


def build_splits(
    images_dir: Path,
    masks_dir: Path,
    train_labels: Path,
    val_labels: Path,
    output_dir: Path,
) -> dict:
    images_dir = images_dir.resolve()
    masks_dir = masks_dir.resolve()
    train_labels = train_labels.resolve()
    val_labels = val_labels.resolve()
    output_dir = output_dir.resolve()
    images = _file_index(images_dir, ".jpg")
    if not images:
        raise ValueError(f"No JPG images found in {images_dir}")
    masks = _file_index(masks_dir, ".png")
    train = load_global_category_labels(train_labels)
    val = load_global_category_labels(val_labels)
    if set(train) & set(val):
        raise ValueError("Official MMOTU train and validation label files overlap")
    if (set(train) | set(val)) != set(images):
        missing = sorted((set(train) | set(val)) - set(images))
        unassigned = sorted(set(images) - (set(train) | set(val)))
        raise ValueError(
            f"Official label/image inventory mismatch: missing_images={missing[:5]}, "
            f"unassigned_images={unassigned[:5]}"
        )

    split_records: dict[str, list[dict]] = {"train": [], "val": []}
    hashes_by_split: dict[str, set[str]] = {"train": set(), "val": set()}
    for split, label_map in (("train", train), ("val", val)):
        for image_key in sorted(label_map):
            image = images[image_key]
            mask = _mask_for_image(image, masks)
            image_pixels = cv2_imread_unicode(str(image), cv2.IMREAD_GRAYSCALE)
            mask_pixels = cv2_imread_unicode(str(mask), cv2.IMREAD_GRAYSCALE)
            if image_pixels is None or mask_pixels is None:
                raise ValueError(f"Unreadable image/mask pair: {image.name}")
            if image_pixels.ndim != 2 or mask_pixels.ndim != 2 or image_pixels.shape != mask_pixels.shape:
                raise ValueError(
                    f"Image/mask geometry mismatch for {image.name}: "
                    f"image={image_pixels.shape}, mask={mask_pixels.shape}"
                )
            image_hash = sha256_file(image)
            if image_hash in hashes_by_split[split]:
                raise ValueError(f"Duplicate image content inside {split}: {image.name}")
            hashes_by_split[split].add(image_hash)
            label = label_map[image_key]
            split_records[split].append(
                {
                    "case_id": f"mmotu_2d_{image.stem}",
                    "image_path": image.relative_to(ROOT).as_posix(),
                    "mask_path": mask.relative_to(ROOT).as_posix(),
                    "image_sha256": image_hash,
                    "mask_sha256": sha256_file(mask),
                    "dataset": "MMOTU OTU_2d",
                    "global_category_id": label["global_category_id"],
                    "global_category": label["global_category"],
                }
            )

    overlap = hashes_by_split["train"] & hashes_by_split["val"]
    if overlap:
        raise ValueError(f"SHA-256 image overlap between official train and validation: {len(overlap)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for split, records in split_records.items():
        with (output_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    manifest = {
        "dataset": "MMOTU OTU_2d",
        "task": "binary pixel-mask segmentation",
        "source_label_type": "image-level global category; not used as a diagnosis",
        "split_level": "image-level",
        "patient_identity_available": False,
        "patient_level_independence_verified": False,
        "split_policy": "official upstream train_cls.txt and val_cls.txt lists",
        "split_counts": {key: len(records) for key, records in split_records.items()},
        "source_label_files": {
            "train": {"path": train_labels.relative_to(ROOT).as_posix(), "sha256": sha256_file(train_labels)},
            "val": {"path": val_labels.relative_to(ROOT).as_posix(), "sha256": sha256_file(val_labels)},
        },
        "mask_policy": "prefer *_binary.PNG; where both variants exist, require exact binary-equivalence",
        "image_sha256_cross_split_overlap": 0,
        "test_split_available": False,
        "vinmec_data_used": False,
        "dataset_terms": "Upstream code license does not establish image/mask dataset redistribution rights.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=ROOT / "dataset/2d/images")
    parser.add_argument("--masks-dir", type=Path, default=ROOT / "dataset/2d/masks")
    parser.add_argument("--train-labels", type=Path, default=ROOT / "metadata/mmotu_2d_train_cls.txt")
    parser.add_argument("--val-labels", type=Path, default=ROOT / "metadata/mmotu_2d_val_cls.txt")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "ai_training/splits/mmotu_2d_official_2026-10-27"
    )
    args = parser.parse_args()
    manifest = build_splits(args.images_dir, args.masks_dir, args.train_labels, args.val_labels, args.output_dir)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
