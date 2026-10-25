"""Safety boundary for the optional, unvalidated O-RADS research route."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.schemas.schemas import CDSSEvaluateRequest
from backend.services.cdss_engine import (
    IOTA_B_FEATURES,
    IOTA_M_FEATURES,
    CDSSReasoningEngine,
)

pytestmark = pytest.mark.usefixtures("doctor_access")


def _iota_eligible_context(**context):
    return {
        "is_persistent_adnexal_mass": True,
        "surgery_indicated": True,
        **context,
    }


def _physiologic_follicle_findings(**overrides):
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 29.9,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "physiologic_lesion_type": "follicle",
        "physiologic_morphology_confirmed": True,
        **overrides,
    }


def test_missing_descriptors_never_produce_a_risk_category():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={"max_diameter_mm": 35.0}, patient_context={}
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["orads_stratification"]["category"] is None
    assert "color_score" in result["orads_stratification"]["missing_fields"]
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["uncertainty_evaluation"]["confidence_score"] is None


def test_project_physiologic_follicle_rule_excludes_exactly_30_mm():
    result = CDSSReasoningEngine().evaluate_case(
        _physiologic_follicle_findings(max_diameter_mm=30.0),
        {"is_premenopausal": True},
    )

    assert result["orads_stratification"]["category"] is None
    assert result["implementation_policy"]["version"] == "project-follicle-lt30-v1"
    assert "không đồng nghĩa bất thường hoặc ác tính" in result["orads_stratification"]["reason"]


@pytest.mark.parametrize("diameter,expected_category", [(29.9, "O-RADS 1"), (30.0, None), (30.1, None)])
def test_physiologic_policy_boundary_is_versioned_and_explicit(diameter, expected_category):
    result = CDSSReasoningEngine().evaluate_case(
        _physiologic_follicle_findings(max_diameter_mm=diameter), {"is_premenopausal": True}
    )
    assert result["orads_stratification"]["category"] == expected_category
    assert result["implementation_policy"]["diameter_rule_mm"] == "0 < diameter < 30"
    assert "ACR US v2022 dùng ≤3 cm" in result["orads_stratification"]["reason"]


def test_empty_api_request_does_not_use_example_schema_defaults():
    with TestClient(app) as client:
        response = client.post("/api/v1/cdss/evaluate", json={})
    assert response.status_code == 200
    assert response.json()["orads_stratification"]["category"] is None
    assert response.json()["status"] == "INSUFFICIENT_DATA"
    assert response.json()["adnex_evaluation"]["status"] == "NOT_EVALUATED"
    assert response.json()["adnex_evaluation"]["probabilities"] is None


def test_cdss_request_model_has_no_fabricated_clinical_defaults():
    request = CDSSEvaluateRequest()

    assert request.vision_findings is None
    assert request.patient_context is None


@pytest.mark.parametrize("findings", [[], "invalid", 7])
def test_engine_fails_closed_for_non_object_findings(findings):
    result = CDSSReasoningEngine().evaluate_case(findings)

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["adnex_evaluation"]["status"] == "NOT_EVALUATED"


def test_cdss_api_rejects_findings_with_the_wrong_top_level_type():
    with TestClient(app) as client:
        response = client.post("/api/v1/cdss/evaluate", json={"vision_findings": []})

    assert response.status_code == 422


def test_cdss_api_rejects_unknown_top_level_fields_instead_of_ignoring_typoed_inputs():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={"adnex_input": {"model_variant": "WITH_CA125"}},
        )

    assert response.status_code == 422


def test_cdss_api_does_not_apply_iota_without_eligibility_context():
    descriptors = {feature: False for feature in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors["b3_acoustic_shadows"] = True
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={
                "vision_findings": {
                    "assessment_source": "clinician",
                    "modality": "ultrasound_2d",
                    "ultrasound_exam_complete": True,
                    "iota_simple_rules": descriptors,
                },
                "patient_context": {},
            },
        )

    assert response.status_code == 200
    assert response.json()["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert response.json()["iota_evaluation"]["eligibility_status"] == "NOT_CONFIRMED"


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
            "acoustic_shadowing": False,
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


def test_orads_1_requires_explicit_premenopausal_physiologic_follicle():
    result = CDSSReasoningEngine().evaluate_case(
        _physiologic_follicle_findings(), {"is_premenopausal": True}
    )

    assert result["status"] == "RULE_MATCHED"
    assert result["orads_stratification"]["category"] == "O-RADS 1"
    assert result["uncertainty_evaluation"]["confidence_score"] is None


def test_orads_1_does_not_follow_from_size_without_confirmed_physiology():
    engine = CDSSReasoningEngine()
    without_type = _physiologic_follicle_findings()
    del without_type["physiologic_lesion_type"]
    del without_type["physiologic_morphology_confirmed"]

    result = engine.evaluate_case(without_type, {"is_premenopausal": True})
    assert result["orads_stratification"]["category"] is None

    for change in (
        {"max_diameter_mm": 30.1},
        {"max_diameter_mm": 30.0},
        {"max_diameter_mm": 10**400},
        {"physiologic_lesion_type": "corpus_luteum"},
        {"physiologic_morphology_confirmed": False},
        {"has_solid_component": True},
    ):
        result = engine.evaluate_case(
            _physiologic_follicle_findings(**change), {"is_premenopausal": True}
        )
        assert result["orads_stratification"]["category"] is None


def test_orads_1_requires_explicit_premenopausal_context():
    result = CDSSReasoningEngine().evaluate_case(_physiologic_follicle_findings(), {})

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["orads_stratification"]["category"] is None
    assert "patient_context.is_premenopausal" in result["orads_stratification"]["missing_fields"]


def test_unknown_morphology_field_cannot_be_ignored_for_low_risk_rule():
    result = CDSSReasoningEngine().evaluate_case(
        _physiologic_follicle_findings(wall_irreglar=True),
        {"is_premenopausal": True},
    )

    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_unknown_vision_fields_block_adnex_probabilities():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={"wall_irreglar": True},
        adnex_inputs=_adnex_inputs(),
    )

    assert (
        result["orads_stratification"]["reason"]
        == "Mô tả siêu âm chứa trường không được hỗ trợ; chưa thể phân tầng."
    )
    assert result["adnex_evaluation"]["status"] == "NOT_EVALUATED"
    assert result["adnex_evaluation"]["probabilities"] is None


def test_cdss_api_fails_closed_for_unknown_nested_finding_fields():
    findings = _physiologic_follicle_findings(wall_irreglar=True)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={"vision_findings": findings, "patient_context": {"is_premenopausal": True}},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "UNSUPPORTED_PATTERN"
    assert response.json()["orads_stratification"]["category"] is None


def test_conflicting_special_lesion_types_fail_closed_instead_of_selecting_first_rule():
    findings = _physiologic_follicle_findings(classic_benign_lesion_type="dermoid")
    result = CDSSReasoningEngine().evaluate_case(
        findings,
        {"is_premenopausal": True},
    )

    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_binary_mask_and_pathology_text_do_not_trigger_orads():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings={
            "max_diameter_mm": 45.0,
            "pathology": "endometrioma",
            "binary_mask_rle": {"size": [512, 512], "counts": [262144]},
        },
        patient_context={"age": 32},
    )
    assert result["status"] == "UNSUPPORTED_PATTERN"
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
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
    }
    for change in (
        {"has_solid_component": True},
        {"locules_count": 3},
        {"color_score": 4},
        {"acoustic_shadowing": True},
    ):
        result = CDSSReasoningEngine().evaluate_case({**base, **change}, {})
        assert result["orads_stratification"]["category"] is None

    missing_shadow_descriptor = CDSSReasoningEngine().evaluate_case(
        {key: value for key, value in base.items() if key != "acoustic_shadowing"}, {}
    )
    assert missing_shadow_descriptor["status"] == "INSUFFICIENT_DATA"


def test_simple_cyst_rule_rejects_size_boundaries_and_nonfinite_values():
    base = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
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
    for diameter in (30.0, 100.0, float("nan"), float("inf"), True):
        result = CDSSReasoningEngine().evaluate_case(
            {**base, "max_diameter_mm": diameter}, {}
        )
        assert result["orads_stratification"]["category"] is None


def test_iota_simple_rules_use_explicit_clinician_feature_descriptors():
    descriptors = {
        "b1_unilocular_cyst": False,
        "b2_solid_component_lt_7mm": False,
        "b3_acoustic_shadows": True,
        "b4_smooth_multilocular_lt_100mm": False,
        "b5_no_detectable_blood_flow": False,
        "m1_irregular_solid_tumor": False,
        "m2_ascites": False,
        "m3_four_or_more_papillary_projections": False,
        "m4_irregular_multilocular_solid_ge_100mm": False,
        "m5_very_strong_color_doppler": False,
    }
    result = CDSSReasoningEngine().evaluate_case(
        {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "iota_simple_rules": descriptors,
        },
        _iota_eligible_context(),
    )

    assert result["iota_evaluation"]["rule_verdict"] == "BENIGN"
    assert result["iota_evaluation"]["benign_features_present"] == ["b3_acoustic_shadows"]
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["requires_clinician_confirmation"] is True

    malignant_descriptors = {
        **descriptors,
        "b3_acoustic_shadows": False,
        "m3_four_or_more_papillary_projections": True,
    }
    malignant = CDSSReasoningEngine().evaluate_case(
        {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "iota_simple_rules": malignant_descriptors,
        },
        _iota_eligible_context(),
    )
    assert malignant["iota_evaluation"]["rule_verdict"] == "MALIGNANT"


@pytest.mark.parametrize(
    ("finding_overrides", "iota_feature"),
    [
        ({"acoustic_shadowing": False}, "b3_acoustic_shadows"),
        ({"color_score": 4}, "b5_no_detectable_blood_flow"),
        ({"has_ascites": False}, "m2_ascites"),
        ({"papillary_projections_count": 0}, "m3_four_or_more_papillary_projections"),
        ({"color_score": 1}, "m5_very_strong_color_doppler"),
    ],
)
def test_conflicting_iota_flags_and_morphology_fail_closed(finding_overrides, iota_feature):
    descriptors = {feature: False for feature in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors[iota_feature] = True
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        **finding_overrides,
        "iota_simple_rules": descriptors,
    }

    result = CDSSReasoningEngine().evaluate_case(findings, _iota_eligible_context())

    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["iota_evaluation"]["invalid_feature_inputs"]


def test_iota_simple_rules_require_persistent_surgical_candidate_context():
    descriptors = {feature: False for feature in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors["b3_acoustic_shadows"] = True
    result = CDSSReasoningEngine().evaluate_case(
        {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "iota_simple_rules": descriptors,
        },
        {},
    )

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["iota_evaluation"]["missing_fields"] == [
        "patient_context.is_persistent_adnexal_mass",
        "patient_context.surgery_indicated",
    ]


def test_iota_simple_rules_stay_unevaluated_outside_the_surgery_candidate_scope():
    descriptors = {feature: False for feature in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors["b3_acoustic_shadows"] = True
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "iota_simple_rules": descriptors,
    }
    result = CDSSReasoningEngine().evaluate_case(
        findings,
        _iota_eligible_context(surgery_indicated=False),
    )

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["iota_evaluation"]["eligibility_status"] == "OUT_OF_SCOPE"
    assert result["iota_evaluation"]["missing_fields"] == []


def test_iota_simple_rules_require_boolean_eligibility_attestations():
    descriptors = {feature: False for feature in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors["b3_acoustic_shadows"] = True
    result = CDSSReasoningEngine().evaluate_case(
        {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "iota_simple_rules": descriptors,
        },
        _iota_eligible_context(is_persistent_adnexal_mass="true"),
    )

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["iota_evaluation"]["missing_fields"] == [
        "patient_context.is_persistent_adnexal_mass"
    ]


def test_iota_simple_rules_are_inconclusive_for_mixed_or_no_features():
    names = (
        "b1_unilocular_cyst",
        "b2_solid_component_lt_7mm",
        "b3_acoustic_shadows",
        "b4_smooth_multilocular_lt_100mm",
        "b5_no_detectable_blood_flow",
        "m1_irregular_solid_tumor",
        "m2_ascites",
        "m3_four_or_more_papillary_projections",
        "m4_irregular_multilocular_solid_ge_100mm",
        "m5_very_strong_color_doppler",
    )
    for positive_features in ((), ("b3_acoustic_shadows", "m1_irregular_solid_tumor")):
        descriptors = {name: name in positive_features for name in names}
        result = CDSSReasoningEngine().evaluate_case(
            {
                "assessment_source": "clinician",
                "modality": "ultrasound_2d",
                "ultrasound_exam_complete": True,
                "iota_simple_rules": descriptors,
            },
            _iota_eligible_context(),
        )
        assert result["iota_evaluation"]["rule_verdict"] == "INCONCLUSIVE"


def test_iota_simple_rules_fail_closed_for_missing_malformed_or_unverified_features():
    base = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "iota_simple_rules": {"b3_acoustic_shadows": True},
    }
    result = CDSSReasoningEngine().evaluate_case(base, _iota_eligible_context())
    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert "iota_simple_rules.b1_unilocular_cyst" in result["iota_evaluation"]["missing_fields"]

    malformed = {
        **base,
        "iota_simple_rules": {
            "b1_unilocular_cyst": 1,
            **{key: False for key in (
                "b2_solid_component_lt_7mm", "b3_acoustic_shadows",
                "b4_smooth_multilocular_lt_100mm", "b5_no_detectable_blood_flow",
                "m1_irregular_solid_tumor", "m2_ascites",
                "m3_four_or_more_papillary_projections",
                "m4_irregular_multilocular_solid_ge_100mm", "m5_very_strong_color_doppler",
            )},
        },
    }
    assert CDSSReasoningEngine().evaluate_case(malformed, _iota_eligible_context())["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"

    unverified = {**base, "assessment_source": "ai"}
    assert CDSSReasoningEngine().evaluate_case(unverified, _iota_eligible_context())["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"


def _typical_dermoid_findings(**overrides):
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "mixed",
        "acoustic_shadowing": True,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "classic_benign_lesion_type": "dermoid",
        "classic_benign_morphology_confirmed": True,
        "dermoid_features": ["hyperechoic_component_with_shadowing"],
        **overrides,
    }


def test_iota_malignant_rule_never_coexists_with_a_low_risk_orads_match():
    iota_features = {name: False for name in IOTA_B_FEATURES + IOTA_M_FEATURES}
    iota_features["m2_ascites"] = True
    simple_cyst = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 2,
        "has_ascites": True,
        "has_peritoneal_nodules": False,
    }
    result = CDSSReasoningEngine().evaluate_case(
        {**simple_cyst, "iota_simple_rules": iota_features},
        _iota_eligible_context(),
    )

    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["rule_verdict"] == "MALIGNANT"


def test_iota_m_feature_with_b_feature_cannot_fall_through_to_low_risk_orads():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
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
    descriptors = {name: False for name in IOTA_B_FEATURES + IOTA_M_FEATURES}
    descriptors["b3_acoustic_shadows"] = True
    descriptors["m2_ascites"] = True
    findings["color_score"] = 2
    findings["acoustic_shadowing"] = True
    findings["has_ascites"] = True
    result = CDSSReasoningEngine().evaluate_case(
        {**findings, "iota_simple_rules": descriptors},
        _iota_eligible_context(),
    )

    assert result["iota_evaluation"]["rule_verdict"] == "INCONCLUSIVE"
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_iota_m_feature_is_not_downgraded_when_other_features_are_missing():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": True,
        "has_peritoneal_nodules": False,
        "iota_simple_rules": {"m2_ascites": True},
    }
    result = CDSSReasoningEngine().evaluate_case(
        findings,
        _iota_eligible_context(),
    )

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert "iota_simple_rules.b1_unilocular_cyst" in result["iota_evaluation"]["missing_fields"]
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_unscoped_clinician_m_feature_cannot_be_overridden_by_low_risk_acr_fields():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "iota_simple_rules": {"m2_ascites": True},
    }
    result = CDSSReasoningEngine().evaluate_case(findings, {})

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert result["iota_evaluation"]["eligibility_status"] == "NOT_CONFIRMED"
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_malformed_iota_feature_cannot_fall_through_to_low_risk_orads():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 45.0,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "iota_simple_rules": {"m2_ascites": "true"},
    }
    result = CDSSReasoningEngine().evaluate_case(findings, _iota_eligible_context())

    assert result["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"
    assert "iota_simple_rules.m2_ascites" in result["iota_evaluation"]["missing_fields"]
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


def test_cdss_api_fails_closed_for_malformed_iota_descriptor_types():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "iota_simple_rules": {"m2_ascites": "true"},
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={
                "vision_findings": findings,
                "patient_context": _iota_eligible_context(),
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None
    assert result["iota_evaluation"]["invalid_feature_inputs"] == [
        "iota_simple_rules.m2_ascites"
    ]


def test_confirmed_typical_dermoid_shadowing_matches_orads_two():
    result = CDSSReasoningEngine().evaluate_case(_typical_dermoid_findings(), {})

    assert result["status"] == "RULE_MATCHED"
    assert result["orads_stratification"]["category"] == "O-RADS 2"
    assert result["orads_stratification"]["requires_clinician_confirmation"] is True


def test_cdss_api_matches_only_explicitly_confirmed_typical_dermoid():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={"vision_findings": _typical_dermoid_findings(), "patient_context": {}},
        )

    assert response.status_code == 200
    result = response.json()
    assert result["orads_stratification"]["category"] == "O-RADS 2"
    assert result["orads_stratification"]["requires_clinician_confirmation"] is True


@pytest.mark.parametrize(
    ("diameter", "category"),
    [(99.9, "O-RADS 2"), (100.0, "O-RADS 3")],
)
def test_typical_dermoid_orads_category_uses_ten_cm_boundary(diameter, category):
    result = CDSSReasoningEngine().evaluate_case(
        _typical_dermoid_findings(max_diameter_mm=diameter), {}
    )

    assert result["orads_stratification"]["category"] == category


@pytest.mark.parametrize(
    "change",
    [
        {"dermoid_features": []},
        {"fluid_echogenicity": "complex"},
        {"fluid_echogenicity": "unrecognized_descriptor"},
        {"classic_benign_morphology_confirmed": False},
        {"locules_count": 4},
        {"acoustic_shadowing": False},
        {"has_solid_component": True},
        {"color_score": 2},
        {"max_diameter_mm": float("nan")},
        {"max_diameter_mm": 10**400},
    ],
)
def test_atypical_or_incomplete_dermoid_descriptions_do_not_get_orads_category(change):
    result = CDSSReasoningEngine().evaluate_case(_typical_dermoid_findings(**change), {})

    assert result["orads_stratification"]["category"] is None


@pytest.mark.parametrize("echogenicity", ["complex", "unrecognized_descriptor"])
def test_cdss_api_fails_closed_for_noncanonical_cyst_content(echogenicity):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cdss/evaluate",
            json={
                "vision_findings": _typical_dermoid_findings(
                    fluid_echogenicity=echogenicity
                ),
                "patient_context": {},
            },
        )

    assert response.status_code == 200
    assert response.json()["orads_stratification"]["category"] is None


def test_acoustic_shadowing_alone_does_not_classify_a_dermoid():
    result = CDSSReasoningEngine().evaluate_case(
        _typical_dermoid_findings(
            classic_benign_lesion_type=None,
            classic_benign_morphology_confirmed=None,
            dermoid_features=None,
        ),
        {},
    )

    assert result["orads_stratification"]["category"] is None


def _adnex_inputs(variant="WITH_CA125", **overrides):
    inputs = {
        "model_variant": variant,
        "age_years": 50.0,
        "ca125_u_ml": 40.0 if variant == "WITH_CA125" else None,
        "is_oncology_center": False,
        "is_persistent_adnexal_mass": True,
        "surgery_indicated": True,
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_lesion_diameter_mm": 60.0,
        "largest_solid_component_mm": 12.0,
        "cyst_locules_count": 11,
        "papillary_projections_count": 4,
        "acoustic_shadowing": True,
        "has_ascites": False,
        "physiologic_follicle_confirmed": False,
    }
    inputs.update(overrides)
    return inputs


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        (
            "WITH_CA125",
            {
                "benign": 0.7944016887938715,
                "borderline": 0.15367013944607558,
                "stage_i_primary_malignancy": 0.03937540470725641,
                "stage_ii_iv_primary_malignancy": 0.009633258837877027,
                "secondary_metastatic": 0.0029195082149195747,
            },
        ),
        (
            "WITHOUT_CA125",
            {
                "benign": 0.830707563962098,
                "borderline": 0.13109490292860837,
                "stage_i_primary_malignancy": 0.030695497161256198,
                "stage_ii_iv_primary_malignancy": 0.005356604042769301,
                "secondary_metastatic": 0.0021454319052679905,
            },
        ),
    ],
)
def test_adnex_calculates_both_published_variants_and_returns_five_probabilities(
    variant, expected
):
    result = CDSSReasoningEngine().evaluate_case(adnex_inputs=_adnex_inputs(variant))

    evaluation = result["adnex_evaluation"]
    assert evaluation["status"] == "EVALUATED_RUO"
    assert evaluation["model_variant"] == variant
    assert evaluation["probabilities"] == pytest.approx(expected, abs=1e-12)
    assert sum(evaluation["probabilities"].values()) == pytest.approx(1.0)
    assert evaluation["total_malignancy_probability"] == pytest.approx(
        sum(value for key, value in expected.items() if key != "benign")
    )
    assert evaluation["requires_clinician_confirmation"] is True
    assert result["evidence_status"] == "UNVALIDATED_RESEARCH_PROTOTYPE"


def test_adnex_is_not_evaluated_when_any_predictor_is_missing_or_null():
    for inputs in (
        {key: value for key, value in _adnex_inputs().items() if key != "has_ascites"},
        _adnex_inputs(has_ascites=None),
        _adnex_inputs(model_variant=None),
    ):
        evaluation = CDSSReasoningEngine().evaluate_case(adnex_inputs=inputs)[
            "adnex_evaluation"
        ]
        assert evaluation["status"] == "NOT_EVALUATED"
        assert evaluation["probabilities"] is None
        assert evaluation["total_malignancy_probability"] is None


@pytest.mark.parametrize(
    "inputs",
    [{1: "unexpected", "unexpected": 1}, {"model_variant": []}],
)
def test_engine_fails_closed_for_malformed_adnex_objects(inputs):
    evaluation = CDSSReasoningEngine().evaluate_case(adnex_inputs=inputs)[
        "adnex_evaluation"
    ]

    assert evaluation["status"] == "NOT_EVALUATED"
    assert evaluation["probabilities"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"is_persistent_adnexal_mass": False},
        {"surgery_indicated": False},
        {"ultrasound_exam_complete": False},
        {"assessment_source": "ai"},
        {"modality": "dicom_mammography"},
        {"physiologic_follicle_confirmed": True},
    ],
)
def test_adnex_fails_closed_outside_explicit_model_scope(change):
    evaluation = CDSSReasoningEngine().evaluate_case(
        adnex_inputs=_adnex_inputs(**change)
    )["adnex_evaluation"]

    assert evaluation["status"] == "NOT_EVALUATED"
    assert evaluation["probabilities"] is None


def test_adnex_fails_closed_when_same_assessment_marks_a_physiologic_follicle():
    result = CDSSReasoningEngine().evaluate_case(
        vision_findings=_physiologic_follicle_findings(max_diameter_mm=20.0),
        patient_context={"is_premenopausal": True},
        adnex_inputs=_adnex_inputs(physiologic_follicle_confirmed=False),
    )

    assert result["orads_stratification"]["category"] == "O-RADS 1"
    assert result["adnex_evaluation"]["status"] == "NOT_EVALUATED"
    assert result["adnex_evaluation"]["probabilities"] is None


def test_adnex_fails_closed_when_same_request_has_conflicting_lesion_descriptors():
    findings = {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": 60.0,
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

    result = CDSSReasoningEngine().evaluate_case(
        findings, {}, _adnex_inputs()
    )

    adnex = result["adnex_evaluation"]
    assert result["orads_stratification"]["category"] == "O-RADS 2"
    assert adnex["status"] == "NOT_EVALUATED"
    assert adnex["probabilities"] is None
    assert set(adnex["invalid_fields"]) == {
        "vision_findings.has_solid_component",
        "adnex_inputs.largest_solid_component_mm",
        "vision_findings.locules_count",
        "adnex_inputs.cyst_locules_count",
        "vision_findings.papillary_projections_count",
        "adnex_inputs.papillary_projections_count",
        "vision_findings.acoustic_shadowing",
        "adnex_inputs.acoustic_shadowing",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("locules_count", 11.0),
        ("has_solid_component", "true"),
        ("papillary_projections_count", 4.0),
        ("acoustic_shadowing", 1),
        ("has_ascites", 0),
        ("ultrasound_exam_complete", 1),
    ],
)
def test_adnex_fails_closed_when_present_duplicate_vision_predictor_has_invalid_type(
    field, value
):
    result = CDSSReasoningEngine().evaluate_case(
        {field: value}, {}, _adnex_inputs()
    )

    adnex = result["adnex_evaluation"]
    assert adnex["status"] == "NOT_EVALUATED"
    assert adnex["probabilities"] is None
    assert f"vision_findings.{field}" in adnex["invalid_fields"]


@pytest.mark.parametrize(
    "patient_context",
    [
        {"is_persistent_adnexal_mass": False},
        {"surgery_indicated": False},
        {"surgery_indicated": "true"},
    ],
)
def test_adnex_fails_closed_when_patient_context_conflicts_with_eligibility(
    patient_context,
):
    evaluation = CDSSReasoningEngine().evaluate_case(
        patient_context=patient_context,
        adnex_inputs=_adnex_inputs(),
    )["adnex_evaluation"]

    assert evaluation["status"] == "NOT_EVALUATED"
    assert evaluation["probabilities"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"model_variant": "WITH_CA125", "ca125_u_ml": None},
        {"model_variant": "WITH_CA125", "ca125_u_ml": 0.0},
        {"model_variant": "WITH_CA125", "ca125_u_ml": -1.0},
        {"model_variant": "WITHOUT_CA125", "ca125_u_ml": 40.0},
        {"max_lesion_diameter_mm": 0.0},
        {"max_lesion_diameter_mm": -1.0},
        {"largest_solid_component_mm": 60.1},
        {"age_years": True},
        {"is_oncology_center": 1},
        {"age_years": float("nan")},
        {"age_years": float("inf")},
        {"age_years": 10**400},
        {"age_years": 131.0},
        {"max_lesion_diameter_mm": 10001.0},
    ],
)
def test_adnex_rejects_invalid_or_extreme_predictors_without_probabilities(change):
    evaluation = CDSSReasoningEngine().evaluate_case(
        adnex_inputs=_adnex_inputs(**change)
    )["adnex_evaluation"]

    assert evaluation["status"] == "NOT_EVALUATED"
    assert evaluation["probabilities"] is None


def test_adnex_uses_published_categories_for_more_than_three_papillary_projections():
    engine = CDSSReasoningEngine()
    four = engine.evaluate_case(adnex_inputs=_adnex_inputs(papillary_projections_count=4))
    more = engine.evaluate_case(adnex_inputs=_adnex_inputs(papillary_projections_count=7))

    assert more["adnex_evaluation"]["status"] == "EVALUATED_RUO"
    assert more["adnex_evaluation"]["probabilities"] == pytest.approx(
        four["adnex_evaluation"]["probabilities"]
    )


def test_adnex_api_evaluates_typed_request_and_keeps_incomplete_request_fail_closed():
    with TestClient(app) as client:
        complete = client.post(
            "/api/v1/cdss/evaluate",
            json={"adnex_inputs": _adnex_inputs()},
        )
        incomplete = client.post(
            "/api/v1/cdss/evaluate",
            json={"adnex_inputs": {"model_variant": "WITH_CA125"}},
        )

    assert complete.status_code == 200
    assert complete.json()["adnex_evaluation"]["status"] == "EVALUATED_RUO"
    assert incomplete.status_code == 200
    assert incomplete.json()["adnex_evaluation"]["status"] == "NOT_EVALUATED"
    assert incomplete.json()["adnex_evaluation"]["probabilities"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"adnex_inputs": {"unknown_predictor": 1}},
        {"adnex_inputs": {"model_variant": "WITH_CA125", "is_oncology_center": 1}},
        {"adnex_inputs": {"model_variant": "UNSUPPORTED"}},
    ],
)
def test_adnex_api_rejects_unknown_fields_and_wrong_scalar_types(payload):
    with TestClient(app) as client:
        response = client.post("/api/v1/cdss/evaluate", json=payload)

    assert response.status_code == 422
