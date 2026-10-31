"""Conservative research-only IOTA and O-RADS rule probes.

The segmentation model supplies only a binary lesion mask. It cannot observe
the morphology or Doppler descriptors needed for O-RADS or IOTA. The engine
accepts clinician-entered descriptors, applies IOTA Simple Rules only for an
explicitly confirmed persistent adnexal mass considered for surgery and when
all ten features are explicit, and matches a small set of narrow ACR rules. It
has no clinical validation and does not infer descriptors from pixels.
"""

import math
from typing import Any

ACR_ASSESSMENT_CATEGORIES = (
    "https://edge.sitecorecloud.io/americancoldf5f-acrorgf92a-productioncb02-3650/"
    "media/ACR/Files/RADS/O-RADS/O-RADS--Ultrasound-v2022-Assessment-Categories.pdf"
)
PHYSIOLOGIC_FOLLICLE_POLICY = {
    "version": "project-follicle-lte30-v2",
    "scope": "Research implementation; not the full ACR rule set",
    "diameter_rule_mm": "0 < diameter <= 30",
    "source_diameter_rule": "ACR O-RADS US v2022: follicle <=3 cm (<=30 mm)",
    "source": ACR_ASSESSMENT_CATEGORIES,
    "deviation": "Project policy supports up to exactly 30 mm; unsupported is not abnormal or malignant.",
}
IOTA_SIMPLE_RULES_SOURCE = "https://www.bmj.com/content/341/bmj.c6839"
IOTA_TERMS_SOURCE = "https://obgyn.onlinelibrary.wiley.com/doi/full/10.1002/uog.70191"
ADNEX_FORMULA_SOURCE = (
    "https://bmjmedicine.bmj.com/content/bmjmed/suppl/2024/02/17/"
    "10.1136/bmjmed-2023-000817.DC1/"
    "bmjmed-2023-000817supp001_data_supplement.pdf"
)
ADNEX_PROBABILITY_KEYS = (
    "benign",
    "borderline",
    "stage_i_primary_malignancy",
    "stage_ii_iv_primary_malignancy",
    "secondary_metastatic",
)
# Coefficients transcribed from Supplement S1 to Barreñada et al., BMJ
# Medicine 2024; see ADNEX_FORMULA_SOURCE. Predictors are in the published order.
ADNEX_WITH_CA125_COEFFICIENTS = (
    (
        -7.577663,
        0.004506,
        0.111642,
        0.372046,
        6.967853,
        -5.65588,
        1.375079,
        0.604238,
        -2.04157,
        0.971061,
        0.953043,
    ),
    (
        -12.276041,
        0.01726,
        0.197249,
        0.87353,
        9.583053,
        -5.83319,
        0.791873,
        0.400369,
        -1.87763,
        0.452731,
        0.452484,
    ),
    (
        -14.91583,
        0.051239,
        0.765456,
        0.430477,
        10.37696,
        -5.70975,
        0.273692,
        0.389874,
        -2.35516,
        1.348408,
        0.459021,
    ),
    (
        -11.909267,
        0.033601,
        0.276166,
        0.449025,
        6.644939,
        -2.3033,
        0.89998,
        0.215645,
        -2.49845,
        1.636407,
        0.808887,
    ),
)
ADNEX_WITHOUT_CA125_COEFFICIENTS = (
    (
        -7.412534,
        0.003489,
        0.430701,
        7.117925,
        -5.74135,
        1.343699,
        0.607211,
        -2.11885,
        1.167767,
        0.983227,
    ),
    (
        -12.201607,
        0.017607,
        0.98728,
        10.07145,
        -6.17742,
        0.763081,
        0.410449,
        -1.98073,
        0.77054,
        0.543677,
    ),
    (
        -12.826207,
        0.045172,
        0.759002,
        11.83296,
        -6.64336,
        0.316444,
        0.390959,
        -2.94082,
        2.691276,
        0.929483,
    ),
    (
        -11.424379,
        0.033407,
        0.560396,
        7.264105,
        -2.77392,
        0.983394,
        0.199164,
        -2.63702,
        2.185574,
        0.906249,
    ),
)

# Broad input sanity ceilings only; these are not ADNEX cohort limits or
# clinical decision thresholds. Values outside them are not sent to the model.
ADNEX_MAX_AGE_YEARS = 130
ADNEX_MAX_CA125_U_ML = 1_000_000
ADNEX_MAX_LESION_DIAMETER_MM = 10_000

# Canonical tokens for the five IOTA cyst-content echogenicity descriptions.
IOTA_CYST_CONTENT_ECHOGENICITIES = frozenset(
    {"anechoic", "low_level", "ground_glass", "hemorrhagic", "mixed"}
)

