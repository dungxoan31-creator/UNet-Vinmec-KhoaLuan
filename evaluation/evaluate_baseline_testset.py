"""Research-only replay of a provenance-checked held-out segmentation split."""

import hashlib
import json
import sys
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_training.metrics_clinical import compute_dataset_clinical_summary, compute_sample_clinical_metrics  # noqa: E402
from ai_training.train_baseline_unet import validate_training_split_identity  # noqa: E402
from backend.core.dataset_paths import resolve_dataset_path  # noqa: E402
from backend.models.unet import StandardUNet  # noqa: E402
from backend.services.preprocessor import UltrasoundPreprocessor  # noqa: E402

DEFAULT_SPLIT_DIR = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    try:
        data = Path(file_path).read_bytes()
    except OSError:
        return None
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), flags)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_checkpoint_provenance(checkpoint_path: Path, split_dir: Path) -> tuple[str, str]:
    """Require a patient-verified split and a checkpoint tied to that exact split."""
    checkpoint_path = Path(checkpoint_path).resolve()
    split_dir = Path(split_dir).resolve()
    identity_status = validate_training_split_identity(split_dir)
    manifest_path = split_dir / "manifest.json"
    config_path = checkpoint_path.parent / "run_config.json"
    if not checkpoint_path.is_file() or not config_path.is_file():
        raise ValueError("Baseline checkpoint provenance is missing or unverifiable")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Baseline checkpoint provenance is missing or unverifiable") from exc
    if not isinstance(config, dict):
        raise ValueError("Baseline checkpoint provenance is missing or unverifiable")

    recorded_checkpoint = config.get("checkpoint_best")
    recorded_checkpoint = Path(recorded_checkpoint) if isinstance(recorded_checkpoint, str) else None
    if recorded_checkpoint is not None and not recorded_checkpoint.is_absolute():
        recorded_checkpoint = ROOT / recorded_checkpoint

    checkpoint_hash = _sha256(checkpoint_path)
    split_hash = _sha256(manifest_path)
    if (
        identity_status != "patient_level_verified"
        or config.get("split_identity_status") != identity_status
        or config.get("test_split_image_data_used") is not False
        or config.get("split_manifest_sha256") != split_hash
        or config.get("checkpoint_best_sha256") != checkpoint_hash
        or recorded_checkpoint is None
        or recorded_checkpoint.resolve() != checkpoint_path
    ):
        raise ValueError("Baseline checkpoint provenance does not verify a patient-isolated run")
    return checkpoint_hash, split_hash


def _resolve_sample_path(root: Path, raw_path: str, *, case_id: str, role: str) -> Path:
    path = resolve_dataset_path(root, raw_path)
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Sample {case_id} {role} path escapes the project dataset root") from exc
    return resolved_path


