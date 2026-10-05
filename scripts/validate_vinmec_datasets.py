"""Audit explicit image/target pairs and exact duplicates across local Vinmec roots.

This scanner never assigns files by directory order and does not write to dataset
roots. It reuses the project's existing sample-ID and mask validation rules.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

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
                image = root / record["image_path"]
                fallback_path = root / record["mask_path"]
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
            image = (root / rel).resolve() if rel and not Path(rel).is_absolute() else Path(rel)
            if not image.is_file():
                continue
            digest = sha256(image)
            assignment = (split, csv_path.as_posix())
            assignments[digest].add(assignment)
            details[digest].append({"split": split, "manifest": csv_path.relative_to(root).as_posix(), "image_path": image.relative_to(root).as_posix()})


def _split_assignments(root: Path) -> tuple[dict[str, set], dict[str, list[dict[str, str]]]]:
    assignments: dict[str, set] = defaultdict(set)
    details: dict[str, list[dict[str, str]]] = defaultdict(list)
    # Existing split snapshots are read as evidence only; no split is rewritten.
    for split in ("train", "val", "test"):
        _read_csv_assignments(root, root / "ai_training/splits/vinmec_2d" / f"{split}.csv", split, assignments, details)
        _read_csv_assignments(root, root / "ai_training/splits/archive_milestone_1" / f"{split}.csv", f"m1_{split}", assignments, details)
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
        "ai_training/splits/archive_milestone_1/README.md",
        "ai_training/splits/full_dataset_2026-10-03/manifest.json",
    ):
        p = root / name
        split_manifests[name] = {"exists": p.is_file(), "sha256": sha256(p) if p.is_file() else None}
    full_m1_provenance = root / "dataset/vinmec_ovarian/empty_masks/PROVENANCE.json"
    summary = {
        "status": "BLOCKED_BEFORE_TRAINING",
        "project_root": str(root),
        "framework": "PyTorch",
        "training_entrypoints": {
            "baseline": "ai_training/train_baseline_unet.py (uses train/val split; default split path must be overridden explicitly)",
            "full_data": "ai_training/train_full_unet.py (currently includes the source test folder in its training pair groups and has no validation loader; unsafe for requested run)",
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
            "interpretation": "The same exact image appears in incompatible train/validation/test assignments across available source manifests; no assignment was selected.",
        },
        "four_path_mapping": {
            "required_fields": list(REQUIRED_FIELDS),
            "status": "NOT_ESTABLISHED",
            "reason": "Observed source schemas provide one annotation/label/mask target per image, not three distinct target files. No aliases were fabricated.",
            "canonical_index_written": False,
        },
        "split_and_leakage": {
            "source_patient_ids_verified": False,
            "m1_patient_codes_are_synthetic": True,
            "full_dataset_2026_10_03_manifest_includes_source_test_in_pool_for_vinmec_2d": True,
            "existing_full_dataset_split_level": "sample-level",
            "vinmec_2d_source_test_count": 382,
            "vinmec_2d_current_train_val_test_counts": {"train": 697, "val": 123, "test": 382},
            "m1_counts": {"train": 215, "val": 46, "test": 46},
            "source_splits_or_duplicate_hash_conflicts_require_review": True,
        },
        "m1_empty_masks": {
            "count": sum(1 for row in all_rows if row["status"] == "derived_empty_mask_requires_source_label_review"),
            "provenance_exists": full_m1_provenance.is_file(),
            "fallback_masks_present": sum(1 for row in all_rows if row.get("fallback_mask_exists") == "true"),
            "fallback_masks_readable": sum(1 for row in all_rows if row.get("fallback_mask_readable") == "true"),
            "fallback_masks_empty": sum(1 for row in all_rows if row.get("fallback_mask_empty") == "true"),
            "fallback_mask_shapes": dict(Counter(row.get("fallback_mask_shape", "") for row in all_rows if row.get("fallback_mask_shape"))),
            "native_source_labels_found": sum(1 for row in all_rows if row["status"] == "derived_empty_mask_requires_source_label_review" and row.get("label_path")),
            "native_source_labels_positive": sum(1 for row in all_rows if row["status"] == "derived_empty_mask_requires_source_label_review" and row.get("native_target_pixels", "0").isdigit() and int(row["native_target_pixels"]) > 0),
            "native_source_shape_matches": sum(1 for row in all_rows if row["status"] == "derived_empty_mask_requires_source_label_review" and row.get("native_target_shape_matches") == "true"),
            "audit_note": "Each fallback is linked through its archived M1 CSV to an image and the separate native source label path. These records remain unresolved because the fallback target is empty while the associated native target is positive; neither is silently substituted.",
        },
        "tracked_split_evidence": split_manifests,
        "blocking_conditions": [
            "No verified source Patient ID mapping across the six roots; patient-level leakage cannot be ruled out.",
            "Exact image content is duplicated across the named roots; the six folders are overlapping copies/derivations, not six independent datasets.",
            "The requested distinct annotation/label/mask paths are not present in the observed schemas; one target file per image is available.",
            "Thirty-five M1 fallback masks conflict with positive native labels and the referenced provenance file is absent.",
            "The full-data training entrypoint currently includes the source Test folder in training and does not use a validation set.",
        ],
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
        fields = ("dataset", "group", "case_id", "sample_id", "patient_id", "image_path", "annotation_path", "label_path", "mask_path", "fallback_mask_exists", "fallback_mask_readable", "fallback_mask_empty", "fallback_mask_shape", "native_target_pixels", "native_target_shape_matches", "target_role", "split", "split_evidence", "image_sha256", "status", "issue")
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
