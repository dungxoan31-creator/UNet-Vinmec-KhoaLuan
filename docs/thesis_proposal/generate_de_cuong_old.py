import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import docx
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
        ("Bối cảnh / Nơi thực tập:", "Vinmec Times City / VinSmart Future"),
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
        
        set_cell_background(cell_k, "F0F4F8")
        set_cell_background(cell_v, "FFFFFF")
        set_cell_margins(cell_k, 50, 50, 80, 80)
        set_cell_margins(cell_v, 50, 50, 80, 80)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x00, 0x56, 0x91)
        return p

    def add_bullet(text, bold_prefix="", level=0):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2.5)
        p.paragraph_format.line_spacing = 1.25
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.bold = True
        p.add_run(text)
        return p

    # ==================== 1. TÊN ĐỀ TÀI DỰ KIẾN ====================
    add_heading_1("1. TÊN ĐỀ TÀI DỰ KIẾN (ĐỀ XUẤT 03 PHƯƠNG ÁN THEO THỨ TỰ ƯU TIÊN)")
    
    p = doc.add_paragraph()
    p.add_run("Dựa trên kết quả rà soát dữ liệu, ý kiến chỉ đạo của Giảng viên hướng dẫn và định hướng chuyên ngành Hệ thống Thông tin Quản lý (MIS) kết hợp vai trò ITBA/PO, sinh viên xin đề xuất 03 phương án tên đề tài như sau:")

    add_heading_2("Phương án 1 (Ưu tiên số 1 – Đề xuất lựa chọn chính thức):")
    p1 = doc.add_paragraph()
    r = p1.add_run("“Xây dựng hệ thống thông tin hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”")
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor(0x99, 0x00, 0x00)
    add_bullet(" Tên đề tài thể hiện đầy đủ 3 trụ cột của một đề tài KLTN chuyên ngành MIS: (1) Xây dựng hệ thống thông tin hoàn chỉnh giải quyết bài toán nghiệp vụ; (2) Ứng dụng công nghệ AI/Deep Learning cốt lõi (Semantic Segmentation) giải quyết bài toán khoanh vùng tổn thương; (3) Tích hợp mô hình tương tác Người – Máy (Human-in-the-Loop: Bác sĩ xem xét, tinh chỉnh và xác nhận kết quả), đảm bảo giá trị thực tiễn, tính an toàn y tế và sự kiểm soát chuyên môn của bác sĩ.", "Lý do ưu tiên cao nhất:")

    add_heading_2("Phương án 2 (Ưu tiên số 2):")
    p2 = doc.add_paragraph()
    r = p2.add_run("“Nghiên cứu ứng dụng Deep Learning trong phân đoạn ảnh siêu âm và xây dựng hệ thống hỗ trợ bác sĩ chẩn đoán tổn thương buồng trứng”")
    r.bold = True
    r.font.size = Pt(12)
    add_bullet(" Nhấn mạnh vào khía cạnh nghiên cứu mô hình Deep Learning phân đoạn ảnh y tế và phát triển hệ thống phần mềm hỗ trợ ra quyết định lâm sàng (Clinical Decision Support System – CDSS).", "Lý do lựa chọn:")

    add_heading_2("Phương án 3 (Ưu tiên số 3):")
    p3 = doc.add_paragraph()
    r = p3.add_run("“Ứng dụng mô hình phân đoạn ảnh y tế hỗ trợ quy trình khoanh vùng và xác nhận tổn thương buồng trứng tại cơ sở y tế”")
    r.bold = True
    r.font.size = Pt(12)
    add_bullet(" Tiếp cận từ góc độ tối ưu hóa và chuẩn hóa quy trình nghiệp vụ (Business Process Optimization) trong công tác chẩn đoán hình ảnh sản phụ khoa tại bệnh viện.", "Lý do lựa chọn:")

    # ==================== 2. VẤN ĐỀ NGHIÊN CỨU ====================
    add_heading_1("2. VẤN ĐỀ NGHIÊN CỨU / BÀI TOÁN CẦN GIẢI QUYẾT")
    
    p = doc.add_paragraph()
    p.add_run("Trong quy trình khám và chẩn đoán bệnh lý phụ khoa tại các cơ sở y tế, siêu âm buồng trứng là kỹ thuật chẩn đoán hình ảnh ban đầu phổ biến và mang tính quyết định. Tuy nhiên, quy trình thực tế hiện đang đối mặt với các thách thức lớn sau:")

    add_bullet(" Ảnh siêu âm buồng trứng có đặc tính vật lý phức tạp: độ tương phản mô mềm thấp, nhiều nhiễu đốm (speckle noise), ranh giới giữa nang/khối u và mô buồng trứng lành thường mờ nhạt và biến dạng đa dạng. Việc phát hiện và khoanh vùng chính xác tổn thương phụ thuộc hoàn toàn vào kinh nghiệm chủ quan và sự tập trung của bác sĩ.", "Thách thức về chuyên môn và chất lượng hình ảnh:")
    add_bullet(" Số lượng bệnh nhân thực hiện siêu âm phụ khoa rất lớn tạo áp lực công việc nặng nề. Việc bác sĩ phải soi xét thủ công từng lát cắt hình ảnh liên tục trong nhiều giờ dễ dẫn đến tình trạng mệt mỏi thị giác, tiềm ẩn nguy cơ bỏ sót tổn thương kích thước nhỏ hoặc đánh giá không đồng nhất giữa các ca khám.", "Áp lực thời gian và nguy cơ sai sót:")
    add_bullet(" Nhiều ứng dụng AI hiện nay dừng lại ở dạng mô hình phân loại 'hộp đen' (Black-box) chỉ đưa ra nhãn dự đoán chung chung mà không chỉ ra căn cứ hình ảnh trực quan, khiến bác sĩ khó kiểm chứng và e ngại khi đưa vào thực tiễn.", "Hạn chế của các giải pháp AI 'hộp đen':")

    p_stat = doc.add_paragraph()
    r_stat = p_stat.add_run("Phát biểu bài toán cốt lõi: ")
    r_stat.bold = True
    p_stat.add_run("Xây dựng giải pháp AI phân đoạn (Segmentation) tự động phát hiện và khoanh vùng chính xác ranh giới vùng tổn thương trên ảnh siêu âm buồng trứng, trực quan hóa kết quả dưới dạng lớp phủ (Mask/Overlay) minh bạch, và tích hợp vào một ứng dụng hệ thống thông tin theo cơ chế Người – Máy phối hợp (Human-in-the-Loop: Bác sĩ kiểm tra, tinh chỉnh ranh giới nếu cần và phê duyệt kết quả cuối cùng).")

    # ==================== 3. MỤC TIÊU NGHIÊN CỨU ====================
    add_heading_1("3. MỤC TIÊU TỔNG QUÁT VÀ CÁC MỤC TIÊU CỤ THỂ")
    
    add_heading_2("3.1. Mục tiêu tổng quát")
    p = doc.add_paragraph()
    p.add_run("Nghiên cứu, thiết kế và xây dựng hệ thống thông tin hỗ trợ phân đoạn tổn thương buồng trứng trên ảnh siêu âm ứng dụng mô hình Deep Learning kết hợp cơ chế Human-in-the-Loop, nhằm hỗ trợ bác sĩ khoanh vùng tổn thương nhanh chóng, trực quan, nâng cao tính chuẩn hóa và tối ưu hóa thời gian trong quy trình chẩn đoán hình ảnh phụ khoa.")

    add_heading_2("3.2. Các mục tiêu cụ thể")
    add_bullet(" Khảo sát và mô hình hóa quy trình chẩn đoán siêu âm hiện tại (As-Is); thiết kế quy trình nghiệp vụ cải tiến có tích hợp AI (To-Be); xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS) hoàn chỉnh gồm Use Cases, User Stories và tiêu chí nghiệm thu (Acceptance Criteria) theo chuẩn ITBA/PO.", "Mục tiêu 1 (Nghiệp vụ & Yêu cầu hệ thống):")
    add_bullet(" Xử lý làm sạch, chuẩn hóa kích thước đa dạng của ảnh siêu âm, loại bỏ nhiễu ngoài vùng khảo sát (ROI Crop), và tổ chức bộ dữ liệu 307 ảnh siêu âm có Ground Truth đã được bác sĩ chuyên khoa xác nhận theo từng ca/bệnh nhân để phân chia tập Train/Val/Test độc lập chống rò rỉ dữ liệu.", "Mục tiêu 2 (Quản lý & Chuẩn hóa dữ liệu):")
    add_bullet(" Nghiên cứu, huấn luyện và thực nghiệm đánh giá các kiến trúc Deep Learning phân đoạn ảnh y tế (U-Net, Attention U-Net, SegFormer), lựa chọn mô hình tối ưu đạt chỉ số phân đoạn cao (Dice Score ≥ 0.80) trên tập kiểm thử.", "Mục tiêu 3 (Mô hình AI cốt lõi):")
    add_bullet(" Thiết kế và lập trình ứng dụng Web Prototype (FastAPI + React/Next.js/HTML5 Canvas) cho phép tải ảnh siêu âm, chạy mô hình AI phân đoạn theo thời gian thực, hiển thị trực quan Mask/Overlay, cung cấp bộ công cụ cho bác sĩ trực tiếp chỉnh sửa ranh giới mask và xác nhận lưu kết quả.", "Mục tiêu 4 (Phát triển hệ thống Web Prototype):")
    add_bullet(" Đo lường hiệu năng kỹ thuật của mô hình (Dice, IoU, Recall) và đánh giá tính khả thi, mức độ cải thiện thời gian thao tác cùng độ hài lòng của bác sĩ chuyên khoa đối với quy trình Human-in-the-Loop.", "Mục tiêu 5 (Đánh giá & Kiểm thử nghiệm thu):")

    # ==================== 4. CÂU HỎI NGHIÊN CỨU ====================
    add_heading_1("4. CÂU HỎI NGHIÊN CỨU / CÂU HỎI MÀ SẢN PHẨM CẦN TRẢ LỜI")
    
    add_bullet(" Quy trình đọc ảnh siêu âm và tương tác giữa bác sĩ với công cụ hỗ trợ AI (To-Be Process) cần được thiết kế và mô hình hóa như thế nào để vừa tối ưu hóa thời gian xử lý, vừa đảm bảo bác sĩ giữ quyền quyết định chuyên môn cao nhất (Human-in-the-Loop)?", "RQ1 (Về quy trình và nghiệp vụ):")
    add_bullet(" Mô hình Deep Learning phân đoạn nào và kỹ thuật tiền xử lý/chuẩn hóa dữ liệu nào đạt hiệu năng cao nhất (về Dice, IoU) trên tập dữ liệu ảnh siêu âm buồng trứng thực tế có độ tương phản thấp và kích thước không đồng nhất?", "RQ2 (Về giải thuật và mô hình AI):")
    add_bullet(" Hệ thống phần mềm cần cung cấp những tính năng giao diện và công cụ tương tác trực quan (Interactive Mask Editing) nào để hỗ trợ bác sĩ rà soát, tinh chỉnh ranh giới tổn thương một cách thuận tiện, nhanh chóng và chính xác?", "RQ3 (Về tính năng phần mềm & Trải nghiệm người dùng):")
    add_bullet(" Khi ứng dụng hệ thống vào thực nghiệm, mức độ đồng thuận của bác sĩ đối với kết quả khoanh vùng của AI (Acceptance Rate) đạt bao nhiêu %, và hệ thống giúp rút ngắn bao nhiêu thời gian so với quy trình khoanh vùng thủ công hoàn toàn?", "RQ4 (Về hiệu quả thực tiễn và tính khả thi):")

    # ==================== 5. ĐỐI TƯỢNG VÀ PHẠM VI NGHIÊN CỨU ====================
    add_heading_1("5. ĐỐI TƯỢNG VÀ PHẠM VI NGHIÊN CỨU")
    
    add_heading_2("5.1. Đối tượng nghiên cứu")
    add_bullet(" Quy trình nghiệp vụ đọc, phân tích và trả kết quả ảnh siêu âm buồng trứng tại bệnh viện.", "")
    add_bullet(" Các giải thuật Deep Learning phân đoạn ảnh y tế (Medical Semantic Segmentation).", "")
    add_bullet(" Phương pháp luận phân tích yêu cầu (ITBA/PO) và kiến trúc hệ thống thông tin hỗ trợ ra quyết định lâm sàng (CDSS) theo mô hình Human-in-the-Loop.", "")

    add_heading_2("5.2. Đối tượng sử dụng và thụ hưởng")
    add_bullet(" Bác sĩ chuyên khoa Chẩn đoán hình ảnh, Bác sĩ Sản phụ khoa tại các cơ sở khám chữa bệnh.", "Người dùng trực tiếp:")
    add_bullet(" Bệnh nhân phụ khoa (nhận kết quả nhanh chóng, minh bạch và chính xác hơn), Quản lý khoa phòng/Bệnh viện (chuẩn hóa dữ liệu và nâng cao năng suất khám).", "Đối tượng hưởng lợi gián tiếp:")

    add_heading_2("5.3. Phạm vi nghiên cứu")
    add_bullet(" Bệnh viện Đa khoa Quốc tế Vinmec Times City / VinSmart Future (nơi sinh viên thực tập và thu thập dữ liệu/nghiệp vụ mẫu).", "Phạm vi không gian & bối cảnh:")
    add_bullet(" Tập trung vào hình ảnh siêu âm buồng trứng 2D (đường bụng hoặc đầu dò âm đạo) và bài toán phân đoạn/khoanh vùng các tổn thương buồng trứng thường gặp (như u nang buồng trứng, nang bì, u đặc, nang xuất huyết).", "Phạm vi dữ liệu y tế:")
    add_bullet(" Tập trung vào quy trình tương tác cốt lõi: Ảnh siêu âm đầu vào → Tiền xử lý/Chuẩn hóa ảnh → Mô hình AI phân đoạn → Lớp phủ Mask/Overlay trực quan → Bác sĩ Review / Tinh chỉnh / Xác nhận (Sign-off) → Xuất phiếu kết quả.", "Phạm vi chức năng phần mềm:")
    add_bullet(" Triển khai giải pháp dưới dạng ứng dụng Web Application Prototype hoàn chỉnh chạy trên môi trường thử nghiệm (Local/On-Premise Server) phục vụ kiểm chứng thực nghiệm.", "Phạm vi kỹ thuật:")
    add_bullet(" Trong khuôn khổ thời gian thực hiện Khóa luận Tốt nghiệp đại học (khoảng 10–12 tuần).", "Phạm vi thời gian:")

    # ==================== 6. NGUỒN DỮ LIỆU SỬ DỤNG ====================
    add_heading_1("6. NGUỒN DỮ LIỆU / THÔNG TIN SỬ DỤNG (MINH BẠCH & CHI TIẾT)")
    
    p = doc.add_paragraph()
    p.add_run("Nguồn dữ liệu sử dụng trong nghiên cứu là ")
    r = p.add_run("DỮ LIỆU THẬT (REAL DATA)")
    r.bold = True
    p.add_run(", được trích xuất từ hồ sơ ca bệnh siêu âm thực tế tại cơ sở y tế (Vinmec), đã được ")
    r_anom = p.add_run("ẨN DANH HÓA HOÀN TOÀN (100% De-identified)")
    r_anom.bold = True
    p.add_run(" các thông tin định danh bệnh nhân (tên, tuổi, mã viện phí, thông tin bác sĩ) để đảm bảo tuân thủ nghiêm ngặt chuẩn an toàn và đạo đức nghiên cứu y tế.")

    add_heading_2("6.1. Bảng tổng hợp chi tiết hiện trạng dữ liệu và nhãn Ground Truth")
    
    data_table = doc.add_table(rows=7, cols=4)
    data_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(data_table, color="1B365D")

    table_headers = ["Hạng mục dữ liệu", "Số lượng", "Tỷ lệ (%)", "Tình trạng & Mục đích sử dụng"]
    for col_idx, h_text in enumerate(table_headers):
        cell = data_table.rows[0].cells[col_idx]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, 70, 70, 90, 90)
        p_h = cell.paragraphs[0]
        p_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_h = p_h.add_run(h_text)
        r_h.bold = True
        r_h.font.size = Pt(10.5)
        r_h.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    data_rows = [
        ("Tổng số ảnh siêu âm thu thập", "417 ảnh", "100%", "Tổng kho dữ liệu thô hiện có"),
        ("Ảnh có Mask ĐÃ ĐƯỢC BÁC SĨ XÁC NHẬN (Ground Truth chuẩn)", "307 ảnh", "73.6%", "Đủ điều kiện làm Ground Truth chuẩn để Train / Validation / Test"),
        ("Ảnh có Mask ĐANG CHỜ BÁC SĨ XÁC NHẬN (Pending)", "110 ảnh", "26.4%", "Lưu trữ riêng, KHÔNG đưa vào tập kiểm thử Test Set chính thức"),
        ("Số ca bệnh / Bệnh nhân tương ứng với 307 ảnh Ground Truth", "185 bệnh nhân (PID)", "—", "Cơ sở phân chia Train/Val/Test theo Patient-level"),
        ("Số trường hợp Empty Mask trong toàn bộ 417 ảnh", "48 ảnh", "11.5%", "Ảnh buồng trứng bình thường/âm tính (True Negative)"),
        ("Số trường hợp Empty Mask trong 307 ảnh Ground Truth", "35 ảnh", "11.4%", "Dùng huấn luyện mô hình phân biệt ca lành tính, chống False Positive")
    ]

    for row_idx, row_data in enumerate(data_rows):
        row_cells = data_table.rows[row_idx + 1].cells
        bg_color = "F7FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = row_cells[col_idx]
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, 50, 50, 70, 70)
            p_cell = cell.paragraphs[0]
            p_cell.paragraph_format.space_after = Pt(2)
            p_cell.paragraph_format.space_before = Pt(2)
            if col_idx in [1, 2]:
                p_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_cell = p_cell.add_run(text)
            r_cell.font.size = Pt(10.5)
            if row_idx == 1:
                r_cell.bold = True
                r_cell.font.color.rgb = RGBColor(0x00, 0x66, 0x00)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    add_heading_2("6.2. Làm rõ 03 điểm mấu chốt về dữ liệu theo chỉ đạo của GVHD")
    add_bullet(" Trong 417 ảnh đã tạo annotation ban đầu, có đúng 307 ảnh đã được bác sĩ chuyên khoa Chẩn đoán hình ảnh trực tiếp rà soát, chỉnh sửa và xác nhận đạt chuẩn chuyên môn. Đề tài cam kết chỉ sử dụng 307 ảnh này làm Ground Truth cho toàn bộ quá trình thực nghiệm kỹ thuật và kiểm thử mô hình. 110 ảnh còn lại đang chờ phê duyệt sẽ được lưu trữ riêng biệt, không đánh đồng là Ground Truth.", "1. Phân định rõ ràng Ground Truth (307 ảnh) và Pending (110 ảnh):")
    add_bullet(" Tập 307 ảnh Ground Truth thuộc về 185 bệnh nhân (mã PID ẩn danh). Đề tài bắt buộc thực hiện phân chia Train / Validation / Test theo cấp độ Bệnh nhân (Patient-level Split) theo tỷ lệ 70% Train (130 bệnh nhân, ~215 ảnh) – 15% Validation (27 bệnh nhân, ~46 ảnh) – 15% Test (28 bệnh nhân, ~46 ảnh). Toàn bộ ảnh của cùng một bệnh nhân chỉ thuộc duy nhất một tập, loại bỏ 100% nguy cơ rò rỉ dữ liệu (Data Leakage).", "2. Phân chia tập dữ liệu theo cấp độ Bệnh nhân (Patient-level Split):")
    add_bullet(" 48 ảnh 'Empty Mask' trong tập dữ liệu là các trường hợp siêu âm mô buồng trứng bình thường, không có tổn thương/nang/u (True Negative cases). Đây là dữ liệu thực tế vô cùng cần thiết để huấn luyện mô hình AI học được đặc trưng mô lành, giúp tránh việc mô hình bắt buộc phải khoanh vùng giả (False Positive) khi gặp ca khám bình thường. Đây hoàn toàn không phải là lỗi dữ liệu hay annotation chưa hoàn thiện.", "3. Bản chất của 48 trường hợp Empty Mask (Ảnh âm tính chuẩn):")

    # ==================== 7. PHƯƠNG PHÁP DỰ KIẾN ====================
    add_heading_1("7. PHƯƠNG PHÁP DỰ KIẾN THỰC HIỆN")
    
    add_heading_2("7.1. Phương pháp phân tích nghiệp vụ và quản lý sản phẩm (ITBA/PO Methodology)")
    add_bullet(" Khảo sát hiện trạng, phỏng vấn bác sĩ chuyên khoa để vẽ sơ đồ luồng công việc As-Is và thiết kế luồng quy trình To-Be tích hợp công cụ hỗ trợ AI.", "Mô hình hóa quy trình nghiệp vụ (Business Process Modeling):")
    add_bullet(" Xây dựng tài liệu SRS chi tiết gồm Biểu đồ Use Case tổng quát, Use Case Specs, danh mục User Stories có cấu trúc chuẩn (As a... I want to... So that...) và bộ tiêu chí nghiệm thu (Given/When/Then Acceptance Criteria).", "Đặc tả yêu cầu phần mềm (SRS Specification):")
    add_bullet(" Thiết kế giao diện ứng dụng y tế (Medical UI/UX) tối ưu trải nghiệm bác sĩ: hỗ trợ chế độ tương phản cao, thao tác zoom/pan mượt mà, trực quan hóa lớp phủ Mask/Overlay với độ trong suốt tùy chỉnh, và bộ công cụ cọ vẽ/tẩy xóa điều chỉnh mask trực tiếp.", "Thiết kế trải nghiệm người dùng & giao diện tương tác:")

    add_heading_2("7.2. Phương pháp tiền xử lý và chuẩn hóa dữ liệu ảnh y tế (Data Preprocessing)")
    add_bullet(" Tự động/bán tự động phát hiện và cắt bỏ các phần viền đen chứa thông số máy siêu âm, thông tin văn bản bên ngoài quạt quét siêu âm, chỉ giữ lại vùng mô cơ quan cần khảo sát.", "Cắt lọc vùng quan tâm (ROI Cropping):")
    add_bullet(" Do ảnh siêu âm gốc có nhiều kích thước khác nhau (800×600, 1024×768, 640×480...), hệ thống thực hiện Resize đồng thời cả ảnh gốc và mask tương ứng về kích thước chuẩn 512×512 pixel bằng kỹ thuật Letterboxing/Padding (giữ nguyên tỷ lệ khung hình Aspect Ratio, không làm biến dạng hình học của tổn thương).", "Chuẩn hóa kích thước đa dạng (Letterbox Resize 512×512):")
    add_bullet(" Lọc nhiễu đốm bằng bộ lọc thích nghi (Median/Gaussian Filter) và chuẩn hóa cường độ điểm ảnh (Min-Max Scaling [0, 1] hoặc Z-score Normalization).", "Chuẩn hóa cường độ điểm ảnh & giảm nhiễu (Intensity Normalization):")
    add_bullet(" Áp dụng các phép biến đổi bảo toàn đặc trưng bệnh học y tế (Lật ngang, xoay nhẹ ±10°, co giãn tỷ lệ nhỏ, điều chỉnh độ tương phản) trên tập Train nhằm nâng cao khả năng khái quát hóa của mô hình.", "Tăng cường dữ liệu an toàn (Data Augmentation):")

    add_heading_2("7.3. Phương pháp xây dựng mô hình Deep Learning phân đoạn (Segmentation Core)")
    add_bullet(" Thử nghiệm và so sánh các kiến trúc mạng Semantic Segmentation tiêu chuẩn trong y tế: U-Net (Kiến trúc nền tảng), Attention U-Net (Tập trung chú ý vào vùng tổn thương nhỏ), và SegFormer / TransUNet (Ứng dụng cơ chế Vision Transformer).", "Lựa chọn kiến trúc mô hình:")
    add_bullet(" Sử dụng hàm mất mát kết hợp Combo Loss = L_Dice + L_BCE nhằm khắc phục triệt để hiện tượng mất cân bằng diện tích giữa vùng tổn thương và nền ảnh xung quanh.", "Hàm mất mát tối ưu (Combo Loss):")
    add_bullet(" Sử dụng bộ tối ưu AdamW kết hợp kỹ thuật điều chỉnh tốc độ học Cosine Annealing Learning Rate Scheduler và Early Stopping để chống quá khớp (Overfitting).", "Chiến lược huấn luyện:")

    add_heading_2("7.4. Phương pháp phát triển và tích hợp hệ thống (System Implementation)")
    add_bullet(" Xây dựng theo kiến trúc Client-Server hiện đại. Backend sử dụng Python FastAPI cung cấp RESTful APIs xử lý tiền xử lý và nạp mô hình AI đã tối ưu hóa (PyTorch / ONNX Runtime) cho tốc độ suy luận nhanh (< 1 giây/ảnh).", "Kiến trúc hệ thống:")
    add_bullet(" Xây dựng bằng React.js/Next.js kết hợp công nghệ HTML5 Canvas hỗ trợ hiển thị 2 lớp (Dual-layer Canvas: Base Image + Interactive Mask Overlay) cho phép bác sĩ thao tác chỉnh sửa ranh giới mask mượt mà theo thời gian thực.", "Giao diện Frontend tương tác:")

    # ==================== 8. SẢN PHẨM CỐT LÕI BẮT BUỘC ====================
    add_heading_1("8. SẢN PHẨM / KẾT QUẢ CỐT LÕI BẮT BUỘC HOÀN THÀNH (CORE MVP)")
    
    p = doc.add_paragraph()
    p.add_run("Bám sát phạm vi bắt buộc đã được Giảng viên hướng dẫn phê duyệt sau Vòng 2, đề tài cam kết hoàn thành ")
    r_core = p.add_run("03 SẢN PHẨM CỐT LÕI")
    r_core.bold = True
    p.add_run(" sau:")

    sp1_box = doc.add_paragraph()
    r = sp1_box.add_run("Sản phẩm 1: Bộ tài liệu Phân tích Nghiệp vụ và Đặc tả Yêu cầu Hệ thống (SRS)")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    add_bullet(" Sơ đồ quy trình nghiệp vụ As-Is và To-Be (BPMN / Activity Diagram).", "")
    add_bullet(" Tài liệu đặc tả yêu cầu phần mềm (SRS) hoàn chỉnh: Danh mục 100% Yêu cầu chức năng (FR) và phi chức năng (NFR), Use Case Diagram và Use Case Specs chi tiết.", "")
    add_bullet(" Danh mục User Stories có cấu trúc chuẩn kèm bộ tiêu chí nghiệm thu Acceptance Criteria (Gherkin format Given/When/Then).", "")

    sp2_box = doc.add_paragraph()
    r = sp2_box.add_run("Sản phẩm 2: Mô hình Deep Learning phân đoạn tổn thương buồng trứng")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    add_bullet(" Trọng số mô hình AI (Model Weights) đã được huấn luyện hoàn chỉnh trên tập Ground Truth 307 ảnh (chia theo Patient ID).", "")
    add_bullet(" Báo cáo thực nghiệm so sánh hiệu năng các kiến trúc mô hình, phân tích ma trận nhầm lẫn và biểu đồ phân bố chỉ số Dice/IoU.", "")
    add_bullet(" Pipeline tiền xử lý và chuẩn hóa ảnh/mask tự động hóa hoàn toàn từ ảnh thô đầu vào.", "")

    sp3_box = doc.add_paragraph()
    r = sp3_box.add_run("Sản phẩm 3: Ứng dụng Web Prototype hoàn chỉnh hỗ trợ quy trình Human-in-the-Loop")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    add_bullet(" Chức năng tiếp nhận / upload ảnh siêu âm phụ khoa.", "")
    add_bullet(" Chức năng tự động chạy mô hình phân đoạn và hiển thị đồng thời ảnh gốc (Original) và lớp phủ ranh giới tổn thương (Mask/Overlay).", "")
    add_bullet(" Bộ công cụ tương tác Người – Máy (Interactive Canvas) cho phép bác sĩ: Phóng to/thu nhỏ, thay đổi độ mờ đục của mask, dùng công cụ cọ vẽ/tẩy (Brush/Eraser) để tinh chỉnh ranh giới tổn thương theo ý kiến chuyên môn.", "")
    add_bullet(" Chức năng xác nhận phê duyệt kết quả (Doctor Confirm/Sign-off), lưu trữ kết quả và xuất phiếu tóm tắt ca khám (Export Report).", "")

    # ==================== 9. PHẦN MỞ RỘNG ====================
    add_heading_1("9. PHẦN MỞ RỘNG (NẾU CÒN THỜI GIAN – TÁCH RÕ KHỎI PHẦN BẮT BUỘC)")
    
    p = doc.add_paragraph()
    r_commit = p.add_run("Nguyên tắc cam kết: ")
    r_commit.bold = True
    p.add_run("Các nội dung dưới đây là hướng nghiên cứu mở rộng, hoàn toàn KHÔNG coi là điều kiện bắt buộc để nghiệm thu sản phẩm cốt lõi. Sinh viên chỉ tiến hành thực hiện khi 03 sản phẩm cốt lõi ở Mục 8 đã hoàn thành 100%, được kiểm thử kỹ lưỡng và đạt chất lượng tốt.")

    add_heading_2("9.1. Hướng mở rộng 1: Gợi ý văn bản mô tả tổn thương / Dự thảo báo cáo siêu âm (Draft Report Suggestion)")
    add_bullet(" Tự động tính toán các thông số hình học của vùng tổn thương từ Mask phân đoạn (kích thước lớn nhất theo mm/pixel, chu vi, diện tích, độ cản âm trung bình) và tự động điền vào mẫu mô tả kết quả siêu âm chuẩn y khoa hỗ trợ bác sĩ soạn thảo kết luận nhanh chóng.", "Phương án 1 (Dựa trên trích xuất đặc trưng hình học):")
    add_bullet(" (Nếu thu thập đủ mẫu văn bản kết luận ẩn danh và thời gian cho phép) Tích hợp mô hình sinh ngôn ngữ nhỏ (Small LLM/VLM) để gợi ý đoạn văn tóm tắt chẩn đoán sơ bộ cho bác sĩ tham khảo.", "Phương án 2 (Mô hình sinh chẩn đoán phụ trợ):")

    add_heading_2("9.2. Hướng mở rộng 2: Dashboard Quản trị & Thống kê chất lượng hỗ trợ của AI")
    add_bullet(" Xây dựng bảng điều khiển (Dashboard) thống kê tổng số ca khám, phân bố các dạng tổn thương buồng trứng theo thời gian.", "")
    add_bullet(" Thống kê tỷ lệ bác sĩ đồng thuận với kết quả phân đoạn ban đầu của AI (Acceptance Rate) và phân tích các trường hợp bác sĩ phải chỉnh sửa nhiều để phản hồi cải tiến mô hình trong các phiên bản sau.", "")

    # ==================== 10. CÁCH ĐÁNH GIÁ KẾT QUẢ ====================
    add_heading_1("10. CÁCH ĐÁNH GIÁ KẾT QUẢ (CHỈ TIÊU, BASELINE, NGƯỜI ĐÁNH GIÁ)")
    
    eval_table = doc.add_table(rows=4, cols=4)
    eval_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(eval_table, color="1B365D")

    eval_headers = ["Nhóm sản phẩm / Kết quả", "Chỉ tiêu đánh giá cụ thể", "Baseline / Cơ sở đối chứng", "Phương pháp & Người đánh giá"]
    for col_idx, h_text in enumerate(eval_headers):
        cell = eval_table.rows[0].cells[col_idx]
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, 70, 70, 90, 90)
        p_h = cell.paragraphs[0]
        p_h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_h = p_h.add_run(h_text)
        r_h.bold = True
        r_h.font.size = Pt(10.5)
        r_h.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    eval_rows = [
        ("Mô hình AI Phân đoạn (Segmentation Core)", 
         "• Dice Similarity Coefficient (DSC)\n• Intersection over Union (IoU / Jaccard)\n• Precision, Recall / Sensitivity", 
         "• Mô hình U-Net chuẩn (Standard U-Net baseline)\n• Mặt nạ Ground Truth do bác sĩ xác nhận", 
         "Đo lường định lượng tự động trên tập Test Set độc lập (phân chia theo Patient ID)."),
        
        ("Ứng dụng Web & Quy trình Human-in-the-Loop", 
         "• Tỷ lệ bác sĩ chấp nhận ngay kết quả AI (Acceptance Rate)\n• Tỷ lệ ca cần chỉnh sửa nhỏ (< 10% diện tích)\n• Thời gian hoàn thành khoanh vùng ca bệnh (Task Completion Time)", 
         "Quy trình bác sĩ quan sát và khoanh vùng thủ công hoàn toàn từ đầu", 
         "Thực nghiệm đo thời gian và ghi nhận thao tác của bác sĩ trên các ca thử nghiệm."),
        
        ("Đánh giá Trải nghiệm & Độ hữu dụng (Usability)", 
         "• Điểm thang đo khả năng sử dụng hệ thống (SUS Score ≥ 75/100)\n• Mức độ hài lòng về tính trực quan và độ dễ thao tác", 
         "Hệ thống phần mềm PACS/HIS hiện tại chưa có tính năng AI tương tác", 
         "Khảo sát và phỏng vấn chuyên sâu Bác sĩ chuyên khoa Chẩn đoán hình ảnh / Sản phụ khoa tại cơ sở thực tập.")
    ]

    for row_idx, row_data in enumerate(eval_rows):
        row_cells = eval_table.rows[row_idx + 1].cells
        bg_color = "F7FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = row_cells[col_idx]
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, 50, 50, 70, 70)
            p_cell = cell.paragraphs[0]
            p_cell.paragraph_format.space_after = Pt(2)
            p_cell.paragraph_format.space_before = Pt(2)
            r_cell = p_cell.add_run(text)
            r_cell.font.size = Pt(10)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    p_eval_man = doc.add_paragraph()
    r_man = p_eval_man.add_run("Người có chuyên môn đánh giá nghiệm thu: ")
    r_man.bold = True
    p_eval_man.add_run("Bác sĩ chuyên khoa Chẩn đoán hình ảnh / Bác sĩ Sản phụ khoa tại Bệnh viện Đa khoa Quốc tế Vinmec Times City.")

    # ==================== 11. CẤU TRÚC CÁC CHƯƠNG KLTN ====================
    add_heading_1("11. CẤU TRÚC CÁC CHƯƠNG DỰ KIẾN CỦA KHÓA LUẬN TỐT NGHIỆP")
    
    p = doc.add_paragraph()
    p.add_run("Khóa luận tốt nghiệp dự kiến được cấu trúc thành 05 chương chính theo chuẩn quy định của Trường Đại học Kinh tế Quốc dân và Viện Công nghệ Thông tin & Kinh tế số, thể hiện rõ tính liên ngành giữa Hệ thống Thông tin Quản lý, Phân tích nghiệp vụ ITBA và Kỹ thuật Trí tuệ Nhân tạo ứng dụng:")

    chapters = [
        ("LỜI MỞ ĐẦU", [
            "Tính cấp thiết của đề tài trong bối cảnh chuyển đổi số y tế và ứng dụng AI.",
            "Mục đích, đối tượng và phạm vi nghiên cứu của khóa luận.",
            "Phương pháp nghiên cứu và ý nghĩa thực tiễn của đề tài.",
            "Bố cục tổng quan của khóa luận tốt nghiệp."
        ]),
        ("CHƯƠNG 1: TỔNG QUAN BÀI TOÁN VÀ CƠ SỞ LÝ LUẬN", [
            "1.1. Tổng quan về quy trình chẩn đoán hình ảnh siêu âm buồng trứng và các bệnh lý thường gặp.",
            "1.2. Các thách thức trong quy trình đọc ảnh thủ công và nhu cầu ứng dụng công nghệ hỗ trợ.",
            "1.3. Cơ sở lý thuyết về Trí tuệ nhân tạo và Deep Learning trong phân đoạn ảnh y tế (Semantic Segmentation: U-Net, Attention U-Net, Transformer).",
            "1.4. Mô hình tương tác Người – Máy (Human-in-the-Loop) trong Hệ thống hỗ trợ ra quyết định lâm sàng (CDSS).",
            "1.5. Tổng quan các công trình nghiên cứu liên quan trong nước và quốc tế, xác định khoảng trống nghiên cứu (Research Gap)."
        ]),
        ("CHƯƠNG 2: PHÂN TÍCH NGHIỆP VỤ VÀ ĐẶC TẢ YÊU CẦU HỆ THỐNG (GÓC NHÌN ITBA/PO)", [
            "2.1. Phân tích bối cảnh tổ chức và quy trình nghiệp vụ hiện tại (As-Is Business Process).",
            "2.2. Đề xuất quy trình nghiệp vụ cải tiến tích hợp công cụ AI hỗ trợ (To-Be Business Process).",
            "2.3. Khảo sát, thu thập và xây dựng bộ dữ liệu ảnh siêu âm buồng trứng có Ground Truth xác nhận bởi chuyên gia.",
            "2.4. Phân tích và mô hình hóa yêu cầu hệ thống: Biểu đồ Use Case, Use Case Specifications.",
            "2.5. Xây dựng tài liệu đặc tả yêu cầu phần mềm (SRS): Yêu cầu chức năng (FR), Yêu cầu phi chức năng (NFR), Backlog User Stories và Acceptance Criteria."
        ]),
        ("CHƯƠNG 3: NGHIÊN CỨU VÀ XÂY DỰNG MÔ HÌNH AI PHÂN ĐOẠN TỔN THƯƠNG BUỒNG TRỨNG", [
            "3.1. Quy trình tiền xử lý và chuẩn hóa dữ liệu ảnh y tế: Cắt vùng ROI, Letterbox Resize, chuẩn hóa cường độ và tăng cường dữ liệu an toàn.",
            "3.2. Thiết kế kiến trúc các mô hình Deep Learning thử nghiệm (U-Net, Attention U-Net, SegFormer).",
            "3.3. Thiết lập môi trường thực nghiệm, hàm mất mát (Combo Loss) và chiến lược huấn luyện phân chia theo cấp độ Bệnh nhân (Patient-level Split).",
            "3.4. Kết quả thực nghiệm định lượng, phân tích so sánh các mô hình và lựa chọn mô hình tối ưu.",
            "3.5. Phân tích lỗi (Error Analysis), trực quan hóa dự đoán và khả năng giải thích của mô hình."
        ]),
        ("CHƯƠNG 4: THIẾT KẾ VÀ XÂY DỰNG HỆ THỐNG THÔNG TIN HỖ TRỢ BÁC SĨ (PROTOTYPE IMPLEMENTATION)", [
            "4.1. Thiết kế kiến trúc tổng thể hệ thống (System Architecture & Tech Stack: FastAPI + React/Next.js).",
            "4.2. Thiết kế cơ sở dữ liệu và đặc tả API giao tiếp (API Contracts).",
            "4.3. Thiết kế giao diện người dùng (UI/UX) và bộ công cụ tương tác Human-in-the-Loop (Interactive Canvas).",
            "4.4. Hiện thực hóa các chức năng cốt lõi của hệ thống (Upload ảnh → Phân đoạn AI → Xem Overlay → Tinh chỉnh Mask → Phê duyệt & Xuất báo cáo).",
            "4.5. (Hướng mở rộng): Hiện thực hóa tính năng gợi ý văn bản chẩn đoán sơ bộ và Dashboard quản trị."
        ]),
        ("CHƯƠNG 5: THỬ NGHIỆM, ĐÁNH GIÁ KẾT QUẢ VÀ THẢO LUẬN", [
            "5.1. Kịch bản thử nghiệm và môi trường đánh giá hệ thống.",
            "5.2. Đánh giá hiệu năng kỹ thuật của mô hình AI và thời gian phản hồi của hệ thống.",
            "5.3. Đánh giá tính hữu dụng (Usability), độ hài lòng và quy trình Human-in-the-Loop với bác sĩ chuyên khoa.",
            "5.4. Thảo luận về kết quả đạt được, đóng góp của đề tài đối với thực tiễn nghiệp vụ và chuyên ngành MIS.",
            "5.5. Phân tích các hạn chế còn tồn tại và bài học kinh nghiệm."
        ]),
        ("KẾT LUẬN VÀ KIẾN NGHỊ", [
            "Tóm tắt các kết quả chính đã đạt được của khóa luận.",
            "Khẳng định mức độ hoàn thành so với mục tiêu ban đầu.",
            "Kiến nghị và đề xuất hướng phát triển, mở rộng hệ thống trong tương lai."
        ]),
        ("DANH MỤC TÀI LIỆU THAM KHẢO & PHỤ LỤC", [
            "Danh mục tài liệu tham khảo theo chuẩn IEEE / APA.",
            "Phụ lục 1: Mẫu phiếu khảo sát và đánh giá của bác sĩ.",
            "Phụ lục 2: Bảng thống kê dữ liệu ca bệnh và Ground Truth chi tiết.",
            "Phụ lục 3: Tài liệu đặc tả yêu cầu phần mềm (SRS) chi tiết.",
            "Phụ lục 4: Hướng dẫn cài đặt và mã nguồn hệ thống."
        ])
    ]

    for ch_title, ch_items in chapters:
        add_heading_2(ch_title)
        for item in ch_items:
            add_bullet(f" {item}", "")

    # Sign-off box
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    sign_table = doc.add_table(rows=1, cols=2)
    sign_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(sign_table, color="FFFFFF")
    
    cell_l, cell_r = sign_table.rows[0].cells
    cell_l.width = Inches(3.2)
    cell_r.width = Inches(3.4)
    
    pl = cell_l.paragraphs[0]
    pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rl = pl.add_run("Ý KIẾN CỦA GIẢNG VIÊN HƯỚNG DẪN\n\n\n\n\nTS. Trần Triệu Hải")
    rl.bold = True
    rl.font.size = Pt(11)

    pr = cell_r.paragraphs[0]
    pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = pr.add_run("Hà Nội, ngày 26 tháng 08 năm 2026\nSINH VIÊN THỰC HIỆN\n\n\n\nNguyễn Hữu Dũng")
    rr.bold = True
    rr.font.size = Pt(11)

    import os
    output_path = os.path.join(os.path.dirname(__file__), "MSV_11235559_NguyenHuuDung_DeCuongSoBo_KLTN_OLD.docx")
    doc.save(output_path)
    print(f"Document successfully created at {output_path}")

if __name__ == "__main__":
    build_de_cuong_doc()
