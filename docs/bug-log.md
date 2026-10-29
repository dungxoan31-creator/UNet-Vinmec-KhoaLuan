# Nhật ký bug — Workstation HITL

Nguồn ban đầu: baseline trên nhánh `main`. `FIXED` nghĩa là có thay đổi và regression test; kết quả kiểm thử nằm trong [test log](test-log.md). Baseline QA-001 đã từng mở ảnh nguồn thật; mọi lần chạy sau khi sửa đã được chuyển sang dữ liệu tổng hợp/`tmp_path`.

| ID | Vai trò | Mức độ | Trạng thái | Mô tả / bước tái hiện | Nguyên nhân gốc | Ảnh hưởng |
|---|---|---|---|---|---|---|
| QA-001 | QA, Tester, Bảo vệ dữ liệu | Blocker | FIXED | Baseline `pytest` và một số browser/API test dùng ảnh từ split/dataset. | Test fixtures phụ thuộc ảnh nguồn. | Mọi luồng test upload đã chuyển sang fixture tổng hợp; test dataset chạy trong `tmp_path`; guard kiểm tra ranh giới; suite sau sửa chạy trên runtime cô lập. Lịch sử vi phạm baseline được giữ lại tại test log. |
| QA-002 | QA, Dev | Major | FIXED | Dataset tests lỗi khi thiếu `reports/dataset_deduplication_report.csv`. | Test phụ thuộc artifact sinh cục bộ và thư mục dữ liệu thật. | Thay bằng dữ liệu synthetic trong `tmp_path`; không cần artifact dataset có sẵn. |
| QA-003 | Dev, Release QA | Blocker build | FIXED | Dockerfile copy `MODEL_CARD.md`, nhưng file thiếu. | Hồ sơ model không được thêm vào build context. | Đã thêm Model Card theo artifact cấu hình đang có; không tuyên bố hiệu lực lâm sàng. |
| QA-004 | QA, PO | Major | FIXED | Test release-evidence yêu cầu acceptance/handoff docs thiếu. | Trạng thái RUO và giới hạn bằng chứng chưa được ghi. | Đã thêm acceptance/handoff với cổng đánh giá độc lập còn blocked và checklist chưa nghiệm thu. |
| QA-005 | QA, Dev | Major | FIXED | Fixture DICOM phát warning VR; ảnh không deterministic giữa lần sinh. | `PatientAge` sai VR `AS`; RNG không seed. | Dùng `034Y`, seed cố định và regression test xác thực parse/hash. |
| QA-006 | QA, UI/UX | P1 | FIXED | Test kỳ vọng xử lý tiếp ngay sau swap ảnh L/R. | Kịch bản E2E chấp nhận trạng thái xác nhận bên cũ sau thay đổi ảnh. | Luồng xác nhận lại được giữ; test kiểm tra CTA bị khóa trước xác nhận mới. |
| QA-007 | QA, UI/UX | P2 | FIXED | Report overflow ngang tại viewport 390×844 với mã giả danh dài. | Grid track giữ min-content width và chuỗi ID không wrap. | CSS chuyển cột co được và wrap nội dung dài; comprehensive matrix không còn overflow. |
| QA-008 | Backend, Data integrity | P1 | FIXED | Xóa Study đã có telemetry gây lỗi FK; error handler còn truy cập user sau khi session đóng. | `ui_events.case_id` chưa được dọn trước khi xóa study; actor ORM instance bị detach. | Dọn telemetry trong transaction, capture actor username trước khi đóng session; stale telemetry cho case đã xóa bị loại an toàn. Có regression tests. |
| QA-009 | QA, Clinical workflow | P2 | FIXED | Test dot-phrase ghi đè nội dung mẫu rồi mong nội dung cũ xuất hiện trong report; placeholder chưa hoàn tất không được xác nhận bị chặn. | E2E tự mâu thuẫn và chưa khẳng định gate lưu nội dung. | Test giữ nội dung mở rộng, xác nhận placeholder bị chặn trước API, hoàn tất nội dung synthetic, kiểm tra report và xử lý XSS. |
| QA-010 | Intake, Clinical workflow | P1 | FIXED | Sau khi chọn ảnh, hint báo sẵn sàng nhưng CTA phân đoạn vẫn khóa trong mọi ca mới. | `hasImages` được tính một lần khi danh sách ảnh rỗng và không cập nhật khi bác sĩ thêm ảnh. | Readiness giờ kiểm tra danh sách ảnh hiện tại; E2E round-trip chạy được từ intake đến viewer. |
| QA-011 | Viewer, HITL | P1 | FIXED | Đặt caliper D1 ghi JavaScript pageerror sau khi cập nhật số đo. | Viewer gọi `tracker.trackUIEvent`, trong khi `trackUIEvent` là hàm export riêng. | Gọi đúng telemetry API; E2E xác nhận caliper không hiệu chuẩn được lưu và xuất lên A4. |
| QA-012 | Report, Print | P2 | FIXED | Hai ảnh của mỗi ảnh siêu âm bị xếp dọc làm phần bằng chứng tràn trang, phá vỡ phân trang một ảnh mỗi trang. | Cặp ảnh gốc/lớp phủ dùng một cột ở trang A4. | In cặp ảnh cạnh nhau; PDF hai ảnh tổng hợp có một trang tóm tắt và một trang cho mỗi ảnh. |
| QA-013 | Workflow, Network handling | P2 | FIXED | Rời workstation trong khi thao tác “Ca tiếp theo” đang tải có thể hiện toast lỗi tiếng Anh cho request bị route hủy bình thường. | `nextCase` coi `AbortError` do điều hướng như lỗi API và hiển thị nguyên văn thông báo trình duyệt. | Bỏ qua riêng `AbortError`; lỗi API/mạng khác vẫn hiển thị. Round-trip E2E xác nhận không còn error toast khi mở report sau lưu. |

## Quy tắc đóng bug

- Có regression test tái hiện điều kiện cũ và xác nhận hành vi sửa.
- Chạy kiểm tra phù hợp; lưu log và cập nhật `docs/test-log.md`.
- Không thay test bằng skip/xfail, không giảm validate và không dùng dữ liệu bệnh nhân thật để làm pass.

