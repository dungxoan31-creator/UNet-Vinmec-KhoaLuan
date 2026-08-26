"""
Standalone CLI evaluation tool:
Runs inference on any custom ultrasound image and outputs caliper measurements,
IQA scores, and saves the overlay image.

Usage:
    python scripts/evaluate_custom_image.py <image_path> [--output <output_path>]
"""

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor


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


def evaluate_image(image_path, output_path=None, weights_path=None):
    if not os.path.exists(image_path):
        print(f"[Error] Image not found at {image_path}")
        return

    if weights_path is None:
        weights_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "checkpoints", "best_attention_unet.pth")
        )

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    engine = InferenceEngine(
        model_weights_path=weights_path if os.path.exists(weights_path) else None, default_pixel_spacing_mm=0.1
    )

    img_np = cv2_imread_unicode(image_path)
    tensor, padded_gray, _transform_params, iqa = preprocessor.preprocess_for_inference(img_np)
    res = engine.run_inference(tensor, padded_gray, pixel_spacing_mm=0.1)

    meas = res["measurements"]
    print("\n" + "=" * 55)
    print("      OVARIAN ULTRASOUND AI EVALUATION REPORT      ")
    print("=" * 55)
    print(f"• Input Image:        {os.path.basename(image_path)}")
    print(f"• Image Quality (IQA): {iqa['iqa_score']:.2f} ({'PASSED' if iqa['is_acceptable'] else 'WARNING'})")
    print(f"• AI Confidence:      {res['confidence_score'] * 100:.1f}%")
    print(f"• Lesions Detected:   {meas['total_lesions']}")
    print(f"• Max Diameter (D1):  {meas['max_diameter_mm']:.1f} mm")
    print(f"• Ortho Diameter (D2):{meas['ortho_diameter_mm']:.1f} mm")
    print(f"• Total Area:         {meas['total_area_cm2']:.3f} cm2")
    print("=" * 55)

    if output_path is None:
        output_path = os.path.splitext(image_path)[0] + "_ai_overlay.png"

    # Save visual overlay
    overlay_b64 = res["overlay_base64"]
    if overlay_b64.startswith("data:image"):
        import base64

        data = base64.b64decode(overlay_b64.split(",")[1])
        with open(output_path, "wb") as f:
            f.write(data)
        print(f"[Success] Saved visual overlay with calipers to {output_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ultrasound image with AI")
    parser.add_argument("image_path", help="Path to ultrasound image (.png, .jpg)")
    parser.add_argument("--output", default=None, help="Path to save overlay image")
    parser.add_argument("--weights", default=None, help="Path to custom model weights")
    args = parser.parse_args()

    evaluate_image(args.image_path, args.output, args.weights)
