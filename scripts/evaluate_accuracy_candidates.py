"""Compare locked U-Net++ candidates on the frozen Validation split only."""

import argparse
import csv
import json
import statistics
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.metrics_clinical import compute_sample_clinical_metrics
from ai_training.train_unetplusplus_resnet34 import sha256_file
from backend.services.inference_engine import InferenceEngine

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = tuple(round(0.30 + 0.05 * step, 2) for step in range(9))


def score_probabilities(probabilities: np.ndarray, reference: np.ndarray, threshold: float) -> dict:
    return compute_sample_clinical_metrics(probabilities >= threshold, reference)


def predict_native_and_flip(model, images, device_type):
    with torch.inference_mode(), torch.amp.autocast(device_type=device_type, enabled=device_type == "cuda"):
        native = torch.sigmoid(model(images)).float()
        mirrored = torch.sigmoid(model(torch.flip(images, dims=(-1,)))).float()
    averaged = (native + torch.flip(mirrored, dims=(-1,))) / 2
    return native[:, 0].cpu().numpy(), averaged[:, 0].cpu().numpy()


def validate_inputs(root, lock, validation_csv):
    checkpoint = root / lock["checkpoint"]
    if sha256_file(checkpoint) != lock["checkpoint_sha256"]:
        raise ValueError("Locked checkpoint SHA-256 mismatch")
    if sha256_file(validation_csv) != lock["split_hashes"]["val.csv"]:
        raise ValueError("Validation CSV SHA-256 mismatch")
    return checkpoint


def create_output_directory(output):
    output.mkdir(parents=True, exist_ok=False)


def aggregate_candidates(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["candidate"], row["threshold"])].append(row)
    return [
        {
            "candidate": candidate,
            "threshold": threshold,
            "count": len(samples),
            **{metric: statistics.mean(sample[metric] for sample in samples) for metric in ("dice", "iou", "recall", "precision")},
            "dice_below_0_5": sum(sample["dice"] < 0.5 for sample in samples),
        }
        for (candidate, threshold), samples in sorted(groups.items())
    ]


def evaluate(root: Path, lock_path: Path, validation_csv: Path, audit_path: Path, output: Path) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit["errors"] or audit["verified_readable_pairs"] != audit["canonical_samples"] or audit.get("fallback_in_unified_index", 0):
        raise ValueError("Data audit did not pass the canonical image-mask gate")

    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checkpoint = validate_inputs(root, lock, validation_csv)
    dataset = OvarianUltrasoundDataset(str(validation_csv), is_train=False)
    if len(dataset) != lock["selection_count"]:
        raise ValueError("Validation count differs from locked manifest")
    engine = InferenceEngine(
        str(checkpoint),
        architecture=lock["architecture"],
        input_normalization=lock["input_normalization"],
    )
    if not engine.is_model_ready or engine.model_checksum != lock["checkpoint_sha256"]:
        raise ValueError("Locked model could not be loaded with the expected checksum")

    rows = []
    loader = DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)
    for batch in loader:
        images = engine.prepare_model_input(batch["image"])
        native, flip_tta = predict_native_and_flip(engine.model, images, engine.device)
        references = batch["mask"].numpy()[:, 0] >= 0.5
        for index, case_id in enumerate(batch["case_id"]):
            for candidate, probabilities in (("native", native), ("flip_tta", flip_tta)):
                for threshold in THRESHOLDS:
                    metrics = score_probabilities(probabilities[index], references[index], threshold)
                    rows.append({
                        "case_id": case_id,
                        "candidate": candidate,
                        "threshold": threshold,
                        "dice": metrics["dice"],
                        "iou": metrics["iou"],
                        "recall": metrics["recall"],
                        "precision": metrics["precision"],
                        "is_empty": metrics["is_empty"],
                    })

    candidates = aggregate_candidates(rows)
    baseline = next(row for row in candidates if row["candidate"] == "native" and row["threshold"] == 0.5)
    historical_dice = lock["validation_metrics_historical"]["dice"]
    if abs(baseline["dice"] - historical_dice) > 1e-6:
        raise ValueError(f"Baseline replay differs from locked Validation Dice: {baseline['dice']} vs {historical_dice}")

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "scope": "Validation-only, image-level exploratory segmentation agreement with supplied masks",
        "test_inference_performed": False,
        "patient_level_independence_verified": False,
        "expert_mask_approval_verified": False,
        "checkpoint_sha256": lock["checkpoint_sha256"],
        "validation_csv_sha256": sha256_file(validation_csv),
        "lock_sha256": sha256_file(lock_path),
        "data_audit_sha256": sha256_file(audit_path),
        "data_audit_missing_source_references": audit["missing_source_path_references"],
        "validation_count": len(dataset),
        "thresholds": THRESHOLDS,
        "preprocessing": "OvarianUltrasoundDataset: grayscale, letterbox 512x512, CLAHE; engine normalization mean 0.449/std 0.226",
        "tta": "horizontal flip probabilities unflipped and averaged with native probabilities",
        "metric_resolution": "512x512 letterboxed; AMP matches historical Validation replay",
        "historical_native_0_5_dice": historical_dice,
        "replayed_native_0_5_dice": baseline["dice"],
        "candidates": candidates,
    }
    create_output_directory(output)
    with (output / "per_image.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--lock", type=Path, default=Path("evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json"))
    parser.add_argument("--validation-csv", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/accuracy_2026-10-09/data_audit/dataset_audit.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    def within_root(path: Path) -> Path:
        return path if path.is_absolute() else root / path
    result = evaluate(root, *(within_root(path) for path in (args.lock, args.validation_csv, args.audit, args.output)))
    best = max(result["candidates"], key=lambda row: row["dice"])
    print(json.dumps({"baseline_dice": result["replayed_native_0_5_dice"], "best_exploratory": best, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
