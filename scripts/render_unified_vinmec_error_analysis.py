"""Render a contact sheet for the already evaluated Test cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.train_baseline_unet import _file_sha256, validate_training_split_identity


def _overlay(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    result = np.repeat(image[:, :, None], 3, axis=2).astype(np.float32)
    selected = mask > 0
    result[selected] = result[selected] * 0.55 + np.asarray(color) * 0.45
    return result.clip(0, 255).astype(np.uint8)


def _rooted_path(root: Path, value: str, field: str) -> Path:
    candidate = Path(value)
    candidate = candidate if candidate.is_absolute() else root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} must be located inside the project root") from exc
    return candidate


def _validate_test_artifacts(root: Path, split_dir: Path, summary: dict) -> None:
    if (
        not isinstance(summary, dict)
        or summary.get("identity_level") != "patient-level"
        or summary.get("patient_level_independence_verified") is not True
        or summary.get("source_patient_identity_verified") is not True
        or summary.get("test_inference_performed") is not True
        or summary.get("test_split_image_data_used") is not False
    ):
        raise ValueError("Test error analysis requires a patient-level, test-isolated evaluation summary")
    if validate_training_split_identity(split_dir) != "patient_level_verified":
        raise ValueError("Patient-level independence is not verified for the current Test split")

    test_csv = split_dir / "test.csv"
    manifest = split_dir / "manifest.json"
    if (
        summary.get("test_csv_sha256") != _file_sha256(test_csv)
        or summary.get("split_manifest_sha256") != _file_sha256(manifest)
    ):
        raise ValueError("Test error-analysis summary does not match the current split artifacts")

    checkpoint_value = summary.get("checkpoint")
    if not isinstance(checkpoint_value, str) or not checkpoint_value.strip():
        raise ValueError("Test error-analysis summary is missing checkpoint provenance")
    checkpoint = _rooted_path(root, checkpoint_value, "checkpoint")
    run_config = checkpoint.parent / "run_config.json"
    if (
        not checkpoint.is_file()
        or not run_config.is_file()
        or summary.get("checkpoint_sha256") != _file_sha256(checkpoint)
        or summary.get("run_config_sha256") != _file_sha256(run_config)
    ):
        raise ValueError("Test error-analysis summary does not match the current checkpoint provenance")


def render(root: Path, output: Path) -> Path:
    eval_dir = root / "evaluation/unified_vinmec_2026-10-06"
    summary = json.loads((eval_dir / "test_summary.json").read_text(encoding="utf-8"))
    split_dir = root / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    _validate_test_artifacts(root, split_dir, summary)
    split_csv = split_dir / "test.csv"
    dataset = OvarianUltrasoundDataset(split_csv, is_train=False)
    index_by_case = {str(row.case_id): index for index, row in dataset.df.iterrows()}
    cases = [("BEST", row) for row in summary["top_5_best_cases"]]
    cases += [("ERROR", row) for row in summary["top_5_error_cases_fp_fn"]]

    tile = 224
    heading = 38
    row_height = tile + heading
    columns = ["Original", "Ground Truth", "Prediction", "Overlay (GT green / Pred red)"]
    sheet = Image.new("RGB", (tile * 4, row_height * len(cases)), "#111827")
    draw = ImageDraw.Draw(sheet)

    for row_index, (group, record) in enumerate(cases):
        sample = dataset[index_by_case[record["case_id"]]]
        image = (sample["image"][0].numpy() * 255).round().astype(np.uint8)
        truth = sample["mask"][0].numpy() > 0.5
        prediction_path = _rooted_path(root, record["prediction_path"], "prediction_path")
        prediction = np.asarray(Image.open(prediction_path).convert("L")) > 0
        original = Image.fromarray(image).resize((tile, tile), Image.Resampling.BILINEAR)
        gt = Image.fromarray(_overlay(image, truth, (0, 220, 120))).resize((tile, tile), Image.Resampling.NEAREST)
        pred = Image.fromarray(_overlay(image, prediction, (255, 65, 65))).resize((tile, tile), Image.Resampling.NEAREST)
        combined = Image.fromarray(_overlay(image, truth, (0, 220, 120)))
        combined_array = np.asarray(combined).copy()
        combined_array[prediction] = (combined_array[prediction] * 0.55 + np.asarray((255, 65, 65)) * 0.45).astype(np.uint8)
        overlay = Image.fromarray(combined_array).resize((tile, tile), Image.Resampling.NEAREST)
        top = row_index * row_height
        title = f"{group} | Dice {record['dice']:.3f} | IoU {record['iou']:.3f} | R {record['recall']:.3f} | P {record['precision']:.3f}"
        draw.text((8, top + 4), title, fill="white")
        for column, (label, picture) in enumerate(zip(columns, (original, gt, pred, overlay), strict=True)):
            left = column * tile
            draw.text((left + 8, top + 22), label, fill="#cbd5e1")
            sheet.paste(picture, (left, top + heading))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/unified_vinmec_2026-10-06/test_error_analysis_contact_sheet.png"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(render(root, output))


if __name__ == "__main__":
    main()
