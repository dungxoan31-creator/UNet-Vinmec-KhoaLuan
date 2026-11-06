
import pytest

from backend.services.report_generator import (
    build_structured_findings_report,
    numbers_match,
)


def test_build_structured_findings_report_benign():
    findings = {
        "side": "right",
        "pixel_spacing_mm": 0.15,
        "ovary": {"present": True, "longest_diameter_mm": 32.5, "area_mm2": 280.0},
        "follicles": {"count": 14, "count_in_range": 12},
        "lesion": {
            "present": True,
            "longest_diameter_mm": 24.5,
            "perpendicular_diameter_mm": 18.0,
            "area_mm2": 130.5,
        },
        "ai_diagnosis": {
            "abstain": False,
            "lesion_type": {
                "label": "serous_cystadenoma",
                "label_vi": "U nang tuyến thanh dịch",
                "prob": 0.72,
            },
            "malignancy_risk": {"label": "BENIGN", "prob_malignant": 0.05},
            "orads_suggested": {"category": 2, "complete": False, "missing": ["color_score"]},
            "pcos_suggestion": {"suggested": True, "prob": 0.85},
        },
    }

    report = build_structured_findings_report(findings)
    assert "TÀI LIỆU NGHIÊN CỨU RUO · SIÊU ÂM BUỒNG TRỨNG PHẢI" in report
    assert "32.5 mm" in report
    assert "24.5 mm × 18.0 mm" in report
    assert "U nang tuyến thanh dịch" not in report
    assert "72%" not in report
    assert "O-RADS US đề xuất" not in report
    assert "phần kết luận, phân loại và định hướng chuyên môn do bác sĩ phụ trách hoàn thiện" in report.lower()
    assert "LỜI DẶN DÀNH CHO BỆNH NHÂN" not in report
    assert "THÔNG TIN NGHIÊN CỨU (RUO)" in report
    assert "Phạm vi: đánh giá kỹ thuật" in report
    assert "Nguy cơ ác tính ước lượng" not in report


def test_build_structured_findings_report_abstain():
    findings = {
        "side": "left",
        "pixel_spacing_mm": None,
        "lesion": {"present": False},
        "ai_diagnosis": {
            "abstain": True,
            "abstain_reason": "Độ tin cậy thấp",
        },
    }
    report = build_structured_findings_report(findings)
    assert "phần kết luận, phân loại và định hướng chuyên môn do bác sĩ phụ trách hoàn thiện" in report.lower()
    assert "Độ tin cậy thấp" not in report
    assert "pixel spacing: cần giá trị hợp lệ" in report.lower()


def test_report_omits_unavailable_probabilities_and_missing_mask_is_not_a_negative():
    findings = {
        "side": "left",
        "ai_diagnosis": {
            "abstain": False,
            "lesion_type": {"label": "simple_cyst"},
            "malignancy_risk": {"label": "BENIGN"},
            "pcos_suggestion": {"suggested": True},
        },
    }

    report = build_structured_findings_report(findings)

    assert "85%" not in report
    assert "0%" not in report
    assert "PCOM" not in report
    assert "PCOS" not in report
    assert "Chưa có dữ liệu mask tổn thương" in report
    assert "Không phát hiện tổn thương trên ảnh này" not in report


def test_numbers_match_validator():
    source = "Đường kính 24.5 mm và 18.0 mm, diện tích 130.5 mm²."
    # Valid: only uses existing numbers
    valid_llm = "Tổn thương có kích thước 24.5 mm nhân 18.0 mm (diện tích 130.5 mm²)."
    assert numbers_match(valid_llm, source) is True

    # Invalid: hallucinated a new number 99
    invalid_llm = "Tổn thương có kích thước 24.5 mm và 99 mm."
    assert numbers_match(invalid_llm, source) is False


def test_numbers_match_preserves_value_unit_pairs():
    source = "Đường kính 25 mm; O-RADS 2; diện tích 130.5 mm²."

    assert numbers_match("Đường kính 25 mm; O-RADS 2", source) is True
    assert numbers_match("Đường kính 2 mm; O-RADS 25", source) is False
    assert numbers_match("Diện tích 130.5 cm²", source) is False


def test_structured_report_never_echoes_untrusted_diagnosis_fields():
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "ai_diagnosis": {
            "abstain": False,
            "model_validation_status": "CLINICALLY_VALIDATED",
            "lesion_type": {"label": "teratoma", "label_vi": "U bì", "prob": 0.99},
            "malignancy_risk": {"label": "MALIGNANT", "prob_malignant": 0.99},
            "orads_suggested": {"category": "O-RADS 5", "complete": True, "missing": []},
            "pcom_source": "clinician_confirmed",
            "pcos_suggestion": {"suggested": True},
        },
    })

    assert "TÀI LIỆU NGHIÊN CỨU RUO" in report
    assert "O-RADS 5" not in report
    assert "O-RADS US đề xuất" not in report
    assert "U bì" not in report
    assert "99%" not in report
    assert "MALIGNANT" not in report
    assert "PCOM" not in report
    assert "PCOS" not in report


