"""Measure loaded segmentation latency; synthetic inputs do not measure accuracy.

Use evaluation/evaluate_val.py for labelled image-level validation. This command
never invents labels, physical spacing, Dice, IoU or model comparison scores.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def benchmark_loaded_adapter(adapter, iterations=5):
    if not adapter.is_loaded:
        raise RuntimeError("Selected segmentation checkpoint is not loaded and verified.")
    engine = adapter.engine
    device = torch.device(engine.device)
    tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)

    def forward():
        engine.forward_probabilities(tensor)
        if device.type == "cuda":
            torch.cuda.synchronize(device)

    forward()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        forward()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "evidence_kind": "SYNTHETIC_INPUT_LATENCY_ONLY",
        "dataset": None, "accuracy_evaluated": False,
        "patient_independence_verified": False,
        "model": adapter.get_info(),
        "device": str(engine.device),
        "input_shape": list(tensor.shape), "warmup_iterations": 1,
        "iterations": iterations,
        "latency_ms": {"median": float(np.median(samples)), "p95": float(np.percentile(samples, 95)),
                       "samples": samples},
        "parameter_count": sum(p.numel() for p in engine.model.parameters()),
        "limitations": "Synthetic zero input; forward pass includes selected TTA and CPU result transfer. No accuracy or clinical performance inference.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/resource_audit/segmentation_latency.json")
    args = parser.parse_args()
    if not 1 <= args.iterations <= 100:
        parser.error("--iterations must be between 1 and 100")
    from backend.app.config import model_registry

    result = benchmark_loaded_adapter(model_registry.get_primary_adapter(), args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
