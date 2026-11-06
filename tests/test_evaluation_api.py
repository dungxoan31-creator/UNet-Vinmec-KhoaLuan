import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import get_current_user
from backend.db.database import UserModel

client = TestClient(app)

@pytest.fixture(autouse=True)
def evaluation_reviewer_access():
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id="evaluation-reviewer",
        username="evaluation_reviewer",
        full_name="Synthetic Evaluation Reviewer",
        role="SENIOR",
        facility_id="FAC-DEFAULT-TEST",
    )
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous


def test_get_evaluation_metrics_withholds_unverified_legacy_archives():
    response = client.get("/api/evaluation/metrics")
    assert response.status_code == 200
    data = response.json()

    assert data["archived_split_status"]["status"] == "BLOCKED"
    assert data["archived_split_status"]["metrics_available"] is False
    assert data["archived_split_status"]["samples_available"] is False
    assert "provenance" in data["archived_split_status"]["reason"].lower()
    assert data["validation"]["count"] is None
    assert data["validation"]["dice_mean"] is None
    assert data["test"]["count"] is None
    assert data["test"]["dice_mean"] is None
    assert "Vinmec" not in str(data["train"])
    assert "Vinmec" not in str(data["validation"])
    assert "Vinmec" not in str(data["test"])


def test_manifest_presence_alone_does_not_unlock_legacy_archives(tmp_path, monkeypatch):
    from backend.app.routers import evaluation

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"counts":{"train":697,"val":123,"test":382},"split_level":"image"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation, "SPLIT_MANIFEST_PATH", str(manifest))

    response = client.get("/api/evaluation/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["archived_split_status"]["manifest_available"] is True
    assert payload["archived_split_status"]["status"] == "BLOCKED"
    assert payload["validation"]["dice_mean"] is None


def test_get_evaluation_samples_withholds_legacy_archive():
    response = client.get("/api/evaluation/samples?limit=10")
    assert response.status_code == 503
    assert "provenance" in response.json()["detail"].lower()


def test_get_sample_workstation_bundle_withholds_legacy_archive():
    response = client.get("/api/evaluation/samples/43/workstation-bundle")
    assert response.status_code == 503
    assert "provenance" in response.json()["detail"].lower()


def test_benchmark_sample_images_are_blocked_in_synthetic_demo(monkeypatch):
    from backend.app.routers import evaluation

    monkeypatch.setattr(evaluation, "SYNTHETIC_DEMO_MODE", True)
    metrics = client.get("/api/evaluation/metrics")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert metrics_payload["current_run"] is None
    assert metrics_payload["current_run_status"]["status"] == "SYNTHETIC_DEMO_BLOCKED"
    assert metrics_payload["validation"]["dice_mean"] is None
    assert metrics_payload["test"]["dice_mean"] is None

    for path in (
        "/api/evaluation/samples",
        "/api/evaluation/samples/43/workstation-bundle",
        "/api/evaluation/samples/43/download/image",
    ):
        response = client.get(path)
        assert response.status_code == 403, (path, response.text)
        assert "synthetic-only demo mode" in response.text
