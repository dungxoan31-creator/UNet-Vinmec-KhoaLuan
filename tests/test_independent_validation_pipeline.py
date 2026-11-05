import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

from backend.models.unet import StandardUNet


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_independent_validation.py"


def _write_split(split_dir, split, image_paths):
    path = split_dir / f"{split}.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "image_path", "mask_path"])
        writer.writeheader()
        for index, image_path in enumerate(image_paths):
            writer.writerow({
                "case_id": f"synthetic_{split}_{index}",
                "image_path": str(image_path),
                "mask_path": "",
            })
    return path


def _write_candidate(root, split_dir):
    checkpoint = root / "checkpoints" / "synthetic-candidate.pth"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(7)
    torch.save(StandardUNet(in_channels=1, num_classes=1, base_filters=32).state_dict(), checkpoint)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    split_hashes = {
        split: hashlib.sha256((split_dir / f"{split}.csv").read_bytes()).hexdigest()
        for split in ("train", "val", "test")
    }
    split_manifest = split_dir / "manifest.json"
    split_manifest.write_text(json.dumps({
        "deduplication": "SHA-256 of raw image bytes",
        "patient_level_independence_verified": False,
        "source_patient_identity_verified": False,
    }), encoding="utf-8")
    evidence_path = root / "training-evidence.json"
    evidence_path.write_text(json.dumps({
        "test_split_image_data_used": False,
        "split_sha256": split_hashes,
        "split_manifest_sha256": hashlib.sha256(split_manifest.read_bytes()).hexdigest(),
        "checkpoint_best_sha256": checkpoint_hash,
    }), encoding="utf-8")
    selected_path = root / "selected_model.json"
    selected_path.write_text(json.dumps({
        "architecture": "standard_unet",
        "model_version": "synthetic-test-only",
        "checkpoint": checkpoint.relative_to(root).as_posix(),
        "checkpoint_sha256": checkpoint_hash,
        "threshold": 0.4,
        "horizontal_flip_tta": True,
        "input_normalization": {"mean": 0.0, "std": 1.0},
        "selection_split": "val",
        "selection_is_validation_tuned": True,
        "test_evaluation": None,
        "candidate_only": True,
        "independent_gate_status": "BLOCKED",
        "training_evidence": evidence_path.relative_to(root).as_posix(),
    }), encoding="utf-8")
    return selected_path.read_bytes()


def _run(root, split_dir, selected_path, output):
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root", str(root),
            "--split-dir", str(split_dir),
            "--model-manifest", str(selected_path),
            "--output", str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_runner_blocks_duplicate_images_and_keeps_candidate_registry_unchanged(tmp_path):
    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    shared_image = tmp_path / "shared.bin"
    shared_image.write_bytes(b"same raw ultrasound image")
    validation_image = tmp_path / "validation.bin"
    validation_image.write_bytes(b"different image")
    _write_split(split_dir, "train", [shared_image])
    _write_split(split_dir, "val", [validation_image])
    _write_split(split_dir, "test", [shared_image])
    (split_dir / "manifest.json").write_text(json.dumps({
        "deduplication": "SHA-256 of raw image bytes",
        "patient_level_independence_verified": False,
        "source_patient_identity_verified": False,
    }), encoding="utf-8")
    selected_path = tmp_path / "selected_model.json"
    selected_path.write_text(json.dumps({"candidate_only": True}), encoding="utf-8")
    original_selection = selected_path.read_bytes()
    output = tmp_path / "artifacts" / "blocked.json"

    result = _run(tmp_path, split_dir, selected_path, output)

    assert result.returncode == 2, result.stdout + result.stderr
    assert output.is_file(), result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED_DUPLICATE_IMAGE"
    assert report["split_audit"]["cross_split_duplicate_counts"]["train_test"] == 1
    assert report["patient_level_independence_verified"] is False
    assert report["evidence_classification"] == "technical_benchmark_unverified_patient_id"
    assert selected_path.read_bytes() == original_selection


def test_runner_records_invalid_split_manifest_as_blocked(tmp_path):
    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    (split_dir / "manifest.json").write_text("[]", encoding="utf-8")
    selected_path = tmp_path / "selected_model.json"
    selected_path.write_text("{}", encoding="utf-8")
    output = tmp_path / "artifacts" / "blocked.json"

    result = _run(tmp_path, split_dir, selected_path, output)

    assert result.returncode == 2
    assert output.is_file()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED_SPLIT_PROVENANCE"
    assert report["benchmark_performed"] is False


def test_runner_evaluates_synthetic_candidate_as_technical_only_and_refuses_overwrite(tmp_path):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    images = []
    for split, value in (("train", 40), ("val", 80), ("test", 120)):
        image = np.full((32, 40), value, dtype=np.uint8)
        mask = np.zeros((32, 40), dtype=np.uint8)
        mask[8:20, 10:28] = 255
        image_path, mask_path = root / f"{split}.png", root / f"{split}-mask.png"
        assert cv2.imwrite(str(image_path), image)
        assert cv2.imwrite(str(mask_path), mask)
        images.append((split, image_path, mask_path))
    for split, image_path, _mask_path in images:
        _write_split(split_dir, split, [image_path])
    test_csv = split_dir / "test.csv"
    with test_csv.open(newline="", encoding="utf-8") as stream:
        test_rows = list(csv.DictReader(stream))
    test_rows[0]["mask_path"] = str(images[-1][2])
    with test_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "image_path", "mask_path"])
        writer.writeheader()
        writer.writerows(test_rows)
    selected_path = root / "selected_model.json"
    original_selection = _write_candidate(root, split_dir)
    output = root / "artifacts" / "technical-report.json"

    result = _run(root, split_dir, selected_path, output)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "TECHNICAL_BENCHMARK_ONLY"
    assert report["benchmark_performed"] is True
    assert report["patient_level_independence_verified"] is False
    assert report["source_patient_identity_verified"] is False
    assert report["test_split_not_used_claimed_by_training_config"] is True
    assert report["test_split_exposure_independently_verified"] is False
    assert report["evidence_classification"] == "technical_benchmark_unverified_patient_id"
    assert set(report["segmentation_metrics"]) == {"dice", "iou", "recall", "precision", "specificity"}
    calibration = report["pixel_probability_calibration"]
    assert calibration["scope"] == "segmentation pixel probabilities; not disease probability"
    assert sum(bucket["count"] for bucket in calibration["bins"]) == 512 * 512
    assert 0 <= calibration["brier_score"] <= 1
    assert report["model"]["candidate_only"] is True
    assert "patient_id" not in report
    assert selected_path.read_bytes() == original_selection

    report_bytes = output.read_bytes()
    rerun = _run(root, split_dir, selected_path, output)
    assert rerun.returncode == 2
    assert "Refusing to overwrite" in rerun.stderr
    assert output.read_bytes() == report_bytes
