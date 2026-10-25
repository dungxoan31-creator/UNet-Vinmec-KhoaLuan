"""RLE decoding must validate stored data before allocating a mask."""

import numpy as np
import pytest

from backend.core.image_utils import MAX_DECODED_IMAGE_PIXELS
from backend.services.inference_engine import InferenceEngine


@pytest.mark.parametrize(
    "rle",
    [
        None,
        [],
        {"shape": [2, 2], "counts": [2, 1], "first_val": 0},
        {"shape": [2, 2], "counts": [5], "first_val": 0},
        {"shape": [2, 2], "counts": [1, -1, 4], "first_val": 0},
        {"shape": [2, 2], "counts": [0, 4], "first_val": 0},
        {"shape": [2, 2], "counts": [4], "first_val": 2},
        {"shape": [2, 2], "counts": [4], "first_val": True},
        {"shape": [2.0, 2], "counts": [4], "first_val": 0},
        {"shape": [0, 2], "counts": [4], "first_val": 0},
        {"shape": [0, 10**100], "counts": [], "first_val": 0},
    ],
)
def test_rle_decoder_rejects_malformed_run_lengths(rle):
    engine = InferenceEngine.__new__(InferenceEngine)

    with pytest.raises(ValueError):
        engine.rle_to_mask(rle)


def test_rle_decoder_rejects_oversized_shape_before_allocating(monkeypatch):
    engine = InferenceEngine.__new__(InferenceEngine)
    monkeypatch.setattr(
        np,
        "zeros",
        lambda *_args, **_kwargs: pytest.fail("oversized shape allocated before validation"),
    )

    with pytest.raises(ValueError, match="size|shape|pixel"):
        engine.rle_to_mask(
            {"shape": [5001, 5000], "counts": [25_005_000], "first_val": 0}
        )


def test_rle_decoder_rejects_oversized_zero_area_dimension_before_allocating(monkeypatch):
    engine = InferenceEngine.__new__(InferenceEngine)
    monkeypatch.setattr(
        np,
        "zeros",
        lambda *_args, **_kwargs: pytest.fail("oversized shape allocated before validation"),
    )

    with pytest.raises(ValueError, match="size|shape|pixel"):
        engine.rle_to_mask(
            {
                "shape": [0, MAX_DECODED_IMAGE_PIXELS + 1],
                "counts": [],
                "first_val": 0,
            }
        )


def test_rle_decoder_accepts_a_valid_small_mask():
    engine = InferenceEngine.__new__(InferenceEngine)
    result = engine.rle_to_mask(
        {"shape": [2, 3], "counts": [2, 2, 2], "first_val": 0}
    )

    np.testing.assert_array_equal(result, np.array([[0, 0, 1], [1, 0, 0]], dtype=np.uint8))


def test_review_request_bounds_rle_runs_before_scanning_counts():
    from backend.schemas.schemas import DoctorReviewRequest

    class OversizedCounts(list):
        def __len__(self):
            return 512 * 512 + 1

        def __iter__(self):
            raise AssertionError("oversized RLE counts were scanned before the length bound")

    with pytest.raises(ValueError, match="maximum run count"):
        DoctorReviewRequest.validate_mask_rle(
            {
                "shape": [512, 512],
                "counts": OversizedCounts(),
                "first_val": 0,
            }
        )
