"""Validation-only verification, error analysis and isolated API benchmark for a frozen model."""

import argparse
import importlib.metadata
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.train_baseline_unet import ComboLoss
from ai_training.train_unetplusplus_resnet34 import batch_metrics
from backend.services.inference_engine import InferenceEngine
from evaluation.measure_candidate_api_latency import percentile
from scripts.audit_milestone3_evidence import ROOT, SPLIT, readable, rows, sha, write_csv, write_json
from scripts.render_unified_vinmec_error_analysis import _overlay


def environment():
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "opencv-python", "fastapi", "httpx", "segmentation-models-pytorch")
        },
    }


def record(command):
    return {
        "started_at": datetime.now(UTC).isoformat(),
        "command": command,
        "seed": 42,
        "environment": environment(),
        "test_inference_performed": False,
    }


def freeze(output):
    output.mkdir(parents=True, exist_ok=False)
    configs = [
        json.loads((ROOT / f"checkpoints/{folder}/run_config.json").read_text(encoding="utf-8"))
        for folder in ("standard_unet_gray_imagenet_norm_2026-10-06", "unetplusplus_resnet34_2026-10-06")
    ]
    protocol = {
        **record("python scripts/verify_milestone3_validation.py freeze"),
        "selection_scope": "retrospective_selection_among_existing_single_seed_runs",
        "primary_criterion": "highest mean per-image Validation Dice at fixed threshold 0.5",
        "secondary_checks": [
            "Validation IoU / Recall / Precision",
            "train_validation_gap",
            "strict_checkpoint_load",
            "prototype_smoke",
        ],
        "normalization_control": "matched grayscale ImageNet mean/std; initialization differs",
        "additional_seed_training": "not_performed_in_this_audit; stability remains unverified",
        "candidate_configs": configs,
        "test_used_for_selection": False,
    }
    write_json(output / "selection_protocol.json", protocol)
    winner = max(configs, key=lambda config: config["best_validation"]["dice"])
    manifest = json.loads((ROOT / "evaluation/selected_model_unetplusplus_candidate.json").read_text(encoding="utf-8"))
    if winner["best_checkpoint_sha256"] != manifest["checkpoint_sha256"]:
        raise ValueError("Validation winner differs from the verified candidate manifest")
    if sha(ROOT / manifest["checkpoint"]) != manifest["checkpoint_sha256"]:
        raise ValueError("Winner checkpoint SHA mismatch")
    for config in configs:
        for field, name in (
            ("train_csv_sha256", "train.csv"),
            ("validation_csv_sha256", "val.csv"),
            ("manifest_sha256", "manifest.json"),
        ):
            if sha(SPLIT / name) != config[field]:
                raise ValueError(f"Frozen split does not match {config['architecture']}: {name}")
    manifest.update(
        {
            "locked_at": datetime.now(UTC).isoformat(),
            "status": "validation_selected_research_model_locked",
            "candidate_only": False,
            "best_epoch": winner["best_epoch"],
            "seed": winner["seed"],
            "selection_protocol": str((output / "selection_protocol.json").relative_to(ROOT)),
            "split_hashes": {name: sha(SPLIT / name) for name in ("train.csv", "val.csv", "test.csv", "manifest.json")},
            "validation_metrics_historical": winner["best_validation"],
            "train_validation_dice_gap": winner["train_metrics_at_best_epoch"]["dice"]
            - winner["best_validation"]["dice"],
            "test_evaluation": None,
            "deployment_scope": "isolated_research_prototype; default_manifest_remains_historical_standard_unet",
            "patient_level_independence": "not_verified",
            "clinical_ground_truth_approval": "not_verified",
        }
    )
    write_json(output / "model_lock.json", manifest)
    print(json.dumps({"winner": manifest["model"], "checkpoint_sha256": manifest["checkpoint_sha256"]}))


