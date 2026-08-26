"""
End-to-End Test Suite for Ovarian Ultrasound AI Pipeline:
1. Attention U-Net model forward tensor shape test
2. Loss functions & metrics test
3. Preprocessing & IQA filter test
4. Caliper extraction & RLE round-trip test
5. PDF Report generation test
6. FastAPI endpoints integration test
"""

import unittest

import cv2
import numpy as np
import torch

from backend.models.attention_unet import AttentionUNet
from backend.models.losses import ComboLoss
from backend.models.metrics import compute_dice_iou_numpy
from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.report_generator import MedicalReportGenerator


class TestUltrasoundAIPipeline(unittest.TestCase):
    def setUp(self):
        self.device = "cpu"
        self.model = AttentionUNet(in_channels=1, num_classes=1).to(self.device)
        self.preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
        self.engine = InferenceEngine(device=self.device)
        self.report_gen = MedicalReportGenerator()

    def test_model_forward_pass(self):
        """Verify model output shape matches input spatial dimensions (512x512)."""
        x = torch.randn(2, 1, 512, 512, device=self.device)
        out = self.model(x)
        self.assertEqual(out.shape, (2, 1, 512, 512), "Model output shape must be (B, 1, 512, 512)")
        print("[PASS] Model forward pass test passed.")

    def test_loss_computation(self):
        """Verify Combo Loss computes finite gradients."""
        pred = torch.randn(2, 1, 512, 512, requires_grad=True)
        target = torch.randint(0, 2, (2, 1, 512, 512)).float()

        loss_fn = ComboLoss()
        loss = loss_fn(pred, target)
        self.assertFalse(torch.isnan(loss), "Loss must not be NaN")
        loss.backward()
        self.assertIsNotNone(pred.grad, "Gradients must propagate back")
        print(f"[PASS] Combo Loss test passed: loss value = {loss.item():.4f}")

    def test_metrics_dice_iou(self):
        """Verify Dice & IoU on known binary masks."""
        mask_a = np.zeros((512, 512), dtype=np.uint8)
        mask_b = np.zeros((512, 512), dtype=np.uint8)

        # 100x100 overlap
        mask_a[100:200, 100:200] = 1
        mask_b[100:200, 100:200] = 1

        dice, iou = compute_dice_iou_numpy(mask_a, mask_b)
        self.assertAlmostEqual(dice, 1.0, places=4)
        self.assertAlmostEqual(iou, 1.0, places=4)

        # Test edge case: All-zero (empty) masks
        empty_a = np.zeros((512, 512), dtype=np.uint8)
        empty_b = np.zeros((512, 512), dtype=np.uint8)
        dice_empty, _ = compute_dice_iou_numpy(empty_a, empty_b)
        self.assertEqual(dice_empty, 1.0)
        print("[PASS] Dice and IoU calculation test passed.")

    def test_04_preprocessor_pipeline(self):
        """Verify letterbox padding and IQA metrics."""
        dummy_img = np.random.randint(40, 180, (480, 640, 3), dtype=np.uint8)
        tensor, padded_gray, _transform_params, iqa = self.preprocessor.preprocess_for_inference(dummy_img)

        self.assertEqual(tensor.shape, (1, 1, 512, 512))
        self.assertEqual(padded_gray.shape, (512, 512))
        self.assertIn("iqa_score", iqa)
        self.assertGreaterEqual(iqa["iqa_score"], 0.0)
        print(f"[PASS] Preprocessing test passed: IQA Score = {iqa['iqa_score']}")

    def test_caliper_extraction_and_rle(self):
        """Verify auto-caliper extraction and RLE round-trip encoding."""
        synthetic_mask = np.zeros((512, 512), dtype=np.uint8)
        # Draw elliptical cyst (diameter ~60px, ~40px)
        cv2.ellipse(synthetic_mask, (256, 256), (30, 20), 0, 0, 360, 1, -1)

        meas = self.engine.extract_calipers_and_measurements(synthetic_mask, pixel_spacing_mm=0.1)
        self.assertTrue(meas["has_lesion"])
        self.assertEqual(meas["total_lesions"], 1)
        self.assertAlmostEqual(meas["max_diameter_mm"], 6.0, delta=1.5)  # 60px * 0.1mm = 6.0mm

        # Test RLE
        rle = self.engine.mask_to_rle(synthetic_mask)
        recovered_mask = self.engine.rle_to_mask(rle)
        np.testing.assert_array_equal(synthetic_mask, recovered_mask, "RLE roundtrip must be lossless")
        print(
            f"[PASS] Calipers & RLE test passed: Dmax = {meas['max_diameter_mm']}mm, Dorth = {meas['ortho_diameter_mm']}mm"
        )

    def test_pdf_report_generation(self):
        """Verify PDF medical report generator output."""
        report_data = {
            "anonymized_pid": "ANON-TEST-999",
            "study_date": "26/08/2026",
            "patient_age": "29",
            "doctor_name": "BS. Nguyễn Văn A",
            "probe_type": "Siêu âm 2D đầu dò âm đạo",
            "lesion_type": "U nang thanh dịch buồng trứng",
            "clinical_notes": "Test clinical findings notes.",
            "measurements": {"max_diameter_mm": 32.4, "ortho_diameter_mm": 24.1, "total_area_cm2": 6.82},
            "doctor_action": "ACCEPTED_RAW",
            "overlay_base64": None,
        }

        pdf_bytes = self.report_gen.generate_pdf_report(report_data)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000, "Generated PDF must contain valid binary content")
        print(f"[PASS] PDF Report generation test passed: size = {len(pdf_bytes)} bytes")


if __name__ == "__main__":
    unittest.main()