IOTA_B_FEATURES = (
    "b1_unilocular_cyst",
    "b2_solid_component_lt_7mm",
    "b3_acoustic_shadows",
    "b4_smooth_multilocular_lt_100mm",
    "b5_no_detectable_blood_flow",
)
IOTA_M_FEATURES = (
    "m1_irregular_solid_tumor",
    "m2_ascites",
    "m3_four_or_more_papillary_projections",
    "m4_irregular_multilocular_solid_ge_100mm",
    "m5_very_strong_color_doppler",
)
IOTA_ASSESSMENT_FIELDS = (
    "assessment_source",
    "modality",
    "ultrasound_exam_complete",
)

REQUIRED_FIELDS = (
    "assessment_source",
    "modality",
    "ultrasound_exam_complete",
    "max_diameter_mm",
    "locules_count",
    "has_solid_component",
    "papillary_projections_count",
    "fluid_echogenicity",
    "acoustic_shadowing",
    "wall_irregular",
    "color_score",
    "has_ascites",
    "has_peritoneal_nodules",
)

VISION_FINDING_FIELDS = frozenset(
    REQUIRED_FIELDS
    + (
        "ortho_diameter_mm",
        "physiologic_lesion_type",
        "physiologic_morphology_confirmed",
        "classic_benign_lesion_type",
        "classic_benign_morphology_confirmed",
        "dermoid_features",
        "iota_simple_rules",
    )
)

DERMOID_CLASSIC_FEATURES = frozenset(
    {
        "hyperechoic_component_with_shadowing",
        "hyperechoic_lines_and_dots",
        "floating_echogenic_spheres",
    }
)


