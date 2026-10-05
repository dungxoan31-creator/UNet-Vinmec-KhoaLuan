"""
Evaluation and Benchmark Samples Router for Ovarian Ultrasound AI.
Serves validation/test metrics, failure cases, and workstation sample bundles.
"""

import base64
import csv
import json
import os

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
VAL_SUMMARY_PATH = os.path.join(BASE_DIR, "evaluation", "retrain_2d_2026-10-03", "validation", "summary.json")
TEST_METRICS_PATH = os.path.join(BASE_DIR, "evaluation", "retrain_2d_2026-10-03", "test_summary.json")
SPLIT_MANIFEST_PATH = os.path.join(BASE_DIR, "ai_training", "splits", "vinmec_2d_retrain_2026-10-03", "manifest.json")
PER_IMAGE_CSV_PATH = os.path.join(BASE_DIR, "evaluation", "retrain_2d_2026-10-03", "validation", "per_image.csv")
PRED_MASKS_DIR = os.path.join(BASE_DIR, "evaluation", "retrain_2d_2026-10-03", "validation", "prediction_masks")


def _read_file_b64(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@router.get("/metrics")
def get_evaluation_metrics():
    """
    Returns train, validation, and test dataset scientific metrics.
    """
    val_data = {}
    if os.path.exists(VAL_SUMMARY_PATH):
        try:
            with open(VAL_SUMMARY_PATH, encoding="utf-8") as f:
                val_data = json.load(f)
        except Exception:
            pass

    test_data = {}
    if os.path.exists(TEST_METRICS_PATH):
        try:
            with open(TEST_METRICS_PATH, encoding="utf-8") as f:
                test_data = json.load(f)
        except Exception:
            pass

    split_manifest = {}
    if os.path.exists(SPLIT_MANIFEST_PATH):
        with open(SPLIT_MANIFEST_PATH, encoding="utf-8") as source:
            split_manifest = json.load(source)
    val_clin = val_data.get("clinical_summary", {})
    test_metrics = test_data.get("mean_per_image", {})
    return {
        "train": {
            "count": split_manifest.get("counts", {}).get("train"),
            "dataset": "Vinmec 2D retraining split; source patient IDs unavailable",
            "loss_function": "0.5 BCE + 0.5 Dice",
        },
        "validation": {
            "count": val_data.get("count"),
            "dice_mean": val_data.get("dice_mean_all_cases"),
            "dice_std": val_clin.get("foreground_dice_std"),
            "iou_mean": val_data.get("iou_mean_all_cases"),
            "iou_std": val_clin.get("foreground_iou_std"),
            "recall_mean": val_data.get("recall_mean_all_cases"),
            "precision_mean": val_clin.get("precision_mean"),
            "specificity": val_clin.get("specificity_all_cases"),
            "checkpoint_sha256": val_data.get("checkpoint_sha256"),
        },
        "test": {
            "count": test_data.get("test_count"),
            "dice_mean": test_metrics.get("dice"),
            "iou_mean": test_metrics.get("iou"),
            "recall_mean": test_metrics.get("recall"),
            "precision_mean": test_metrics.get("precision"),
            "specificity": test_metrics.get("specificity_background_pixels"),
            "specificity_normal_cases": test_metrics.get("specificity_normal_cases"),
            "checkpoint_sha256": test_data.get("checkpoint_sha256"),
            "patient_level_independence_verified": test_data.get("patient_level_independence_verified", False),
            "dataset": "Vinmec 2D source Test; image-level evidence",
        },
    }


@router.get("/samples")
def get_evaluation_samples(
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Returns list of validation benchmark samples with failure categories.
    """
    if not os.path.exists(PER_IMAGE_CSV_PATH):
        return []

    samples = []
    with open(PER_IMAGE_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dice = float(row.get("dice", 0.0))
            iou = float(row.get("iou", 0.0))
            recall = float(row.get("recall", 0.0))
            precision = float(row.get("precision", 0.0))
            specificity = float(row.get("specificity", 0.0))

            if dice < 0.70:
                if recall < 0.55:
                    cat = "FALSE_NEGATIVE_DOMINANT"
                elif precision < 0.55:
                    cat = "FALSE_POSITIVE_DOMINANT"
                else:
                    cat = "LOW_DICE"
            elif dice >= 0.90:
                cat = "EXCELLENT"
            else:
                cat = "GOOD"

            if category and category.upper() != "ALL":
                if category.upper() == "FAILURE_CASES" and dice >= 0.70:
                    continue
                elif category.upper() != "FAILURE_CASES" and cat != category.upper():
                    continue

            samples.append(
                {
                    "case_id": row.get("case_id"),
                    "image_path": row.get("image_path"),
                    "mask_path": row.get("mask_path"),
                    "dice": round(dice, 4),
                    "iou": round(iou, 4),
                    "recall": round(recall, 4),
                    "precision": round(precision, 4),
                    "specificity": round(specificity, 4),
                    "failure_category": cat,
                    "tp": int(row.get("tp", 0)),
                    "fp": int(row.get("fp", 0)),
                    "fn": int(row.get("fn", 0)),
                    "tn": int(row.get("tn", 0)),
                }
            )

    return samples[offset : offset + limit]


@router.get("/samples/{case_id}/workstation-bundle")
def get_sample_workstation_bundle(case_id: str):
    """
    Loads complete bundle for a benchmark sample to render in the Doctor Workstation.
    """
    if not os.path.exists(PER_IMAGE_CSV_PATH):
        raise HTTPException(status_code=404, detail="Dataset evaluation records not found.")

    target_row = None
    with open(PER_IMAGE_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("case_id")).strip() == str(case_id).strip():
                target_row = row
                break

    if not target_row:
        raise HTTPException(status_code=404, detail=f"Case ID {case_id} not found in validation split.")

    raw_img_rel = target_row.get("image_path", "").replace("\\", "/")
    gt_mask_rel = target_row.get("mask_path", "").replace("\\", "/")
    pred_mask_path = os.path.join(PRED_MASKS_DIR, f"{case_id}.png")

    def archived_source(relative_path: str) -> str:
        primary = os.path.join(BASE_DIR, relative_path)
        if os.path.isfile(primary):
            return primary
        archive_relative = relative_path.replace("dataset/Vinmec_2D/", "dataset_backup_archive/Vinmec_2D/")
        return os.path.join(BASE_DIR, archive_relative)

    img_full_path = archived_source(raw_img_rel)
    gt_full_path = archived_source(gt_mask_rel)

    img_b64 = _read_file_b64(img_full_path)
    gt_b64 = _read_file_b64(gt_full_path)
    pred_b64 = _read_file_b64(pred_mask_path)

    if not img_b64:
        raise HTTPException(status_code=404, detail=f"Image file for sample {case_id} not accessible.")

    dice = float(target_row.get("dice", 0.0))
    iou = float(target_row.get("iou", 0.0))

    return {
        "case_id": case_id,
        "image_id": f"BENCHMARK-{case_id}",
        "filename": os.path.basename(raw_img_rel),
        "original_image_base64": f"data:image/jpeg;base64,{img_b64}",
        "ground_truth_mask_base64": f"data:image/png;base64,{gt_b64}" if gt_b64 else None,
        "prediction_mask_base64": f"data:image/png;base64,{pred_b64}" if pred_b64 else None,
        "confidence_score": None,
        "inference_time_ms": None,
        "benchmark_metrics": {
            "dice": round(dice, 4),
            "iou": round(iou, 4),
            "recall": round(float(target_row.get("recall", 0.0)), 4),
            "precision": round(float(target_row.get("precision", 0.0)), 4),
        },
        "measurements": {"calibrated": False},
        "quality_gate": {
            "status": "NOT_ASSESSED",
            "message": "Điểm Dice lịch sử là độ đo phân đoạn, không phải phê duyệt lâm sàng.",
        },
        "provenance": {
            "model_name": "Standard U-Net (Baseline)",
            "checkpoint_sha256": "5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e",
            "dataset_source": "Vinmec 2D Validation; source patient IDs unavailable",
        },
    }
