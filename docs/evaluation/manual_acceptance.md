# Nghiệm thu kỹ thuật thủ công — trạng thái và giới hạn

Tài liệu này mô tả phạm vi cần kiểm tra cho prototype RUO. Nội dung này **không phải nghiệm thu cho codebase hiện tại** và không chứng minh hệ thống sẵn sàng vận hành lâm sàng.

## Trạng thái bằng chứng

- Kiểm tra tự động phải được dẫn bằng log có ngày chạy, mã commit/nhánh, phiên bản trình duyệt và fixture tổng hợp.
- Các tuyên bố về pilot, ZIP export, hoặc khảo sát bác sĩ từ tài liệu cũ là **tuyên bố lịch sử, chưa xác minh ở codebase hiện tại**.
- Chưa có xác nhận bác sĩ lâm sàng cho quy trình hoặc nội dung báo cáo.
- Cổng đánh giá độc lập theo bệnh nhân vẫn `BLOCKED` do chưa xác minh Patient ID nguồn và tính độc lập của tập test.
- Không dùng ảnh bệnh nhân thật cho kiểm thử tự động. E2E chỉ dùng fixture do `scripts/generate_synthetic_e2e_fixtures.py` tạo ra.

## Checklist nghiệm thu kỹ thuật cần bằng chứng

- [ ] Nhận đúng hai ảnh tổng hợp, gán đúng trái/phải và có bước xác nhận khi nguồn mơ hồ.
- [ ] Dừng xử lý đúng khi tệp rỗng, hỏng, sai định dạng, quá giới hạn hoặc DICOM thiếu metadata.
- [ ] Khôi phục được ảnh/mask gốc và mọi nét chỉnh sửa sau undo/redo.
- [ ] Không lưu khi chưa xem cả hai bên, phiên lease mất, revision xung đột hoặc nội dung cảnh báo chưa được xử lý.
- [ ] Phiếu chỉ hiển thị reviewer và revision đã lưu thực tế.
- [ ] Không hiện đơn vị vật lý nếu thiếu calibration.
- [ ] Không có pageerror, console error hoặc lỗi HTTP 500 không mong muốn trong các viewport đã định.

Danh sách kết quả chạy thực tế nằm trong [`../test-log.md`](../test-log.md); các điểm chưa được chứng minh nằm trong [`../known-issues.md`](../known-issues.md).
