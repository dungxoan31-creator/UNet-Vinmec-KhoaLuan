import pytest

from backend.services.clinical_templates import (
    CLINICAL_MACRO_TEMPLATES,
    apply_clinical_template,
    get_clinical_templates_list,
)


def test_clinical_templates_registry():
    templates = get_clinical_templates_list()
    assert len(templates) >= 5
    keys = [t["id"] for t in templates]
    assert "PHYSIOLOGIC_FOLLICLE" in keys
    assert "HEMORRHAGIC_CYST" in keys
    assert "CLASSIC_DERMOID" in keys
    assert "ENDOMETRIOMA" in keys
    assert "SMOOTH_MULTILOCULAR_BENIGN" in keys


def test_apply_physiologic_follicle_template():
    applied = apply_clinical_template(
        "PHYSIOLOGIC_FOLLICLE",
        max_diameter_mm=22.0,
        patient_context={"is_premenopausal": True},
    )
    assert applied["template_id"] == "PHYSIOLOGIC_FOLLICLE"
    findings = applied["findings"]
    assert findings["max_diameter_mm"] == 22.0
    assert findings["physiologic_lesion_type"] == "follicle"
    assert findings["physiologic_morphology_confirmed"] is None
    assert findings["locules_count"] == 1
    assert findings["has_solid_component"] is False

    # A template does not constitute a clinician-confirmed exam.
    cdss = applied["cdss_result"]
    assert cdss["status"] != "RULE_MATCHED"
    assert cdss["orads_stratification"]["category"] is None


def test_apply_classic_dermoid_template():
    applied = apply_clinical_template(
        "CLASSIC_DERMOID",
        max_diameter_mm=45.0,
        patient_context={"is_premenopausal": True},
    )
    findings = applied["findings"]
    assert findings["max_diameter_mm"] == 45.0
    assert findings["classic_benign_lesion_type"] == "dermoid"
    assert findings["acoustic_shadowing"] is True

    cdss = applied["cdss_result"]
    assert cdss["status"] != "RULE_MATCHED"
    assert cdss["orads_stratification"]["category"] is None


def test_apply_endometrioma_template():
    applied = apply_clinical_template(
        "ENDOMETRIOMA",
        max_diameter_mm=38.0,
        patient_context={"is_premenopausal": True},
    )
    findings = applied["findings"]
    assert findings["classic_benign_lesion_type"] == "endometrioma"
    assert findings["fluid_echogenicity"] == "ground_glass"

    cdss = applied["cdss_result"]
    assert cdss["status"] != "RULE_MATCHED"
    assert cdss["orads_stratification"]["category"] is None


def test_apply_multilocular_template():
    applied = apply_clinical_template(
        "SMOOTH_MULTILOCULAR_BENIGN",
        max_diameter_mm=60.0,
        patient_context={"is_premenopausal": True},
    )
    findings = applied["findings"]
    assert findings["locules_count"] >= 2
    assert findings["has_solid_component"] is False


def test_apply_unknown_template_raises_value_error():
    with pytest.raises(ValueError, match="Không tìm thấy template"):
        apply_clinical_template("NON_EXISTENT_TEMPLATE")


@pytest.mark.parametrize("template_id", CLINICAL_MACRO_TEMPLATES)
def test_templates_never_invent_measurements_or_issue_management(template_id):
    applied = apply_clinical_template(template_id)
    assert applied["findings"]["max_diameter_mm"] is None
    assert applied["findings"]["assessment_source"] is None
    assert applied["findings"]["ultrasound_exam_complete"] is None
    assert applied["recommendation"] is None
    assert applied["cdss_result"]["orads_stratification"]["category"] is None
    assert applied["cdss_result"]["orads_stratification"]["clinical_management"] is None


def test_api_list_clinical_templates(doctor_access):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        res = client.get("/api/v1/clinical-templates")
    assert res.status_code == 200
    data = res.json()
    assert "templates" in data
    assert len(data["templates"]) >= 5


def test_api_apply_clinical_template(doctor_access):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        res = client.post(
            "/api/v1/clinical-templates/apply",
            json={"template_id": "PHYSIOLOGIC_FOLLICLE", "max_diameter_mm": 24.0},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["template_id"] == "PHYSIOLOGIC_FOLLICLE"
    assert data["findings"]["max_diameter_mm"] == 24.0
    assert data["findings"]["physiologic_lesion_type"] == "follicle"
