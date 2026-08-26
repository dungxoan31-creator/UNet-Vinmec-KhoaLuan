"""
Tests for JWT Authentication, RBAC Role Enforcement, and DICOM Calibration Tag Parser.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.inference import extract_dicom_calibration_spacing


class TestAuthAndDicomFeatures(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_jwt_login_doctor_success(self):
        """Verify that DOCTOR can log in and receive a valid JWT bearer token."""
        r = self.client.post("/api/auth/login", json={"username": "bacsi", "password": "any"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["username"], "bacsi")
        self.assertEqual(data["user"]["role"], "DOCTOR")

    def test_02_jwt_login_admin_success(self):
        """Verify that ADMIN can log in and receive a valid JWT bearer token."""
        r = self.client.post("/api/auth/login", json={"username": "admin", "password": "any"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["role"], "ADMIN")

    def test_03_protected_current_user_with_token(self):
        """Verify that `/api/auth/current-user` resolves user from JWT Bearer header."""
        login_r = self.client.post("/api/auth/login", json={"username": "admin"}).json()
        token = login_r["access_token"]

        r = self.client.get("/api/auth/current-user", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["username"], "admin")
        self.assertEqual(r.json()["role"], "ADMIN")

    def test_04_role_switch_issues_new_token(self):
        """Verify that `/api/auth/switch-role` issues a new token matching target role."""
        r = self.client.post("/api/auth/switch-role", json={"role": "ADMIN"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("access_token", r.json())
        self.assertEqual(r.json()["user"]["role"], "ADMIN")

    def test_05_dicom_calibration_fallback_on_non_dicom(self):
        """Verify that non-DICOM raster files safely default to 0.1 mm/px spacing."""
        spacing = extract_dicom_calibration_spacing("dummy_image.png")
        self.assertEqual(spacing, 0.1)


if __name__ == "__main__":
    unittest.main()
