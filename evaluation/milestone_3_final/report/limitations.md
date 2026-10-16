# Giới hạn Hệ thống và Khuyến cáo An toàn Y tế

Tài liệu này xác định các giới hạn kỹ thuật và lâm sàng của nguyên mẫu nghiên cứu Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (Milestone 3).

---

## 1. Bản chất Ngữ nghĩa Y khoa: Bất thường $\neq$ Ác tính
- Mặt nạ phân đoạn (Segmentation Mask) do mô hình AI tạo ra chỉ đại diện cho việc gom cụm các điểm ảnh có hình thái phản âm nghi ngờ u nang hoặc tổn thương cấu trúc buồng trứng.
- Mặt nạ **không** phản ánh chẩn đoán ác tính (Malignancy).
- Việc phân loại u nang lành tính, u giáp biên hay ung thư buồng trứng đòi hỏi tích hợp đầy đủ các tiêu chuẩn lâm sàng IOTA Simple Rules, IOTA ADNEX, O-RADS US v2022 và kết quả giải phẫu bệnh (Histopathology).

## 2. Giới hạn về Độ đo: Pixel Recall $\neq$ Diagnostic Sensitivity
- Chỉ số Pixel Recall đo lường tỷ lệ các pixel tổn thương trong nhãn tham chiếu được mô hình bao phủ.
- Không được đồng nhất Pixel Recall cao với độ nhạy phát hiện ca bệnh (Patient-level Sensitivity). Một tổn thương lớn có thể có Pixel Recall cao nhưng vẫn có thể bị phân loại sai tính chất u.

## 3. Trạng thái Tập Kiểm thử Độc lập (Independent Test Gate)
- Tập kiểm thử 402 ảnh hiện có là **Retrospective Test Replay**, tức là tập dữ liệu đã từng được sử dụng để khảo sát và đánh giá trong quá trình phát triển trước đó.
- Cổng kiểm thử độc lập (`independent_gate`) hiện ở trạng thái **BLOCKED** do thiếu ánh xạ định danh bệnh nhân gốc (`patient_id`) và biên bản kiểm định nguồn độc lập.
- Hệ thống không tuyên bố hoàn thành đánh giá độc lập (`evaluation_complete = False`) khi chưa thỏa mãn các yêu cầu kiểm soát rò rỉ dữ liệu (Data Leakage Guard).

## 4. Khảo sát Người dùng Lâm sàng Chưa Tiến hành (NOT_CONDUCTED)
- Khảo sát tương tác với bác sĩ lâm sàng thực tế được ghi nhận trạng thái trung thực là **NOT_CONDUCTED**.
- Dự án tuyệt đối không đưa vào các đánh giá giả định hoặc điểm Likert tự tạo.
- Tính khả dụng của hệ thống hiện được bảo chứng thông qua Quy trình Nghiệm thu Kỹ thuật (Manual Technical Acceptance) và kiểm thử tự động Live E2E.

## 5. Hiện tượng Ảnh gần trùng xuyên Split (Cross-Split Near Duplicates)
- Các đợt kiểm toán dữ liệu ghi nhận 59 cặp ảnh có độ tương đồng cao giữa tập Train và tập Test/Val do dữ liệu nguồn lịch sử chưa phân tách triệt để cấp bệnh nhân.
- Đây là giới hạn mang tính lịch sử của bộ dữ liệu nguồn và cần được xử lý triệt để trong các đợt thu thập dữ liệu lâm sàng tiếp theo.

## 6. Giới hạn Đo đạc Kích thước và Thể tích 2D
- Tính năng đo kích thước chiều dài, chiều rộng và thể tích u chỉ có giá trị khi ảnh đầu vào là định dạng DICOM chuẩn có trường thông tin `PixelSpacing` đã được máy siêu âm hiệu chuẩn.
- Đối với các ảnh định dạng JPG/PNG thông thường, các phép đo kích thước hiển thị theo đơn vị pixel và chỉ mang tính chất tham khảo tương đối trong phòng thí nghiệm.

## 7. Ranh giới Pháp lý và Mục đích Sử dụng
- Hệ thống là **nguyên mẫu nghiên cứu (Research Prototype)** phục vụ nghiên cứu mô hình tương tác Người và Máy (Human-in-the-Loop) trong chuyên ngành Hệ thống Thông tin Quản lý (MIS).
- Nghiêm cấm sử dụng hệ thống như một thiết bị y tế tự động hoặc làm căn cứ duy nhất để ra quyết định phẫu thuật, chỉ định điều trị hoặc can thiệp lâm sàng trên bệnh nhân thực tế.
