"""Build a deduplicated, read-only Vinmec segmentation manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _split_kind(label: str) -> str | None:
    token = label.strip().lower()
    if token == "train" or token.endswith("_train"):
        return "train"
    if token in {"val", "validation"} or token.endswith(("_val", "_validation")):
        return "val"
    if token == "test" or token.endswith("_test"):
        return "test"
    return None


def assign_split(evidence: set[str]) -> str:
    """Resolve conflicting split evidence conservatively: Test, then Val, then Train."""
    kinds = {_split_kind(label) for label in evidence} - {None}
    for split in ("test", "val", "train"):
        if split in kinds:
            return split
    raise ValueError("No recognized split evidence for sample")


def _fallback_image_hashes(root: Path) -> set[str]:
    hashes = set()
    split_root = root / "ai_training/splits/archive_milestone_1"
    for split in ("train", "val", "test"):
        path = split_root / f"{split}.csv"
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row.get("is_empty_mask", "").lower() != "true":
                    continue
                image = root / row["image_path"]
                fallback = root / row["mask_path"]
                mask = cv2.imread(str(fallback), cv2.IMREAD_GRAYSCALE)
                if not image.is_file() or mask is None or np.any(mask):
                    raise ValueError(f"Invalid or unreadable fallback record: {row.get('case_id', row['image_path'])}")
                hashes.add(_sha256(image))
    if len(hashes) != 35:
        raise ValueError(f"Expected 35 distinct fallback-associated images; found {len(hashes)}")
    return hashes


def _read_audit_rows(root: Path) -> list[dict[str, str]]:
    audit = root / "reports/dataset_validation_samples.csv"
    with audit.open(newline="", encoding="utf-8-sig") as stream:
        return [row for row in csv.DictReader(stream) if row.get("image_sha256")]


def _target_signature(root: Path, record: dict[str, str]) -> str:
    target_rel = next((record.get(field, "") for field in ("annotation_path", "label_path", "mask_path") if record.get(field)), "")
    target = root / target_rel
    mask = cv2.imread(str(target), cv2.IMREAD_GRAYSCALE) if target.is_file() else None
    if mask is None:
        raise ValueError(f"Target is missing or unreadable: {target_rel}")
    binary = np.ascontiguousarray(mask > 0, dtype=np.uint8)
    return hashlib.sha256(binary.tobytes()).hexdigest()


def build(root: Path, split_dir: Path, index_path: Path) -> dict:
    root = root.resolve()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _read_audit_rows(root):
        if row.get("status", "").startswith("matched"):
            grouped[row["image_sha256"]].append(row)

    fallback_hashes = _fallback_image_hashes(root)
    if not fallback_hashes.issubset(grouped):
        raise ValueError("Some fallback-associated images are absent from the validated mapping")

    records = []
    target_disagreements = []
    for image_hash, source_rows in sorted(grouped.items()):
        image_signatures = {_target_signature(root, row) for row in source_rows}
        if len(image_signatures) != 1:
            target_disagreements.append(image_hash)
            continue
        if image_hash in fallback_hashes:
            continue

        source_rows.sort(key=lambda row: (row["dataset"] != "Vinmec", row["image_path"], row["mask_path"] or row["label_path"] or row["annotation_path"]))
        canonical = source_rows[0]
        target_rel = next(canonical[field] for field in ("annotation_path", "label_path", "mask_path") if canonical.get(field))
        evidence = {label for row in source_rows for label in row.get("split_evidence", "").split(";") if label}
        records.append({
            "sample_id": image_hash,
            "case_id": image_hash,
            "patient_id": "",
            "identity_level": "image_sha256; source Patient/Case ID unavailable",
            "image_path": canonical["image_path"],
            "mask_path": target_rel,
            "target_role": canonical["target_role"],
            "canonical_source": canonical["dataset"],
            "source_datasets": ";".join(sorted({row["dataset"] for row in source_rows})),
            "source_image_paths": ";".join(sorted({row["image_path"] for row in source_rows})),
            "source_target_paths": ";".join(sorted({path for row in source_rows for path in (row["annotation_path"], row["label_path"], row["mask_path"]) if path})),
            "split_evidence": ";".join(sorted(evidence)),
            "split": assign_split(evidence),
            "image_sha256": image_hash,
            "status": "ready_image_level",
        })
    if target_disagreements:
        raise ValueError(f"Binary target disagreement for {len(target_disagreements)} duplicate images; see hashes: {target_disagreements[:10]}")

    split_dir.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(records[0])
    _write_csv(index_path, records, fields)
    _write_csv(split_dir / "all_samples.csv", records, fields)
    dataloader_fields = ("case_id", "image_path", "mask_path", "patient_id", "image_sha256")
    for split in ("train", "val", "test"):
        selected = [row for row in records if row["split"] == split]
        _write_csv(split_dir / f"{split}.csv", selected, dataloader_fields)

    counts = {split: sum(row["split"] == split for row in records) for split in ("train", "val", "test")}
    summary = {
        "status": "ready_for_image_level_training",
        "deduplication": "SHA-256 of raw image bytes; one canonical record per unique image",
        "input_unique_images": len(grouped),
        "fallback_associated_images_excluded": len(fallback_hashes),
        "samples_after_exclusion": len(records),
        "split_counts": counts,
        "split_policy": "Test evidence takes precedence over Validation, then Train; no image hash crosses splits.",
        "identity_limit": "No verified source Patient/Case IDs; split guarantees image-content separation only.",
        "target_policy": "One verified binary target per image; all duplicate-source target masks must agree after binarization.",
        "target_disagreements": 0,
        "training_seed": 42,
        "split_seed": None,
        "canonical_index": index_path.relative_to(root).as_posix(),
        "split_manifest_directory": split_dir.relative_to(root).as_posix(),
        "training_test_policy": "Test CSV is held out; the baseline trainer uses only Train and Validation for optimization and checkpoint selection.",
    }
    (split_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...] | list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--split-dir", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"))
    parser.add_argument("--index", type=Path, default=Path("dataset/index.csv"))
    args = parser.parse_args()
    root = args.root.resolve()
    split_dir = args.split_dir if args.split_dir.is_absolute() else root / args.split_dir
    index_path = args.index if args.index.is_absolute() else root / args.index
    print(json.dumps(build(root, split_dir, index_path), indent=2))


if __name__ == "__main__":
    main()
