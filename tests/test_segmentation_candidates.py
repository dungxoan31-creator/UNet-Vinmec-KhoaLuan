import numpy as np
import pytest

from backend.services.segmentation_candidates import build_mask_candidate


def candidate(mask, **overrides):
    parameters = {
        "min_component_area": 0,
        "closing_kernel_size": 0,
        "fill_holes": False,
        "smoothing_kernel_size": None,
    }
    parameters.update(overrides)
    return build_mask_candidate(mask, **parameters)


def test_component_filter_uses_explicit_area():
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[100:110, 100:110] = 1
    mask[300, 300:302] = 1

    result = candidate(mask, min_component_area=3)

    assert result[100:110, 100:110].sum() == 100
    assert result[300, 300:302].sum() == 0
    assert result.sum() == 100


def test_hole_fill_is_opt_in():
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[100:111, 100:111] = 1
    mask[105, 105] = 0

    unchanged = candidate(mask, fill_holes=False)
    filled = candidate(mask, fill_holes=True)

    assert unchanged[105, 105] == 0
    assert filled[105, 105] == 1
    assert unchanged.sum() == 120
    assert filled.sum() == 121


def test_closing_is_disabled_at_zero():
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[100:111, 100:111] = 1
    mask[105, 105] = 0

    result = candidate(mask, closing_kernel_size=0)

    np.testing.assert_array_equal(result, mask)


def test_border_component_is_preserved():
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[0:2, 0:2] = 1
    mask[20:22, 20:22] = 1

    result = candidate(mask, min_component_area=5)

    assert result[0:2, 0:2].sum() == 4
    assert result[20:22, 20:22].sum() == 0
    assert result.sum() == 4


@pytest.mark.parametrize("value", [0, 1])
def test_empty_and_full_masks_are_noops(value):
    mask = np.full((512, 512), value, dtype=np.uint8)

    result = candidate(
        mask,
        min_component_area=262144,
        closing_kernel_size=3,
        fill_holes=True,
        smoothing_kernel_size=3,
    )

    np.testing.assert_array_equal(result, mask)
    assert result.dtype == np.uint8
    assert not np.shares_memory(result, mask)


@pytest.mark.parametrize(
    "mask",
    [
        np.zeros((511, 512), dtype=np.uint8),
        np.zeros((512, 512, 1), dtype=np.uint8),
        np.full((512, 512), 2, dtype=np.uint8),
        np.full((512, 512), np.nan, dtype=np.float32),
        np.full((512, 512), np.inf, dtype=np.float32),
        np.full((512, 512), "0", dtype=object),
    ],
)
def test_invalid_shape_or_values_raise(mask):
    with pytest.raises(ValueError):
        candidate(mask)


@pytest.mark.parametrize(
    "parameters",
    [
        {"min_component_area": -1},
        {"min_component_area": 262145},
        {"min_component_area": True},
        {"closing_kernel_size": 1},
        {"closing_kernel_size": 2},
        {"closing_kernel_size": 32},
        {"closing_kernel_size": True},
        {"fill_holes": 1},
        {"smoothing_kernel_size": 1},
        {"smoothing_kernel_size": 2},
        {"smoothing_kernel_size": 33},
        {"smoothing_kernel_size": True},
    ],
)
def test_invalid_shape_or_values_raise_for_parameters(parameters):
    mask = np.zeros((512, 512), dtype=np.uint8)
    with pytest.raises(ValueError):
        candidate(mask, **parameters)


def test_input_is_not_mutated():
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[100:111, 100:111] = 1
    mask[105, 105] = 0
    original = mask.copy()

    result = candidate(
        mask,
        min_component_area=2,
        closing_kernel_size=3,
        fill_holes=True,
        smoothing_kernel_size=3,
    )

    np.testing.assert_array_equal(mask, original)
    assert result.dtype == np.uint8
    assert result.shape == (512, 512)
    assert not np.shares_memory(result, mask)
