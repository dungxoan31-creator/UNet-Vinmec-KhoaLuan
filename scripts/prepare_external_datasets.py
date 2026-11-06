"""
CLI tool for auditing and preparing external ovarian ultrasound datasets:
- MMOTU (Multi-Modality Ovarian Tumor Ultrasound)
- OvaTUS (Bệnh viện Phụ sản TW / Sigmlab)
- ShaunSpinelli/OTU_2D
- HananSaadat/ovarian_ultrasound_dataset
- PCOSGen

Records available image-level labels and does not infer patient identity or O-RADS from dataset names.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ai_training.external_dataset_adapters import SUPPORTED_EXTERNAL_DATASETS  # noqa: E402
from ai_training.mmotu_label_schema import MMOTU_8_CLASSES  # noqa: E402


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_global_category_labels(labels_files: Path | list[Path] | None) -> dict[str, dict[str, Any]]:
    if labels_files is None:
        return {}
    if isinstance(labels_files, (str, Path)):
        labels_files = [Path(labels_files)]
    labels: dict[str, dict[str, Any]] = {}
    for labels_path in labels_files:
        labels_path = Path(labels_path)
        if not labels_path.is_file():
            raise FileNotFoundError(f"Global category label file not found: {labels_path}")
        for line_number, line in enumerate(labels_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            fields = line.strip().split()
            if not fields or fields[0].startswith("#"):
                continue
            if len(fields) != 2:
                raise ValueError(f"Expected '<filename> <class_id>' at {labels_path}:{line_number}")
            filename, raw_class_id = fields
            if Path(filename).name != filename:
                raise ValueError(f"Label filename must be a simple file name at {labels_path}:{line_number}")
            try:
                class_id = int(raw_class_id)
            except ValueError as exc:
                raise ValueError(f"Invalid class ID at {labels_path}:{line_number}: {raw_class_id}") from exc
            if not 0 <= class_id < len(MMOTU_8_CLASSES):
                raise ValueError(f"MMOTU class ID out of range at {labels_path}:{line_number}: {class_id}")
            key = filename.casefold()
            if key in labels:
                raise ValueError(f"Duplicate global category label for {filename}")
            labels[key] = {
                "global_category_id": class_id,
                "global_category": MMOTU_8_CLASSES[class_id],
                "global_category_label_file": labels_path.name,
            }
    return labels


def scan_external_dataset_directory(
    dataset_key: str,
    images_dir: Path,
    masks_dir: Path = None,
    labels_csv: Path | list[Path] = None,
    output_manifest_path: Path = None,
) -> dict:
    if dataset_key not in SUPPORTED_EXTERNAL_DATASETS:
        raise ValueError(f"Unknown dataset_key: {dataset_key}. Supported: {list(SUPPORTED_EXTERNAL_DATASETS.keys())}")

    config = SUPPORTED_EXTERNAL_DATASETS[dataset_key]
    labels_by_name = load_global_category_labels(labels_csv)
    if labels_by_name and dataset_key != "mmotu":
        raise ValueError("The configured global category label schema is specific to MMOTU")
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    image_files = sorted([f for f in images_dir.glob("**/*") if f.suffix.lower() in valid_extensions])
    print(f"[{config.name}] Discovered {len(image_files)} image files in {images_dir}")

    mask_index = {}
    if masks_dir and config.has_pixel_masks:
        for candidate in masks_dir.glob("**/*"):
            if candidate.is_file() and candidate.suffix.lower() in valid_extensions:
                key = candidate.name.casefold()
                if key in mask_index:
                    raise ValueError(f"Case-insensitive duplicate mask filename: {candidate.name}")
                mask_index[key] = candidate

    records: list[dict] = []
    skipped_corrupted = 0

    for img_path in image_files:
        # Verify decodability
        try:
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                skipped_corrupted += 1
                continue
            h, w = img.shape[:2]
        except Exception:
            skipped_corrupted += 1
            continue

        sample_id = img_path.stem
        mask_path_str = None

        if masks_dir and config.has_pixel_masks:
            # Prefer an explicitly binary mask when a source provides both
            # semantic-color and binarized variants (as local MMOTU does).
            candidate_mask = next(
                (
                    mask_index[name.casefold()]
                    for name in (
                        f"{sample_id}_binary.png",
                        f"{sample_id}_binary.jpg",
                        f"{sample_id}.png",
                        f"{sample_id}.jpg",
                        f"{sample_id}.tif",
                        f"{sample_id}.tiff",
                    )
                    if name.casefold() in mask_index
                ),
                None,
            )
            if candidate_mask is not None:
                mask_path_str = str(candidate_mask.resolve())

        record = {
            "sample_id": sample_id,
            "image_path": str(img_path.resolve()),
            "mask_path": mask_path_str,
            "original_width": w,
            "original_height": h,
            "dataset_name": config.name,
            "modality": config.modality,
            "clinical_category": config.clinical_focus.value,
            "default_orads_tier": config.default_orads_tier,
        }
        global_label = labels_by_name.get(img_path.name.casefold())
        if labels_by_name and global_label is None:
            raise ValueError(f"No global category label found for MMOTU image: {img_path.name}")
        if global_label:
            record.update(global_label)
        records.append(record)

    if labels_by_name:
        image_names = {path.name.casefold() for path in image_files}
        unknown_labels = sorted(set(labels_by_name) - image_names)
        if unknown_labels:
            raise ValueError(f"Global category labels reference images that were not scanned: {unknown_labels[:5]}")

    summary = {
        "dataset_key": dataset_key,
        "dataset_name": config.name,
        "citation": config.citation_source,
        "total_valid_samples": len(records),
        "skipped_corrupted": skipped_corrupted,
        "has_pixel_masks": config.has_pixel_masks,
        "clinical_category": config.clinical_focus.value,
        "samples": records,
    }
    if labels_by_name:
        summary["label_type"] = "image-level global category annotation"
        summary["class_id_to_name"] = {str(index): name for index, name in enumerate(MMOTU_8_CLASSES)}
        summary["global_category_counts"] = {
            name: sum(record.get("global_category") == name for record in records)
            for name in MMOTU_8_CLASSES
        }
        summary["patient_identity_available"] = False
        summary["patient_level_independence_verified"] = False
        summary["split_level"] = "image-level"

    if output_manifest_path:
        output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        output_manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[{config.name}] Manifest saved to: {output_manifest_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Prepare and register external ovarian ultrasound datasets.")
    parser.add_argument("--dataset", required=True, choices=list(SUPPORTED_EXTERNAL_DATASETS.keys()), help="Dataset identifier")
    parser.add_argument("--images-dir", required=True, type=Path, help="Directory containing ultrasound images")
    parser.add_argument("--masks-dir", type=Path, default=None, help="Directory containing segmentation masks (if available)")
    parser.add_argument(
        "--labels-file",
        dest="labels_files",
        type=Path,
        action="append",
        default=None,
        help="Optional MMOTU '<filename> <class_id>' label file; may be provided more than once",
    )
    parser.add_argument("--output-manifest", type=Path, default=None, help="Path to write output manifest JSON")

    args = parser.parse_args()
    summary = scan_external_dataset_directory(
        dataset_key=args.dataset,
        images_dir=args.images_dir,
        masks_dir=args.masks_dir,
        labels_csv=args.labels_files,
        output_manifest_path=args.output_manifest,
    )
    print(f"Successfully processed {summary['total_valid_samples']} samples for {summary['dataset_name']}.")


if __name__ == "__main__":
    main()
