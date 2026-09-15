"""
Unit tests for Preprocessing Pipeline: Letterbox, Nearest Mask Interpolation, and Inversion.
"""

import numpy as np
import pytest
from backend.services.preprocessor import UltrasoundPreprocessor

def test_letterbox_shape_and_binary_mask():
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    
    # Non-square arbitrary size image (e.g. 480x640)
    raw_img = (np.random.rand(480, 640) * 255).astype(np.uint8)
    raw_mask = np.zeros((480, 640), dtype=np.uint8)
    raw_mask[100:300, 150:450] = 1 # Lesion region
    
    padded_img, params = preprocessor.letterbox_resize(raw_img, is_mask=False)
    padded_mask, _ = preprocessor.letterbox_resize(raw_mask, is_mask=True)
    
    assert padded_img.shape == (512, 512)
    assert padded_mask.shape == (512, 512)
    
    # Strict binary check for mask (no gray values introduced by interpolation)
    unique_vals = np.unique(padded_mask)
    assert set(unique_vals).issubset({0, 1}), f"Mask must remain strictly binary {0, 1}, got: {unique_vals}"

def test_letterbox_inversion_fidelity():
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    
    orig_h, orig_w = 400, 600
    raw_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
    raw_mask[120:280, 200:400] = 1
    
    padded_mask, params = preprocessor.letterbox_resize(raw_mask, is_mask=True)
    restored_mask = preprocessor.inverse_letterbox_mask(padded_mask, params)
    
    assert restored_mask.shape == (orig_h, orig_w)
    # Check Dice between raw_mask and restored_mask
    intersection = (raw_mask * restored_mask).sum()
    dice = (2.0 * intersection) / (raw_mask.sum() + restored_mask.sum())
    assert dice > 0.98, f"Inversion fidelity too low: {dice:.4f}"
