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
