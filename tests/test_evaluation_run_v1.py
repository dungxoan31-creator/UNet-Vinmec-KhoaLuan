"""Tests for Reproducible Native-Space Evaluation Runner v1."""

import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
import pytest
import torch

from evaluation.run_evaluation import evaluate_run

ROOT = Path(__file__).resolve().parents[1]


class FakeParityEngine:
    """Mock engine that predicts specific mask patterns."""
    def __init__(self, mode="match"):
        self.mode = mode
        self.threshold = 0.5
        self.is_model_ready = True
        self.device = "cpu"

    def predict_binary(self, tensor_512: torch.Tensor) -> np.ndarray:
        # Return a known 512x512 pattern
        mask = np.zeros((512, 512), dtype=np.uint8)
        if self.mode == "match":
            # Mask on active middle area
            mask[100:400, 100:400] = 1
        elif self.mode == "empty":
            pass
        elif self.mode == "partial":
            mask[100:250, 100:400] = 1
        return mask


def _setup_three_case_fixture(tmp_path):
    root_dir = tmp_path / "repo"
    root_dir.mkdir(parents=True)
    images_dir = root_dir / "images"
    masks_dir = root_dir / "masks"
    images_dir.mkdir()
    masks_dir.mkdir()

    cases = []
    # 3 samples:
    # 1. perfect overlap
    # 2. partial overlap
    # 3. empty GT and empty Pred
    configs = [
        ("s1", "match", False),
        ("s2", "partial", False),
        ("s3", "empty", True),
    ]

    for sid, mode, is_empty in configs:
        img_arr = np.full((300, 400), 120, dtype=np.uint8)
        mask_arr = np.zeros((300, 400), dtype=np.uint8)
        if not is_empty:
            # GT inside letterboxed active region
            mask_arr[50:250, 50:350] = 255

        img_file = images_dir / f"{sid}.png"
        mask_file = masks_dir / f"{sid}_mask.png"
        cv2.imwrite(str(img_file), img_arr)
        cv2.imwrite(str(mask_file), mask_arr)

        cases.append({
            "sample_id": sid,
            "source_case_id": f"c_{sid}",
            "patient_id": f"p_{sid}",
            "split": "val",
            "modality": "2d",
            "image_path": str(img_file.relative_to(root_dir)).replace("\\", "/"),
            "mask_path": str(mask_file.relative_to(root_dir)).replace("\\", "/"),
            "image_sha256": hashlib.sha256(img_file.read_bytes()).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_file.read_bytes()).hexdigest(),
            "identity_evidence": "",
            "label_evidence": "",
            "development_history_evidence": ""
        })

    manifest_csv = root_dir / "manifest.csv"
    with open(manifest_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(cases[0].keys()))
        writer.writeheader()
        writer.writerows(cases)

    protocol_json = root_dir / "protocol.json"
    proto_data = {
        "schema_version": 1,
        "protocol_id": "test_proto",
        "run_kinds": ["validation_dry_run", "retrospective_test_replay", "independent_test"],
        "model": {
            "architecture": "standard_unet",
            "checkpoint_path": "dummy.pth",
            "strict_load": False
        },
        "preprocess": {
            "color_mode": "grayscale",
            "target_size": [512, 512],
            "clahe": {"clip_limit": 2.0, "tile_grid_size": [8, 8]},
            "normalization": "scale_255",
            "data_type": "float32"
        },
        "inference": {
            "device": "cpu",
            "batch_size": 1,
            "threshold": 0.5,
            "operator": ">=",
            "mode": "eval"
        },
        "postprocess": {"morphology": None, "remove_small_components": False},
        "evaluation": {
            "coordinate_space": "native",
            "interpolation": "nearest",
            "bootstrap_seed": 42
        }
    }
    protocol_json.write_text(json.dumps(proto_data), encoding="utf-8")

    return root_dir, protocol_json, manifest_csv


