"""Conservative research-only O-RADS US v2022 rule probe.

The segmentation model supplies only a binary lesion mask. It cannot observe
the morphology or Doppler descriptors needed for O-RADS or IOTA. This engine
therefore accepts clinician-entered descriptors and matches one narrow ACR
rule; all other requests remain unclassified. It has no clinical validation.
"""

from typing import Any

ACR_ASSESSMENT_CATEGORIES = (
    "https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/"
    "O-RADS--US-v2022-Assessment-Categories.pdf"
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
    "wall_irregular",
    "color_score",
    "has_ascites",
    "has_peritoneal_nodules",
)


class CDSSReasoningEngine:
    """Deterministic rules with explicit evidence boundaries."""

    version = "0.1.0-research"
    guideline_source = "ACR O-RADS US v2022"

    def evaluate_case(
        self,
        vision_findings: dict[str, Any] | None = None,
        patient_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        findings = vision_findings or {}
        missing = [key for key in REQUIRED_FIELDS if findings.get(key) is None]

        if missing:
            return self._response(
                "INSUFFICIENT_DATA",
                "Thiếu đặc điểm siêu âm do người đánh giá nhập; chưa thể phân tầng O-RADS.",
                missing_fields=missing,
            )

        # None of the fields below are inferred from a mask, image filename,
        # pathology text, patient age, or a default Doppler color score.
        if (
            findings["assessment_source"] != "clinician"
            or findings["modality"] != "ultrasound_2d"
            or findings["ultrasound_exam_complete"] is not True
        ):
            return self._response(
                "INSUFFICIENT_DATA",
                "Cần đánh giá siêu âm 2D đầy đủ và mô tả hình thái do bác sĩ nhập.",
            )

        diameter = findings["max_diameter_mm"]
        if type(diameter) not in (float, int) or not 30 < diameter < 100:
            return self._response(
                "UNSUPPORTED_PATTERN",
                "Kích thước nằm ngoài quy tắc nang đơn giản 3–10 cm đã triển khai.",
            )

        simple_cyst = (
            type(findings["locules_count"]) is int
            and findings["locules_count"] == 1
            and findings["has_solid_component"] is False
            and type(findings["papillary_projections_count"]) is int
            and findings["papillary_projections_count"] == 0
            and findings["fluid_echogenicity"] == "anechoic"
            and findings["wall_irregular"] is False
            and type(findings["color_score"]) is int
            and findings["color_score"] == 1
            and findings["has_ascites"] is False
            and findings["has_peritoneal_nodules"] is False
        )
        if not simple_cyst:
            return self._response(
                "UNSUPPORTED_PATTERN",
                "Bộ quy tắc hiện chỉ đối chiếu nang đơn giản 3–10 cm.",
            )

        return self._response(
            "RULE_MATCHED",
            "Nang đơn giản đơn thùy, thành nhẵn, 3–10 cm theo mô tả đã nhập.",
            category="O-RADS 2",
        )

    @staticmethod
    def _response(
        status: str,
        reason: str,
        *,
        category: str | None = None,
        missing_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "status": status,
            "orads_stratification": {
                "category": category,
                "reason": reason,
                "missing_fields": missing_fields or [],
                "requires_clinician_confirmation": True,
                "clinical_management": None,
            },
            "iota_evaluation": {"rule_verdict": "NOT_EVALUATED"},
            "uncertainty_evaluation": {
                "level": "UNKNOWN",
                "confidence_score": None,
                "reason": "Bộ quy tắc chưa được kiểm định lâm sàng.",
            },
            "measurements_summary": {},
            "citations": [
                {
                    "title": "ACR O-RADS US v2022 Assessment Categories Algorithm",
                    "url": ACR_ASSESSMENT_CATEGORIES,
                    "verification_status": "[VERIFIED]",
                }
            ],
            "evidence_status": "UNVALIDATED_RESEARCH_PROTOTYPE",
        }
