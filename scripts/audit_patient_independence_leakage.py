#!/usr/bin/env python3
"""Dataset Split Independence and Leakage Audit Tool (Block 4).

Rigorously verifies zero data leakage (SHA-256 image hashes) between train, validation,
and test partitions, and provides ingestion contract for data custodian cohort groups.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit.independence")

COHORT_INGESTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DataCustodianCohortMapping",
    "description": "Standard schema for external hospital data custodians to supply pseudonymized patient cohort groupings.",
    "type": "object",
    "required": ["institution_id", "custodian_attestation_hash", "records"],
    "properties": {
        "institution_id": {"type": "string"},
        "custodian_attestation_hash": {"type": "string"},
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["image_sha256", "pseudonymized_patient_group_id"],
                "properties": {
                    "image_sha256": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"},
                    "pseudonymized_patient_group_id": {"type": "string"},
                    "study_date": {"type": "string"},
                },
            },
        },
    },
}


def audit_splits(splits_dir: str) -> dict[str, Any]:
    """Audit split CSV files by directory to ensure zero mutual leakage between train, val, and test."""
    splits_path = Path(splits_dir)
    if not splits_path.exists():
        logger.warning("Splits directory not found: %s", splits_dir)
        return {"status": "SKIPPED", "reason": "Directory not found"}

    # Group CSV files by their parent directory
    folders: dict[str, dict[str, set[str]]] = {}
    missing_files: list[dict[str, str]] = []
    csv_files = [f for f in splits_path.rglob("*.csv") if "all_samples" not in f.stem and "mapping" not in f.stem]

    for file in csv_files:
        folder_name = file.parent.name
        name = file.stem.lower()
        if folder_name not in folders:
            folders[folder_name] = {}

        hashes = set()
        with open(file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            hash_col = next(
                (c for c in reader.fieldnames or [] if "hash" in c.lower() or "sha256" in c.lower()),
                None,
            )
            file_col = next(
                (c for c in reader.fieldnames or [] if "file" in c.lower() or "path" in c.lower() or "image" in c.lower()),
                None,
            )
            for row in reader:
                h = None
                if hash_col and row.get(hash_col):
                    h = row[hash_col].strip().lower()
                elif file_col and row.get(file_col):
                    val = row[file_col].strip()
                    resolved = None
                    p = Path(val)
                    if p.is_file():
                        resolved = p
                    else:
                        for base_dir in [file.parent, splits_path, Path(".")]:
                            cand = base_dir / p
                            if cand.is_file():
                                resolved = cand
                                break
                    if resolved:
                        with open(resolved, "rb") as bf:
                            h = hashlib.file_digest(bf, "sha256").hexdigest()
                    else:
                        # Fail-closed: Never hash file path string when image bytes are missing
                        missing_files.append({"split": name, "folder": folder_name, "path": val})
                if h:
                    hashes.add(h)
        folders[folder_name][name] = hashes
        logger.info("Folder '%s' / '%s': %d records", folder_name, name, len(hashes))

    folder_results = {}
    total_leakages = 0
    for folder_name, partitions in folders.items():
        keys = list(partitions.keys())
        leakages = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                overlap = partitions[k1].intersection(partitions[k2])
                if overlap:
                    leakages.append({"pair": f"{k1} vs {k2}", "overlap_count": len(overlap)})
                    total_leakages += len(overlap)
        folder_results[folder_name] = {
            "status": "PASS" if not leakages else "LEAKAGE_DETECTED",
            "leakages": leakages,
        }

    if missing_files:
        status = "FAIL"
        conclusion = (
            f"Audit FAILED (fail-closed): {len(missing_files)} referenced image files could not be resolved on disk. "
            "Verification of partition independence requires actual byte-level validation."
        )
    elif total_leakages > 0:
        status = "LEAKAGE_DETECTED"
        conclusion = f"Partition independence violated: {total_leakages} overlapping records found."
    elif not folders or all(len(parts) <= 1 for parts in folders.values()) or all(all(len(h) == 0 for h in parts.values()) for parts in folders.values()):
        status = "INCOMPLETE"
        conclusion = "Audit INCOMPLETE: No valid partitions or records found to evaluate."
    else:
        status = "PASS"
        conclusion = (
            "Partition independence verified across train/val/test splits. "
            "Patient-level independence remains unverified (A4) in absence of ground truth patient groupings."
        )

    result = {
        "status": status,
        "total_leakages": total_leakages,
        "missing_files_count": len(missing_files),
        "missing_files": missing_files[:20],
        "folder_audits": folder_results,
        "conclusion": conclusion,
    }
    logger.info("Audit result: %s (leakages=%d)", status, total_leakages)
    return result


def export_custodian_schema(out_path: str) -> None:
    Path(out_path).write_text(json.dumps(COHORT_INGESTION_SCHEMA, indent=2), encoding="utf-8")
    logger.info("Exported custodian schema to %s", out_path)


def main():
    parser = argparse.ArgumentParser(description="Audit dataset splits for independence")
    parser.add_argument("--splits-dir", default="ai_training/splits", help="Path to splits directory")
    parser.add_argument("--schema-out", default="docs/evaluation/custodian_cohort_schema.json", help="Path to export schema")
    args = parser.parse_args()

    export_custodian_schema(args.schema_out)
    res = audit_splits(args.splits_dir)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
