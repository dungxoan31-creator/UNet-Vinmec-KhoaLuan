# BỘ TRI THỨC CHUNG & QUY TẮC LÀM VIỆC MASTER (MASTER PROJECT GUIDELINES)
> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (MIS / ITBA / AI)
> **Phạm vi áp dụng**: Vĩnh viễn cho toàn bộ codebase, tài liệu, đề cương và các tác vụ phát triển phần mềm.

---

## 1. SUPERPOWERS (Quy trình & Kỷ luật Kỹ thuật Chặt chẽ)
* **Brainstorming trước khi thực hiện**: Trước khi thêm tính năng mới hoặc thay đổi kiến trúc lớn, phải làm rõ mục tiêu, yêu cầu nghiệp vụ và phương án kỹ thuật.
* **Systematic Debugging (Chẩn đoán lỗi hệ thống)**: Khi gặp lỗi runtime hoặc test failure, tuyệt đối không đoán mò hay vá lỗi bề mặt (symptom patching). Phải đọc full log, trace đúng nguyên nhân gốc (Root Cause) trước khi sửa code.
* **Verification Before Completion (Xác minh thực nghiệm trước khi công bố)**: Không bao giờ tuyên bố hoàn thành khi chưa chạy lệnh build/test thực tế và thu thập minh chứng log xanh (Pass).
* **Execution Planning**: Đối với các tác vụ đa bước phức tạp, lập kế hoạch chi tiết từng bước (Step-by-step Plan) kèm các checkpoint rà soát.

---

## 2. PONYTAIL (Phong cách Giao tiếp & Báo cáo Súc tích, Trực diện)
* **Ngắn gọn, đi thẳng vào vấn đề**: Loại bỏ câu từ rườm rà, xã giao thừa thãi.
* **Định dạng minh bạch**: Sử dụng Markdown với các tiêu đề rõ ràng, danh mục bullet point và đường dẫn file dạng Clickable Link (`file:///...`).
* **Tổng kết hướng hành động**: Mỗi lượt phản hồi đều tóm tắt ngắn gọn kết quả đã hoàn thành và các bước kế tiếp cụ thể.

---

## 3. ECC - EXPLICIT CONTEXT & CONSTRAINTS (Tuân thủ Ràng buộc & Đặc tả Miền)
* **Không đoán mò Schema / Code Logic**: Phải kiểm tra file nguồn trực tiếp trước khi gọi API, sử dụng biến hoặc chỉnh sửa cấu trúc dữ liệu.
* **Chuẩn hóa Tri thức Y tế**: Tuân thủ tuyệt đối các chuẩn y khoa quốc tế đã định nghĩa trong dự án (IOTA Simple Rules/ADNEX, ACR O-RADS US v2022, ISUOG morphology lexicon).
* **Bảo toàn Phạm vi Cốt lõi (Core Scope)**: Giữ vững các cam kết nghiệp vụ: Patient-Level Data Split (chống Data Leakage), Letterbox 512×512 Resize, Combo Loss ($L_{\text{Dice}} + L_{\text{BCE}}$), và cơ chế rà soát Human-in-the-Loop (HITL).

---

## 4. TASTE-SKILL (Tư duy Thẩm mỹ Code & UX Y tế Tinh tế)
* **Mã nguồn Sạch (Clean Code & Architecture)**: Mô-đun hóa cao, tách biệt rõ ràng giữa Backend (FastAPI), Model Core (PyTorch), CDSS Reasoning Engine và Frontend Canvas.
* **Trải nghiệm Người dùng Y tế (Clinical UI/UX)**: Thiết kế giao diện tương phản tối ưu cho phòng đọc ảnh, thao tác mượt mà (Brush/Eraser/Opacity/Zoom/Pan), trực quan hóa lớp phủ Overlay minh bạch giúp bác sĩ kiểm soát tuyệt đối.

---

## 5. DIAGRAM-DESIGN (Mô hình hóa Trực quan & Sơ đồ Chuẩn hóa)
* **Sử dụng Mermaid Diagram**: Biểu diễn quy trình nghiệp vụ As-Is / To-Be, kiến trúc hệ thống tổng thể, luồng xử lý dữ liệu và Sequence Diagrams bằng Mermaid code block chuẩn GFM.
* **Độ chính xác cú pháp**: Đặt label trong ngoặc ngoặc kép `""` để tránh lỗi cú pháp, đảm bảo sơ đồ trực quan, dễ hiểu từ góc nhìn ITBA/PO.

---

## 6. HUMANIZER (Văn phong Tự nhiên, Chuyên nghiệp & Chuẩn Chuyên ngành)
* **Ngôn ngữ ITBA / PO & MIS Chuyên nghiệp**: Trình bày tài liệu, đặc tả SRS, đề cương khóa luận và báo cáo bằng văn phong mượt mà, học thuật, tự nhiên như chuyên gia kinh tế số & y tế thông minh thực thụ.
* **Loại bỏ Văn phong AI Robot**: Không sử dụng các mẫu câu cứng nhắc, lặp lại sáo rỗng. Văn bản phải có tính thuyết phục, logic chặt chẽ và tự nhiên.

---

## 7. ZERO-HALLUCINATION & CLINICAL PRECISION PROTOCOL (Kỷ luật Chính xác Y tế & Chống Bịa đặt)
* **Xác thực Nguồn Độc lập (Evidence Grounding)**: Tuyệt đối không suy đoán số liệu bệnh nhân, số lượng ảnh, DOI, URL, hoặc giấy phép. Mọi nguồn tài liệu/dataset phải được xác thực từ cổng chính thống (PubMed, RSNA, IOTA Group, GitHub chính thức) và gắn nhãn `[VERIFIED]` / `[PARTIALLY VERIFIED]`.
* **Phân định Rõ ràng Vai trò Dữ liệu**:
  - *Dataset Huấn luyện (AI Training)*: Phải có nhãn mô bệnh học hoặc đồng thuận chuyên gia, mặt nạ pixel-level chuẩn.
  - *Tham chiếu Trực quan (Visual Atlas)*: Radiopaedia/Web Atlas chỉ dùng làm đối chuẩn hình thái định tính, tuân thủ bản quyền CC-BY-NC-SA (không cào dữ liệu huấn luyện ML).
  - *Chuẩn Lâm sàng (Clinical Guidelines)*: O-RADS US v2022 và IOTA Lexicon/ADNEX/Simple Rules dùng làm động cơ suy luận tất định (Deterministic CDSS).
* **Bảo toàn Ngữ nghĩa Y khoa**:
  - Không đồng nhất "Bất thường" với "Ác tính" (Abnormal != Malignant).
  - Phân loại chính xác các mốc kích thước sinh lý ($<30\text{ mm}$ là nang noãn sinh lý) và đặc trưng chỉ điểm lành tính (Bóng cản âm trong u bì/thecoma).
* **Kỷ luật Thực thi Mã nguồn**: Viết code và lưu file thông qua các công cụ file tool chuẩn; không nhúng chuỗi văn bản dài chứa ký tự đặc biệt vào câu lệnh terminal.

---

> **Cam kết**: Tự động áp dụng bộ tri thức này vào mọi tác vụ lập trình, phân tích nghiệp vụ, viết tài liệu và kiểm thử trong dự án.

