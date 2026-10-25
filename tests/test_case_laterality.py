import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

pytestmark = pytest.mark.usefixtures("doctor_access")

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
    assert data["patient_id"].startswith("SYN-")
    assert data["patient_id"] != payload["patient_id"]
    assert data.get("ovary_side") == "RIGHT"
    assert data.get("contralateral_status") == "NOT_VISUALIZED"

def test_missing_study_context_defaults_to_unknown():
    payload = {
        "patient_id": "BN-TEST-LATERALITY-02",
        "study_date": "2026-10-03",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("ovary_side") == "UNKNOWN"
    assert data.get("contralateral_status") == "UNKNOWN"


def test_create_case_rejects_missing_study_date():
    response = client.post(
        "/api/cases",
        json={"patient_id": "BN-TEST-LATERALITY-NO-DATE"},
    )
    assert response.status_code == 422
