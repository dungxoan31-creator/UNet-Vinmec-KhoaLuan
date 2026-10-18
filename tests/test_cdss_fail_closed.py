"""Safety boundary for the optional, unvalidated O-RADS research route."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.cdss_engine import CDSSReasoningEngine

pytestmark = pytest.mark.usefixtures("doctor_access")


def test_missing_descriptors_never_produce_a_risk_category():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={"max_diameter_mm": 35.0}, patient_context={}
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["uncertainty_evaluation"]["confidence_score"] is None
    assert "color_score" in result["orads_stratification"]["missing_fields"]


def test_empty_api_request_does_not_use_example_schema_defaults():
    with TestClient(app) as client:
        response = client.post("/api/v1/cdss/evaluate", json={})
    assert response.status_code == 200
    assert response.json()["orads_stratification"]["category"] is None
    assert response.json()["status"] == "INSUFFICIENT_DATA"


def test_clinician_entered_complete_simple_cyst_matches_limited_rule():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "max_diameter_mm": 45.0,
            "locules_count": 1,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "anechoic",
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
        },
        patient_context={"is_postmenopausal": False},
    )
    assert result["status"] == "RULE_MATCHED"
    assert result["orads_stratification"]["category"] == "O-RADS 2"
    assert result["uncertainty_evaluation"]["confidence_score"] is None
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"


def test_binary_mask_and_pathology_text_do_not_trigger_orads():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={
            "max_diameter_mm": 45.0,
            "pathology": "endometrioma",
            "binary_mask_rle": {"size": [512, 512], "counts": [262144]},
        },
        patient_context={"age": 32},
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["orads_stratification"]["category"] is None


def test_conflicting_or_unsupported_descriptors_are_not_downgraded_to_simple_cyst():
    base = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
    }
    for change in ({"has_solid_component": True}, {"locules_count": 3}, {"color_score": 4}):
        result = CDSSReasoningEngine().evaluate_case({**base, **change}, {})
        assert result["orads_stratification"]["category"] is None
