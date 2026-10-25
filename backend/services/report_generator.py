"""Render a research-use-only ultrasound report draft as an A4 PDF."""

import os
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

# ReportLab imports for fallback
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class MedicalReportGenerator:
    def __init__(self):
        self._init_unicode_fonts()

    def _init_unicode_fonts(self):
        """Register TrueType Unicode Fonts on Windows for ReportLab fallback to prevent black box glyph errors."""
        self.font_regular = "Helvetica"
        self.font_bold = "Helvetica-Bold"

        font_candidates = [
            ("Arial", r"C:\Windows\Fonts\arial.ttf", "Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"),
            ("SegoeUI", r"C:\Windows\Fonts\segoeui.ttf", "SegoeUI-Bold", r"C:\Windows\Fonts\segoeuib.ttf"),
            ("Times", r"C:\Windows\Fonts\times.ttf", "Times-Bold", r"C:\Windows\Fonts\timesbd.ttf"),
            (
                "DejaVuSans",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "DejaVuSans-Bold",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ),
        ]

        for reg_name, reg_path, bld_name, bld_path in font_candidates:
            if os.path.exists(reg_path) and os.path.exists(bld_path):
                try:
                    pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                    pdfmetrics.registerFont(TTFont(bld_name, bld_path))
                    self.font_regular = reg_name
                    self.font_bold = bld_name
                    break
                except Exception as e:
                    print(f"Font registration notice for {reg_name}: {e}")

        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            "ReportTitle",
            parent=self.styles["Heading1"],
            fontName=self.font_bold,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0068AB"),
            alignment=1,
        )
        self.subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=self.styles["Normal"],
            fontName=self.font_bold,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#008CA8"),
            alignment=1,
        )
        self.section_heading = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Heading2"],
            fontName=self.font_bold,
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#004D80"),
            spaceBefore=4,
            spaceAfter=2,
        )
        self.body_style = ParagraphStyle(
            "ReportBody",
            parent=self.styles["Normal"],
            fontName=self.font_regular,
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#0F172A"),
        )
        self.bold_body_style = ParagraphStyle(
            "ReportBoldBody",
            parent=self.body_style,
            fontName=self.font_bold,
        )
        self.draft_notice_style = ParagraphStyle(
            "DraftNotice",
            parent=self.bold_body_style,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#9F1239"),
            alignment=1,
        )

    def _normalize_report_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize supplied case data without inventing clinical fields."""
        if not isinstance(raw_data, dict):
            raise ValueError("Report data must be an object.")
        raw_pid = raw_data.get("patientId") or raw_data.get("anonymized_pid") or raw_data.get("pid")
        if not raw_pid or not str(raw_pid).strip():
            raise ValueError("Thiếu mã định danh bệnh nhân (patientId/anonymized_pid) bắt buộc để khởi tạo phiếu kết quả.")
        pid = str(raw_pid).strip()

        pname = raw_data.get("patientName") or raw_data.get("full_name") or "Chưa ghi nhận"
        pgender = raw_data.get("patientGender") or "Chưa ghi nhận"
        pdob = raw_data.get("patientDob") or "Chưa ghi nhận"
        order_date = raw_data.get("orderDate") or raw_data.get("study_date") or "Chưa ghi nhận"
        completed_date = raw_data.get("completedDate") or "Chưa ghi nhận"
        vis_type = raw_data.get("visitType") or "Chưa ghi nhận"
        ref_doc = raw_data.get("referringDoctor") or "Chưa ghi nhận"
        service = raw_data.get("serviceName") or "Chưa ghi nhận"
        order_name = raw_data.get("orderName") or "Chưa ghi nhận"
        rpid = raw_data.get("rpid") or "Chưa ghi nhận"
        clin_diag = raw_data.get("clinicalDiagnosis") or raw_data.get("clinical_notes") or "Chưa ghi nhận"
        technique = raw_data.get("technique") or "Chưa ghi nhận"

        raw_measurements = raw_data.get("measurements")
        meas = raw_measurements if isinstance(raw_measurements, dict) else {}
        d1 = meas.get("max_diameter_mm")
        d2 = meas.get("ortho_diameter_mm")
        area = meas.get("total_area_cm2")
        d1_str = f"{d1} mm" if d1 is not None else "Chưa ghi nhận"
        d2_str = f"{d2} mm" if d2 is not None else "Chưa ghi nhận"
        area_str = f"{area} cm²" if area is not None else "Chưa ghi nhận"

        has_measurements = any(value is not None for value in (d1, d2, area))
        measurement_text = (
            f"- Số đo AI đề xuất, chưa được bác sĩ xác nhận: D1 = {d1_str}, "
            f"D2 = {d2_str}, diện tích = {area_str}."
            if has_measurements
            else "- Chưa ghi nhận số đo."
        )
        ovary_r1 = raw_data.get("ovary_r1") or "Buồng trứng phải: Chưa ghi nhận mô tả của bác sĩ."
        ovary_r2 = raw_data.get("ovary_r2") or "- Hình thái: Chưa ghi nhận mô tả của bác sĩ."
        ovary_r3 = raw_data.get("ovary_r3") or measurement_text
        ovary_r4 = raw_data.get("ovary_r4") or "- Doppler: Chưa ghi nhận mô tả của bác sĩ."
        ovary_l1 = raw_data.get("ovary_l1") or "Buồng trứng trái: Chưa ghi nhận mô tả của bác sĩ."
        douglas = raw_data.get("douglas") or "Cùng đồ sau: Chưa ghi nhận mô tả của bác sĩ."

        conc1 = raw_data.get("conclusion_l1") or "Kết luận: Chưa được bác sĩ ghi nhận."
        conc2 = raw_data.get("conclusion_l2") or ""
        doc_title = raw_data.get("doctorTitle") or "Chưa ghi nhận"
        doc_name = raw_data.get("doctorName") or raw_data.get("doctor_name") or "Chưa ghi nhận"

        fac_key = raw_data.get("facilityKey") or ""
        hosp_name = raw_data.get("hospitalName") or "Chưa ghi nhận"
        dept_name = raw_data.get("departmentName") or "Chưa ghi nhận"
        hosp_addr = raw_data.get("hospitalAddress") or "Chưa ghi nhận"
        hosp_contact = raw_data.get("hospitalContact") or "Chưa ghi nhận"

        img_before = raw_data.get("imageBefore") or raw_data.get("image_base64")
        img_after = raw_data.get("imageAfter") or raw_data.get("overlay_base64")

        normalized = {
            "facilityKey": fac_key,
            "hospitalName": hosp_name,
            "departmentName": dept_name,
            "hospitalAddress": hosp_addr,
            "hospitalContact": hosp_contact,
            "reportTitle": "BÁO CÁO NGHIÊN CỨU RUO — CHƯA CÓ GIÁ TRỊ CHẨN ĐOÁN",
            "patientId": str(pid),
            "patientName": pname,
            "patientGender": pgender,
            "patientDob": pdob,
            "orderDate": order_date,
            "visitType": vis_type,
            "referringDoctor": ref_doc,
            "serviceName": service,
            "orderName": order_name,
            "completedDate": completed_date,
            "rpid": rpid,
            "clinicalDiagnosis": clin_diag,
            "technique": technique,
            "ovary_r1": ovary_r1,
            "ovary_r2": ovary_r2,
            "ovary_r3": ovary_r3,
            "ovary_r4": ovary_r4,
            "ovary_l1": ovary_l1,
            "douglas": douglas,
            "conclusion_l1": conc1,
            "conclusion_l2": conc2,
            "doctorTitle": doc_title,
            "doctorName": doc_name,
            "signingContext": ", ".join(
                str(value).strip()
                for value in (raw_data.get("signingLocation"), raw_data.get("signedDate"))
                if value and str(value).strip()
            ),
            # Approval must come from a persisted server-side workflow, never
            # from a caller-supplied report dictionary.
            "footerApprovedBy": "Bản nháp chưa được bác sĩ duyệt.",
            "imageBefore": img_before,
            "imageAfter": img_after,
            "imageBeforeCaption": raw_data.get("imageBeforeCaption") or "Ảnh siêu âm đầu vào",
            "imageCaliperTag": raw_data.get("imageCaliperTag")
            or (f"D1: {d1_str} • D2: {d2_str} • Diện tích: {area_str}" if has_measurements else "Chưa ghi nhận số đo"),
        }
        for key, value in normalized.items():
            if key not in {"imageBefore", "imageAfter"}:
                normalized[key] = escape(value) if isinstance(value, str) else "Chưa ghi nhận"
        return normalized

    def generate_pdf_report(self, report_data: dict[str, Any], output_path: str | None = None) -> bytes:
        """
        Generate an RUO report draft with supplied data and Unicode-capable fonts.
        """
        normalized_data = self._normalize_report_data(report_data)
        return self._generate_via_reportlab(normalized_data, output_path)

    def _generate_via_reportlab(self, data: dict[str, Any], output_path: str | None = None) -> bytes:
        """ReportLab single-page A4 generator using registered TrueType Unicode fonts."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            output_path if output_path else buffer,
            pagesize=A4,
            leftMargin=1.2 * cm,
            rightMargin=1.2 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.0 * cm,
        )

        story = []

        # 1. Header
        story.append(Paragraph(data["hospitalName"], self.title_style))
        story.append(Paragraph(data["departmentName"], self.subtitle_style))
        story.append(Spacer(1, 2 * mm))

        # 2. Main Title
        main_title_style = ParagraphStyle(
            "MainTitle",
            parent=self.title_style,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#004D80"),
        )
        story.append(Paragraph(data["reportTitle"], main_title_style))
        story.append(Paragraph(data["footerApprovedBy"], self.draft_notice_style))
        story.append(Spacer(1, 2 * mm))

        # 3. Patient Info Table
        info_data = [
            [
                Paragraph("<b>Mã BN (PID):</b>", self.body_style),
                Paragraph(data["patientId"], self.body_style),
                Paragraph("<b>Ngày khám:</b>", self.body_style),
                Paragraph(data["orderDate"], self.body_style),
            ],
            [
                Paragraph("<b>Họ và tên:</b>", self.body_style),
                Paragraph(f"<b>{data['patientName']}</b>", self.bold_body_style),
                Paragraph("<b>Giới tính:</b>", self.body_style),
                Paragraph(data["patientGender"], self.body_style),
            ],
            [
                Paragraph("<b>Bác sĩ chỉ định:</b>", self.body_style),
                Paragraph(data["referringDoctor"], self.body_style),
                Paragraph("<b>Ngày sinh:</b>", self.body_style),
                Paragraph(data["patientDob"], self.body_style),
            ],
            [
                Paragraph("<b>Chẩn đoán:</b>", self.body_style),
                Paragraph(data["clinicalDiagnosis"], self.body_style),
                Paragraph("<b>Mã RPID:</b>", self.body_style),
                Paragraph(data["rpid"], self.body_style),
            ],
        ]

        t_info = Table(info_data, colWidths=[3.2 * cm, 5.8 * cm, 2.8 * cm, 6.2 * cm])
        t_info.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(t_info)
        story.append(Spacer(1, 2 * mm))

        # 4. Description Findings
        story.append(Paragraph("MÔ TẢ HÌNH ẢNH SIÊU ÂM:", self.section_heading))
        story.append(Paragraph("<b>1. BUỒNG TRỨNG PHẢI:</b>", self.bold_body_style))
        story.append(Paragraph(data["ovary_r1"], self.body_style))
        story.append(Paragraph(data["ovary_r2"], self.body_style))
        story.append(Paragraph(data["ovary_r3"], self.body_style))
        story.append(Paragraph(data["ovary_r4"], self.body_style))
        story.append(Paragraph(f"<b>2. BUỒNG TRỨNG TRÁI:</b> {data['ovary_l1']}", self.body_style))
        story.append(Paragraph(f"<b>3. TÚI CÙNG DOUGLAS:</b> {data['douglas']}", self.body_style))
        story.append(Spacer(1, 3 * mm))

        # 5. Conclusion
        story.append(Paragraph("KẾT LUẬN & ĐỀ NGHỊ:", self.section_heading))
        story.append(Paragraph(f"<b>{data['conclusion_l1']}</b>", self.bold_body_style))
        story.append(Paragraph(data["conclusion_l2"], self.body_style))
        story.append(Spacer(1, 4 * mm))

        doc.build(story)
        if output_path:
            with open(output_path, "rb") as f:
                return f.read()
        return buffer.getvalue()
