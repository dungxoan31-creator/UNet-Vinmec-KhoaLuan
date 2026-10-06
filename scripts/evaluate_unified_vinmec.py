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


def evaluate(root: Path, split_dir: Path, checkpoint: Path, output_dir: Path, batch_size: int = 2) -> dict:
    root, split_dir, checkpoint, output_dir = (p.resolve() for p in (root, split_dir, checkpoint, output_dir))
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
                predicted = (probabilities[offset, 0] > 0.5).astype(np.uint8)
                truth = (ground_truth[offset, 0] > 0.5).astype(np.uint8)
                metrics = compute_sample_clinical_metrics(predicted, truth)
                prediction_rel = (Path("evaluation/unified_vinmec_2026-10-06/predictions") / f"{case_id}.png").as_posix()
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
    config = json.loads((root / "checkpoints/unified_vinmec_2026-10-06/run_config.json").read_text(encoding="utf-8"))
    summary = {
        "status": "evaluated_once",
        "test_samples": count,
        "checkpoint": checkpoint.relative_to(root).as_posix(),
        "checkpoint_sha256": _sha256(checkpoint),
        "strict_state_dict_load": True,
        "best_epoch_selected_on_validation": config["best_epoch"],
        "threshold": 0.5,
        "test_loss": loss_sum / count,
        "segmentation_metrics_only": metrics,
        "metrics_by_source_membership": by_source,
        "source_membership_note": "Source groups overlap because folders contain duplicate image content; per-source subsets are not independent.",
        "identity_level": "image-level; source Patient/Case IDs unavailable",
        "test_policy": "Evaluated after checkpoint selection; not used for training or model selection.",
        "preprocessing": "Grayscale, Letterbox 512x512, CLAHE; same loader as training.",
        "top_5_best_cases": ranked[:5],
        "top_5_error_cases_fp_fn": worst[:5],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "test_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / "test_per_image.csv", per_image, list(per_image[0]))
    _write_csv(output_dir / "test_metrics_by_source.csv", by_source, list(by_source[0]))
    for row in index_rows:
        row["ground_truth_path"] = row["mask_path"]
        row["prediction_path"] = ""
        row["prediction_split"] = ""
    per_image_by_id = {row["sample_id"]: row for row in per_image}
    for row in index_rows:
        if row["sample_id"] in per_image_by_id:
            row["prediction_path"] = per_image_by_id[row["sample_id"]]["prediction_path"]
            row["prediction_split"] = "test"
    fields = list(index_rows[0])
    _write_csv(root / "dataset/index.csv", index_rows, fields)
    _write_csv(split_dir / "all_samples.csv", index_rows, fields)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--split-dir", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"))
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/unified_vinmec_2026-10-06/baseline_unet_best.pth"))
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/unified_vinmec_2026-10-06"))
    args = parser.parse_args()
    root = args.root.resolve()
    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    evaluate(root, resolve(args.split_dir), resolve(args.checkpoint), resolve(args.output_dir))


if __name__ == "__main__":
    main()
