"""One-process synthetic GPU concurrency check; does not represent patient cases."""
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.config import model_registry
from backend.services.model_service import InferenceBusyError

adapter = model_registry.get_primary_adapter()
engine = adapter.engine
if not adapter.is_loaded or str(engine.device).split(":")[0] != "cuda":
    raise RuntimeError("A verified checkpoint on CUDA is required")
tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
gray = np.zeros((512, 512), dtype=np.uint8)
torch.cuda.reset_peak_memory_stats()
start = threading.Barrier(4)

def run(_index):
    start.wait(timeout=10)
    begin = time.perf_counter()
    try:
        result = model_registry.predict(tensor, gray, pixel_spacing_mm=None)
        return {"status": "ok", "elapsed_ms": round((time.perf_counter() - begin) * 1000, 1),
                "device": result.get("provenance", {}).get("device")}
    except InferenceBusyError:
        return {"status": "busy", "elapsed_ms": round((time.perf_counter() - begin) * 1000, 1)}

with ThreadPoolExecutor(max_workers=4) as pool:
    outcomes = list(pool.map(run, range(4)))
torch.cuda.synchronize()
print(json.dumps({"device": torch.cuda.get_device_name(0), "outcomes": outcomes,
    "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
    "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
    "scope": "single process; four simultaneous synthetic requests, no HTTP or patient data"}))
