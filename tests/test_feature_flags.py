"""
Tests for System Feature Flags (v2.0 Architecture).
Verifies parsing of APP_FEATURES and reflection in /api/capabilities.
"""


from fastapi.testclient import TestClient

from backend.app.config import is_feature_enabled
from backend.app.main import app


def test_is_feature_enabled_default():
    # Defaults in config: autofill, fast_review, cdss_background, uncertainty_overlay
    assert is_feature_enabled("autofill") is True
    assert is_feature_enabled("fast_review") is True
    assert is_feature_enabled("cdss_background") is True
    assert is_feature_enabled("uncertainty_overlay") is True
    assert is_feature_enabled("non_existent_feature") is False


def test_capabilities_endpoint_includes_feature_flags():
    client = TestClient(app)
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    data = response.json()

    assert "feature_autofill" in data
    assert "feature_fast_review" in data
    assert "feature_cdss_background" in data
    assert "feature_uncertainty_overlay" in data
    assert "enabled_features" in data
    assert isinstance(data["enabled_features"], list)
    assert "autofill" in data["enabled_features"]
