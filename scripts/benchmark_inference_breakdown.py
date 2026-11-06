"""
Comprehensive Empirical Latency & Stage Breakdown Benchmark.
Measures:
- Preprocessing (Letterbox 512x512 + CLAHE clip=2.0)
- Model Forward Pass (U-Net++ ResNet34 Native + Horizontal-Flip TTA)
- Vectorized Postprocessing (keep[labels] CC Filtering + Morphological closing)
- Morphometry (ISUOG Caliper d1/d2 + Geometric features)
- Mask Encoding (Lossless RLE + Overlay Base64)
- Total End-to-End Latency
Compares: GPU (NVIDIA RTX 3050 Laptop GPU) vs CPU Fallback.
Data: Validation Cohort from ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import SELECTION_MANIFEST_PATH, model_registry, preprocessor  # noqa: E402
from backend.core.dataset_paths import resolve_dataset_path  # noqa: E402
from backend.core.image_utils import cv2_imread_unicode  # noqa: E402


def percentile(data: list[float], pct: float) -> float:
    arr = np.array(data)
    return float(np.percentile(arr, pct))


def run_benchmark(sample_size: int = 15, repeats_per_image: int = 5):
    print("=" * 70)
    print("OVARIAN ULTRASOUND AI DECISION SUPPORT SYSTEM - LATENCY BENCHMARK")
    print("=" * 70)

    # 1. Hardware Info
    cuda_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_available else "N/A"
    print(f"Device: {device_name if cuda_available else 'CPU'}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CPU Threads: {os.cpu_count()}")

    # 2. Check Model Adapter
    adapter = model_registry.get_primary_adapter()
    if not adapter.is_loaded:
        raise RuntimeError("Selected checkpoint could not be loaded or SHA-256 mismatch.")
    manifest_meta = json.loads(SELECTION_MANIFEST_PATH.read_text(encoding="utf-8"))
    print(f"Model: {manifest_meta.get('model', 'U-Net++')}")
    print(f"Architecture: {manifest_meta.get('architecture')}")
    print(f"Checkpoint SHA-256: {manifest_meta.get('checkpoint_sha256')[:16]}...")
    print(f"Threshold: {manifest_meta.get('threshold')}, TTA: {manifest_meta.get('horizontal_flip_tta')}")
    print("-" * 70)

    # 3. Load Validation Images
    val_csv_path = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv"
    with open(val_csv_path, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    valid_images = []
    for row in reader:
        resolved = resolve_dataset_path(ROOT, row["image_path"])
        if resolved and resolved.is_file():
            valid_images.append(resolved)
        if len(valid_images) >= sample_size:
            break

    print(f"Selected {len(valid_images)} representative validation images for benchmarking.")
    print("-" * 70)

    # 4. Warm-up GPU
    print("Executing 5 GPU warm-up iterations to compile CUDA kernels...")
    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    dummy_gray = np.zeros((512, 512), dtype=np.uint8)
    for _ in range(5):
        adapter.engine.run_inference(dummy_tensor, dummy_gray)
    if cuda_available:
        torch.cuda.synchronize()
    print("Warm-up complete. Starting timed benchmark runs...\n")

    # 5. Measure Stage-by-Stage Breakdown on GPU
    timings = {
        "read_image_ms": [],
        "letterbox_clahe_ms": [],
        "forward_tta_ms": [],
        "postprocess_mask_ms": [],
        "calipers_morphology_ms": [],
        "rle_overlay_ms": [],
        "end_to_end_ms": [],
    }

    engine = adapter.engine

    for img_idx, img_path in enumerate(valid_images):
        for rep in range(repeats_per_image):
            t_total_start = time.perf_counter()

            # Stage 1: Read Image
            t0 = time.perf_counter()
            img_bgr = cv2_imread_unicode(str(img_path), flags=cv2.IMREAD_COLOR)
            t_read = (time.perf_counter() - t0) * 1000

            # Stage 2: Letterbox & CLAHE Preprocessing
            t0 = time.perf_counter()
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            padded_gray, scale_params = preprocessor.letterbox_resize(img_gray)
            enhanced = preprocessor.clahe.apply(padded_gray)
            tensor_512 = torch.from_numpy(enhanced).float().unsqueeze(0).unsqueeze(0) / 255.0
            t_prep = (time.perf_counter() - t0) * 1000

            # Stage 3: Forward Pass with TTA (GPU)
            if cuda_available:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            probs_512 = engine.forward_probabilities(tensor_512)
            if cuda_available:
                torch.cuda.synchronize()
            t_forward = (time.perf_counter() - t0) * 1000

            # Stage 4: Post-processing Mask
            t0 = time.perf_counter()
            mask_512 = engine.post_process_mask(probs_512)
            clean_mask = preprocessor.inverse_letterbox_mask(mask_512, scale_params)
            t_post = (time.perf_counter() - t0) * 1000

            # Stage 5: Caliper & Morphology Extraction
            t0 = time.perf_counter()
            measurements = engine.extract_calipers_and_measurements(clean_mask, pixel_spacing_mm=0.2)
            t_calipers = (time.perf_counter() - t0) * 1000

            # Stage 6: RLE & Overlay Base64 Encoding
            t0 = time.perf_counter()
            _ = engine.mask_to_rle(clean_mask)
            _ = engine.generate_overlay_base64(img_gray, clean_mask, measurements)
            t_rle = (time.perf_counter() - t0) * 1000

            t_total = (time.perf_counter() - t_total_start) * 1000

            timings["read_image_ms"].append(t_read)
            timings["letterbox_clahe_ms"].append(t_prep)
            timings["forward_tta_ms"].append(t_forward)
            timings["postprocess_mask_ms"].append(t_post)
            timings["calipers_morphology_ms"].append(t_calipers)
            timings["rle_overlay_ms"].append(t_rle)
            timings["end_to_end_ms"].append(t_total)

    total_runs = len(timings["end_to_end_ms"])

    def stats_dict(vals):
        return {
            "mean": round(float(np.mean(vals)), 2),
            "std": round(float(np.std(vals)), 2),
            "median_p50": round(percentile(vals, 50), 2),
            "p90": round(percentile(vals, 90), 2),
            "p95": round(percentile(vals, 95), 2),
            "min": round(float(np.min(vals)), 2),
            "max": round(float(np.max(vals)), 2),
        }

    report = {
        "benchmark_metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device": device_name if cuda_available else "CPU",
            "samples": len(valid_images),
            "repeats_per_sample": repeats_per_image,
            "total_runs": total_runs,
            "model_version": manifest_meta.get("model_version"),
            "checkpoint_sha256": manifest_meta.get("checkpoint_sha256"),
        },
        "gpu_breakdown_ms": {k: stats_dict(v) for k, v in timings.items()},
    }

    # Print Summary Table
    print(f"BENCHMARK RESULTS (N={total_runs} runs on {device_name}):")
    print("-" * 75)
    print(f"{'Pipeline Stage':<28} | {'Mean (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'Std (ms)':<8}")
    print("-" * 75)
    stage_names = [
        ("Image Read (Unicode)", "read_image_ms"),
        ("Letterbox & CLAHE", "letterbox_clahe_ms"),
        ("PyTorch Forward + TTA", "forward_tta_ms"),
        ("Postprocess (Vectorized)", "postprocess_mask_ms"),
        ("ISUOG Calipers & Morph", "calipers_morphology_ms"),
        ("RLE + Overlay Base64", "rle_overlay_ms"),
        ("TOTAL END-TO-END", "end_to_end_ms"),
    ]
    for label, key in stage_names:
        s = report["gpu_breakdown_ms"][key]
        print(f"{label:<28} | {s['mean']:<10} | {s['median_p50']:<10} | {s['p95']:<10} | {s['std']:<8}")
    print("-" * 75)

    # 6. Save JSON report
    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "latency_benchmark_breakdown.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Latency benchmark report exported to: {out_file}")


if __name__ == "__main__":
    run_benchmark(sample_size=15, repeats_per_image=5)
