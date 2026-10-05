"""Validate that a review decision matches its submitted segmentation mask."""

import numpy as np
from fastapi import HTTPException


def validate_review_mask(action: str, final_mask: np.ndarray, predicted_mask: np.ndarray) -> None:
    unchanged = np.array_equal(final_mask, predicted_mask)
    if action == "ACCEPTED_RAW" and not unchanged:
        raise HTTPException(status_code=422, detail="ACCEPTED_RAW requires the original prediction mask")
    if action == "MODIFIED" and unchanged:
        raise HTTPException(status_code=422, detail="MODIFIED requires an edited mask")
    if action == "REJECTED_ALL" and np.any(final_mask):
        raise HTTPException(status_code=422, detail="REJECTED_ALL requires an empty mask")
