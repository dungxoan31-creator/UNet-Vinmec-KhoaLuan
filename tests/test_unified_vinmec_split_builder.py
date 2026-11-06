import csv

import pytest

from scripts import build_unified_vinmec_splits as split_builder
from scripts.build_unified_vinmec_splits import _write_csv, assign_split


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ({"train"}, "train"),
        ({"train", "val"}, "val"),
        ({"train", "val", "test"}, "test"),
        ({"test", "val"}, "test"),
    ],
)
def test_conflicting_split_evidence_never_moves_test_or_validation_to_train(evidence, expected):
    assert assign_split(evidence) == expected


def test_split_assignment_rejects_missing_evidence():
    with pytest.raises(ValueError, match="No recognized split evidence"):
        assign_split(set())


def test_csv_projection_ignores_non_loader_provenance_fields(tmp_path):
    path = tmp_path / "train.csv"
    _write_csv(path, [{"case_id": "sample", "image_path": "i.png", "provenance": "source"}], ("case_id", "image_path"))
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == [{"case_id": "sample", "image_path": "i.png"}]


def test_unverified_source_identity_never_marks_manifest_ready_for_training(tmp_path, monkeypatch):
    source_row = {
        "status": "matched",
        "image_sha256": "a" * 64,
        "dataset": "Vinmec",
        "image_path": "images/sample.png",
        "mask_path": "masks/sample.png",
        "annotation_path": "",
        "label_path": "",
        "target_role": "annotation",
        "split_evidence": "train",
    }
    monkeypatch.setattr(split_builder, "_read_audit_rows", lambda _root: [source_row])
    monkeypatch.setattr(split_builder, "_fallback_image_hashes", lambda _root: set())
    monkeypatch.setattr(split_builder, "_target_signature", lambda _root, _row: "binary-target")

    split_dir = tmp_path / "splits"
    summary = split_builder.build(tmp_path, split_dir, tmp_path / "index.csv")

    assert summary["status"] == "blocked_unverified_patient_identity"
    assert summary["source_patient_identity_verified"] is False
    assert summary["patient_level_independence_verified"] is False
    assert "blocked" in summary["training_test_policy"].lower()
