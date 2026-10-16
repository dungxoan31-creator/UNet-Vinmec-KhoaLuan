"""
Evaluation and Benchmark Samples Router for Ovarian Ultrasound AI.
Serves validation/test metrics, failure cases, and workstation sample bundles.
"""

import base64
import csv
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.core.dataset_paths import resolve_dataset_path

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
VAL_SUMMARY_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "summary.json")
TEST_METRICS_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "test_summary.json")
SPLIT_MANIFEST_PATH = os.path.join(BASE_DIR, "ai_training", "splits", "vinmec_2d_retrain_2026-10-03", "manifest.json")
PER_IMAGE_CSV_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "per_image.csv")
PRED_MASKS_DIR = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "prediction_masks")
CURRENT_RUN_PATH = os.path.join(BASE_DIR, "evaluation", "current_run.json")
RELEASE_STATUS_PATH = os.path.join(BASE_DIR, "evaluation", "milestone_3_final", "report", "release_status.json")


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
    # Load verified current run if pointer exists
    current_run = None
    if os.path.exists(CURRENT_RUN_PATH):
        try:
            with open(CURRENT_RUN_PATH, encoding="utf-8") as f:
                ptr = json.load(f)
            sum_path = ptr.get("summary_path")
            if sum_path:
                full_sum_path = os.path.join(BASE_DIR, sum_path) if not os.path.isabs(sum_path) else sum_path
                if os.path.exists(full_sum_path):
                    with open(full_sum_path, encoding="utf-8") as sf:
                        sum_data = json.load(sf)
                    primary = sum_data.get("primary", {})
                    secondary = sum_data.get("secondary", {})
                    current_run = {
                        "run_id": ptr.get("run_id"),
                        "run_kind": ptr.get("run_kind"),
                        "label": ptr.get("label", ptr.get("run_id")),
                        "status": ptr.get("status", "COMPLETE"),
                        "is_historical": ptr.get("run_kind") == "retrospective_test_replay",
                        "checkpoint_sha256": ptr.get("checkpoint_sha256"),
                        "protocol_sha256": ptr.get("protocol_sha256"),
                        "manifest_sha256": ptr.get("manifest_sha256"),
                        "counts": sum_data.get("counts", {}),
                        "primary": {
                            k: {
                                "mean": v.get("mean"),
                                "median": v.get("median"),
                                "std": v.get("std"),
                                "min": v.get("min"),
                                "max": v.get("max"),
                                "n_valid": v.get("n_valid"),
                                "n_null": v.get("n_null"),
                                "null_reason": v.get("null_reason"),
                            }
                            for k, v in primary.items()
                        },
                        "secondary": {
                            "micro_dice": secondary.get("micro_dice"),
                            "micro_iou": secondary.get("micro_iou"),
                            "all_images_agreement_dice": secondary.get("all_images_agreement_dice", {}).get("mean"),
                        },
                    }
        except Exception:
            current_run = None

    # Load release status / blockers if present
    evidence_status = {
        "prototype_ready": True,
        "evaluation_complete": False,
        "independent_gate_status": "BLOCKED",
        "blockers": ["Independent test cohort patient-level mapping unverified (independent_gate status: BLOCKED)"],
    }
    if os.path.exists(RELEASE_STATUS_PATH):
        try:
            with open(RELEASE_STATUS_PATH, encoding="utf-8") as rf:
                rel = json.load(rf)
                evidence_status["prototype_ready"] = rel.get("prototype_ready", True)
                evidence_status["evaluation_complete"] = rel.get("evaluation_complete", False)
                evidence_status["independent_gate_status"] = rel.get("independent_gate_status", "BLOCKED")
                evidence_status["blockers"] = rel.get("blockers", [])
        except Exception:
            pass

    return {
        "schema_version": 2,
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
        "current_run": current_run,
        "historical_runs": {
            "validation_2026-10-03": {"count": val_data.get("count"), "dice_mean": val_data.get("dice_mean_all_cases")},
            "test_2026-10-03": {"count": test_data.get("test_count"), "dice_mean": test_metrics.get("dice")},
        },
        "evidence_status": evidence_status,
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
        return str(resolve_dataset_path(Path(BASE_DIR), relative_path))

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
