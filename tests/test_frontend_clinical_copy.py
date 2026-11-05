import re
from pathlib import Path


def test_prediction_response_disclaimer_matches_the_ruo_workflow():
    from backend.schemas.schemas import PredictionResponse

    response = PredictionResponse.model_validate(
        {
            "image_id": "image-1",
            "filename": "image.png",
            "confidence_score": 0.5,
            "inference_time_ms": 1,
            "iqa": {
                "iqa_score": 0.5,
                "laplacian_variance": 0.0,
                "contrast_std": 0.0,
                "shadow_ratio": 0.0,
                "flags": [],
                "is_acceptable": True,
            },
            "measurements": {
                "has_lesion": False,
                "total_lesions": 0,
                "lesions": [],
                "max_diameter_mm": None,
                "ortho_diameter_mm": None,
                "total_area_cm2": None,
            },
            "rle_mask": {},
            "overlay_base64": "",
            "original_image_base64": "",
        }
    )
    disclaimer = response.clinical_disclaimer

    assert "RUO" in disclaimer
    assert "chưa được xác thực lâm sàng" in disclaimer.casefold()
    assert "ký duyệt" not in disclaimer.casefold()
    assert "chẩn đoán" in disclaimer.casefold()


def test_admin_role_editor_preserves_unsupported_legacy_roles():
    source = Path("frontend/app/admin-users.js").read_text(encoding="utf-8")

    assert 'const activeRoles = ["BS", "QT"];' in source
    assert 'DOCTOR: "BS"' in source
    assert 'ADMIN: "QT"' in source
    assert 'user && !selectedRole' in source
    assert 'esc(user.role || "chưa xác định")' in source
    assert 'if (body.role === "") delete body.role;' in source


def test_orads_1_copy_requires_physiological_interpretation_not_size_alone():
    source = Path("frontend/app/viewer.js").read_text(encoding="utf-8")

    assert "const ORADS1_OPTION_LABEL =" in source
    assert "nang noãn < 30 mm" in source.casefold()
    assert "nang noãn ≤ 30 mm" not in source.casefold()
    assert "đối chiếu nang noãn &lt;30 mm" in source.casefold()
    assert "mốc đúng 30 mm chưa được policy dự án tự phân tầng" in source.casefold()
    assert "orads1Option.textContent = ORADS1_OPTION_LABEL;" in source

    admin_source = Path("frontend/app/admin-reports.js").read_text(encoding="utf-8")
    assert "Nguy cơ thấp (1–<10%)" in admin_source
    assert "Nguy cơ trung bình (10–<50%)" in admin_source


def test_workstation_offers_orads_0_for_technically_incomplete_evaluation():
    source = Path("frontend/app/viewer.js").read_text(encoding="utf-8")

    assert 'new Option(ORADS0_OPTION_LABEL, "O-RADS 0")' in source
    assert "đánh giá chưa đầy đủ do yếu tố kỹ thuật" in source.casefold()
    assert "chưa phân tầng nguy cơ" in source.casefold()


def test_workstation_and_report_preview_use_neutral_ruo_copy():
    active_surfaces = (
        Path("frontend/index.html").read_text(encoding="utf-8"),
        Path("frontend/app/report-preview.js").read_text(encoding="utf-8"),
    )

    index_copy, report_copy = (surface.casefold() for surface in active_surfaces)
    assert "ruo-safety-banner" not in index_copy
    assert "thông tin nghiên cứu ruo" in report_copy
    assert "bác sĩ phụ trách" in report_copy
    for copy in (index_copy, report_copy):
        assert "chưa được xác thực lâm sàng" not in copy
        assert "không dùng cho chăm sóc bệnh nhân" not in copy
        assert "không thay thế đánh giá của bác sĩ" not in copy


def test_dicom_notice_distinguishes_metadata_filter_from_unreviewed_pixels():
    intake_copy = Path("frontend/app/intake.js").read_text(encoding="utf-8").casefold()
    assert "máy chủ lọc một số metadata văn bản và thay uid nguồn" in intake_copy
    assert "nhưng không làm sạch pixel ảnh" in intake_copy
    assert "burnedinannotation không xác nhận ảnh sạch" in intake_copy
    assert "không tải ảnh có chữ định danh" in intake_copy

    patient_copy = Path("frontend/app/patients.js").read_text(encoding="utf-8").casefold()
    assert "dicom chưa được khử định danh đầy đủ" in patient_copy
    assert "không lưu mã nguồn dạng văn bản" in patient_copy
    assert "không làm sạch pixel ảnh" in patient_copy


def test_active_workstation_distinguishes_clinician_orads_from_ai_segmentation():
    source = Path("frontend/app/viewer.js").read_text(encoding="utf-8")

    assert "AI đề xuất phân đoạn" in source
    assert re.search(
        r'<label class="field">Phân tầng ACR O-RADS do bác sĩ chọn\s*'
        r'<select id="oradsScore" aria-describedby="oradsHelp">',
        source,
    )
    assert 'id="oradsHelp"' in source
    assert "Lựa chọn này do bác sĩ nhập; hệ thống không tự suy luận O-RADS. Để trống khi chưa đủ thông tin." in source
