"""Research-only image-level screening against checkpoint development images."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from ai_training.metrics_clinical import compute_dataset_clinical_summary, compute_sample_clinical_metrics
from ai_training.train_baseline_unet import validate_checkpoint_provenance, validate_training_split_identity
from backend.core.dataset_paths import resolve_dataset_path
from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor

ROOT = Path(__file__).resolve().parents[1]


def image_fingerprint(path: Path) -> str:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()


def binary_prediction(probability: np.ndarray, threshold: float) -> np.ndarray:
    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("Threshold must be a finite number between 0 and 1") from exc
    if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
        raise ValueError("Threshold must be between 0 and 1")
    return (probability >= threshold).astype(np.uint8)


def select_unseen_pairs(
    source_images: Path, source_masks: Path, training_dirs: list[Path]
) -> list[tuple[Path, Path]]:
    seen = {
        image_fingerprint(path)
        for folder in training_dirs
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
    }
    pairs = []
    for image in sorted(source_images.glob("*.JPG")):
        mask = source_masks / f"{image.stem}.PNG"
        if not mask.is_file():
            raise ValueError(f"Missing mask: {mask}")
        if image_fingerprint(image) not in seen:
            pairs.append((image, mask))
    return pairs


def _development_image_dirs(root: Path, split_dir: Path) -> list[Path]:
    directories = set()
    for split in ("train", "val", "test"):
        csv_path = split_dir / f"{split}.csv"
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if "image_path" not in (reader.fieldnames or []):
                raise ValueError(f"Development {split}.csv is missing image_path")
            for row_number, row in enumerate(reader, start=2):
                image_path = (row.get("image_path") or "").strip()
                if not image_path:
                    raise ValueError(f"Development image path is empty at {csv_path}:{row_number}")
                resolved = resolve_dataset_path(root, image_path).resolve()
                if not resolved.is_file():
                    raise ValueError(f"Development image is missing: {resolved}")
                directories.add(resolved.parent)
    return sorted(directories)


def evaluate(source_dir: Path, checkpoint: Path, output_dir: Path, training_dirs: list[Path], threshold: float = 0.5) -> dict:
    checkpoint = Path(checkpoint).resolve()
    run_config_path = checkpoint.parent / "full_unet_run_config.json"
    if not checkpoint.is_file() or not run_config_path.is_file():
        raise ValueError("Checkpoint provenance is missing or unverifiable")
    try:
        run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Checkpoint provenance is missing or unverifiable") from exc
    split_dir_value = run_config.get("split_dir") if isinstance(run_config, dict) else None
    if not isinstance(split_dir_value, str) or not Path(split_dir_value).is_absolute():
        raise ValueError("Checkpoint provenance has no absolute training split directory")
    split_dir = Path(split_dir_value).resolve()
    manifest_path = split_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Checkpoint training split manifest is missing")
    split_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    checkpoint_hash = validate_checkpoint_provenance(checkpoint, expected_split_manifest_sha256=split_hash)
    if run_config.get("architecture") != "Standard U-Net (base_filters=32)":
        raise ValueError("Checkpoint architecture does not match the external evaluator")
    if validate_training_split_identity(split_dir) != "patient_level_verified":
        raise ValueError("Checkpoint training split is not patient-level verified")
    all_training_dirs = list({Path(path).resolve() for path in training_dirs})
    all_training_dirs.extend(_development_image_dirs(ROOT, split_dir))

    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("Threshold must be a finite number between 0 and 1") from exc
    if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
        raise ValueError("Threshold must be between 0 and 1")

    images_dir = source_dir / "images"
    masks_dir = source_dir / "labels"
    pairs = select_unseen_pairs(images_dir, masks_dir, all_training_dirs)
    if not pairs:
        raise ValueError("No unseen image-mask pairs remain after overlap screening")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != checkpoint_hash:
        raise ValueError("Checkpoint changed after provenance verification")
    model.eval()
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    rows = []
    for index, (image_path, mask_path) in enumerate(pairs, start=1):
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None or image.shape != mask.shape:
            raise ValueError(f"Invalid image-mask pair: {image_path.name}")
        invalid_mask_values = set(np.unique(mask).tolist()) - {0, 1, 255}
        if invalid_mask_values:
            raise ValueError(f"Invalid reference mask values for {image_path.name}: {invalid_mask_values}")
        padded, transform = preprocessor.letterbox_resize(image, is_mask=False)
        enhanced = preprocessor.clahe.apply(padded)
        tensor = torch.from_numpy(enhanced).unsqueeze(0).unsqueeze(0).float().to(device) / 255.0
        with torch.inference_mode():
            probability = torch.sigmoid(model(tensor)).squeeze().cpu().numpy()
            prediction = binary_prediction(probability, threshold)
        restored = preprocessor.inverse_letterbox_mask(prediction, transform)
        metrics = compute_sample_clinical_metrics(restored, (mask > 0).astype(np.uint8))
        if restored.shape != mask.shape:
            raise ValueError(f"Prediction and reference mask shapes differ for {image_path.name}")
        rows.append({"sample_id": f"sample-{index}", **metrics})

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "external_vinmec_per_image.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "benchmark_tag": "[RESEARCH USE ONLY - IMAGE-LEVEL SCREENING]",
        "evaluation_scope": "image_level_external_screening",
        "patient_independence_verified": False,
        "label_provenance_verified": False,
        "source": "User-supplied image-mask cohort",
        "checkpoint_sha256": checkpoint_hash,
        "training_split_manifest_sha256": split_hash,
        "training_patient_identity_verified": True,
        "source_images": len(list(images_dir.glob("*.JPG"))),
        "training_images": sum(len(list(folder.glob("*.JPG"))) for folder in training_dirs),
        "unseen_images": len(rows),
        "screening": "exact decoded grayscale image SHA-256; patient identity unavailable",
        "threshold": threshold,
        "metrics": compute_dataset_clinical_summary(rows),
        "worst_lesion_cases": sorted(
            ({"sample_id": row["sample_id"], "dice": row["dice"]} for row in rows if not row["is_empty"]),
            key=lambda item: item["dice"],
        )[:5],
    }
    (output_dir / "external_vinmec_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("dataset/Vinmec"))
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/full_unet_final.pth"))
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/external_vinmec"))
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    training_dirs = [
        Path("dataset/Vinmec_2D/train/train_image"),
        Path("dataset/Vinmec_2D/test/image"),
        Path("dataset/Vinmec_CEUS/image"),
    ]
    evaluate(args.source_dir, args.checkpoint, args.output_dir, training_dirs, args.threshold)
