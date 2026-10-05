"""Check selected prototype weights on M1 Validation without computing clinical metrics."""

import csv
import hashlib
import json
import statistics
from pathlib import Path
from time import perf_counter

import cv2
import torch

from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor


def validation_rows(root: Path) -> list[dict[str, str]]:
    with (root / "ai_training/splits/val.csv").open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 46 or any(row["split"] != "VAL" for row in rows):
        raise ValueError("Milestone 1 Validation must contain exactly 46 VAL rows")
    return rows


def _summarize(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(values), 2),
        "p95_ms": round(statistics.quantiles(values, n=100, method="inclusive")[94], 2),
        "mean_ms": round(statistics.mean(values), 2),
    }


def run(root: Path, output: Path) -> dict:
    root = root.resolve()
    rows = validation_rows(root)
    selected = json.loads((root / "evaluation/selected_model.json").read_text(encoding="utf-8"))
    checkpoint = root / selected["checkpoint"]
    sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if sha != selected["checkpoint_sha256"]:
        raise ValueError("Selected checkpoint SHA-256 does not match its manifest")
    if selected["model"] != "Standard U-Net":
        raise ValueError("This sanity check requires the selected Standard U-Net")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    state = torch.load(checkpoint, map_location=device, weights_only=True)
    incompatibility = model.load_state_dict(state, strict=True)
    model.eval()
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    threshold = float(selected["threshold"])
    results = []

    with torch.inference_mode():
        for index, row in enumerate(rows):
            image_path = root / row["image_path"]
            image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError(f"Cannot decode Validation image: {image_path}")
            if cv2.imread(str(root / row["mask_path"]), cv2.IMREAD_GRAYSCALE) is None:
                raise ValueError(f"Cannot decode Validation mask: {row['mask_path']}")
            started = perf_counter()
            tensor, _padded, _transform, _quality = preprocessor.preprocess_for_inference(image)
            tensor = tensor.to(device)
            if device.type == "cuda":
                torch.cuda.synchronize()
            prepared = perf_counter()
            if index == 0:
                model(tensor)  # Warm up using the first Validation image only.
                if device.type == "cuda":
                    torch.cuda.synchronize()
                prepared = perf_counter()
            probability = torch.sigmoid(model(tensor))
            binary = probability >= threshold
            if device.type == "cuda":
                torch.cuda.synchronize()
            completed = perf_counter()
            if tuple(binary.shape) != (1, 1, 512, 512):
                raise ValueError(f"Unexpected prediction shape: {tuple(binary.shape)}")
            results.append({
                "case_id": row["case_id"],
                "image_path": row["image_path"],
                "declared_empty_control": row["is_empty_mask"].lower() == "true",
                "predicted_positive_pixels": int(binary.sum().item()),
                "preprocess_ms": round((prepared - started) * 1000, 2) if index else None,
                "model_forward_ms": round((completed - prepared) * 1000, 2),
                "preprocess_plus_forward_ms": round((completed - started) * 1000, 2) if index else None,
            })

    forward_times = [row["model_forward_ms"] for row in results]
    total_times = [row["preprocess_plus_forward_ms"] for row in results if row["preprocess_plus_forward_ms"] is not None]
    summary = {
        "status": "PASS",
        "purpose": "model loading and inference pipeline sanity check; no segmentation metric computed",
        "source_split_csv": "ai_training/splits/val.csv",
        "validation_count": len(results),
        "test_set_used": False,
        "selected_model_sha256": sha,
        "checkpoint": selected["checkpoint"],
        "checkpoint_load_strict": True,
        "missing_keys": list(incompatibility.missing_keys),
        "unexpected_keys": list(incompatibility.unexpected_keys),
        "threshold": threshold,
        "device": str(device),
        "prediction_shape": [1, 1, 512, 512],
        "declared_empty_controls": sum(row["declared_empty_control"] for row in results),
        "clinical_negative_verified": False,
        "model_forward_latency": _summarize(forward_times),
        "preprocess_plus_forward_latency_excluding_warmup": _summarize(total_times),
        "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "evaluation/m1_validation_sanity_check.json"
    result = run(project_root, output_path)
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
