"""Make reproducible sample-level train/validation CSVs from the audited pair tables."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

GROUPS = {
    "Vinmec_2D": ("vinmec_2d_mapping.csv",),
    "Vinmec_CEUS": ("vinmec_full_ceus_mapping.csv",),
    "Vinmec_Split_2D": ("vinmec_2d_train_mapping.csv", "vinmec_2d_test_mapping.csv"),
    "Vinmec_Split_CEUS": ("vinmec_ceus_mapping.csv",),
}
FIELDS = ("case_id", "image_path", "mask_path", "patient_id")


def _read_sources(audit_dir: Path, filenames: tuple[str, ...], group: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for filename in filenames:
        with (audit_dir / filename).open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                if row["status"] != "matched":
                    raise ValueError(f"Unvalidated pair in {filename}: sample_id={row['sample_id']} status={row['status']}")
                case_id = f"{group}-{row['sample_id']}"
                if case_id in seen:
                    raise ValueError(f"Duplicate sample ID after grouping: {case_id}")
                seen.add(case_id)
                rows.append({
                    "case_id": case_id,
                    "image_path": row["image"],
                    "mask_path": row["annotation"],
                    "patient_id": "",
                })
    return rows


def prepare(audit_dir: Path, output_dir: Path, val_fraction: float, seed: int) -> dict:
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between zero and one")
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for group, sources in GROUPS.items():
        rows = _read_sources(audit_dir, sources, group)
        rng = random.Random(seed)
        rng.shuffle(rows)
        n_val = max(1, round(len(rows) * val_fraction))
        val_rows, train_rows = rows[:n_val], rows[n_val:]
        if not train_rows:
            raise ValueError(f"No training samples remain for {group}")
        group_dir = output_dir / group.lower()
        group_dir.mkdir(parents=True, exist_ok=True)
        for split, split_rows in (("train", train_rows), ("val", val_rows)):
            with (group_dir / f"{split}.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(split_rows)
        # The trainer expects a test.csv; an empty manifest prevents accidental test evaluation.
        with (group_dir / "test.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            csv.DictWriter(stream, fieldnames=FIELDS).writeheader()
        hashes = {
            split: hashlib.sha256((group_dir / f"{split}.csv").read_bytes()).hexdigest()
            for split in ("train", "val")
        }
        summary = {
            "group": group,
            "source_mapping_tables": list(sources),
            "source_pairs": len(rows),
            "train": len(train_rows),
            "validation": len(val_rows),
            "test": 0,
            "split_level": "sample-level",
            "patient_id_status": "Patient IDs unavailable; patient-level independence is not verified",
            "source_test_included_in_pool": group == "Vinmec_Split_2D",
            "independent_test_available": False,
            "seed": seed,
            "validation_fraction": val_fraction,
            "csv_sha256": hashes,
        }
        (group_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        summaries[group] = summary
    (output_dir / "manifest.json").write_text(json.dumps({"seed": seed, "validation_fraction": val_fraction, "groups": summaries}, indent=2) + "\n", encoding="utf-8")
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=Path("evaluation/dataset_pair_audit_2026-10-03"))
    parser.add_argument("--output-dir", type=Path, default=Path("ai_training/splits/full_dataset_2026-10-03"))
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = prepare(args.audit_dir, args.output_dir, args.val_fraction, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