def test_pipeline_three_case_oracle(tmp_path):
    root_dir, protocol_json, manifest_csv = _setup_three_case_fixture(tmp_path)
    output_dir = tmp_path / "output_run"

    res = evaluate_run(
        root=root_dir,
        protocol_path=protocol_json,
        manifest_path=manifest_csv,
        output=output_dir,
        run_kind="validation_dry_run",
        engine=FakeParityEngine(mode="match")
    )

    assert res["status"] == "COMPLETE"
    assert (output_dir / "run_manifest.json").exists()
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "per_image_metrics.csv").exists()
    assert (output_dir / "predictions" / "s1.png").exists()

    # Verify native shape of predictions
    pred1 = cv2.imread(str(output_dir / "predictions" / "s1.png"), cv2.IMREAD_GRAYSCALE)
    assert pred1.shape == (300, 400), "Prediction must be in native image shape"


def test_no_overwrite(tmp_path):
    root_dir, protocol_json, manifest_csv = _setup_three_case_fixture(tmp_path)
    output_dir = tmp_path / "output_run"
    output_dir.mkdir(parents=True)
    (output_dir / "existing_file.txt").write_text("hello")

    with pytest.raises(FileExistsError, match="exists|overwrite"):
        evaluate_run(
            root=root_dir,
            protocol_path=protocol_json,
            manifest_path=manifest_csv,
            output=output_dir,
            run_kind="validation_dry_run",
            engine=FakeParityEngine(mode="match")
        )


def test_partial_run_never_published(tmp_path):
    root_dir, protocol_json, manifest_csv = _setup_three_case_fixture(tmp_path)
    output_dir = tmp_path / "output_run"

    class FailingEngine:
        def __init__(self):
            self.calls = 0
            self.threshold = 0.5
            self.is_model_ready = True
            self.device = "cpu"

        def predict_binary(self, tensor_512):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("Inference crash on sample 2")
            return np.zeros((512, 512), dtype=np.uint8)

    with pytest.raises(RuntimeError, match="Inference crash"):
        evaluate_run(
            root=root_dir,
            protocol_path=protocol_json,
            manifest_path=manifest_csv,
            output=output_dir,
            run_kind="validation_dry_run",
            engine=FailingEngine()
        )

    # Check status is PARTIAL or FAILED, not COMPLETE
    manifest_data = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["status"] in {"PARTIAL", "FAILED"}


def test_changed_protocol_or_manifest_rejected_by_lock(tmp_path):
    from evaluation.run_evaluation import freeze_protocol
    root_dir, protocol_json, manifest_csv = _setup_three_case_fixture(tmp_path)
    lock_dir = tmp_path / "lock_dir"
    freeze_protocol(protocol_json, manifest_csv, lock_dir, prior_test_access=False)

    lock_file = lock_dir / "protocol_lock.json"
    assert lock_file.exists()

    # Tamper with protocol
    tampered_proto = json.loads(protocol_json.read_text(encoding="utf-8"))
    tampered_proto["inference"]["threshold"] = 0.4
    protocol_json.write_text(json.dumps(tampered_proto), encoding="utf-8")

    engine = FakeParityEngine()
    output_dir = tmp_path / "output_tampered"
    with pytest.raises(ValueError, match="lock mismatch"):
        evaluate_run(
            root=root_dir,
            protocol_path=protocol_json,
            manifest_path=manifest_csv,
            output=output_dir,
            run_kind="validation_dry_run",
            engine=engine,
            lock_path=lock_file
        )


def test_prior_test_access_prevents_independent_label(tmp_path):
    from evaluation.run_evaluation import freeze_protocol
    root_dir, protocol_json, manifest_csv = _setup_three_case_fixture(tmp_path)
    lock_dir = tmp_path / "lock_dir_prior"
    freeze_protocol(protocol_json, manifest_csv, lock_dir, prior_test_access=True)

    lock_file = lock_dir / "protocol_lock.json"
    output_dir = tmp_path / "output_prior"
    engine = FakeParityEngine()

    with pytest.raises(ValueError, match="Prior test access"):
        evaluate_run(
            root=root_dir,
            protocol_path=protocol_json,
            manifest_path=manifest_csv,
            output=output_dir,
            run_kind="independent_test",
            engine=engine,
            lock_path=lock_file
        )

