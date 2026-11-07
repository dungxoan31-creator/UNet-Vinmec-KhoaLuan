"""Run a research-only, image-level benchmark without changing model selection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from ai_training.dataset_loader import OvarianUltrasoundDataset  # noqa: E402
from ai_training.metrics_clinical import compute_sample_clinical_metrics  # noqa: E402
from backend.services.inference_engine import InferenceEngine  # noqa: E402

SPLITS = ("train", "val", "test")
METRIC_NAMES = ("dice", "iou", "recall", "precision", "specificity")
CALIBRATION_BINS = 15


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the project root") from exc
    return resolved


def _resolve_data_path(root: Path, split_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    for base in (root, split_dir):
        candidate = base / path
        if candidate.is_file():
            return candidate.resolve()
    return (root / path).resolve()


def _audit_image_splits(root: Path, split_dir: Path) -> dict[str, Any]:
    split_hashes: dict[str, set[str]] = {name: set() for name in SPLITS}
    row_counts: dict[str, int] = {}
    missing_count = 0
    hash_mismatch_count = 0
    within_split_duplicate_counts = {name: 0 for name in SPLITS}

    for split in SPLITS:
        csv_path = split_dir / f"{split}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"Missing {split}.csv")
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if not rows or any(not row.get("image_path") for row in rows):
            raise ValueError(f"Invalid or empty {split}.csv")
        row_counts[split] = len(rows)
        for row in rows:
            image_path = _resolve_data_path(root, split_dir, row["image_path"])
            if not image_path.is_file():
                missing_count += 1
                continue
            image_hash = _sha256(image_path)
            stored_hash = (row.get("image_sha256") or "").strip().casefold()
            if stored_hash and stored_hash != image_hash:
                hash_mismatch_count += 1
            if image_hash in split_hashes[split]:
                within_split_duplicate_counts[split] += 1
            split_hashes[split].add(image_hash)

    cross_split_duplicate_counts = {
        "train_val": len(split_hashes["train"] & split_hashes["val"]),
        "train_test": len(split_hashes["train"] & split_hashes["test"]),
        "val_test": len(split_hashes["val"] & split_hashes["test"]),
    }
    return {
        "deduplication_basis": "recomputed SHA-256 of raw image bytes",
        "row_counts": row_counts,
        "hashes_verified": {split: len(values) for split, values in split_hashes.items()},
        "missing_image_count": missing_count,
        "stored_image_hash_mismatch_count": hash_mismatch_count,
        "within_split_duplicate_counts": within_split_duplicate_counts,
        "cross_split_duplicate_counts": cross_split_duplicate_counts,
        "cross_split_overlap_audit_complete": missing_count == 0 and hash_mismatch_count == 0,
        "patient_level_independence_verified": False,
    }


def _calibration_result(
    bin_count: np.ndarray,
    bin_probability_sum: np.ndarray,
    bin_positive_sum: np.ndarray,
    brier_sum: float,
    pixel_count: int,
) -> dict[str, Any]:
    bins = []
    for index, count in enumerate(bin_count):
        bins.append({
            "lower_bound": index / CALIBRATION_BINS,
            "upper_bound": (index + 1) / CALIBRATION_BINS,
            "count": int(count),
            "mean_predicted_probability": (
                float(bin_probability_sum[index] / count) if count else None
            ),
            "observed_positive_fraction": float(bin_positive_sum[index] / count) if count else None,
        })
    return {
        "scope": "segmentation pixel probabilities; not disease probability",
        "interpretation": "descriptive only; no independent clinical calibration validation",
        "brier_score": float(brier_sum / pixel_count),
        "pixel_count": pixel_count,
        "bins": bins,
    }


def _add_calibration(
    probabilities: np.ndarray,
    truth: np.ndarray,
    bin_count: np.ndarray,
    bin_probability_sum: np.ndarray,
    bin_positive_sum: np.ndarray,
) -> float:
    flattened_probability = np.clip(probabilities.astype(np.float64, copy=False).ravel(), 0.0, 1.0)
    flattened_truth = (truth.ravel() > 0).astype(np.float64, copy=False)
    bin_indices = np.minimum(
        (flattened_probability * CALIBRATION_BINS).astype(np.int64),
        CALIBRATION_BINS - 1,
    )
    bin_count += np.bincount(bin_indices, minlength=CALIBRATION_BINS)
    bin_probability_sum += np.bincount(
        bin_indices, weights=flattened_probability, minlength=CALIBRATION_BINS
    )
    bin_positive_sum += np.bincount(
        bin_indices, weights=flattened_truth, minlength=CALIBRATION_BINS
    )
    return float(np.square(flattened_probability - flattened_truth).sum())


def _base_report() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "BLOCKED",
        "benchmark_performed": False,
        "patient_level_independence_verified": False,
        "source_patient_identity_verified": False,
        "test_split_exposure_independently_verified": False,
        "test_split_not_used_claimed_by_training_config": False,
        "clinical_validation_claimed": False,
        "result_signature_status": "UNSIGNED",
        "independent_gate_status": "BLOCKED",
        "evidence_classification": "technical_benchmark_unverified_patient_id",
        "blockers": [],
    }


def run_validation(root: Path, split_dir: Path, model_manifest_path: Path) -> dict[str, Any]:
    report = _base_report()
    root = root.resolve()
    split_dir = _inside(root, split_dir, "split_dir")
    model_manifest_path = _inside(root, model_manifest_path, "model_manifest")

    split_manifest_path = split_dir / "manifest.json"
    try:
        split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(split_manifest, dict):
            raise ValueError("split manifest must be an object")
        if "sha-256" not in str(split_manifest.get("deduplication", "")).casefold():
            report["status"] = "BLOCKED_SPLIT_PROVENANCE"
            report["blockers"].append("SPLIT_SHA256_POLICY_MISSING")
            return report
        split_audit = _audit_image_splits(root, split_dir)
    except FileNotFoundError:
        report["status"] = "BLOCKED_MISSING_ASSETS"
        report["blockers"].append("SPLIT_OR_SOURCE_IMAGE_MISSING")
        return report
    except (OSError, json.JSONDecodeError, ValueError):
        report["status"] = "BLOCKED_SPLIT_PROVENANCE"
        report["blockers"].append("SPLIT_METADATA_INVALID")
        return report

    report["split_audit"] = split_audit
    if split_audit["missing_image_count"]:
        report["status"] = "BLOCKED_MISSING_ASSETS"
        report["blockers"].append("SOURCE_IMAGES_MISSING")
        return report
    if split_audit["stored_image_hash_mismatch_count"]:
        report["status"] = "BLOCKED_IMAGE_HASH_MISMATCH"
        report["blockers"].append("STORED_IMAGE_SHA256_MISMATCH")
        return report
    if any(split_audit["within_split_duplicate_counts"].values()) or any(
        split_audit["cross_split_duplicate_counts"].values()
    ):
        report["status"] = "BLOCKED_DUPLICATE_IMAGE"
        report["blockers"].append("IMAGE_SHA256_OVERLAP")
        return report

    try:
        selected = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        report["status"] = "BLOCKED_MODEL_MANIFEST"
        report["blockers"].append("MODEL_MANIFEST_UNREADABLE")
        return report
    if not isinstance(selected, dict):
        report["status"] = "BLOCKED_MODEL_MANIFEST"
        report["blockers"].append("MODEL_MANIFEST_INVALID")
        return report
    if selected.get("test_evaluation") is not None or selected.get("synthetic_test_benchmark"):
        report["status"] = "BLOCKED_TEST_HISTORY"
        report["blockers"].append("MODEL_OR_TEST_COHORT_HAS_PRIOR_TEST_BENCHMARK")
        return report
    if (
        selected.get("candidate_only") is not True
        or selected.get("selection_split") != "val"
        or selected.get("selection_is_validation_tuned") is not True
    ):
        report["status"] = "BLOCKED_SELECTION_PROVENANCE"
        report["blockers"].append("CANDIDATE_OR_VALIDATION_SELECTION_NOT_VERIFIED")
        return report

    checkpoint_value = selected.get("checkpoint")
    evidence_value = selected.get("training_evidence")
    if not isinstance(checkpoint_value, str) or not isinstance(evidence_value, str):
        report["status"] = "BLOCKED_CHECKPOINT_PROVENANCE"
        report["blockers"].append("CHECKPOINT_OR_TRAINING_EVIDENCE_MISSING")
        return report
    try:
        checkpoint = _inside(root, root / checkpoint_value, "checkpoint")
        evidence_path = _inside(root, root / evidence_value, "training_evidence")
        checkpoint_hash = _sha256(checkpoint)
        training_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if not isinstance(training_evidence, dict):
            raise ValueError("training evidence must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        report["status"] = "BLOCKED_CHECKPOINT_PROVENANCE"
        report["blockers"].append("CHECKPOINT_OR_TRAINING_EVIDENCE_UNAVAILABLE")
        return report

    expected_hash = selected.get("checkpoint_sha256")
    expected_split_hashes = training_evidence.get("split_sha256")
    split_hashes_match = isinstance(expected_split_hashes, dict) and all(
        expected_split_hashes.get(split) == _sha256(split_dir / f"{split}.csv")
        for split in SPLITS
    )
    manifest_hash_matches = training_evidence.get("split_manifest_sha256") == _sha256(split_manifest_path)
    checkpoint_hash_matches = (
        expected_hash == checkpoint_hash
        and training_evidence.get("checkpoint_best_sha256") == checkpoint_hash
    )
    if (
        training_evidence.get("test_split_image_data_used") is not False
        or not split_hashes_match
        or not manifest_hash_matches
        or not checkpoint_hash_matches
    ):
        report["status"] = "BLOCKED_CHECKPOINT_PROVENANCE"
        report["blockers"].append("TRAINING_EVIDENCE_DOES_NOT_LOCK_THIS_TEST_SPLIT_AND_CHECKPOINT")
        return report

    try:
        architecture = selected.get("architecture")
        input_normalization = selected.get("input_normalization", {})
        horizontal_flip_tta = selected.get("horizontal_flip_tta", False)
        if not isinstance(architecture, str) or not architecture.strip():
            raise ValueError("invalid model architecture")
        if not isinstance(input_normalization, dict) or type(horizontal_flip_tta) is not bool:
            raise ValueError("invalid inference protocol")
        threshold = float(selected["threshold"])
        if not math.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError("invalid threshold")
        engine = InferenceEngine(
            model_weights_path=str(checkpoint),
            device="cpu",
            threshold=threshold,
            architecture=architecture,
            input_normalization=input_normalization,
            horizontal_flip_tta=horizontal_flip_tta,
            expected_checkpoint_sha256=expected_hash,
            model_version=selected.get("model_version"),
        )
        if not engine.is_model_ready:
            raise RuntimeError("selected checkpoint did not load")
        dataset = OvarianUltrasoundDataset(str(split_dir / "test.csv"), is_train=False)
        if len(dataset) == 0:
            raise ValueError("test split is empty")

        sample_metrics = []
        bin_count = np.zeros(CALIBRATION_BINS, dtype=np.int64)
        bin_probability_sum = np.zeros(CALIBRATION_BINS, dtype=np.float64)
        bin_positive_sum = np.zeros(CALIBRATION_BINS, dtype=np.float64)
        brier_sum = 0.0
        pixel_count = 0
        with torch.inference_mode():
            for index in range(len(dataset)):
                sample = dataset[index]
                tensor = sample["image"].unsqueeze(0)
                truth = (sample["mask"].squeeze(0).numpy() > 0.5).astype(np.uint8)
                probabilities = np.asarray(engine.forward_probabilities(tensor), dtype=np.float32)
                if probabilities.shape != truth.shape or not np.isfinite(probabilities).all():
                    raise ValueError("invalid model probability map")
                prediction = (probabilities >= threshold).astype(np.uint8)
                sample_metrics.append(compute_sample_clinical_metrics(prediction, truth))
                brier_sum += _add_calibration(
                    probabilities, truth, bin_count, bin_probability_sum, bin_positive_sum
                )
                pixel_count += int(probabilities.size)
        report.update({
            "status": "TECHNICAL_BENCHMARK_ONLY",
            "benchmark_performed": True,
            "test_split_not_used_claimed_by_training_config": True,
            "model": {
                "architecture": selected["architecture"],
                "model_version": selected.get("model_version"),
                "checkpoint_sha256": checkpoint_hash,
                "candidate_only": True,
                "threshold": threshold,
                "horizontal_flip_tta": horizontal_flip_tta,
                "registry_updated": False,
            },
            "test_sample_count": len(sample_metrics),
            "metric_level": "image-level pixel segmentation; not patient-level or diagnostic performance",
            "segmentation_metrics": {
                name: float(statistics.fmean(sample[name] for sample in sample_metrics))
                for name in METRIC_NAMES
            },
            "pixel_probability_calibration": _calibration_result(
                bin_count, bin_probability_sum, bin_positive_sum, brier_sum, pixel_count
            ),
        })
        return report
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        report["status"] = "BLOCKED_INFERENCE"
        report["blockers"].append("INFERENCE_OR_TEST_LABELS_INVALID")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--split-dir", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"))
    parser.add_argument("--model-manifest", type=Path, default=Path("evaluation/selected_model.json"))
    parser.add_argument("--output", required=True, type=Path, help="New JSON path inside root; existing files are refused")
    args = parser.parse_args()
    root = args.root.resolve()
    split_dir = args.split_dir if args.split_dir.is_absolute() else root / args.split_dir
    model_manifest = args.model_manifest if args.model_manifest.is_absolute() else root / args.model_manifest
    try:
        output = _inside(root, args.output if args.output.is_absolute() else root / args.output, "output")
    except ValueError as exc:
        parser.error(str(exc))
    if output.exists():
        parser.error(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        report = run_validation(root, split_dir, model_manifest)
    except ValueError:
        report = _base_report()
        report["status"] = "BLOCKED_INPUT_PATH"
        report["blockers"].append("INPUT_PATH_OUTSIDE_PROJECT_ROOT")
    try:
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except FileExistsError:
        parser.error(f"Refusing to overwrite existing output: {output}")
    print(json.dumps({"status": report["status"], "blockers": report["blockers"], "output": str(output)}))
    return 0 if report["status"] == "TECHNICAL_BENCHMARK_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
