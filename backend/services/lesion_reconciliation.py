"""Generate conservative component-link proposals, never clinical identities.

Indices are temporary for one mask. All links, including one-to-one links,
require an explicit clinician decision before an identity can be persisted.
This module does not associate components across images or studies.
"""

import hashlib

import cv2
import numpy as np

MAX_TRACKS = 128
MAX_PIXELS = 512 * 512


def _binary_mask(value, shape=None):
    if not isinstance(value, np.ndarray) or value.ndim != 2 or value.size == 0 or value.size > MAX_PIXELS:
        raise ValueError("Mask must be a nonempty bounded two-dimensional array")
    if shape is not None and value.shape != shape:
        raise ValueError("All masks must share the same coordinate space")
    if value.dtype.kind not in "biuf" or not np.isfinite(value).all() or not np.isin(value, [0, 1]).all():
        raise ValueError("Mask must contain only finite binary values")
    return value.astype(np.uint8, copy=False)


def review_component_candidates(mask: np.ndarray) -> dict:
    """Expose ephemeral 8-connected candidates in the reviewed 512 mask."""
    current = _binary_mask(mask, (512, 512))
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(current, connectivity=8)
    if count - 1 > MAX_TRACKS:
        raise ValueError("Too many components for safe review")
    unique_labels, first_indices = np.unique(labels, return_index=True)
    seeds = dict(zip(unique_labels.tolist(), first_indices.tolist(), strict=True))
    components = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        seed = int(seeds[index])
        components.append({
            "component_index": index,
            "pixel_count": area,
            "bounding_box_xywh": [x, y, width, height],
            "seed_xy": [seed % 512, seed // 512],
        })
    return {
        "coordinate_space": "letterbox-512",
        "connectivity": 8,
        "algorithm": "opencv-connected-components-8-v1",
        "mask_sha256": hashlib.sha256(current.tobytes()).hexdigest(),
        "requires_clinician_confirmation": True,
        "components": components,
    }


def propose_component_links(previous_masks: dict[str, np.ndarray], current_mask: np.ndarray) -> dict:
    """Compare one image's previous regions with its current 8-connected mask.

    A one-to-one overlap is only a graph property, not proof of clinical identity.
    Split and merge edges are ambiguous even when one overlap is much larger.
    No IDs are generated, assigned, or persisted by this function.
    """
    current = _binary_mask(current_mask)
    if not isinstance(previous_masks, dict) or len(previous_masks) > MAX_TRACKS:
        raise ValueError("Previous region collection is invalid or too large")
    if any(not isinstance(key, str) or not key or len(key) > 128 for key in previous_masks):
        raise ValueError("Previous region IDs must be bounded nonempty strings")
    old_ids = sorted(previous_masks)

    old_labels = np.zeros(current.shape, dtype=np.int32)
    for index, old_id in enumerate(old_ids, 1):
        region = _binary_mask(previous_masks[old_id], current.shape).astype(bool, copy=False)
        if not region.any() or np.any(old_labels[region]):
            raise ValueError("Previous regions must be nonempty and disjoint")
        old_labels[region] = index

    component_count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(current, connectivity=8)
    if component_count - 1 > MAX_TRACKS:
        raise ValueError("Too many current components for safe reconciliation")
    overlapping = (old_labels > 0) & (labels > 0)
    pairs = np.unique(np.column_stack((old_labels[overlapping], labels[overlapping])), axis=0)
    old_to_components = {index: set() for index in range(1, len(old_ids) + 1)}
    component_to_old = {index: set() for index in range(1, component_count)}
    for old_index, component_index in pairs:
        old_to_components[int(old_index)].add(int(component_index))
        component_to_old[int(component_index)].add(int(old_index))

    unambiguous, ambiguous, new_components = [], [], []
    for component_index, old_indices in component_to_old.items():
        if not old_indices:
            new_components.append(component_index)
        elif len(old_indices) == 1 and len(old_to_components[next(iter(old_indices))]) == 1:
            old_index = next(iter(old_indices))
            unambiguous.append({"component_index": component_index, "previous_id": old_ids[old_index - 1]})
        else:
            ambiguous.append({"component_index": component_index,
                              "previous_ids": sorted(old_ids[index - 1] for index in old_indices)})
    return {
        "connectivity": 8,
        "requires_clinician_confirmation": True,
        "unambiguous": unambiguous,
        "ambiguous": ambiguous,
        "new_components": new_components,
        "missing_previous_ids": [old_ids[index - 1] for index, links in old_to_components.items() if not links],
    }
