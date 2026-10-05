"""Evaluate a trained binary U-Net on a declared validation or test CSV."""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
import torch

from ai_training.dataset_loader import cv2_imread_unicode
from ai_training.metrics_clinical import compute_dataset_clinical_summary, compute_sample_clinical_metrics
from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor


def _resolve_path(value: str, splits_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    for candidate in (path, splits_dir.parent / path, splits_dir / path):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"File listed in split CSV not found: {value}")


def _read_pairs(splits_dir: Path, split: str) -> list[tuple[str, Path, Path, np.ndarray, np.ndarray]]:
    csv_path = splits_dir / f"{split}.csv"
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"case_id", "image_path", "mask_path"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{csv_path} must contain {', '.join(sorted(required))}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"Empty split: {csv_path}")

    pairs = []
    seen_ids = set()
    for row in rows:
        case_id = row["case_id"].strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", case_id) or case_id in seen_ids:
            raise ValueError(f"Invalid or duplicate case_id: {case_id!r}")
        seen_ids.add(case_id)
        image_path = _resolve_path(row["image_path"], splits_dir)
        mask_path = _resolve_path(row["mask_path"], splits_dir)
        image = cv2_imread_unicode(str(image_path), cv2.IMREAD_GRAYSCALE)
        mask = cv2_imread_unicode(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None:
            raise ValueError(f"Unreadable image or mask: {case_id}")
        if image.shape != mask.shape:
            raise ValueError(f"Image/mask shape mismatch: {case_id}: {image.shape} vs {mask.shape}")
        if not set(np.unique(mask)).issubset({0, 1, 255}):
            raise ValueError(f"Mask is not binary (0/1 or 0/255): {case_id}")
        pairs.append((case_id, image_path, mask_path, image, (mask > 0).astype(np.uint8)))
    return pairs


def _write_png(path: Path, image: np.ndarray) -> None:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise OSError(f"Cannot encode PNG: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


def _labeled_panel(image: np.ndarray, label: str) -> np.ndarray:
    height, width = image.shape[:2]
    heading = np.full((32, width, 3), 255, dtype=np.uint8)
    cv2.putText(heading, label, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 1, cv2.LINE_AA)
    return np.vstack((heading, image))


def evaluate(
    splits_dir: Path,
    checkpoint: Path,
    output_dir: Path,
    split: str = "val",
    threshold: float = 0.5,
    expected_sha256: str | None = None,
) -> dict:
    if split not in {"val", "test"}:
        raise ValueError("split must be val or test")
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between zero and one")
    splits_dir, checkpoint, output_dir = map(Path, (splits_dir, checkpoint, output_dir))
    pairs = _read_pairs(splits_dir, split)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if expected_sha256 is not None and checkpoint_sha256 != expected_sha256:
        raise ValueError("Checkpoint checksum does not match locked selection")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    model.eval()
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    rows = []
    for index, (case_id, image_path, mask_path, image, ground_truth) in enumerate(pairs):
        padded, transform = preprocessor.letterbox_resize(image, is_mask=False)
        enhanced = preprocessor.clahe.apply(padded)
        tensor = torch.from_numpy(enhanced).unsqueeze(0).unsqueeze(0).float().to(device) / 255.0
        with torch.inference_mode():
            probability = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
        prediction = preprocessor.inverse_letterbox_mask((probability >= threshold).astype(np.uint8), transform)
        metrics = compute_sample_clinical_metrics(prediction, ground_truth)
        rows.append({"case_id": case_id, "image_path": str(image_path), "mask_path": str(mask_path), **metrics})
        _write_png(output_dir / "prediction_masks" / f"{case_id}.png", prediction * 255)

        original = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        gt_panel = cv2.cvtColor(ground_truth * 255, cv2.COLOR_GRAY2BGR)
        pred_panel = cv2.cvtColor(prediction * 255, cv2.COLOR_GRAY2BGR)
        blended = original.copy()
        blended[prediction > 0] = (
            0.5 * blended[prediction > 0] + 0.5 * np.array([0, 0, 255])
        ).astype(np.uint8)
        comparison = np.concatenate((
            _labeled_panel(original, "Image"),
            _labeled_panel(gt_panel, "Ground Truth"),
            _labeled_panel(pred_panel, "Prediction"),
            _labeled_panel(blended, "Overlay"),
        ), axis=1)
        _write_png(output_dir / "comparison_panels" / f"{case_id}.png", comparison)
        if index < 5:
            overlay = np.zeros((*image.shape, 4), dtype=np.uint8)
            overlay[prediction > 0] = (0, 0, 255, 125)  # BGRA red, transparent elsewhere
            _write_png(output_dir / "overlays" / f"{case_id}.png", overlay)
            _write_png(output_dir / "samples" / f"{case_id}.png", comparison)

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "split": split,
        "count": len(rows),
        "threshold": threshold,
        "preprocessing": "grayscale, 512x512 letterbox, CLAHE, divide by 255; inverse nearest-neighbor mask resize",
        "checkpoint_sha256": checkpoint_sha256,
        "patient_split_status": "Not asserted by this evaluator; consult audited split manifest",
        "comparison_panel_count": len(rows),
        "comparison_panel_order": ["Image", "Ground Truth", "Prediction", "Overlay"],
        "dice_mean_all_cases": float(np.mean([row["dice"] for row in rows])),
        "iou_mean_all_cases": float(np.mean([row["iou"] for row in rows])),
        "recall_mean_all_cases": float(np.mean([row["recall"] for row in rows])),
        "clinical_summary": compute_dataset_clinical_summary(rows),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    print(json.dumps(evaluate(
        args.splits_dir, args.checkpoint, args.output_dir, args.split,
        threshold=args.threshold, expected_sha256=args.expected_sha256,
    ), indent=2))
