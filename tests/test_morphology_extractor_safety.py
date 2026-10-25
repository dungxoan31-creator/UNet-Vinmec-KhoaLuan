import cv2
import numpy as np
import pytest

from backend.services.morphology_extractor import MorphologicalFeatureExtractor


def _assert_not_classified(result):
    assessment = result["cdss_classification"]
    assert assessment["orads_category"] is None
    assert assessment["iota_rule"] == "NOT_EVALUATED"
    assert assessment["malignancy_risk"] is None
    assert assessment["management"] is None


def test_empty_mask_does_not_establish_a_normal_ovary():
    result = MorphologicalFeatureExtractor().extract_features(
        np.zeros((64, 64), dtype=np.uint8),
        np.zeros((64, 64), dtype=np.uint8),
    )

    _assert_not_classified(result)
    assert result["acoustic_profile"]["posterior_shadow_index"] is None


def test_posterior_shadow_index_is_unknown_without_lateral_reference_tissue():
    image = np.full((96, 96), 100, dtype=np.uint8)
    mask = np.ones_like(image)

    result = MorphologicalFeatureExtractor().extract_features(image, mask)

    assert result["acoustic_profile"]["posterior_shadow_index"] is None


def test_posterior_shadow_index_is_unknown_when_reference_tissue_has_zero_intensity():
    image = np.zeros((96, 96), dtype=np.uint8)
    image[40:60, 30:66] = 100
    mask = np.zeros_like(image)
    cv2.rectangle(mask, (30, 20), (65, 39), 1, -1)

    result = MorphologicalFeatureExtractor().extract_features(image, mask)

    assert result["acoustic_profile"]["posterior_shadow_index"] is None


def test_mask_texture_does_not_assign_orads_or_management():
    image = np.zeros((96, 96), dtype=np.uint8)
    mask = np.zeros_like(image)
    cv2.circle(mask, (48, 48), 20, 1, -1)

    result = MorphologicalFeatureExtractor().extract_features(image, mask)

    _assert_not_classified(result)


def test_uncalibrated_mask_reports_pixels_without_fabricated_physical_units():
    image = np.zeros((96, 96), dtype=np.uint8)
    mask = np.zeros_like(image)
    cv2.circle(mask, (48, 48), 20, 1, -1)

    result = MorphologicalFeatureExtractor().extract_features(image, mask)

    measurements = result["measurements"]
    assert measurements["max_diameter_mm"] is None
    assert measurements["ortho_diameter_mm"] is None
    assert measurements["total_area_cm2"] is None
    assert measurements["perimeter_mm"] is None
    assert measurements["volume_cm3"] is None


@pytest.mark.parametrize(
    ("image", "mask"),
    [
        (np.zeros((0, 0), dtype=np.uint8), np.zeros((0, 0), dtype=np.uint8)),
        (np.zeros((32, 32), dtype=np.uint8), np.zeros((16, 32), dtype=np.uint8)),
        (np.zeros((32, 32, 3), dtype=np.uint8), np.zeros((32, 32), dtype=np.uint8)),
        (np.zeros((32, 32), dtype=np.uint8), np.full((32, 32), np.nan)),
    ],
)
def test_malformed_image_or_mask_dimensions_and_values_are_rejected(image, mask):
    with pytest.raises(ValueError):
        MorphologicalFeatureExtractor().extract_features(image, mask)
