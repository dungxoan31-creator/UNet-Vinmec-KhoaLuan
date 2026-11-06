import numpy as np

from backend.services.inference_engine import synthesize_multibranch_findings

PROBABILITIES = {
    "simple_cyst": 0.80,
    "serous_cystadenoma": 0.10,
    "mucinous_cystadenoma": 0.05,
    "chocolate_cyst": 0.02,
    "teratoma": 0.01,
    "theca_cell_tumor": 0.01,
    "high_grade_serous_cystadenocarcinoma": 0.01,
    "normal_ovary": 0.0,
}


def complete_clinician_findings():
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 35.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
    }


def test_estimated_mask_features_are_not_automatically_sent_to_cdss():
    img_gray = np.full((512, 512), 40, dtype=np.uint8)
    mask = np.zeros((512, 512), dtype=np.uint8)
    mask[200:300, 200:300] = 1
    img_gray[200:300, 200:300] = 5

    findings = synthesize_multibranch_findings(
        study_id="STUDY-TEST-001",
        side="right",
        pixel_spacing_mm=0.2,
        lesion_measurements={"longest_diameter_mm": 25.0},
        follicle_measurements=None,
        lesion_probs=PROBABILITIES,
        img_gray=img_gray,
        binary_mask=mask,
    )

    assert findings["study_id"] == "STUDY-TEST-001"
    assert findings["side"] == "right"
    assert findings["follicles"] is None
    assert findings["ai_diagnosis"]["pcos_suggestion"] is None
    assert "cdss_raw" not in findings["ai_diagnosis"]
    assert findings["ai_diagnosis"]["orads_suggested"]["complete"] is False


def test_explicit_clinician_findings_use_nested_orads_category_mapping():
    findings = synthesize_multibranch_findings(
        study_id="STUDY-TEST-002",
        side="left",
        lesion_probs=PROBABILITIES,
        clinician_findings=complete_clinician_findings(),
    )

    diagnosis = findings["ai_diagnosis"]
    assert diagnosis["cdss_raw"]["status"] == "RULE_MATCHED"
    assert diagnosis["cdss_raw"]["orads_stratification"]["category"] == "O-RADS 2"
    assert diagnosis["orads_suggested"]["category"] == "O-RADS 2"


def test_missing_clinician_descriptors_are_not_marked_complete():
    findings = synthesize_multibranch_findings(
        study_id="STUDY-TEST-003",
        side="left",
        lesion_probs=PROBABILITIES,
        clinician_findings={
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "max_diameter_mm": 40.0,
        },
    )

    diagnosis = findings["ai_diagnosis"]
    assert diagnosis["cdss_raw"]["status"] == "INSUFFICIENT_DATA"
    assert diagnosis["cdss_raw"]["orads_stratification"]["missing_fields"]
    assert diagnosis["orads_suggested"]["complete"] is False
    assert diagnosis["orads_suggested"]["category"] is None


def test_synthesize_abstains_on_invalid_probability_vector():
    findings = synthesize_multibranch_findings(
        study_id="STUDY-TEST-004",
        side="left",
        lesion_probs={"simple_cyst": float("nan")},
    )

    assert findings["ai_diagnosis"]["abstain"] is True
    assert findings["ai_diagnosis"]["malignancy_risk"] is None
