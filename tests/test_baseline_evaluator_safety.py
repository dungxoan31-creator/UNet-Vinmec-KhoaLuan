import hashlib
import json

import cv2
import numpy as np
import pytest
import torch

from evaluation import evaluate_baseline_testset as evaluator
from tests.patient_split_fixture import attach_source_identity_evidence


class EmptyModel(torch.nn.Module):
    def forward(self, inputs):
        return torch.zeros(
            (inputs.shape[0], 1, inputs.shape[-2], inputs.shape[-1]),
            dtype=inputs.dtype,
            device=inputs.device,
        )


def _prepare_evaluation(tmp_path, monkeypatch, *, verified=True, mask_kind="valid", image_exists=True):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    manifest = {
        "source_patient_identity_verified": verified,
        "patient_ids_verified": verified,
        "identity_level": "patient_verified" if verified else "image_level_only",
        "split_counts": {name: 1 for name in ("train", "val", "test")},
    }
    manifest_path = split_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    image = np.full((24, 32), 90, dtype=np.uint8)
    mask = np.zeros_like(image)
    image_path = root / "image.png"
    mask_path = root / "mask.png"
    if mask_kind == "valid":
        assert cv2.imwrite(str(mask_path), mask)
    elif mask_kind == "mismatch":
        assert cv2.imwrite(str(mask_path), np.zeros((24, 31), dtype=np.uint8))
    elif mask_kind == "invalid_values":
        assert cv2.imwrite(str(mask_path), np.full_like(image, 42))

    for index, name in enumerate(("train", "val", "test")):
        split_image = image_path if name == "test" else root / f"{name}.png"
        split_mask = mask_path if name == "test" else root / f"{name}_mask.png"
        split_pixels = image if name == "test" else np.full_like(image, 91 + index)
        encoded_image = cv2.imencode(".png", split_pixels)[1].tobytes()
        if image_exists or name != "test":
            split_image.write_bytes(encoded_image)
        if name != "test":
            assert cv2.imwrite(str(split_mask), np.zeros_like(mask))
        split_hash = hashlib.sha256(encoded_image).hexdigest()
        split_mask_hash = (
            hashlib.sha256(split_mask.read_bytes()).hexdigest()
            if split_mask.is_file()
            else "0" * 64
        )
        (split_dir / f"{name}.csv").write_text(
            "patient_id,image_sha256,mask_sha256,case_id,image_path,mask_path,is_empty_mask\n"
            f"P-{name},{split_hash},{split_mask_hash},case-{name},{split_image},{split_mask},False\n",
            encoding="utf-8",
        )

    test_csv = split_dir / "test.csv"
    checkpoint_dir = root / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint = checkpoint_dir / "baseline_unet_best.pth"
    torch.save({}, checkpoint)
    if verified:
        attach_source_identity_evidence(split_dir)
    run_config = {
        "split_identity_status": "patient_level_verified" if verified else "image_level_only",
        "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "test_split_image_data_used": False,
        "checkpoint_best": str(checkpoint.resolve()),
        "checkpoint_best_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    }
    (checkpoint_dir / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")

    monkeypatch.setattr(evaluator, "ROOT", root, raising=False)
    monkeypatch.setattr(evaluator, "StandardUNet", lambda **kwargs: EmptyModel())
    return {
        "checkpoint_path": checkpoint,
        "test_csv": test_csv,
        "output_metrics": root / "out" / "metrics.json",
        "vis_dir": root / "out" / "visualizations",
    }


def test_baseline_evaluator_blocks_unverified_patient_identity_before_writing(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch, verified=False)

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        evaluator.evaluate_test_set(**args)

    assert not args["output_metrics"].exists()
    assert not args["vis_dir"].exists()


def test_baseline_evaluator_requires_checkpoint_run_provenance(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch)
    (args["checkpoint_path"].parent / "run_config.json").unlink()

    with pytest.raises(ValueError, match="checkpoint provenance"):
        evaluator.evaluate_test_set(**args)

    assert not args["output_metrics"].exists()
    assert not args["vis_dir"].exists()


def test_baseline_evaluator_checks_checkpoint_hash_and_uses_safe_loading(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch)
    original_load = torch.load
    load_options = []

    def safe_load(*load_args, **load_kwargs):
        load_options.append(load_kwargs.get("weights_only"))
        return original_load(*load_args, **load_kwargs)

    monkeypatch.setattr(evaluator.torch, "load", safe_load)
    summary = evaluator.evaluate_test_set(**args)

    assert load_options == [True]
    assert summary["evaluation_scope"] == "retrospective_test_replay"
    assert summary["patient_independence_verified"] is True
    assert summary["label_provenance_verified"] is False
    assert args["output_metrics"].is_file()


def test_baseline_evaluator_does_not_trust_label_verification_flag_without_evidence(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch)
    manifest_path = args["test_csv"].parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["label_provenance_verified"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config_path = args["checkpoint_path"].parent / "run_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["split_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    config_path.write_text(json.dumps(config), encoding="utf-8")

    summary = evaluator.evaluate_test_set(**args)

    assert summary["label_provenance_verified"] is False


def test_baseline_evaluator_rejects_checkpoint_hash_mismatch(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch)
    args["checkpoint_path"].write_bytes(b"changed checkpoint")

    with pytest.raises(ValueError, match="patient-isolated run"):
        evaluator.evaluate_test_set(**args)

    assert not args["output_metrics"].exists()
    assert not args["vis_dir"].exists()


@pytest.mark.parametrize("mask_kind", ["missing", "mismatch", "invalid_values"])
def test_baseline_evaluator_rejects_missing_or_invalid_reference_mask(tmp_path, monkeypatch, mask_kind):
    args = _prepare_evaluation(tmp_path, monkeypatch, mask_kind=mask_kind)

    with pytest.raises(ValueError, match="mask"):
        evaluator.evaluate_test_set(**args)

    assert not args["output_metrics"].exists()
    assert not args["vis_dir"].exists()


def test_baseline_evaluator_rejects_unreadable_image_instead_of_skipping(tmp_path, monkeypatch):
    args = _prepare_evaluation(tmp_path, monkeypatch, image_exists=False)

    with pytest.raises(ValueError, match="image"):
        evaluator.evaluate_test_set(**args)

    assert not args["output_metrics"].exists()
    assert not args["vis_dir"].exists()