def validation(output):
    audit = json.loads((output.parent / "verified_data/dataset_audit.json").read_text(encoding="utf-8"))
    if audit["errors"] or audit["fallback_in_unified_index"]:
        raise ValueError("Canonical data integrity gate failed")
    lock = json.loads((output / "model_lock.json").read_text(encoding="utf-8"))
    started = record(
        "python scripts/verify_milestone3_validation.py validation --output " + output.relative_to(ROOT).as_posix()
    )
    dataset = OvarianUltrasoundDataset(str(SPLIT / "val.csv"), is_train=False)
    engine = InferenceEngine(
        str(ROOT / lock["checkpoint"]),
        architecture=lock["architecture"],
        input_normalization=lock["input_normalization"],
    )
    if not engine.is_model_ready or engine.model_checksum != lock["checkpoint_sha256"]:
        raise ValueError("Frozen checkpoint could not be loaded")
    per_image, metric_values, loss_sum = [], {}, 0.0
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    loader = DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)
    prediction_dir = output / "validation_predictions"
    prediction_dir.mkdir(exist_ok=False)
    index = 0
    with torch.no_grad():
        for batch in loader:
            images = engine.prepare_model_input(batch["image"])
            targets = batch["mask"].to(engine.device)
            with torch.amp.autocast(device_type=engine.device, enabled=engine.device == "cuda"):
                logits = engine.model(images)
                loss = criterion(logits, targets)
            metrics = {key: value.cpu().tolist() for key, value in batch_metrics(logits, targets).items()}
            for key, values in metrics.items():
                metric_values.setdefault(key, []).extend(values)
            loss_sum += loss.item() * len(images)
            predictions = (torch.sigmoid(logits) >= lock["threshold"]).cpu().numpy()[:, 0]
            references = targets.cpu().numpy()[:, 0] >= 0.5
            for j, (prediction, reference) in enumerate(zip(predictions, references, strict=True)):
                row = dataset.df.iloc[index]
                path = prediction_dir / f"{row['case_id']}.png"
                Image.fromarray(prediction.astype(np.uint8) * 255).save(path)
                per_image.append(
                    {
                        "case_id": str(row["case_id"]),
                        "image_path": row["image_path"],
                        "reference_mask_path": row["mask_path"],
                        "prediction_path": path.relative_to(ROOT).as_posix(),
                        "checkpoint_sha256": engine.model_checksum,
                        "threshold": lock["threshold"],
                        "metric_resolution": "512x512 letterboxed; AMP matches training validation",
                        "reference_status": "supplied_reference_label; expert_approval_not_verified",
                        "fp": int((prediction & ~reference).sum()),
                        "fn": int((~prediction & reference).sum()),
                        "tp": int((prediction & reference).sum()),
                        "tn": int((~prediction & ~reference).sum()),
                        "reference_foreground": int(reference.sum()),
                        **{key: values[j] for key, values in metrics.items()},
                    }
                )
                index += 1
    write_csv(output / "validation_per_image.csv", per_image)
    measured = {key: statistics.mean(values) for key, values in metric_values.items()}
    measured["loss"] = loss_sum / len(dataset)
    write_json(
        output / "validation_summary.json",
        {
            **started,
            "finished_at": datetime.now(UTC).isoformat(),
            "checkpoint_sha256": engine.model_checksum,
            "strict_load": True,
            "validation_csv": (SPLIT / "val.csv").relative_to(ROOT).as_posix(),
            "validation_csv_sha256": sha(SPLIT / "val.csv"),
            "count": len(dataset),
            "metrics": measured,
            "historical_metrics": lock["validation_metrics_historical"],
            "difference_from_history": {k: measured[k] - lock["validation_metrics_historical"][k] for k in measured},
            "interpretation": "computational segmentation agreement with supplied labels; not clinically validated metrics or diagnostic accuracy",
            "empty_reference_count": sum(r["reference_foreground"] == 0 for r in per_image),
        },
    )
    cases = []
    for category, ordered in (
        ("best_dice", sorted(per_image, key=lambda r: r["dice"], reverse=True)),
        ("false_positive", sorted(per_image, key=lambda r: r["fp"], reverse=True)),
        ("false_negative", sorted(per_image, key=lambda r: r["fn"], reverse=True)),
    ):
        for row in ordered[:5]:
            sample = dataset[dataset.df.index[dataset.df["case_id"] == row["case_id"]][0]]
            img = (sample["image"][0].numpy() * 255).round().astype(np.uint8)
            ref = sample["mask"][0].numpy() >= 0.5
            pred = readable(ROOT / row["prediction_path"]) > 0
            composite = _overlay(img, ref, (0, 220, 120))
            composite[pred] = (composite[pred] * 0.55 + np.asarray((255, 65, 65)) * 0.45).astype(np.uint8)
            panel = np.concatenate(
                (
                    np.repeat(img[:, :, None], 3, axis=2),
                    _overlay(img, ref, (0, 220, 120)),
                    _overlay(img, pred, (255, 65, 65)),
                    composite,
                ),
                axis=1,
            )
            # Reference and prediction are kept in separate columns to avoid ambiguity in the composite.
            folder = output / "error_analysis"
            folder.mkdir(exist_ok=True)
            panel_path = folder / f"{category}_{row['case_id']}.png"
            Image.fromarray(panel).save(panel_path)
            cases.append({"category": category, **row, "panel_path": panel_path.relative_to(ROOT).as_posix()})
    write_csv(output / "error_analysis_summary.csv", cases)
    write_json(
        output / "error_analysis_summary.json",
        {
            "checkpoint_sha256": engine.model_checksum,
            "split": "validation",
            "cases": cases,
            "description": "columns: preprocessed image, reference overlay, prediction overlay, composite; FN=missing pixels; FP=excess pixels; no pathology labels",
        },
    )
    print(json.dumps({"count": len(dataset), "validation": measured, "cases": len(cases)}))