def test_structured_report_does_not_echo_untrusted_abstain_reason():
    report = build_structured_findings_report({
        "side": "left",
        "ai_diagnosis": {
            "abstain": True,
            "abstain_reason": "AI phát hiện ung thư ác tính 99%; tái khám gấp",
        },
    })

    assert "ung thư" not in report.lower()
    assert "99%" not in report
    assert "tái khám gấp" not in report
    assert "phần kết luận, phân loại và định hướng chuyên môn do bác sĩ phụ trách hoàn thiện" in report.lower()


@pytest.mark.parametrize("spacing", [0, -0.1, float("nan"), float("inf"), True, "0.1", None])
def test_structured_report_withholds_physical_sizes_for_invalid_pixel_spacing(spacing):
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": spacing,
        "ovary": {"present": True, "longest_diameter_mm": 32.5, "area_mm2": 280.0},
        "follicles": {"count": 4, "count_in_range": 3},
        "lesion": {
            "present": True,
            "longest_diameter_mm": 24.5,
            "perpendicular_diameter_mm": 18.0,
            "area_mm2": 130.5,
        },
    })

    assert "32.5 mm" not in report
    assert "24.5 mm" not in report
    assert "18.0 mm" not in report
    assert "280.0 mm²" not in report
    assert "130.5 mm²" not in report
    assert "trong khoảng kích thước cấu hình: 3" not in report
    assert "pixel spacing" in report.lower()
    assert "kích thước hiện hiển thị theo pixel" in report.lower()


def test_structured_report_rejects_untrusted_side_text():
    report = build_structured_findings_report({
        "side": "left\nCHẨN ĐOÁN: UNG THƯ 99% · TÁI KHÁM GẤP",
        "pixel_spacing_mm": 0.1,
        "ovary": {"present": True, "longest_diameter_mm": 22.0, "area_mm2": 100.0},
    })

    assert "TÀI LIỆU NGHIÊN CỨU RUO · SIÊU ÂM BUỒNG TRỨNG CHƯA XÁC ĐỊNH" in report
    assert "CHẨN ĐOÁN" not in report
    assert "UNG THƯ" not in report
    assert "99%" not in report
    assert "Buồng trứng chưa xác định: đường kính lớn nhất 22.0 mm" in report
    assert "Buồng trứng None" not in report


def test_structured_report_treats_malformed_nested_data_as_unavailable():
    report = build_structured_findings_report({
        "side": [],
        "pixel_spacing_mm": 0.1,
        "ovary": ["UNTRUSTED"],
        "follicles": ["UNTRUSTED"],
        "measurements": ["UNTRUSTED"],
        "lesion": ["UNTRUSTED"],
    })

    assert "UNTRUSTED" not in report
    assert "CHƯA XÁC ĐỊNH" in report
    assert "Chưa có dữ liệu mask tổn thương" in report


def test_structured_report_does_not_echo_invalid_follicle_count_values():
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "follicles": {
            "count": 4,
            "count_in_range": "UNG THƯ 99% · TÁI KHÁM GẤP",
        },
    })

    assert "Số vùng ứng viên trên mask (chưa xác nhận là nang): 4" in report
    assert "trong khoảng kích thước cấu hình: không xác định" in report
    assert "UNG THƯ" not in report
    assert "99%" not in report


def test_structured_report_handles_huge_untrusted_numeric_values():
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "lesion": {"present": True, "longest_diameter_mm": 10**5000},
    })

    assert "kích thước không xác định × không xác định" in report


def test_structured_report_handles_non_object_root_and_overflow_spacing():
    root_report = build_structured_findings_report(["UNTRUSTED"])
    spacing_report = build_structured_findings_report({"pixel_spacing_mm": 10**5000})

    assert "CHƯA XÁC ĐỊNH" in root_report
    assert "UNTRUSTED" not in root_report
    assert "pixel spacing: cần giá trị hợp lệ" in spacing_report.lower()


def test_structured_report_rejects_boolean_and_impossible_follicle_counts():
    report = build_structured_findings_report({
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "follicles": {"count": True, "count_in_range": True},
    })

    assert "Số vùng ứng viên trên mask: không xác định do dữ liệu đếm không hợp lệ." in report
    assert "Số vùng ứng viên trên mask (chưa xác nhận là nang): True" not in report


def test_structured_report_accepts_zero_candidate_count_as_valid():
    report = build_structured_findings_report({
        "side": "left",
        "follicles": {"count": 0, "count_in_range": 0},
    })

    assert "Số vùng ứng viên trên mask: không xác định do dữ liệu đếm không hợp lệ." not in report
