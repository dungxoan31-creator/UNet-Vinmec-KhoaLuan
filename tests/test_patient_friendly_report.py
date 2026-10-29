from backend.services.report_generator import (
    build_patient_friendly_report_text,
    build_patient_friendly_summary,
    build_structured_findings_report,
)


def test_patient_summary_is_neutral_and_never_uses_case_findings():
    adversarial_findings = {
        "side": "left",
        "has_lesion": True,
        "lesion": {"present": True, "longest_diameter_mm": 18.5},
        "follicles": {"count": 8},
        "ai_diagnosis": {
            "model_validation_status": "CLINICALLY_VALIDATED",
            "orads_suggested": {"category": "O-RADS 1"},
            "malignancy_risk": {"prob_malignant": 0.78},
            "lesion_type": {"label": "dermoid_cyst", "label_vi": "U bì"},
        },
    }

    summary = build_patient_friendly_summary(adversarial_findings)
    report = build_patient_friendly_report_text(adversarial_findings)

    assert summary["status_color"] == "GRAY"
    assert summary["lifestyle_advice"] == []
    assert "không tạo giải thích" in summary["explanation"].lower()
    assert "RUO" in summary["disclaimer"]
    assert "18.5" not in report
    assert "78%" not in report
    assert "O-RADS" not in report
    assert "lành tính" not in report.lower()
    assert "tái khám" not in report.lower()
    assert "chăm sóc bệnh nhân" in report.lower()


def test_untrusted_validation_flag_cannot_unlock_diagnosis_or_malignancy_claims():
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "ai_diagnosis": {
            "model_validation_status": "CLINICALLY_VALIDATED",
            "lesion_type": {"label": "dermoid", "label_vi": "U bì", "prob": 0.99},
            "malignancy_risk": {"prob_malignant": 0.78},
            "orads_suggested": {"category": "O-RADS 5", "complete": True},
        },
    })

    assert "không phát hành kết luận chẩn đoán" in report.lower()
    assert "99%" not in report
    assert "78%" not in report
    assert "Nguy cơ ác tính ước lượng" not in report
