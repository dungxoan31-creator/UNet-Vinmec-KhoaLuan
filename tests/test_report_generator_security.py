import pytest

from backend.services.report_generator import MedicalReportGenerator


def test_untrusted_report_text_cannot_create_pdf_link_annotations():
    report = MedicalReportGenerator().generate_pdf_report(
        {
            "patientId": "PID-TEST",
            "patientName": '<link href="https://attacker.invalid">Patient</link>',
        }
    )

    assert report.startswith(b"%PDF-")
    assert b"/Annots" not in report


def test_malformed_measurements_fail_closed_instead_of_aborting_report():
    report = MedicalReportGenerator().generate_pdf_report(
        {"patientId": "PID-TEST", "measurements": ["invalid"]}
    )

    assert report.startswith(b"%PDF-")


def test_invalid_measurement_numbers_are_omitted_without_aborting_report():
    generator = MedicalReportGenerator()
    payload = {
        "patientId": "PID-TEST",
        "measurements": {
            "max_diameter_mm": 10**5000,
            "ortho_diameter_mm": float("nan"),
            "total_area_cm2": True,
            "pixel_spacing_mm": 0.1,
            "calibrated": True,
            "calibration_source": "MANUAL",
        },
    }
    normalized = generator._normalize_report_data(payload)
    pdf = generator.generate_pdf_report(payload)

    assert pdf.startswith(b"%PDF-")
    assert normalized["ovary_r3"] == "- Chưa ghi nhận số đo."
    assert normalized["imageCaliperTag"] == "Chưa ghi nhận số đo"


@pytest.mark.parametrize("spacing", [0, -0.1, float("nan"), float("inf"), True, "0.1", None])
def test_pdf_generator_withholds_physical_measurements_without_usable_spacing(spacing):
    normalized = MedicalReportGenerator()._normalize_report_data(
        {
            "patientId": "PID-TEST",
            "measurements": {
                "max_diameter_mm": 24.5,
                "ortho_diameter_mm": 18.0,
                "total_area_cm2": 0.13,
                "pixel_spacing_mm": spacing,
                "calibrated": True,
                "calibration_source": "DICOM",
            },
        }
    )

    assert normalized["ovary_r3"] == "- Chưa ghi nhận số đo."
    assert normalized["imageCaliperTag"] == "Chưa ghi nhận số đo"


def test_physical_report_measurements_require_usable_calibration_metadata():
    normalized = MedicalReportGenerator()._normalize_report_data(
        {
            "patientId": "PID-TEST",
            "measurements": {
                "max_diameter_mm": 24.5,
                "ortho_diameter_mm": 18.0,
                "total_area_cm2": 0.13,
                "pixel_spacing_mm": None,
                "calibrated": False,
                "calibration_source": "NONE",
            },
        }
    )

    assert normalized["ovary_r3"] == "- Chưa ghi nhận số đo."
    assert normalized["imageCaliperTag"] == "Chưa ghi nhận số đo"


def test_verified_calibration_preserves_valid_report_measurements():
    normalized = MedicalReportGenerator()._normalize_report_data(
        {
            "patientId": "PID-TEST",
            "measurements": {
                "max_diameter_mm": 24.5,
                "ortho_diameter_mm": 18.0,
                "total_area_cm2": 0.13,
                "pixel_spacing_mm": 0.1,
                "calibrated": True,
                "calibration_source": "MANUAL",
            },
        }
    )

    assert "D1 = 24.5 mm, D2 = 18.0 mm, diện tích = 0.13 cm²" in normalized["ovary_r3"]
    assert "D1: 24.5 mm • D2: 18.0 mm • Diện tích: 0.13 cm²" == normalized["imageCaliperTag"]


def test_null_report_payload_is_rejected_as_invalid_object():
    import pytest

    with pytest.raises(ValueError, match="Report data must be an object"):
        MedicalReportGenerator().generate_pdf_report(None)


