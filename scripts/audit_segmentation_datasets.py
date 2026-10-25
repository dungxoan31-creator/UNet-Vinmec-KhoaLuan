"""Build sample-ID-based image/annotation audits for the local ultrasound datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

DATASETS = {
    "Vinmec_2D": ("dataset/Vinmec/Vinmec_2d/images", "dataset/Vinmec/Vinmec_2d/annotations", True),
    "Vinmec_CEUS": ("dataset/Vinmec/Vinmec_3d/images", "dataset/Vinmec/Vinmec_3d/annotations", True),
    "Vinmec_2D_train": ("dataset/Vinmec_2D/train/train_image", "dataset/Vinmec_2D/train/train_label/label", False),
    "Vinmec_2D_test": ("dataset/Vinmec_2D/test/image", "dataset/Vinmec_2D/test/label/black_write", False),
    "Vinmec_CEUS_subset": ("dataset/Vinmec_CEUS/image", "dataset/Vinmec_CEUS/label", False),
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
ANNOTATION_EXTENSIONS = {".png", ".bmp", ".tif", ".tiff"}
NUMBER = re.compile(r"(\d+)(?:_[^/]*)?$")


def sample_id(path: Path) -> str | None:
    match = NUMBER.search(path.stem)
    return str(int(match.group(1))) if match else None


def read_image(path: Path, flags: int) -> np.ndarray | None:
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
    except (OSError, cv2.error):
        return None


def binary_signature(mask: np.ndarray) -> tuple[tuple[int, ...], str]:
    foreground = np.any(mask != 0, axis=2) if mask.ndim == 3 else mask != 0
    binary = foreground.astype(np.uint8)
    return binary.shape, hashlib.sha256(binary.tobytes()).hexdigest()


def mask_is_binary(mask: np.ndarray) -> bool:
    if mask.ndim == 2:
        colors = np.unique(mask)
        return len(colors) <= 2
    if mask.ndim == 3 and mask.shape[2] in (3, 4):
        foreground = np.any(mask != 0, axis=2)
        if not np.any(foreground):
            return True
        color = mask[foreground][0]
        return bool(np.all(np.all(mask[foreground] == color, axis=1)))
    return False


def audit_dataset(root: Path, name: str, image_rel: str, annotation_rel: str, allow_equivalent_variants: bool):
    image_dir, annotation_dir = root / image_rel, root / annotation_rel
    images: dict[str, list[Path]] = defaultdict(list)
    annotations: dict[str, list[Path]] = defaultdict(list)
    issues: list[dict[str, str]] = []

    for path in image_dir.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            sid = sample_id(path)
            if sid is None:
                issues.append({"dataset": name, "sample_id": "", "files": path.relative_to(root).as_posix(), "reason": "image filename has no numeric sample_id"})
            else:
                images[sid].append(path)
    for path in annotation_dir.iterdir():
        if path.is_file() and path.suffix.lower() in ANNOTATION_EXTENSIONS:
            sid = sample_id(path)
            if sid is None:
                issues.append({"dataset": name, "sample_id": "", "files": path.relative_to(root).as_posix(), "reason": "annotation filename has no numeric sample_id"})
            else:
                annotations[sid].append(path)

    rows: list[dict[str, str]] = []
    counters = {"images": sum(map(len, images.values())), "annotations": sum(map(len, annotations.values())), "matched": 0, "missing_annotation": 0, "orphan_annotation": 0, "duplicate_image_id": 0, "duplicate_annotation_id": 0, "corrupt_files": 0, "empty_annotations": 0, "shape_mismatch": 0, "invalid_masks": 0, "uncertain_mappings": 0}

    for sid in sorted(images.keys() | annotations.keys(), key=lambda value: (int(value), value)):
        image_files, annotation_files = images.get(sid, []), annotations.get(sid, [])
        if len(image_files) > 1:
            counters["duplicate_image_id"] += 1
            issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in image_files), "reason": "duplicate image sample_id; no image selected"})
            rows.append({"sample_id": sid, "image": ";".join(p.relative_to(root).as_posix() for p in image_files), "annotation": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "status": "duplicate_image_id"})
            continue
        if not image_files:
            counters["orphan_annotation"] += len(annotation_files)
            issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "reason": "annotation has no image with this sample_id"})
            rows.append({"sample_id": sid, "image": "", "annotation": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "status": "orphan_annotation"})
            continue
        if len(annotation_files) > 1:
            counters["duplicate_annotation_id"] += 1
            issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "reason": "duplicate annotation sample_id; candidates validated below"})
        if not annotation_files:
            counters["missing_annotation"] += 1
            rows.append({"sample_id": sid, "image": image_files[0].relative_to(root).as_posix(), "annotation": "", "status": "missing_annotation"})
            continue

        image_path = image_files[0]
        image = read_image(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            counters["corrupt_files"] += 1
            issues.append({"dataset": name, "sample_id": sid, "files": image_path.relative_to(root).as_posix(), "reason": "image cannot be decoded"})
        decoded: list[tuple[Path, np.ndarray]] = []
        for annotation_path in annotation_files:
            mask = read_image(annotation_path, cv2.IMREAD_UNCHANGED)
            if mask is None:
                counters["corrupt_files"] += 1
                issues.append({"dataset": name, "sample_id": sid, "files": annotation_path.relative_to(root).as_posix(), "reason": "annotation cannot be decoded"})
                continue
            decoded.append((annotation_path, mask))
            if not mask_is_binary(mask):
                counters["invalid_masks"] += 1
                issues.append({"dataset": name, "sample_id": sid, "files": annotation_path.relative_to(root).as_posix(), "reason": "annotation has more than background and one foreground color"})
            if not np.any(mask):
                counters["empty_annotations"] += 1
                issues.append({"dataset": name, "sample_id": sid, "files": annotation_path.relative_to(root).as_posix(), "reason": "annotation is empty"})
            if image is not None and mask.shape[:2] != image.shape[:2]:
                counters["shape_mismatch"] += 1
                issues.append({"dataset": name, "sample_id": sid, "files": f"{image_path.relative_to(root).as_posix()};{annotation_path.relative_to(root).as_posix()}", "reason": f"image shape {image.shape[:2]} differs from annotation shape {mask.shape[:2]}"})

        selected: Path | None = None
        if len(annotation_files) == 1 and len(decoded) == 1:
            selected = decoded[0][0]
        elif allow_equivalent_variants and len(decoded) == len(annotation_files) and decoded:
            signatures = {binary_signature(mask) for _, mask in decoded}
            if len(signatures) == 1:
                preferred = [path for path, _ in decoded if path.stem.lower().endswith("_binary") and not path.stem.lower().endswith("_binary_binary")]
                selected = preferred[0] if len(preferred) == 1 else None
                if selected:
                    issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "reason": f"equivalent duplicate masks after foreground binarization; selected {selected.relative_to(root).as_posix()}"})
            if selected is None:
                counters["uncertain_mappings"] += 1
                issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "reason": "multiple annotation candidates without one verified canonical mask; mapping not selected"})
        else:
            counters["uncertain_mappings"] += 1
            issues.append({"dataset": name, "sample_id": sid, "files": ";".join(p.relative_to(root).as_posix() for p in annotation_files), "reason": "multiple annotation candidates; mapping not selected"})

        if selected is None:
            status = "uncertain_mapping"
        elif image is None or len(decoded) != len(annotation_files):
            status = "file_error"
        elif any(mask.shape[:2] != image.shape[:2] for _, mask in decoded) or any(not mask_is_binary(mask) or not np.any(mask) for _, mask in decoded):
            status = "invalid_pair"
        else:
            status = "matched"
            counters["matched"] += 1
        rows.append({"sample_id": sid, "image": image_path.relative_to(root).as_posix(), "annotation": selected.relative_to(root).as_posix() if selected else ";".join(p.relative_to(root).as_posix() for p in annotation_files), "status": status})
    return rows, issues, counters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/dataset_pair_audit_2026-10-03"))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    issues_all: list[dict[str, str]] = []
    summaries = {}
    for name, (image_rel, annotation_rel, variants) in DATASETS.items():
        rows, issues, counters = audit_dataset(root, name, image_rel, annotation_rel, variants)
        with (output / f"{name.lower()}_mapping.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=("sample_id", "image", "annotation", "status"))
            writer.writeheader()
            writer.writerows(rows)
        issues_all.extend(issues)
        summaries[name] = counters
    with (output / "issues.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=("dataset", "sample_id", "files", "reason"))
        writer.writeheader()
        writer.writerows(issues_all)
    (output / "summary.json").write_text(json.dumps({"root": str(root), "datasets": summaries}, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), "datasets": summaries}, indent=2))


if __name__ == "__main__":
    main()