def serve(output, port):
    import uvicorn
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    os.environ["MODEL_SELECTION_MANIFEST"] = str(output / "model_lock.json")
    from backend.db import database

    runtime = output / "runtime"
    runtime.mkdir(exist_ok=True)
    database.DB_PATH = str(runtime / "technical_test.sqlite3")
    database.engine = create_engine(f"sqlite:///{database.DB_PATH}", connect_args={"check_same_thread": False})
    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
    from backend.app import config

    for name, child in (("UPLOAD_DIR", "uploads"), ("REPORTS_DIR", "reports")):
        folder = runtime / child
        folder.mkdir(exist_ok=True)
        setattr(config, name, str(folder))
    config.DATA_DIR = str(runtime)
    from backend.app.main import app

    # Instrument only this isolated, sequential benchmark process; production code is unchanged.
    timings = {}
    engine = config.model_registry.get_primary_adapter().engine

    def timed_method(instance, name, key):
        original = getattr(instance, name)

        def wrapped(*args, **kwargs):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            start = time.perf_counter()
            result = original(*args, **kwargs)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            timings[key] = (time.perf_counter() - start) * 1000
            return result

        setattr(instance, name, wrapped)

    timed_method(config.preprocessor, "preprocess_for_inference", "preprocessing_ms")
    timed_method(engine, "prepare_model_input", "input_transfer_normalization_ms")
    timed_method(engine.model, "forward", "forward_ms")
    timed_method(engine, "run_inference", "engine_total_ms")

    @app.middleware("http")
    async def timing_header(request, call_next):
        timings.clear()
        start = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api/predict/") and response.status_code == 200:
            timings["server_api_ms"] = (time.perf_counter() - start) * 1000
            timings["postprocessing_ms"] = (
                timings["engine_total_ms"] - timings["forward_ms"] - timings["input_transfer_normalization_ms"]
            )
            timings["api_overhead_ms"] = (
                timings["server_api_ms"] - timings["preprocessing_ms"] - timings["engine_total_ms"]
            )
            response.headers["X-Audit-Timings"] = json.dumps(timings)
        return response

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def summary(values):
    return (
        {"n": len(values), "p50_ms": statistics.median(values), "p95_ms": percentile(values, 0.95)} if values else None
    )


