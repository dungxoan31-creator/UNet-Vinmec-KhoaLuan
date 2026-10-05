"""Bind a completed source-test evaluation to the validation-selected checkpoint."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "evaluation/retrain_2d_2026-10-03"
SPLIT_DIR = ROOT / "ai_training/splits/vinmec_2d_retrain_2026-10-03"
SELECTION_PATH = ROOT / "evaluation/selected_model.json"


def main() -> None:
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    checkpoint = ROOT / selection["checkpoint"]
    checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    summary = json.loads((RESULT_DIR / "test/summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((SPLIT_DIR / "manifest.json").read_text(encoding="utf-8"))
    if checksum != selection["checkpoint_sha256"] or checksum != summary["checkpoint_sha256"]:
        raise ValueError("Test evaluation checkpoint does not match the validation selection")
    if summary["threshold"] != selection["threshold"] or summary["split"] != "test":
        raise ValueError("Test threshold or split differs from the locked selection")
    if summary["count"] != manifest["counts"]["test"]:
        raise ValueError("Test image count differs from the split manifest")

    with (RESULT_DIR / "test/per_image.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != summary["count"] or len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("Missing or duplicate per-image results")

    def case_record(row: dict[str, str]) -> dict:
        case_id = row["case_id"]
        prediction = RESULT_DIR / "test/prediction_masks" / f"{case_id}.png"
        panel = RESULT_DIR / "test/comparison_panels" / f"{case_id}.png"
        if not prediction.is_file() or not panel.is_file() or not (ROOT / row["image_path"]).is_file() or not (ROOT / row["mask_path"]).is_file():
            raise FileNotFoundError(f"Incomplete image, mask, prediction or panel for {case_id}")
        fp, fn = int(row["fp"]), int(row["fn"])
        return {
            "case_id": case_id,
            "dice": float(row["dice"]),
            "iou": float(row["iou"]),
            "false_positive_pixels": fp,
            "false_negative_pixels": fn,
            "dominant_pixel_error": "false_positive" if fp > fn else "false_negative" if fn > fp else "equal",
            "image_path": Path(row["image_path"]).as_posix(),
            "ground_truth_mask_path": Path(row["mask_path"]).as_posix(),
            "prediction_mask_path": prediction.relative_to(ROOT).as_posix(),
            "comparison_panel_path": panel.relative_to(ROOT).as_posix(),
        }

    ranked = sorted(rows, key=lambda row: (-float(row["dice"]), row["case_id"]))
    worst = sorted(rows, key=lambda row: (float(row["dice"]), row["case_id"]))
    clinical = summary["clinical_summary"]
    report = {
        "evidence_status": "PARTIALLY VERIFIED: image-level source Test; patient identity unavailable",
        "checkpoint_sha256": checksum,
        "selection_split": selection["selection_split"],
        "threshold": selection["threshold"],
        "test_count": summary["count"],
        "source_test_preserved_from_training": manifest["source_test_preserved"],
        "patient_split_status": manifest["patient_id_status"],
        "patient_level_independence_verified": False,
        "test_previously_accessed_for_earlier_checkpoint": True,
        "normal_control_count": clinical["normal_cases_count"],
        "mean_per_image": {
            "dice": summary["dice_mean_all_cases"],
            "iou": summary["iou_mean_all_cases"],
            "precision": clinical["precision_mean"],
            "recall": summary["recall_mean_all_cases"],
            "specificity_background_pixels": clinical["specificity_all_cases"],
            "specificity_normal_cases": clinical["specificity_normal_cases"],
        },
        "top_5_by_dice": [case_record(row) for row in ranked[:5]],
        "bottom_5_by_dice": [case_record(row) for row in worst[:5]],
        "full_metrics_path": "evaluation/retrain_2d_2026-10-03/test/summary.json",
        "per_image_metrics_path": "evaluation/retrain_2d_2026-10-03/test/per_image.csv",
    }
    report_path = RESULT_DIR / "test_summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selection["test_evaluation"] = {
        "summary": report_path.relative_to(ROOT).as_posix(),
        "checkpoint_sha256": checksum,
        "threshold": selection["threshold"],
        "count": summary["count"],
        "patient_level_independence_verified": False,
    }
    SELECTION_PATH.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
