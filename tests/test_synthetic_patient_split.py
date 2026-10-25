import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"


def _write_synthetic_source_manifest(tmp_path, rows, fieldnames=("case_id", "image_sha256", "split", "image_path", "mask_path")):
    source_manifest = tmp_path / "all_samples.csv"
    with source_manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return source_manifest


def _synthetic_rows():
    return [
        {
            "case_id": split,
            "image_sha256": hashlib.sha256(split.encode()).hexdigest(),
            "split": split,
            "image_path": f"images/{split}.png",
            "mask_path": f"masks/{split}.png",
        }
        for split in ("train", "val", "test")
    ]


def test_synthetic_patient_split_manifests_exist():
    mapping_csv = SPLIT_DIR / "patient_mapping_simulated.csv"
    cohort_json = SPLIT_DIR / "patient_cohort_metadata.json"
    assert mapping_csv.exists(), "patient_mapping_simulated.csv must exist"
    assert cohort_json.exists(), "patient_cohort_metadata.json must exist"
    cohort = json.loads(cohort_json.read_text(encoding="utf-8"))
    assert cohort["benchmark_tag"] == "[SIMULATED - TECHNICAL BENCHMARK ONLY]"
    assert cohort["source_patient_identity_verified"] is False
    assert cohort["synthetic_patient_disjointness_verified"] is True


def test_synthetic_patient_split_disjointness_and_counts():
    mapping_csv = SPLIT_DIR / "patient_mapping_simulated.csv"
    with mapping_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1604, "Must contain all 1604 canonical samples"

    patients_by_split = {"train": set(), "val": set(), "test": set()}
    for r in rows:
        split = r["split"]
        pid = r["patient_id"]
        assert pid.startswith("SIM-PAT-"), f"Invalid simulated patient ID: {pid}"
        patients_by_split[split].add(pid)

    train_pts = patients_by_split["train"]
    val_pts = patients_by_split["val"]
    test_pts = patients_by_split["test"]

    assert len(train_pts & val_pts) == 0, "Patient overlap between train and val!"
    assert len(train_pts & test_pts) == 0, "Patient overlap between train and test!"
    assert len(val_pts & test_pts) == 0, "Patient overlap between val and test!"

    # Check total patients
    total_unique = len(train_pts | val_pts | test_pts)
    assert total_unique == len(train_pts) + len(val_pts) + len(test_pts)
    assert total_unique > 700


