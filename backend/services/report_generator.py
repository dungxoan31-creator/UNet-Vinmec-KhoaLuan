"""
Medical Ultrasound Report Generator Service (Vinmec Standard 1-Page A4 PDF):
- Primary: Headless Browser Rendering (Edge / Chrome) of Official Vinmec HTML Template (Single Page A4, Full Unicode UTF-8)
- Fallback: ReportLab PDF Generator with Registered TrueType Unicode Fonts (Arial / Segoe UI)
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from io import BytesIO
from typing import Any

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
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "templates",
            "medical_report",
            "vinmec_diagnosis_template.html",
        )
        self.edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            shutil.which("msedge"),
            shutil.which("chrome"),
        ]
        self._init_unicode_fonts()

    def _init_unicode_fonts(self):
        """Register TrueType Unicode Fonts on Windows for ReportLab fallback to prevent black box glyph errors."""
        self.font_regular = "Helvetica"
        self.font_bold = "Helvetica-Bold"

        font_candidates = [
            ("Arial", r"C:\Windows\Fonts\arial.ttf", "Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"),
            ("SegoeUI", r"C:\Windows\Fonts\segoeui.ttf", "SegoeUI-Bold", r"C:\Windows\Fonts\segoeuib.ttf"),
            ("Times", r"C:\Windows\Fonts\times.ttf", "Times-Bold", r"C:\Windows\Fonts\timesbd.ttf"),
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

    def _find_browser_binary(self) -> str | None:
        for p in self.edge_paths:
            if p and os.path.exists(p):
                return p
        return None

    def _normalize_report_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Maps incoming API payload to full Vinmec Diagnosis Report format."""
        raw_pid = raw_data.get("patientId") or raw_data.get("anonymized_pid") or raw_data.get("pid")
        if not raw_pid or not str(raw_pid).strip():
            raise ValueError("Thiếu mã định danh bệnh nhân (patientId/anonymized_pid) bắt buộc để khởi tạo phiếu kết quả.")
        pid = str(raw_pid).strip()

        pname = raw_data.get("patientName") or raw_data.get("full_name") or "Chưa ghi nhận"
        pgender = raw_data.get("patientGender") or "N/A"
        pdob = raw_data.get("patientDob") or "N/A"
        order_date = raw_data.get("orderDate") or raw_data.get("study_date") or datetime.now().strftime("%d-%b-%Y %I:%M %p")
        completed_date = raw_data.get("completedDate") or order_date
        vis_type = raw_data.get("visitType") or "Chưa ghi nhận"
        ref_doc = raw_data.get("referringDoctor") or "Chưa ghi nhận"
        service = raw_data.get("serviceName") or "Khám chuyên khoa Phụ khoa — Siêu âm Đầu dò"
        order_name = raw_data.get("orderName") or "Siêu âm buồng trứng qua ngả âm đạo"
        rpid = raw_data.get("rpid") or f"HAN{datetime.now().strftime('%y%m%d%H%M')}"
        clin_diag = raw_data.get("clinicalDiagnosis") or raw_data.get("clinical_notes") or "Chưa ghi nhận"
        technique = raw_data.get("technique") or "Siêu âm 2D Doppler màu ngả âm đạo kết hợp mô hình AI hỗ trợ đo đạc kích thước."

        meas = raw_data.get("measurements") or {}
        d1 = meas.get("max_diameter_mm")
        d2 = meas.get("ortho_diameter_mm")
        area = meas.get("total_area_cm2")
        d1_str = f"{d1} mm" if d1 is not None else "Chưa ghi nhận"
        d2_str = f"{d2} mm" if d2 is not None else "Chưa ghi nhận"
        area_str = f"{area} cm²" if area is not None else "Chưa ghi nhận"

        lesion = raw_data.get("lesion_type") or "Tổn thương dạng nang"

        ovary_r1 = raw_data.get("ovary_r1") or "Khảo sát buồng trứng phải: Xem chi tiết hình ảnh đính kèm."
        ovary_r2 = raw_data.get("ovary_r2") or f"- Hình thái: Ghi nhận {lesion}."
        ovary_r3 = raw_data.get("ovary_r3") or f"- Đo đạc tự động: D1 = {d1_str}, D2 = {d2_str}, Diện tích = {area_str}."
        ovary_r4 = raw_data.get("ovary_r4") or "- Doppler màu: Chưa ghi nhận."
        ovary_l1 = raw_data.get("ovary_l1") or "Khảo sát buồng trứng trái: Xem chi tiết hình ảnh đính kèm."
        douglas = raw_data.get("douglas") or "Cùng đồ sau: Chưa phát hiện bất thường rõ rệt."

        conc1 = raw_data.get("conclusion_l1") or "1. ĐỀ NGHỊ BÁC SĨ LÂM SÀNG ĐỐI CHIẾU TRIỆU CHỨNG VÀ HÌNH ẢNH SIÊU ÂM."
        conc2 = raw_data.get("conclusion_l2") or ""
        doc_title = raw_data.get("doctorTitle") or "Bác sĩ chuyên khoa Chẩn đoán hình ảnh"
        doc_name = raw_data.get("doctorName") or raw_data.get("doctor_name") or "Bác sĩ thực hiện"

        fac_key = raw_data.get("facilityKey") or "times_city"
        hosp_name = raw_data.get("hospitalName") or "HỆ THỐNG Y TẾ VINMEC"
        dept_name = raw_data.get("departmentName") or "KHOA CHẨN ĐOÁN HÌNH ẢNH"
        hosp_addr = raw_data.get("hospitalAddress") or "Hà Nội, Việt Nam"
        hosp_contact = raw_data.get("hospitalContact") or "Tổng đài: 1900 232 389"

        img_before = raw_data.get("imageBefore") or raw_data.get("image_base64")
        img_after = raw_data.get("imageAfter") or raw_data.get("overlay_base64") or img_before

        return {
            "facilityKey": fac_key,
            "hospitalName": hosp_name,
            "departmentName": dept_name,
            "hospitalAddress": hosp_addr,
            "hospitalContact": hosp_contact,
            "reportTitle": "PHIẾU KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG & TIỂU KHUNG",
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
            "footerApprovedBy": f"Kết quả đã được duyệt bởi: {doc_name} — Hệ thống AI Decision Support v1.2",
            "imageBefore": img_before,
            "imageAfter": img_after,
            "imageBeforeCaption": raw_data.get("imageBeforeCaption") or "Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)",
            "imageCaliperTag": raw_data.get("imageCaliperTag") or f"D1: {d1} mm • D2: {d2} mm • DT: {area} cm²",
        }

    def generate_pdf_report(self, report_data: dict[str, Any], output_path: str | None = None) -> bytes:
        """
        Generates official Vinmec single-page A4 PDF report with full Unicode Vietnamese support.
        Tries Headless Browser (Edge/Chrome) first, then falls back to Unicode ReportLab.
        """
        normalized_data = self._normalize_report_data(report_data)
        browser_bin = self._find_browser_binary()

        if browser_bin and os.path.exists(self.template_path):
            try:
                pdf_bytes = self._generate_via_browser(browser_bin, normalized_data)
                if output_path:
                    with open(output_path, "wb") as f:
                        f.write(pdf_bytes)
                return pdf_bytes
            except Exception as e:
                print(f"Browser PDF generation fallback notice: {e}")

        # Fallback to Unicode ReportLab
        return self._generate_via_reportlab(normalized_data, output_path)

    def _generate_via_browser(self, browser_bin: str, data: dict[str, Any]) -> bytes:
        with open(self.template_path, encoding="utf-8") as f:
            template_html = f.read()

        # Inject JSON into template
        data_json = json.dumps(data, ensure_ascii=False)
        injected_html = template_html.replace(
            "const DEFAULT_DATA = {",
            f"const DEFAULT_DATA = {data_json}; const OLD_DATA = {{",
            1
        )

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as temp_html:
            temp_html_path = temp_html.name
            temp_html.write(injected_html)

        temp_pdf_path = temp_html_path.replace(".html", ".pdf")

        try:
            cmd = [
                browser_bin,
                "--headless",
                "--disable-gpu",
                "--run-all-compositor-stages-before-draw",
                "--no-pdf-header-footer",
                f"--print-to-pdf={temp_pdf_path}",
                temp_html_path,
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=20)

            with open(temp_pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return pdf_bytes
        finally:
            if os.path.exists(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except Exception:
                    pass


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

        # 6. Doctor Signature Block
        sig_data = [
            [
                "",
                Paragraph(
                    f"Hà Nội, {datetime.now().strftime('ngày %d tháng %m năm %Y')}<br/><b>{data['doctorTitle']}</b><br/><br/><br/><b>{data['doctorName']}</b>",
                    ParagraphStyle(
                        "Sig",
                        parent=self.body_style,
                        alignment=1,
                        fontName=self.font_regular,
                    ),
                ),
            ]
        ]
        t_sig = Table(sig_data, colWidths=[10 * cm, 8 * cm])
        t_sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(t_sig)

        doc.build(story)
        if output_path:
            with open(output_path, "rb") as f:
                return f.read()
        return buffer.getvalue()