def benchmark(output, port):
    provenance = record(
        "python scripts/verify_milestone3_validation.py benchmark --output " + output.relative_to(ROOT).as_posix()
    )
    lock = json.loads((output / "model_lock.json").read_text(encoding="utf-8"))
    val_rows = rows(SPLIT / "val.csv")
    chosen = [val_rows[i] for i in np.linspace(0, len(val_rows) - 1, 24, dtype=int)]
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
        "MODEL_SELECTION_MANIFEST": str(output / "model_lock.json"),
        "E2E_BASE_URL": f"http://127.0.0.1:{port}",
        "SMOKE_VALIDATION_CSV": str(SPLIT / "val.csv"),
    }
    server_log = (output / "api_server.txt").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, __file__, "serve", "--output", str(output), "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    samples, failures = [], []
    try:
        with httpx.Client(base_url=env["E2E_BASE_URL"], timeout=120) as client:
            deadline = time.monotonic() + 90
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Isolated API exited; inspect api_server.txt")
                try:
                    if client.get("/").status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("API startup exceeded 90 seconds")
                time.sleep(0.5)
            for row in chosen:
                path = ROOT / row["image_path"]
                upload = client.post("/api/upload", files={"file": (path.name, path.read_bytes(), "image/jpeg")})
                upload.raise_for_status()
                ids = upload.json()
                try:
                    warmup = client.post(f"/api/predict/{ids['image_id']}")
                    if warmup.status_code != 200:
                        failures.append(
                            {"image": row["image_path"], "status": warmup.status_code, "detail": warmup.text}
                        )
                        continue
                    for repeat in range(3):
                        start = time.perf_counter()
                        response = client.post(f"/api/predict/{ids['image_id']}")
                        elapsed = (time.perf_counter() - start) * 1000
                        response.raise_for_status()
                        result = response.json()
                        if result["provenance"]["model_checksum"] != lock["checkpoint_sha256"]:
                            raise ValueError("API is running a different checkpoint")
                        samples.append(
                            {
                                "image": row["image_path"],
                                "repeat": repeat + 1,
                                "server_pipeline_ms": result["inference_time_ms"],
                                "http_total_ms": elapsed,
                                **json.loads(response.headers["X-Audit-Timings"]),
                            }
                        )
                finally:
                    client.delete(f"/api/cases/{ids['study_id']}").raise_for_status()
            smoke = subprocess.run(
                ["node", "tests/browser_hitl_smoke.js"],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            (output / "browser_smoke.txt").write_text(smoke.stdout + smoke.stderr, encoding="utf-8")
            write_json(
                output / "browser_smoke_run.json",
                {
                    **provenance,
                    "command": "node tests/browser_hitl_smoke.js",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "exit_code": smoke.returncode,
                    "checkpoint_sha256": lock["checkpoint_sha256"],
                    "validation_csv": str(SPLIT.relative_to(ROOT) / "val.csv"),
                    "base_url": env["E2E_BASE_URL"],
                    "scope": "technical_ui_test; isolated_db; no_clinical_participant",
                },
            )
    finally:
        server.terminate()
        server.wait(timeout=20)
        server_log.close()
    write_csv(output / "api_latency_requests.csv", samples)
    write_json(
        output / "api_latency_summary.json",
        {
            **provenance,
            "finished_at": datetime.now(UTC).isoformat(),
            "checkpoint_sha256": lock["checkpoint_sha256"],
            "validation_csv_sha256": sha(SPLIT / "val.csv"),
            "protocol": "24 evenly spaced Validation rows, 1 warm-up per image, 3 sequential measured requests; localhost HTTP; isolated DB",
            "attempted_images": len(chosen),
            "successful_images": len({r["image"] for r in samples}),
            "measured_requests": len(samples),
            "failed_images": failures,
            "server_pipeline": summary([r["server_pipeline_ms"] for r in samples]),
            "http_total": summary([r["http_total_ms"] for r in samples]),
            "components": {
                key: summary([r[key] for r in samples])
                for key in (
                    "preprocessing_ms",
                    "input_transfer_normalization_ms",
                    "forward_ms",
                    "postprocessing_ms",
                    "api_overhead_ms",
                )
            },
            "timing_boundary": "server field includes preprocessing and engine, excludes decoding, DB commit and response serialization; HTTP total includes those",
            "instrumentation": "isolated method wrappers, perf_counter and CUDA synchronization; postprocessing = engine total minus transfer/normalization and forward; adds synchronization overhead",
            "limitation": "engineering benchmark on one device; no concurrency, network or clinical SLA claims",
        },
    )
    print(json.dumps({"requests": len(samples), "failed_images": len(failures), "smoke_exit": smoke.returncode}))


def tests(output):
    command = [sys.executable, "-m", "pytest", "-q"]
    run = record(" ".join(command))
    run["seed"] = None
    run["seed_note"] = "No suite-wide seed supplied; individual tests may set fixture-local seeds."
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    log = completed.stdout + completed.stderr
    (output / "pytest_latest.txt").write_text(log, encoding="utf-8")
    counts = {
        name: int(match.group(1)) if (match := re.search(rf"(\d+) {name}", log)) else 0
        for name in ("passed", "failed", "errors", "skipped", "warnings")
    }
    write_json(
        output / "pytest_latest.json",
        {
            **run,
            "finished_at": datetime.now(UTC).isoformat(),
            "exit_code": completed.returncode,
            "counts": counts,
            "log": (output / "pytest_latest.txt").relative_to(ROOT).as_posix(),
            "scope": "entire existing software suite; not clinician evaluation or selected-model Test evaluation",
        },
    )
    print(json.dumps({"exit_code": completed.returncode, "counts": counts}))


def comparator(output):
    from ai_training.train_unetplusplus_resnet34 import run_epoch
    from backend.models.unet import StandardUNet

    provenance = record(
        "python scripts/verify_milestone3_validation.py comparator --output " + output.relative_to(ROOT).as_posix()
    )
    config = json.loads(
        (ROOT / "checkpoints/standard_unet_gray_imagenet_norm_2026-10-06/run_config.json").read_text(encoding="utf-8")
    )
    checkpoint = ROOT / config["best_checkpoint"].replace("\\", "/")
    if sha(checkpoint) != config["best_checkpoint_sha256"]:
        raise ValueError("Comparator checkpoint SHA mismatch")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    dataset = OvarianUltrasoundDataset(str(SPLIT / "val.csv"), is_train=False)
    metrics = run_epoch(
        model, DataLoader(dataset, batch_size=2, num_workers=0), ComboLoss(bce_weight=0.5, dice_weight=0.5), device
    )
    write_json(
        output / "standard_comparator_validation.json",
        {
            **provenance,
            "finished_at": datetime.now(UTC).isoformat(),
            "strict_load": True,
            "checkpoint_sha256": sha(checkpoint),
            "count": len(dataset),
            "metrics": metrics,
            "validation_csv_sha256": sha(SPLIT / "val.csv"),
            "difference_from_history": {key: metrics[key] - config["best_validation"][key] for key in metrics},
            "interpretation": "computational agreement with supplied labels; clinician approval not verified",
        },
    )
    print(json.dumps(metrics))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "validation", "serve", "benchmark", "tests", "comparator"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8026)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if args.mode == "freeze":
        freeze(output)
    elif args.mode == "validation":
        validation(output)
    elif args.mode == "serve":
        serve(output, args.port)
    elif args.mode == "tests":
        tests(output)
    elif args.mode == "comparator":
        comparator(output)
    else:
        benchmark(output, args.port)


if __name__ == "__main__":
    main()
