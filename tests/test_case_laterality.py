import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_create_case_with_ovary_laterality():
    payload = {
        "patient_id": "BN-TEST-LATERALITY-01",
        "study_code": "US-TEST-RO-001",
        "study_date": "2026-10-03",
        "patient_age": "30-39",
        "clinical_notes": "Khảo sát u nang bì buồng trứng phải",
        "active_ovary_side": "RIGHT",
        "contralateral_status": "NOT_VISUALIZED",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "BN-TEST-LATERALITY-01"
    assert data.get("ovary_side") == "RIGHT"
    assert data.get("contralateral_status") == "NOT_VISUALIZED"

def test_default_contralateral_status():
    payload = {
        "patient_id": "BN-TEST-LATERALITY-02",
        "study_date": "2026-10-03",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("ovary_side") == "RIGHT"
    assert data.get("contralateral_status") == "NOT_VISUALIZED"
