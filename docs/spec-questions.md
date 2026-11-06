# Quyết định đã nhận và câu hỏi còn mở

Không dùng suy đoán kỹ thuật thay cho quyết định nghiệp vụ hoặc lâm sàng. Các câu hỏi này không ngăn việc sửa lỗi độc lập như fixture, test isolation và build.

## Quyền riêng tư và định danh

### Đã xác nhận

- **PID giả danh:** Giữ cùng PID cho cùng PID nguồn qua các phiên và khởi động lại khi database và khóa HMAC ổn định. Không lưu PID nguồn dạng có thể khôi phục. Không tự hết hạn bản ghi; admin vẫn được xóa theo quyền.
- **Visit No:** Backend tự cấp số sáu chữ số duy nhất toàn hệ thống cho mỗi lượt khảo sát. Giá trị lưu trong Study và không nhận từ client. Xóa ca không làm số đã cấp được dùng lại.

### Còn mở

1. **DICOM:** Chính sách bắt buộc cho PatientName, PatientID, StudyDate, UID và burn-in pixel là gì? Prototype hiện lọc metadata text và cảnh báo nhưng không làm sạch pixel.
2. **Vận hành định danh:** Ai sở hữu khóa HMAC, backup/restore, luân chuyển khóa, nhật ký xóa và quy trình phục hồi database? Việc đổi khóa hoặc chuyển sang database khác có thể làm thay đổi PID giả danh.

## Nghiệp vụ lâm sàng

3. **Ngưỡng nang noãn:** Chính sách codebase là `<30 mm`, trong khi bảng ACR O-RADS US v2022 ghi follicle `≤3 cm`. Cách ghi nhận chính thức tại đúng 30 mm là gì và ai là chủ sở hữu chính sách?
4. **Đo thể tích:** Xác nhận dùng `0.523 × d1 × d2 × d3`, vị trí mặt phẳng đo, quy tắc làm tròn, đơn vị và hành vi khi một trục không đo được.
5. **O-RADS/IOTA:** Phiên bản lexicon chính thức, tập trường bắt buộc theo từng loại tổn thương, trạng thái “không áp dụng/không đủ dữ liệu”, và quy trình review/duyệt phiên bản rules là gì? Không tính score khi thiếu descriptor bắt buộc.
6. **Doppler và mô tả:** Trường Color Score, thành phần đặc, nhú, vách, dịch cùng đồ và các descriptor nào bắt buộc theo quy trình cơ sở?
7. **Báo cáo:** Ai được ký/phát hành? Mẫu A4, tên/biểu trưng, timezone, nội dung hành chính và yêu cầu lưu bản đã phát hành nào là bắt buộc? Đây là RUO prototype, không được tự hiển thị như kết quả bệnh viện đã ký.

## Hạ tầng và nghiệm thu

8. **Giới hạn tệp:** Intake hiện hiển thị giới hạn trong UI; xác nhận ngưỡng byte tối đa theo API/proxy và có tính kích thước multipart overhead hay không.
9. **SLO:** PO/IT cần đưa ngưỡng p95 cho mở ca, xem ảnh, lưu review, tạo phiếu, phục hồi sau mất kết nối, cùng tải đồng thời mục tiêu. Chưa có số liệu để tự đặt ngưỡng nghiệm thu.
10. **Thiết bị:** Xác nhận 390×844 mobile là thiết bị thao tác được hay chỉ yêu cầu xem responsive; màn hình tablet có dùng touch/stylus không?
