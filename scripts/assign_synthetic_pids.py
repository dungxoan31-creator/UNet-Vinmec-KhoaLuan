"""Assign reproducible synthetic 9-digit IDs for E2E schema testing.

These IDs encode no real patient relationship and must not be used to claim
patient-level independence of the Vinmec source images.
"""

import argparse
import csv
import hashlib
import io
import json
import random
from collections import Counter
from pathlib import Path

SPLITS = ("train", "val", "test")
STATUS = "partitioned by synthetic patient_id; disjoint split validated"


def assign_synthetic_pids(splits_dir: Path, mapping_output: Path, seed: int = 42) -> dict:
    splits_dir, mapping_output = Path(splits_dir), Path(mapping_output)
    manifest_path = splits_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get("counts", {}).get(split) is None for split in SPLITS):
        raise ValueError("Manifest must declare train, val and test image counts")
    prior_synthetic_ids = {
        record["case_id"]: record["patient_id"] for record in manifest.get("records", [])
    } if manifest.get("synthetic_patient_metadata") else {}

    rows_by_split = {}
    fields_by_split = {}
    original_hashes = {}
    case_ids = set()
    for split in SPLITS:
        path = splits_dir / f"{split}.csv"
        original_hashes[split] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or ())
            if not {"case_id", "image_path", "mask_path"}.issubset(fields):
                raise ValueError(f"Missing required CSV columns in {path}")
            rows = list(reader)
        if len(rows) != manifest["counts"][split]:
            raise ValueError(f"{split} count differs from the manifest")
        for row in rows:
            case_id = row["case_id"].strip()
            if not case_id or case_id in case_ids:
                raise ValueError(f"Empty or duplicate case_id: {case_id!r}")
            case_ids.add(case_id)
            if row.get("patient_id") and prior_synthetic_ids.get(case_id) != row["patient_id"]:
                raise ValueError("Refusing to replace patient IDs without matching synthetic provenance")
        if "patient_id" not in fields:
            fields.append("patient_id")
        fields_by_split[split] = fields
        rows_by_split[split] = rows

    rng = random.Random(seed)
    groups = []
    for split in SPLITS:
        rows = rows_by_split[split]
        indices = list(range(len(rows)))
        rng.shuffle(indices)
        offset = 0
        while offset < len(indices):
            size = min(rng.randint(1, 3), len(indices) - offset)
            groups.append((split, [rows[index] for index in indices[offset:offset + size]]))
            offset += size

    if len(groups) > 1_000_000:
        raise ValueError("Synthetic PID namespace is too small")
    for (_, group), number in zip(groups, rng.sample(range(100_000_000, 101_000_000), len(groups))):
        for row in group:
            row["patient_id"] = str(number)

    patient_sets = {
        split: {row["patient_id"] for row in rows_by_split[split]}
        for split in SPLITS
    }
    if any(patient_sets[left] & patient_sets[right] for i, left in enumerate(SPLITS) for right in SPLITS[i + 1:]):
        raise AssertionError("Synthetic PID overlap across splits")
    group_sizes = Counter(row["patient_id"] for rows in rows_by_split.values() for row in rows)
    if not all(1 <= size <= 3 for size in group_sizes.values()):
        raise AssertionError("Synthetic group outside the 1-3 image range")

    counts = {split: len(rows_by_split[split]) for split in SPLITS}
    unique = {split: len(patient_sets[split]) for split in SPLITS}
    records = [
        {
            "case_id": row["case_id"],
            "image_path": row["image_path"],
            "split": split,
            "patient_id": row["patient_id"],
        }
        for split in SPLITS for row in rows_by_split[split]
    ]
    mapping = {
        "metadata_type": "synthetic_patient_id",
        "purpose": "E2E schema and integration testing only",
        "source_patient_identity_verified": False,
        "clinical_patient_leakage_excluded": False,
        "seed": seed,
        "patient_id_format": "^100[0-9]{6}$",
        "images_per_synthetic_patient": [1, 3],
        "counts": counts,
        "unique_patients_per_split": unique,
        "records": records,
    }
    mapping_bytes = (json.dumps(mapping, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    csv_bytes = {}
    for split in SPLITS:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields_by_split[split], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_by_split[split])
        csv_bytes[split] = buffer.getvalue().encode("utf-8")

    manifest.setdefault("split_csv_sha256_before_synthetic_metadata", original_hashes)
    manifest.update({
        "patient_id_status": "synthetic metadata only; source patient identity unavailable",
        "patient_split_status": STATUS,
        "synthetic_patient_metadata": True,
        "source_patient_identity_verified": False,
        "clinical_patient_leakage_excluded": False,
        "records_with_patient_id": counts,
        "unique_patients_per_split": unique,
        "patient_id_format_required": "^100[0-9]{6}$",
        "synthetic_patient_group_size_range": [1, 3],
        "mapping_file": mapping_output.as_posix(),
        "mapping_sha256": hashlib.sha256(mapping_bytes).hexdigest(),
        "split_csv_sha256_with_synthetic_metadata": {
            split: hashlib.sha256(csv_bytes[split]).hexdigest() for split in SPLITS
        },
        "records": records,
    })

    mapping_output.parent.mkdir(parents=True, exist_ok=True)
    mapping_output.write_bytes(mapping_bytes)
    for split in SPLITS:
        (splits_dir / f"{split}.csv").write_bytes(csv_bytes[split])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"counts": counts, "unique_patients_per_split": unique, "patient_split_status": STATUS}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits-dir", type=Path, default=Path("ai_training/splits/vinmec_2d_retrain_2026-10-03"))
    parser.add_argument("--mapping-output", type=Path, default=Path("ai_training/splits/patient_mapping.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(assign_synthetic_pids(args.splits_dir, args.mapping_output, args.seed), indent=2))
