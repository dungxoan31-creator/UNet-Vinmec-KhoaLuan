"""
Medical-Grade Safety, Uncertainty, Security, Reproducibility, and Audit Trail Test Suite.
Verifies compliance with Clinical Decision Support System (CDSS) standards.
"""

import os
import sys
import unittest
from io import BytesIO

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.db.database import AuditLogModel, SessionLocal


class TestMedicalSafetyAndGovernance(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def _upload_test_image(self, patient_id="PID-SAFETY-01", study_id=None):
        dummy_img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.circle(dummy_img, (256, 256), 180, (70, 70, 70), -1)
        cv2.ellipse(dummy_img, (256, 256), (50, 35), 0, 0, 360, (20, 20, 20), -1)
        _, img_buf = cv2.imencode(".png", dummy_img)
        img_bytes = img_buf.tobytes()

        upload_files = {"file": ("test_ovary_us.png", img_bytes, "image/png")}
        upload_data = {"anonymized_pid": patient_id}
        if study_id:
            upload_data["study_id"] = study_id
        r = self.client.post("/api/upload", data=upload_data, files=upload_files)
        self.assertEqual(r.status_code, 200)
        return r.json()["image_id"]

    def test_01_uncertainty_and_provenance_schema(self):
        """
        Verify that AI model outputs contain rigorous uncertainty quantification
        and cryptographic model provenance metadata.
        """
        image_id = self._upload_test_image("PID-SAFETY-PROV")
        r = self.client.post(f"/api/predict/{image_id}")
        self.assertEqual(r.status_code, 200)
        data = r.json()

        # 1. Provenance check
        self.assertIn("provenance", data)
        prov = data["provenance"]
        self.assertIsNotNone(prov)
        self.assertIn("model_name", prov)
        self.assertIn("model_version", prov)
        self.assertIn("model_checksum", prov)
        self.assertEqual(len(prov["model_checksum"]), 64)  # Valid SHA-256

        # 2. Uncertainty check
        self.assertIn("uncertainty", data)
        uncert = data["uncertainty"]
        self.assertIsNotNone(uncert)
        self.assertIn("entropy_score", uncert)
        self.assertIn("uncertainty_level", uncert)
        self.assertIn("clinical_alert", uncert)
        self.assertIn(uncert["uncertainty_level"], ["LOW", "MODERATE", "HIGH"])

        # 3. Clinical disclaimer check
        self.assertIn("clinical_disclaimer", data)
        print(
            f"[PASS] Provenance & Uncertainty Verified: Model={prov['model_name']} {prov['model_version']}, Entropy={uncert['entropy_score']}"
        )

    def test_02_audit_trail_lifecycle_traceability(self):
        """
        Verify that every critical clinical event (Upload, IQA, Inference, Review)
        is permanently recorded into the immutable AuditLog database table.
        """
        # Create a fresh patient study and test the entire lifecycle
        pid = "PID-AUDIT-LIFECYCLE-99"
        case_r = self.client.post(
            "/api/cases",
            json={
                "patient_id": pid,
                "study_code": "STD-AUDIT-01",
                "study_date": "2026-08-26",
                "patient_age": "29",
                "clinical_notes": "Audit lifecycle test case",
            },
        )
        self.assertEqual(case_r.status_code, 200)
        study_id = case_r.json()["study_id"]

        # 1. Upload
        image_id = self._upload_test_image(pid, study_id)

        # 2. IQA
        iqa_r = self.client.post(f"/api/validate-image?image_id={image_id}")
        self.assertEqual(iqa_r.status_code, 200)

        # 3. Predict
        pred_r = self.client.post(f"/api/predict/{image_id}")
        self.assertEqual(pred_r.status_code, 200)
        rle = pred_r.json()["rle_mask"]

        # 4. Review
        rev_r = self.client.post(
            "/api/review",
            json={
                "image_id": image_id,
                "doctor_id": "BS. Clinical Auditor",
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": rle,
                "lesion_type": "U nang buồng trứng",
                "clinical_notes": "Audit review verified.",
                "time_spent_seconds": 15,
            },
        )
        self.assertEqual(rev_r.status_code, 200)

        # Query DB Audit Logs for this image and review
        logs = (
            self.db.query(AuditLogModel)
            .filter(AuditLogModel.entity_id.in_([image_id, rev_r.json()["review_id"]]))
            .all()
        )
        self.assertGreaterEqual(len(logs), 4)

        actions = [log.action_type for log in logs]
        self.assertIn("UPLOAD_IMAGE", actions)
        self.assertIn("VALIDATE_IQA", actions)
        self.assertIn("RUN_PREDICTION", actions)
        self.assertIn("DOCTOR_ACCEPTED_RAW", actions)
        print(f"[PASS] Complete Audit Trail Verified: Logged actions = {actions}")

    def test_03_deterministic_inference_reproducibility(self):
        """
        Verify that identical inputs produce identical deterministic segmentation
        masks, caliper measurements, and confidence scores across multiple runs.
        """
        image_id = self._upload_test_image("PID-DETERMINISM-01")
        r1 = self.client.post(f"/api/predict/{image_id}").json()
        r2 = self.client.post(f"/api/predict/{image_id}").json()

        # Compare measurements
        m1 = r1["measurements"]
        m2 = r2["measurements"]
        self.assertEqual(m1["max_diameter_mm"], m2["max_diameter_mm"])
        self.assertEqual(m1["ortho_diameter_mm"], m2["ortho_diameter_mm"])
        self.assertEqual(m1["total_area_cm2"], m2["total_area_cm2"])
        self.assertEqual(r1["confidence_score"], r2["confidence_score"])
        self.assertEqual(r1["rle_mask"]["counts"], r2["rle_mask"]["counts"])
        print("[PASS] Deterministic Reproducibility Verified: 100% Bit-exact consistency")

    def test_04_security_path_traversal_prevention(self):
        """
        Verify that malicious filenames with directory traversal patterns
        (e.g., ../../../evil.png) are safely sanitized.
        """
        img = np.full((200, 200), 100, dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        r = self.client.post(
            "/api/upload",
            files={"file": ("../../../../etc/malicious.png", BytesIO(buf.tobytes()), "image/png")},
            data={"anonymized_pid": "PID-SECURITY-01"},
        )
        self.assertEqual(r.status_code, 200)
        filename = r.json()["filename"]
        self.assertEqual(filename, "malicious.png")
        self.assertNotIn("..", filename)
        print("[PASS] Path Traversal Attack Safely Neutralized")


if __name__ == "__main__":
    unittest.main()
