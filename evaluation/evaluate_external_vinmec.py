"""Image-level evaluation on Vinmec external validation images."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from ai_training.metrics_clinical import compute_dataset_clinical_summary, compute_sample_clinical_metrics
from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor


def image_fingerprint(path: Path) -> str:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()


def binary_prediction(probability: np.ndarray, threshold: float) -> np.ndarray:
    if not 0.0 < threshold < 1.0:
        raise ValueError("Threshold must be between 0 and 1")
    return (probability >= threshold).astype(np.uint8)


def select_unseen_pairs(
    source_images: Path, source_masks: Path, training_dirs: list[Path]
) -> list[tuple[Path, Path]]:
    seen = {image_fingerprint(path) for folder in training_dirs for path in folder.glob("*.JPG")}
    pairs = []
    for image in sorted(source_images.glob("*.JPG")):
        mask = source_masks / f"{image.stem}.PNG"
        if not mask.is_file():
            raise ValueError(f"Missing mask: {mask}")
        if image_fingerprint(image) not in seen:
            pairs.append((image, mask))
    return pairs


def evaluate(source_dir: Path, checkpoint: Path, output_dir: Path, training_dirs: list[Path], threshold: float = 0.5) -> dict:
    images_dir = source_dir / "images"
    masks_dir = source_dir / "labels"
    pairs = select_unseen_pairs(images_dir, masks_dir, training_dirs)
    if not pairs:
        raise ValueError("No unseen image-mask pairs remain after overlap screening")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    model.eval()
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    rows = []
    for image_path, mask_path in pairs:
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None or image.shape != mask.shape:
            raise ValueError(f"Invalid image-mask pair: {image_path.name}")
        padded, transform = preprocessor.letterbox_resize(image, is_mask=False)
        enhanced = preprocessor.clahe.apply(padded)
        tensor = torch.from_numpy(enhanced).unsqueeze(0).unsqueeze(0).float().to(device) / 255.0
        with torch.inference_mode():
            probability = torch.sigmoid(model(tensor)).squeeze().cpu().numpy()
            prediction = binary_prediction(probability, threshold)
        restored = preprocessor.inverse_letterbox_mask(prediction, transform)
        metrics = compute_sample_clinical_metrics(restored, (mask > 0).astype(np.uint8))
        rows.append({"image": image_path.name, **metrics})

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "external_vinmec_per_image.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "source": "Vinmec Ultrasound Repository",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "source_images": len(list(images_dir.glob("*.JPG"))),
        "training_images": sum(len(list(folder.glob("*.JPG"))) for folder in training_dirs),
        "unseen_images": len(rows),
        "screening": "exact decoded grayscale image SHA-256; patient identity unavailable",
        "threshold": threshold,
        "metrics": compute_dataset_clinical_summary(rows),
        "worst_lesion_cases": sorted(
            ({"image": row["image"], "dice": row["dice"]} for row in rows if not row["is_empty"]),
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
