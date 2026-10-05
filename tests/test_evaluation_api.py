from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

def test_get_evaluation_metrics():
    resp = client.get("/api/evaluation/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "validation" in data
    assert "test" in data
    assert data["validation"]["dice_mean"] > 0.80
    assert data["validation"]["count"] == 123
    assert data["test"]["dice_mean"] > 0.50

def test_get_evaluation_samples():
    resp = client.get("/api/evaluation/samples?limit=10")
    assert resp.status_code == 200
    samples = resp.json()
    assert len(samples) > 0
    assert "case_id" in samples[0]
    assert "dice" in samples[0]
    assert "failure_category" in samples[0]

def test_get_sample_workstation_bundle():
    resp = client.get("/api/evaluation/samples/43/workstation-bundle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "43"
    assert data["original_image_base64"].startswith("data:image/jpeg;base64,")
    assert data["ground_truth_mask_base64"].startswith("data:image/png;base64,")
    assert data["prediction_mask_base64"].startswith("data:image/png;base64,")
    assert "benchmark_metrics" in data
    assert data["benchmark_metrics"]["dice"] > 0.90
