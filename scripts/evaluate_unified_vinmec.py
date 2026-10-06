"""Evaluate the selected unified Vinmec U-Net once on its held-out Test split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.metrics_clinical import compute_dataset_clinical_summary, compute_sample_clinical_metrics
from ai_training.train_baseline_unet import ComboLoss
from backend.models.unet import StandardUNet


def summarize_samples(samples: list[dict]) -> dict:
    summary = compute_dataset_clinical_summary(samples)
    summary["empty_mask_cases_count"] = summary.pop("normal_cases_count")
    summary["empty_mask_specificity"] = summary.pop("specificity_normal_cases")
    return summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_error_panel(root: Path, output_path: Path, record: dict) -> None:
    def read(path_key: str) -> np.ndarray:
        path = Path(record[path_key])
        if not path.is_absolute():
            path = root / path
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"Could not read {path_key}: {path}")
        return image

    truth = read("ground_truth_path") > 0
    prediction = read("prediction_path") > 0
    original = read("image_path")
    size = (truth.shape[1], truth.shape[0])
    if prediction.shape != truth.shape:
        prediction = cv2.resize(prediction.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0
    if original.shape != truth.shape:
        original = cv2.resize(original, size, interpolation=cv2.INTER_AREA)

    truth_view = cv2.cvtColor(truth.astype(np.uint8) * 255, cv2.COLOR_GRAY2BGR)
    truth_view[:, :, 1] = np.maximum(truth_view[:, :, 1], truth_view[:, :, 0])
    prediction_view = cv2.cvtColor(prediction.astype(np.uint8) * 255, cv2.COLOR_GRAY2BGR)
    prediction_view[:, :, 1] = np.maximum(prediction_view[:, :, 1], prediction_view[:, :, 0])
    errors = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
    errors[prediction & ~truth] = (0, 0, 255)  # False positive: red
    errors[truth & ~prediction] = (255, 160, 0)  # False negative: blue/orange in BGR

    panels = [cv2.cvtColor(original, cv2.COLOR_GRAY2BGR), truth_view, prediction_view, errors]
    labels = ["Original", "Ground truth", "Prediction", "FP red / FN blue"]
    for panel, label in zip(panels, labels):
        cv2.putText(panel, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), np.hstack(panels)):
        raise OSError(f"Could not write error-analysis panel: {output_path}")


def _write_error_analysis(root: Path, output_dir: Path, best: list[dict], errors: list[dict]) -> None:
    for label, rows in (("best", best), ("fp_fn_errors", errors)):
        for index, record in enumerate(rows, start=1):
            filename = f"{label}_{index:02d}_dice_{record['dice']:.3f}.png"
            _write_error_panel(root, output_dir / "error_analysis" / filename, record)


def evaluate(
    root: Path,
    split_dir: Path,
    checkpoint: Path,
    output_dir: Path,
    batch_size: int = 2,
    threshold: float = 0.5,
) -> dict:
    root, split_dir, checkpoint, output_dir = (p.resolve() for p in (root, split_dir, checkpoint, output_dir))
    try:
        output_rel = output_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("output_dir must be located inside root to keep artifacts traceable") from exc
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing evaluation artifacts: {output_dir}")
    test_csv = split_dir / "test.csv"
    with (split_dir / "all_samples.csv").open(newline="", encoding="utf-8-sig") as stream:
        index_rows = list(csv.DictReader(stream))
    index_by_case = {row["case_id"]: row for row in index_rows}
    dataset = OvarianUltrasoundDataset(test_csv, is_train=False)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    model.eval()
    criterion = ComboLoss()
    predictions_dir = output_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    per_image = []
    loss_sum = 0.0
    count = 0
    with torch.inference_mode():
        for batch in loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            logits = model(images)
            loss_sum += criterion(logits, masks).item() * images.shape[0]
            probabilities = torch.sigmoid(logits).cpu().numpy()
            ground_truth = masks.cpu().numpy()
            for offset, case_id in enumerate(batch["case_id"]):
                record = index_by_case[case_id]
                predicted = (probabilities[offset, 0] > threshold).astype(np.uint8)
                truth = (ground_truth[offset, 0] > 0.5).astype(np.uint8)
                metrics = compute_sample_clinical_metrics(predicted, truth)
                prediction_rel = (output_rel / "predictions" / f"{case_id}.png").as_posix()
                prediction_path = root / prediction_rel
                cv2.imwrite(str(prediction_path), predicted * 255)
                per_image.append({
                    "sample_id": case_id,
                    "case_id": case_id,
                    "patient_id": "",
                    "source_datasets": record["source_datasets"],
                    "split": "test",
                    "image_path": record["image_path"],
                    "ground_truth_path": record["mask_path"],
                    "prediction_path": prediction_rel,
                    "image_sha256": record["image_sha256"],
                    **metrics,
                })
                count += 1

    metrics = summarize_samples(per_image)
    sources = defaultdict(list)
    for record in per_image:
        for source in record["source_datasets"].split(";"):
            sources[source].append(record)
    by_source = [{"dataset": name, "source_membership_count": len(rows), **summarize_samples(rows)} for name, rows in sorted(sources.items())]

    ranked = sorted(per_image, key=lambda row: row["dice"], reverse=True)
    worst = sorted(per_image, key=lambda row: row["fp"] + row["fn"], reverse=True)
    config_path = checkpoint.parent / "run_config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"Run configuration not found beside checkpoint: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    best_cases = ranked[:5]
    error_cases = worst[:5]
    summary = {
        "status": "evaluated_once_for_locked_checkpoint",
        "test_samples": count,
        "checkpoint": checkpoint.relative_to(root).as_posix(),
        "checkpoint_sha256": _sha256(checkpoint),
        "strict_state_dict_load": True,
        "best_epoch_selected_on_validation": config["best_epoch"],
        "validation_dice_selected_checkpoint": config.get("best_validation_dice"),
        "threshold": threshold,
        "test_loss": loss_sum / count,
        "segmentation_metrics_only": metrics,
        "metrics_by_source_membership": by_source,
        "source_membership_note": "Source groups overlap because folders contain duplicate image content; per-source subsets are not independent.",
        "identity_level": "image-level; source Patient/Case IDs unavailable",
        "test_policy": "Checkpoint and threshold were locked using Validation; Test metrics were not used for training, threshold selection, or model selection.",
        "test_history_note": "The previous baseline checkpoint was evaluated on this same Test split before refinement. This result is retained separately; it was not used to select the current checkpoint.",
        "preprocessing": "Grayscale, Letterbox 512x512, CLAHE; same loader as training.",
        "top_5_best_cases": best_cases,
        "top_5_error_cases_fp_fn": error_cases,
        "error_analysis_directory": (output_rel / "error_analysis").as_posix(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_error_analysis(root, output_dir, best_cases, error_cases)
    (output_dir / "test_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / "test_per_image.csv", per_image, list(per_image[0]))
    _write_csv(output_dir / "test_metrics_by_source.csv", by_source, list(by_source[0]))
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--split-dir", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    root = args.root.resolve()
    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    evaluate(root, resolve(args.split_dir), resolve(args.checkpoint), resolve(args.output_dir), threshold=args.threshold)


if __name__ == "__main__":
    main()
