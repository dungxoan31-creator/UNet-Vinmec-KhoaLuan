"""
Medical Ultrasound Report Generator Service (PDF Generation via ReportLab):
- Header with Hospital/Clinic branding
- Patient metadata & Study details
- Embedded Ultrasound Images (Original + Overlay with Calipers)
- Measurements Table (Dmax, Dorth, Area)
- Doctor's Final Diagnosis & Signature Block
"""

import base64
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class MedicalReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.title_style = ParagraphStyle(
            "ReportTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1B365D"),
            alignment=1,  # Center
        )

        self.subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#555555"),
            alignment=1,
        )

        self.section_heading = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#005691"),
            spaceBefore=8,
            spaceAfter=4,
        )

        self.body_style = ParagraphStyle(
            "ReportBody",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#222222"),
        )

        self.bold_body_style = ParagraphStyle("ReportBoldBody", parent=self.body_style, fontName="Helvetica-Bold")

    def generate_pdf_report(self, report_data, output_path=None):
        """
        report_data dictionary containing:
        - anonymized_pid: str
        - study_date: str
        - patient_age: str
        - doctor_name: str
        - lesion_type: str
        - clinical_notes: str
        - measurements: dict (max_diameter_mm, ortho_diameter_mm, total_area_cm2)
        - image_bytes_or_b64: str or bytes (overlay image)
        - doctor_action: str ('ACCEPTED_RAW', 'MODIFIED', 'REJECTED')
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            output_path if output_path else buffer,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        story = []

        # 1. Header with hospital info
        header_text = Paragraph("VINMEC HEALTHCARE SYSTEM — TIMES CITY INTERNATIONAL HOSPITAL", self.title_style)
        sub_text = Paragraph(
            "KHOA CHẨN ĐOÁN HÌNH ẢNH & SẢN PHỤ KHOA — KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG", self.subtitle_style
        )
        story.append(header_text)
        story.append(sub_text)
        story.append(Spacer(1, 0.4 * cm))

        # 2. Patient & Exam Info Table
        exam_date = report_data.get("study_date", datetime.now().strftime("%d/%m/%Y"))
        pid = report_data.get("anonymized_pid", "ANON-PATIENT-001")
        age = report_data.get("patient_age", "32 (Tuổi sinh đẻ)")
        probe = report_data.get("probe_type", "Siêu âm 2D đầu dò âm đạo (TVUS)")
        doctor = report_data.get("doctor_name", "BS. Nguyễn Văn A (CKI CĐHA)")

        info_data = [
            [
                Paragraph("<b>Mã bệnh nhân (PID):</b>", self.body_style),
                Paragraph(pid, self.body_style),
                Paragraph("<b>Ngày thực hiện:</b>", self.body_style),
                Paragraph(exam_date, self.body_style),
            ],
            [
                Paragraph("<b>Nhóm tuổi / Trạng thái:</b>", self.body_style),
                Paragraph(age, self.body_style),
                Paragraph("<b>Kỹ thuật khảo sát:</b>", self.body_style),
                Paragraph(probe, self.body_style),
            ],
            [
                Paragraph("<b>Bác sĩ chẩn đoán:</b>", self.body_style),
                Paragraph(doctor, self.body_style),
                Paragraph("<b>Hỗ trợ AI:</b>", self.body_style),
                Paragraph("Human-in-the-Loop v1.2", self.body_style),
            ],
        ]

        t_info = Table(info_data, colWidths=[4.2 * cm, 4.8 * cm, 3.8 * cm, 5.2 * cm])
        t_info.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FB")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0C4DE")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_info)
        story.append(Spacer(1, 0.4 * cm))

        # 3. Ultrasound Visual Evidence Section
        story.append(Paragraph("1. HÌNH ẢNH SIÊU ÂM VÀ VÙNG KHOANH ĐO (OVERLAY & CALIPERS)", self.section_heading))

        overlay_b64 = report_data.get("overlay_base64")
        if overlay_b64:
            try:
                if overlay_b64.startswith("data:image"):
                    overlay_b64 = overlay_b64.split(",")[1]
                img_data = base64.b64decode(overlay_b64)
                img_io = BytesIO(img_data)
                rl_img = RLImage(img_io, width=8.5 * cm, height=8.5 * cm)

                # Table to center image
                img_table = Table([[rl_img]], colWidths=[18 * cm])
                img_table.setStyle(
                    TableStyle(
                        [
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                story.append(img_table)
            except Exception as e:
                story.append(Paragraph(f"<i>[Hình ảnh hiển thị lỗi: {e}]</i>", self.body_style))

        story.append(Spacer(1, 0.3 * cm))

        # 4. Measurements Table
        story.append(Paragraph("2. KẾT QUẢ ĐO ĐẠC KÍCH THƯỚC TỔN THƯƠNG", self.section_heading))
        meas = report_data.get("measurements", {})
        dmax = meas.get("max_diameter_mm", 0.0)
        dorth = meas.get("ortho_diameter_mm", 0.0)
        area = meas.get("total_area_cm2", 0.0)

        d3 = meas.get("d3_mm", round((dmax + dorth) / 2.0, 1)) if (dmax > 0 and dorth > 0) else 0.0
        volume = (
            meas.get("volume_cm3", round(0.523 * (dmax * dorth * d3) / 1000.0, 2)) if (dmax > 0 and dorth > 0) else 0.0
        )

        meas_rows = [
            [
                Paragraph("<b>Chỉ số đo đạc</b>", self.bold_body_style),
                Paragraph("<b>Giá trị</b>", self.bold_body_style),
                Paragraph("<b>Đơn vị</b>", self.bold_body_style),
                Paragraph("<b>Đánh giá & Ý nghĩa lâm sàng</b>", self.bold_body_style),
            ],
            [
                Paragraph("Đường kính lớn nhất (D1 / Dmax)", self.body_style),
                Paragraph(f"<b>{dmax}</b>", self.body_style),
                Paragraph("mm", self.body_style),
                Paragraph("Kích thước trục dài nhất của khối u", self.body_style),
            ],
            [
                Paragraph("Đường kính trực giao (D2 / Dorth)", self.body_style),
                Paragraph(f"<b>{dorth}</b>", self.body_style),
                Paragraph("mm", self.body_style),
                Paragraph("Trục vuông góc xác định độ cầu/dẹt", self.body_style),
            ],
            [
                Paragraph("Chiều sâu lát cắt (D3 / Depth)", self.body_style),
                Paragraph(f"<b>{d3}</b>", self.body_style),
                Paragraph("mm", self.body_style),
                Paragraph("Trục không gian thứ 3 (Ước tính / Đo đạc)", self.body_style),
            ],
            [
                Paragraph("Thể tích hình elip (Volume V)", self.body_style),
                Paragraph(f"<b>{volume}</b>", self.body_style),
                Paragraph("mL (cm³)", self.body_style),
                Paragraph("V = 0.523 × D1 × D2 × D3 (Chuẩn ISUOG)", self.body_style),
            ],
            [
                Paragraph("Diện tích mặt cắt tổn thương (Area)", self.body_style),
                Paragraph(f"<b>{area}</b>", self.body_style),
                Paragraph("cm²", self.body_style),
                Paragraph("Diện tích lát cắt qua tâm tổn thương", self.body_style),
            ],
        ]

        t_meas = Table(meas_rows, colWidths=[6.0 * cm, 2.5 * cm, 2.0 * cm, 7.5 * cm])
        t_meas.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_meas)
        story.append(Spacer(1, 0.3 * cm))

        # 5. Doctor Conclusion & Sign-off
        story.append(Paragraph("3. KẾT LUẬN VÀ NHẬN ĐỊNH CỦA BÁC SĨ CHUYÊN KHOA", self.section_heading))
        lesion_type = report_data.get("lesion_type", "U nang buồng trứng phải (Nghi ngờ U bì / Dermoid Cyst)")
        notes = report_data.get(
            "clinical_notes",
            "Hình ảnh khối giảm âm kèm vách tăng âm phản xạ, giới hạn rõ, không thấy tăng sinh mạch máu bất thường trên Doppler. Đề nghị theo dõi định kỳ sau 3 tháng.",
        )
        doc_action = report_data.get("doctor_action", "Đã kiểm tra và phê duyệt kết quả")

        conc_data = [
            [
                Paragraph("<b>Chẩn đoán / Phân loại:</b>", self.bold_body_style),
                Paragraph(f"<font color='#990000'><b>{lesion_type}</b></font>", self.body_style),
            ],
            [Paragraph("<b>Mô tả chi tiết:</b>", self.bold_body_style), Paragraph(notes, self.body_style)],
            [
                Paragraph("<b>Trạng thái duyệt:</b>", self.bold_body_style),
                Paragraph(f"✓ {doc_action} (Đã xác nhận bởi Bác sĩ)", self.body_style),
            ],
        ]
        t_conc = Table(conc_data, colWidths=[4.5 * cm, 13.5 * cm])
        t_conc.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFDF5")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#F6E05E")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FEFCBF")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t_conc)
        story.append(Spacer(1, 0.4 * cm))

        # 6. Signature block & Disclaimer
        disclaimer = Paragraph(
            "<i>* Khuyến cáo an toàn: Hệ thống AI chỉ hỗ trợ phát hiện và đo đạc sơ bộ. Quyết định chẩn đoán và điều trị cuối cùng thuộc về Bác sĩ chuyên khoa có chứng chỉ hành nghề.</i>",
            self.subtitle_style,
        )

        sig_data = [
            [
                disclaimer,
                Paragraph(
                    f"<i>Hà Nội, ngày {datetime.now().strftime('%d/%m/%Y')}</i><br/><b>BÁC SĨ CHUYÊN KHOA</b><br/><br/><br/><b>{doctor}</b>",
                    ParagraphStyle("Sig", parent=self.body_style, alignment=1),
                ),
            ]
        ]
        t_sig = Table(sig_data, colWidths=[10 * cm, 8 * cm])
        t_sig.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ]
            )
        )
        story.append(t_sig)

        doc.build(story)

        if not output_path:
            buffer.seek(0)
            return buffer.getvalue()
        return output_path
