"""Audit explicit image/target pairs and exact duplicates across local Vinmec roots.

This scanner never assigns files by directory order and does not write to dataset
roots. It reuses the project's existing sample-ID and mask validation rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.dataset_paths import resolve_dataset_path
from scripts.audit_segmentation_datasets import audit_dataset, read_image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

# Each adapter names one observed directory pair. `target_role` records the
# source's actual term; the target is not copied into the other semantic fields.
ADAPTERS = (
    ("Vinmec", "Vinmec_2D", "dataset/Vinmec/Vinmec_2d/images", "dataset/Vinmec/Vinmec_2d/annotations", "annotation", "source_lists", True),
    ("Vinmec", "Vinmec_3D_source", "dataset/Vinmec/Vinmec_3d/images", "dataset/Vinmec/Vinmec_3d/annotations", "annotation", "source_lists", True),
    ("Vinmec_2D", "Vinmec_2D_source_train", "dataset/Vinmec_2D/train/train_image", "dataset/Vinmec_2D/train/train_label/label", "label", "source_train_pool", False),
    ("Vinmec_2D", "Vinmec_2D_source_test", "dataset/Vinmec_2D/test/image", "dataset/Vinmec_2D/test/label/black_write", "label", "source_test", False),
    ("Vinmec_CEUS", "Vinmec_CEUS_subset", "dataset/Vinmec_CEUS/image", "dataset/Vinmec_CEUS/label", "label", "unpartitioned", False),
    ("vinmec_m1_307", "M1_307", "dataset/vinmec_m1_307/images", "dataset/vinmec_m1_307/masks", "mask", "M1_snapshot", False),
    ("vinmec_ovarian", "Ovarian_2D_train", "dataset/vinmec_ovarian/OTU_2D/train/train_image", "dataset/vinmec_ovarian/OTU_2D/train/train_label/label", "label", "source_train_pool", False),
    ("vinmec_ovarian", "Ovarian_2D_test", "dataset/vinmec_ovarian/OTU_2D/test/image", "dataset/vinmec_ovarian/OTU_2D/test/label/black_write", "label", "source_test", False),
    ("vinmec_ovarian", "Ovarian_CEUS", "dataset/vinmec_ovarian/OTU_CEUS/image", "dataset/vinmec_ovarian/OTU_CEUS/label", "label", "unpartitioned", False),
    ("vinmec_splits", "M1_train", "dataset/vinmec_splits/train/images", "dataset/vinmec_splits/train/masks", "mask", "train", False),
    ("vinmec_splits", "M1_val", "dataset/vinmec_splits/val/images", "dataset/vinmec_splits/val/masks", "mask", "val", False),
    ("vinmec_splits", "M1_test", "dataset/vinmec_splits/test/images", "dataset/vinmec_splits/test/masks", "mask", "test", False),
)

ROOTS = ("Vinmec", "Vinmec_2D", "Vinmec_CEUS", "vinmec_m1_307", "vinmec_ovarian", "vinmec_splits")
REQUIRED_FIELDS = ("image_path", "annotation_path", "label_path", "mask_path")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _paths_for_role(target_role: str, target: str) -> dict[str, str]:
    return {
        "annotation_path": target if target_role == "annotation" else "",
        "label_path": target if target_role == "label" else "",
        "mask_path": target if target_role == "mask" else "",
    }


def _inventory(root: Path, name: str) -> dict:
    base = root / "dataset" / name
    files = [p for p in base.rglob("*") if p.is_file()] if base.is_dir() else []
    extensions = Counter(p.suffix.lower() or "<no-extension>" for p in files)
    return {
        "exists": base.is_dir(),
        "file_count": len(files),
        "extension_counts": dict(sorted(extensions.items())),
        "directories": sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_dir()),
    }


def _load_m1_source_warnings(root: Path) -> list[dict[str, str]]:
    rows = []
    split_dir = root / "ai_training/splits/archive_milestone_1"
    adapters = (
        ("OTU_2D/train/train_image", "OTU_2D/train/train_label/label"),
        ("OTU_2D/test/image", "OTU_2D/test/label/black_write"),
        ("OTU_CEUS/image", "OTU_CEUS/label"),
    )
    for split in ("train", "val", "test"):
        csv_path = split_dir / f"{split}.csv"
        if not csv_path.is_file():
            continue
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            for record in csv.DictReader(stream):
                if record.get("is_empty_mask", "").lower() != "true":
                    continue
                image = resolve_dataset_path(root, record["image_path"])
                fallback_path = resolve_dataset_path(root, record["mask_path"])
                fallback_array = read_image(fallback_path, -1) if fallback_path.is_file() else None
                native = None
                for image_part, target_part in adapters:
                    marker = f"/ {image_part}/".replace(" ", "")
                    image_text = image.as_posix()
                    if marker in image_text:
                        native = Path(image_text.replace(marker, f"/{target_part}/")).with_suffix(".PNG")
                        break
                native_array = read_image(native, -1) if native and native.is_file() else None
                image_array = read_image(image, -1) if image.is_file() else None
                target_pixels = int(np.count_nonzero(native_array)) if native_array is not None else None
                shape_matches = bool(
                    native_array is not None
                    and image_array is not None
                    and native_array.shape[:2] == image_array.shape[:2]
                )
                rows.append({
                    "dataset": "vinmec_ovarian",
                    "group": "M1_derived_empty_mask",
                    "case_id": record.get("case_id", ""),
                    "sample_id": Path(record.get("image_path", "")).stem,
                    "image_path": record.get("image_path", ""),
                    "annotation_path": "",
                    "label_path": native.relative_to(root).as_posix() if native else "",
                    "mask_path": record.get("mask_path", ""),
                    "fallback_mask_exists": str(fallback_path.is_file()).lower(),
                    "fallback_mask_readable": str(fallback_array is not None).lower(),
                    "fallback_mask_empty": str(fallback_array is not None and not np.any(fallback_array)).lower(),
                    "fallback_mask_shape": "x".join(map(str, fallback_array.shape[:2])) if fallback_array is not None else "",
                    "native_target_exists": str(native is not None and native.is_file()).lower(),
                    "native_target_pixels": str(target_pixels) if target_pixels is not None else "",
                    "native_target_shape_matches": str(shape_matches).lower(),
                    "split": split,
                    "patient_id": record.get("patient_id", ""),
                    "status": "derived_empty_mask_requires_source_label_review",
                    "reason": "M1 split CSV explicitly maps the fallback mask to this image; the mapped native source label is recorded separately and is not replaced or treated as a verified ground truth.",
                })
    return rows


def _read_csv_assignments(root: Path, csv_path: Path, split: str, assignments: dict, details: dict) -> None:
    if not csv_path.is_file():
        return
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            rel = row.get("image_path", "")
            image = resolve_dataset_path(root, rel).resolve() if rel and not Path(rel).is_absolute() else Path(rel)
            if not image.is_file():
                continue
            digest = sha256(image)
            assignment = (split, csv_path.as_posix())
            assignments[digest].add(assignment)
            details[digest].append({"split": split, "manifest": csv_path.relative_to(root).as_posix(), "image_path": image.relative_to(root).as_posix()})


def _split_assignments(root: Path) -> tuple[dict[str, set], dict[str, list[dict[str, str]]]]:
    assignments: dict[str, set] = defaultdict(set)
    details: dict[str, list[dict[str, str]]] = defaultdict(list)
    # Source and archived snapshots are evidence only; synthetic mock splits are excluded.
    snapshots = (
        ("root", root / "ai_training/splits"),
        ("vinmec_2d", root / "ai_training/splits/vinmec_2d"),
        ("vinmec_2d_retrain", root / "ai_training/splits/vinmec_2d_retrain_2026-10-03"),
        ("archive_pre_pid", root / "ai_training/splits/archive_pre_pid"),
        ("archive_milestone_1", root / "ai_training/splits/archive_milestone_1"),
        ("unified", root / "ai_training/splits/unified_vinmec_clean_2026-10-06"),
    )
    for snapshot, split_dir in snapshots:
        for split in ("train", "val", "test"):
            _read_csv_assignments(root, split_dir / f"{split}.csv", f"{snapshot}_{split}", assignments, details)
    for split in ("train", "val", "test"):
        for csv_path in (root / "ai_training/splits/full_dataset_2026-10-03").rglob(f"{split}.csv"):
            if csv_path.is_file():
                _read_csv_assignments(root, csv_path, f"full_{split}", assignments, details)

    # The Vinmec-provided train/validation lists are sample-ID lists. Resolve
    # only within their own modality directory; numeric IDs are never joined
    # between different roots or modalities.
    for modality in ("2d", "3d"):
        image_dir = root / "dataset/Vinmec" / f"Vinmec_{modality}" / "images"
        list_dir = root / "dataset/Vinmec" / f"Vinmec_{modality}"
        for split in ("train", "val"):
            split_file = list_dir / f"{split}.txt"
            if not split_file.is_file():
                continue
            for line in split_file.read_text(encoding="utf-8-sig").splitlines():
                token = line.strip().split()[0] if line.strip() else ""
                stem = Path(token).stem
                image = image_dir / f"{stem}.JPG"
                if image.is_file():
                    digest = sha256(image)
                    assignments[digest].add((f"source_{split}", split_file.as_posix()))
                    details[digest].append({"split": f"source_{split}", "manifest": split_file.relative_to(root).as_posix(), "image_path": image.relative_to(root).as_posix()})

    # The materialized directory split provides exact per-image M1 membership.
    for split in ("train", "val", "test"):
        image_dir = root / "dataset/vinmec_splits" / split / "images"
        if image_dir.is_dir():
            for image in image_dir.iterdir():
                if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS:
                    digest = sha256(image)
                    assignments[digest].add((f"m1_{split}", "dataset/vinmec_splits"))
                    details[digest].append({"split": f"m1_{split}", "manifest": "dataset/vinmec_splits", "image_path": image.relative_to(root).as_posix()})
    return assignments, details


def _split_kind(label: str) -> str:
    token = label.lower()
    if token == "train" or token.endswith("_train"):
        return "train"
    if token in {"val", "validation"} or token.endswith("_val") or token.endswith("_validation"):
        return "val"
    if token == "test" or token.endswith("_test"):
        return "test"
    return token


def _read_optional_csv(path: Path) -> list[dict[str, str]] | None:
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _source_test_row_count(rows: list[dict[str, str]] | None) -> int | None:
    if rows is None:
        return None
    count = 0
    for row in rows:
        path = str(row.get("image_path") or "").replace("\\", "/").lower()
        if "/test/" in f"/{path.strip('/')}/":
            count += 1
    return count


def _read_legacy_vinmec_2d_split_evidence(root: Path) -> dict:
    split_dir = root / "ai_training/splits/full_dataset_2026-10-03/vinmec_split_2d"
    manifest_path = split_dir / "manifest.json"
    manifest = {}
    manifest_readable = False
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
                manifest_readable = True
        except (OSError, json.JSONDecodeError):
            pass

    split_rows = {split: _read_optional_csv(split_dir / f"{split}.csv") for split in ("train", "val", "test")}
    split_counts = {
        split: len(rows) if rows is not None else None
        for split, rows in split_rows.items()
    }
    source_test_rows = {split: _source_test_row_count(split_rows[split]) for split in ("train", "val")}
    m1_counts = {
        split: len(rows) if rows is not None else None
        for split in ("train", "val", "test")
        for rows in (_read_optional_csv(root / "ai_training/splits/archive_milestone_1" / f"{split}.csv"),)
    }
    return {
        "manifest_exists": manifest_path.is_file(),
        "manifest_readable": manifest_readable,
        "source_test_included_in_pool": manifest.get("source_test_included_in_pool"),
        "split_level": manifest.get("split_level"),
        "source_test_rows_in_train_val": source_test_rows,
        "source_test_count": sum(source_test_rows.values()) if all(value is not None for value in source_test_rows.values()) else None,
        "split_counts": split_counts,
        "m1_counts": m1_counts,
    }


def _active_split_integrity(root: Path, observed_image_hashes: dict[Path, str] | None = None) -> dict:
    split_dir = root / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    manifest_path = split_dir / "manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except (OSError, json.JSONDecodeError):
            pass

    rows_by_split = {
        split: _read_optional_csv(split_dir / f"{split}.csv")
        for split in ("train", "val", "test")
    }
    counts = {split: len(rows) if rows is not None else None for split, rows in rows_by_split.items()}
    declared_hashes: dict[str, set[str]] = {split: set() for split in rows_by_split}
    actual_hashes: dict[str, set[str]] = {split: set() for split in rows_by_split}
    invalid_hash_rows = 0
    hash_mismatches = 0
    missing_images = 0
    missing_masks = 0
    missing_pairs = 0
    patient_ids_present = 0
    patient_ids_by_split: dict[str, set[str]] = {split: set() for split in rows_by_split}

    for split, rows in rows_by_split.items():
        for row in rows or []:
            recorded_hash = str(row.get("image_sha256") or "").strip().lower()
            valid_hash = len(recorded_hash) == 64 and all(char in "0123456789abcdef" for char in recorded_hash)
            if valid_hash:
                declared_hashes[split].add(recorded_hash)
            else:
                invalid_hash_rows += 1
            patient_id = str(row.get("patient_id") or "").strip()
            patient_ids_present += bool(patient_id)
            if patient_id:
                patient_ids_by_split[split].add(patient_id)

            image_path = resolve_dataset_path(root, str(row.get("image_path") or ""))
            mask_path = resolve_dataset_path(root, str(row.get("mask_path") or ""))
            image_exists, mask_exists = image_path.is_file(), mask_path.is_file()
            missing_images += not image_exists
            missing_masks += not mask_exists
            missing_pairs += not (image_exists and mask_exists)
            if image_exists:
                resolved_image = image_path.resolve()
                actual_hash = (observed_image_hashes or {}).get(resolved_image) or sha256(resolved_image)
                actual_hashes[split].add(actual_hash)
                if valid_hash and actual_hash.lower() != recorded_hash:
                    hash_mismatches += 1

    def overlap_count(hash_sets: dict[str, set[str]]) -> int:
        splits = tuple(hash_sets)
        return sum(
            len(hash_sets[left] & hash_sets[right])
            for index, left in enumerate(splits)
            for right in splits[index + 1:]
        )

    declared_overlap = overlap_count(declared_hashes)
    actual_overlap = overlap_count(actual_hashes)
    expected_counts = manifest.get("split_counts")
    counts_match = (
        all(counts[split] is not None and type(expected_counts.get(split)) is int and counts[split] == expected_counts[split] for split in counts)
        if isinstance(expected_counts, dict)
        else None
    )
    total_rows = sum(len(rows) if rows is not None else 0 for rows in rows_by_split.values())
    patient_id_overlap_count = sum(
        len(patient_ids_by_split[left] & patient_ids_by_split[right])
        for index, left in enumerate(rows_by_split)
        for right in tuple(rows_by_split)[index + 1:]
    )
    patient_ids_complete = total_rows > 0 and patient_ids_present == total_rows
    patient_level_verified = manifest.get("source_patient_identity_verified") is True and (
        manifest.get("patient_ids_verified") is True or manifest.get("identity_level") == "patient_verified"
    ) and patient_ids_complete and patient_id_overlap_count == 0 and counts_match is True and all(
        count is not None and count > 0 for count in counts.values()
    )
    image_hash_validation_complete = (
        invalid_hash_rows == 0 and hash_mismatches == 0 and missing_images == 0
    )
    image_level_training_ready = (
        counts_match is True
        and all(count is not None and count > 0 for count in counts.values())
        and image_hash_validation_complete
        and missing_masks == 0
        and declared_overlap == 0
        and actual_overlap == 0
    )
    patient_independent_evaluation_allowed = (
        patient_level_verified
        and image_level_training_ready
    )

    return {
        "manifest_exists": manifest_path.is_file(),
        "manifest_status": manifest.get("status"),
        "identity_limit": manifest.get("identity_limit"),
        "patient_level_verified": patient_level_verified,
        "patient_ids_present": patient_ids_present,
        "patient_id_rows_missing_count": total_rows - patient_ids_present,
        "patient_id_overlap_count": patient_id_overlap_count,
        "record_counts": counts,
        "manifest_counts_match_csv": counts_match,
        "image_level_training_ready": image_level_training_ready,
        "patient_independent_evaluation_allowed": patient_independent_evaluation_allowed,
        "declared_hash_overlap_count": declared_overlap,
        "actual_hash_overlap_count": actual_overlap,
        "invalid_hash_row_count": invalid_hash_rows,
        "recorded_hash_mismatch_count": hash_mismatches,
        "missing_image_count": missing_images,
        "missing_mask_count": missing_masks,
        "missing_pair_count": missing_pairs,
        "image_hash_validation_complete": image_hash_validation_complete,
        "image_hash_split_disjoint": declared_overlap == 0 and actual_overlap == 0 and invalid_hash_rows == 0 and hash_mismatches == 0,
    }


def _summarize_m1_empty_masks(all_rows: list[dict], provenance_exists: bool) -> dict:
    rows = [row for row in all_rows if row.get("status") == "derived_empty_mask_requires_source_label_review"]
    count = len(rows)
    fallback_present = sum(row.get("fallback_mask_exists") == "true" for row in rows)
    fallback_readable = sum(row.get("fallback_mask_readable") == "true" for row in rows)
    fallback_empty = sum(row.get("fallback_mask_empty") == "true" for row in rows)
    native_found = sum(row.get("native_target_exists") == "true" for row in rows)
    native_positive = sum(
        row.get("native_target_exists") == "true"
        and str(row.get("native_target_pixels", "")).isdigit()
        and int(row["native_target_pixels"]) > 0
        for row in rows
    )
    native_shape_matches = sum(
        row.get("native_target_exists") == "true" and row.get("native_target_shape_matches") == "true"
        for row in rows
    )

    if not count:
        audit_note = "No archived M1 empty-mask records were found."
    elif native_positive:
        audit_note = f"{native_positive} archived M1 fallback records map to positive native labels; neither target is silently substituted."
    elif fallback_present < count or native_found < count:
        audit_note = (
            f"Archived M1 CSVs identify {count} fallback-mask records, but current fallback masks "
            f"({fallback_present}/{count}) or native source labels ({native_found}/{count}) are unavailable; "
            "their prior conflict claims cannot be revalidated from this workspace."
        )
    else:
        audit_note = "Archived M1 fallback masks and native source labels were located; no target was silently substituted."

    return {
        "count": count,
        "provenance_exists": provenance_exists,
        "fallback_masks_present": fallback_present,
        "fallback_masks_readable": fallback_readable,
        "fallback_masks_empty": fallback_empty,
        "fallback_mask_shapes": dict(Counter(row.get("fallback_mask_shape", "") for row in rows if row.get("fallback_mask_shape"))),
        "native_source_labels_found": native_found,
        "native_source_labels_positive": native_positive,
        "native_source_shape_matches": native_shape_matches,
        "audit_note": audit_note,
    }


def audit(root: Path, output_dir: Path) -> dict:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict] = {}
    all_rows: list[dict[str, str]] = []
    all_issues: list[dict[str, str]] = []
    image_occurrences: dict[str, list[tuple[str, str]]] = defaultdict(list)
    root_role_counts = {name: {"annotation": 0, "label": 0, "mask": 0} for name in ROOTS}
    channel_stats: dict[str, dict[str, Counter]] = defaultdict(lambda: {"image_channels": Counter(), "target_channels": Counter(), "image_formats": Counter(), "target_formats": Counter()})

    for dataset_name, group_name, image_rel, target_rel, target_role, split, variants in ADAPTERS:
        source_image_rel, source_target_rel = image_rel, target_rel
        image_rel = resolve_dataset_path(root, image_rel).relative_to(root).as_posix()
        target_rel = resolve_dataset_path(root, target_rel).relative_to(root).as_posix()
        rows, issues, counters = audit_dataset(root, group_name, image_rel, target_rel, variants)
        group_rows = []
        root_role_counts[dataset_name][target_role] += counters["annotations"]
        for row in rows:
            image_rel_path, target_rel_path = row["image"], row["annotation"]
            image_path = root / image_rel_path if image_rel_path and ";" not in image_rel_path else None
            target_path = root / target_rel_path if target_rel_path and ";" not in target_rel_path else None
            image_hash = sha256(image_path) if image_path and image_path.is_file() else ""
            if image_hash:
                image_occurrences[image_hash].append((dataset_name, image_rel_path))
            if image_path and image_path.is_file():
                image_array = read_image(image_path, -1)
                if image_array is not None:
                    channels = image_array.shape[2] if image_array.ndim == 3 else 1
                    channel_stats[group_name]["image_channels"][str(channels)] += 1
                    channel_stats[group_name]["image_formats"][image_path.suffix.lower()] += 1
            if target_path and target_path.is_file():
                target_array = read_image(target_path, -1)
                if target_array is not None:
                    channels = target_array.shape[2] if target_array.ndim == 3 else 1
                    channel_stats[group_name]["target_channels"][str(channels)] += 1
                    channel_stats[group_name]["target_formats"][target_path.suffix.lower()] += 1
            mapped = {
                "dataset": dataset_name,
                "group": group_name,
                "sample_id": row["sample_id"],
                "case_id": f"{dataset_name}::{group_name}::{row['sample_id']}",
                "patient_id": "",
                "image_path": image_rel_path,
                **_paths_for_role(target_role, target_rel_path),
                "target_role": target_role,
                "split": split,
                "image_sha256": image_hash,
                "status": row["status"],
                "issue": "",
            }
            group_rows.append(mapped)
            all_rows.append(mapped)

        for issue in issues:
            all_issues.append({"dataset": dataset_name, "group": group_name, **issue})
        summaries[group_name] = {
            "dataset": dataset_name,
            "image_directory": image_rel,
            "target_directory": target_rel,
            "source_image_directory": source_image_rel,
            "source_target_directory": source_target_rel,
            "target_role": target_role,
            "source_split_label": split,
            "pair_audit": counters,
            "format_channels": {key: dict(value) for key, value in channel_stats[group_name].items()},
            "full_four_path_mapping_count": sum(all(bool(row[field]) for field in REQUIRED_FIELDS) for row in group_rows),
            "sample_records": len(group_rows),
        }

    all_rows.extend(_load_m1_source_warnings(root))
    for row in all_rows:
        if row["status"] not in {"matched"}:
            all_issues.append({
                "dataset": row["dataset"], "group": row.get("group", "empty_masks"),
                "sample_id": row["sample_id"],
                "files": ";".join(value for value in (row["image_path"], row["annotation_path"], row["label_path"], row["mask_path"]) if value),
                "reason": row.get("reason", row["status"]),
            })

    split_assignments, split_details = _split_assignments(root)
    split_conflicts = []
    for digest, assignment_list in split_assignments.items():
        distinct_splits = sorted({_split_kind(split) for split, _ in assignment_list})
        if len(distinct_splits) > 1:
            split_conflicts.append({
                "sha256": digest,
                "split_assignments": ";".join(distinct_splits),
                "evidence": json.dumps(split_details[digest], ensure_ascii=False),
            })
    for row in all_rows:
        digest = row.get("image_sha256", "")
        if digest and digest in split_assignments:
            evidence = sorted({split for split, _ in split_assignments[digest]})
            labels = sorted({_split_kind(split) for split in evidence})
            row["split_evidence"] = ";".join(evidence)
            if len(labels) > 1:
                row["split"] = "conflict"
                row["status"] = f"{row['status']};split_conflict"
                row["issue"] = "Exact image SHA is assigned to more than one split in existing manifests/source lists."
            elif labels:
                row["split"] = labels[0]
    table_rows = []
    for dataset in ROOTS:
        dataset_rows = [row for row in all_rows if row["dataset"] == dataset]
        split_evidence = [
            {_split_kind(label) for label in row.get("split_evidence", "").split(";") if label}
            for row in dataset_rows
        ]
        table_rows.append({
            "dataset": dataset,
            "candidate_records_before_cross_root_dedup": sum(1 for row in dataset_rows if row["image_path"]),
            "valid_image_target_pairs": sum(1 for row in dataset_rows if row["status"].startswith("matched")),
            "train_evidence_records": sum(1 for labels in split_evidence if "train" in labels),
            "validation_evidence_records": sum(1 for labels in split_evidence if "val" in labels),
            "test_evidence_records": sum(1 for labels in split_evidence if "test" in labels),
            "conflicting_split_records": sum(1 for row in dataset_rows if row["split"] == "conflict"),
            "count_note": "Per-root candidate counts overlap across roots; do not sum as independent samples.",
        })
    duplicate_rows = []
    duplicate_hash_count = 0
    duplicate_extra_paths = 0
    for digest, occurrences in sorted(image_occurrences.items()):
        distinct_roots = sorted({dataset for dataset, _ in occurrences})
        if len(occurrences) > 1:
            duplicate_hash_count += 1
            duplicate_extra_paths += len(occurrences) - 1
            duplicate_rows.append({
                "sha256": digest,
                "occurrence_count": len(occurrences),
                "dataset_roots": ";".join(distinct_roots),
                "paths": ";".join(path for _, path in occurrences),
            })

    roots_summary = {}
    for name in ROOTS:
        inv = _inventory(root, name)
        group_names = [g for g, s in summaries.items() if s["dataset"] == name]
        if name == "vinmec_ovarian":
            root_role_counts[name]["mask"] += len(list((root / "dataset/vinmec_ovarian/empty_masks").glob("*.png")))
        group_counts = [summaries[g]["pair_audit"] for g in group_names]
        inv.update({
            "image_files_in_adapted_dirs": sum(c["images"] for c in group_counts),
            "annotation_files_in_adapted_dirs": root_role_counts[name]["annotation"],
            "label_files_in_adapted_dirs": root_role_counts[name]["label"],
            "mask_files_in_adapted_dirs": root_role_counts[name]["mask"],
            "adapter_groups": group_names,
            "sample_records": sum(summaries[g]["sample_records"] for g in group_names),
            "candidate_pairs": sum(c["images"] for c in group_counts),
            "complete_image_target_pairs": sum(c["matched"] for c in group_counts),
            "missing_targets": sum(c["missing_annotation"] for c in group_counts),
            "orphan_targets": sum(c["orphan_annotation"] for c in group_counts),
            "duplicate_image_ids": sum(c["duplicate_image_id"] for c in group_counts),
            "duplicate_target_ids": sum(c["duplicate_annotation_id"] for c in group_counts),
            "unreadable_files": sum(c["corrupt_files"] for c in group_counts),
            "shape_mismatches": sum(c["shape_mismatch"] for c in group_counts),
            "invalid_or_empty_targets": sum(c["invalid_masks"] + c["empty_annotations"] for c in group_counts),
            "unresolved_mapping_count": sum(c["uncertain_mappings"] for c in group_counts),
            "patient_id_status": "No verified source patient IDs found; M1 synthetic IDs are structural only",
            "image_channel_distribution": {group: summaries[group]["format_channels"]["image_channels"] for group in group_names},
            "target_channel_distribution": {group: summaries[group]["format_channels"]["target_channels"] for group in group_names},
        })
        roots_summary[name] = inv

    split_manifests = {}
    for name in (
        "ai_training/splits/vinmec_2d/manifest.json",
        "ai_training/splits/vinmec_2d_retrain_2026-10-03/manifest.json",
        "ai_training/splits/unified_vinmec_clean_2026-10-06/manifest.json",
        "ai_training/splits/archive_milestone_1/README.md",
        "ai_training/splits/full_dataset_2026-10-03/manifest.json",
    ):
        p = root / name
        split_manifests[name] = {"exists": p.is_file(), "sha256": sha256(p) if p.is_file() else None}
    full_m1_provenance = root / "dataset/vinmec_ovarian/empty_masks/PROVENANCE.json"
    legacy_split_evidence = _read_legacy_vinmec_2d_split_evidence(root)
    observed_image_hashes = {
        (root / relative_path).resolve(): digest
        for digest, occurrences in image_occurrences.items()
        for _, relative_path in occurrences
    }
    active_split_integrity = _active_split_integrity(root, observed_image_hashes)
    m1_empty_masks = _summarize_m1_empty_masks(all_rows, full_m1_provenance.is_file())
    missing_source_directories = sum(
        issue.get("reason") in {"image directory does not exist", "annotation directory does not exist"}
        for issue in all_issues
    )
    blocking_conditions = [
        "No verified source Patient ID mapping is available; patient-level leakage cannot be ruled out."
    ]
    if active_split_integrity["missing_pair_count"]:
        blocking_conditions.append(
            f"The active unified split references {active_split_integrity['missing_pair_count']} image/mask pairs unavailable in the current workspace."
        )
    if active_split_integrity["declared_hash_overlap_count"] or active_split_integrity["actual_hash_overlap_count"]:
        blocking_conditions.append("The active unified split contains image SHA-256 overlap across partitions.")
    if active_split_integrity["recorded_hash_mismatch_count"]:
        blocking_conditions.append(
            f"{active_split_integrity['recorded_hash_mismatch_count']} active split image SHA-256 values do not match available source files."
        )
    if active_split_integrity["manifest_counts_match_csv"] is False:
        blocking_conditions.append("The active unified split CSV row counts do not match its manifest.")
    if missing_source_directories:
        blocking_conditions.append(
            f"{missing_source_directories} recorded source directories are absent; the audit covers only available canonical data and cannot revalidate those roots."
        )
    if duplicate_hash_count:
        blocking_conditions.append(
            f"{duplicate_hash_count} exact-image SHA-256 groups occur more than once in the scanned roots and require source-level reconciliation."
        )
    blocking_conditions.append(
        "The observed schemas provide one annotation/label/mask target per image, not three distinct target files."
    )
    if m1_empty_masks["native_source_labels_positive"]:
        blocking_conditions.append(
            f"{m1_empty_masks['native_source_labels_positive']} archived M1 fallback records map to positive native labels; source-label review is required."
        )
    elif m1_empty_masks["count"] and (
        m1_empty_masks["fallback_masks_present"] < m1_empty_masks["count"]
        or m1_empty_masks["native_source_labels_found"] < m1_empty_masks["count"]
    ):
        blocking_conditions.append(
            f"{m1_empty_masks['count']} archived M1 fallback records cannot be fully revalidated because referenced source files are unavailable; provenance is absent."
        )
    if legacy_split_evidence["source_test_included_in_pool"] is True:
        source_test_count = legacy_split_evidence["source_test_count"]
        source_test_description = f"{source_test_count} source Test records" if source_test_count is not None else "source Test records"
        blocking_conditions.append(
            f"The legacy sample-level Vinmec_2D split pools {source_test_description} into Train/Validation; it cannot support an independent Test result."
        )
    if len(split_conflicts):
        blocking_conditions.append(
            f"{len(split_conflicts)} image hashes have incompatible split assignments in available manifests."
        )
    summary = {
        "status": "BLOCKED_BEFORE_TRAINING",
        "project_root": str(root),
        "framework": "PyTorch",
        "training_entrypoints": {
            "baseline": "ai_training/train_baseline_unet.py (accepts image-level splits after image/mask, SHA-256, and binary-mask validation; research development only)",
            "full_data": "ai_training/train_full_unet.py (does not require patient IDs; loads Train and Validation only, selects by validation Dice, and leaves Test image data held out)",
        },
        "datasets": roots_summary,
        "dataset_table_before_training": table_rows,
        "groups": summaries,
        "cross_root_exact_image_duplicates": {
            "duplicate_sha256_count": duplicate_hash_count,
            "extra_copied_paths": duplicate_extra_paths,
            "details_csv": "reports/dataset_validation_duplicates.csv",
        },
        "existing_split_conflicts": {
            "conflicting_image_hash_count": len(split_conflicts),
            "details_csv": "reports/dataset_validation_split_conflicts.csv",
            "interpretation": "The same exact image appears in incompatible train/validation/test assignments across active and archived source snapshots; these cross-snapshot conflicts do not identify which historic assignment is authoritative.",
        },
        "active_split_integrity": active_split_integrity,
        "four_path_mapping": {
            "required_fields": list(REQUIRED_FIELDS),
            "status": "NOT_ESTABLISHED",
            "reason": "Observed source schemas provide one annotation/label/mask target per image, not three distinct target files. No aliases were fabricated.",
            "canonical_index_written": False,
        },
        "split_and_leakage": {
            "source_patient_ids_verified": active_split_integrity["patient_level_verified"],
            "image_level_training_ready": active_split_integrity["image_level_training_ready"],
            "m1_patient_codes_are_synthetic": True,
            "full_dataset_2026_10_03_manifest_includes_source_test_in_pool_for_vinmec_2d": legacy_split_evidence["source_test_included_in_pool"],
            "existing_full_dataset_split_level": legacy_split_evidence["split_level"],
            "vinmec_2d_source_test_count": legacy_split_evidence["source_test_count"],
            "vinmec_2d_source_test_rows_in_train_val": legacy_split_evidence["source_test_rows_in_train_val"],
            "vinmec_2d_current_train_val_test_counts": legacy_split_evidence["split_counts"],
            "m1_counts": legacy_split_evidence["m1_counts"],
            "source_splits_or_duplicate_hash_conflicts_require_review": bool(
                legacy_split_evidence["source_test_included_in_pool"] is True
                or split_conflicts
                or duplicate_hash_count
            ),
        },
        "m1_empty_masks": m1_empty_masks,
        "tracked_split_evidence": split_manifests,
        "blocking_conditions": blocking_conditions,
        "issues_csv": "reports/dataset_validation_issues.csv",
        "samples_csv": "reports/dataset_validation_samples.csv",
        "no_source_files_modified": True,
        "training_started": False,
    }

    (output_dir / "dataset_validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "dataset_validation.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("dataset", "exists", "file_count", "image_files_in_adapted_dirs", "annotation_files_in_adapted_dirs", "label_files_in_adapted_dirs", "mask_files_in_adapted_dirs", "candidate_pairs", "complete_image_target_pairs", "missing_targets", "orphan_targets", "duplicate_image_ids", "duplicate_target_ids", "unreadable_files", "shape_mismatches", "invalid_or_empty_targets", "unresolved_mapping_count", "patient_id_status")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for dataset, values in roots_summary.items():
            writer.writerow({"dataset": dataset, **{field: values.get(field, "") for field in fields if field != "dataset"}})
    with (output_dir / "dataset_validation_samples.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("dataset", "group", "case_id", "sample_id", "patient_id", "image_path", "annotation_path", "label_path", "mask_path", "fallback_mask_exists", "fallback_mask_readable", "fallback_mask_empty", "fallback_mask_shape", "native_target_exists", "native_target_pixels", "native_target_shape_matches", "target_role", "split", "split_evidence", "image_sha256", "status", "issue")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    with (output_dir / "dataset_validation_issues.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("dataset", "group", "sample_id", "files", "reason")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_issues)
    with (output_dir / "dataset_validation_duplicates.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("sha256", "occurrence_count", "dataset_roots", "paths")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(duplicate_rows)
    with (output_dir / "dataset_validation_split_conflicts.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("sha256", "split_assignments", "evidence")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(split_conflicts)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    summary = audit(root, output)
    print(json.dumps(summary, indent=2))
    print("\nDataset              Candidates  Valid pairs  Train evidence  Val evidence  Test evidence  Split conflicts")
    for row in summary["dataset_table_before_training"]:
        print(f"{row['dataset']:<20} {row['candidate_records_before_cross_root_dedup']:>10} {row['valid_image_target_pairs']:>12} {row['train_evidence_records']:>14} {row['validation_evidence_records']:>12} {row['test_evidence_records']:>14} {row['conflicting_split_records']:>16}")
    print("Counts overlap across roots until exact-duplicate groups and split conflicts are reconciled.")


if __name__ == "__main__":
    main()