def _is_finite_measurement(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


class CDSSReasoningEngine:
    """Deterministic rules with explicit evidence boundaries."""

    version = "0.2.0-research"
    guideline_source = "IOTA Simple Rules + ACR O-RADS US v2022"

    def evaluate_case(
        self,
        vision_findings: dict[str, Any] | None = None,
        patient_context: dict[str, Any] | None = None,
        adnex_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        findings = vision_findings if isinstance(vision_findings, dict) else {}
        unknown_fields = sorted(set(findings) - VISION_FINDING_FIELDS, key=str)
        if unknown_fields:
            invalid_fields = [f"vision_findings.{field}" for field in unknown_fields]
            response = self._response(
                "UNSUPPORTED_PATTERN",
                "Mô tả siêu âm chứa trường không được hỗ trợ; chưa thể phân tầng.",
            )
            adnex_evaluation = self._adnex_not_evaluated(
                "ADNEX was not evaluated because vision findings contain unsupported fields.",
                invalid_fields=invalid_fields,
            )
            return self._with_adnex(response, adnex_evaluation)

        adnex_evaluation = self._evaluate_adnex(
            adnex_inputs, findings, patient_context
        )
        iota_evaluation = self._evaluate_iota(findings, patient_context)
        if iota_evaluation["malignant_features_present"]:
            return self._with_adnex(
                self._response(
                    "UNSUPPORTED_PATTERN",
                    "Có đặc điểm M do bác sĩ nhập; không đối chiếu thành nhãn O-RADS nguy cơ thấp. Cần bác sĩ rà soát các mô tả.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )
        if iota_evaluation["invalid_feature_inputs"]:
            return self._with_adnex(
                self._response(
                    "UNSUPPORTED_PATTERN",
                    "Mô tả IOTA có trường sai kiểu hoặc ngoài bộ quy tắc; chưa thể phân tầng O-RADS.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )
        if (
            findings.get("physiologic_lesion_type") is not None
            and findings.get("classic_benign_lesion_type") is not None
        ):
            return self._with_adnex(
                self._response(
                    "UNSUPPORTED_PATTERN",
                    "Mô tả đồng thời khai báo nhiều loại tổn thương đặc hiệu; cần bác sĩ rà soát lại.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )
        if findings.get("physiologic_lesion_type") is not None:
            return self._with_adnex(
                self._evaluate_physiologic_follicle(
                    findings, patient_context, iota_evaluation
                ),
                adnex_evaluation,
            )
        if findings.get("classic_benign_lesion_type") is not None:
            return self._with_adnex(
                self._evaluate_classic_dermoid(findings, iota_evaluation),
                adnex_evaluation,
            )
        missing = [key for key in REQUIRED_FIELDS if findings.get(key) is None]

        if missing:
            return self._with_adnex(
                self._response(
                    "INSUFFICIENT_DATA",
                    "Thiếu đặc điểm siêu âm do người đánh giá nhập; chưa thể phân tầng O-RADS.",
                    missing_fields=missing,
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )

        # None of the fields below are inferred from a mask, image filename,
        # pathology text, patient age, or a default Doppler color score.
        if (
            findings["assessment_source"] != "clinician"
            or findings["modality"] != "ultrasound_2d"
            or findings["ultrasound_exam_complete"] is not True
        ):
            return self._with_adnex(
                self._response(
                    "INSUFFICIENT_DATA",
                    "Cần đánh giá siêu âm 2D đầy đủ và mô tả hình thái do bác sĩ nhập.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )

        diameter = findings["max_diameter_mm"]
        if type(diameter) not in (float, int) or not 30 < diameter <= 100:
            return self._with_adnex(
                self._response(
                    "UNSUPPORTED_PATTERN",
                    "Kích thước nằm ngoài quy tắc nang đơn giản 3–10 cm đã triển khai.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )

        simple_cyst = (
            type(findings["locules_count"]) is int
            and findings["locules_count"] == 1
            and findings["has_solid_component"] is False
            and type(findings["papillary_projections_count"]) is int
            and findings["papillary_projections_count"] == 0
            and findings["fluid_echogenicity"] == "anechoic"
            and findings["acoustic_shadowing"] is False
            and findings["wall_irregular"] is False
            and type(findings["color_score"]) is int
            and findings["color_score"] == 1
            and findings["has_ascites"] is False
            and findings["has_peritoneal_nodules"] is False
        )
        if not simple_cyst:
            return self._with_adnex(
                self._response(
                    "UNSUPPORTED_PATTERN",
                    "Bộ quy tắc hiện chỉ đối chiếu nang đơn giản 3–10 cm.",
                    iota_evaluation=iota_evaluation,
                ),
                adnex_evaluation,
            )

        return self._with_adnex(
            self._response(
                "RULE_MATCHED",
                "Nang đơn giản đơn thùy, thành nhẵn, 3–10 cm theo mô tả đã nhập.",
                category="O-RADS 2",
                iota_evaluation=iota_evaluation,
            ),
            adnex_evaluation,
        )

    @staticmethod
    def _evaluate_physiologic_follicle(
        findings: dict[str, Any],
        patient_context: dict[str, Any] | None,
        iota_evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        required = REQUIRED_FIELDS + ("physiologic_morphology_confirmed",)
        missing = [field for field in required if findings.get(field) is None]
        if not isinstance(patient_context, dict) or patient_context.get("is_premenopausal") is None:
            missing.append("patient_context.is_premenopausal")
        if missing:
            return CDSSReasoningEngine._response(
                "INSUFFICIENT_DATA",
                "Cần mô tả đầy đủ và xác nhận tình trạng tiền mãn kinh trước khi đối chiếu nang sinh lý.",
                missing_fields=missing,
                iota_evaluation=iota_evaluation,
            )

        if (
            findings["assessment_source"] != "clinician"
            or findings["modality"] != "ultrasound_2d"
            or findings["ultrasound_exam_complete"] is not True
        ):
            return CDSSReasoningEngine._response(
                "INSUFFICIENT_DATA",
                "Nang sinh lý chỉ được đối chiếu từ mô tả bác sĩ trên siêu âm 2D đầy đủ.",
                iota_evaluation=iota_evaluation,
            )

        diameter = findings["max_diameter_mm"]
        if (
            findings["physiologic_lesion_type"] != "follicle"
            or patient_context["is_premenopausal"] is not True
            or findings["physiologic_morphology_confirmed"] is not True
            or not _is_finite_measurement(diameter)
            or not 0 < diameter <= 30
        ):
            return CDSSReasoningEngine._response(
                "UNSUPPORTED_PATTERN",
                "Không đủ tiêu chí theo policy nghiên cứu project-follicle-lte30-v2 (0 < kích thước <= 30 mm). "
                "ACR US v2022 dùng ≤3 cm; ngoài phạm vi policy không đồng nghĩa bất thường hoặc ác tính.",
                iota_evaluation=iota_evaluation,
            )

        simple_follicle = (
            type(findings["locules_count"]) is int
            and findings["locules_count"] == 1
            and findings["has_solid_component"] is False
            and type(findings["papillary_projections_count"]) is int
            and findings["papillary_projections_count"] == 0
            and findings["fluid_echogenicity"] == "anechoic"
            and findings["acoustic_shadowing"] is False
            and findings["wall_irregular"] is False
            and type(findings["color_score"]) is int
            and findings["color_score"] == 1
            and findings["has_ascites"] is False
            and findings["has_peritoneal_nodules"] is False
        )
        if not simple_follicle:
            return CDSSReasoningEngine._response(
                "UNSUPPORTED_PATTERN",
                "Mô tả có đặc điểm không phù hợp với nang noãn sinh lý đã khai báo.",
                iota_evaluation=iota_evaluation,
            )

        return CDSSReasoningEngine._response(
            "RULE_MATCHED",
            "Bác sĩ đã xác nhận nang noãn sinh lý <=30 mm trên siêu âm 2D đầy đủ theo policy "
            "nghiên cứu project-follicle-lte30-v2; ACR US v2022 dùng ≤3 cm.",
            category="O-RADS 1",
            iota_evaluation=iota_evaluation,
        )

    @staticmethod
    def _evaluate_classic_dermoid(
        findings: dict[str, Any], iota_evaluation: dict[str, Any]
    ) -> dict[str, Any]:
        required = REQUIRED_FIELDS + (
            "classic_benign_morphology_confirmed",
            "dermoid_features",
        )
        missing = [field for field in required if findings.get(field) is None]
        if missing:
            return CDSSReasoningEngine._response(
                "INSUFFICIENT_DATA",
                "Cần đặc điểm siêu âm và xác nhận hình thái u bì điển hình từ bác sĩ.",
                missing_fields=missing,
                iota_evaluation=iota_evaluation,
            )

        if (
            findings["assessment_source"] != "clinician"
            or findings["modality"] != "ultrasound_2d"
            or findings["ultrasound_exam_complete"] is not True
        ):
            return CDSSReasoningEngine._response(
                "INSUFFICIENT_DATA",
                "Phân loại u bì điển hình yêu cầu siêu âm 2D đầy đủ do bác sĩ xác nhận.",
                iota_evaluation=iota_evaluation,
            )

        diameter = findings["max_diameter_mm"]
        features = findings["dermoid_features"]
        if (
            findings["classic_benign_lesion_type"] != "dermoid"
            or findings["classic_benign_morphology_confirmed"] is not True
            or not _is_finite_measurement(diameter)
            or diameter <= 0
            or type(findings["locules_count"]) is not int
            or findings["locules_count"] < 1
            or findings["locules_count"] > 3
            or type(findings["fluid_echogenicity"]) is not str
            or findings["fluid_echogenicity"] not in IOTA_CYST_CONTENT_ECHOGENICITIES
            or findings["has_solid_component"] is not False
            or type(findings["papillary_projections_count"]) is not int
            or findings["papillary_projections_count"] != 0
            or findings["wall_irregular"] is not False
            or type(findings["color_score"]) is not int
            or findings["color_score"] != 1
            or findings["has_ascites"] is not False
            or findings["has_peritoneal_nodules"] is not False
            or type(findings["acoustic_shadowing"]) is not bool
            or type(features) is not list
            or not features
            or any(type(feature) is not str or feature not in DERMOID_CLASSIC_FEATURES for feature in features)
            or len(features) != len(set(features))
            or (
                "hyperechoic_component_with_shadowing" in features
                and findings["acoustic_shadowing"] is not True
            )
        ):
            return CDSSReasoningEngine._response(
                "UNSUPPORTED_PATTERN",
                "Mô tả không đủ hoặc không điển hình cho u bì; bóng cản âm đơn lẻ không xác định O-RADS.",
                iota_evaluation=iota_evaluation,
            )

        category = "O-RADS 2" if diameter < 100 else "O-RADS 3"
        return CDSSReasoningEngine._response(
            "RULE_MATCHED",
            "Bác sĩ xác nhận hình thái u bì điển hình; phân loại theo ngưỡng kích thước ACR O-RADS US v2022.",
            category=category,
            iota_evaluation=iota_evaluation,
        )

    @staticmethod
    def _evaluate_iota(
        findings: dict[str, Any], patient_context: dict[str, Any] | None
    ) -> dict[str, Any]:
        result = {
            "rule_verdict": "NOT_EVALUATED",
            "framework": "IOTA Simple Rules",
            "eligibility_status": "NOT_APPLICABLE",
            "missing_fields": [],
            "benign_features_present": [],
            "malignant_features_present": [],
            "requires_clinician_confirmation": True,
            "interpretation": "Rule output only; not a histopathological diagnosis.",
        }
        result["invalid_feature_inputs"] = []
        if "iota_simple_rules" not in findings:
            return result
        descriptors = findings["iota_simple_rules"]
        if not isinstance(descriptors, dict):
            result["missing_fields"] = ["iota_simple_rules"]
            result["invalid_feature_inputs"] = ["iota_simple_rules"]
            return result

        all_features = IOTA_B_FEATURES + IOTA_M_FEATURES
        result["invalid_feature_inputs"] = [
            f"iota_simple_rules.{field}"
            for field, value in descriptors.items()
            if field not in all_features or type(value) is not bool
        ]

        result["eligibility_status"] = "NOT_CONFIRMED"
        invalid_assessment = [
            field
            for field in IOTA_ASSESSMENT_FIELDS
            if findings.get(field) is None
        ]
        if (
            invalid_assessment
            or findings.get("assessment_source") != "clinician"
            or findings.get("modality") != "ultrasound_2d"
            or findings.get("ultrasound_exam_complete") is not True
        ):
            result["missing_fields"] = invalid_assessment or [
                field
                for field, expected in (
                    ("assessment_source", "clinician"),
                    ("modality", "ultrasound_2d"),
                    ("ultrasound_exam_complete", True),
                )
                if findings.get(field) != expected
            ]
            return result

        # Preserve an explicit clinician M flag as a safety conflict even if
        # IOTA scope or the remaining feature set is incomplete.
        result["malignant_features_present"] = [
            field for field in IOTA_M_FEATURES if descriptors.get(field) is True
        ]

        conflicting_inputs = []
        explicit_boolean_pairs = (
            ("b3_acoustic_shadows", "acoustic_shadowing"),
            ("m2_ascites", "has_ascites"),
        )
        for rule_field, finding_field in explicit_boolean_pairs:
            rule_value = descriptors.get(rule_field)
            finding_value = findings.get(finding_field)
            if (
                type(rule_value) is bool
                and type(finding_value) is bool
                and rule_value is not finding_value
            ):
                conflicting_inputs.append(
                    f"iota_simple_rules.{rule_field} conflicts with vision_findings.{finding_field}"
                )

        papillary_count = findings.get("papillary_projections_count")
        m3_value = descriptors.get("m3_four_or_more_papillary_projections")
        if (
            type(papillary_count) is int
            and papillary_count >= 0
            and type(m3_value) is bool
            and m3_value is not (papillary_count >= 4)
        ):
            conflicting_inputs.append(
                "iota_simple_rules.m3_four_or_more_papillary_projections conflicts "
                "with vision_findings.papillary_projections_count"
            )

        color_score = findings.get("color_score")
        if type(color_score) is int and color_score in (1, 2, 3, 4):
            for rule_field, expected in (
                ("b5_no_detectable_blood_flow", color_score == 1),
                ("m5_very_strong_color_doppler", color_score == 4),
            ):
                rule_value = descriptors.get(rule_field)
                if type(rule_value) is bool and rule_value is not expected:
                    conflicting_inputs.append(
                        f"iota_simple_rules.{rule_field} conflicts with vision_findings.color_score"
                    )

        if conflicting_inputs:
            result["invalid_feature_inputs"].extend(conflicting_inputs)
            return result

        eligibility_fields = (
            "is_persistent_adnexal_mass",
            "surgery_indicated",
        )
        if not isinstance(patient_context, dict):
            result["missing_fields"] = [
                f"patient_context.{field}" for field in eligibility_fields
            ]
            return result

        invalid_eligibility = [
            f"patient_context.{field}"
            for field in eligibility_fields
            if type(patient_context.get(field)) is not bool
        ]
        if invalid_eligibility:
            result["missing_fields"] = invalid_eligibility
            return result
        if not all(patient_context[field] for field in eligibility_fields):
            result["eligibility_status"] = "OUT_OF_SCOPE"
            return result
        result["eligibility_status"] = "ELIGIBLE"

        result["missing_fields"] = [
            f"iota_simple_rules.{field}"
            for field in all_features
            if type(descriptors.get(field)) is not bool
        ]
        if result["missing_fields"]:
            return result

        benign = [field for field in IOTA_B_FEATURES if descriptors[field] is True]
        malignant = result["malignant_features_present"]
        result["benign_features_present"] = benign
        if benign and not malignant:
            result["rule_verdict"] = "BENIGN"
        elif malignant and not benign:
            result["rule_verdict"] = "MALIGNANT"
        else:
            result["rule_verdict"] = "INCONCLUSIVE"
        return result

    @staticmethod
    def _with_adnex(
        response: dict[str, Any], adnex_evaluation: dict[str, Any]
    ) -> dict[str, Any]:
        response["adnex_evaluation"] = adnex_evaluation
        return response

    @staticmethod
    def _adnex_not_evaluated(
        reason: str,
        *,
        model_variant: str | None = None,
        missing_fields: list[str] | None = None,
        invalid_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "model": "IOTA ADNEX",
            "status": "NOT_EVALUATED",
            "reason": reason,
            "model_variant": model_variant,
            "eligibility_status": "NOT_CONFIRMED",
            "probabilities": None,
            "total_malignancy_probability": None,
            "missing_fields": missing_fields or [],
            "invalid_fields": invalid_fields or [],
            "requires_clinician_confirmation": True,
            "source_url": ADNEX_FORMULA_SOURCE,
        }

    @staticmethod
    def _evaluate_adnex(
        adnex_inputs: dict[str, Any] | None,
        vision_findings: dict[str, Any] | None = None,
        patient_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if adnex_inputs is None:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX inputs were not supplied; no probabilities were calculated."
            )
        if not isinstance(adnex_inputs, dict):
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX inputs must be an object; no probabilities were calculated."
            )
        conflicting_scope_fields = []
        if (
            isinstance(vision_findings, dict)
            and vision_findings.get("physiologic_lesion_type") is not None
        ):
            conflicting_scope_fields.append("vision_findings.physiologic_lesion_type")
        if isinstance(patient_context, dict):
            conflicting_scope_fields.extend(
                f"patient_context.{field}"
                for field in ("is_persistent_adnexal_mass", "surgery_indicated")
                if field in patient_context and patient_context[field] is not True
            )
        if conflicting_scope_fields:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX was not evaluated because other assessment fields conflict with its eligibility.",
            )

        conflicting_descriptors = []
        if isinstance(vision_findings, dict):
            shared_fields = {
                "assessment_source": "assessment_source",
                "modality": "modality",
                "ultrasound_exam_complete": "ultrasound_exam_complete",
                "max_diameter_mm": "max_lesion_diameter_mm",
                "locules_count": "cyst_locules_count",
                "papillary_projections_count": "papillary_projections_count",
                "acoustic_shadowing": "acoustic_shadowing",
                "has_ascites": "has_ascites",
            }
            for finding_field, adnex_field in shared_fields.items():
                if finding_field not in vision_findings:
                    continue
                value = vision_findings[finding_field]
                if finding_field in {"assessment_source", "modality"}:
                    valid_value = type(value) is str
                elif finding_field == "ultrasound_exam_complete":
                    valid_value = type(value) is bool
                elif finding_field == "max_diameter_mm":
                    valid_value = _is_finite_measurement(value) and value > 0
                elif finding_field == "locules_count":
                    valid_value = type(value) is int and value >= 1
                elif finding_field == "papillary_projections_count":
                    valid_value = type(value) is int and value >= 0
                else:
                    valid_value = type(value) is bool
                if not valid_value or value != adnex_inputs.get(adnex_field):
                    conflicting_descriptors.extend(
                        (
                            f"vision_findings.{finding_field}",
                            f"adnex_inputs.{adnex_field}",
                        )
                    )

            solid_component = adnex_inputs.get("largest_solid_component_mm")
            has_solid_component = vision_findings.get("has_solid_component")
            if "has_solid_component" in vision_findings and (
                type(has_solid_component) is not bool
                or (
                    _is_finite_measurement(solid_component)
                    and (
                        (has_solid_component and solid_component == 0)
                        or (not has_solid_component and solid_component > 0)
                    )
                )
            ):
                conflicting_descriptors.extend(
                    (
                        "vision_findings.has_solid_component",
                        "adnex_inputs.largest_solid_component_mm",
                    )
                )

        if conflicting_descriptors:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX was not evaluated because lesion descriptors conflict across the same assessment.",
                invalid_fields=sorted(set(conflicting_descriptors)),
            )

        allowed_fields = {
            "model_variant",
            "age_years",
            "ca125_u_ml",
            "is_oncology_center",
            "is_persistent_adnexal_mass",
            "surgery_indicated",
            "assessment_source",
            "modality",
            "ultrasound_exam_complete",
            "max_lesion_diameter_mm",
            "largest_solid_component_mm",
            "cyst_locules_count",
            "papillary_projections_count",
            "acoustic_shadowing",
            "has_ascites",
            "physiologic_follicle_confirmed",
        }
        unknown_fields = sorted(
            set(adnex_inputs) - allowed_fields, key=lambda field: str(field)
        )
        if unknown_fields:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX input contains unknown predictors.",
                invalid_fields=[str(field) for field in unknown_fields],
            )

        model_variant = adnex_inputs.get("model_variant")
        if model_variant is not None and (
            type(model_variant) is not str
            or model_variant not in {"WITH_CA125", "WITHOUT_CA125"}
        ):
            return CDSSReasoningEngine._adnex_not_evaluated(
                "Select one of the published ADNEX variants explicitly.",
                invalid_fields=["model_variant"],
            )

        required_fields = {
            "model_variant",
            "age_years",
            "is_oncology_center",
            "is_persistent_adnexal_mass",
            "surgery_indicated",
            "assessment_source",
            "modality",
            "ultrasound_exam_complete",
            "max_lesion_diameter_mm",
            "largest_solid_component_mm",
            "cyst_locules_count",
            "papillary_projections_count",
            "acoustic_shadowing",
            "has_ascites",
            "physiologic_follicle_confirmed",
        }
        if model_variant == "WITH_CA125":
            required_fields.add("ca125_u_ml")
        missing_fields = sorted(
            field
            for field in required_fields
            if field not in adnex_inputs or adnex_inputs[field] is None
        )
        if missing_fields:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "Required clinician-entered ADNEX predictors or eligibility fields are missing.",
                model_variant=model_variant,
                missing_fields=missing_fields,
            )

        numeric_fields = [
            "age_years",
            "max_lesion_diameter_mm",
            "largest_solid_component_mm",
        ]
        if model_variant == "WITH_CA125":
            numeric_fields.append("ca125_u_ml")
        invalid_fields = [
            field
            for field in numeric_fields
            if not _is_finite_measurement(adnex_inputs[field])
        ]
        boolean_fields = (
            "is_oncology_center",
            "is_persistent_adnexal_mass",
            "surgery_indicated",
            "ultrasound_exam_complete",
            "acoustic_shadowing",
            "has_ascites",
            "physiologic_follicle_confirmed",
        )
        invalid_fields.extend(
            field for field in boolean_fields if type(adnex_inputs[field]) is not bool
        )
        count_fields = ("cyst_locules_count", "papillary_projections_count")
        invalid_fields.extend(
            field
            for field in count_fields
            if type(adnex_inputs[field]) is not int or adnex_inputs[field] < 0
        )
        if type(adnex_inputs["assessment_source"]) is not str:
            invalid_fields.append("assessment_source")
        if type(adnex_inputs["modality"]) is not str:
            invalid_fields.append("modality")

        if model_variant == "WITHOUT_CA125" and adnex_inputs.get("ca125_u_ml") is not None:
            invalid_fields.append("ca125_u_ml")

        if invalid_fields:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "One or more ADNEX inputs have an invalid type or value.",
                model_variant=model_variant,
                invalid_fields=sorted(set(invalid_fields)),
            )

        age = float(adnex_inputs["age_years"])
        diameter = float(adnex_inputs["max_lesion_diameter_mm"])
        solid_component = float(adnex_inputs["largest_solid_component_mm"])
        ca125 = (
            float(adnex_inputs["ca125_u_ml"])
            if model_variant == "WITH_CA125"
            else None
        )
        invalid_fields = []
        if not 0 <= age <= ADNEX_MAX_AGE_YEARS:
            invalid_fields.append("age_years")
        if not 0 < diameter <= ADNEX_MAX_LESION_DIAMETER_MM:
            invalid_fields.append("max_lesion_diameter_mm")
        if not 0 <= solid_component <= diameter:
            invalid_fields.append("largest_solid_component_mm")
        if ca125 is not None and not 0 < ca125 <= ADNEX_MAX_CA125_U_ML:
            invalid_fields.append("ca125_u_ml")
        if invalid_fields:
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX values are outside the finite input sanity limits.",
                model_variant=model_variant,
                invalid_fields=invalid_fields,
            )

        if (
            adnex_inputs["is_persistent_adnexal_mass"] is not True
            or adnex_inputs["surgery_indicated"] is not True
            or adnex_inputs["ultrasound_exam_complete"] is not True
            or adnex_inputs["assessment_source"] != "clinician"
            or adnex_inputs["modality"] != "ultrasound_2d"
            or adnex_inputs["physiologic_follicle_confirmed"] is True
        ):
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX requires a complete clinician-entered 2D ultrasound for a persistent mass considered to require surgery; confirmed physiologic follicles are outside this model scope.",
                model_variant=model_variant,
            )

        solid_proportion = solid_component / diameter
        locules_over_ten = int(adnex_inputs["cyst_locules_count"] > 10)
        papillary_projection_category = min(
            adnex_inputs["papillary_projections_count"], 4
        )
        shadowing = int(adnex_inputs["acoustic_shadowing"])
        ascites = int(adnex_inputs["has_ascites"])
        oncology_center = int(adnex_inputs["is_oncology_center"])

        if model_variant == "WITH_CA125":
            predictors = (
                age,
                math.log2(ca125),
                math.log2(diameter),
                solid_proportion,
                solid_proportion * solid_proportion,
                locules_over_ten,
                papillary_projection_category,
                shadowing,
                ascites,
                oncology_center,
            )
            coefficients = ADNEX_WITH_CA125_COEFFICIENTS
        else:
            predictors = (
                age,
                math.log2(diameter),
                solid_proportion,
                solid_proportion * solid_proportion,
                locules_over_ten,
                papillary_projection_category,
                shadowing,
                ascites,
                oncology_center,
            )
            coefficients = ADNEX_WITHOUT_CA125_COEFFICIENTS

        try:
            logits = [
                math.fsum(
                    (coefficient[0],)
                    + tuple(
                        coefficient_value * predictor
                        for coefficient_value, predictor in zip(
                            coefficient[1:], predictors, strict=True
                        )
                    )
                )
                for coefficient in coefficients
            ]
            if not all(math.isfinite(logit) for logit in logits):
                raise ValueError("non-finite ADNEX linear predictor")
            maximum_logit = max(0.0, *logits)
            weights = [math.exp(-maximum_logit)] + [
                math.exp(logit - maximum_logit) for logit in logits
            ]
            denominator = math.fsum(weights)
            probability_values = [weight / denominator for weight in weights]
        except (OverflowError, ValueError):
            return CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX could not produce finite probabilities from these inputs.",
                model_variant=model_variant,
            )

        probabilities = dict(zip(ADNEX_PROBABILITY_KEYS, probability_values, strict=True))
        total_malignancy_probability = math.fsum(probability_values[1:])
        return {
            "model": "IOTA ADNEX",
            "status": "EVALUATED_RUO",
            "reason": "Research-use-only probabilities; no diagnosis, risk category, or management recommendation is produced.",
            "model_variant": model_variant,
            "eligibility_status": "ELIGIBLE",
            "probabilities": probabilities,
            "total_malignancy_probability": total_malignancy_probability,
            "requires_clinician_confirmation": True,
            "source_url": ADNEX_FORMULA_SOURCE,
        }

    @staticmethod
    def _response(
        status: str,
        reason: str,
        *,
        category: str | None = None,
        missing_fields: list[str] | None = None,
        iota_evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "status": status,
            "ruleset_version": "2022.1",
            "orads_stratification": {
                "category": category,
                "reason": reason,
                "missing_fields": missing_fields or [],
                "requires_clinician_confirmation": True,
                "clinical_management": None,
            },
            "iota_evaluation": iota_evaluation or {
                "rule_verdict": "NOT_EVALUATED",
                "framework": "IOTA Simple Rules",
                "eligibility_status": "NOT_APPLICABLE",
                "missing_fields": [],
                "benign_features_present": [],
                "malignant_features_present": [],
                "invalid_feature_inputs": [],
                "requires_clinician_confirmation": True,
                "interpretation": "Rule output only; not a histopathological diagnosis.",
            },
            "adnex_evaluation": CDSSReasoningEngine._adnex_not_evaluated(
                "ADNEX inputs were not supplied; no probabilities were calculated."
            ),
            "uncertainty_evaluation": {
                "level": "UNKNOWN",
                "confidence_score": None,
                "reason": "Bộ quy tắc chưa được kiểm định lâm sàng.",
            },
            "measurements_summary": {},
            "implementation_policy": dict(PHYSIOLOGIC_FOLLICLE_POLICY),
            "citations": [
                {
                    "title": "ACR O-RADS US v2022 Assessment Categories",
                    "url": ACR_ASSESSMENT_CATEGORIES,
                    "verification_status": "[VERIFIED]",
                },
                {
                    "title": "IOTA Simple Rules prospective validation",
                    "url": IOTA_SIMPLE_RULES_SOURCE,
                    "verification_status": "[VERIFIED]",
                },
                {
                    "title": "Updated IOTA terms, definitions and measurements (2026)",
                    "url": IOTA_TERMS_SOURCE,
                    "verification_status": "[VERIFIED]",
                },
                {
                    "title": "IOTA ADNEX Risk Model scope and predictors",
                    "url": "https://iotaplus.org/en/adnex-risk-model",
                    "verification_status": "[VERIFIED]",
                },
                {
                    "title": "Original IOTA ADNEX prospective multicentre study",
                    "url": "https://www.bmj.com/content/349/bmj.g5920",
                    "verification_status": "[VERIFIED]",
                },
                {
                    "title": "IOTA ADNEX formula coefficients, supplement S1 (BMJ Medicine 2024)",
                    "url": ADNEX_FORMULA_SOURCE,
                    "verification_status": "[VERIFIED]",
                },
            ],
            "evidence_status": "UNVALIDATED_RESEARCH_PROTOTYPE",
        }
