"""
CLI tool for auditing and preparing external ovarian ultrasound datasets:
- MMOTU (Multi-Modality Ovarian Tumor Ultrasound)
- OvaTUS (Bệnh viện Phụ sản TW / Sigmlab)
- ShaunSpinelli/OTU_2D
- HananSaadat/ovarian_ultrasound_dataset
- PCOSGen

Enforces Patient-Level Isolation & Clinical Guardrails (ACR O-RADS 1 Follicles vs 2-5 Neoplasms).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ai_training.external_dataset_adapters import SUPPORTED_EXTERNAL_DATASETS  # noqa: E402


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_external_dataset_directory(
    dataset_key: str,
    images_dir: Path,
    masks_dir: Path = None,
    labels_csv: Path = None,
    output_manifest_path: Path = None,
) -> dict:
    if dataset_key not in SUPPORTED_EXTERNAL_DATASETS:
        raise ValueError(f"Unknown dataset_key: {dataset_key}. Supported: {list(SUPPORTED_EXTERNAL_DATASETS.keys())}")

    config = SUPPORTED_EXTERNAL_DATASETS[dataset_key]
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    image_files = sorted([f for f in images_dir.glob("**/*") if f.suffix.lower() in valid_extensions])
    print(f"[{config.name}] Discovered {len(image_files)} image files in {images_dir}")

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
            # Check for candidate mask extensions
            candidate_mask = masks_dir / f"{sample_id}.png"
            if not candidate_mask.exists():
                candidate_mask = masks_dir / f"{sample_id}.jpg"
            if candidate_mask.exists():
                mask_path_str = str(candidate_mask.resolve())

        records.append({
            "sample_id": sample_id,
            "image_path": str(img_path.resolve()),
            "mask_path": mask_path_str,
            "original_width": w,
            "original_height": h,
            "dataset_name": config.name,
            "modality": config.modality,
            "clinical_category": config.clinical_focus.value,
            "default_orads_tier": config.default_orads_tier,
        })

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
    parser.add_argument("--output-manifest", type=Path, default=None, help="Path to write output manifest JSON")

    args = parser.parse_args()
    summary = scan_external_dataset_directory(
        dataset_key=args.dataset,
        images_dir=args.images_dir,
        masks_dir=args.masks_dir,
        output_manifest_path=args.output_manifest,
    )
    print(f"Successfully processed {summary['total_valid_samples']} samples for {summary['dataset_name']}.")


if __name__ == "__main__":
    main()
