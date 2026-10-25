"""Generate technical-only synthetic groups for schema and pipeline checks.

Synthetic group IDs are not source patient identities and must not be used to
claim patient-level independence or clinical evaluation validity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from backend.core.dataset_paths import resolve_dataset_path

ROOT = Path(__file__).resolve().parents[1]
ALL_SAMPLES_CSV = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06/all_samples.csv"
OUTPUT_MAPPING_CSV = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06/patient_mapping_simulated.csv"
OUTPUT_ALL_PATIENT_CSV = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06/all_samples_patient_split.csv"
OUTPUT_COHORT_JSON = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06/patient_cohort_metadata.json"

SPLITS = ("train", "val", "test")
REQUIRED_COLUMNS = {"case_id", "image_sha256", "split", "image_path", "mask_path"}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
BENCHMARK_TAG = "[SIMULATED - TECHNICAL BENCHMARK ONLY]"


def _read_and_validate_source(source_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with source_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = list(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")

        rows = []
        seen_cases: set[str] = set()
        seen_hashes: set[str] = set()
        split_counts: Counter[str] = Counter()
        for line_number, source_row in enumerate(reader, start=2):
            row = {key: (value or "") for key, value in source_row.items() if key is not None}
            case_id = row["case_id"].strip()
            if not case_id:
                raise ValueError(f"case_id is empty at row {line_number}")
            if case_id in seen_cases:
                raise ValueError(f"duplicate case_id: {case_id}")
            seen_cases.add(case_id)

            split = row["split"].strip().lower()
            if split not in SPLITS:
                raise ValueError(f"invalid split at row {line_number}: {row['split']!r}")
            split_counts[split] += 1

            image_hash = row["image_sha256"].strip().lower()
            if not HASH_RE.fullmatch(image_hash):
                raise ValueError(f"invalid image SHA-256 at row {line_number}: {row['image_sha256']!r}")
            if image_hash in seen_hashes:
                raise ValueError(f"duplicate image SHA-256: {image_hash}")
            seen_hashes.add(image_hash)

            for field in ("image_path", "mask_path"):
                row[field] = row[field].strip()
                if not row[field]:
                    raise ValueError(f"{field} is empty at row {line_number}")

            # If source bytes are available in this checkout, reject a manifest
            # hash that does not identify those bytes. Missing paths in isolated
            # fixtures are allowed; the CSV itself is never rewritten.
            image_path = resolve_dataset_path(ROOT, row["image_path"])
            if image_path.is_file():
                actual_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
                if actual_hash != image_hash:
                    raise ValueError(f"image SHA-256 does not match source file at row {line_number}")

            row["case_id"] = case_id
            row["image_sha256"] = image_hash
            row["split"] = split
            rows.append(row)

    absent = [split for split in SPLITS if split_counts[split] == 0]
    if absent:
        raise ValueError(f"at least one sample in each split: {', '.join(absent)}")
    return rows, columns


def _assign_synthetic_groups(rows: list[dict[str, str]], seed: int) -> dict[str, int]:
    rng = random.Random(seed)
    patient_counts: dict[str, int] = {}
    for split in SPLITS:
        split_rows = [row for row in rows if row["split"] == split]
        rng.shuffle(split_rows)
        group_number = 0
        index = 0
        while index < len(split_rows):
            group_number += 1
            group_size = min(rng.randint(1, 3), len(split_rows) - index)
            # Include the split in the identifier so accidental cross-split
            # reuse is impossible even if this implementation later changes.
            synthetic_id = f"SIM-PAT-{split.upper()}-{group_number:05d}"
            for row in split_rows[index:index + group_size]:
                row["patient_id"] = synthetic_id
                row["patient_id_type"] = "synthetic_technical_only"
                row["benchmark_tag"] = BENCHMARK_TAG
            index += group_size
        patient_counts[split] = group_number
    return patient_counts


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def generate_synthetic_cohort(seed: int = 42) -> dict:
    """Write deterministic technical-only cohort mappings after fail-closed validation."""
    rows, source_columns = _read_and_validate_source(Path(ALL_SAMPLES_CSV))
    patient_counts = _assign_synthetic_groups(rows, seed)

    mapping_columns = ["case_id", "image_sha256", "split", "patient_id", "image_path", "mask_path", "benchmark_tag"]
    _write_csv(Path(OUTPUT_MAPPING_CSV), mapping_columns, rows)
    all_columns = list(source_columns)
    for column in ("patient_id", "patient_id_type", "benchmark_tag"):
        if column not in all_columns:
            all_columns.append(column)
    _write_csv(Path(OUTPUT_ALL_PATIENT_CSV), all_columns, rows)

    split_statistics = {
        split: {
            "images": sum(row["split"] == split for row in rows),
            "synthetic_patient_groups": patient_counts[split],
        }
        for split in SPLITS
    }
    metadata = {
        "benchmark_tag": BENCHMARK_TAG,
        "seed": seed,
        "total_images": len(rows),
        "split_statistics": split_statistics,
        "source_patient_identity_verified": False,
        "patient_level_independence_verified": False,
        "synthetic_patient_disjointness_verified": True,
        "clinical_metadata_is_synthetic": True,
        "label_provenance_verified": False,
        "note": "Synthetic groups are technical fixtures only; they do not represent real patients or independent clinical cohorts.",
    }
    cohort_path = Path(OUTPUT_COHORT_JSON)
    cohort_path.parent.mkdir(parents=True, exist_ok=True)
    cohort_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    print(json.dumps(generate_synthetic_cohort(), ensure_ascii=False, indent=2))
