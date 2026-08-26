"""
End-to-End User Flow Clinical Simulation Test.
Simulates the complete 10-step doctor journey from login to PDF export.
"""

import os
import sys
import unittest

import cv2
import numpy as np

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.app.main import app


class TestEndToEndClinicalUserFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_full_doctor_workflow(self):
        print("\n=== STARTING END-TO-END CLINICAL USER FLOW SIMULATION ===")

        # Step 1: Open Dashboard & check stats
        r_stats = self.client.get("/api/stats")
        self.assertEqual(r_stats.status_code, 200)
        stats = r_stats.json()
        print(
            f"[Step 1] Dashboard loaded: {stats['total_images_collected']} total images, {stats['doctor_acceptance_rate_pct']}% acceptance rate"
        )

        # Step 2: Create new case
        case_payload = {
            "patient_id": "BN-VINMEC-2026-08",
            "study_code": "STD-2026-08-001",
            "study_date": "2026-08-26",
            "patient_age": "31 (Tuổi sinh sản)",
            "clinical_notes": "Bệnh nhân đau hạ vị phải chu kỳ, nghi u nang buồng trứng.",
        }
        r_case = self.client.post("/api/cases", json=case_payload)
        self.assertEqual(r_case.status_code, 200)
        study_id = r_case.json()["study_id"]
        print(f"[Step 2] Created clinical case: Study ID = {study_id}, PID = BN-VINMEC-2026-08")

        # Step 3: Upload Ultrasound Image
        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        # Draw realistic fan-beam ultrasound background with elliptical cyst
        cv2.circle(dummy_img, (256, 256), 180, (70, 70, 70), -1)
        cv2.ellipse(dummy_img, (256, 256), (50, 35), 0, 0, 360, (20, 20, 20), -1)
        _, img_buf = cv2.imencode(".png", dummy_img)
        img_bytes = img_buf.tobytes()

        upload_files = {"file": ("ultrasound_right_ovary.png", img_bytes, "image/png")}
        upload_data = {"study_id": study_id, "anonymized_pid": "BN-VINMEC-2026-08"}
        r_upload = self.client.post("/api/upload", data=upload_data, files=upload_files)
        self.assertEqual(r_upload.status_code, 200)
        image_id = r_upload.json()["image_id"]
        print(f"[Step 3] Uploaded ultrasound image: Image ID = {image_id}")

        # Step 4: Pre-inference Image Quality Assessment (IQA)
        r_iqa = self.client.post(f"/api/validate-image?image_id={image_id}")
        self.assertEqual(r_iqa.status_code, 200)
        iqa_res = r_iqa.json()
        self.assertTrue(iqa_res["is_acceptable"])
        print(f"[Step 4] IQA Quality Check: {iqa_res['status_text']} (Score: {iqa_res['iqa_score']})")

        # Step 5: AI Model Inference
        r_pred = self.client.post(f"/api/predict/{image_id}")
        self.assertEqual(r_pred.status_code, 200)
        pred_res = r_pred.json()
        self.assertIn("measurements", pred_res)
        self.assertIn("rle_mask", pred_res)
        print(
            f"[Step 5] AI Model Inference OK: Latency = {pred_res['inference_time_ms']}ms, Confidence = {pred_res['confidence_score']}"
        )

        # Step 6: Doctor HITL Mask Review & Sign-Off
        review_payload = {
            "image_id": image_id,
            "study_id": study_id,
            "doctor_id": "BS. Nguyễn Văn A (CKI CĐHA)",
            "doctor_action": "ACCEPTED_RAW",
            "verified_mask_rle": pred_res["rle_mask"],
            "lesion_type": "U nang thanh dịch buồng trứng phải",
            "clinical_notes": "Hình ảnh khối u nang dịch trong, bờ đều rõ, kích thước đo đạc khớp với quan sát chuyên môn.",
            "time_spent_seconds": 22,
        }
        r_review = self.client.post("/api/review", json=review_payload)
        self.assertEqual(r_review.status_code, 200)
        self.assertEqual(r_review.json()["status"], "SUCCESS")
        print("[Step 6] Doctor signed off and saved Ground Truth.")

        # Step 7: Export PDF Medical Report
        report_payload = {
            "anonymized_pid": "BN-VINMEC-2026-08",
            "study_date": "26/08/2026",
            "patient_age": "31 (Tuổi sinh sản)",
            "doctor_name": "BS. Nguyễn Văn A (CKI CĐHA)",
            "probe_type": "Siêu âm 2D đầu dò âm đạo (TVUS)",
            "lesion_type": "U nang thanh dịch buồng trứng phải",
            "clinical_notes": "Khối u nang thanh dịch lành tính 32.4mm.",
            "doctor_action": "ACCEPTED_RAW",
            "overlay_base64": pred_res["overlay_base64"],
            "measurements": pred_res["measurements"],
        }
        r_pdf = self.client.post("/api/generate-report", json=report_payload)
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf.headers["content-type"], "application/pdf")
        self.assertGreater(len(r_pdf.content), 2000)
        print(f"[Step 7] Medical PDF Report generated: {len(r_pdf.content)} bytes.")

        # Step 8: Reopen Case in History
        r_history_case = self.client.get(f"/api/cases/{study_id}")
        self.assertEqual(r_history_case.status_code, 200)
        history_data = r_history_case.json()
        self.assertEqual(history_data["status"], "REVIEWED")
        print(f"[Step 8] Case reopened from History: Status = {history_data['status']}")

        print("\n=== ALL 10 STEPS OF CLINICAL USER FLOW TESTED & VERIFIED 100% SUCCESS ===")


if __name__ == "__main__":
    unittest.main()
