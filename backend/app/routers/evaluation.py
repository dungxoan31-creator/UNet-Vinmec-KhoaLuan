"""
Evaluation and Benchmark Samples Router for Ovarian Ultrasound AI.
Serves validation/test metrics, failure cases, and workstation sample bundles.
"""

import base64
import csv
import json
import math
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from backend.app.config import SYNTHETIC_DEMO_MODE
from backend.app.security import require_evaluation_reviewer

router = APIRouter(dependencies=[Depends(require_evaluation_reviewer)])


def _deny_benchmark_sample_access_in_synthetic_demo():
    if SYNTHETIC_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail="Benchmark case images are unavailable in synthetic-only demo mode.",
        )

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
VAL_SUMMARY_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "summary.json")
TEST_METRICS_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "test_summary.json")
SPLIT_MANIFEST_PATH = os.path.join(BASE_DIR, "ai_training", "splits", "vinmec_2d_retrain_2026-10-03", "manifest.json")
PER_IMAGE_CSV_PATH = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "per_image.csv")
PRED_MASKS_DIR = os.path.join(BASE_DIR, "evaluation", "archive", "retrain_2d_2026-10-03", "validation", "prediction_masks")
CURRENT_RUN_PATH = os.path.join(BASE_DIR, "evaluation", "current_run.json")
RELEASE_STATUS_PATH = os.path.join(BASE_DIR, "evaluation", "milestone_3_final", "report", "release_status.json")
EVALUATION_SOURCE_EXTENSIONS = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"})
EVALUATION_SAMPLE_METRIC_FIELDS = ("dice", "iou", "recall", "precision", "specificity")
EVALUATION_SAMPLE_COUNT_FIELDS = ("tp", "fp", "fn", "tn")
EVALUATION_SAMPLE_REQUIRED_FIELDS = frozenset(
    ("case_id", "image_path", "mask_path", *EVALUATION_SAMPLE_METRIC_FIELDS, *EVALUATION_SAMPLE_COUNT_FIELDS)
)
LEGACY_ARCHIVE_BLOCK_REASON = (
    "Legacy evaluation provenance is unverified; archived metrics and samples are withheld."
)


def _legacy_archive_status() -> dict[str, Any]:
    """Keep the pre-v2 archive unavailable until its source chain is reviewed and bound."""
    return {
        "status": "BLOCKED",
        "metrics_available": False,
        "samples_available": False,
        "manifest_available": Path(SPLIT_MANIFEST_PATH).is_file(),
        "reason": LEGACY_ARCHIVE_BLOCK_REASON,
    }


def _require_legacy_archive_available() -> None:
    status = _legacy_archive_status()
    if status["status"] != "AVAILABLE":
        raise HTTPException(status_code=503, detail=status["reason"])


