"""Synthetic identifiers support E2E schema checks, not patient provenance."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from scripts.assign_synthetic_pids import assign_synthetic_pids


def test_synthetic_pids_are_disjoint_and_reproducible(tmp_path):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 7, "val": 3, "test": 4}
    for split, count in counts.items():
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("case_id", "image_path", "mask_path", "patient_id", "image_sha256"),
            )
            writer.writeheader()
            for index in range(count):
                image_path = splits_dir / "images" / f"{split}_{index}.png"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_bytes = f"{split}-{index}".encode()
                image_path.write_bytes(image_bytes)
                writer.writerow({
                    "case_id": f"{split}_{index}",
                    "image_path": str(image_path),
                    "mask_path": f"masks/{split}_{index}.png",
                    "patient_id": "",
                    "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
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


def test_retired_retrain_archive_is_not_required_for_current_split_safety():
    root = Path(__file__).resolve().parents[1]
    retired_dir = root / "ai_training/splits/vinmec_2d_retrain_2026-10-03"
    assert not retired_dir.exists()

    canonical_dir = root / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    manifest = json.loads((canonical_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "blocked_unverified_patient_identity"
    assert manifest["source_patient_identity_verified"] is False
    assert manifest["patient_level_independence_verified"] is False


def test_selected_run_config_does_not_require_deleted_split_archives():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "checkpoints/retrain_2d_2026-10-03_stable/run_config.json").read_text(encoding="utf-8"))
    assert config["original_split_sha"] == config["split_sha256"]
    assert config["original_split_archive_status"] == "training CSV files not located"
    assert config["patient_split_status"] == "partitioned by synthetic patient_id; source patient identity unavailable"
    for split, archived_path in config["pre_pid_split_archive"].items():
        assert not (root / archived_path).exists(), split


def test_synthetic_pid_assignment_rejects_cross_split_image_hashes(tmp_path):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 1, "val": 1, "test": 1}
    for split, image_bytes in (
        ("train", b"same source image"),
        ("val", b"same source image"),
        ("test", b"different source image"),
    ):
        image_path = splits_dir / "images" / f"{split}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("case_id", "image_path", "mask_path", "image_sha256"),
            )
            writer.writeheader()
            writer.writerow({
                "case_id": f"{split}-different-id",
                "image_path": str(image_path),
                "mask_path": f"masks/{split}.png",
                "image_sha256": image_hash,
            })
    (splits_dir / "manifest.json").write_text(json.dumps({"counts": counts}), encoding="utf-8")

    with pytest.raises(ValueError, match="Image SHA-256 overlap"):
        assign_synthetic_pids(splits_dir, tmp_path / "mapping.json")


def test_synthetic_pid_assignment_rejects_hash_not_matching_source_bytes(tmp_path):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 1, "val": 1, "test": 1}
    for split in counts:
        image_path = splits_dir / "images" / f"{split}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(f"actual-{split}".encode())
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("case_id", "image_path", "mask_path", "image_sha256"),
            )
            writer.writeheader()
            writer.writerow({
                "case_id": f"{split}-case",
                "image_path": str(image_path),
                "mask_path": f"masks/{split}.png",
                "image_sha256": hashlib.sha256(f"claim-{split}".encode()).hexdigest(),
            })
    (splits_dir / "manifest.json").write_text(json.dumps({"counts": counts}), encoding="utf-8")

    with pytest.raises(ValueError, match="Image SHA-256 does not match the source file"):
        assign_synthetic_pids(splits_dir, tmp_path / "mapping.json")


@pytest.mark.parametrize("bad_hash", ("", "not-a-hash", "g" * 64))
def test_synthetic_pid_assignment_rejects_invalid_image_hashes(tmp_path, bad_hash):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 1, "val": 1, "test": 1}
    for split in counts:
        image_hash = bad_hash if split == "train" else hashlib.sha256(split.encode()).hexdigest()
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("case_id", "image_path", "mask_path", "image_sha256"),
            )
            writer.writeheader()
            writer.writerow({
                "case_id": f"{split}-case",
                "image_path": f"images/{split}.png",
                "mask_path": f"masks/{split}.png",
                "image_sha256": image_hash,
            })
    (splits_dir / "manifest.json").write_text(json.dumps({"counts": counts}), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid or missing image SHA-256"):
        assign_synthetic_pids(splits_dir, tmp_path / "mapping.json")


def test_synthetic_pid_assignment_requires_image_hash_column(tmp_path):
    splits_dir = tmp_path / "splits"
    splits_dir.mkdir()
    counts = {"train": 1, "val": 1, "test": 1}
    for split in counts:
        with (splits_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("case_id", "image_path", "mask_path"))
            writer.writeheader()
            writer.writerow({
                "case_id": f"{split}-case",
                "image_path": f"images/{split}.png",
                "mask_path": f"masks/{split}.png",
            })
    (splits_dir / "manifest.json").write_text(json.dumps({"counts": counts}), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required CSV columns"):
        assign_synthetic_pids(splits_dir, tmp_path / "mapping.json")
