"""Stream statistics for the canonical image-level segmentation manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.dataset_paths import resolve_dataset_path


def audit(root: Path, manifest: Path) -> dict:
    rows = list(csv.DictReader(manifest.open(encoding="utf-8-sig", newline="")))
    split_counts = Counter(row.get("split", "") for row in rows)
    extensions = Counter(Path(row["image_path"]).suffix.lower() for row in rows)
    image_shapes = Counter()
    mask_shapes = Counter()
    mask_values: set[int] = set()
    image_min, image_max = 255, 0
    mask_min, mask_max = 255, 0
    missing_patient_ids = 0
    errors = []

    for row in rows:
        sid = row.get("sample_id") or row.get("case_id") or "(unknown)"
        image_path = resolve_dataset_path(root, row["image_path"])
        mask_path = resolve_dataset_path(root, row["mask_path"])
        image = cv2.imdecode(np.frombuffer(image_path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE) if image_path.is_file() else None
        mask = cv2.imdecode(np.frombuffer(mask_path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE) if mask_path.is_file() else None

        if image is None or mask is None:
            errors.append({"sample_id": sid, "error": "missing_or_unreadable_pair"})
            continue
        image_shapes[f"{image.shape[1]}x{image.shape[0]}"] += 1
        mask_shapes[f"{mask.shape[1]}x{mask.shape[0]}"] += 1
        if image.shape != mask.shape:
            errors.append({"sample_id": sid, "error": f"shape_mismatch:{image.shape}:{mask.shape}"})
        image_min = min(image_min, int(image.min()))
        image_max = max(image_max, int(image.max()))
        mask_min = min(mask_min, int(mask.min()))
        mask_max = max(mask_max, int(mask.max()))
        mask_values.update(int(value) for value in np.unique(mask))
        missing_patient_ids += not bool((row.get("patient_id") or "").strip())

    return {
        "manifest": manifest.resolve().as_posix(),
        "sample_count": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "image_extensions": dict(sorted(extensions.items())),
        "image_shape_unique_count": len(image_shapes),
        "image_shapes_wh_most_common_10": dict(image_shapes.most_common(10)),
        "mask_shape_unique_count": len(mask_shapes),
        "mask_shapes_wh_most_common_10": dict(mask_shapes.most_common(10)),
        "image_grayscale_raw_min_max": [image_min, image_max] if rows else None,
        "mask_grayscale_raw_min_max": [mask_min, mask_max] if rows else None,
        "mask_grayscale_raw_unique_values": sorted(mask_values),
        "patient_id_missing_count": missing_patient_ids,
        "pair_errors": errors,
        "status": "READY_IMAGE_LEVEL_ONLY" if not errors else "FAILED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06/all_samples.csv"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    result = audit(root, manifest)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] == "FAILED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
