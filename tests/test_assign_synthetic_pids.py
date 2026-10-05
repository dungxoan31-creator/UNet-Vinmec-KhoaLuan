"""Synthetic identifiers support E2E schema checks, not patient provenance."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.assign_synthetic_pids import assign_synthetic_pids


def test_synthetic_pids_are_disjoint_and_reproducible(tmp_path):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 7, "val": 3, "test": 4}
    for split, count in counts.items():
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("case_id", "image_path", "mask_path", "patient_id"))
            writer.writeheader()
            for index in range(count):
                writer.writerow({
                    "case_id": f"{split}_{index}",
                    "image_path": f"images/{split}_{index}.png",
                    "mask_path": f"masks/{split}_{index}.png",
                    "patient_id": "",
                })
    (splits_dir / "manifest.json").write_text(json.dumps({"counts": counts}), encoding="utf-8")
    mapping_path = tmp_path / "patient_mapping.json"

    assign_synthetic_pids(splits_dir, mapping_path, seed=42)
    first_mapping = mapping_path.read_text(encoding="utf-8")
    first_csvs = {split: (splits_dir / f"{split}.csv").read_text(encoding="utf-8") for split in counts}
    assign_synthetic_pids(splits_dir, mapping_path, seed=42)
    assert mapping_path.read_text(encoding="utf-8") == first_mapping
    assert {split: (splits_dir / f"{split}.csv").read_text(encoding="utf-8") for split in counts} == first_csvs

    mapping = json.loads(first_mapping)
    manifest = json.loads((splits_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(mapping["records"]) == len(manifest["records"]) == sum(counts.values())
    assert manifest["patient_split_status"] == "partitioned by synthetic patient_id; disjoint split validated"
    assert manifest["source_patient_identity_verified"] is False
    patient_sets = {}
    group_sizes = Counter()
    for split, count in counts.items():
        with (splits_dir / f"{split}.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == count
        assert all(re.fullmatch(r"100\d{6}", row["patient_id"]) for row in rows)
        patient_sets[split] = {row["patient_id"] for row in rows}
        group_sizes.update(row["patient_id"] for row in rows)
        assert manifest["unique_patients_per_split"][split] == len(patient_sets[split])
    assert patient_sets["train"].isdisjoint(patient_sets["val"])
    assert patient_sets["train"].isdisjoint(patient_sets["test"])
    assert patient_sets["val"].isdisjoint(patient_sets["test"])
    assert all(1 <= size <= 3 for size in group_sizes.values())


def test_repository_mapping_covers_1202_images_without_cross_split_ids():
    root = Path(__file__).resolve().parents[1]
    splits_dir = root / "ai_training/splits/vinmec_2d_retrain_2026-10-03"
    mapping_path = root / "ai_training/splits/patient_mapping.json"
    manifest = json.loads((splits_dir / "manifest.json").read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(mapping_path.read_bytes()).hexdigest() == manifest["mapping_sha256"]
    assert mapping["records"] == manifest["records"]
    assert manifest["source_patient_identity_verified"] is False

    patient_sets = {}
    group_sizes = Counter()
    csv_records = []
    for split in ("train", "val", "test"):
        csv_path = splits_dir / f"{split}.csv"
        assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == manifest["split_csv_sha256_with_synthetic_metadata"][split]
        with csv_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == manifest["counts"][split]
        assert all(re.fullmatch(r"100\d{6}", row["patient_id"]) for row in rows)
        csv_records.extend({
            "case_id": row["case_id"], "image_path": row["image_path"],
            "split": split, "patient_id": row["patient_id"],
        } for row in rows)
        patient_sets[split] = {row["patient_id"] for row in rows}
        group_sizes.update(row["patient_id"] for row in rows)
        assert len(patient_sets[split]) == manifest["unique_patients_per_split"][split]
    assert sum(manifest["counts"].values()) == 1202
    assert csv_records == mapping["records"]
    assert patient_sets["train"].isdisjoint(patient_sets["val"])
    assert patient_sets["train"].isdisjoint(patient_sets["test"])
    assert patient_sets["val"].isdisjoint(patient_sets["test"])
    assert all(1 <= size <= 3 for size in group_sizes.values())


def test_selected_run_config_tracks_distinct_training_pre_pid_and_current_csvs():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "checkpoints/retrain_2d_2026-10-03_stable/run_config.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "ai_training/splits/vinmec_2d_retrain_2026-10-03/manifest.json").read_text(encoding="utf-8"))

    assert config["original_split_sha"] == config["split_sha256"]
    assert config["original_split_archive_status"] == "training CSV files not located"
    assert config["patient_split_status"] == "partitioned by synthetic patient_id; source patient identity unavailable"
    assert config["pre_pid_split_sha"] == manifest["split_csv_sha256_before_synthetic_metadata"]
    assert config["current_split_sha"] == manifest["split_csv_sha256_with_synthetic_metadata"]

    for split in ("train", "val", "test"):
        archived_path = root / config["pre_pid_split_archive"][split]
        source_path = root / "ai_training/splits/vinmec_2d" / f"{split}.csv"
        current_path = root / config["splits_dir"] / f"{split}.csv"
        assert archived_path.is_file()
        assert archived_path.read_bytes() == source_path.read_bytes()
        assert hashlib.sha256(archived_path.read_bytes()).hexdigest() == config["pre_pid_split_sha"][split]
        assert hashlib.sha256(current_path.read_bytes()).hexdigest() == config["current_split_sha"][split]
        assert config["original_split_sha"][split] != config["pre_pid_split_sha"][split]
        assert config["pre_pid_split_sha"][split] != config["current_split_sha"][split]
