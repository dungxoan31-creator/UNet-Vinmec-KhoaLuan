# Developer backlog — QA workstation

Các ticket dưới đây chuyển phát hiện thành tiêu chí có thể triển khai. Ticket `DONE` phải có regression test; ticket `OPEN` cần Product/Clinical/Data Owner hoặc chưa có performance baseline.

## QA-TEST-SYNTHETIC-001 — Chặn ảnh nguồn trong automated test

- **User Story:** Là QA, tôi cần test upload chỉ dùng fixture tổng hợp để không đưa ảnh nguồn vào browser/API test.
- **Business Rules:** Không mở ảnh `dataset/` hay `ai_training/` trong browser/API smoke; unit test ảnh tự sinh trong `tmp_path`; không sửa split/weights.
- **Functional Requirements:** Generator deterministic; helper kiểm tra fixtures tồn tại; guard rà soát nguồn E2E.
- **Validation Rules:** Kiểm tra signature PNG, kích thước 512×512, DICOM parse được, fixture zero/corrupt/oversize thuộc lớp negative.
- **Acceptance Criteria:** Given fixture chưa có, When E2E khởi động, Then chỉ synthetic generator được gọi. Given source path xuất hiện trong test upload, When guard chạy, Then test fail.
- **Test Scenarios:** Fixture thiếu; PNG/JPEG/DICOM đúng; ảnh corrupt; zero-byte; >25 MiB; forbidden dataset path.
- **Dependencies:** Python/OpenCV, pydicom, Node helper.
- **Priority / Status:** P0 / DONE.

## QA-UI-REPORT-001 — In báo cáo A4 hai trang rõ ràng

- **User Story:** Là bác sĩ cần in hoặc lưu PDF, tôi muốn nhận diện nhanh đúng lượt và đối chiếu dữ liệu hai bên mà ảnh không bị thu nhỏ quá mức.
- **Business Rules:** Giữ PID giả danh, Visit No, ngày, revision, trạng thái rà soát, số đo/đơn vị, mô tả đã lưu và cảnh báo RUO; không tự sinh kết luận.
- **Functional Requirements:** Trang 1 hiển thị PID, Visit, ngày khảo sát, mã ca, trạng thái, số đo, O-RADS, mô tả và ghi chú theo bên; trang 2 hiển thị ảnh gốc và lớp phủ theo bên, trạng thái rà soát, model/checkpoint ở cuối trang. Visit xuất hiện ở cả hai trang.
- **Validation Rules:** Chuỗi dài được wrap; mask rỗng được ghi rõ; reviewer/revision chỉ lấy từ bản ghi đã lưu; CSS in A4 ẩn giao diện ứng dụng.
- **Acceptance Criteria:** Given ca tổng hợp có hai bên, When in/Lưu PDF, Then báo cáo có đúng hai trang A4; trang đầu tập trung số đo và ghi nhận lâm sàng; trang hai có ảnh gốc/lớp phủ, model/checkpoint/Reviewer ID ở mục hỗ trợ cuối trang và ghi chú RUO; chữ phân cấp rõ, đầu mục trái/phải dễ nhận ra, thông tin kỹ thuật không nằm ở đầu phiếu và hệ thống không tự sinh kết luận.
- **Test Scenarios:** Hai bên; thiếu mask; chưa rà soát; ghi chú dài; mã dài; Visit No thiếu do legacy; màn hình hẹp; dữ liệu HTML độc hại hiển thị inert.
- **Dependencies:** `frontend/app/report-preview.js`, `frontend/css/report-preview.css`, route report E2E.
- **Priority / Status:** P1 / DONE.

## QA-DATA-DELETE-001 — Xóa telemetry thuộc Study trong transaction

- **User Story:** Là admin, tôi cần xóa case tổng hợp sau test mà FK telemetry không để lại ca lỗi hoặc trả 500.
- **Business Rules:** UI event gắn case bị xóa cùng transaction; giữ audit log của thao tác xóa; không xóa file ngoài upload root.
- **Functional Requirements:** Dọn UIEventModel theo `case_id` trước khi delete Study; lưu `actor_username` trước rollback/session close.
- **Validation Rules:** FK bật; DB rollback không xóa file trước commit; audit log chỉ ghi khi transaction persist.
- **Acceptance Criteria:** Given Study có UI events, When admin delete, Then API trả SUCCESS, Study và events không còn, audit có actor; không còn DB error.
- **Test Scenarios:** Có/không ảnh; có review; telemetry; commit lỗi; rollback lỗi; file ngoài upload root.
- **Dependencies:** `cases.py`, DB schema, `test_case_delete_integrity.py`.
- **Priority / Status:** P1 / DONE.

## QA-HITL-TELEMETRY-001 — Bỏ batch event stale cho case đã xóa

