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
    r_sub = sub_p.add_run("Chuyên ngành: Hệ thống Thông tin Quản lý (MIS) – Khóa 65\n")
    r_sub.italic = True
    r_sub.font.size = Pt(11.5)
    r_sub.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # Info Table Box
    info_table = doc.add_table(rows=5, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(info_table, color="B0C4DE")

    info_data = [
        ("Sinh viên thực hiện:", "Nguyễn Hữu Dũng — Mã SV: 11235559 — Lớp: HTTTQL 65A"),
        ("Giảng viên hướng dẫn:", "TS. Trần Triệu Hải"),
        ("Định hướng nghề nghiệp:", "IT Business Analyst (ITBA) / Product Owner (PO)"),
        ("Bối cảnh / Nơi thực tập:", "Vinmec Times City / VinSmart Future (Môi trường nghiên cứu & nghiệp vụ)"),
        ("Thời hạn nộp đề cương:", "23h59 Chủ nhật, ngày 30/08/2026")
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

    # --- 1. TÊN ĐỀ TÀI DỰ KIẾN ---
    add_heading_1("1. TÊN ĐỀ TÀI DỰ KIẾN (ĐỀ XUẤT 03 PHƯƠNG ÁN THEO THỨ TỰ ƯU TIÊN)")
    add_body("Dựa trên kết quả rà soát dữ liệu thực tế, định hướng chỉ đạo của Giảng viên hướng dẫn và mục tiêu chuyên ngành Hệ thống Thông tin Quản lý (MIS) kết hợp vai trò IT Business Analyst (ITBA) / Product Owner (PO), sinh viên xin đề xuất 03 phương án tên đề tài như sau:")
    
    add_bullet(" “Xây dựng hệ thống thông tin hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”", bold_prefix="Phương án 1 (Ưu tiên số 1 – Đề xuất chính thức):")
    add_body("• Lý do ưu tiên cao nhất: Tên đề tài thể hiện trọn vẹn 3 trụ cột cốt lõi của một đề tài KLTN xuất sắc ngành MIS: (1) Xây dựng hệ thống thông tin hoàn chỉnh giải quyết bài toán nghiệp vụ y tế thực tế; (2) Ứng dụng kỹ thuật AI/Deep Learning cốt lõi (Semantic Segmentation) khoanh vùng chính xác ranh giới tổn thương; (3) Tích hợp mô hình tương tác Người – Máy (Human-in-the-Loop: Bác sĩ trực tiếp rà soát, tinh chỉnh và phê duyệt kết quả), bảo đảm tính an toàn y tế, nâng cao năng suất và giữ vững quyền kiểm soát chuyên môn tối cao của bác sĩ.", italic=True)

    add_bullet(" “Nghiên cứu ứng dụng Deep Learning trong phân đoạn ảnh siêu âm và xây dựng hệ thống hỗ trợ bác sĩ khoanh vùng tổn thương buồng trứng”", bold_prefix="Phương án 2 (Ưu tiên số 2):")
    add_body("• Lý do lựa chọn: Nhấn mạnh vào khía cạnh nghiên cứu kỹ thuật mô hình Deep Learning phân đoạn ảnh y tế và phát triển hệ thống phần mềm hỗ trợ ra quyết định lâm sàng (Clinical Decision Support System – CDSS).", italic=True)

    add_bullet(" “Ứng dụng mô hình phân đoạn ảnh học sâu hỗ trợ chuẩn hóa quy trình khoanh vùng và xác nhận tổn thương buồng trứng”", bold_prefix="Phương án 3 (Ưu tiên số 3):")
    add_body("• Lý do lựa chọn: Tiếp cận từ góc độ tối ưu hóa và chuẩn hóa quy trình nghiệp vụ (Business Process Optimization & Data Governance) trong công tác chẩn đoán hình ảnh sản phụ khoa tại cơ sở y tế.", italic=True)

    # --- 2. VẤN ĐỀ NGHIÊN CỨU ---
    add_heading_1("2. VẤN ĐỀ NGHIÊN CỨU / BÀI TOÁN CẦN GIẢI QUYẾT")
    add_body("Trong quy trình khám và chẩn đoán bệnh lý phụ khoa tại các bệnh viện, siêu âm buồng trứng là kỹ thuật chẩn đoán hình ảnh ban đầu phổ biến và mang tính quyết định nhất. Tuy nhiên, quy trình thực tế hiện đang đối mặt với các thách thức lớn sau:")
    add_bullet(" Ảnh siêu âm buồng trứng có đặc tính vật lý phức tạp: độ tương phản mô mềm thấp, nhiều nhiễu đốm (speckle noise), ranh giới giữa khối u nang và nhu mô lành xung quanh thường mờ nhạt và biến dạng đa dạng. Việc phát hiện và khoanh vùng tổn thương phụ thuộc hoàn toàn vào kinh nghiệm chủ quan và sự tập trung của bác sĩ.", bold_prefix="Thách thức về chuyên môn và chất lượng hình ảnh:")
    add_bullet(" Số lượng bệnh nhân thực hiện siêu âm phụ khoa rất lớn tạo áp lực công việc nặng nề. Việc bác sĩ phải soi xét thủ công từng lát cắt hình ảnh liên tục trong nhiều giờ dễ dẫn đến tình trạng mệt mỏi thị giác, tiềm ẩn nguy cơ bỏ sót tổn thương kích thước nhỏ hoặc đánh giá không đồng nhất giữa các ca khám.", bold_prefix="Áp lực thời gian và nguy cơ sai sót:")
    add_bullet(" Nhiều ứng dụng AI hiện nay dừng lại ở dạng mô hình phân loại 'hộp đen' (Black-box) chỉ đưa ra nhãn dự đoán chung chung mà không chỉ ra căn cứ hình ảnh trực quan, khiến bác sĩ khó kiểm chứng và e ngại khi đưa vào thực tiễn.", bold_prefix="Hạn chế của các giải pháp AI 'hộp đen':")
    add_bullet(" Nghiên cứu và xây dựng giải pháp AI phân đoạn (Semantic Segmentation) tự động phát hiện và khoanh vùng chính xác ranh giới vùng tổn thương trên ảnh siêu âm buồng trứng, trực quan hóa kết quả dưới dạng lớp phủ (Mask/Overlay) minh bạch, và tích hợp vào một hệ thống thông tin theo cơ chế Người – Máy phối hợp (Human-in-the-Loop: Bác sĩ kiểm tra, tinh chỉnh ranh giới nếu cần và phê duyệt kết quả cuối cùng trước khi xuất phiếu kết quả).", bold_prefix="Phát biểu bài toán cốt lõi:")

    # --- 3. MỤC TIÊU NGHIÊN CỨU ---
    add_heading_1("3. MỤC TIÊU TỔNG QUÁT VÀ CÁC MỤC TIÊU CỤ THỂ")
    add_heading_2("3.1. Mục tiêu tổng quát")
    add_body("Nghiên cứu, thiết kế và xây dựng hệ thống thông tin hỗ trợ phân đoạn tổn thương buồng trứng trên ảnh siêu âm ứng dụng mô hình Deep Learning kết hợp cơ chế Human-in-the-Loop, nhằm hỗ trợ bác sĩ khoanh vùng tổn thương nhanh chóng, trực quan, nâng cao tính chuẩn hóa và tối ưu hóa thời gian trong quy trình chẩn đoán hình ảnh phụ khoa.")
    
    add_heading_2("3.2. Các mục tiêu cụ thể")
    add_bullet(" Khảo sát và mô hình hóa quy trình chẩn đoán siêu âm hiện tại (As-Is); thiết kế quy trình nghiệp vụ cải tiến có tích hợp AI (To-Be); xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS) hoàn chỉnh gồm Use Cases, User Stories và tiêu chí nghiệm thu (Acceptance Criteria) theo chuẩn ITBA/PO.", bold_prefix="Mục tiêu 1 (Nghiệp vụ & Yêu cầu hệ thống):")
    add_bullet(" Xử lý làm sạch, chuẩn hóa kích thước ảnh y tế (Letterbox Resize 512×512 bảo toàn tỷ lệ khung hình), khử nhiễu và tổ chức bộ dữ liệu ảnh siêu âm chuẩn có Ground Truth (1.202 ảnh OTU_2D) theo cấu trúc Train/Val/Test độc lập chống rò rỉ dữ liệu (Zero Data Leakage).", bold_prefix="Mục tiêu 2 (Quản lý & Chuẩn hóa dữ liệu):")
    add_bullet(" Nghiên cứu, huấn luyện và thực nghiệm đánh giá các kiến trúc Deep Learning phân đoạn ảnh y tế (Standard U-Net, Attention U-Net, SegFormer), lựa chọn mô hình tối ưu đạt chỉ số phân đoạn cao (Dice Score ≥ 0.82) trên tập kiểm thử độc lập.", bold_prefix="Mục tiêu 3 (Mô hình AI cốt lõi):")
    add_bullet(" Thiết kế và lập trình ứng dụng Web Prototype (FastAPI + HTML5 Interactive Canvas) cho phép tải ảnh siêu âm, chạy mô hình AI phân đoạn theo thời gian thực (< 1 giây/ảnh), hiển thị trực quan Mask/Overlay, cung cấp bộ công cụ cho bác sĩ trực tiếp chỉnh sửa ranh giới mask và xác nhận lưu kết quả / xuất báo cáo chuẩn.", bold_prefix="Mục tiêu 4 (Phát triển hệ thống Web Prototype):")
    add_bullet(" Đo lường hiệu năng kỹ thuật của mô hình (Dice, IoU, Recall) và đánh giá tính khả thi, mức độ cải thiện thời gian thao tác cùng độ hài lòng của bác sĩ chuyên khoa đối với quy trình Human-in-the-Loop (thông qua thang đo SUS Score).", bold_prefix="Mục tiêu 5 (Đánh giá & Kiểm thử nghiệm thu):")

    # --- 4. CÂU HỎI NGHIÊN CỨU ---
    add_heading_1("4. CÂU HỎI NGHIÊN CỨU / CÂU HỎI MÀ SẢN PHẨM CẦN TRẢ LỜI")
    add_bullet(" Quy trình đọc ảnh siêu âm và tương tác giữa bác sĩ với công cụ hỗ trợ AI (To-Be Process) cần được thiết kế và mô hình hóa như thế nào để vừa tối ưu hóa thời gian xử lý, vừa đảm bảo bác sĩ giữ quyền quyết định chuyên môn cao nhất (Human-in-the-Loop)?", bold_prefix="RQ1 (Về quy trình và nghiệp vụ):")
    add_bullet(" Mô hình Deep Learning phân đoạn nào (Standard U-Net, Attention U-Net hay SegFormer) và kỹ thuật tiền xử lý/chuẩn hóa dữ liệu nào đạt hiệu năng cao nhất (về Dice, IoU) trên tập dữ liệu ảnh siêu âm buồng trứng có độ tương phản thấp và kích thước không đồng nhất?", bold_prefix="RQ2 (Về giải thuật và mô hình AI):")
    add_bullet(" Hệ thống phần mềm cần cung cấp những tính năng giao diện và công cụ tương tác trực quan (Interactive Dual-layer Canvas) nào để hỗ trợ bác sĩ rà soát, tinh chỉnh ranh giới tổn thương một cách thuận tiện, nhanh chóng và chính xác?", bold_prefix="RQ3 (Về tính năng phần mềm & Trải nghiệm người dùng):")
    add_bullet(" Khi ứng dụng hệ thống vào thực nghiệm, mức độ đồng thuận của bác sĩ đối với kết quả khoanh vùng của AI (Initial Acceptance Rate) đạt bao nhiêu %, và hệ thống giúp rút ngắn bao nhiêu thời gian hoàn thành ca bệnh so với quy trình khoanh vùng thủ công hoàn toàn?", bold_prefix="RQ4 (Về hiệu quả thực tiễn và tính khả thi):")

    # --- 5. ĐỐI TƯỢNG VÀ PHẠM VI ---
    add_heading_1("5. ĐỐI TƯỢNG VÀ PHẠM VI NGHIÊN CỨU")
    add_heading_2("5.1. Đối tượng nghiên cứu")
    add_bullet(" Quy trình nghiệp vụ đọc, phân tích và trả kết quả ảnh siêu âm buồng trứng tại cơ sở y tế.")
    add_bullet(" Các giải thuật Deep Learning phân đoạn ảnh y tế (Medical Semantic Segmentation: U-Net, Attention U-Net, SegFormer).")
    add_bullet(" Phương pháp luận phân tích yêu cầu (ITBA/PO) và kiến trúc hệ thống thông tin hỗ trợ ra quyết định lâm sàng (CDSS) theo mô hình Human-in-the-Loop.")

    add_heading_2("5.2. Đối tượng sử dụng và thụ hưởng")
    add_bullet(" Bác sĩ chuyên khoa Chẩn đoán hình ảnh, Bác sĩ Sản phụ khoa tại các cơ sở khám chữa bệnh.", bold_prefix="Người dùng trực tiếp:")
    add_bullet(" Bệnh nhân phụ khoa (nhận kết quả nhanh chóng, minh bạch và trực quan hơn), Quản lý khoa phòng/Bệnh viện (chuẩn hóa dữ liệu và nâng cao năng suất khám).", bold_prefix="Đối tượng hưởng lợi gián tiếp:")

    add_heading_2("5.3. Phạm vi nghiên cứu")
    add_bullet(" Bệnh viện Đa khoa Quốc tế Vinmec Times City / VinSmart Future (môi trường sinh viên thực tập và thu thập quy trình nghiệp vụ mẫu).", bold_prefix="Phạm vi không gian & bối cảnh:")
    add_bullet(" Tập trung vào hình ảnh siêu âm buồng trứng 2D B-mode và bài toán phân đoạn/khoanh vùng các khối u nang buồng trứng (Ovarian Tumors/Lesions) trên tập dữ liệu chuẩn OTU_2D (1.202 ảnh có Ground Truth xác thực).", bold_prefix="Phạm vi dữ liệu y tế:")
    add_bullet(" Tập trung vào quy trình tương tác cốt lõi: Tiếp nhận ảnh siêu âm → Tiền xử lý & IQA → Mô hình AI phân đoạn → Lớp phủ Mask/Overlay trực quan → Bác sĩ Review / Tinh chỉnh / Xác nhận (Sign-off) → Xuất phiếu kết quả.", bold_prefix="Phạm vi chức năng phần mềm:")
    add_bullet(" Triển khai giải pháp dưới dạng ứng dụng Web Application Prototype hoàn chỉnh chạy trên môi trường On-Premise/Local phục vụ kiểm chứng thực nghiệm.", bold_prefix="Phạm vi kỹ thuật:")
    add_bullet(" Trong khuôn khổ thời gian thực hiện Khóa luận Tốt nghiệp đại học (khoảng 10–12 tuần).", bold_prefix="Phạm vi thời gian:")

    # --- 6. NGUỒN DỮ LIỆU ---
    add_heading_1("6. NGUỒN DỮ LIỆU / THÔNG TIN SỬ DỤNG (MINH BẠCH & HỌC THUẬT)")
    add_body("Để bảo đảm tính minh bạch học thuật, khả năng tái lập thực nghiệm (Reproducibility) và tuân thủ nghiêm ngặt đạo đức nghiên cứu y tế, đề tài sử dụng kết hợp hai nguồn thông tin:")
    add_bullet(" Bộ dữ liệu chuẩn công khai Ovarian Tumor Ultrasound (OTU_2D Benchmark) gồm 1.202 ảnh siêu âm buồng trứng 2D B-mode có 100% Ground Truth Mask phân đoạn nhị phân đã được các chuyên gia y tế thẩm định và công bố trên các diễn đàn khoa học uy tín.", bold_prefix="1. Nguồn dữ liệu thực nghiệm AI (PUBLIC REAL BENCHMARK):")
    add_bullet(" Quy trình As-Is thực tế, mẫu biểu kết quả siêu âm buồng trứng, tiêu chuẩn thuật ngữ IOTA/O-RADS và khảo sát nghiệp vụ thu thập trực tiếp tại Bệnh viện Đa khoa Quốc tế Vinmec Times City.", bold_prefix="2. Nguồn dữ liệu nghiệp vụ & Phân tích yêu cầu (CLINICAL BUSINESS CONTEXT):")

    add_heading_2("6.1. Bảng cấu trúc phân chia dữ liệu thực nghiệm (Zero-Leakage Data Split)")
    
    data_table = doc.add_table(rows=5, cols=4)
    data_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(data_table, color="B0C4DE")

    headers_data = ["Tập dữ liệu", "Số lượng ảnh", "Tỷ lệ (%)", "Mục đích sử dụng & Cam kết học thuật"]
    for j, h in enumerate(headers_data):
        cell = data_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    rows_data = [
        ("Tập Huấn luyện (Train Set)", "700 ảnh", "58.2%", "Huấn luyện trọng số mô hình Deep Learning (U-Net, Attention U-Net, SegFormer)."),
        ("Tập Thẩm định (Validation Set)", "120 ảnh", "10.0%", "Hiệu chỉnh siêu tham số, chọn lọc Checkpoint tối ưu và kích hoạt Early Stopping."),
        ("Tập Kiểm thử độc lập (Test Set)", "382 ảnh", "31.8%", "Đánh giá hiệu năng khách quan trên tập Held-out Benchmark độc lập (100% Zero-leakage)."),
        ("TỔNG CỘNG (OTU_2D Benchmark)", "1.202 ảnh", "100%", "Toàn bộ 1.202 ảnh đều có Ground Truth nhị phân chuẩn xác, phân định rõ ranh giới u nang.")
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
            elif j in [1, 2]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(val)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(val)
            r.font.size = Pt(10)
            bg_c = "F4F8FC" if i % 2 == 0 else "FFFFFF"
            set_cell_background(cell, bg_c)
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    add_heading_2("6.2. Giải trình các điểm mấu chốt về dữ liệu theo yêu cầu của GVHD")
    add_bullet(" Toàn bộ 1.202 ảnh trong tập OTU_2D đều đã có mặt nạ ranh giới (Ground Truth) được xác nhận bởi các chuyên gia y tế trong công bố gốc. Tập Test Set (382 ảnh) được giữ nguyên vẹn từ bộ benchmark chuẩn để bảo đảm tính công bằng khi so sánh với các nghiên cứu quốc tế.", bold_prefix="1. Tính xác thực của Ground Truth:")
    add_bullet(" Việc phân chia Train (700) – Validation (120) – Test (382) được khóa cứng theo danh sách Case-ID cố định; 100% hình ảnh của cùng một ca bệnh chỉ thuộc duy nhất một tập, loại bỏ hoàn toàn nguy cơ rò rỉ dữ liệu (Data Leakage).", bold_prefix="2. Cam kết phân chia không rò rỉ (Zero-Leakage Split):")
    add_bullet(" Bộ dữ liệu OTU_2D là tập dữ liệu chuyên sâu về bệnh lý khối u buồng trứng (100% ảnh đều có tổn thương). Để giải quyết bài toán chống khoanh vùng giả (False Positive) khi gặp ảnh buồng trứng bình thường không có u, hệ thống tích hợp bộ lọc tiền xử lý chất lượng ảnh (IQA) và cơ chế ngưỡng tin cậy (Confidence Thresholding). Việc mở rộng thu thập thêm tập ảnh buồng trứng bình thường (Negative Controls) được xác định là hướng phát triển tiếp theo.", bold_prefix="3. Giải trình về ảnh âm tính / không có u:")

    # --- 7. PHƯƠNG PHÁP DỰ KIẾN ---
    add_heading_1("7. PHƯƠNG PHÁP DỰ KIẾN THỰC HIỆN")
    add_heading_2("7.1. Phương pháp phân tích nghiệp vụ và quản lý sản phẩm (ITBA/PO Methodology)")
    add_bullet(" Khảo sát hiện trạng, phỏng vấn bác sĩ để vẽ sơ đồ luồng công việc As-Is và thiết kế luồng quy trình To-Be tích hợp công cụ hỗ trợ AI.", bold_prefix="Mô hình hóa quy trình nghiệp vụ (Business Process Modeling):")
    add_bullet(" Xây dựng tài liệu SRS chi tiết gồm Biểu đồ Use Case tổng quát, Use Case Specs, danh mục User Stories có cấu trúc chuẩn và bộ tiêu chí nghiệm thu (Given/When/Then Acceptance Criteria).", bold_prefix="Đặc tả yêu cầu phần mềm (SRS Specification):")
    add_bullet(" Thiết kế giao diện ứng dụng y tế (Medical UI/UX) tối ưu trải nghiệm bác sĩ: hỗ trợ chế độ tương phản cao, thao tác zoom/pan mượt mà, trực quan hóa lớp phủ Mask/Overlay với độ trong suốt tùy chỉnh, và bộ công cụ cọ vẽ/tẩy xóa điều chỉnh mask trực tiếp.", bold_prefix="Thiết kế trải nghiệm người dùng & giao diện tương tác:")

    add_heading_2("7.2. Phương pháp tiền xử lý và chuẩn hóa dữ liệu ảnh y tế (Data Preprocessing)")
    add_bullet(" Tự động/bán tự động phát hiện và cắt bỏ các phần viền đen chứa thông số máy siêu âm, thông tin văn bản bên ngoài quạt quét siêu âm, chỉ giữ lại vùng mô cơ quan cần khảo sát.", bold_prefix="Cắt lọc vùng quan tâm (ROI Cropping):")
    add_bullet(" Do ảnh siêu âm gốc có nhiều kích thước khác nhau (800×600, 1024×768, 640×480...), hệ thống thực hiện Resize đồng thời cả ảnh gốc và mask tương ứng về kích thước chuẩn 512×512 pixel bằng kỹ thuật Letterboxing/Padding (giữ nguyên tỷ lệ khung hình Aspect Ratio, không làm biến dạng hình học của tổn thương). Sử dụng phép nội suy Nearest Neighbor cho Mask để bảo toàn tính nhị phân và Bilinear cho Image.", bold_prefix="Chuẩn hóa kích thước đa dạng (Letterbox Resize 512×512):")
    add_bullet(" Lọc nhiễu đốm bằng bộ lọc thích nghi và chuẩn hóa cường độ điểm ảnh (Min-Max Scaling [0, 1] hoặc Z-score Normalization).", bold_prefix="Chuẩn hóa cường độ điểm ảnh & giảm nhiễu (Intensity Normalization):")
    add_bullet(" Áp dụng các phép biến đổi bảo toàn đặc trưng bệnh học y tế (Lật ngang, xoay nhẹ ±10°, co giãn tỷ lệ nhỏ, điều chỉnh độ tương phản) trên tập Train nhằm nâng cao khả năng khái quát hóa của mô hình.", bold_prefix="Tăng cường dữ liệu an toàn (Data Augmentation):")

    add_heading_2("7.3. Phương pháp xây dựng mô hình Deep Learning phân đoạn (Segmentation Core)")
    add_bullet(" Thử nghiệm và so sánh các kiến trúc mạng Semantic Segmentation tiêu chuẩn trong y tế: Standard U-Net (Kiến trúc nền tảng đối chứng), Attention U-Net (Kiến trúc đề xuất tập trung vào vùng tổn thương tương phản thấp), và SegFormer (Ứng dụng cơ chế Vision Transformer).", bold_prefix="Lựa chọn kiến trúc mô hình:")
    add_bullet(" Sử dụng hàm mất mát kết hợp Combo Loss = L_Dice + L_BCE nhằm khắc phục triệt để hiện tượng mất cân bằng diện tích giữa vùng tổn thương và nền ảnh xung quanh.", bold_prefix="Hàm mất mát tối ưu (Combo Loss):")
    add_bullet(" Sử dụng bộ tối ưu AdamW kết hợp kỹ thuật điều chỉnh tốc độ học Cosine Annealing Learning Rate Scheduler và Early Stopping để chống quá khớp (Overfitting).", bold_prefix="Chiến lược huấn luyện:")

    add_heading_2("7.4. Phương pháp phát triển và tích hợp hệ thống (System Implementation)")
    add_bullet(" Xây dựng theo kiến trúc Client-Server hiện đại. Backend sử dụng Python FastAPI cung cấp RESTful APIs xử lý tiền xử lý và nạp mô hình AI đã tối ưu hóa (PyTorch / ONNX Runtime) cho tốc độ suy luận nhanh (< 1 giây/ảnh).", bold_prefix="Kiến trúc hệ thống:")
    add_bullet(" Xây dựng bằng công nghệ HTML5 Canvas hỗ trợ hiển thị 2 lớp (Dual-layer Canvas: Base Image + Interactive Mask Overlay) cho phép bác sĩ thao tác chỉnh sửa ranh giới mask mượt mà theo thời gian thực.", bold_prefix="Giao diện Frontend tương tác:")

    # --- 8. SẢN PHẨM CỐT LÕI BẮT BUỘC ---
    add_heading_1("8. SẢN PHẨM / KẾT QUẢ CỐT LÕI BẮT BUỘC HOÀN THÀNH (CORE SCOPE)")
    add_body("Bám sát phạm vi bắt buộc đã được Giảng viên hướng dẫn phê duyệt, đề tài cam kết hoàn thành 03 SẢN PHẨM CỐT LÕI sau:")
    
    add_bullet(" Sơ đồ As-Is / To-Be; Tài liệu SRS hoàn chỉnh với 100% Yêu cầu chức năng (FR) và phi chức năng (NFR), Use Case Specs, danh mục User Stories kèm bộ tiêu chí nghiệm thu Acceptance Criteria (Gherkin format).", bold_prefix="Sản phẩm 1: Bộ tài liệu Phân tích Nghiệp vụ và Đặc tả Yêu cầu Hệ thống (SRS)")
    add_bullet(" Trọng số mô hình Attention U-Net đã được huấn luyện hoàn chỉnh trên tập dữ liệu OTU_2D; Báo cáo thực nghiệm so sánh định lượng (Dice, IoU, Precision, Recall) với mô hình đối chứng U-Net; Pipeline tiền xử lý và chuẩn hóa ảnh/mask tự động.", bold_prefix="Sản phẩm 2: Mô hình Deep Learning phân đoạn tổn thương buồng trứng")
    add_bullet(" Ứng dụng Web hoàn chỉnh hỗ trợ quy trình khép kín: Upload ảnh → Tiền xử lý & IQA → AI Segmentation → Xem Mask/Overlay → Tinh chỉnh ranh giới bằng Canvas Tools (Brush, Eraser, Opacity, Zoom/Pan) → Bác sĩ xác nhận (Doctor Sign-off) → Xuất phiếu kết quả siêu âm chuẩn.", bold_prefix="Sản phẩm 3: Ứng dụng Web Prototype hoàn chỉnh hỗ trợ quy trình Human-in-the-Loop")

    # --- 9. PHẦN MỞ RỘNG ---
    add_heading_1("9. PHẦN MỞ RỘNG (NẾU CÒN THỜI GIAN – TÁCH RÕ KHỎI PHẦN BẮT BUỘC)")
    add_body("Nguyên tắc cam kết: Các nội dung dưới đây là hướng nghiên cứu mở rộng, hoàn toàn KHÔNG coi là điều kiện bắt buộc để nghiệm thu sản phẩm cốt lõi. Sinh viên chỉ tiến hành thực hiện khi 03 sản phẩm cốt lõi ở Mục 8 đã hoàn thành 100%, được kiểm thử kỹ lưỡng và đạt chất lượng tốt.")
    
    add_bullet(" Tự động tính toán các thông số hình học của vùng tổn thương từ Mask phân đoạn (đường kính lớn nhất D1, đường kính trực giao D2, diện tích) và tự động điền vào mẫu mô tả kết quả siêu âm hỗ trợ bác sĩ soạn thảo kết luận nhanh chóng.", bold_prefix="9.1. Hướng mở rộng 1: Tự động trích xuất kích thước hình học u (Caliper Extraction)")
    add_bullet(" Xây dựng bảng điều khiển thống kê tổng số ca khám, phân bố kích thước khối u và theo dõi tỷ lệ bác sĩ đồng thuận với kết quả phân đoạn ban đầu của AI (Initial Acceptance Rate) để phản hồi cải tiến mô hình trong các phiên bản tiếp theo.", bold_prefix="9.2. Hướng mở rộng 2: Dashboard Quản trị & Thống kê chất lượng hỗ trợ của AI")

    # --- 10. CÁCH ĐÁNH GIÁ KẾT QUẢ ---
    add_heading_1("10. CÁCH ĐÁNH GIÁ KẾT QUẢ (CHỈ TIÊU, BASELINE, NGƯỜI ĐÁNH GIÁ)")
    
    eval_table = doc.add_table(rows=4, cols=4)
    eval_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(eval_table, color="B0C4DE")

    headers_eval = ["Nhóm sản phẩm / Kết quả", "Chỉ tiêu đánh giá cụ thể", "Baseline / Cơ sở đối chứng", "Phương pháp & Người đánh giá"]
    for j, h in enumerate(headers_eval):
        cell = eval_table.rows[0].cells[j]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    rows_eval = [
        ("Mô hình AI Phân đoạn (Segmentation Core)", 
         "• Dice Similarity Coefficient (DSC ≥ 0.82)\n• Intersection over Union (IoU ≥ 0.70)\n• Precision, Recall / Sensitivity", 
         "• Mô hình Standard U-Net baseline\n• Mặt nạ Ground Truth của bộ OTU_2D Benchmark", 
         "Đo lường định lượng tự động trên tập Test Set độc lập (382 ảnh held-out)."),
        ("Ứng dụng Web & Quy trình Human-in-the-Loop", 
         "• Tỷ lệ bác sĩ chấp nhận ngay (Acceptance Rate)\n• Tỷ lệ ca cần chỉnh sửa nhẹ (< 10% diện tích)\n• Thời gian hoàn thành ca bệnh (Task Completion Time)", 
         "Quy trình bác sĩ quan sát và khoanh vùng tổn thương thủ công từ đầu", 
         "Thực nghiệm đo thời gian và ghi nhận thao tác của bác sĩ chuyên khoa trên các ca thử nghiệm."),
        ("Đánh giá Trải nghiệm & Độ hữu dụng (Usability)", 
         "• Điểm thang đo khả năng sử dụng hệ thống (SUS Score ≥ 75/100)\n• Mức độ hài lòng về tính trực quan và độ dễ thao tác", 
         "Quy trình phần mềm PACS/HIS hiện tại chưa có tính năng AI tương tác", 
         "Khảo sát và phỏng vấn Bác sĩ chuyên khoa Chẩn đoán hình ảnh / Sản phụ khoa.")
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
    add_body("Khóa luận tốt nghiệp dự kiến được cấu trúc thành 05 chương chính theo chuẩn quy định của Trường Đại học Kinh tế Quốc dân và Viện Công nghệ Thông tin & Kinh tế số, thể hiện rõ tính liên ngành giữa Hệ thống Thông tin Quản lý, Phân tích nghiệp vụ ITBA và Kỹ thuật Trí tuệ Nhân tạo ứng dụng:")
    
    add_bullet(" Tính cấp thiết của đề tài; Mục đích, đối tượng, phạm vi nghiên cứu; Phương pháp nghiên cứu và bố cục khóa luận.", bold_prefix="LỜI MỞ ĐẦU:")
    
    add_bullet(" Tổng quan quy trình siêu âm phụ khoa; Thách thức trong đọc ảnh thủ công; Cơ sở lý thuyết Semantic Segmentation (U-Net, Attention U-Net, Transformer); Mô hình tương tác Người – Máy (Human-in-the-Loop) trong CDSS; Tổng quan các nghiên cứu liên quan và khoảng trống nghiên cứu (Research Gap).", bold_prefix="CHƯƠNG 1: TỔNG QUAN BÀI TOÁN VÀ CƠ SỞ LÝ LUẬN:")
    
    add_bullet(" Phân tích bối cảnh và quy trình As-Is; Đề xuất quy trình To-Be tích hợp AI; Khảo sát và chuẩn bị dữ liệu OTU_2D Benchmark; Phân tích và mô hình hóa Use Cases; Xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS: FR, NFR, User Stories, Acceptance Criteria).", bold_prefix="CHƯƠNG 2: PHÂN TÍCH NGHIỆP VỤ VÀ ĐẶC TẢ YÊU CẦU HỆ THỐNG (GÓC NHÌN ITBA/PO):")
    
    add_bullet(" Pipeline tiền xử lý và chuẩn hóa ảnh (ROI crop, Letterbox resize 512×512, Nearest Neighbor interpolation cho mask); Thiết kế kiến trúc mô hình (Standard U-Net, Attention U-Net, SegFormer); Thiết lập thực nghiệm, Combo Loss và phân chia tập dữ liệu Zero-Leakage; Kết quả thực nghiệm định lượng, so sánh đối chứng và phân tích lỗi (Error Analysis).", bold_prefix="CHƯƠNG 3: NGHIÊN CỨU VÀ XÂY DỰNG MÔ HÌNH AI PHÂN ĐOẠN TỔN THƯƠNG BUỒNG TRỨNG:")
    
    add_bullet(" Thiết kế kiến trúc tổng thể (FastAPI + HTML5 Canvas); Đặc tả API RESTful; Thiết kế giao diện Medical UI/UX và bộ công cụ tương tác Canvas; Hiện thực hóa các chức năng cốt lõi (Upload → AI Segment → Overlay → Chỉnh sửa Mask → Phê duyệt & Xuất báo cáo); Hướng mở rộng: Trích xuất Caliper và Dashboard quản trị.", bold_prefix="CHƯƠNG 4: THIẾT KẾ VÀ XÂY DỰNG HỆ THỐNG THÔNG TIN HỖ TRỢ BÁC SĨ (PROTOTYPE IMPLEMENTATION):")
    
    add_bullet(" Kịch bản thử nghiệm và môi trường đánh giá; Đánh giá hiệu năng kỹ thuật của mô hình AI; Đánh giá tính hữu dụng (Usability), độ hài lòng và quy trình Human-in-the-Loop với bác sĩ chuyên khoa (SUS Score); Thảo luận về đóng góp thực tiễn và chuyên ngành MIS; Phân tích hạn chế và bài học kinh nghiệm.", bold_prefix="CHƯƠNG 5: THỬ NGHIỆM, ĐÁNH GIÁ KẾT QUẢ VÀ THẢO LUẬN:")
    
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
    r_l2 = p_l.add_run("TS. Trần Triệu Hải")
    r_l2.bold = True
    r_l2.font.size = Pt(11.5)

    p_r = c_right.paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_r1 = p_r.add_run("Hà Nội, ngày 28 tháng 08 năm 2026\nSINH VIÊN THỰC HIỆN\n\n\n\n\n")
    r_r1.bold = True
    r_r1.font.size = Pt(11)
    r_r2 = p_r.add_run("Nguyễn Hữu Dũng")
    r_r2.bold = True
    r_r2.font.size = Pt(11.5)

    out_path = os.path.abspath(r"C:\Users\PeaceD_Dung\Documents\Khóa luận\docs\thesis_proposal\MSV_11235559_NguyenHuuDung_DeCuongSoBo_KLTN.docx")
    doc.save(out_path)
    print(f"Successfully generated proposal document at: {out_path}")

if __name__ == "__main__":
    build_de_cuong_doc()
