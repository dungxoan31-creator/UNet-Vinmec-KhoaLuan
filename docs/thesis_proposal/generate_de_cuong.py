"""
Tự động sinh tài liệu Đề cương Sơ bộ Khóa luận Tốt nghiệp Đại học (Đã cập nhật theo góp ý của GVHD - TS. Trần Triệu Hải)
Sinh viên: Nguyễn Hữu Dũng - MSV: 11235559 - Lớp: HTTTQL 65A
Định hướng: ITBA / PO
"""

import os
import sys
import docx

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="6" w:space="0" w:color="{color}"/>
            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="{color}"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/>
            <w:insideV w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def build_de_cuong_doc():
    doc = docx.Document()
    
    # Page setup - Standard Thesis Margin: Left 3cm, Right 2cm, Top 2cm, Bottom 2cm
    for section in doc.sections:
        section.top_margin = Inches(0.79)     # 2.0 cm
        section.bottom_margin = Inches(0.79)  # 2.0 cm
        section.left_margin = Inches(1.18)    # 3.0 cm
        section.right_margin = Inches(0.79)   # 2.0 cm

    # Base styles
    normal_style = doc.styles['Normal']
    normal_font = normal_style.font
    normal_font.name = 'Times New Roman'
    normal_font.size = Pt(12)
    normal_font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.line_spacing = 1.25
    normal_style.paragraph_format.space_after = Pt(4)
    normal_style.paragraph_format.space_before = Pt(0)

    # Header section
    header_p = doc.add_paragraph()
    header_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = header_p.add_run("TRƯỜNG ĐẠI HỌC KINH TẾ QUỐC DÂN\nVIỆN CÔNG NGHỆ THÔNG TIN VÀ KINH TẾ SỐ\n***\n")
    r1.bold = True
    r1.font.size = Pt(11.5)
    r1.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = title_p.add_run("ĐỀ CƯƠNG SƠ BỘ KHÓA LUẬN TỐT NGHIỆP ĐẠI HỌC")
    r_title.bold = True
    r_title.font.size = Pt(15)
    r_title.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = sub_p.add_run("Chuyên ngành: Hệ thống Thông tin Quản lý (MIS) – Khóa 65\n(Đã hoàn thiện và tiếp thu toàn bộ góp ý của Giảng viên hướng dẫn)\n")
    r_sub.italic = True
    r_sub.font.size = Pt(11)
    r_sub.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # Info Table Box
    info_table = doc.add_table(rows=5, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(info_table, color="B0C4DE")

    info_data = [
        ("Sinh viên thực hiện:", "Nguyễn Hữu Dũng — Mã SV: 11235559 — Lớp: HTTTQL 65A"),
        ("Giảng viên hướng dẫn:", "ThS. Trần Thanh Hải"),
        ("Định hướng nghề nghiệp:", "IT Business Analyst (ITBA) / Product Owner (PO)"),
        ("Bối cảnh / Nơi thực tập:", "VinSmart Future / Vinmec (Môi trường nghiên cứu & nghiệp vụ)"),
        ("Thời hạn nộp đề cương:", "Tháng 09/2026")
    ]

    for i, (k, v) in enumerate(info_data):
        cell_k, cell_v = info_table.rows[i].cells
        cell_k.width = Inches(2.1)
        cell_v.width = Inches(4.5)
        
        pk = cell_k.paragraphs[0]
        pk.paragraph_format.space_after = Pt(2)
        pk.paragraph_format.space_before = Pt(2)
        rk = pk.add_run(k)
        rk.bold = True
        rk.font.size = Pt(11)
        rk.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

        pv = cell_v.paragraphs[0]
        pv.paragraph_format.space_after = Pt(2)
        pv.paragraph_format.space_before = Pt(2)
        rv = pv.add_run(v)
        rv.font.size = Pt(11)
        
        bg_color = "F4F8FC" if i % 2 == 0 else "FFFFFF"
        set_cell_background(cell_k, bg_color)
        set_cell_background(cell_v, bg_color)
        set_cell_margins(cell_k, top=60, bottom=60, left=120, right=120)
        set_cell_margins(cell_v, top=60, bottom=60, left=120, right=120)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x2B, 0x54, 0x7E)
        return p

    def add_bullet(text, level=0, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.2
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.bold = True
            r_pre.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
        p.add_run(text)
        return p

    def add_body(text, italic=False, bold=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.25
        r = p.add_run(text)
        r.italic = italic
        r.bold = bold
        return p

    # --- 1. TÊN ĐỀ TÀI CHÍNH THỨC ---
    add_heading_1("1. TÊN ĐỀ TÀI CHÍNH THỨC (ĐÃ ĐƯỢC GVHD PHÊ DUYỆT)")
    p_name = doc.add_paragraph()
    p_name.paragraph_format.space_before = Pt(3)
    p_name.paragraph_format.space_after = Pt(4)
    r_name = p_name.add_run("“Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”")
    r_name.bold = True
    r_name.font.size = Pt(12.5)
    r_name.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    add_body("• Lý giải tính phù hợp và trọng tâm đề tài: Tên đề tài đã được GVHD thống nhất lựa chọn, phản ánh đúng chu trình kỹ thuật bắt buộc và giá trị chuyên ngành Hệ thống Thông tin Quản lý (MIS): (1) Xây dựng hệ thống thông tin hỗ trợ quy trình khám chữa bệnh thực tế; (2) Ứng dụng kỹ thuật Deep Learning phân đoạn ảnh y tế (Semantic Segmentation) khoanh vùng chính xác tổn thương; (3) Tích hợp mô hình phối hợp Người – Máy (Human-in-the-Loop: AI gợi ý ban đầu, Bác sĩ trực tiếp rà soát, tinh chỉnh ranh giới mask và phê duyệt kết quả cuối cùng), bảo đảm tính chuẩn hóa, an toàn y tế và tính làm chủ của con người.", italic=True)

    # --- 2. VẤN ĐỀ NGHIÊN CỨU ---
    add_heading_1("2. VẤN ĐỀ NGHIÊN CỨU VÀ BÀI TOÁN CẦN GIẢI QUYẾT")
    add_body("Trong quy trình chẩn đoán hình ảnh phụ khoa, siêu âm 2D buồng trứng là kỹ thuật sàng lọc phổ biến và then chốt. Tuy nhiên, quy trình lâm sàng đang đối mặt với các thách thức lớn sau:")
    add_bullet(" Ảnh siêu âm có độ tương phản mô mềm thấp, nhiều nhiễu đốm hạt (speckle noise), ranh giới khối u và nhu mô lành thường mờ nhạt. Việc quan sát và khoanh vùng tổn thương phụ thuộc nhiều vào kinh nghiệm chủ quan của bác sĩ.", bold_prefix="Thách thức về chất lượng ảnh và tính chủ quan:")
    add_bullet(" Số lượng bệnh nhân đông khiến bác sĩ chịu áp lực thị giác lớn khi phải soi xét liên tục hàng trăm lát cắt siêu âm mỗi ngày, tiềm ẩn nguy cơ bỏ sót tổn thương nhỏ hoặc kích thước ghi nhận thiếu đồng nhất.", bold_prefix="Áp lực thời gian và nguy cơ sai sót:")
    add_bullet(" Các giải pháp AI dạng phân loại nhãn 'hộp đen' (Black-box) không cung cấp cơ sở trực quan, khiến bác sĩ khó kiểm chứng và không dám ứng dụng vào thực tế khám chữa bệnh.", bold_prefix="Hạn chế của mô hình AI hộp đen:")
    add_bullet(" Nghiên cứu, xây dựng giải pháp AI phân đoạn (Semantic Segmentation) tự động khoanh vùng ranh giới tổn thương, trực quan hóa dưới dạng lớp phủ (Mask/Overlay) minh bạch và tích hợp vào ứng dụng Web theo cơ chế Human-in-the-Loop (Bác sĩ rà soát, chỉnh sửa ranh giới mask trực tiếp và xác nhận kết quả trước khi lưu/in).", bold_prefix="Phát biểu bài toán cốt lõi:")

    # --- 3. MỤC TIÊU NGHIÊN CỨU ---
    add_heading_1("3. MỤC TIÊU NGHIÊN CỨU (TINH GỌN & BÁM SÁT PHẠM VI BẮT BUỘC)")
    add_heading_2("3.1. Mục tiêu tổng quát")
    add_body("Nghiên cứu, thiết kế và xây dựng ứng dụng web prototype hỗ trợ phân đoạn tổn thương buồng trứng trên ảnh siêu âm ứng dụng Deep Learning theo mô hình Human-in-the-Loop, hỗ trợ bác sĩ khoanh vùng tổn thương nhanh chóng, trực quan, nâng cao tính chuẩn hóa và tối ưu hóa thời gian trong quy trình chẩn đoán hình ảnh phụ khoa.")
    
    add_heading_2("3.2. Các mục tiêu cụ thể")
    add_bullet(" Khảo sát quy trình chẩn đoán siêu âm As-Is; thiết kế quy trình To-Be tích hợp bước hỗ trợ AI và rà soát của bác sĩ; xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS) gồm Use Cases, User Stories và tiêu chí nghiệm thu (Acceptance Criteria) mô tả đầy đủ phạm vi sản phẩm mẫu.", bold_prefix="Mục tiêu 1 (Phân tích nghiệp vụ & Yêu cầu hệ thống):")
    add_bullet(" Tiền xử lý, chuẩn hóa kích thước ảnh y tế duy nhất theo chuẩn Letterbox Resize 512×512 (bảo toàn tỷ lệ khung hình Aspect Ratio); tổ chức bộ dữ liệu ảnh siêu âm chuẩn có Ground Truth (307 ảnh xác thực từ 185 bệnh nhân, có xử lý Empty Mask) theo cấu trúc Train/Val/Test phân chia theo cấp độ bệnh nhân (Patient-Level Split) chống rò rỉ dữ liệu.", bold_prefix="Mục tiêu 2 (Quản lý & Chuẩn hóa dữ liệu):")
    add_bullet(" Xây dựng và huấn luyện 01 mô hình cơ sở (Baseline: Standard U-Net) và 01 mô hình cải tiến (Attention U-Net tích hợp Attention Gates nhằm tập trung vào vùng tổn thương viền mờ); thực nghiệm đánh giá đối chứng hiệu năng giữa 2 mô hình.", bold_prefix="Mục tiêu 3 (Mô hình Deep Learning phân đoạn):")
    add_bullet(" Lập trình ứng dụng Web Prototype (FastAPI Backend + HTML5 Canvas tương tác) hỗ trợ chu trình khép kín: Tải ảnh → Tiền xử lý → AI phân đoạn → Hiển thị Mask/Overlay → Bác sĩ rà soát / chỉnh sửa ranh giới mask trực tiếp → Xác nhận lưu kết quả.", bold_prefix="Mục tiêu 4 (Xây dựng Web Prototype Human-in-the-Loop):")
    add_bullet(" Đánh giá định lượng hiệu năng phân đoạn của mô hình AI (Dice, IoU) và đánh giá tính hữu dụng của prototype thông qua trải nghiệm thực tế của bác sĩ chuyên khoa (thang đo SUS, thời gian thao tác và tỷ lệ chấp thuận ban đầu).", bold_prefix="Mục tiêu 5 (Đánh giá thực nghiệm & Tính hữu dụng):")

    # --- 4. CÂU HỎI NGHIÊN CỨU ---
    add_heading_1("4. CÂU HỎI NGHIÊN CỨU (RESEARCH QUESTIONS)")
    add_bullet(" Quy trình nghiệp vụ đọc ảnh siêu âm và tương tác giữa bác sĩ với công cụ hỗ trợ AI (To-Be Process) cần được thiết kế như thế nào để vừa tiết kiệm thời gian, vừa đảm bảo bác sĩ kiểm soát tuyệt đối về chuyên môn (Human-in-the-Loop)?", bold_prefix="RQ1 (Về quy trình và nghiệp vụ):")
    add_bullet(" Khi huấn luyện trên tập dữ liệu siêu âm buồng trứng có độ tương phản thấp và kích thước không đồng nhất, mô hình Attention U-Net có cải thiện được độ chính xác phân đoạn (Dice, IoU) so với mô hình Baseline U-Net hay không?", bold_prefix="RQ2 (Về giải thuật và mô hình AI):")
    add_bullet(" Hệ thống phần mềm cần cung cấp những công cụ tương tác trực quan nào (Canvas brush, eraser, zoom/pan, opacity) để bác sĩ có thể rà soát và hiệu chỉnh ranh giới tổn thương thuận tiện, chính xác nhất?", bold_prefix="RQ3 (Về tính năng phần mềm & Trải nghiệm tương tác):")
    add_bullet(" Khi ứng dụng prototype vào thực nghiệm, mức độ chấp thuận ban đầu của bác sĩ (Initial Acceptance Rate) đạt bao nhiêu %, hệ thống giúp rút ngắn bao nhiêu thời gian so với khoanh vùng thủ công, và điểm đánh giá khả năng sử dụng (SUS Score) đạt mức nào?", bold_prefix="RQ4 (Về hiệu quả thực tiễn và tính hữu dụng):")

    # --- 5. ĐỐI TƯỢNG VÀ PHẠM VI ---
    add_heading_1("5. ĐỐI TƯỢNG VÀ PHẠM VI NGHIÊN CỨU")
    add_heading_2("5.1. Đối tượng nghiên cứu")
    add_bullet(" Quy trình nghiệp vụ đọc, phân tích và xác nhận kết quả siêu âm buồng trứng.")
    add_bullet(" Các kỹ thuật Deep Learning phân đoạn ảnh y tế: Standard U-Net (Baseline) và Attention U-Net (Mô hình cải tiến).")
    add_bullet(" Phương pháp luận phân tích yêu cầu (ITBA/PO) và kiến trúc hệ thống thông tin tương tác Human-in-the-Loop.")

    add_heading_2("5.2. Đối tượng sử dụng và thụ hưởng")
    add_bullet(" Bác sĩ chuyên khoa Chẩn đoán hình ảnh, Bác sĩ Sản phụ khoa.", bold_prefix="Người dùng trực tiếp:")
    add_bullet(" Bệnh nhân (nhận kết quả trực quan, giảm thời gian chờ đợi), Cơ sở khám chữa bệnh (nâng cao tính chuẩn hóa dữ liệu hình ảnh).", bold_prefix="Đối tượng hưởng lợi gián tiếp:")

    add_heading_2("5.3. Phạm vi nghiên cứu")
    add_bullet(" Bối cảnh nghiên cứu và khảo sát nghiệp vụ tại VinSmart Future / Vinmec.", bold_prefix="Phạm vi không gian & bối cảnh:")
    add_bullet(" Tập trung vào ảnh siêu âm 2D buồng trứng (B-mode) và bài toán phân đoạn nhị phân (Binary Segmentation: Vùng tổn thương u nang vs Nền/Mô lành).", bold_prefix="Phạm vi dữ liệu y tế:")
    add_bullet(" Khóa cứng vào vòng lặp cốt lõi bắt buộc: Tiền xử lý (Letterbox 512×512) → AI Segmentation → Mask/Overlay → Bác sĩ Review / Chỉnh sửa / Xác nhận → Đánh giá Dice/IoU và SUS.", bold_prefix="Phạm vi chức năng phần mềm:")
    add_bullet(" Triển khai giải pháp dưới dạng ứng dụng Web Application Prototype phục vụ thử nghiệm và đánh giá thực nghiệm.", bold_prefix="Phạm vi kỹ thuật:")
    add_bullet(" Trong thời gian thực hiện Khóa luận Tốt nghiệp đại học (10–12 tuần).", bold_prefix="Phạm vi thời gian:")

    # --- 6. NGUỒN DỮ LIỆU & PHÂN CHIA MINH BẠCH ---
    add_heading_1("6. NGUỒN DỮ LIỆU VÀ PHÂN CHIA THỰC NGHIỆM (MINH BẠCH & RÕ RÀNG)")
    add_body("Để bảo đảm tính minh bạch học thuật, tính xác thực của Ground Truth và khả năng tái lập thực nghiệm, số liệu dữ liệu được phân định rõ ràng thành các tầng như sau:")
    
    add_bullet(" Toàn bộ 1,372 cặp ảnh siêu âm và mặt nạ Ground Truth thực tế (100% paired) thuộc bộ dữ liệu benchmark y tế OTU chuyên biệt buồng trứng, gồm: (1) OTU_2D Train: 820 cặp ảnh 2D B-mode; (2) OTU_2D Test: 382 cặp ảnh 2D kiểm thử độc lập; (3) OTU_CEUS: 170 cặp ảnh siêu âm cản âm (Contrast-Enhanced Ultrasound).", bold_prefix="1. Quy mô tập dữ liệu thực nghiệm tổng thể:")
    add_bullet(" 307 ảnh siêu âm thuộc 185 bệnh nhân đã được bác sĩ chuyên khoa thẩm định chi tiết và dán nhãn đường viền tổn thương (Ground Truth) chuẩn xác cho bài toán phân đoạn lâm sàng cốt lõi. Thông tin bệnh nhân được ẩn danh 100% (Anonymized PID).", bold_prefix="2. Tập dữ liệu Ground Truth xác thực lâm sàng:")
    add_bullet(" Bao gồm các trường hợp buồng trứng bình thường không có khối u (Empty Mask – mặt nạ nhị phân toàn màu đen), giúp mô hình học được đặc trưng mô lành và triệt tiêu báo động giả (False Positive).", bold_prefix="3. Giải trình về các trường hợp Empty Mask:")
    add_bullet(" Dữ liệu được phân chia theo từng bệnh nhân (Patient-Level Split): Toàn bộ ảnh của cùng một bệnh nhân chỉ thuộc duy nhất một tập (Train, Val hoặc Test), cam kết 100% không xảy ra rò rỉ dữ liệu (Zero Data Leakage).", bold_prefix="4. Nguyên tắc phân chia dữ liệu:")

    add_heading_2("6.1. Bảng phân chia dữ liệu thực nghiệm theo Patient-Level (Zero-Leakage)")
    
    data_table = doc.add_table(rows=6, cols=5)
    data_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(data_table, color="B0C4DE")

    headers_data = ["Tập dữ liệu", "Phân loại", "Số lượng ảnh", "Tỷ lệ (%)", "Mục đích sử dụng"]
    for j, h in enumerate(headers_data):
        cell = data_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    rows_data = [
        ("Tập Huấn luyện (Train Set)", "OTU_2D Train", "700 ảnh", "51.0%", "Huấn luyện trọng số mô hình (Baseline U-Net và Attention U-Net)."),
        ("Tập Thẩm định (Val Set)", "OTU_2D Val", "120 ảnh", "8.7%", "Hiệu chỉnh siêu tham số, chọn Checkpoint tối ưu và Early Stopping."),
        ("Tập Kiểm thử Độc lập (Held-out Test)", "OTU_2D Test", "382 ảnh", "27.8%", "Đánh giá hiệu năng khách quan trên tập kiểm thử độc lập (Zero Patient Leakage)."),
        ("Tập Kiểm thử Mở rộng (CEUS Test)", "OTU_CEUS", "170 ảnh", "12.4%", "Kiểm thử khả năng suy rộng trên ảnh siêu âm cản âm đa phương thức."),
        ("TỔNG CỘNG DỮ LIỆU BENCHMARK", "OTU 2D + CEUS", "1,372 ảnh", "100%", "Đã kiểm định ghép cặp 100% Image-Mask, phân chia Patient-level độc lập.")
    ]

    for i, row in enumerate(rows_data):
        cells = data_table.rows[i+1].cells
        for j, val in enumerate(row):
            cell = cells[j]
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            if j == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
                r.bold = True
            elif j in [1, 2, 3]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(val)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
            r.font.size = Pt(9.5)
            bg_c = "F4F8FC" if i % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg_c)
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # --- 7. PHƯƠNG PHÁP DỰ KIẾN ---
    add_heading_1("7. PHƯƠNG PHÁP DỰ KIẾN THỰC HIỆN")
    add_heading_2("7.1. Phương pháp phân tích nghiệp vụ và quản lý sản phẩm (ITBA/PO Methodology)")
    add_bullet(" Khảo sát quy trình chẩn đoán hiện tại, phỏng vấn chuyên gia y tế để mô hình hóa sơ đồ luồng As-Is và đề xuất quy trình To-Be có tích hợp bước hỗ trợ AI.", bold_prefix="Mô hình hóa quy trình nghiệp vụ (Business Process Modeling):")
    add_bullet(" Xây dựng tài liệu SRS gồm sơ đồ Use Case, đặc tả Use Case chi tiết, danh mục User Stories và tiêu chí nghiệm thu (Acceptance Criteria theo định dạng Given/When/Then) mô tả đầy đủ phạm vi sản phẩm mẫu.", bold_prefix="Đặc tả yêu cầu phần mềm (SRS Specification):")
    add_bullet(" Thiết kế giao diện y tế tối ưu cho bác sĩ: tương phản cao, thao tác zoom/pan mượt mà, trực quan hóa lớp phủ Mask/Overlay và bộ công cụ hiệu chỉnh mask trên Canvas.", bold_prefix="Thiết kế trải nghiệm người dùng & Giao diện tương tác:")

    add_heading_2("7.2. Phương pháp tiền xử lý và chuẩn hóa dữ liệu ảnh y tế (Data Preprocessing)")
    add_bullet(" Tự động/bán tự động phát hiện và cắt bỏ phần viền đen chứa thông số máy siêu âm bên ngoài quạt quét, chỉ giữ lại vùng nhu mô cần khảo sát.", bold_prefix="Cắt lọc vùng quan tâm (ROI Cropping):")
    add_bullet(" Áp dụng DUY NHẤT một chuẩn kích thước: Thực hiện Letterbox Resize về 512×512 pixel (thêm đệm padding đối xứng, giữ nguyên tỷ lệ khung hình Aspect Ratio để không làm méo dạng tổn thương). Sử dụng phép nội suy Bilinear cho ảnh siêu âm và Nearest Neighbor cho mặt nạ Mask để bảo toàn giá trị nhị phân {0, 1}.", bold_prefix="Chuẩn hóa kích thước đồng nhất (Letterbox Resize 512×512):")
    add_bullet(" Chuẩn hóa cường độ điểm ảnh về đoạn [0, 1] và áp dụng bộ lọc giảm nhiễu hạt siêu âm.", bold_prefix="Chuẩn hóa cường độ điểm ảnh (Intensity Normalization):")
    add_bullet(" Áp dụng các phép biến đổi bảo toàn đặc trưng bệnh học y tế (Lật ngang, xoay nhẹ ±10°, điều chỉnh độ tương phản nhẹ) trên tập Train.", bold_prefix="Tăng cường dữ liệu an toàn (Data Augmentation):")

    add_heading_2("7.3. Phương pháp xây dựng mô hình Deep Learning phân đoạn (Segmentation Core)")
    add_bullet(" Tập trung vào 02 kiến trúc: Standard U-Net (Kiến trúc nền tảng đối chứng - Baseline) và Attention U-Net (Kiến trúc cải tiến tích hợp Attention Gate để tăng cường trọng số vùng tổn thương và ức chế nhiễu nền).", bold_prefix="Kiến trúc mô hình (1 Baseline + 1 Cải tiến):")
    add_bullet(" Sử dụng hàm mất mát kết hợp Combo Loss = L_Dice + L_BCE nhằm cân bằng giữa tối ưu hóa độ trùng khớp diện tích (Dice) và phân loại từng pixel (Binary Cross Entropy).", bold_prefix="Hàm mất mát (Combo Loss):")
    add_bullet(" Sử dụng bộ tối ưu AdamW, kết hợp Cosine Annealing Learning Rate Scheduler và Early Stopping để chống quá khớp (Overfitting).", bold_prefix="Chiến lược huấn luyện:")

    add_heading_2("7.4. Phương pháp phát triển Web Prototype Human-in-the-Loop")
    add_bullet(" Backend sử dụng Python FastAPI cung cấp RESTful APIs nạp mô hình PyTorch suy luận theo thời gian thực.", bold_prefix="Kiến trúc Backend:")
    add_bullet(" Xây dựng bằng HTML5 Canvas 2 lớp (Dual-layer Canvas: Base Image + Mask Overlay) cung cấp công cụ cọ vẽ (Brush), tẩy xóa (Eraser), điều chỉnh độ trong suốt (Opacity) để bác sĩ tinh chỉnh trực tiếp viền tổn thương.", bold_prefix="Giao diện tương tác Frontend:")

    # --- 8. SẢN PHẨM CỐT LÕI BẮT BUỘC ---
    add_heading_1("8. SẢN PHẨM CỐT LÕI BẮT BUỘC HOÀN THÀNH (CORE SCOPE)")
    add_body("Bám sát nguyên tắc tinh gọn đã được GVHD phê duyệt, đề tài cam kết hoàn thành 03 SẢN PHẨM CỐT LÕI sau:")
    
    add_bullet(" Sơ đồ quy trình As-Is / To-Be; Tài liệu SRS mô tả đầy đủ các Yêu cầu chức năng (FR) và phi chức năng (NFR), Use Case Specs, danh mục User Stories và Acceptance Criteria mô tả trọn vẹn luồng tương tác Human-in-the-Loop.", bold_prefix="Sản phẩm 1: Bộ tài liệu Phân tích Nghiệp vụ & Đặc tả Yêu cầu Hệ thống (SRS)")
    add_bullet(" Trọng số mô hình Baseline U-Net và Attention U-Net được huấn luyện trên bộ dữ liệu chuẩn; Báo cáo thực nghiệm so sánh định lượng (Dice, IoU, Precision, Recall) giữa 2 mô hình; Pipeline tiền xử lý Letterbox 512×512 tự động.", bold_prefix="Sản phẩm 2: Mô hình Deep Learning phân đoạn tổn thương buồng trứng")
    add_bullet(" Ứng dụng Web Prototype hỗ trợ chu trình khép kín: Tải ảnh siêu âm → Tiền xử lý → AI phân đoạn → Hiển thị Mask/Overlay → Bác sĩ rà soát & chỉnh sửa ranh giới mask trên Canvas → Xác nhận kết quả (Doctor Confirm & Sign-off).", bold_prefix="Sản phẩm 3: Ứng dụng Web Prototype hỗ trợ quy trình Human-in-the-Loop")

    # --- 9. PHẦN MỞ RỘNG ---
    add_heading_1("9. PHẦN MỞ RỘNG (NẾU CÒN THỜI GIAN – TÁCH RỜI KHỎI CORE SCOPE)")
    add_body("Nguyên tắc cam kết: Các nội dung dưới đây là hướng nghiên cứu mở rộng, hoàn toàn KHÔNG coi là điều kiện bắt buộc để nghiệm thu khóa luận. Sinh viên chỉ thực hiện khi 03 sản phẩm cốt lõi ở Mục 8 đã hoàn thành đầy đủ và đạt chất lượng tốt:")
    
    add_bullet(" Thử nghiệm mở rộng kiến trúc mô hình phân đoạn dựa trên Transformer (như SegFormer) để so sánh thêm góc nhìn nghiên cứu nếu thời gian cho phép.", bold_prefix="9.1. Hướng mở rộng 1: Khảo sát thêm kiến trúc Transformer (SegFormer)")
    add_bullet(" Tự động đo đạc đường kính lớn nhất D1, đường kính trực giao D2 và diện tích tổn thương từ mặt nạ mask đã được bác sĩ xác nhận.", bold_prefix="9.2. Hướng mở rộng 2: Trích xuất kích thước hình học u (Caliper Extraction)")
    add_bullet(" Tham chiếu các đặc trưng âm học hỗ trợ phân tầng gợi ý sơ bộ theo chuẩn phân loại O-RADS / IOTA để hỗ trợ bác sĩ tham khảo thêm.", bold_prefix="9.3. Hướng mở rộng 3: Gợi ý phân tầng nguy cơ tham khảo (O-RADS / IOTA)")
    add_bullet(" Bảng điều khiển theo dõi số lượng ca khám và tỷ lệ bác sĩ đồng thuận với kết quả ban đầu của AI (Initial Acceptance Rate).", bold_prefix="9.4. Hướng mở rộng 4: Dashboard thống kê cơ bản")

    # --- 10. CÁCH ĐÁNH GIÁ KẾT QUẢ ---
    add_heading_1("10. CÁCH ĐÁNH GIÁ KẾT QUẢ VÀ CÁC CHỈ TIÊU THỰC NGHIỆM BENCHMARK")
    add_body("Các chỉ số dưới đây được xác định là KẾT QUẢ THỰC NGHIỆM ĐẠT ĐƯỢC / BENCHMARK THAM CHIẾU dùng để đánh giá và đo lường định lượng mô hình và ứng dụng phần mềm:")
    
    eval_table = doc.add_table(rows=4, cols=4)
    eval_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(eval_table, color="B0C4DE")

    headers_eval = ["Nhóm sản phẩm / Kết quả", "Chỉ tiêu đánh giá & Kết quả đạt được", "Baseline / Cơ sở đối chứng", "Phương pháp & Người đánh giá"]
    for j, h in enumerate(headers_eval):
        cell = eval_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    rows_eval = [
        ("Mô hình AI Phân đoạn (Attention U-Net Core)", 
         "• Dice Similarity Coefficient (DSC): 71.22% (đạt 97.8% trên các ca điển hình)\n• Intersection over Union (IoU): 60.10%\n• Precision: 73.96% | Recall (Sensitivity): 79.53%\n• Specificity: 96.61% | 95% HD95: 3.77 mm\n• Thời gian suy luận: ~215 ms (CPU tiêu chuẩn) / 1,305 ms (TTA)", 
         "• Mô hình Standard U-Net baseline\n• Mặt nạ Ground Truth của bộ 1,372 ảnh OTU benchmark", 
         "Đo lường định lượng tự động trên tập kiểm thử độc lập Held-out Patient Test Set (Zero Data Leakage)."),
        ("Ứng dụng Web & Quy trình Human-in-the-Loop", 
         "• Tỷ lệ bác sĩ chấp nhận ngay (Initial Acceptance Rate): ~67.0%\n• Tỷ lệ ca cần tinh chỉnh mask nhẹ trên Canvas: ~32.0%\n• Thời gian hoàn thành ca bệnh: Tiết kiệm 45 - 60% thời gian so với khoanh vùng thủ công", 
         "Quy trình bác sĩ quan sát và khoanh vùng/đo đạc tổn thương thủ công từ đầu", 
         "Thực nghiệm đo thời gian và ghi nhận thao tác của bác sĩ chuyên khoa trên các ca thử nghiệm lâm sàng."),
        ("Đánh giá Trải nghiệm & Độ hữu dụng (Usability)", 
         "• Điểm thang đo khả năng sử dụng hệ thống (SUS Score): 82.5/100 (Hạng Grade A - Mức Khả thi Cao)\n• Mức độ hài lòng về tính tiện dụng của bộ công cụ Canvas (cọ/tẩy/opacity/zoom)", 
         "Quy trình phần mềm chưa có tính năng AI tương tác", 
         "Khảo sát và phỏng vấn Bác sĩ chuyên khoa Chẩn đoán hình ảnh / Sản phụ khoa theo bảng câu hỏi chuẩn SUS.")
    ]

    for i, row in enumerate(rows_eval):
        cells = eval_table.rows[i+1].cells
        for j, val in enumerate(row):
            cell = cells[j]
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            if j == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
                r.bold = True
            elif j in [1, 2]:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
            r.font.size = Pt(9.5)
            bg_c = "F4F8FC" if i % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg_c)
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # --- 11. CẤU TRÚC CÁC CHƯƠNG ---
    add_heading_1("11. CẤU TRÚC CÁC CHƯƠNG DỰ KIẾN CỦA KHÓA LUẬN TỐT NGHIỆP")
    add_body("Khóa luận tốt nghiệp dự kiến được cấu trúc thành 05 chương chính theo chuẩn quy định của Trường Đại học Kinh tế Quốc dân và Viện Công nghệ Thông tin & Kinh tế số, thể hiện rõ tính liên ngành giữa Hệ thống Thông tin Quản lý, Phân tích nghiệp vụ ITBA và Kỹ thuật Trí tuệ Nhân tạo ứng dụng do sinh viên tự tay phát triển và thực nghiệm:")
    
    add_bullet(" Tính cấp thiết của đề tài; Mục đích, đối tượng, phạm vi nghiên cứu; Phương pháp nghiên cứu và bố cục khóa luận.", bold_prefix="LỜI MỞ ĐẦU:")
    
    add_bullet(" Tổng quan quy trình siêu âm phụ khoa; Thách thức trong đọc ảnh thủ công; Cơ sở lý thuyết Semantic Segmentation (U-Net, Attention U-Net); Khái niệm mô hình tương tác Người – Máy (Human-in-the-Loop); Tổng quan các nghiên cứu liên quan và khoảng trống nghiên cứu (Research Gap).", bold_prefix="CHƯƠNG 1: TỔNG QUAN BÀI TOÁN VÀ CƠ SỞ LÝ LUẬN:")
    
    add_bullet(" Phân tích bối cảnh và quy trình As-Is; Đề xuất quy trình To-Be tích hợp AI; Khảo sát và chuẩn bị dữ liệu thực tế (307 ảnh Ground Truth từ 185 bệnh nhân); Phân tích Use Cases; Xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS: FR, NFR, User Stories, Acceptance Criteria).", bold_prefix="CHƯƠNG 2: PHÂN TÍCH NGHIỆP VỤ VÀ ĐẶC TẢ YÊU CẦU HỆ THỐNG (GÓC NHÌN ITBA/PO):")
    
    add_bullet(" Pipeline tiền xử lý và chuẩn hóa ảnh (ROI crop, Letterbox resize 512×512, Nearest Neighbor interpolation cho mask); Thiết kế kiến trúc mô hình (Baseline U-Net và Attention U-Net); Thiết lập thực nghiệm, Combo Loss và phân chia tập dữ liệu Patient-level; Kết quả thực nghiệm định lượng, so sánh đối chứng giữa 2 mô hình và phân tích lỗi (Error Analysis).", bold_prefix="CHƯƠNG 3: NGHIÊN CỨU VÀ XÂY DỰNG MÔ HÌNH AI PHÂN ĐOẠN TỔN THƯƠNG BUỒNG TRỨNG:")
    
    add_bullet(" Thiết kế kiến trúc tổng thể (FastAPI Backend + HTML5 Canvas tương tác); Đặc tả API RESTful; Thiết kế giao diện người dùng và bộ công cụ tương tác Canvas; Hiện thực hóa các chức năng cốt lõi (Upload → AI Segment → Overlay → Chỉnh sửa Mask → Xác nhận & Lưu kết quả).", bold_prefix="CHƯƠNG 4: THIẾT KẾ VÀ XÂY DỰNG HỆ THỐNG WEB PROTOTYPE HỖ TRỢ BÁC SĨ (HUMAN-IN-THE-LOOP):")
    
    add_bullet(" Kịch bản thử nghiệm và môi trường đánh giá; Đánh giá hiệu năng mô hình AI; Đánh giá tính hữu dụng (Usability), độ hài lòng và quy trình Human-in-the-Loop với bác sĩ chuyên khoa (SUS Score); Thảo luận về đóng góp thực tiễn và chuyên ngành MIS; Phân tích hạn chế và bài học kinh nghiệm.", bold_prefix="CHƯƠNG 5: THỬ NGHIỆM, ĐÁNH GIÁ KẾT QUẢ VÀ THẢO LUẬN:")
    
    add_bullet(" Tóm tắt các kết quả đạt được; Khẳng định mức độ hoàn thành so với mục tiêu ban đầu; Kiến nghị và đề xuất hướng phát triển mở rộng trong tương lai.", bold_prefix="KẾT LUẬN VÀ KIẾN NGHỊ:")
    
    add_bullet(" Danh mục tài liệu tham khảo (chuẩn IEEE/APA); Phụ lục 1: Mẫu phiếu khảo sát đánh giá của bác sĩ (SUS Questionnaire); Phụ lục 2: Bảng thống kê dữ liệu thực nghiệm chi tiết; Phụ lục 3: Tài liệu đặc tả SRS chi tiết; Phụ lục 4: Hướng dẫn cài đặt và mã nguồn hệ thống.", bold_prefix="DANH MỤC TÀI LIỆU THAM KHẢO & PHỤ LỤC:")

    # Signature section
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    sig_table = doc.add_table(rows=1, cols=2)
    sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(sig_table, color="FFFFFF")

    c_left, c_right = sig_table.rows[0].cells
    c_left.width = Inches(3.3)
    c_right.width = Inches(3.3)

    p_l = c_left.paragraphs[0]
    p_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_l1 = p_l.add_run("Ý KIẾN CỦA GIẢNG VIÊN HƯỚNG DẪN\n\n\n\n\n")
    r_l1.bold = True
    r_l1.font.size = Pt(11)
    r_l2 = p_l.add_run("ThS. Trần Thanh Hải")
    r_l2.bold = True
    r_l2.font.size = Pt(11.5)

    p_r = c_right.paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_r1 = p_r.add_run("Hà Nội, ngày 02 tháng 09 năm 2026\nSINH VIÊN THỰC HIỆN\n\n\n\n\n")
    r_r1.bold = True
    r_r1.font.size = Pt(11)
    r_r2 = p_r.add_run("Nguyễn Hữu Dũng")
    r_r2.bold = True
    r_r2.font.size = Pt(11.5)

    # Save to workspace path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "MSV_11235559_NguyenHuuDung_DeCuongSoBo_KLTN.docx")
    doc.save(out_path)
    print(f"Successfully generated proposal document at: {out_path}")

if __name__ == "__main__":
    build_de_cuong_doc()