- **User Story:** Là browser đang flush telemetry, tôi cần nhận phản hồi an toàn nếu case đã bị admin xóa trong lúc offline.
- **Business Rules:** Event tham chiếu case không tồn tại không được insert; không làm endpoint thành HTTP 500.
- **Functional Requirements:** Kiểm tra tồn tại case ID theo batch; bỏ event stale và trả `discarded_unknown_case`.
- **Validation Rules:** Batch có ID hợp lệ, thiếu ID, ID bị xóa, hỗn hợp hợp lệ/stale.
- **Acceptance Criteria:** Given case đã xóa, When event đến muộn, Then HTTP 200 với `received=0`, counter bị loại chính xác, không có hàng DB.
- **Test Scenarios:** Một stale event; hỗn hợp; tất cả case hợp lệ; batch rỗng bị schema chặn.
- **Dependencies:** `hitl.py`, `UIEventBatchRequest`, test telemetry.
- **Priority / Status:** P1 / DONE.

## QA-LATERALITY-001 — Xác nhận lại sau swap

- **User Story:** Là bác sĩ, tôi cần thấy ảnh đã đảo và xác nhận lại L/R trước khi chạy.
- **Business Rules:** Gợi ý filename/DICOM không thay xác nhận bác sĩ; đổi bên xóa xác nhận cũ.
- **Functional Requirements:** Hai checkbox theo side; CTA disabled trước khi đủ xác nhận.
- **Validation Rules:** L/R đúng; mismatch; filename không gợi ý; đổi bên nhiều lần.
- **Acceptance Criteria:** Given đã chọn ảnh và xác nhận, When swap, Then cả hai side trở lại trạng thái chưa xác nhận và API không chạy trước khi xác nhận lại.
- **Test Scenarios:** Mismatch; cặp gợi ý; swap; thiếu một side; xác nhận rồi đổi file.
- **Dependencies:** Intake laterality flow, comprehensive E2E.
- **Priority / Status:** P1 / BEHAVIOR VERIFIED; test kỳ vọng cũ đã sửa.

## QA-IDENTITY-001 — Chốt chính sách PID nguồn

- **User Story:** Là người dùng kiểm thử, tôi cần PID giả danh giữ ổn định qua phiên chạy để truy xuất lại lượt cũ.
- **Business Rules:** Dùng HMAC có khóa riêng; giữ khóa và database ổn định; không lưu/in PID nguồn. Admin được xóa ca theo quyền.
- **Functional Requirements:** Cùng PID nguồn ánh xạ đến cùng PID giả danh; Study được lưu trong database bền vững và không có TTL tự động.
- **Validation Rules:** Không xuất PID nguồn qua API response/log; đổi khóa được migration guard chặn.
- **Acceptance Criteria:** Given cùng database và khóa HMAC, When tạo ca qua hai phiên ứng dụng, Then PID giả danh giữ nguyên và ca trước vẫn truy xuất được.
- **Test Scenarios:** Hai phiên `TestClient`; PID số 0 đầu; PID trùng; khóa bị thiếu/thay đổi; admin deletion.
- **Dependencies:** Patient identity HMAC, SQLite startup migration, retention/backup vận hành.
- **Priority / Status:** P1 / DONE — lưu bền vững phụ thuộc giữ database và khóa HMAC.

## QA-VISIT-001 — Xác định nguồn và vòng đời Visit No

- **User Story:** Là bác sĩ tiếp nhận, tôi cần mã lượt duy nhất do hệ thống cấp và được in nhất quán trên phiếu.
- **Business Rules:** Server cấp số sáu chữ số tăng dần cho mỗi Study; uniqueness toàn hệ thống; số đã xóa không dùng lại; không nhận giá trị do client nhập.
- **Functional Requirements:** Lưu Visit No trong DB, trả qua API tạo/list/detail, hiển thị trong intake, worklist và report.
- **Validation Rules:** Unique index; migration backfill ổn định; từ chối trường client gửi; hết dải thì trả 503.
- **Acceptance Criteria:** Given hai lượt được tạo đồng thời cho cùng PID, When lưu, Then có Visit No sáu chữ số khác nhau và cùng số được trả lại sau khi mở lại ca.
- **Test Scenarios:** Tạo đồng thời; restart; migration legacy; xóa lượt; gửi Visit No thủ công; hết dải.
- **Dependencies:** `StudyModel`, sequence migration, case API, intake và report.
- **Priority / Status:** P1 / DONE.

## QA-PERF-001 — Đặt SLO và benchmark giờ cao điểm

- **User Story:** Là quản trị vận hành, tôi cần p50/p95 và tải đồng thời mục tiêu để biết workstation đáp ứng giờ cao điểm.
- **Business Rules:** Không đặt latency target như sự thật nếu chưa có user/load profile.
- **Functional Requirements:** Đo login, mở case, upload, inference, lưu review, report, in, reconnect; ghi tài nguyên máy và kích thước fixture.
- **Validation Rules:** Warm/cold cache; concurrency; timeout; tải 60–100 lượt/ngày theo kịch bản được PO duyệt.
- **Acceptance Criteria:** Given SLO được phê duyệt, When benchmark trên staging, Then report p50/p95/error rate và recovery theo từng endpoint.
- **Test Scenarios:** Giờ cao điểm; worker/model restart; network interruption; upload max size; simultaneous review.
- **Dependencies:** Product/IT SLO, staging, observability.
- **Priority / Status:** P1 / OPEN — chưa có SLO.
