"""Comprehensive 30-case synthetic validation matrix for deterministic CDSS reasoning.

Covers O-RADS US v2022 stratification, IOTA Simple Rules, and IOTA ADNEX risk model
under Assumption A3 with ruleset_version locked to '2022.1'.
"""

from __future__ import annotations

import pytest

from backend.services.cdss_engine import (
    IOTA_B_FEATURES,
    IOTA_M_FEATURES,
    CDSSReasoningEngine,
)


def _base_valid_findings(**overrides):
    return {
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
        **overrides,
    }


def _iota_eligible_context(**context):
    return {
        "is_persistent_adnexal_mass": True,
        "surgery_indicated": True,
        **context,
    }


def _iota_all_features_dict(active_features=(), color_score=1):
    # Default all 10 features to False
    d = {f: False for f in IOTA_B_FEATURES + IOTA_M_FEATURES}
    # Enforce Doppler consistency
    if color_score == 1:
        d["b5_no_detectable_blood_flow"] = True
    elif color_score == 4:
        d["m5_very_strong_color_doppler"] = True
    # Activate any additional features
    for feat in active_features:
        d[feat] = True
    return d


# 30 Synthetic Test Cases Matrix
SYNTHETIC_CASES = [
    # --- Category 1: Physiologic Follicles (O-RADS 1) ---
    {
        "id": "CASE-01",
        "description": "Physiologic follicle 20mm in premenopausal woman",
        "findings": _base_valid_findings(
            max_diameter_mm=20.0,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {"is_premenopausal": True},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 1",
    },
    {
        "id": "CASE-02",
        "description": "Small follicle 12mm in premenopausal woman",
        "findings": _base_valid_findings(
            max_diameter_mm=12.0,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {"is_premenopausal": True},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 1",
    },
    {
        "id": "CASE-03",
        "description": "Dominant follicle 28.5mm in premenopausal woman (<30mm)",
        "findings": _base_valid_findings(
            max_diameter_mm=28.5,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {"is_premenopausal": True},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 1",
    },
    {
        "id": "CASE-04",
        "description": "Physiologic follicle flag claimed for postmenopausal woman (invalid)",
        "findings": _base_valid_findings(
            max_diameter_mm=20.0,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {"is_premenopausal": False},
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_orads": None,
    },
    {
        "id": "CASE-05",
        "description": "Follicle exceeding 30mm threshold (35mm)",
        "findings": _base_valid_findings(
            max_diameter_mm=35.0,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {"is_premenopausal": True},
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_orads": None,
    },
    {
        "id": "CASE-06",
        "description": "Follicle with missing premenopausal status in patient context",
        "findings": _base_valid_findings(
            max_diameter_mm=22.0,
            physiologic_lesion_type="follicle",
            physiologic_morphology_confirmed=True,
        ),
        "context": {},
        "expected_status": "INSUFFICIENT_DATA",
        "expected_orads": None,
    },
    # --- Category 2: Simple Cysts (O-RADS 2) ---
    {
        "id": "CASE-07",
        "description": "Simple unilocular anechoic cyst 35mm",
        "findings": _base_valid_findings(max_diameter_mm=35.0),
        "context": {"is_premenopausal": True},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
    },
    {
        "id": "CASE-08",
        "description": "Simple unilocular anechoic cyst 60mm",
        "findings": _base_valid_findings(max_diameter_mm=60.0),
        "context": {"is_premenopausal": False},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
    },
    {
        "id": "CASE-09",
        "description": "Simple unilocular anechoic cyst 95mm (approaching 10cm limit)",
        "findings": _base_valid_findings(max_diameter_mm=95.0),
        "context": {"is_premenopausal": True},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
    },
    {
        "id": "CASE-10",
        "description": "Simple cyst under 30mm without physiologic follicle flag",
        "findings": _base_valid_findings(max_diameter_mm=25.0),
        "context": {},
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_orads": None,
    },
    {
        "id": "CASE-11",
        "description": "Simple cyst exceeding 100mm (110mm)",
        "findings": _base_valid_findings(max_diameter_mm=110.0),
        "context": {},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 3",
    },
    # --- Category 3: Classic Dermoid Cysts (O-RADS 2 vs O-RADS 3) ---
    {
        "id": "CASE-12",
        "description": "Classic typical dermoid 45mm with shadowing (<10cm -> O-RADS 2)",
        "findings": _base_valid_findings(
            max_diameter_mm=45.0,
            acoustic_shadowing=True,
            fluid_echogenicity="mixed",
            classic_benign_lesion_type="dermoid",
            classic_benign_morphology_confirmed=True,
            dermoid_features=["hyperechoic_component_with_shadowing"],
        ),
        "context": {},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
    },
    {
        "id": "CASE-13",
        "description": "Classic dermoid 75mm with hyperechoic lines and dots",
        "findings": _base_valid_findings(
            max_diameter_mm=75.0,
            acoustic_shadowing=True,
            fluid_echogenicity="mixed",
            classic_benign_lesion_type="dermoid",
            classic_benign_morphology_confirmed=True,
            dermoid_features=["hyperechoic_lines_and_dots"],
        ),
        "context": {},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
    },
    {
        "id": "CASE-14",
        "description": "Large classic dermoid 120mm (>=10cm -> O-RADS 3)",
        "findings": _base_valid_findings(
            max_diameter_mm=120.0,
            acoustic_shadowing=True,
            fluid_echogenicity="mixed",
            classic_benign_lesion_type="dermoid",
            classic_benign_morphology_confirmed=True,
            dermoid_features=["hyperechoic_component_with_shadowing"],
        ),
        "context": {},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 3",
    },
    {
        "id": "CASE-15",
        "description": "Dermoid declaring hyperechoic shadowing but acoustic_shadowing=False (contradiction)",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            acoustic_shadowing=False,
            fluid_echogenicity="mixed",
            classic_benign_lesion_type="dermoid",
            classic_benign_morphology_confirmed=True,
            dermoid_features=["hyperechoic_component_with_shadowing"],
        ),
        "context": {},
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_orads": None,
    },
    {
        "id": "CASE-16",
        "description": "Dermoid declaring solid component (has_solid_component=True) -> not classic benign",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            has_solid_component=True,
            acoustic_shadowing=True,
            fluid_echogenicity="mixed",
            classic_benign_lesion_type="dermoid",
            classic_benign_morphology_confirmed=True,
            dermoid_features=["hyperechoic_component_with_shadowing"],
        ),
        "context": {},
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_orads": None,
    },
    # --- Category 4: IOTA Simple Rules (B-Rules, M-Rules, Inconclusive) ---
    {
        "id": "CASE-17",
        "description": "IOTA Simple Rules: Pure B1 (unilocular) + B5 (no blood flow)",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            iota_simple_rules=_iota_all_features_dict(["b1_unilocular_cyst"], color_score=1),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
        "expected_iota": "BENIGN",
    },
    {
        "id": "CASE-18",
        "description": "IOTA Simple Rules: Pure B3 (acoustic shadows)",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            acoustic_shadowing=True,
            iota_simple_rules=_iota_all_features_dict(["b3_acoustic_shadows"], color_score=1),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",  # O-RADS does not support simple cyst with shadowing
        "expected_iota": "BENIGN",
    },
    {
        "id": "CASE-19",
        "description": "IOTA Simple Rules: Pure B4 (smooth multilocular cyst <100mm)",
        "findings": _base_valid_findings(
            max_diameter_mm=60.0,
            locules_count=3,
            iota_simple_rules=_iota_all_features_dict(["b4_smooth_multilocular_lt_100mm"], color_score=1),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",  # O-RADS narrow engine only matches unilocular
        "expected_iota": "BENIGN",
    },
    {
        "id": "CASE-20",
        "description": "IOTA Simple Rules: Pure M1 (irregular solid tumor) -> Malignant verdict & O-RADS safety block",
        "findings": _base_valid_findings(
            max_diameter_mm=70.0,
            has_solid_component=True,
            wall_irregular=True,
            color_score=2,
            iota_simple_rules=_iota_all_features_dict(["m1_irregular_solid_tumor"], color_score=2),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_iota": "MALIGNANT",
    },
    {
        "id": "CASE-21",
        "description": "IOTA Simple Rules: Pure M2 (ascites) -> Malignant verdict",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            has_ascites=True,
            color_score=2,
            iota_simple_rules=_iota_all_features_dict(["m2_ascites"], color_score=2),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_iota": "MALIGNANT",
    },
    {
        "id": "CASE-22",
        "description": "IOTA Simple Rules: Pure M3 (at least 4 papillary projections)",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            papillary_projections_count=4,
            color_score=2,
            iota_simple_rules=_iota_all_features_dict(["m3_four_or_more_papillary_projections"], color_score=2),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_iota": "MALIGNANT",
    },
    {
        "id": "CASE-23",
        "description": "IOTA Simple Rules: Both B and M present (B1 unilocular + M2 ascites) -> INCONCLUSIVE",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            has_ascites=True,
            color_score=1,
            iota_simple_rules=_iota_all_features_dict(["b1_unilocular_cyst", "m2_ascites"], color_score=1),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_iota": "INCONCLUSIVE",
    },
    {
        "id": "CASE-24",
        "description": "IOTA Simple Rules: Neither B nor M present (all 10 False, color_score=2) -> INCONCLUSIVE",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            color_score=2,
            iota_simple_rules=_iota_all_features_dict([], color_score=2),
        ),
        "context": _iota_eligible_context(),
        "expected_status": "UNSUPPORTED_PATTERN",
        "expected_iota": "INCONCLUSIVE",
    },
    {
        "id": "CASE-25",
        "description": "IOTA Simple Rules: Ineligible (persistent mass = False) -> OUT_OF_SCOPE",
        "findings": _base_valid_findings(
            max_diameter_mm=50.0,
            iota_simple_rules=_iota_all_features_dict(["b1_unilocular_cyst"], color_score=1),
        ),
        "context": {"is_persistent_adnexal_mass": False, "surgery_indicated": False},
        "expected_status": "RULE_MATCHED",
        "expected_orads": "O-RADS 2",
        "expected_iota_eligibility": "OUT_OF_SCOPE",
    },
    # --- Category 5: IOTA ADNEX Risk Model Evaluation ---
    {
        "id": "CASE-26",
        "description": "IOTA ADNEX with CA125: 60yo postmenopausal, oncology center, 70mm, 20mm solid, CA125=150",
        "findings": _base_valid_findings(
            max_diameter_mm=70.0,
            has_solid_component=True,
            locules_count=1,
            papillary_projections_count=0,
            acoustic_shadowing=False,
            has_ascites=False,
        ),
        "context": {"age": 60, "is_postmenopausal": True},
        "adnex_inputs": {
            "model_variant": "WITH_CA125",
            "age_years": 60,
            "is_oncology_center": True,
            "is_persistent_adnexal_mass": True,
            "surgery_indicated": True,
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "max_lesion_diameter_mm": 70.0,
            "largest_solid_component_mm": 20.0,
            "cyst_locules_count": 1,
            "papillary_projections_count": 0,
            "acoustic_shadowing": False,
            "has_ascites": False,
            "physiologic_follicle_confirmed": False,
            "ca125_u_ml": 150.0,
        },
        "expected_adnex_status": "EVALUATED_RUO",
    },
    {
        "id": "CASE-27",
        "description": "IOTA ADNEX without CA125: 28yo premenopausal, non-oncology, 40mm, unilocular",
        "findings": _base_valid_findings(
            max_diameter_mm=40.0,
            has_solid_component=False,
            locules_count=1,
            papillary_projections_count=0,
            acoustic_shadowing=False,
            has_ascites=False,
        ),
        "context": {"age": 28, "is_premenopausal": True},
        "adnex_inputs": {
            "model_variant": "WITHOUT_CA125",
            "age_years": 28,
            "is_oncology_center": False,
            "is_persistent_adnexal_mass": True,
            "surgery_indicated": True,
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": True,
            "max_lesion_diameter_mm": 40.0,
            "largest_solid_component_mm": 0.0,
            "cyst_locules_count": 1,
            "papillary_projections_count": 0,
            "acoustic_shadowing": False,
            "has_ascites": False,
            "physiologic_follicle_confirmed": False,
        },
        "expected_adnex_status": "EVALUATED_RUO",
    },
    # --- Category 6: Fail-Closed Boundaries & Safety Gates ---
    {
        "id": "CASE-28",
        "description": "Safety gate: AI-inferred assessment source rejected (requires clinician)",
        "findings": _base_valid_findings(assessment_source="ai_inferred"),
        "context": {},
        "expected_status": "INSUFFICIENT_DATA",
    },
    {
        "id": "CASE-29",
        "description": "Safety gate: Incomplete ultrasound exam rejected",
        "findings": _base_valid_findings(ultrasound_exam_complete=False),
        "context": {},
        "expected_status": "INSUFFICIENT_DATA",
    },
    {
        "id": "CASE-30",
        "description": "Safety gate: Unsupported unexpected fields rejected",
        "findings": _base_valid_findings(unsupported_custom_flag=True),
        "context": {},
        "expected_status": "UNSUPPORTED_PATTERN",
    },
]


@pytest.mark.parametrize("case", SYNTHETIC_CASES, ids=[c["id"] for c in SYNTHETIC_CASES])
def test_cdss_synthetic_case_matrix(case):
    """Execute each synthetic case against the deterministic CDSS reasoning engine."""
    engine = CDSSReasoningEngine()
    result = engine.evaluate_case(
        vision_findings=case.get("findings"),
        patient_context=case.get("context"),
        adnex_inputs=case.get("adnex_inputs"),
    )

    # 1. Ruleset locking check
    assert result.get("ruleset_version") == "2022.1", (
        f"{case['id']}: ruleset_version must be locked to '2022.1'"
    )

    # 2. Main engine status check
    if "expected_status" in case:
        assert result["status"] == case["expected_status"], (
            f"{case['id']} ({case['description']}): Expected status '{case['expected_status']}', got '{result['status']}'"
        )

    # 3. O-RADS category check
    if "expected_orads" in case:
        actual_cat = result["orads_stratification"]["category"]
        assert actual_cat == case["expected_orads"], (
            f"{case['id']} ({case['description']}): Expected O-RADS '{case['expected_orads']}', got '{actual_cat}'"
        )

    # 4. IOTA Simple Rules verdict check
    if "expected_iota" in case:
        actual_iota = result["iota_evaluation"]["rule_verdict"]
        assert actual_iota == case["expected_iota"], (
            f"{case['id']} ({case['description']}): Expected IOTA verdict '{case['expected_iota']}', got '{actual_iota}'"
        )

    # 5. IOTA eligibility check
    if "expected_iota_eligibility" in case:
        actual_elig = result["iota_evaluation"]["eligibility_status"]
        assert actual_elig == case["expected_iota_eligibility"], (
            f"{case['id']}: Expected eligibility '{case['expected_iota_eligibility']}', got '{actual_elig}'"
        )

    # 6. ADNEX evaluation check
    if "expected_adnex_status" in case:
        adnex = result.get("adnex_evaluation", {})
        assert adnex.get("status") == case["expected_adnex_status"], (
            f"{case['id']}: Expected ADNEX status '{case['expected_adnex_status']}', got '{adnex.get('status')}'"
        )
        probs = adnex.get("probabilities", {})
        assert probs is not None
        prob_sum = sum(probs.values())
        assert prob_sum == pytest.approx(1.0, abs=0.01), (
            f"{case['id']}: ADNEX probabilities must sum to 1.0, got {prob_sum}"
        )


def test_cdss_matrix_complete_case_count():
    """Verify that the synthetic validation matrix contains at least 30 distinct cases."""
    assert len(SYNTHETIC_CASES) >= 30, f"Expected >= 30 cases, got {len(SYNTHETIC_CASES)}"
