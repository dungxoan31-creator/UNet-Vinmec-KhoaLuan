# Roadmap cải tiến workstation HITL

Không gắn mốc thời gian khi chưa có owner, tải triển khai và SLO đã thống nhất.

## Quick wins — đã triển khai

- Chuyển upload E2E/API smoke sang fixture tổng hợp; thêm guard ngăn đường dẫn split/dataset quay lại.
- Sinh PNG/JPEG/DICOM deterministic và sửa metadata DICOM `PatientAge` theo VR.
- Sửa report mobile: ID giả danh dài wrap trong viewport hẹp.
- Hỗ trợ nhiều ảnh tĩnh mỗi bên, cho phép khảo sát một bên khi trạng thái đối bên được ghi rõ; readiness được tính theo danh sách ảnh hiện tại.
- Thêm caliper D1/D2 do bác sĩ đặt bằng hai điểm ảnh nguồn; số đo chưa hiệu chuẩn giữ đơn vị pixel và thắng số đo proxy của mask trong report.
- Thiết kế lại report A4 theo số ảnh: trang tóm tắt, sau đó một trang cho từng ảnh với ảnh gốc/lớp phủ cạnh nhau, số đo và ghi chú tương ứng; RUO và trạng thái chữ ký hiển thị rõ.
- Giữ O-RADS/IOTA ở dữ liệu bác sĩ nhập; không suy Doppler, PCOS hoặc nguy cơ ác tính từ ảnh B-mode/mask thiếu descriptor.
- Huấn luyện classifier nghiên cứu 8 lớp theo ảnh từ nhãn MMOTU chính thức; lưu provenance và chỉ số validation, không đưa checkpoint vào luồng sản phẩm hoặc suy diễn nguy cơ ác tính.
- Giữ PID giả danh qua các phiên bằng database và khóa HMAC ổn định; server cấp Visit No sáu chữ số duy nhất, không tái sử dụng khi xóa ca.
- Sửa xóa case: dọn telemetry gắn study trong transaction và không để handler lỗi truy cập user đã detach.
- Bỏ telemetry đến muộn cho case đã xóa để tránh FK 500.
- Sửa kịch bản đổi bên để kiểm tra xác nhận lại; mở ma trận 5 route × 3 viewport; chụp screenshot cho hai vòng comprehensive.
- Bổ sung Model Card và tài liệu acceptance/handoff nêu rõ RUO, cổng test độc lập và giới hạn bằng chứng.

## Short-term — cần quyết định và nghiệm thu

- Hoàn thiện quy trình vận hành cho khóa HMAC, backup/restore, nhật ký xóa và phục hồi database; ứng dụng đã giữ ổn định PID khi dùng cùng database và khóa.
- Đánh giá năng lực dải Visit No sáu chữ số trước triển khai dài hạn; backend chặn tạo mới bằng 503 khi hết số.
- Chốt descriptor O-RADS/IOTA, ngưỡng đúng 30 mm, Doppler, thể tích, precision/rounding và các trường bắt buộc với chuyên gia lâm sàng.
- Xác minh quyền sử dụng dữ liệu, nguồn/ý nghĩa nhãn và chất lượng ảnh cho các lần huấn luyện nghiên cứu. Patient ID không phải điều kiện chạy training; trước mọi đánh giá patient-independent hoặc cân nhắc sử dụng lâm sàng vẫn cần cohort đánh giá độc lập, mapping phù hợp, hiệu chuẩn và thẩm định chính thức.
- Xác nhận kích thước request thực tế qua app/proxy; kiểm tra chính sách DICOM metadata và burn-in.
- PO/IT đưa SLO p95 và concurrency profile; sau đó mới benchmark giờ cao điểm.
- Thiết kế lại bảng quản trị mobile thành thẻ hoặc chọn cột thiết yếu nếu admin mobile là workflow được hỗ trợ.
- Thực hiện usability review với bác sĩ: thời gian/ca, click count, lỗi laterality, tỷ lệ nhập lại và tần suất scroll.

## Long-term — phụ thuộc kiến trúc/tích hợp

- Tích hợp HIS/RIS cấp PID/Visit No theo phiên khám; đảm bảo idempotency và reconcile khi mất kết nối.
- Chính sách khử định danh DICOM end-to-end gồm metadata, UID, pixel burn-in, audit và xác minh bằng test độc lập trước khi dùng dữ liệu thật.
- Rules O-RADS/IOTA có versioning, provenance, test corpus synthetic/approved và sign-off lâm sàng; thiếu descriptor thì fail closed.
- Luồng phát hành report có quyền ký, chữ ký số, revision bất biến, audit và mẫu in được tổ chức phê duyệt.
- Benchmark và telemetry vận hành không chứa dữ liệu nhận diện; theo dõi p95, lỗi lưu, upload và recovery mà không lấy clinical text làm event payload.
- Chỉ xem xét supervised pilot khi gate đánh giá độc lập theo bệnh nhân được xác minh và có đánh giá lâm sàng chính thức.
