"""Sequential synthetic end-to-end inference soak; not a clinical or HTTP benchmark."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_synthetic_image(seed: int = 20261029) -> np.ndarray:
    """Build a deterministic grayscale raster in memory without reading project data."""
    rng = np.random.default_rng(seed)
    height, width = 480, 640
    y, x = np.mgrid[0:height, 0:width]
    depth_falloff = 0.8 - 0.45 * (y / max(height - 1, 1))
    scanlines = 8.0 * np.sin(x / 5.0)
    speckle = rng.normal(0.0, 22.0, size=(height, width))
    signal = 104.0 * depth_falloff + scanlines + speckle
    raster = np.clip(signal, 0, 255).astype(np.uint8)

    # Synthetic shapes only exercise preprocessing and segmentation code paths.
    raster[((x - 318) / 78) ** 2 + ((y - 246) / 61) ** 2 <= 1.0] //= 3
    raster[((x - 430) / 28) ** 2 + ((y - 185) / 22) ** 2 <= 1.0] //= 2
    return raster


def nearest_rank_percentile(values: Sequence[float], percentile: float) -> float:
    """Return the nearest-rank percentile (rank = ceil(p * n))."""
    if not values:
        raise ValueError("values must not be empty")
    if not math.isfinite(percentile) or not 0 < percentile <= 100:
        raise ValueError("percentile must be in the range (0, 100]")
    ordered = sorted(float(value) for value in values)
    rank = math.ceil((percentile / 100.0) * len(ordered))
    return ordered[rank - 1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    if args.warmup < 0:
        parser.error("--warmup must be zero or greater")
    return args


def main() -> int:
    args = parse_args()
    from backend.app.config import CHECKPOINT_PATH, MODEL_SELECTION, model_registry, preprocessor

    adapter = model_registry.get_primary_adapter()
    engine = adapter.engine
    requested_device = torch.device(engine.device)
    expected_checkpoint_sha256 = str(MODEL_SELECTION.get("checkpoint_sha256", "")).lower()
    actual_checkpoint_sha256 = str(engine.model_checksum or "").lower()

    if not adapter.is_loaded or not CHECKPOINT_PATH:
        raise RuntimeError("A loaded, manifest-selected checkpoint is required for this soak")
    if not expected_checkpoint_sha256 or actual_checkpoint_sha256 != expected_checkpoint_sha256:
        raise RuntimeError("Loaded checkpoint checksum does not match the selected model manifest")
    if requested_device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; this benchmark does not silently fall back to CPU")

    cuda_index = requested_device.index
    if cuda_index is None:
        cuda_index = torch.cuda.current_device()
    cuda_device = torch.device("cuda", cuda_index)
    device_name = torch.cuda.get_device_name(cuda_device)

    synthetic_images = [
        build_synthetic_image(args.seed + index)
        for index in range(args.warmup + args.iterations)
    ]
    fixture_hashes = [
        hashlib.sha256(
            f"{image.shape}:{image.dtype}".encode("ascii") + image.tobytes()
        ).hexdigest()
        for image in synthetic_images
    ]
    fixture_set_sha256 = hashlib.sha256("".join(fixture_hashes).encode("ascii")).hexdigest()

    def run_one(image: np.ndarray):
        tensor_512, padded_gray, _transform, _iqa = preprocessor.preprocess_for_inference(image)
        result = model_registry.predict(tensor_512, padded_gray, pixel_spacing_mm=None)
        return tensor_512, padded_gray, result

    for image in synthetic_images[: args.warmup]:
        tensor_512, padded_gray, result = run_one(image)
        if str(result.get("provenance", {}).get("device", "")).split(":")[0] != "cuda":
            raise RuntimeError("Model fell back from CUDA during warmup")
        del tensor_512, padded_gray, result

    torch.cuda.synchronize(cuda_device)
    gc.collect()
    baseline_allocated = torch.cuda.memory_allocated(cuda_device)
    baseline_reserved = torch.cuda.memory_reserved(cuda_device)
    torch.cuda.reset_peak_memory_stats(cuda_device)

    total_ms: list[float] = []
    preprocessing_ms: list[float] = []
    inference_pipeline_ms: list[float] = []
    allocated_samples: list[int] = []

    measured_images = synthetic_images[args.warmup :]
    for image in measured_images:
        started = time.perf_counter()
        tensor_512, padded_gray, _transform, _iqa = preprocessor.preprocess_for_inference(image)
        preprocessed = time.perf_counter()
        result = model_registry.predict(tensor_512, padded_gray, pixel_spacing_mm=None)
        torch.cuda.synchronize(cuda_device)
        finished = time.perf_counter()

        result_device = str(result.get("provenance", {}).get("device", ""))
        if result_device.split(":")[0] != "cuda" or str(engine.device).split(":")[0] != "cuda":
            raise RuntimeError("Model fell back from CUDA during the soak")
        if result.get("provenance", {}).get("pixel_spacing_mm") is not None:
            raise RuntimeError("Synthetic soak unexpectedly used a pixel-spacing calibration")

        preprocessing_ms.append((preprocessed - started) * 1000.0)
        inference_pipeline_ms.append((finished - preprocessed) * 1000.0)
        total_ms.append((finished - started) * 1000.0)
        allocated_samples.append(torch.cuda.memory_allocated(cuda_device))
        del tensor_512, padded_gray, _transform, _iqa, result

    torch.cuda.synchronize(cuda_device)
    gc.collect()
    final_allocated = torch.cuda.memory_allocated(cuda_device)
    final_reserved = torch.cuda.memory_reserved(cuda_device)

    payload = {
        "status": "PASS",
        "benchmark_type": "SYNTHETIC_TECHNICAL_ONLY",
        "scope": (
            "sequential single-process in-memory raster; production preprocessing, model registry, "
            "segmentation postprocessing and response construction; no HTTP, PostgreSQL, concurrent "
            "clients, patient data or clinical validity claim"
        ),
        "patient_data_used": False,
        "clinical_performance_claim": False,
        "device": device_name,
        "device_index": cuda_index,
        "device_total_memory_bytes": torch.cuda.get_device_properties(cuda_device).total_memory,
        "model_version": MODEL_SELECTION.get("model_version"),
        "checkpoint_sha256": actual_checkpoint_sha256,
        "synthetic_input": {
            "shape": list(synthetic_images[0].shape),
            "dtype": str(synthetic_images[0].dtype),
            "count": len(synthetic_images),
            "unique_count": len(set(fixture_hashes)),
            "fixture_set_sha256": fixture_set_sha256,
            "pixel_spacing_mm": None,
        },
        "warmup_runs": args.warmup,
        "measured_runs": args.iterations,
        "latency_ms": {
            "preprocessing_p50": statistics.median(preprocessing_ms),
            "inference_pipeline_p50": statistics.median(inference_pipeline_ms),
            "end_to_end_p50": statistics.median(total_ms),
            "end_to_end_p95_nearest_rank": nearest_rank_percentile(total_ms, 95),
            "end_to_end_max": max(total_ms),
        },
        "cuda_memory_bytes": {
            "baseline_allocated_after_warmup": baseline_allocated,
            "baseline_reserved_after_warmup": baseline_reserved,
            "peak_allocated": torch.cuda.max_memory_allocated(cuda_device),
            "peak_reserved": torch.cuda.max_memory_reserved(cuda_device),
            "final_allocated_after_gc": final_allocated,
            "final_reserved_after_gc": final_reserved,
            "allocated_min_during_measured_runs": min(allocated_samples),
            "allocated_max_during_measured_runs": max(allocated_samples),
            "allocated_delta_after_gc": final_allocated - baseline_allocated,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
