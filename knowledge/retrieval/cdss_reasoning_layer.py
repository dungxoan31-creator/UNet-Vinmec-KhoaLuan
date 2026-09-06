"""
Clinical Decision Support Reasoning Layer.
Connects Computer Vision image findings + Clinical patient context -> Evidence-based interpretation,
IOTA rules, O-RADS risk stratification, uncertainty boundaries, and guideline citations.
"""

from typing import Any, Dict, Optional, List

from knowledge.retrieval.medical_knowledge_retriever import MedicalKnowledgeRetriever


class CDSSReasoningEngine:
    def __init__(self, retriever: Optional[MedicalKnowledgeRetriever] = None):
        self.retriever = retriever or MedicalKnowledgeRetriever()

    def evaluate_case(
        self,
        vision_findings: Dict[str, Any],
        patient_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes structured imaging findings into evidence-supported clinical reasoning.
        """
        patient_context = patient_context or {}
        patient_age = patient_context.get("age", 35)
        is_postmenopausal = patient_context.get("is_postmenopausal", patient_age >= 50)
        is_incomplete = vision_findings.get("is_incomplete", False) or vision_findings.get("quality_score", 1.0) < 0.3

        # 1. Extract geometric and morphological parameters
        dmax_mm = vision_findings.get("max_diameter_mm", 0.0)
        dorth_mm = vision_findings.get("ortho_diameter_mm", 0.0)
        d3_mm = vision_findings.get("d3_mm", (dmax_mm + dorth_mm) / 2.0 if dmax_mm > 0 else 0.0)
        volume_ml = vision_findings.get("volume_ml", 0.523 * (dmax_mm / 10.0) * (dorth_mm / 10.0) * (d3_mm / 10.0))

        has_solid = vision_findings.get("has_solid_component", False)
        max_solid_mm = vision_findings.get("max_solid_diameter_mm", 0.0)
        papillary_count = vision_findings.get("papillary_projections_count", 0)
        has_shadowing = vision_findings.get("acoustic_shadowing", False)
        fluid_type = vision_findings.get("fluid_echogenicity", "anechoic")  # anechoic, ground_glass, mixed, reticular
        locules_count = vision_findings.get("locules_count", 1)  # 1: unilocular, >1: multilocular
        color_score = vision_findings.get("color_score", 1)  # 1 to 4
        has_ascites = vision_findings.get("has_ascites", False)
        contour = vision_findings.get("contour", "smooth")  # smooth, irregular

        conflict_reconciliations = []

        # 2. IOTA Simple Rules Evaluation
        b_rules_met = []
        m_rules_met = []

        # B-rules
        if locules_count == 1 and not has_solid and papillary_count == 0:
            b_rules_met.append("B1: Unilocular cyst")
        if has_solid and max_solid_mm > 0 and max_solid_mm < 7.0:
            b_rules_met.append("B2: Small solid component (< 7mm)")
        if has_shadowing:
            b_rules_met.append("B3: Presence of acoustic shadows")
        if locules_count > 1 and not has_solid and dmax_mm < 100.0:
            b_rules_met.append("B4: Smooth multilocular cyst (< 100mm)")
        if color_score == 1:
            b_rules_met.append("B5: Avascular (Color Score 1)")

        # M-rules
        if (has_solid or contour == "irregular") and not has_shadowing and dmax_mm >= 30.0 and color_score >= 3:
            m_rules_met.append("M1: Irregular solid tumor")
        if has_ascites:
            m_rules_met.append("M2: Presence of ascites")
        if papillary_count >= 4:
            m_rules_met.append("M3: ≥ 4 papillary projections")
        if locules_count > 1 and (has_solid or contour == "irregular") and dmax_mm >= 100.0:
            m_rules_met.append("M4: Irregular multilocular-solid tumor (≥ 100mm)")
        if color_score == 4:
            m_rules_met.append("M5: Very strong blood flow (Color Score 4)")

        if len(b_rules_met) > 0 and len(m_rules_met) == 0:
            iota_verdict = "BENIGN (Satisfies IOTA B-Rules)"
        elif len(m_rules_met) > 0 and len(b_rules_met) == 0:
            iota_verdict = "MALIGNANT (Satisfies IOTA M-Rules)"
        else:
            iota_verdict = "INCONCLUSIVE (Requires ADNEX / Expert Evaluation)"

        # 3. O-RADS Risk Stratification Evaluation
        if is_incomplete:
            orads_code = "O-RADS 0"
            orads_name = "Incomplete Evaluation"
            malignancy_risk = "N/A"
            management = "Repeat ultrasound or perform pelvic MRI due to technical limitations."
        elif dmax_mm == 0:
            orads_code = "O-RADS 1"
            orads_name = "Normal Physiological Ovary"
            malignancy_risk = "0.0%"
            management = "No follow-up required."
        elif has_solid or papillary_count > 0:
            # Check solid component rules
            if has_shadowing and contour == "smooth" and color_score <= 2 and not has_ascites:
                # KC-003 Conflict Synergy: Solid mass with smooth contour & shadowing -> O-RADS 3
                orads_code = "O-RADS 3"
                orads_name = "Solid Mass with Smooth Contour and Shadowing (Low Risk)"
                malignancy_risk = "1% to < 10%"
                management = "Gynecologist evaluation; pelvic MRI or elective surgical resection."
                conflict_reconciliations.append({
                    "conflict_id": "KC-003",
                    "topic": "Solid Lesions with Acoustic Shadowing",
                    "expected_orads": "O-RADS 3 (Low Risk)",
                    "expected_iota": "Rule B3 (Acoustic Shadows -> Benign)",
                    "resolution": "O-RADS 3 (Low Risk) and IOTA B3 synergy applied for ovarian fibroma/thecoma spectrum."
                })
            elif max_solid_mm > 0 and max_solid_mm < 7.0 and not has_shadowing:
                # KC-001 Conflict: IOTA B2 (< 7mm) vs O-RADS 4 (≥ 3mm)
                orads_code = "O-RADS 4"
                orads_name = "Intermediate Risk of Malignancy (Solid component ≥ 3mm)"
                malignancy_risk = "10% to < 50%"
                management = "Referral to Gynecologic Oncologist; Pelvic MRI with contrast."
                conflict_reconciliations.append({
                    "conflict_id": "KC-001",
                    "topic": "Solid Component Definition & Cutoff for Benignity",
                    "expected_iota": "Rule B2 (Solid component < 7mm)",
                    "expected_orads": "O-RADS 4 (Solid component ≥ 3mm)",
                    "resolution": "O-RADS US v2022 takes precedence for risk stratification (O-RADS 4)."
                })
            elif (
                papillary_count >= 4 or color_score == 4 or has_ascites or (has_solid and dmax_mm >= 80 and color_score >= 3)
            ):
                orads_code = "O-RADS 5"
                orads_name = "High Risk of Malignancy"
                malignancy_risk = "≥ 50%"
                management = "Urgent referral to Gynecologic Oncologist; Staging CT and multidisciplinary surgical planning."
            else:
                orads_code = "O-RADS 4"
                orads_name = "Intermediate Risk of Malignancy"
                malignancy_risk = "10% to < 50%"
                management = "Referral to Gynecologic Oncologist; Pelvic MRI with contrast."
        elif locules_count == 1 and papillary_count == 0:
            if fluid_type == "anechoic":
                if (not is_postmenopausal and dmax_mm <= 100.0) or (is_postmenopausal and dmax_mm <= 50.0):
                    orads_code = "O-RADS 2"
                    orads_name = "Almost Certainly Benign"
                    malignancy_risk = "< 1%"
                    management = "Routine follow-up in 12 months or no follow-up if < 50mm."
                else:
                    orads_code = "O-RADS 3"
                    orads_name = "Low Risk of Malignancy"
                    malignancy_risk = "1% to < 10%"
                    management = "Ultrasound follow-up in 6-12 months or general gynecologist evaluation."
            elif fluid_type in ["ground_glass", "endometrioma"] and dmax_mm < 100.0:
                orads_code = "O-RADS 2"
                orads_name = "Classic Endometrioma (Almost Certainly Benign)"
                malignancy_risk = "< 1%"
                management = "Management per symptom severity; annual follow-up."
            elif (has_shadowing or fluid_type in ["dermoid", "mixed"]) and dmax_mm < 100.0:
                orads_code = "O-RADS 2"
                orads_name = "Classic Dermoid Teratoma (Almost Certainly Benign)"
                malignancy_risk = "< 1%"
                management = "Annual ultrasound or elective cystectomy if symptomatic."
            elif fluid_type == "reticular" and not is_postmenopausal and dmax_mm < 100.0:
                orads_code = "O-RADS 2"
                orads_name = "Classic Hemorrhagic Cyst (Almost Certainly Benign)"
                malignancy_risk = "< 1%"
                management = "Follow-up ultrasound in 6-12 weeks."
            else:
                orads_code = "O-RADS 3"
                orads_name = "Low Risk of Malignancy"
                malignancy_risk = "1% to < 10%"
                management = "Gynecologist consult."
        elif locules_count > 1:
            if dmax_mm < 100.0 and color_score <= 3:
                orads_code = "O-RADS 3"
                orads_name = "Smooth Multilocular Cyst (Low Risk)"
                malignancy_risk = "1% to < 10%"
                management = "Management by gynecologist; follow-up ultrasound in 3-6 months."
            else:
                # KC-002 Conflict: Smooth multilocular cyst ≥ 10cm upgraded to O-RADS 4 per ACR v2022
                orads_code = "O-RADS 4"
                orads_name = "Large Multilocular Cyst ≥ 100mm (Intermediate Risk)"
                malignancy_risk = "10% to < 50%"
                management = "Gynecologist or Gynecologic Oncologist consultation; pelvic MRI."
                conflict_reconciliations.append({
                    "conflict_id": "KC-002",
                    "topic": "Multilocular Cyst Size Cutoff (< 10cm vs ≥ 10cm)",
                    "expected_iota": "Rule B4 (Smooth multilocular < 100mm)",
                    "expected_orads": "O-RADS 4 (Smooth multilocular ≥ 10cm)",
                    "resolution": "Categorized as O-RADS 4 per ACR due to risk of large mucinous neoplasms."
                })
        else:
            orads_code = "O-RADS 3"
            orads_name = "Low Risk of Malignancy"
            malignancy_risk = "1% to < 10%"
            management = "Gynecologist evaluation."

        # 4. Uncertainty & Insufficient Data Warnings
        clinical_alerts = []
        is_uncertain = False
        if dmax_mm > 0 and dmax_mm < 15.0:
            clinical_alerts.append(
                "Kích thước tổn thương nhỏ (< 15mm) có thể là nang sinh lý tồn tại ngắn hạn; nên siêu âm kiểm tra lại sau sạch kinh 3-5 ngày."
            )
        if has_solid and color_score == 1 and not has_shadowing:
            clinical_alerts.append(
                "Phát hiện thành phần dạng đặc nhưng không có dòng chảy mạch máu (Color Score 1) — Cần phân biệt cục máu đông thoái hóa (clot) hoặc cặn mucin đặc."
            )
            is_uncertain = True
        if dmax_mm >= 100.0 and locules_count > 1:
            clinical_alerts.append(
                "Khối u đa thùy kích thước lớn (≥ 10cm) — Cần loại trừ u tuyến nhầy giáp biên (Mucinous Borderline Tumor)."
            )

        # 5. Citations & Provenance
        citations = [
            "SRC-ACR-ORADS-US-2022",
            "SRC-IOTA-CONSENSUS-2026",
            "SRC-IOTA-SIMPLE-RULES-2016",
            "SRC-ESGO-ISUOG-IOTA-ESGE-2021",
        ]

        return {
            "measurements_summary": {
                "dmax_mm": dmax_mm,
                "dorth_mm": dorth_mm,
                "d3_mm": d3_mm,
                "volume_ml": round(volume_ml, 2),
            },
            "iota_evaluation": {
                "verdict": iota_verdict,
                "b_rules_met": b_rules_met,
                "m_rules_met": m_rules_met,
                "citation": "SRC-IOTA-SIMPLE-RULES-2016",
            },
            "orads_stratification": {
                "category_code": orads_code,
                "category_name": orads_name,
                "malignancy_risk": malignancy_risk,
                "management_recommendation": management,
                "citation": "SRC-ACR-ORADS-US-2022",
            },
            "uncertainty_evaluation": {
                "is_uncertain": is_uncertain,
                "clinical_alerts": clinical_alerts,
            },
            "conflict_reconciliations": conflict_reconciliations,
            "citations": citations,
            "evidence_status": "EVIDENCE_SUPPORTED_TIER_1",
        }

