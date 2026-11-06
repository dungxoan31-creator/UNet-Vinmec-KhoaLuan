import hashlib
import json

import numpy as np
import pytest
import torch

import scripts.evaluate_unified_vinmec as evaluator
import scripts.render_unified_vinmec_error_analysis as error_renderer
from scripts.evaluate_unified_vinmec import summarize_samples


def test_summary_keeps_empty_masks_separate_from_lesion_segmentation_metrics():
    samples = [
        {"dice": 0.5, "iou": 0.3, "recall": 0.6, "precision": 0.7, "specificity": 0.8, "is_empty": False},
        {"dice": 0.0, "iou": 0.0, "recall": 1.0, "precision": 0.0, "specificity": 0.9, "is_empty": True},
    ]
    summary = summarize_samples(samples)
    assert summary["total_cases_evaluated"] == 2
    assert summary["lesion_cases_count"] == 1
    assert summary["empty_mask_cases_count"] == 1
    assert summary["foreground_dice_mean"] == 0.5
    assert summary["empty_mask_specificity"] == 0.9


def test_evaluation_writes_only_to_requested_output_and_preserves_split_index(tmp_path, monkeypatch):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    dataset_dir = root / "dataset"
    dataset_dir.mkdir()
    image_path = dataset_dir / "image.png"
    mask_path = dataset_dir / "mask.png"
    import cv2

    cv2.imwrite(str(image_path), np.zeros((16, 16), dtype=np.uint8))
    cv2.imwrite(str(mask_path), np.zeros((16, 16), dtype=np.uint8))
    case_id = "../../outside"
    (split_dir / "test.csv").write_text(f"case_id,image_path,mask_path\n{case_id},image.png,mask.png\n")
    original_index = "canonical index must remain untouched\n"
    original_samples = (
        "sample_id,case_id,image_path,mask_path,source_datasets,image_sha256\n"
        f"{case_id},{case_id},dataset/image.png,dataset/mask.png,Mock,sha-case-a\n"
    )
    (root / "dataset" / "index.csv").write_text(original_index)
    (split_dir / "all_samples.csv").write_text(original_samples)

    checkpoint_dir = root / "checkpoints" / "candidate"
    checkpoint_dir.mkdir(parents=True)
    checkpoint = checkpoint_dir / "best.pth"
    checkpoint.write_bytes(b"checkpoint")
    manifest = {
        "source_patient_identity_verified": True,
        "patient_ids_verified": True,
        "identity_level": "patient_verified",
        "split_counts": {name: 1 for name in ("train", "val", "test")},
    }
    manifest_path = split_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (checkpoint_dir / "run_config.json").write_text(json.dumps({
        "best_epoch": 7,
        "split_identity_status": "patient_level_verified",
        "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "split_sha256": {
            "test": hashlib.sha256((split_dir / "test.csv").read_bytes()).hexdigest(),
        },
        "test_split_image_data_used": False,
        "checkpoint_best": str(checkpoint.resolve()),
        "checkpoint_best_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    }), encoding="utf-8")

    class FakeDataset:
        def __init__(self, *_args, **_kwargs):
            pass

        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return {
                "image": torch.zeros(1, 16, 16),
                "mask": torch.zeros(1, 16, 16),
                "case_id": case_id,
                "image_path": str(image_path),
            }

    class FakeModel(torch.nn.Module):
        def load_state_dict(self, _state, strict=True):
            assert strict is True

        def forward(self, images):
            return torch.full_like(images, -10.0)

    class FakeLoader:
        def __init__(self, *_args, **_kwargs):
            pass

        def __iter__(self):
            yield {
                "image": torch.zeros(1, 1, 16, 16),
                "mask": torch.zeros(1, 1, 16, 16),
                "case_id": [case_id],
            }

    monkeypatch.setattr(evaluator, "OvarianUltrasoundDataset", FakeDataset)
    monkeypatch.setattr(evaluator, "DataLoader", FakeLoader)
    monkeypatch.setattr(evaluator, "StandardUNet", lambda **_kwargs: FakeModel())
    monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "patient_level_verified", raising=False)
    monkeypatch.setattr(torch, "load", lambda *_args, **_kwargs: {})
    output_dir = root / "evaluation" / "milestone_3"

    summary = evaluator.evaluate(root, split_dir, checkpoint, output_dir)

    assert summary["checkpoint"] == "checkpoints/candidate/best.pth"
    assert summary["patient_level_independence_verified"] is True
    assert summary["identity_level"] == "patient-level"
    assert summary["test_inference_performed"] is True
    assert summary["test_split_image_data_used"] is False
    assert summary["test_csv_sha256"] == hashlib.sha256((split_dir / "test.csv").read_bytes()).hexdigest()
    assert summary["split_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert summary["run_config_sha256"] == hashlib.sha256(
        (checkpoint_dir / "run_config.json").read_bytes()
    ).hexdigest()
    safe_prediction = f"0001_{hashlib.sha256(case_id.encode()).hexdigest()[:16]}.png"
    assert (output_dir / "predictions" / safe_prediction).is_file()
    assert not (root / "evaluation" / "outside.png").exists()
    assert (output_dir / "test_summary.json").is_file()
    assert (root / "dataset" / "index.csv").read_text() == original_index
    assert (split_dir / "all_samples.csv").read_text() == original_samples


def test_error_renderer_rejects_historical_image_level_test_summary_before_loading_dataset(
    tmp_path, monkeypatch
):
    evaluation_dir = tmp_path / "evaluation" / "unified_vinmec_2026-10-06"
    evaluation_dir.mkdir(parents=True)
    (evaluation_dir / "test_summary.json").write_text(json.dumps({
        "identity_level": "image-level; source Patient/Case IDs unavailable",
        "top_5_best_cases": [],
        "top_5_error_cases_fp_fn": [],
    }), encoding="utf-8")
    output = tmp_path / "error-sheet.png"

    monkeypatch.setattr(
        error_renderer,
        "OvarianUltrasoundDataset",
        lambda *_args, **_kwargs: pytest.fail("Test dataset loaded before its identity gate"),
    )

    with pytest.raises(ValueError, match="(?i)patient-level"):
        error_renderer.render(tmp_path, output)

    assert not output.exists()


def test_error_renderer_rechecks_split_identity_even_if_summary_claims_patient_level(
    tmp_path, monkeypatch
):
    evaluation_dir = tmp_path / "evaluation" / "unified_vinmec_2026-10-06"
    evaluation_dir.mkdir(parents=True)
    (evaluation_dir / "test_summary.json").write_text(json.dumps({
        "identity_level": "patient-level",
        "patient_level_independence_verified": True,
        "test_inference_performed": True,
        "test_split_image_data_used": False,
        "top_5_best_cases": [],
        "top_5_error_cases_fp_fn": [],
    }), encoding="utf-8")
    output = tmp_path / "error-sheet.png"
    monkeypatch.setattr(error_renderer, "validate_training_split_identity", lambda _path: "image_level_only", raising=False)
    monkeypatch.setattr(
        error_renderer,
        "OvarianUltrasoundDataset",
        lambda *_args, **_kwargs: pytest.fail("Test dataset loaded despite an unverified split"),
    )

    with pytest.raises(ValueError, match="(?i)patient-level"):
        error_renderer.render(tmp_path, output)

    assert not output.exists()


def test_error_renderer_rejects_summary_bound_to_stale_test_csv(tmp_path, monkeypatch):
    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    test_csv = split_dir / "test.csv"
    test_csv.write_text("case_id,image_path,mask_path\ncase-1,image.png,mask.png\n", encoding="utf-8")
    manifest = split_dir / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    checkpoint = tmp_path / "candidate.pth"
    checkpoint.write_bytes(b"checkpoint")
    run_config = tmp_path / "run_config.json"
    run_config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(error_renderer, "validate_training_split_identity", lambda _path: "patient_level_verified")

    with pytest.raises(ValueError, match="(?i)current split artifacts"):
        error_renderer._validate_test_artifacts(tmp_path, split_dir, {
            "identity_level": "patient-level",
            "patient_level_independence_verified": True,
            "source_patient_identity_verified": True,
            "test_inference_performed": True,
            "test_split_image_data_used": False,
            "test_csv_sha256": "0" * 64,
            "split_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "checkpoint": "candidate.pth",
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "run_config_sha256": hashlib.sha256(run_config.read_bytes()).hexdigest(),
        })


def test_evaluation_rejects_empty_test_split_before_model_load(tmp_path, monkeypatch):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    (split_dir / "test.csv").write_text("case_id,image_path,mask_path\n", encoding="utf-8")
    (split_dir / "all_samples.csv").write_text(
        "case_id,image_path,mask_path,source_datasets,image_sha256\n", encoding="utf-8"
    )
    checkpoint = root / "candidate.pth"
    checkpoint.write_bytes(b"checkpoint")
    output_dir = root / "evaluation" / "empty"

    class EmptyDataset:
        def __init__(self, *_args, **_kwargs):
            pass

        def __len__(self):
            return 0

    monkeypatch.setattr(evaluator, "_verified_run_config", lambda *_args: {"best_epoch": 1})
    monkeypatch.setattr(evaluator, "OvarianUltrasoundDataset", EmptyDataset)
    monkeypatch.setattr(
        evaluator,
        "StandardUNet",
        lambda **_kwargs: pytest.fail("model initialized for an empty Test split"),
    )

    with pytest.raises(ValueError, match="(?i)test split must not be empty"):
        evaluator.evaluate(root, split_dir, checkpoint, output_dir)

    assert not output_dir.exists()


def test_evaluation_blocks_unverified_patient_identity_before_loading_data(tmp_path, monkeypatch):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    (split_dir / "test.csv").write_text("case_id,image_path,mask_path\n", encoding="utf-8")
    (split_dir / "all_samples.csv").write_text("case_id,image_path,mask_path,source_datasets,image_sha256\n", encoding="utf-8")
    checkpoint = root / "candidate.pth"
    checkpoint.write_bytes(b"checkpoint")
    output_dir = root / "evaluation" / "blocked"

    monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "image_level_only", raising=False)
    monkeypatch.setattr(
        evaluator,
        "OvarianUltrasoundDataset",
        lambda *_args, **_kwargs: pytest.fail("dataset loaded before patient identity gate"),
    )

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        evaluator.evaluate(root, split_dir, checkpoint, output_dir)

    assert not output_dir.exists()


