"""Explicit, research-only binary mask transforms.

This module is deliberately separate from clinical inference. Callers must
provide every transform parameter, and the input mask is never modified.
"""

import cv2
import numpy as np

MASK_SHAPE = (512, 512)
MAX_COMPONENT_AREA = MASK_SHAPE[0] * MASK_SHAPE[1]


def _integer_parameter(name: str, value: object, *, minimum: int, maximum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _validate_mask(mask: np.ndarray) -> np.ndarray:
    try:
        array = np.asarray(mask)
    except (TypeError, ValueError) as exc:
        raise ValueError("mask must be a numeric 512x512 binary array") from exc

    if array.shape != MASK_SHAPE:
        raise ValueError("mask must have shape 512x512")
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.floating)
        or np.issubdtype(array.dtype, np.bool_)
    ):
        raise ValueError("mask must contain only numeric binary values")
    if not np.isfinite(array).all():
        raise ValueError("mask values must be finite")
    if not np.logical_or(array == 0, array == 1).all():
        raise ValueError("mask values must be binary 0 or 1")
    return np.array(array, dtype=np.uint8, copy=True)


def _validate_smoothing_kernel(value: int | None) -> int | None:
    if value is None:
        return None
    kernel_size = _integer_parameter(
        "smoothing_kernel_size", value, minimum=3, maximum=31
    )
    if kernel_size % 2 == 0:
        raise ValueError("smoothing_kernel_size must be odd")
    return kernel_size


def build_mask_candidate(
    mask: np.ndarray,
    *,
    min_component_area: int,
    closing_kernel_size: int,
    fill_holes: bool,
    smoothing_kernel_size: int | None,
) -> np.ndarray:
    """Return a new candidate mask using only explicitly selected transforms.

    Components smaller than the requested area are removed unless they touch
    the image border. Border-touching foreground is retained because the image
    may crop a lesion; enclosed background holes are handled separately.
    """
    source = _validate_mask(mask)
    min_area = _integer_parameter(
        "min_component_area", min_component_area, minimum=0, maximum=MAX_COMPONENT_AREA
    )
    closing_size = _integer_parameter(
        "closing_kernel_size", closing_kernel_size, minimum=0, maximum=31
    )
    if closing_size != 0 and (closing_size < 3 or closing_size % 2 == 0):
        raise ValueError("closing_kernel_size must be 0 or an odd value from 3 to 31")
    if type(fill_holes) is not bool:
        raise ValueError("fill_holes must be a bool")
    smoothing_size = _validate_smoothing_kernel(smoothing_kernel_size)

    if not source.any() or source.all():
        return source

    candidate = source
    if min_area > 0:
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
            candidate, connectivity=8
        )
        remove_component = np.zeros(component_count, dtype=bool)
        for label in range(1, component_count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            width = int(stats[label, cv2.CC_STAT_WIDTH])
            height = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])
            touches_border = (
                x == 0
                or y == 0
                or x + width == MASK_SHAPE[1]
                or y + height == MASK_SHAPE[0]
            )
            if area < min_area and not touches_border:
                remove_component[label] = True
        candidate[remove_component[labels]] = 0

    if closing_size >= 3:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (closing_size, closing_size)
        )
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, kernel)

    if fill_holes:
        padded = np.pad(candidate, 1, mode="constant", constant_values=0)
        outside = padded.copy()
        cv2.floodFill(outside, None, (0, 0), 2)
        enclosed_background = outside[1:-1, 1:-1] == 0
        candidate = candidate.copy()
        candidate[enclosed_background] = 1

    if smoothing_size is not None:
        probabilities = cv2.GaussianBlur(
            candidate.astype(np.float32), (smoothing_size, smoothing_size), 0
        )
        candidate = (probabilities >= 0.5).astype(np.uint8)

    return np.array(candidate, dtype=np.uint8, copy=True)
