"""Regression tests for audit fixes - BLOCKER issues."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


def test_be_01_forgot_password_does_not_leak_reset_token(monkeypatch):
    """BE-01: Forgot password endpoint must NOT return reset token in public HTTP response."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    with TestClient(app) as client:
        # Request forgot password for existing user 'admin'
        response = client.post("/api/auth/forgot-password", json={"username": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert "Nếu tài khoản tồn tại" in data["message"]
        # CRITICAL SECURITY CHECK: reset_token must NOT be leaked in public response
        assert "reset_token" not in data or data["reset_token"] is None, (
            f"BE-01 VULNERABILITY DETECTED: reset_token was publicly returned in response: {data.get('reset_token')}"
        )
