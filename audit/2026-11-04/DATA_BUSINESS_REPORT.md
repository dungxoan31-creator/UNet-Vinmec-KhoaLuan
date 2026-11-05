## 6. Input, dữ liệu sinh tự động và business rules

`field-inventory.json` có 415 occurrence field theo snapshot, **không phải 415 field độc nhất**. Có nhãn, name/id, required, readOnly, value tổng hợp và nhiều kích thước control. Backend models/API được map riêng trong inventory và api-coverage.

| Dữ liệu | Nguồn | Xác minh / vấn đề |
|---|---|---|
| PID 9 số trong intake | crypto random + uniqueness chỉ trong danh bạ local | Read-only trong modal; không phải enterprise patient master, không unique toàn mạng |
| Patient SYN-... | UUID + HMAC mapping server | Stable cùng source string, nhưng thiếu namespace facility: AUD-001 |
| Visit No 6 số | Bộ đếm server gắn Study | Có giá trị trong response; tạo Visit UI đầy đủ/idempotent lost-response chưa chạy |
| VIS code | generate_visit_code cho VisitModel riêng | Không đồng nhất với Study.visit_no; standalone visit APIs NOT TESTED |
| Study code | Server generated | Quan sát response; uniqueness/concurrency chưa stress |
| Ngày giờ khảo sát | Giờ browser local, user sửa được | Form/submit trace đã đọc; timezone roundtrip chưa kiểm thử |
| Tuổi | Current year minus birth_year ở frontend | Không truyền sang case creation; không suy ra independent clinical context |
| Reason | Dropdown mặc định Khác/chưa ghi nhận | Truyền clinical_notes/clinical_indication; không xác nhận đã hỏi bệnh sử |
| Pixel spacing | DICOM/calibration hoặc không có | Synthetic upload ban đầu uncalibrated, nhập 0.1 tạo MANUAL/history; phantom chưa chạy |
| AI confidence | Model score | Uncalibrated, không được hiểu là xác suất bệnh; UI đã có cảnh báo |
| O-RADS | Người dùng chọn | Persist/reopen đúng; rule/clinical validation đầy đủ chưa làm |
| Mô tả/notes | Người dùng nhập | Saved values đi vào report; note chưa lưu không thay note trên report đã lấy server |
| Admin report header | JSON cấu hình | Scope toàn cục và không nối renderer: AUD-002/017 |

Trùng PID cross-facility là lỗi quan hệ dữ liệu; không phải yêu cầu tạo patient ID giả cho training. Training tiếp tục được đánh giá ở image-level, không đòi patient ID hoặc dựng patient ID giả. Không xem local patient danh bạ vận hành là nguồn chứng minh patient-level independence.


See [full report](REPORT.md) and [complete issue register](ISSUE_REGISTER.md) for evidence, priorities and limitations.
