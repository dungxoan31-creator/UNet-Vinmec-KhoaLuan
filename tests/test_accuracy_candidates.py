"""Validation-only candidate scoring and TTA alignment checks."""

import hashlib
import json

import numpy as np
import pytest
import torch

from scripts.evaluate_accuracy_candidates import (
    aggregate_candidates,
    create_output_directory,
    evaluate,
    predict_native_and_flip,
    score_probabilities,
    validate_inputs,
)


def test_score_probabilities_applies_threshold_to_reference_pixels():
    probabilities = np.array([[0.4, 0.6]], dtype=np.float32)
    reference = np.array([[0, 1]], dtype=np.uint8)

    assert score_probabilities(probabilities, reference, 0.5)["dice"] == pytest.approx(1.0)
    missed = score_probabilities(probabilities, reference, 0.7)
    assert missed["dice"] == 0.0
    assert missed["recall"] == 0.0


def test_score_probabilities_keeps_empty_reference_explicit():
    reference = np.zeros((2, 2), dtype=np.uint8)
    assert score_probabilities(np.zeros((2, 2)), reference, 0.5)["dice"] == 1.0
    false_positive = score_probabilities(np.ones((2, 2)), reference, 0.5)
    assert false_positive["dice"] == 0.0
    assert false_positive["is_empty"] is True


def test_flip_tta_aligns_predictions_back_to_native_orientation():
    class IdentityLogits(torch.nn.Module):
        def forward(self, images):
            return images

    images = torch.tensor([[[[-2.0, 2.0]]]])
    native, averaged = predict_native_and_flip(IdentityLogits(), images, "cpu")
    np.testing.assert_allclose(native, averaged, atol=1e-7)
    assert native[0, 0, 0] < native[0, 0, 1]


def test_validate_inputs_rejects_checkpoint_and_validation_hash_mismatch(tmp_path):
    checkpoint = tmp_path / "best.pth"
    validation = tmp_path / "val.csv"
    checkpoint.write_bytes(b"locked weights")
    validation.write_bytes(b"frozen validation")
    lock = {
        "checkpoint": "best.pth",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "split_hashes": {"val.csv": hashlib.sha256(validation.read_bytes()).hexdigest()},
    }
    assert validate_inputs(tmp_path, lock, validation) == checkpoint

    checkpoint.write_bytes(b"changed weights")
    with pytest.raises(ValueError, match="checkpoint"):
        validate_inputs(tmp_path, lock, validation)
    checkpoint.write_bytes(b"locked weights")
    validation.write_bytes(b"changed validation")
    with pytest.raises(ValueError, match="Validation"):
        validate_inputs(tmp_path, lock, validation)


def test_create_output_directory_never_overwrites_existing_artifacts(tmp_path):
    output = tmp_path / "candidates"
    create_output_directory(output)
    (output / "summary.json").write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        create_output_directory(output)
    assert (output / "summary.json").read_text(encoding="utf-8") == "existing"


def test_aggregate_candidates_uses_mean_per_image_and_counts_low_dice():
    rows = [
        {"candidate": "native", "threshold": 0.5, "dice": 1.0, "iou": 1.0, "recall": 1.0, "precision": 1.0},
        {"candidate": "native", "threshold": 0.5, "dice": 0.2, "iou": 0.1, "recall": 0.4, "precision": 0.3},
    ]
    result = aggregate_candidates(rows)
    assert result == [{
        "candidate": "native",
        "threshold": 0.5,
        "count": 2,
        "dice": 0.6,
        "iou": 0.55,
        "recall": 0.7,
        "precision": 0.65,
        "dice_below_0_5": 1,
    }]


def test_evaluate_rejects_failed_data_audit_before_creating_output(tmp_path):
    audit = tmp_path / "dataset_audit.json"
    audit.write_text(json.dumps({"errors": [{"sample_id": "x"}], "verified_readable_pairs": 0, "canonical_samples": 1}), encoding="utf-8")
    output = tmp_path / "candidates"
    with pytest.raises(ValueError, match="audit"):
        evaluate(tmp_path, tmp_path / "lock.json", tmp_path / "val.csv", audit, output)
    assert not output.exists()