def _load_reference_pair(root: Path, row: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    case_id = str(row["case_id"])
    image_path = _resolve_sample_path(root, str(row["image_path"]), case_id=case_id, role="image")
    mask_path = _resolve_sample_path(root, str(row["mask_path"]), case_id=case_id, role="mask")
    image = cv2_imread_unicode(image_path)
    if image is None:
        raise ValueError(f"Sample {case_id} has a missing or unreadable image: {image_path}")
    mask = cv2_imread_unicode(mask_path)
    if mask is None:
        raise ValueError(f"Sample {case_id} has a missing or unreadable reference mask: {mask_path}")
    if image.shape != mask.shape:
        raise ValueError(f"Sample {case_id} image and reference mask shapes differ")
    invalid_values = set(np.unique(mask).tolist()) - {0, 1, 255}
    if invalid_values:
        raise ValueError(f"Sample {case_id} reference mask contains invalid values: {invalid_values}")
    return image, (mask > 0).astype(np.uint8)


def _save_grid(cases: list[dict], output_path: Path, title: str) -> None:
    fig, axes = plt.subplots(len(cases), 3, figsize=(12, 4 * len(cases)))
    for index, case in enumerate(cases):
        axes[index, 0].imshow(case["image"], cmap="gray")
        axes[index, 0].set_title(f"{case['label']}\nRaw Image")
        axes[index, 0].axis("off")

        axes[index, 1].imshow(case["image"], cmap="gray")
        axes[index, 1].imshow(np.ma.masked_where(case["mask"] == 0, case["mask"]), cmap="autumn", alpha=0.5)
        axes[index, 1].set_title("Reference Segmentation Mask")
        axes[index, 1].axis("off")

        axes[index, 2].imshow(case["image"], cmap="gray")
        axes[index, 2].imshow(np.ma.masked_where(case["prediction"] == 0, case["prediction"]), cmap="winter", alpha=0.5)
        axes[index, 2].set_title(f"AI Prediction\nDice: {case['dice']:.4f} | IoU: {case['iou']:.4f}")
        axes[index, 2].axis("off")

    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def evaluate_test_set(
    checkpoint_path=ROOT / "checkpoints/baseline_unet_best.pth",
    test_csv=DEFAULT_SPLIT_DIR / "test.csv",
    output_metrics=ROOT / "evaluation/baseline_test_metrics.json",
    vis_dir=ROOT / "evaluation/baseline_visualizations",
):
    checkpoint_path = Path(checkpoint_path).resolve()
    test_csv = Path(test_csv).resolve()
    split_dir = test_csv.parent
    if test_csv != (split_dir / "test.csv").resolve():
        raise ValueError("Evaluation must use the test.csv inside the provenance-checked split directory")
    checkpoint_hash, split_hash = validate_checkpoint_provenance(checkpoint_path, split_dir)

    df = pd.read_csv(test_csv)
    required_columns = {"case_id", "image_path", "mask_path"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"Test CSV is missing required columns: {required_columns - set(df.columns)}")
    if df.empty or df["case_id"].isna().any() or df["case_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Test CSV must contain at least one sample with a non-empty case_id")
    if df["case_id"].astype(str).duplicated().any():
        raise ValueError("Test CSV contains duplicate case_id values")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    if _sha256(checkpoint_path) != checkpoint_hash:
        raise ValueError("Baseline checkpoint changed after provenance verification")
    model.eval()

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    sample_results = []
    case_predictions = []
    for index, (_, row) in enumerate(df.iterrows(), start=1):
        raw_image, raw_mask = _load_reference_pair(ROOT, row)
        padded_image, transform = preprocessor.letterbox_resize(raw_image, is_mask=False)
        enhanced_image = preprocessor.clahe.apply(padded_image)
        tensor_image = torch.from_numpy(enhanced_image).unsqueeze(0).unsqueeze(0).float().to(device) / 255.0

        with torch.inference_mode():
            logits = model(tensor_image)
            if logits.shape != (1, 1, 512, 512):
                raise ValueError(f"Model returned unexpected segmentation shape: {tuple(logits.shape)}")
            prediction_512 = (torch.sigmoid(logits) >= 0.5).squeeze().cpu().numpy().astype(np.uint8)

        restored_mask = preprocessor.inverse_letterbox_mask(prediction_512, transform)
        metrics = compute_sample_clinical_metrics(restored_mask, raw_mask)
        sample_results.append(metrics)
        case_predictions.append(
            {
                "label": f"Sample {index}",
                "image": raw_image,
                "mask": raw_mask,
                "prediction": restored_mask,
                "dice": metrics["dice"],
                "iou": metrics["iou"],
                "is_empty": metrics["is_empty"],
            }
        )

    summary = compute_dataset_clinical_summary(sample_results)
    if not summary:
        raise ValueError("No test samples were evaluated")
    summary.update(
        {
            "benchmark_tag": "[RESEARCH USE ONLY - RETROSPECTIVE TEST REPLAY]",
            "evaluation_scope": "retrospective_test_replay",
            "patient_independence_verified": True,
            "source_patient_identity_verified": True,
            "label_provenance_verified": False,
            "checkpoint_sha256": checkpoint_hash,
            "split_manifest_sha256": split_hash,
        }
    )

    output_metrics = Path(output_metrics)
    output_metrics.parent.mkdir(parents=True, exist_ok=True)
    output_metrics.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lesion_cases = sorted((case for case in case_predictions if not case["is_empty"]), key=lambda case: case["dice"])
    if len(lesion_cases) >= 9:
        mid = len(lesion_cases) // 2
        visualizations = Path(vis_dir)
        visualizations.mkdir(parents=True, exist_ok=True)
        _save_grid(lesion_cases[:3], visualizations / "best_matches.png", "Top 3 Best Segmentation Matches")
        _save_grid(lesion_cases[mid - 1 : mid + 2], visualizations / "average_matches.png", "Median Segmentation Cases")
        _save_grid(lesion_cases[-3:], visualizations / "worst_matches.png", "Lowest Segmentation Matches")

    print(f"Held-out research replay evaluated {summary['total_cases_evaluated']} samples.")
    print(f"Foreground Dice: {summary['foreground_dice_mean']:.4f} ± {summary['foreground_dice_std']:.4f}")
    print(f"Foreground IoU: {summary['foreground_iou_mean']:.4f} ± {summary['foreground_iou_std']:.4f}")
    print(f"Recall: {summary['recall_sensitivity_mean']:.4f} | Precision: {summary['precision_mean']:.4f}")
    print(f"Specificity: {summary['specificity_all_cases']:.4f}")
    print(f"Metrics saved to {output_metrics}")
    return summary


if __name__ == "__main__":
    evaluate_test_set()
