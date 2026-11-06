import cv2
import numpy as np

from backend.services.morphology_extractor import separate_and_count_follicles


def test_separate_and_count_follicles_empty():
    empty_mask = np.zeros((512, 512), dtype=np.uint8)
    res = separate_and_count_follicles(empty_mask)
    assert res["count"] == 0
    assert res["count_in_range"] is None
    assert res["diameters_px"] == []
    assert res["diameters_mm"] is None


def test_separate_and_count_follicles_single():
    mask = np.zeros((512, 512), dtype=np.uint8)
    # Circle center (200, 200), radius 10 -> diameter ~ 20px
    cv2.circle(mask, (200, 200), 10, 1, -1)

    res = separate_and_count_follicles(mask, pixel_spacing_mm=0.2)
    assert res["count"] == 1
    assert len(res["diameters_px"]) == 1
    # Diameter ~ 20px
    assert 18.0 <= res["diameters_px"][0] <= 22.0
    # In mm: 20px * 0.2 = 4.0 mm
    assert 3.6 <= res["diameters_mm"][0] <= 4.4
    # 4.0 mm is in range [2.0, 9.0]
    assert res["count_in_range"] == 1


def test_separate_and_count_follicles_touching_split():
    mask = np.zeros((512, 512), dtype=np.uint8)
    # Two touching circles: center1 (200, 200) r=14, center2 (200, 224) r=14 (distance=24 < 28, overlapping)
    cv2.circle(mask, (200, 200), 14, 1, -1)
    cv2.circle(mask, (200, 224), 14, 1, -1)

    # Standard connectedComponents would see 1 component
    num_cc, _ = cv2.connectedComponents(mask)
    assert num_cc == 2  # background + 1 merged blob

    # Watershed separation must split them into 2 distinct follicles!
    res = separate_and_count_follicles(mask, min_distance_px=8)
    assert res["count"] == 2
    assert len(res["diameters_px"]) == 2


def test_separate_and_count_follicles_ovary_mask_boundary():
    follicle_mask = np.zeros((512, 512), dtype=np.uint8)
    # One follicle inside ovary (150, 150), one follicle outside ovary (350, 350)
    cv2.circle(follicle_mask, (150, 150), 10, 1, -1)
    cv2.circle(follicle_mask, (350, 350), 10, 1, -1)

    ovary_mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.circle(ovary_mask, (150, 150), 40, 1, -1)

    res = separate_and_count_follicles(follicle_mask, ovary_mask=ovary_mask)
    assert res["count"] == 1


def test_border_component_keeps_marker_when_an_interior_component_exists():
    mask = np.zeros((64, 64), dtype=np.uint8)
    cv2.circle(mask, (2, 20), 2, 1, -1)
    cv2.circle(mask, (32, 32), 6, 1, -1)

    result = separate_and_count_follicles(mask)

    assert cv2.connectedComponents(mask)[0] - 1 == 2
    assert result["count"] == 2