def _read_file_b64(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _resolve_project_artifact(path: str | Path) -> Path:
    """Resolve a benchmark artifact only when it remains inside the project root."""
    root = Path(BASE_DIR).resolve()
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.") from exc
    return resolved


def _resolve_sample_source(recorded_path: str) -> Path:
    normalized = recorded_path.replace("\\", "/") if isinstance(recorded_path, str) else ""
    relative = Path(normalized)
    if (
        not relative.parts
        or relative.is_absolute()
        or relative.parts[0].lower() != "dataset"
        or ".." in relative.parts
        or relative.suffix.lower() not in EVALUATION_SOURCE_EXTENSIONS
    ):
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.")

    resolved = _resolve_project_artifact(Path(BASE_DIR) / relative)
    dataset_root = (Path(BASE_DIR) / "dataset").resolve()
    try:
        resolved.relative_to(dataset_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=503, detail="Evaluation sample source files are unavailable.")
    return resolved


def _resolve_evaluation_summary(path: str | Path) -> Path:
    evaluation_root = (Path(BASE_DIR) / "evaluation").resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(BASE_DIR) / candidate
    resolved = _resolve_project_artifact(candidate)
    try:
        resolved.relative_to(evaluation_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evaluation summary not accessible.") from exc
    if resolved.suffix.lower() != ".json":
        raise HTTPException(status_code=404, detail="Evaluation summary not accessible.")
    return resolved


def _resolve_prediction_mask(case_id: str) -> Path:
    if (
        not case_id
        or case_id in {".", ".."}
        or any(separator in case_id for separator in ("/", "\\", ":"))
        or any(ord(character) < 32 or ord(character) == 127 for character in case_id)
    ):
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.")

    prediction_root = Path(PRED_MASKS_DIR).resolve()
    resolved = _resolve_project_artifact(prediction_root / f"{case_id}.png")
    try:
        resolved.relative_to(prediction_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evaluation artifact not accessible.") from exc
    return resolved


def _reject_nonfinite_json_constant(value: str):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _validate_current_run_summary(pointer: dict[str, Any], summary: dict[str, Any]):
    required_fields = {"counts", "primary", "secondary"}
    if not required_fields.issubset(summary):
        raise ValueError("Current run summary is missing required sections.")

    counts = summary["counts"]
    primary = summary["primary"]
    secondary = summary["secondary"]
    if not isinstance(counts, dict) or not isinstance(primary, dict) or not isinstance(secondary, dict):
        raise ValueError("Current run summary has invalid section types.")

    count_fields = ("total_samples", "nonempty_gt_samples", "empty_gt_samples")
    if any(
        isinstance(counts.get(field), bool)
        or not isinstance(counts.get(field), int)
        or counts[field] < 0
        for field in count_fields
    ):
        raise ValueError("Current run summary has invalid sample counts.")
    if counts["total_samples"] != counts["nonempty_gt_samples"] + counts["empty_gt_samples"]:
        raise ValueError("Current run summary sample counts do not reconcile.")

    bounded_metrics = {"dice", "iou", "recall", "precision", "specificity"}
    required_metrics = bounded_metrics | {"hd95_px"}
    if not required_metrics.issubset(primary):
        raise ValueError("Current run summary is missing primary metrics.")
    statistic_fields = ("mean", "median", "std", "min", "max")
    for name in required_metrics:
        metric = primary[name]
        if not isinstance(metric, dict):
            raise ValueError("Current run primary metric has an invalid shape.")
        for field in statistic_fields:
            value = metric.get(field)
            if value is None:
                continue
            try:
                valid = (
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(value)
                    and value >= 0
                    and (name not in bounded_metrics or value <= 1)
                )
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Current run summary contains an invalid metric value.")
        for field in ("n_valid", "n_null"):
            value = metric.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Current run summary contains invalid metric counts.")

    agreement = secondary.get("all_images_agreement_dice")
    if not isinstance(agreement, dict):
        raise ValueError("Current run summary has invalid agreement metrics.")
    secondary_metrics = {
        "all_images_agreement_dice": agreement.get("mean"),
        "micro_dice": secondary.get("micro_dice"),
        "micro_iou": secondary.get("micro_iou"),
    }
    for value in secondary_metrics.values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError("Current run summary contains invalid secondary metrics.")

    for field in ("checkpoint_sha256", "protocol_sha256", "manifest_sha256"):
        pointer_hash = pointer.get(field)
        summary_hash = summary.get(field)
        if pointer_hash is None and summary_hash is None:
            continue
        if (
            not isinstance(pointer_hash, str)
            or not isinstance(summary_hash, str)
            or len(pointer_hash) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in pointer_hash)
            or pointer_hash.lower() != summary_hash.lower()
        ):
            raise ValueError("Current run pointer hash does not match its summary.")

    if summary.get("run_id") != pointer.get("run_id"):
        raise ValueError("Current run pointer does not match the summary run ID.")
    return counts, primary, secondary, agreement


@router.get("/metrics")
def get_evaluation_metrics():
    """
    Returns the current run plus an explicit blocked state for the unverified legacy archive.
    """
    # Expose pointer availability separately so a stale pointer cannot imply a completed run.
    current_run = None
    current_run_status = {
        "run_id": None,
        "status": "NO_POINTER",
        "artifact_available": False,
    }
    if SYNTHETIC_DEMO_MODE:
        current_run_status["status"] = "SYNTHETIC_DEMO_BLOCKED"
    elif os.path.exists(CURRENT_RUN_PATH):
        current_run_status["status"] = "INVALID_POINTER"
        try:
            with open(CURRENT_RUN_PATH, encoding="utf-8") as f:
                ptr = json.load(f, parse_constant=_reject_nonfinite_json_constant)
            if not isinstance(ptr, dict):
                raise ValueError("Current run pointer must be a JSON object.")
            run_id = ptr.get("run_id")
            if not isinstance(run_id, str) or not run_id.strip():
                raise ValueError("Current run pointer has no valid run ID.")
            current_run_status["run_id"] = run_id
            sum_path = ptr.get("summary_path")
            if not isinstance(sum_path, str) or not sum_path.strip():
                raise ValueError("Current run pointer has no summary path.")
            full_sum_path = _resolve_evaluation_summary(sum_path)
            if not full_sum_path.is_file():
                current_run_status["status"] = "ARTIFACT_MISSING"
            else:
                current_run_status["status"] = "ARTIFACT_INVALID"
                with open(full_sum_path, encoding="utf-8") as sf:
                    sum_data = json.load(sf, parse_constant=_reject_nonfinite_json_constant)
                if not isinstance(sum_data, dict):
                    raise ValueError("Current run summary must be a JSON object.")
                counts, primary, secondary, agreement = _validate_current_run_summary(ptr, sum_data)
                current_run = {
                    "run_id": run_id,
                    "run_kind": ptr.get("run_kind"),
                    "label": ptr.get("label", run_id),
                    "status": ptr.get("status", "COMPLETE"),
                    "is_historical": ptr.get("run_kind") == "retrospective_test_replay",
                    "checkpoint_sha256": ptr.get("checkpoint_sha256"),
                    "protocol_sha256": ptr.get("protocol_sha256"),
                    "manifest_sha256": ptr.get("manifest_sha256"),
                    "counts": counts,
                    "primary": {
                        key: {
                            field: metric.get(field)
                            for field in (
                                "mean",
                                "median",
                                "std",
                                "min",
                                "max",
                                "n_valid",
                                "n_null",
                                "null_reason",
                            )
                        }
                        for key, metric in primary.items()
                    },
                    "secondary": {
                        "micro_dice": secondary.get("micro_dice"),
                        "micro_iou": secondary.get("micro_iou"),
                        "all_images_agreement_dice": agreement.get("mean"),
                    },
                }
                current_run_status.update(status="AVAILABLE", artifact_available=True)
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
                rel = json.load(rf, parse_constant=_reject_nonfinite_json_constant)
                evidence_status["prototype_ready"] = rel.get("prototype_ready", True)
                evidence_status["evaluation_complete"] = rel.get("evaluation_complete", False)
                evidence_status["independent_gate_status"] = rel.get("independent_gate_status", "BLOCKED")
                evidence_status["blockers"] = rel.get("blockers", [])
        except Exception:
            pass

    return {
        "schema_version": 2,
        "archived_split_status": _legacy_archive_status(),
        "train": {
            "count": None,
            "dataset": "Historical archive (source provenance unverified)",
            "loss_function": None,
        },
        "validation": {
            "count": None,
            "dice_mean": None,
            "dice_std": None,
            "iou_mean": None,
            "iou_std": None,
            "recall_mean": None,
            "precision_mean": None,
            "specificity": None,
            "checkpoint_sha256": None,
            "dataset": "Historical archive (source provenance unverified)",
        },
        "test": {
            "count": None,
            "dice_mean": None,
            "iou_mean": None,
            "recall_mean": None,
            "precision_mean": None,
            "specificity": None,
            "specificity_normal_cases": None,
            "checkpoint_sha256": None,
            "patient_level_independence_verified": False,
            "dataset": "Historical archive (source provenance unverified)",
        },
        "current_run": current_run,
        "current_run_status": current_run_status,
        "historical_runs": {
            "status": "BLOCKED",
        },
        "evidence_status": evidence_status,
    }


def _read_evaluation_sample_rows() -> list[dict[str, Any]] | None:
    if not os.path.isfile(PER_IMAGE_CSV_PATH):
        return None

    rows = []
    try:
        with open(PER_IMAGE_CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not EVALUATION_SAMPLE_REQUIRED_FIELDS.issubset(reader.fieldnames or ()):
                raise HTTPException(status_code=503, detail="Evaluation sample records are invalid.")

            for row in reader:
                try:
                    case_id = (row["case_id"] or "").strip()
                    image_path = (row["image_path"] or "").strip()
                    mask_path = (row["mask_path"] or "").strip()
                    metrics = {field: float(row[field]) for field in EVALUATION_SAMPLE_METRIC_FIELDS}
                    counts = {field: int(row[field]) for field in EVALUATION_SAMPLE_COUNT_FIELDS}
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    raise HTTPException(
                        status_code=503, detail="Evaluation sample records are invalid."
                    ) from exc

                if (
                    not case_id
                    or not image_path
                    or not mask_path
                    or not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in metrics.values())
                    or any(value < 0 for value in counts.values())
                ):
                    raise HTTPException(status_code=503, detail="Evaluation sample records are invalid.")

                rows.append(
                    {
                        "case_id": case_id,
                        "image_path": image_path,
                        "mask_path": mask_path,
                        **metrics,
                        **counts,
                    }
                )
    except (csv.Error, OSError, UnicodeError) as exc:
        raise HTTPException(status_code=503, detail="Evaluation sample records are unavailable.") from exc

    return rows


@router.get(
    "/samples",
    dependencies=[Depends(_deny_benchmark_sample_access_in_synthetic_demo)],
)
def get_evaluation_samples(
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Returns list of validation benchmark samples with failure categories.
    """
    _require_legacy_archive_available()
    rows = _read_evaluation_sample_rows()
    if rows is None:
        return []

    samples = []
    for row in rows:
        dice = row["dice"]
        recall = row["recall"]
        precision = row["precision"]
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
                "case_id": row["case_id"],
                "image_path": row["image_path"],
                "mask_path": row["mask_path"],
                "dice": round(dice, 4),
                "iou": round(row["iou"], 4),
                "recall": round(recall, 4),
                "precision": round(precision, 4),
                "specificity": round(row["specificity"], 4),
                "failure_category": cat,
                **{field: row[field] for field in EVALUATION_SAMPLE_COUNT_FIELDS},
            }
        )

    page_samples = samples[offset : offset + limit]
    for sample in page_samples:
        _resolve_sample_source(sample["image_path"])
        _resolve_sample_source(sample["mask_path"])

    return page_samples


@router.get(
    "/samples/{case_id}/workstation-bundle",
    dependencies=[Depends(_deny_benchmark_sample_access_in_synthetic_demo)],
)
def get_sample_workstation_bundle(case_id: str):
    """
    Loads complete bundle for a benchmark sample to render in the Doctor Workstation.
    """
    _require_legacy_archive_available()
    rows = _read_evaluation_sample_rows()
    if rows is None:
        raise HTTPException(status_code=404, detail="Dataset evaluation records not found.")

    target_row = next((row for row in rows if row["case_id"] == str(case_id).strip()), None)
    if target_row is None:
        raise HTTPException(status_code=404, detail=f"Case ID {case_id} not found in validation split.")

    raw_img_rel = target_row["image_path"].replace("\\", "/")
    gt_mask_rel = target_row["mask_path"].replace("\\", "/")
    pred_mask_path = str(_resolve_prediction_mask(case_id))
    img_full_path = str(_resolve_sample_source(raw_img_rel))
    gt_full_path = str(_resolve_sample_source(gt_mask_rel))

    img_b64 = _read_file_b64(img_full_path)
    gt_b64 = _read_file_b64(gt_full_path)
    pred_b64 = _read_file_b64(pred_mask_path)

    if not img_b64:
        raise HTTPException(status_code=404, detail=f"Image file for sample {case_id} not accessible.")

    dice = target_row["dice"]
    iou = target_row["iou"]

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
            "recall": round(target_row["recall"], 4),
            "precision": round(target_row["precision"], 4),
        },
        "measurements": {"calibrated": False},
        "quality_gate": {
            "status": "NOT_ASSESSED",
            "message": "Điểm Dice lịch sử là độ đo phân đoạn, không phải phê duyệt lâm sàng.",
        },
        "provenance": {
            "model_name": "Standard U-Net (Baseline)",
            "checkpoint_sha256": "5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e",
            "dataset_source": "Historical archive; source provenance unverified",
        },
    }


@router.get(
    "/samples/{case_id}/download/{artifact_type}",
    dependencies=[Depends(_deny_benchmark_sample_access_in_synthetic_demo)],
)
def download_evaluation_artifact(case_id: str, artifact_type: str):
    """
    UC-75: Download specific evaluation artifact (image, ground_truth, prediction, overlay).
    Requires a clinical role; source-image de-identification is not verified here.
    """
    valid_types = {"image", "ground_truth", "prediction", "overlay"}
    if artifact_type.lower() not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Loại artifact '{artifact_type}' không hợp lệ. Chọn một trong: {', '.join(sorted(valid_types))}",
        )

    _require_legacy_archive_available()
    rows = _read_evaluation_sample_rows()
    if rows is None:
        raise HTTPException(status_code=404, detail="Dataset evaluation records not found.")

    target_row = next((row for row in rows if row["case_id"] == str(case_id).strip()), None)
    if target_row is None:
        raise HTTPException(status_code=404, detail=f"Case ID {case_id} not found in validation split.")

    raw_img_rel = target_row["image_path"].replace("\\", "/")
    gt_mask_rel = target_row["mask_path"].replace("\\", "/")
    pred_mask_path = str(_resolve_prediction_mask(case_id))
    img_full_path = str(_resolve_sample_source(raw_img_rel))
    gt_full_path = str(_resolve_sample_source(gt_mask_rel))

    art = artifact_type.lower()
    if art == "image":
        if not os.path.isfile(img_full_path):
            raise HTTPException(status_code=404, detail="Image file not accessible.")
        return FileResponse(
            img_full_path,
            media_type="image/jpeg",
            filename=f"evaluation_{case_id}_image.jpg",
        )
    elif art == "ground_truth":
        if not os.path.isfile(gt_full_path):
            raise HTTPException(status_code=404, detail="Ground truth mask file not accessible.")
        return FileResponse(
            gt_full_path,
            media_type="image/png",
            filename=f"evaluation_{case_id}_gt.png",
        )
    elif art == "prediction":
        if not os.path.isfile(pred_mask_path):
            raise HTTPException(status_code=404, detail="Prediction mask file not accessible.")
        return FileResponse(
            pred_mask_path,
            media_type="image/png",
            filename=f"evaluation_{case_id}_pred.png",
        )
    elif art == "overlay":
        if not os.path.isfile(img_full_path) or not os.path.isfile(pred_mask_path):
            raise HTTPException(status_code=404, detail="Required files for overlay not accessible.")
        img = cv2.imread(img_full_path)
        mask = cv2.imread(pred_mask_path, cv2.IMREAD_GRAYSCALE)
        if img is None or mask is None:
            raise HTTPException(status_code=422, detail="Failed to decode images for overlay generation.")
        if mask.shape[:2] != img.shape[:2]:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        overlay = img.copy()
        mask_bool = mask > 0
        overlay[mask_bool] = (
            overlay[mask_bool].astype(float) * 0.6 + np.array([0, 255, 0], dtype=float) * 0.4
        ).astype(np.uint8)
        _, enc = cv2.imencode(".png", overlay)
        return Response(
            content=enc.tobytes(),
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=evaluation_{case_id}_overlay.png"},
        )
