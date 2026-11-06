"""Numeric bounds for safely reporting physical image measurements."""

import math
import sys

from backend.core.image_utils import MAX_DECODED_IMAGE_PIXELS

# Measurement code squares spacing and multiplies it by the foreground pixel
# area before converting to cm². Keep that intermediate finite even for the
# largest image accepted by the decoder.
MAX_PIXEL_SPACING_MM = math.sqrt(
    sys.float_info.max / (MAX_DECODED_IMAGE_PIXELS * 100)
)


def normalize_pixel_spacing(value) -> float | None:
    """Return a positive, finite spacing that keeps area calculations finite."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        spacing = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(spacing) or not 0 < spacing <= MAX_PIXEL_SPACING_MM:
        return None
    return spacing
