"""
Comprehensive Test Suite for FastAPI Endpoints, Case Management, IQA, Model Registry, and PDF Report.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.app.main import app


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_health_check(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "healthy")
        print("[PASS] Health Check Endpoint OK")

    def _upload_test_image(self, patient_id="BN-TEST-8899"):
        import cv2
        import numpy as np

        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.circle(dummy_img, (256, 256), 180, (70, 70, 70), -1)
        cv2.ellipse(dummy_img, (256, 256), (50, 35), 0, 0, 360, (20, 20, 20), -1)
        _, img_buf = cv2.imencode(".png", dummy_img)
        img_bytes = img_buf.tobytes()

        upload_files = {"file": ("test_ovary_us.png", img_bytes, "image/png")}
        upload_data = {"anonymized_pid": patient_id}
        r = self.client.post("/api/upload", data=upload_data, files=upload_files)
        self.assertEqual(r.status_code, 200)
        return r.json()["image_id"]

    def test_03_create_case_and_list(self):
        # Create case
        payload = {
            "patient_id": "BN-TEST-8899",
            "study_code": "STD-TEST-001",
            "study_date": "2026-08-26",
            "patient_age": "34 (Tuổi sinh sản)",
            "clinical_notes": "Siêu âm tầm soát u buồng trứng",
        }
        r_create = self.client.post("/api/cases", json=payload)
        self.assertEqual(r_create.status_code, 200)
        case_data = r_create.json()
        self.assertEqual(case_data["patient_id"], "BN-TEST-8899")
        study_id = case_data["study_id"]
        print(f"[PASS] Case Created OK: study_id = {study_id}")

        # List cases
        r_list = self.client.get("/api/cases")
        self.assertEqual(r_list.status_code, 200)
        cases = r_list.json()
        self.assertGreaterEqual(len(cases), 1)
        print(f"[PASS] Cases List OK: {len(cases)} cases retrieved")

        # Get case detail
        r_detail = self.client.get(f"/api/cases/{study_id}")
        self.assertEqual(r_detail.status_code, 200)
        self.assertEqual(r_detail.json()["study_id"], study_id)
        print("[PASS] Case Detail OK")

    def test_04_validate_image_quality(self):
        image_id = self._upload_test_image()
        r = self.client.post(f"/api/validate-image?image_id={image_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["is_acceptable"])
        self.assertEqual(len(data["details"]), 4)
        print(f"[PASS] Pre-inference IQA Check OK: Score = {data['iqa_score']}")

    def test_05_model_prediction_pipeline(self):
        image_id = self._upload_test_image()
        r = self.client.post(f"/api/predict/{image_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("rle_mask", data)
        self.assertIn("measurements", data)
        self.assertIn("overlay_base64", data)
        print(f"[PASS] Prediction on image OK: Dmax={data['measurements']['max_diameter_mm']}mm")

    def test_06_doctor_review_and_ground_truth(self):
        image_id = self._upload_test_image()
        r_pred = self.client.post(f"/api/predict/{image_id}")
        rle = r_pred.json()["rle_mask"]

        review_payload = {
            "image_id": image_id,
            "doctor_id": "BS. Nguyễn Văn A",
            "doctor_action": "ACCEPTED_RAW",
            "verified_mask_rle": rle,
            "lesion_type": "U nang thanh dịch buồng trứng",
            "clinical_notes": "U nang thanh dịch đơn thuần 32.4mm, viền mỏng đều.",
            "time_spent_seconds": 18,
        }
        r = self.client.post("/api/review", json=review_payload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "SUCCESS")
        print("[PASS] Doctor Review & Ground Truth Submission OK")

    def test_07_pdf_report_generation(self):
        report_payload = {
            "anonymized_pid": "BN-TEST-8899",
            "study_date": "26/08/2026",
            "patient_age": "34 (Tuổi sinh sản)",
            "doctor_name": "BS. Nguyễn Văn A",
            "probe_type": "Siêu âm 2D đầu dò âm đạo",
            "lesion_type": "U nang thanh dịch buồng trứng",
            "clinical_notes": "Khối u nang thanh dịch lành tính 32.4mm.",
            "measurements": {"max_diameter_mm": 32.4, "ortho_diameter_mm": 24.1, "total_area_cm2": 6.82},
            "doctor_action": "ACCEPTED_RAW",
            "overlay_base64": None,
        }
        r = self.client.post("/api/generate-report", json=report_payload)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "application/pdf")
        self.assertGreater(len(r.content), 1000)
        print(f"[PASS] PDF Report Generation OK: {len(r.content)} bytes")

    def test_08_admin_models_and_stats(self):
        r_admin = self.client.get("/api/admin/models")
        self.assertEqual(r_admin.status_code, 200)
        data = r_admin.json()
        self.assertEqual(data["active_primary_model"], "attention_unet")
        self.assertEqual(len(data["registered_models"]), 5)
        print(f"[PASS] Admin Model Registry Overview OK: {len(data['registered_models'])} models registered")

        r_stats = self.client.get("/api/stats")
        self.assertEqual(r_stats.status_code, 200)
        print("[PASS] Operational Dashboard Stats OK")

    def test_08b_clinical_nlp_narrative_generation(self):
        payload = {
            "vision_findings": {
                "max_diameter_mm": 35.4,
                "ortho_diameter_mm": 26.2,
                "d3_mm": 30.8,
                "volume_ml": 14.9,
                "has_solid_component": False,
                "papillary_projections_count": 0,
                "acoustic_shadowing": False,
                "fluid_echogenicity": "anechoic",
                "locules_count": 1,
                "color_score": 1,
                "has_ascites": False,
            },
            "patient_info": {
                "patient_id": "BN-TEST-9988",
                "patient_age": "32 (Tuổi sinh sản)",
                "study_code": "STD-TEST-99",
            },
            "pathology_name": "U nang thanh dịch buồng trứng (Simple Serous Cyst)",
        }
        r = self.client.post("/api/generate-narrative", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("sonographic_findings_text", data)
        self.assertIn("clinical_conclusion_text", data)
        self.assertIn("O-RADS 2", data["clinical_conclusion_text"])
        self.assertIn("IOTA", data["clinical_conclusion_text"])
        print("[PASS] Clinical NLP Narrative & Diagnostic Conclusion Generation OK")

    def test_09_unsuitable_image_detection_and_rejection(self):
        from io import BytesIO

        import cv2
        import numpy as np

        # Case A: Solid black/blank image
        black_img = np.zeros((256, 256), dtype=np.uint8)
        _, buf = cv2.imencode(".png", black_img)
        r_upload_blank = self.client.post(
            "/api/upload",
            files={"file": ("blank_test.png", BytesIO(buf.tobytes()), "image/png")},
            data={"anonymized_pid": "TEST-UNSUITABLE-01"},
        )
        self.assertEqual(r_upload_blank.status_code, 200)
        img_id_blank = r_upload_blank.json()["image_id"]

        r_val_blank = self.client.post(f"/api/validate-image?image_id={img_id_blank}")
        self.assertEqual(r_val_blank.status_code, 200)
        self.assertFalse(r_val_blank.json()["is_acceptable"])
        print("[PASS] Rejected Blank/All-Black Image in IQA check")

        # Check prediction rejection with 422
        r_pred_blank = self.client.post(f"/api/predict/{img_id_blank}")
        self.assertEqual(r_pred_blank.status_code, 422)
        print("[PASS] HTTP 422 Unprocessable Entity successfully returned on blank image")

        # Case B: Colorful non-ultrasound natural photo (e.g. RGB red/green landscape)
        color_img = np.zeros((300, 300, 3), dtype=np.uint8)
        color_img[:, :, 2] = 220  # High red saturation
        color_img[:, :, 1] = 80
        _, buf_col = cv2.imencode(".jpg", color_img)
        r_upload_col = self.client.post(
            "/api/upload",
            files={"file": ("natural_photo.jpg", BytesIO(buf_col.tobytes()), "image/jpeg")},
            data={"anonymized_pid": "TEST-UNSUITABLE-02"},
        )
        self.assertEqual(r_upload_col.status_code, 200)
        img_id_col = r_upload_col.json()["image_id"]

        r_val_col = self.client.post(f"/api/validate-image?image_id={img_id_col}")
        self.assertEqual(r_val_col.status_code, 200)
        self.assertFalse(r_val_col.json()["is_acceptable"])
        print("[PASS] Rejected Non-Medical Color Photo in IQA check")

        # Check prediction rejection with 422
        r_pred_col = self.client.post(f"/api/predict/{img_id_col}")
        self.assertEqual(r_pred_col.status_code, 422)
        print("[PASS] HTTP 422 successfully returned on color photo")

        # Case C: Tiny corrupted resolution (40x40 px)
        tiny_img = np.full((40, 40), 100, dtype=np.uint8)
        _, buf_tiny = cv2.imencode(".png", tiny_img)
        r_upload_tiny = self.client.post(
            "/api/upload",
            files={"file": ("tiny.png", BytesIO(buf_tiny.tobytes()), "image/png")},
            data={"anonymized_pid": "TEST-UNSUITABLE-03"},
        )
        self.assertEqual(r_upload_tiny.status_code, 200)
        img_id_tiny = r_upload_tiny.json()["image_id"]

        r_val_tiny = self.client.post(f"/api/validate-image?image_id={img_id_tiny}")
        self.assertEqual(r_val_tiny.status_code, 200)
        self.assertFalse(r_val_tiny.json()["is_acceptable"])
        print("[PASS] Rejected Tiny Low-Resolution Image in IQA check")

        r_pred_tiny = self.client.post(f"/api/predict/{img_id_tiny}")
        self.assertEqual(r_pred_tiny.status_code, 422)
        print("[PASS] HTTP 422 successfully returned on tiny image")

    def test_10_case_delete_and_file_cleanup(self):
        # Create and upload case
        payload = {
            "patient_id": "BN-DELETE-TEST",
            "study_code": "STD-DEL-001",
            "study_date": "2026-08-29",
            "patient_age": "29",
            "clinical_notes": "Test deletion and cleanup",
        }
        r_create = self.client.post("/api/cases", json=payload)
        self.assertEqual(r_create.status_code, 200)
        study_id = r_create.json()["study_id"]

        _ = self._upload_test_image(patient_id="BN-DELETE-TEST")

        # Delete case
        r_del = self.client.delete(f"/api/cases/{study_id}")
        self.assertEqual(r_del.status_code, 200)
        self.assertEqual(r_del.json()["status"], "SUCCESS")

        # Verify 404 on re-fetching
        r_get = self.client.get(f"/api/cases/{study_id}")
        self.assertEqual(r_get.status_code, 404)
        print("[PASS] Case Deletion and Verification OK")

    def test_11_error_handling_and_edge_cases(self):
        # Non-existent case
        r_not_found = self.client.get("/api/cases/non-existent-uuid-12345")
        self.assertEqual(r_not_found.status_code, 404)

        # Non-existent image predict
        r_pred_none = self.client.post("/api/predict/non-existent-img-uuid")
        self.assertEqual(r_pred_none.status_code, 404)

        # Empty body upload
        r_empty_up = self.client.post("/api/upload", files={"file": ("empty.png", b"", "image/png")})
        self.assertEqual(r_empty_up.status_code, 400)
        print("[PASS] Negative and Edge-Case API Error Handlers OK")

    def test_12_morphology_and_caliper_boundary_tests(self):
        import cv2
        import numpy as np

        from backend.app.config import model_registry
        from backend.services.morphology_extractor import MorphologicalFeatureExtractor

        # Test 3-channel RGB image in morphology extractor
        extractor = MorphologicalFeatureExtractor()
        rgb_img = np.full((512, 512, 3), 120, dtype=np.uint8)
        mask = np.zeros((512, 512), dtype=np.uint8)
        cv2.circle(mask, (256, 256), 60, 1, -1)

        features = extractor.extract_features(rgb_img, mask, pixel_spacing_mm=0.1)
        self.assertTrue(features["has_lesion"])
        self.assertGreater(features["measurements"]["max_diameter_mm"], 0)

        # Test zero and negative pixel spacing in caliper extraction
        engine = model_registry.get_primary_adapter().engine
        meas_zero = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=0.0)
        self.assertGreater(meas_zero["max_diameter_mm"], 0)
        print("[PASS] Morphology and Caliper Boundary & Spacing Tests OK")


if __name__ == "__main__":
    unittest.main()
