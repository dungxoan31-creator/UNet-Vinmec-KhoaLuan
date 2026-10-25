"""Shared source-image decoding and physical calibration helpers."""

import logging
import math
import os

import cv2
from PIL import Image

from backend.core.calibration import normalize_pixel_spacing
from backend.core.image_utils import cv2_imread_unicode, is_within_decoded_image_limit
from backend.services.source_measurements import calibration_metadata

logger = logging.getLogger(__name__)


def validate_pixel_spacing(spacing: float | None) -> float | None:
    """Return a usable millimeter scale, rejecting invalid supplied values."""
    if spacing is None:
        return None
    normalized = normalize_pixel_spacing(spacing)
    if normalized is None:
        raise ValueError("pixel_spacing_mm must be positive, finite, and within the safe measurement range.")
    return normalized


def is_single_frame_ultrasound_dicom(dicom) -> bool:
    """The 2D model accepts a single ultrasound still image, not cine or other modalities."""
    try:
        return str(dicom.get("Modality", "")).upper() == "US" and int(dicom.get("NumberOfFrames", 1)) == 1
    except (TypeError, ValueError):
        return False


def _integer_dicom_value(value) -> int | None:
    """Return an integer-valued DICOM header element without coercing malformed types."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def decode_ultrasound_image(file_path: str, grayscale: bool = False):
    """Decode bounded raster or single-frame ultrasound DICOM pixels."""
    if not file_path.lower().endswith(".dcm"):
        try:
            with Image.open(file_path) as image_header:
                if not is_within_decoded_image_limit(*image_header.size):
                    return None
        except Exception:
            return None
        image = cv2_imread_unicode(
            file_path, cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
        )
        if image is None or not is_within_decoded_image_limit(image.shape[1], image.shape[0]):
            return None
        return image

    try:
        import pydicom

        dicom = pydicom.dcmread(file_path)
        if not is_single_frame_ultrasound_dicom(dicom):
            return None
        if not is_within_decoded_image_limit(
            getattr(dicom, "Columns", None), getattr(dicom, "Rows", None)
        ):
            return None
        rows, columns = int(dicom.Rows), int(dicom.Columns)
        samples_per_pixel = _integer_dicom_value(getattr(dicom, "SamplesPerPixel", None))
        photometric = str(getattr(dicom, "PhotometricInterpretation", "")).strip().upper()
        if samples_per_pixel is None:
            return None
        if photometric in ("MONOCHROME1", "MONOCHROME2", "PALETTE COLOR"):
            if samples_per_pixel != 1:
                return None
        elif photometric in ("RGB", "YBR_FULL", "YBR_FULL_422"):
            if samples_per_pixel != 3:
                return None
        else:
            return None

        bits_allocated = _integer_dicom_value(getattr(dicom, "BitsAllocated", None))
        bits_stored = _integer_dicom_value(getattr(dicom, "BitsStored", None))
        high_bit = _integer_dicom_value(getattr(dicom, "HighBit", None))
        pixel_representation = _integer_dicom_value(
            getattr(dicom, "PixelRepresentation", None)
        )
        allowed_bits = (8, 16) if photometric == "PALETTE COLOR" else (8,)
        if (
            bits_allocated not in allowed_bits
            or bits_stored != bits_allocated
            or high_bit != bits_stored - 1
            or pixel_representation != 0
        ):
            return None

        if samples_per_pixel == 3:
            planar_configuration = _integer_dicom_value(
                getattr(dicom, "PlanarConfiguration", None)
            )
            if planar_configuration not in (0, 1):
                return None
            if photometric == "YBR_FULL_422" and planar_configuration != 0:
                return None

        image = dicom.pixel_array
        if image.ndim == 4:
            if image.shape[0] != 1:
                return None
            image = image[0]
        elif image.ndim == 3 and samples_per_pixel == 1:
            if image.shape[0] != 1:
                return None
            image = image[0]
        if samples_per_pixel == 1:
            if image.ndim != 2 or image.shape != (rows, columns):
                return None
        elif image.ndim != 3 or image.shape != (rows, columns, samples_per_pixel):
            return None
        if not is_within_decoded_image_limit(image.shape[1], image.shape[0]):
            return None
        if photometric in ("YBR_FULL", "YBR_FULL_422") and not hasattr(
            dicom, "pixel_array_options"
        ):
            try:
                from pydicom.pixels import convert_color_space
            except ImportError:
                from pydicom.pixel_data_handlers.util import convert_color_space

            image = convert_color_space(image, photometric, "RGB")
        if photometric == "PALETTE COLOR":
            try:
                from pydicom.pixels import apply_color_lut
            except ImportError:
                from pydicom.pixel_data_handlers.util import apply_color_lut

            image = apply_color_lut(image, dicom)
            if image.ndim != 3 or image.shape[2] != 3:
                return None
            if image.dtype == "uint16":
                image = cv2.convertScaleAbs(image, alpha=1 / 257)
            elif image.dtype != "uint8":
                return None
        elif image.dtype != "uint8":
            image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        if photometric == "MONOCHROME1":
            image = cv2.bitwise_not(image)
        if image.ndim == 3:
            if grayscale:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                # Raster decoding uses OpenCV's BGR order; keep DICOM callers consistent.
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image
    except Exception:
        return None


def extract_dicom_calibration_spacing(file_path: str) -> float | None:
    """Extract isotropic millimeters per pixel from validated DICOM distance tags."""
    if not file_path.lower().endswith(".dcm"):
        return None
    try:
        import pydicom

        dcm = pydicom.dcmread(file_path, stop_before_pixels=True)
        us_regions = dcm.get("SequenceOfUltrasoundRegions")
        if us_regions is not None:
            # The current measurement pipeline stores one scalar for the whole image.
            # DICOM ultrasound regions can have independent scales, so accept only one
            # 2D spatial region that explicitly covers the full decoded image.
            if len(us_regions) != 1:
                return None
            region = us_regions[0]
            if getattr(region, "RegionSpatialFormat", None) != 1:
                return None

            columns, rows = getattr(dcm, "Columns", None), getattr(dcm, "Rows", None)
            if not is_within_decoded_image_limit(columns, rows):
                return None
            columns, rows = int(columns), int(rows)
            try:
                region_bounds = (
                    region.RegionLocationMinX0,
                    region.RegionLocationMinY0,
                    region.RegionLocationMaxX1,
                    region.RegionLocationMaxY1,
                )
                integer_bounds = tuple(int(value) for value in region_bounds)
                if any(isinstance(value, bool) or int(value) != value for value in region_bounds):
                    return None
            except (AttributeError, OverflowError, TypeError, ValueError):
                return None
            if integer_bounds != (0, 0, columns - 1, rows - 1):
                return None

            dx = getattr(region, "PhysicalDeltaX", None)
            dy = getattr(region, "PhysicalDeltaY", None)
            unit_x = getattr(region, "PhysicalUnitsXDirection", None)
            unit_y = getattr(region, "PhysicalUnitsYDirection", None)
            # DICOM physical unit 3 is centimeters; 4 is seconds and is not a spatial scale.
            if dx is None or dy is None or unit_x != 3 or unit_y != 3:
                return None

            spacing_x = float(dx) * 10.0
            spacing_y = float(dy) * 10.0
            if (
                math.isfinite(spacing_x)
                and math.isfinite(spacing_y)
                and spacing_x > 0
                and spacing_y > 0
                and math.isclose(spacing_x, spacing_y, rel_tol=0.001)
            ):
                # Apply the same arithmetic bound used at every other calibration
                # boundary after rounding; tiny values may round to zero.
                return normalize_pixel_spacing(round(spacing_x, 4))
            return None

        pixel_spacing = dcm.get("PixelSpacing")
        if pixel_spacing and len(pixel_spacing) >= 2:
            row_spacing, column_spacing = float(pixel_spacing[0]), float(pixel_spacing[1])
            if (
                math.isfinite(row_spacing)
                and math.isfinite(column_spacing)
                and row_spacing > 0
                and column_spacing > 0
                and math.isclose(row_spacing, column_spacing, rel_tol=0.001)
            ):
                return normalize_pixel_spacing(round(row_spacing, 4))
    except Exception as exc:
        logger.info("DICOM calibration tags could not be read: %s", exc)
    return None


def get_image_calibration(image_record) -> dict:
    """Return stored scale metadata, matching it against DICOM tags when available."""
    raw_path = getattr(image_record, "raw_path", None)
    dicom_spacing = (
        extract_dicom_calibration_spacing(raw_path)
        if isinstance(raw_path, (str, os.PathLike)) and os.path.isfile(raw_path)
        else None
    )
    return calibration_metadata(getattr(image_record, "pixel_spacing_mm", None), dicom_spacing)
