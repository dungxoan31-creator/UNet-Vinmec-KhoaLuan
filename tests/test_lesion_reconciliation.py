"""Proposals must never assign a lesion ID across ambiguous mask edits."""
import numpy as np
import pytest

from backend.services.lesion_reconciliation import propose_component_links


def test_area_reordering_keeps_identity_by_overlap_not_rank():
    first = np.zeros((32, 32), np.uint8)
    second = np.zeros_like(first)
    first[2:8, 2:8] = 1
    second[20:28, 20:28] = 1
    edited = np.zeros_like(first)
    edited[2:10, 2:10] = 1
    edited[20:25, 20:25] = 1
    result = propose_component_links({"first": first, "second": second}, edited)
    assert {item["previous_id"] for item in result["unambiguous"]} == {"first", "second"}
    assert result["ambiguous"] == []


def test_split_requires_confirmation_and_does_not_duplicate_identity():
    previous = np.zeros((32, 32), np.uint8)
    previous[4:16, 4:16] = 1
    edited = previous.copy()
    edited[4:16, 9] = 0
    result = propose_component_links({"old": previous}, edited)
    assert result["unambiguous"] == []
    assert len(result["ambiguous"]) == 2
    assert all(item["previous_ids"] == ["old"] for item in result["ambiguous"])


def test_merge_requires_confirmation_without_selecting_one_prior_identity():
    left = np.zeros((32, 32), np.uint8)
    right = np.zeros_like(left)
    left[4:10, 4:10] = 1
    right[4:10, 15:21] = 1
    merged = left | right
    merged[6, 9:16] = 1
    result = propose_component_links({"a": left, "b": right}, merged)
    assert result["unambiguous"] == []
    assert result["ambiguous"][0]["previous_ids"] == ["a", "b"]


def test_disappeared_and_new_region_are_not_silently_linked():
    old = np.zeros((32, 32), np.uint8)
    old[2:5, 2:5] = 1
    current = np.zeros_like(old)
    current[20:23, 20:23] = 1
    result = propose_component_links({"old": old}, current)
    assert result["unambiguous"] == []
    assert result["missing_previous_ids"] == ["old"]
    assert len(result["new_components"]) == 1


def test_overlapping_prior_regions_are_rejected():
    mask = np.zeros((32, 32), np.uint8)
    mask[4:10, 4:10] = 1
    with pytest.raises(ValueError):
        propose_component_links({"a": mask, "b": mask}, mask)


def test_diagonal_contacts_use_the_same_eight_connectivity_as_viewer():
    current = np.zeros((32, 32), np.uint8)
    current[10, 10] = current[11, 11] = 1
    current[20, 20] = 1
    result = propose_component_links({}, current)
    assert result["connectivity"] == 8
    assert len(result["new_components"]) == 2


def test_invalid_identifiers_and_nonbinary_masks_are_rejected():
    mask = np.zeros((32, 32), np.uint8)
    mask[1, 1] = 1
    with pytest.raises(ValueError):
        propose_component_links({"a": mask, 5: mask}, mask)
    invalid = mask.copy()
    invalid[2, 2] = 2
    with pytest.raises(ValueError):
        propose_component_links({}, invalid)


def test_even_one_pixel_overlap_is_only_a_proposal():
    old = np.zeros((32, 32), np.uint8)
    old[2:6, 2:6] = 1
    current = np.zeros_like(old)
    current[5:12, 5:12] = 1
    result = propose_component_links({"old": old}, current)
    assert result["requires_clinician_confirmation"] is True
    assert result["unambiguous"][0]["previous_id"] == "old"


def test_empty_current_mask_marks_previous_region_missing():
    old = np.zeros((32, 32), np.uint8)
    old[2:6, 2:6] = 1
    result = propose_component_links({"old": old}, np.zeros_like(old))
    assert result["missing_previous_ids"] == ["old"]
    assert not result["new_components"]
