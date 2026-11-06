"""
Research-only suggestions for common ultrasound descriptions.
No template constitutes a confirmed examination or management recommendation.
"""

from typing import Any

from backend.services.cdss_engine import CDSSReasoningEngine

CLINICAL_MACRO_TEMPLATES: dict[str, dict[str, Any]] = {
    "PHYSIOLOGIC_FOLLICLE": {
        "id": "PHYSIOLOGIC_FOLLICLE",
        "label": "Nang noãn sinh lý (<30 mm)",
        "badge": "Mẫu tham khảo RUO",
        "description": "Nang noãn buồng trứng sinh lý bình thường <30 mm, dịch trống âm, thành mỏng nhẵn.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
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
            "physiologic_morphology_confirmed": None,
        },
        "default_diameter_mm": None,
        "recommendation": None,
    },
    "HEMORRHAGIC_CYST": {
        "id": "HEMORRHAGIC_CYST",
        "label": "Nang hoàng thể xuất huyết",
        "badge": "Mẫu tham khảo RUO",
        "description": "Nang cơ năng có phản âm dạng lưới mạng nhện / sợi fibrin thoái triển.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
            "locules_count": 1,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "mixed",
            "acoustic_shadowing": False,
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
            "classic_benign_lesion_type": "hemorrhagic",
            "classic_benign_morphology_confirmed": None,
        },
        "default_diameter_mm": None,
        "recommendation": None,
    },
    "CLASSIC_DERMOID": {
        "id": "CLASSIC_DERMOID",
        "label": "U bì / U quái điển hình",
        "badge": "Mẫu tham khảo RUO",
        "description": "U bì buồng trứng trưởng thành lành tính có bóng cản âm / nốt tăng âm Rokitansky.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
            "locules_count": 1,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "hyperechoic_strands",
            "acoustic_shadowing": True,
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
            "classic_benign_lesion_type": "dermoid",
            "classic_benign_morphology_confirmed": None,
            "dermoid_features": ["hyperechoic_component_with_shadowing"],
        },
        "default_diameter_mm": None,
        "recommendation": None,
    },
    "ENDOMETRIOMA": {
        "id": "ENDOMETRIOMA",
        "label": "U lạc nội mạc tử cung",
        "badge": "Mẫu tham khảo RUO",
        "description": "Nang lạc nội mạc tử cung có dịch kính mờ đồng nhất, không có thành phần đặc.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
            "locules_count": 1,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "ground_glass",
            "acoustic_shadowing": False,
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
            "classic_benign_lesion_type": "endometrioma",
            "classic_benign_morphology_confirmed": None,
        },
        "default_diameter_mm": None,
        "recommendation": None,
    },
    "SIMPLE_CYST": {
        "id": "SIMPLE_CYST",
        "label": "Nang đơn thùy dịch trong (>30 mm)",
        "badge": "Mẫu tham khảo RUO",
        "description": "Nang đơn thùy dịch trống âm hoàn toàn, thành mỏng nhẵn, không vách, không bóng cản.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
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
        "default_diameter_mm": None,
        "recommendation": None,
    },
    "SMOOTH_MULTILOCULAR_BENIGN": {
        "id": "SMOOTH_MULTILOCULAR_BENIGN",
        "label": "U nang đa thùy trơn láng (<100 mm)",
        "badge": "Mẫu tham khảo RUO",
        "description": "U nang có nhiều vách ngăn trơn láng, không có thành phần đặc, kích thước dưới 100 mm.",
        "findings_template": {
            "assessment_source": None,
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": None,
            "locules_count": 2,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "fluid_echogenicity": "anechoic",
            "acoustic_shadowing": False,
            "wall_irregular": False,
            "color_score": 1,
            "has_ascites": False,
            "has_peritoneal_nodules": False,
        },
        "default_diameter_mm": None,
        "recommendation": None,
    },
}


def get_clinical_templates_list() -> list[dict[str, Any]]:
    """Trả về danh sách tóm tắt các Smart Macro Chips để hiển thị trên giao diện."""
    return [
        {
            "id": t["id"],
            "label": t["label"],
            "badge": "Mẫu tham khảo RUO",
            "description": t["description"],
            "recommendation": None,
            "default_diameter_mm": None,
        }
        for t in CLINICAL_MACRO_TEMPLATES.values()
    ]


def apply_clinical_template(
    template_id: str,
    max_diameter_mm: float | None = None,
    patient_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Trả mẫu gợi ý chưa xác nhận. Mẫu không tự xác lập quan sát lâm sàng,
    kích thước, tình trạng mãn kinh, phân tầng hoặc khuyến nghị xử trí.
    """
    if template_id not in CLINICAL_MACRO_TEMPLATES:
        raise ValueError(f"Không tìm thấy template với ID '{template_id}'.")

    template = CLINICAL_MACRO_TEMPLATES[template_id]
    findings = dict(template["findings_template"])

    # Suggested descriptors are not a clinician-confirmed examination.
    findings["assessment_source"] = None
    findings["ultrasound_exam_complete"] = None
    if "physiologic_morphology_confirmed" in findings:
        findings["physiologic_morphology_confirmed"] = None
    if "classic_benign_morphology_confirmed" in findings:
        findings["classic_benign_morphology_confirmed"] = None
    findings["max_diameter_mm"] = max_diameter_mm

    # Chạy CDSS suy luận ngay lập tức
    context = patient_context or {}
    cdss_engine = CDSSReasoningEngine()
    cdss_result = cdss_engine.evaluate_case(
        vision_findings=findings,
        patient_context=context,
    )

    return {
        "template_id": template_id,
        "label": template["label"],
        "badge": "Mẫu tham khảo RUO",
        "recommendation": None,
        "status": "UNCONFIRMED_PROPOSAL",
        "findings": findings,
        "cdss_result": cdss_result,
    }
