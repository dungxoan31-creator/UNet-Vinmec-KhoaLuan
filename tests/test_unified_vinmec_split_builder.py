import csv

import pytest

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
