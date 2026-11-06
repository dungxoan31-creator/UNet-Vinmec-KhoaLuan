from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "audit_remediation_2026_10_28"
    / "gpu_soak.py"
)
if not BENCHMARK_PATH.exists():
    pytest.skip(
        f"Benchmark artifact not found at {BENCHMARK_PATH} (gitignored or absent in fresh checkout).",
        allow_module_level=True,
    )

SPEC = importlib.util.spec_from_file_location("synthetic_gpu_soak", BENCHMARK_PATH)
assert SPEC is not None and SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


def test_synthetic_image_is_deterministic_and_in_memory() -> None:
    first = BENCHMARK.build_synthetic_image(seed=17)
    second = BENCHMARK.build_synthetic_image(seed=17)

    assert first.shape == (480, 640)
    assert first.dtype == np.uint8
    assert np.array_equal(first, second)
    assert not np.array_equal(first, BENCHMARK.build_synthetic_image(seed=18))
    assert first.std() > 0


def test_nearest_rank_percentile_uses_rank_ceil_p_n() -> None:
    values = list(range(1, 51))

    assert BENCHMARK.nearest_rank_percentile(values, 50) == 25
    assert BENCHMARK.nearest_rank_percentile(values, 95) == 48
    assert BENCHMARK.nearest_rank_percentile(values, 100) == 50


@pytest.mark.parametrize(
    ("values", "percentile"),
    [([], 95), ([1, 2], 0), ([1, 2], 100.1), ([1, 2], float("nan"))],
)
def test_nearest_rank_percentile_rejects_invalid_inputs(values, percentile) -> None:
    with pytest.raises(ValueError):
        BENCHMARK.nearest_rank_percentile(values, percentile)