def test_evaluation_rejects_checkpoint_hash_mismatch_before_loading_data(tmp_path, monkeypatch):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    test_csv = split_dir / "test.csv"
    test_csv.write_text("case_id,image_path,mask_path\n", encoding="utf-8")
    (split_dir / "all_samples.csv").write_text("case_id,image_path,mask_path,source_datasets,image_sha256\n", encoding="utf-8")
    manifest_path = split_dir / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    checkpoint_dir = root / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint = checkpoint_dir / "best.pth"
    checkpoint.write_bytes(b"checkpoint")
    (checkpoint_dir / "run_config.json").write_text(json.dumps({
        "best_epoch": 7,
        "split_identity_status": "patient_level_verified",
        "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "split_sha256": {"test": hashlib.sha256(test_csv.read_bytes()).hexdigest()},
        "test_split_image_data_used": False,
        "checkpoint_best": str(checkpoint.resolve()),
        "checkpoint_best_sha256": "0" * 64,
    }), encoding="utf-8")
    output_dir = root / "evaluation" / "blocked"

    monkeypatch.setattr(evaluator, "validate_training_split_identity", lambda _path: "patient_level_verified", raising=False)
    monkeypatch.setattr(
        evaluator,
        "OvarianUltrasoundDataset",
        lambda *_args, **_kwargs: pytest.fail("dataset loaded before checkpoint provenance gate"),
    )

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        evaluator.evaluate(root, split_dir, checkpoint, output_dir)

    assert not output_dir.exists()


