"""Reproducible Native-Space Segmentation Evaluator v1."""

import argparse
import csv
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
import torch

from evaluation.protocol import load_protocol, load_cases, audit_inputs, normalize_reference, resolve_dataset_path
from evaluation.segmentation_metrics import score_masks, aggregate_metrics


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def _save_histogram_png(values: List[float], output_path: Path, title: str = "Dice Distribution"):
    """Draw a 20-bin histogram [0, 1] using PIL/cv2 without GUI dependencies."""
    w, h = 600, 400
    img = np.full((h, w, 3), 255, dtype=np.uint8)

    bins = 20
    hist, _ = np.histogram(values, bins=bins, range=(0.0, 1.0))
    max_h = max(int(np.max(hist)), 1)

    margin_x, margin_y = 60, 50
    plot_w = w - 2 * margin_x
    plot_h = h - 2 * margin_y

    bar_w = plot_w // bins
    for i, count in enumerate(hist):
        bar_len = int((count / max_h) * plot_h)
        x0 = margin_x + i * bar_w
        y0 = h - margin_y - bar_len
        x1 = x0 + bar_w - 2
        y1 = h - margin_y
        cv2.rectangle(img, (x0, y0), (x1, y1), (180, 100, 30), -1)

    # Draw axes
    cv2.line(img, (margin_x, h - margin_y), (w - margin_x, h - margin_y), (0, 0, 0), 2)
    cv2.line(img, (margin_x, margin_y), (margin_x, h - margin_y), (0, 0, 0), 2)

    cv2.putText(img, f"{title} (N={len(values)})", (margin_x, margin_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(img, "0.0", (margin_x - 10, h - margin_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.putText(img, "1.0", (w - margin_x - 15, h - margin_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), img)


def evaluate_run(
    root: Path,
    protocol_path: Path,
    manifest_path: Path,
    output: Path,
    run_kind: str,
    engine: Optional[Any] = None,
    lock_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Execute complete reproducible native-space segmentation evaluation."""
    root = root.resolve()
    protocol_path = protocol_path.resolve()
    manifest_path = manifest_path.resolve()
    output = output.resolve()

    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory {output} already exists and is not empty. Overwrites are forbidden.")

    output.mkdir(parents=True, exist_ok=True)
    preds_dir = output / "predictions"
    preds_dir.mkdir(parents=True, exist_ok=True)
    dists_dir = output / "distributions"
    dists_dir.mkdir(parents=True, exist_ok=True)

    log_file = output / "run.log"
    log_fp = open(log_file, "w", encoding="utf-8")

    def log(msg: str):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = f"[{timestamp}] {msg}"
        print(line)
        log_fp.write(line + "\n")
        log_fp.flush()

    log(f"Starting evaluation run. run_kind={run_kind}, output={output}")

    # Load protocol & cases
    protocol = load_protocol(protocol_path)
    cases = load_cases(root, manifest_path)
    protocol_sha = _compute_sha256(protocol_path)
    manifest_sha = _compute_sha256(manifest_path)

    # Save protocol and input audit snapshot
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")

    audit = audit_inputs(root, cases, protocol, run_kind)
    (output / "input_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")

    # Failures file
    failures_csv = output / "failures.csv"
    with open(failures_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "errors"])
        writer.writeheader()
        if audit["failures"]:
            writer.writerows(audit["failures"])

    # Initial run_manifest
    run_manifest = {
        "schema_version": 1,
        "run_id": output.name,
        "run_kind": run_kind,
        "status": "RUNNING",
        "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha,
        "manifest_sha256": manifest_sha,
        "checkpoint_sha256": protocol["model"].get("checkpoint_sha256"),
        "counts": audit["counts"]
    }
    (output / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    if audit["status"] != "READY":
        run_manifest["status"] = audit["status"]
        run_manifest["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (output / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
        log(f"Audit status is {audit['status']}. Halting run.")
        log_fp.close()
        raise SystemExit(2)

    # Check lock if required
    if lock_path:
        log(f"Verifying protocol lock from {lock_path}")
        lock_data = json.loads(Path(lock_path).read_text(encoding="utf-8"))
        if lock_data.get("protocol_sha256") != protocol_sha:
            raise ValueError("Protocol lock mismatch: protocol file was modified")
        if lock_data.get("manifest_sha256") != manifest_sha:
            raise ValueError("Protocol lock mismatch: manifest file was modified")

    # Initialize Engine & Preprocessor
    if engine is None:
        from backend.services.inference_engine import InferenceEngine
        cp_path = root / protocol["model"]["checkpoint_path"]
        if not cp_path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {cp_path}")
        
        calc_cp_sha = _compute_sha256(cp_path)
        expected_cp_sha = (protocol["model"].get("checkpoint_sha256") or "").lower()
        if expected_cp_sha and calc_cp_sha != expected_cp_sha:
            raise ValueError(f"Checkpoint SHA256 mismatch: expected {expected_cp_sha}, got {calc_cp_sha}")

        engine = InferenceEngine(
            model_weights_path=str(cp_path),
            architecture=protocol["model"]["architecture"],
            threshold=protocol["inference"]["threshold"],
            device=protocol["inference"]["device"]
        )

    from backend.services.preprocessor import UltrasoundPreprocessor
    preprocessor = UltrasoundPreprocessor(target_size=tuple(protocol["preprocess"]["target_size"]))

    per_image_rows: List[Dict[str, Any]] = []

    try:
        log(f"Evaluating {len(cases)} cases...")
        for idx, case in enumerate(cases):
            sid = case["sample_id"]
            img_resolved = resolve_dataset_path(root, case["image_path"])
            mask_resolved = resolve_dataset_path(root, case["mask_path"])

            img_bytes = img_resolved.read_bytes()
            mask_bytes = mask_resolved.read_bytes()

            raw_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
            raw_gt = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
            gt_norm = normalize_reference(raw_gt)

            tensor_512, padded_gray, transform, _ = preprocessor.preprocess_for_inference(raw_img)
            pred_512 = engine.predict_binary(tensor_512)

            native_pred = preprocessor.inverse_letterbox_mask(pred_512, transform)
            native_pred = (native_pred > 0).astype(np.uint8)

            if native_pred.shape != raw_img.shape:
                raise ValueError(f"Prediction shape mismatch on sample {sid}: {native_pred.shape} vs {raw_img.shape}")

            # Save native binary prediction PNG (0 or 255 for standard PNG visualization)
            pred_png_path = preds_dir / f"{sid}.png"
            cv2.imwrite(str(pred_png_path), native_pred * 255)
            pred_sha = _compute_sha256(pred_png_path)

            scores = score_masks(native_pred, gt_norm)
            row_dict = {
                "sample_id": sid,
                "source_case_id": case.get("source_case_id", ""),
                "patient_id": case.get("patient_id", ""),
                "split": case.get("split", ""),
                "modality": case.get("modality", ""),
                "dice": scores["dice"],
                "iou": scores["iou"],
                "recall": scores["recall"],
                "precision": scores["precision"],
                "specificity": scores["specificity"],
                "hd95_px": scores["hd95_px"],
                "tp": scores["tp"],
                "fp": scores["fp"],
                "fn": scores["fn"],
                "tn": scores["tn"],
                "fp_area_px": scores["fp_area_px"],
                "fn_area_px": scores["fn_area_px"],
                "under_fraction": scores["under_fraction"],
                "over_fraction": scores["over_fraction"],
                "gt_empty": scores["gt_empty"],
                "pred_empty": scores["pred_empty"],
                "prediction_sha256": pred_sha
            }
            per_image_rows.append(row_dict)

            if (idx + 1) % 50 == 0 or (idx + 1) == len(cases):
                log(f"Processed {idx + 1}/{len(cases)} samples")

        # Readback verification
        log("Verifying readback of predictions...")
        for row in per_image_rows:
            sid = row["sample_id"]
            p_file = preds_dir / f"{sid}.png"
            if not p_file.exists():
                raise RuntimeError(f"Readback failure: missing prediction PNG {p_file}")
            read_img = cv2.imread(str(p_file), cv2.IMREAD_GRAYSCALE)
            read_binary = (read_img > 0).astype(np.uint8)
            # Compare sha
            if _compute_sha256(p_file) != row["prediction_sha256"]:
                raise RuntimeError(f"Readback SHA256 mismatch for sample {sid}")

        # Write per_image_metrics.csv
        per_image_csv = output / "per_image_metrics.csv"
        with open(per_image_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(per_image_rows[0].keys()))
            writer.writeheader()
            writer.writerows(per_image_rows)

        # Write per_case_metrics.csv if case IDs are present
        per_case_csv = output / "per_case_metrics.csv"
        case_groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in per_image_rows:
            cid = r.get("source_case_id") or r.get("sample_id")
            case_groups.setdefault(cid, []).append(r)

        per_case_rows = []
        for cid, items in case_groups.items():
            valid_dices = [item["dice"] for item in items if item["dice"] is not None]
            valid_ious = [item["iou"] for item in items if item["iou"] is not None]
            per_case_rows.append({
                "source_case_id": cid,
                "patient_id": items[0].get("patient_id", ""),
                "n_images": len(items),
                "mean_dice": float(np.mean(valid_dices)) if valid_dices else None,
                "mean_iou": float(np.mean(valid_ious)) if valid_ious else None
            })
        with open(per_case_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["source_case_id", "patient_id", "n_images", "mean_dice", "mean_iou"])
            writer.writeheader()
            writer.writerows(per_case_rows)

        # Statistical Aggregation
        summary = aggregate_metrics(per_image_rows, bootstrap_seed=protocol["evaluation"].get("bootstrap_seed", 42))
        summary["schema_version"] = 1
        summary["run_id"] = output.name
        summary["run_kind"] = run_kind
        summary["status"] = "COMPLETE"
        summary["counts"] = {
            "total_samples": len(per_image_rows),
            "nonempty_gt_samples": sum(1 for r in per_image_rows if not r["gt_empty"]),
            "empty_gt_samples": sum(1 for r in per_image_rows if r["gt_empty"])
        }
        summary["protocol_sha256"] = protocol_sha
        summary["manifest_sha256"] = manifest_sha
        summary["checkpoint_sha256"] = protocol["model"].get("checkpoint_sha256")

        summary_file = output / "summary.json"
        summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Distribution plot
        dice_values = [r["dice"] for r in per_image_rows if r["dice"] is not None]
        _save_histogram_png(dice_values, dists_dir / "dice_histogram.png", title="Dice Coefficient Distribution")

        run_manifest["status"] = "COMPLETE"
        run_manifest["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (output / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

        log("Evaluation run completed successfully.")
        log_fp.close()
        return summary

    except Exception as e:
        log(f"Evaluation failed with exception: {e}")
        run_manifest["status"] = "PARTIAL"
        run_manifest["error"] = str(e)
        run_manifest["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (output / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
        log_fp.close()
        raise


def main():
    parser = argparse.ArgumentParser(description="Run reproducible native-space segmentation evaluation.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repo root directory")
    parser.add_argument("--protocol", type=Path, required=True, help="Path to protocol JSON")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to manifest CSV")
    parser.add_argument("--run-kind", type=str, required=True, choices=["validation_dry_run", "retrospective_test_replay", "independent_test"])
    parser.add_argument("--output", type=Path, required=True, help="Output directory for immutable run artifacts")
    parser.add_argument("--lock", type=Path, default=None, help="Optional lock file for freeze verification")

    args = parser.parse_args()
    summary = evaluate_run(
        root=args.root,
        protocol_path=args.protocol,
        manifest_path=args.manifest,
        output=args.output,
        run_kind=args.run_kind,
        lock_path=args.lock
    )
    print(f"Run {args.run_kind} completed. Primary Dice Mean: {summary['primary']['dice']['mean']}")


if __name__ == "__main__":
    main()