def test_dataset_statistics_preserves_source_identity_limits():
    manifest = json.loads((SPLIT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["samples_after_exclusion"] == 1604
    assert manifest["source_patient_identity_verified"] is False
    assert manifest["patient_ids_verified"] is False
    assert manifest["patient_level_independence_verified"] is False


def test_synthetic_cohort_generation_does_not_overwrite_source_statistics(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    source_manifest = tmp_path / "all_samples.csv"
    with source_manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["case_id", "image_sha256", "split", "image_path", "mask_path"],
        )
        writer.writeheader()
        for split in ("train", "val", "test"):
            writer.writerow({
                "case_id": split,
                "image_sha256": hashlib.sha256(split.encode()).hexdigest(),
                "split": split,
                "image_path": f"images/{split}.png",
                "mask_path": f"masks/{split}.png",
            })

    source_stats = tmp_path / "dataset_statistics.json"
    original_stats = {
        "sample_count": 3,
        "patient_id_missing_count": 3,
        "source_patient_identity_verified": False,
        "patient_level_split_verified": False,
        "status": "READY_IMAGE_LEVEL_ONLY",
    }
    source_stats.write_text(json.dumps(original_stats), encoding="utf-8")
    original_bytes = source_stats.read_bytes()
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    generator.generate_synthetic_cohort(seed=1)

    assert source_stats.read_bytes() == original_bytes
    cohort = json.loads((tmp_path / "patient_cohort_metadata.json").read_text(encoding="utf-8"))
    assert cohort["benchmark_tag"] == "[SIMULATED - TECHNICAL BENCHMARK ONLY]"
    assert cohort["source_patient_identity_verified"] is False


def test_current_synthetic_cohort_source_passes_fail_closed_validation(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    source_manifest = SPLIT_DIR / "all_samples.csv"
    original_bytes = source_manifest.read_bytes()
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    result = generator.generate_synthetic_cohort()

    assert {
        split: result["split_statistics"][split]["images"]
        for split in ("train", "val", "test")
    } == {"train": 661, "val": 541, "test": 402}
    assert source_manifest.read_bytes() == original_bytes
    cohort = json.loads((tmp_path / "patient_cohort_metadata.json").read_text(encoding="utf-8"))
    assert cohort["total_images"] == 1604
    assert cohort["source_patient_identity_verified"] is False
    assert cohort["clinical_metadata_is_synthetic"] is True


@pytest.mark.parametrize("bad_split", ("", "validation"))
def test_synthetic_cohort_generation_rejects_empty_or_unknown_split(tmp_path, monkeypatch, bad_split):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[1]["split"] = bad_split
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="split"):
        generator.generate_synthetic_cohort()


def test_synthetic_cohort_generation_rejects_duplicate_image_hashes(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[1]["image_sha256"] = rows[0]["image_sha256"]
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="duplicate image SHA-256"):
        generator.generate_synthetic_cohort()


@pytest.mark.parametrize("bad_hash", ("", "not-a-hash", "g" * 64))
def test_synthetic_cohort_generation_rejects_invalid_image_hashes(tmp_path, monkeypatch, bad_hash):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[1]["image_sha256"] = bad_hash
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="invalid image SHA-256"):
        generator.generate_synthetic_cohort()


def test_synthetic_cohort_generation_rejects_duplicate_case_ids(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[1]["case_id"] = rows[0]["case_id"]
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="duplicate case_id"):
        generator.generate_synthetic_cohort()


def test_synthetic_cohort_generation_normalizes_split_whitespace_and_case(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[0]["split"] = " TRAIN "
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    output_manifest = tmp_path / "all_samples_patient_split.csv"
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", output_manifest)
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    generator.generate_synthetic_cohort()

    with output_manifest.open(newline="", encoding="utf-8") as stream:
        output_rows = list(csv.DictReader(stream))
    assert output_rows[0]["split"] == "train"


def test_synthetic_cohort_generation_rejects_empty_manifest(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    source_manifest = _write_synthetic_source_manifest(tmp_path, [])
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="at least one sample in each split"):
        generator.generate_synthetic_cohort()


def test_synthetic_cohort_generation_rejects_missing_manifest_columns(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    source_manifest = _write_synthetic_source_manifest(
        tmp_path,
        [],
        fieldnames=("case_id", "image_sha256", "split"),
    )
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="missing required columns"):
        generator.generate_synthetic_cohort()


def test_synthetic_cohort_generation_rejects_missing_split_partition(tmp_path, monkeypatch):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()[:2]
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match="at least one sample in each split: test"):
        generator.generate_synthetic_cohort()


@pytest.mark.parametrize("path_field", ("image_path", "mask_path"))
def test_synthetic_cohort_generation_rejects_empty_source_paths(tmp_path, monkeypatch, path_field):
    from scripts import prepare_synthetic_patient_cohort as generator

    rows = _synthetic_rows()
    rows[0][path_field] = "  "
    source_manifest = _write_synthetic_source_manifest(tmp_path, rows)
    monkeypatch.setattr(generator, "ALL_SAMPLES_CSV", source_manifest)
    monkeypatch.setattr(generator, "OUTPUT_MAPPING_CSV", tmp_path / "patient_mapping_simulated.csv")
    monkeypatch.setattr(generator, "OUTPUT_ALL_PATIENT_CSV", tmp_path / "all_samples_patient_split.csv")
    monkeypatch.setattr(generator, "OUTPUT_COHORT_JSON", tmp_path / "patient_cohort_metadata.json")

    with pytest.raises(ValueError, match=path_field):
        generator.generate_synthetic_cohort()