@pytest.mark.parametrize("threshold", [None, float("nan"), float("inf"), -0.1, 0.0, 1.0, 1.1])
def test_evaluation_rejects_invalid_threshold(tmp_path, threshold):
    with pytest.raises(ValueError, match="(?i)threshold"):
        evaluator.evaluate(
            tmp_path,
            tmp_path / "splits",
            tmp_path / "candidate.pth",
            tmp_path / "evaluation" / "run",
            threshold=threshold,
        )


@pytest.mark.parametrize("batch_size", [None, 0, -1, 1.5, True])
def test_evaluation_rejects_invalid_batch_size(tmp_path, batch_size):
    with pytest.raises(ValueError, match="(?i)batch_size"):
        evaluator.evaluate(
            tmp_path,
            tmp_path / "splits",
            tmp_path / "candidate.pth",
            tmp_path / "evaluation" / "run",
            batch_size=batch_size,
        )


def test_evaluation_refuses_to_overwrite_existing_artifacts(tmp_path):
    output_dir = tmp_path / "evaluation" / "locked"
    output_dir.mkdir(parents=True)
    (output_dir / "test_summary.json").write_text("historical evidence")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        evaluator.evaluate(tmp_path, tmp_path / "splits", tmp_path / "candidate.pth", output_dir)
