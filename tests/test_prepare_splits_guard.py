import csv
import hashlib
import json

import pandas as pd
import pytest
from PIL import Image

from ai_training.train_baseline_unet import validate_training_split_identity
from scripts import prepare_splits
from scripts.prepare_splits import validate_patient_split_metadata


def _metadata():
    return pd.DataFrame(
        [
            {
                "case_id": "case-train", "patient_id": " PID-A ", "split": "train",
                "image_path": "images/train.png", "mask_path": "masks/train.png", "is_empty_mask": False,
            },
            {
                "case_id": "case-val", "patient_id": "PID-B", "split": "val",
                "image_path": "images/val.png", "mask_path": "masks/val.png", "is_empty_mask": False,
            },
            {
                "case_id": "case-test", "patient_id": "PID-C", "split": "test",
                "image_path": "images/test.png", "mask_path": "masks/test.png", "is_empty_mask": False,
            },
        ]
    )


def _identity_manifest():
    return {
        "source_patient_identity_verified": True,
        "patient_ids_verified": True,
        "identity_level": "patient_verified",
        "identity_source": "source_case_crosswalk",
        "identity_evidence_reference": "approved data mapping record",
        "metadata_sha256": "a" * 64,
    }


def test_patient_split_requires_source_identity_evidence():
    with pytest.raises(ValueError, match="source-verified patient identity"):
        validate_patient_split_metadata(_metadata(), {}, "a" * 64)


def test_patient_split_normalizes_and_reports_verified_disjoint_groups():
    validated, evidence = validate_patient_split_metadata(
        _metadata(), _identity_manifest(), "a" * 64
    )

    assert validated["split"].tolist() == ["TRAIN", "VAL", "TEST"]
    assert validated["patient_id"].tolist() == ["PID-A", "PID-B", "PID-C"]
    assert evidence["split_counts"] == {"train": 1, "val": 1, "test": 1}
    assert evidence["unique_patient_ids"] == 3


def test_patient_split_rejects_empty_identity_and_unknown_split():
    rows = _metadata()
    rows.loc[0, "patient_id"] = "   "
    with pytest.raises(ValueError, match="empty patient_id"):
        validate_patient_split_metadata(rows, _identity_manifest(), "a" * 64)

    rows = _metadata()
    rows.loc[0, "split"] = "holdout"
    with pytest.raises(ValueError, match="unknown split"):
        validate_patient_split_metadata(rows, _identity_manifest(), "a" * 64)


def test_patient_split_rejects_one_patient_assigned_to_multiple_splits():
    rows = _metadata()
    rows.loc[1, "patient_id"] = "PID-A"

    with pytest.raises(ValueError, match="crosses split boundaries"):
        validate_patient_split_metadata(rows, _identity_manifest(), "a" * 64)


def test_patient_split_identity_manifest_must_match_metadata_hash():
    with pytest.raises(ValueError, match="metadata SHA-256"):
        validate_patient_split_metadata(_metadata(), _identity_manifest(), "b" * 64)


def test_patient_split_refuses_synthetic_identity_attestation():
    manifest = _identity_manifest()
    manifest["synthetic_patient_metadata"] = True

    with pytest.raises(ValueError, match="Synthetic patient metadata"):
        validate_patient_split_metadata(_metadata(), manifest, "a" * 64)


def test_split_creation_binds_output_manifest_to_verified_source_without_rewriting_it(
    tmp_path, monkeypatch
):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    data_dir = tmp_path / "dataset" / "2d"
    (data_dir / "images").mkdir(parents=True)
    (data_dir / "masks").mkdir()
    source_csv = metadata_dir / "kltn_ground_truth_307.csv"
    rows = []
    for image_value, (split, patient_id) in enumerate(
        (("TRAIN", "PID-A"), ("VAL", "PID-B"), ("TEST", "PID-C")), start=100
    ):
        image_path = data_dir / "images" / f"{split.lower()}.png"
        mask_path = data_dir / "masks" / f"{split.lower()}.png"
        Image.new("L", (8, 8), image_value).save(image_path)
        Image.new("L", (8, 8), 0).save(mask_path)
        rows.append(
            {
                "case_id": f"case-{split.lower()}",
                "patient_id": patient_id,
                "split": split,
                "image_path": image_path.relative_to(tmp_path).as_posix(),
                "mask_path": mask_path.relative_to(tmp_path).as_posix(),
                "is_empty_mask": "True",
            }
        )

    with source_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    original_bytes = source_csv.read_bytes()
    identity_manifest = _identity_manifest()
    identity_manifest["metadata_sha256"] = hashlib.sha256(original_bytes).hexdigest()
    identity_manifest_path = metadata_dir / "patient_identity_manifest.json"
    identity_manifest_path.write_text(json.dumps(identity_manifest), encoding="utf-8")
    monkeypatch.setattr(prepare_splits, "ROOT", tmp_path)
    output_dir = tmp_path / "output"

    prepare_splits.main(identity_manifest_path, output_dir)

    manifest = json.loads((output_dir / "de_cuong_split_manifest.json").read_text())
    canonical_manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["source_patient_identity_verified"] is True
    assert manifest["split_counts"] == {"train": 1, "val": 1, "test": 1}
    assert manifest["input_metadata_sha256"] == identity_manifest["metadata_sha256"]
    assert canonical_manifest["identity_manifest_sha256"] == hashlib.sha256(
        identity_manifest_path.read_bytes()
    ).hexdigest()
    assert canonical_manifest["source_metadata_path"] == "../metadata/kltn_ground_truth_307.csv"
    assert validate_training_split_identity(output_dir) == "patient_level_verified"
    assert "clinical_site" not in manifest
    assert source_csv.read_bytes() == original_bytes
    for split in ("train", "val", "test"):
        output_rows = pd.read_csv(output_dir / f"{split}.csv")
        assert len(output_rows) == 1
        assert len(output_rows.loc[0, "image_sha256"]) == 64
        assert len(output_rows.loc[0, "mask_sha256"]) == 64
