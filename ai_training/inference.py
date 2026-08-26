"""
Standalone Production Inference Script for Ovarian Lesion Segmentation.
Directly loads production checkpoint and outputs:
- Segmentation Mask (Binary PNG)
- High-fidelity Overlay with Calipers (Dmax, Dorth)
- JSON Metadata Report

Usage:
    python ai_training/inference.py --image "path/to/image.jpg" --output "result.png"
"""

import os
import sys
import json
import argparse
import numpy as np
import cv2
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models.attention_unet import AttentionUNet
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.inference_engine import InferenceEngine

def cv2_imread_unicode(file_path, flags=cv2.IMREAD_COLOR):
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)

def cv2_imwrite_unicode(file_path, img_np):
    ext = os.path.splitext(file_path)[1]
    ret, buf = cv2.imencode(ext, img_np)
    if ret:
        with open(file_path, "wb") as f:
            f.write(buf)

def run_standalone_inference(image_path, output_path=None, weights_path=None):
    if not os.path.exists(image_path):
        print(f"[Error] Image not found: {image_path}")
        return False

    if weights_path is None:
        # Check production path first, then checkpoints
        prod_weights = os.path.abspath(os.path.join(os.path.dirname(__file__), "production_model", "model.pth"))
        chk_weights = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints", "best_attention_unet.pth"))
        weights_path = prod_weights if os.path.exists(prod_weights) else chk_weights

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Inference] Loading production Attention U-Net on {device}...")

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    engine = InferenceEngine(model_weights_path=weights_path, device=device, default_pixel_spacing_mm=0.1)

    # 1. Preprocess
    img_np = cv2_imread_unicode(image_path, cv2.IMREAD_COLOR)
    tensor, padded_gray, transform_params, iqa = preprocessor.preprocess_for_inference(img_np)

    # 2. Run Inference
    result = engine.run_inference(tensor, padded_gray, pixel_spacing_mm=0.1)
    meas = result["measurements"]

    # 3. Outputs
    if output_path is None:
        output_path = os.path.splitext(image_path)[0] + "_ai_result.png"

    # Save overlay image
    overlay_b64 = result["overlay_base64"]
    if overlay_b64.startswith("data:image"):
        import base64
        data = base64.b64decode(overlay_b64.split(",")[1])
        with open(output_path, "wb") as f:
            f.write(data)

    # Save isolated mask
    mask_out_path = os.path.splitext(output_path)[0] + "_mask.png"
    cv2_imwrite_unicode(mask_out_path, result["binary_mask_np"] * 255)

    # Print summary
    print("\n" + "="*60)
    print("      OVARIAN LESION AI SEGMENTATION RESULT       ")
    print("="*60)
    print(f"  Input Image:              {os.path.basename(image_path)}")
    print(f"  Image Dimensions:         {img_np.shape[1]}x{img_np.shape[0]} px")
    print(f"  IQA Quality Score:        {iqa['iqa_score']:.2f} ({'PASSED' if iqa['is_acceptable'] else 'WARNING'})")
    print(f"  AI Confidence:            {result['confidence_score']*100:.1f}%")
    print(f"  Detected Lesions:         {meas['total_lesions']}")
    print(f"  Max Diameter (D1):        {meas['max_diameter_mm']:.1f} mm")
    print(f"  Orthogonal Diameter (D2): {meas['ortho_diameter_mm']:.1f} mm")
    print(f"  Depth (D3):               {meas.get('d3_mm', 0.0):.1f} mm")
    print(f"  Calculated Volume (V):    {meas.get('total_volume_cm3', 0.0):.2f} mL")
    print(f"  Cross-Sectional Area:     {meas['total_area_cm2']:.3f} cm2")
    print(f"  Saved Overlay Image:      {os.path.basename(output_path)}")
    print(f"  Saved Mask Image:         {os.path.basename(mask_out_path)}")
    print("="*60 + "\n")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone AI Ovarian Ultrasound Inference")
    parser.add_argument("--image", required=True, help="Path to input ultrasound image")
    parser.add_argument("--output", default=None, help="Path to save output overlay image")
    parser.add_argument("--weights", default=None, help="Path to custom model weights")
    args = parser.parse_args()

    run_standalone_inference(args.image, args.output, args.weights)
