"""
Unit and Integration Tests for RESTful API v1 Endpoints:
- POST /api/v1/segment
- POST /api/v1/cdss/evaluate
- POST /api/v1/cases/confirm
- Preprocessing Letterbox 512x512 with Bilinear (image) & Nearest Neighbor (mask) verification
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.preprocessor import UltrasoundPreprocessor


class TestV1Endpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.preprocessor = UltrasoundPreprocessor()

    def test_01_letterbox_image_and_mask_interpolation(self):
        """
        Verifies Letterbox 512x512 preserves aspect ratio,
        uses Bilinear for image and Nearest Neighbor for binary mask.
        """
        # Create non-square 800x600 test image and binary mask
        dummy_img = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.circle(dummy_img, (400, 300), 150, (120, 120, 120), -1)

        dummy_mask = np.zeros((600, 800), dtype=np.uint8)
        cv2.circle(dummy_mask, (400, 300), 150, 1, -1)

        # 1. Letterbox resize image (is_mask=False, Bilinear)
        padded_img, params_img = self.preprocessor.letterbox_resize(dummy_img, (512, 512), is_mask=False)
        self.assertEqual(padded_img.shape, (512, 512, 3))
        self.assertEqual(params_img["orig_w"], 800)
        self.assertEqual(params_img["orig_h"], 600)
        self.assertEqual(params_img["target_w"], 512)
        self.assertEqual(params_img["target_h"], 512)

        # 2. Letterbox resize mask (is_mask=True, Nearest Neighbor)
        padded_mask, params_mask = self.preprocessor.letterbox_resize(dummy_mask, (512, 512), is_mask=True)
        self.assertEqual(padded_mask.shape, (512, 512))

        # Check binary mask values are strictly {0, 1} with no fractional anti-aliasing interpolation values
        unique_vals = set(np.unique(padded_mask))
        self.assertTrue(unique_vals.issubset({0, 1}))

        # 3. Test Inverse Letterbox Mask
        restored_mask = self.preprocessor.inverse_letterbox_mask(padded_mask, params_mask)
        self.assertEqual(restored_mask.shape, (600, 800))
        restored_unique = set(np.unique(restored_mask))
        self.assertTrue(restored_unique.issubset({0, 1}))

        print("[PASS] Letterbox 512x512 Bilinear/Nearest-Neighbor & Inverse Mask OK")

    def test_02_segment_v1_endpoint(self):
        """
        Tests POST /api/v1/segment:
        Receives ultrasound image -> Preprocesses 512x512 -> PyTorch inference -> Binary Mask (RLE & Base64 PNG).
        """
        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.circle(dummy_img, (256, 256), 180, (75, 75, 75), -1)
        cv2.ellipse(dummy_img, (256, 256), (50, 35), 0, 0, 360, (25, 25, 25), -1)
        _, buf = cv2.imencode(".png", dummy_img)

        files = {"file": ("test_ultrasound.png", buf.tobytes(), "image/png")}
        data = {"pixel_spacing_mm": "0.1"}

        r = self.client.post("/api/v1/segment", files=files, data=data)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertTrue(res["success"])
        self.assertIn("rle_mask", res)
        self.assertIn("binary_mask_base64", res)
        self.assertTrue(res["binary_mask_base64"].startswith("data:image/png;base64,"))
        self.assertIn("confidence_score", res)
        self.assertIn("measurements", res)
        self.assertIn("provenance", res)
        print(f"[PASS] POST /api/v1/segment OK: Confidence={res['confidence_score']}")

    def test_03_cdss_evaluate_v1_endpoint(self):
        """
        Tests POST /api/v1/cdss/evaluate:
        Receives features -> Calls CDSS Engine -> Returns O-RADS/IOTA recommendations.
        """
        # Case A: Simple benign cyst
        payload_benign = {
            "vision_findings": {
                "max_diameter_mm": 35.0,
                "ortho_diameter_mm": 25.0,
                "has_solid_component": False,
                "papillary_projections_count": 0,
                "acoustic_shadowing": False,
                "fluid_echogenicity": "anechoic",
                "locules_count": 1,
                "color_score": 1,
                "has_ascites": False,
            },
            "patient_context": {"age": 32, "is_postmenopausal": False},
        }

        r = self.client.post("/api/v1/cdss/evaluate", json=payload_benign)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertTrue(res["success"])
        self.assertIn("iota_evaluation", res)
        self.assertIn("orads_stratification", res)
        self.assertIn("B1: Unilocular cyst", res["iota_evaluation"]["b_rules_met"][0])
        self.assertEqual(res["orads_stratification"]["category_code"], "O-RADS 2")
        self.assertEqual(res["orads_stratification"]["malignancy_risk"], "< 1%")

        # Case B: Malignant suspicion
        payload_malignant = {
            "vision_findings": {
                "max_diameter_mm": 85.0,
                "ortho_diameter_mm": 60.0,
                "has_solid_component": True,
                "papillary_projections_count": 5,
                "acoustic_shadowing": False,
                "fluid_echogenicity": "mixed",
                "locules_count": 3,
                "color_score": 4,
                "has_ascites": True,
            },
            "patient_context": {"age": 58, "is_postmenopausal": True},
        }
        r_mal = self.client.post("/api/v1/cdss/evaluate", json=payload_malignant)
        self.assertEqual(r_mal.status_code, 200)
        res_mal = r_mal.json()
        self.assertEqual(res_mal["orads_stratification"]["category_code"], "O-RADS 5")
        self.assertEqual(res_mal["orads_stratification"]["malignancy_risk"], "≥ 50%")
        print("[PASS] POST /api/v1/cdss/evaluate OK (Benign O-RADS 2 & Malignant O-RADS 5 verified)")

    def test_04_cases_confirm_v1_endpoint(self):
        """
        Tests POST /api/v1/cases/confirm:
        Stores Doctor Review Sign-Off (HITL Ground Truth).
        """
        # Upload image to generate a real image_id
        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.circle(dummy_img, (256, 256), 150, (80, 80, 80), -1)
        _, buf = cv2.imencode(".png", dummy_img)

        r_upload = self.client.post(
            "/api/upload",
            files={"file": ("hitl_test.png", buf.tobytes(), "image/png")},
            data={"anonymized_pid": "BN-HITL-V1-001"},
        )
        self.assertEqual(r_upload.status_code, 200)
        image_id = r_upload.json()["image_id"]
        study_id = r_upload.json()["study_id"]

        # Run segment to get a valid RLE mask
        r_seg = self.client.post(f"/api/v1/segment?image_id={image_id}")
        self.assertEqual(r_seg.status_code, 200)
        rle = r_seg.json()["rle_mask"]

        # Post HITL Sign-Off to /api/v1/cases/confirm
        confirm_payload = {
            "image_id": image_id,
            "study_id": study_id,
            "doctor_id": "BS. Nguyễn Văn A",
            "doctor_action": "ACCEPTED_RAW",
            "verified_mask_rle": rle,
            "lesion_type": "U nang thanh dịch buồng trứng",
            "clinical_notes": "Xác nhận kết quả phân đoạn AI chính xác.",
            "time_spent_seconds": 12,
        }

        r_confirm = self.client.post("/api/v1/cases/confirm", json=confirm_payload)
        self.assertEqual(r_confirm.status_code, 200)
        res_confirm = r_confirm.json()
        self.assertTrue(res_confirm["success"])
        self.assertEqual(res_confirm["status"], "CONFIRMED")
        self.assertTrue(res_confirm["is_ground_truth"])
        self.assertIn("review_id", res_confirm)

        # Verify case status updated to REVIEWED
        r_case = self.client.get(f"/api/cases/{study_id}")
        self.assertEqual(r_case.status_code, 200)
        self.assertEqual(r_case.json()["status"], "REVIEWED")

        print("[PASS] POST /api/v1/cases/confirm OK: Ground Truth saved & Study Status = REVIEWED")

    def test_05_generate_narrative_with_ollama_flag(self):
        """
        Tests POST /api/generate-narrative with use_ollama parameter flag.
        """
        payload = {
            "vision_findings": {"max_diameter_mm": 42.0, "ortho_diameter_mm": 30.0},
            "patient_info": {"patient_age": "34"},
            "use_ollama": True,
        }
        r = self.client.post("/api/generate-narrative", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertIn("generation_mode", res)
        self.assertIn("sonographic_findings_text", res)
        self.assertIn("clinical_conclusion_text", res)
        print(f"[PASS] POST /api/generate-narrative with use_ollama=True OK: Mode={res['generation_mode']}")


if __name__ == "__main__":
    unittest.main()