def test_client_payload_cannot_mark_a_report_as_approved():
    normalized = MedicalReportGenerator()._normalize_report_data(
        {
            "patientId": "PID-TEST",
            "approval_status": "APPROVED",
            "approved_by": "Forged Reviewer",
        }
    )

    assert normalized["footerApprovedBy"] == "Bản nháp chưa được bác sĩ duyệt."
    assert "Forged Reviewer" not in normalized["footerApprovedBy"]


def test_unverified_clinical_text_is_not_emitted_in_ruo_report(monkeypatch):
    import backend.services.report_generator as report_generator

    marker = "UNVERIFIED-MALIGNANT-AND-SURGERY-CLAIM"
    rendered_paragraphs = []
    original_paragraph = report_generator.Paragraph

    def capture_paragraph(text, style):
        rendered_paragraphs.append(text)
        return original_paragraph(text, style)

    monkeypatch.setattr(report_generator, "Paragraph", capture_paragraph)
    payload = {
        "patientId": "PID-TEST",
        "clinicalDiagnosis": marker,
        "clinical_notes": marker,
        "ovary_r1": marker,
        "ovary_r2": marker,
        "ovary_r3": marker,
        "ovary_r4": marker,
        "ovary_l1": marker,
        "douglas": marker,
        "conclusion_l1": marker,
        "conclusion_l2": marker,
    }

    pdf = MedicalReportGenerator().generate_pdf_report(payload)
    rendered = "\n".join(rendered_paragraphs)

    assert pdf.startswith(b"%PDF-")
    assert marker not in rendered
    assert "Không phát hành chẩn đoán lâm sàng trong bản nháp RUO." in rendered
    assert "Không phát hành kết luận lâm sàng trong bản nháp RUO." in rendered
    assert "Không phát hành đề nghị chăm sóc trong bản nháp RUO." in rendered


def test_generated_pdf_labels_draft_and_omits_unverified_signature(monkeypatch):
    import backend.services.report_generator as report_generator

    rendered_paragraphs = []
    original_paragraph = report_generator.Paragraph

    def capture_paragraph(text, style):
        rendered_paragraphs.append(text)
        return original_paragraph(text, style)

    monkeypatch.setattr(report_generator, "Paragraph", capture_paragraph)
    pdf = MedicalReportGenerator().generate_pdf_report(
        {
            "patientId": "PID-TEST",
            "doctorTitle": "Unverified Doctor Title",
            "doctorName": "Unverified Doctor Name",
            "approval_status": "APPROVED",
        }
    )

    rendered_text = "\n".join(rendered_paragraphs)
    assert pdf.startswith(b"%PDF-")
    assert "Bản nháp chưa được bác sĩ duyệt." in rendered_text
    assert "TÀI LIỆU NGHIÊN CỨU (RUO)" in rendered_text
    assert "LỜI DẶN DÀNH CHO BỆNH NHÂN" not in rendered_text
    assert "Quý khách vui lòng mang kết quả này đến Bác sĩ điều trị" not in rendered_text
    assert "Unverified Doctor Title" not in rendered_text
    assert "Unverified Doctor Name" not in rendered_text


def test_linux_unicode_font_is_available_for_pdf_generation(monkeypatch):
    from pathlib import Path

    import backend.services.report_generator as report_generator

    registered_fonts = []
    monkeypatch.setattr(
        report_generator.os.path,
        "exists",
        lambda path: path.startswith("/usr/share/fonts/truetype/dejavu/"),
    )
    monkeypatch.setattr(report_generator, "TTFont", lambda name, _path: name)
    monkeypatch.setattr(report_generator.pdfmetrics, "registerFont", registered_fonts.append)

    generator = report_generator.MedicalReportGenerator()

    assert generator.font_regular == "DejaVuSans"
    assert generator.font_bold == "DejaVuSans-Bold"
    assert registered_fonts == ["DejaVuSans", "DejaVuSans-Bold"]
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    assert "fonts-dejavu-core" in dockerfile.read_text(encoding="utf-8")
