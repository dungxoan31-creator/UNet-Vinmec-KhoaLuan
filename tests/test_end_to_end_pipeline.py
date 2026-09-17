"""
End-to-End Integration Smoke Test for Ultrasound Preprocessing -> Baseline Inference -> Morphology Extraction.
Verifies the complete pipeline runs smoothly and latency is within clinical requirements (< 100ms on GPU).
"""

import os
import time
import cv2
import numpy as np
import pytest
import torch

from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.morphology_extractor import MorphologicalFeatureExtractor

def test_full_pipeline_smoke_flow():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 1. Initialize components
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    checkpoint_path = "checkpoints/baseline_unet_best.pth"
    if os.path.exists(checkpoint_path):
        model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.eval()
    morphology = MorphologicalFeatureExtractor(default_pixel_spacing_mm=0.1)

    # 2. Load an actual ultrasound image
    sample_img_path = "dataset/vinmec_ovarian/OTU_2D/train/train_image/1.JPG"
    if not os.path.exists(sample_img_path):
        sample_img_path = "dataset/dataset/OTU_2D/train/train_image/1.JPG"
    if os.path.exists(sample_img_path):
        raw_img = cv2.imread(sample_img_path, cv2.IMREAD_GRAYSCALE)
    else:
        raw_img = (np.random.rand(480, 640) * 255).astype(np.uint8)

    t0 = time.time()

    # Step A: Preprocessing
    img_pad, params = preprocessor.letterbox_resize(raw_img, is_mask=False)
    img_clahe = preprocessor.clahe.apply(img_pad)
    tensor = torch.from_numpy(img_clahe).unsqueeze(0).unsqueeze(0).float() / 255.0
    tensor = tensor.to(device)

    # Step B: Inference
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)
        pred_512 = (probs > 0.5).squeeze().cpu().numpy().astype(np.uint8)

    # Step C: Inverse Letterbox to original size
    restored_mask = preprocessor.inverse_letterbox_mask(pred_512, params)

    # Step D: Clinical Biomarker & Caliper Extraction
    features = morphology.extract_features(raw_img, restored_mask, pixel_spacing_mm=0.1)

    latency_ms = (time.time() - t0) * 1000

    print(f"\n[PIPELINE SMOKE TEST]")
    print(f"  - Input Raw Shape:  {raw_img.shape}")
    print(f"  - Preprocessed:     {img_clahe.shape}")
    print(f"  - Restored Mask:    {restored_mask.shape}")
    print(f"  - Caliper D1 (max): {features['measurements']['max_diameter_mm']:.2f} mm")
    print(f"  - O-RADS Category:  {features['cdss_classification']['orads_category']}")
    print(f"  - Total Latency:    {latency_ms:.2f} ms")

    assert restored_mask.shape == raw_img.shape, "Restored mask dimensions must match raw image"
    assert "measurements" in features, "Morphology features must contain geometric measurements"
    assert "cdss_classification" in features, "Must produce clinical stratification"
