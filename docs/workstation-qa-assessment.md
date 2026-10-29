# Đánh giá QA/QC workstation siêu âm buồng trứng HITL

**Phạm vi:** codebase hiện tại trên nhánh `main`
**Bằng chứng:** source review, pytest, JS tests, isolated API/browser E2E và screenshot route matrix. Đây là đánh giá kỹ thuật prototype RUO, không phải xác nhận lâm sàng.

## Kết luận tổng quan

Baseline không thể chấp nhận để tiếp tục test: một số test mở ảnh trong split/dataset thật; suite có bốn lỗi; fixture DICOM phát warning; và luồng xóa ca sau review có thể trả 500 do FK telemetry. Sau sửa, test chạy trong database cô lập và dùng fixture tổng hợp; hai vòng comprehensive liên tiếp, round-trip, safety, viewer, doctor, live UI và browser smoke đều pass. Mobile report đã được sửa hết tràn ngang.

Một đánh giá hoàn chỉnh về tốc độ làm việc 60–100 ca/ngày, hiệu năng giờ cao điểm, nội dung chuyên môn và mức độ hài lòng của bác sĩ chưa có dữ liệu. Không diễn giải pass kỹ thuật thành clinical readiness.

Vòng E2E ngày 2026-10-27 xác nhận intake nhiều ảnh tĩnh, caliper thủ công theo tọa độ ảnh nguồn, lưu/mở lại và report phân trang một ảnh mỗi trang. Vòng này cũng phát hiện ba lỗi tích hợp/runtime được sửa và kiểm tra hồi quy: CTA intake luôn khóa do readiness dùng trạng thái ảnh cũ, telemetry caliper gọi nhầm API, và cặp ảnh bằng chứng khiến PDF tràn trang. Chi tiết nằm trong [test log](test-log.md).

## Điểm theo nhóm

Điểm chỉ mô tả bằng chứng kỹ thuật trong repository; các điểm UI/logic/an toàn không thay thế quan sát bác sĩ.

| Nhóm | Điểm | Căn cứ / giới hạn |
|---|---:|---|
| UI/UX | 7/10 | Đã kiểm tra 5 route × 3 viewport; tìm và sửa report tràn ngang tại 390×844. Chưa có usability study với bác sĩ. |
| Tốc độ thao tác | Chưa đủ dữ liệu đánh giá | Không đo click count, thời gian thao tác trên ca điển hình hoặc mức giảm nhập liệu. |
| Logic nghiệp vụ | 7/10 | Đã test intake, xác nhận laterality sau đổi bên, lưu/reopen report và fail-closed cho review chưa đủ dữ liệu. Quyết định PID/Visit còn mở. |
| Tính đầy đủ chuyên môn | Chưa đủ dữ liệu đánh giá | Chưa có chuyên gia lâm sàng ký duyệt descriptor, report và phạm vi áp dụng O-RADS/IOTA. |
| An toàn bệnh nhân | 7/10 | Có gate hai bên, calibration, lease/revision, review warnings và RUO label; chưa có clinical validation hoặc xác thực độc lập theo bệnh nhân. |
| Hiệu năng | Chưa đủ dữ liệu đánh giá | Chưa thu thập p50/p95, concurrency, thời gian phục hồi hoặc hiệu năng tải ảnh trong giờ cao điểm. |
| Sử dụng giờ cao điểm | Chưa đủ dữ liệu đánh giá | Chưa mô phỏng tải 60–100 lượt/ngày hoặc nhiều người dùng đồng thời. |

## Vấn đề và trạng thái

| ID | Vấn đề đã quan sát | Ảnh hưởng / rủi ro | Ưu tiên | Trạng thái |
|---|---|---|---|---|
| QA-001 | Một số test lấy ảnh từ `dataset/` và `ai_training/.../val.csv`. | Có thể đưa ảnh nguồn vào browser, upload hoặc log test; rủi ro bảo mật dữ liệu. | P0 | Đã chuyển sang fixture/tệp `tmp_path`; có regression guard. Baseline đã từng đọc ảnh nguồn; xem test log. |
| QA-002 | Dataset tests phụ thuộc report/artifact cục bộ và đọc dữ liệu nguồn. | Suite không hermetic, hỏng khi checkout thiếu generated report. | P1 | Builder test chạy trên ảnh tổng hợp trong `tmp_path`. |
| QA-003 | Dockerfile copy `MODEL_CARD.md` nhưng file thiếu. | Build release dừng trước khi tạo image. | P1 | Đã bổ sung Model Card dựa trên artifact trong repository. |
| QA-004 | Tài liệu acceptance/handoff release còn thiếu. | Trạng thái RUO, cổng test độc lập và giới hạn pilot không được bàn giao rõ. | P1 | Đã bổ sung acceptance/handoff với giới hạn bằng chứng. |
| QA-005 | Fixture DICOM có `PatientAge` không đúng VR và generator không seed RNG. | Warning khi parse; E2E không tái lập byte ảnh. | P2 | `034Y`, RNG seed cố định; kiểm tra DICOM và hash PNG lặp lại. |
| QA-006 | Test sau nút đổi bên mong hệ thống cho chạy ngay. | Test vô tình khuyến khích bỏ qua xác nhận trái/phải. | P1 | Giữ xác nhận lại; sửa test để kiểm tra nút khóa và checkbox hai bên. |
| QA-007 | Report có PID giả danh dài làm tràn trang ở 390×844. | Nội dung bị cắt, dễ đọc nhầm mã/chi tiết báo cáo. | P2 | Grid report mobile dùng track co được và wrap mã dài; ma trận xác nhận không tràn. |
| QA-008 | Xóa Study sau HITL thất bại FK từ `ui_events.case_id`; lỗi xử lý tiếp theo đọc `current_user` sau khi đóng session và che root error. | Ca không xóa được, trả 500, test data/telemetry mồ côi. | P1 | Xóa telemetry gắn ca trước Study; chụp actor ID trước rollback/close; thêm test stale event bị loại an toàn. |
| QA-009 | Live E2E kiểm tra report có dot-phrase sau khi test đã ghi đè nội dung; template chưa hoàn tất vẫn được dùng để lưu. | Kỳ vọng test tự mâu thuẫn và không kiểm thử đúng gate nội dung. | P2 | Test giữ nội dung mở rộng, thử lưu khi placeholder còn thiếu, hoàn tất nội dung tổng hợp rồi kiểm tra report/XSS. |
| QA-010 | Sau chọn ảnh, hint báo sẵn sàng nhưng CTA phân đoạn khóa. | `hasImages` được tính một lần khi danh sách còn rỗng. | P1 | Readiness kiểm tra danh sách động; round-trip E2E qua intake/upload thành công. |
| QA-011 | Đặt caliper D1 tạo JavaScript pageerror. | Viewer gọi nhầm `tracker.trackUIEvent`; hàm telemetry được export riêng. | P1 | Sửa API call; E2E xác nhận số đo pixel được lưu và hiện trên report. |
| QA-012 | Cặp ảnh gốc/lớp phủ làm mỗi trang bằng chứng bị tràn. | Bố cục một cột dùng gần hết chiều cao A4. | P2 | Đặt cặp ảnh cạnh nhau; PDF hai ảnh synthetic có đúng ba trang. |
| QA-013 | Rời workstation khi thao tác “Ca tiếp theo” tải dở có thể hiện toast AbortError bằng tiếng Anh. | `nextCase` hiển thị lỗi điều hướng bình thường như lỗi hệ thống. | P2 | Chỉ lọc `AbortError`; các lỗi API khác vẫn báo. Round-trip xác nhận chuyển sang report không để lại error toast. |

Chi tiết bước tái hiện và tiêu chí đóng nằm trong [bug log](bug-log.md). Hạng mục chưa quyết định nằm trong [known issues](known-issues.md) và [câu hỏi đặc tả](spec-questions.md).

## Phản biện hai vai trò

### QA-006 — xác nhận lại laterality sau khi đổi ảnh

**Bác sĩ khó tính:** Đổi bên rồi phải tick lại hai lần là thêm thao tác. Ở ca đông, thao tác thừa làm chậm.

**QA/QC:** Tên file/DICOM là gợi ý, không xác nhận giải phẫu. Đổi bên làm mất căn cứ cho xác nhận cũ; nếu giữ xác nhận, mask và báo cáo có thể gán nhầm trái/phải.

**Giải pháp thống nhất:** Giữ gate hiện tại. Hiển thị hai checkbox ngay cạnh thumbnail, giữ nút phân đoạn khóa cho tới khi bác sĩ xác nhận cả hai. Test kiểm tra cả UI lẫn trạng thái backend sau swap.

### QA-007 — report trên mobile

**Bác sĩ khó tính:** PID dài đẩy nội dung ra ngoài màn hình; phải kéo ngang hoặc đoán phần bị khuất.

**QA/QC:** Grid track mobile có min-content width do chuỗi mã không có điểm ngắt. Lỗi tái hiện ở report route 390×844, document scrollWidth 412 px.

**Giải pháp thống nhất:** Một cột co được trong metadata report và `overflow-wrap:anywhere` cho paragraph chứa định danh. Sau sửa document không vượt viewport; mã dài tự xuống dòng.

### QA-008 — xóa ca sau khi có telemetry

**Bác sĩ khó tính:** Dọn một ca test mà server trả 500 thì không thể nghiệm thu an toàn; thao tác này cũng có thể làm kẹt dữ liệu vận hành.

**QA/QC:** `ui_events.case_id` là FK vào `studies`; luồng delete chỉ dọn HITL sessions/events, review batches và review/prediction. Trace ghi `FOREIGN KEY constraint failed`, sau đó `DetachedInstanceError` trong handler.

**Giải pháp thống nhất:** Xóa UI telemetry thuộc đúng study trong cùng transaction trước khi xóa study. Capture `actor_username` trước khi session đóng. Event telemetry đến muộn cho case đã xóa được bỏ và trả kết quả có số event bị loại, không gây 500.

### QA-009 — nội dung mẫu chưa hoàn tất

**Bác sĩ khó tính:** Mẫu câu phải điền nhanh, nhưng không thể vô tình lưu nguyên dấu ngoặc vuông như mô tả đã xác nhận.

**QA/QC:** Hàm lưu chặn unresolved placeholders; nút lưu không nhất thiết disabled, vì vậy phải kiểm tra toast/cảnh báo và chắc chắn request không tới API.

**Giải pháp thống nhất:** Giữ gate nghiệp vụ, cho phép bác sĩ sửa mẫu trực tiếp; E2E chứng minh placeholder bị chặn, nội dung hoàn tất được lưu và HTML-like text vẫn vô hại.

## To-Be wireframe dạng văn bản

```text
┌ Topbar: tên ứng dụng | ca hiện tại | kết nối | tài khoản
├ Sidebar: Tổng quan | Tiếp nhận | Worklist | Quản trị
└ Nội dung route
   ├ Intake: PID/Visit/date → hai upload card L/R → xác nhận bên → CTA phân đoạn cố định cuối vùng
   ├ Viewer: toolbar | ảnh/canvas chính giữa | panel mô tả và cảnh báo
   │         nút Lưu rà soát và Lưu rồi in luôn kiểm tra seen/revision/content gate
   ├ Report: nhãn RUO → bản nháp nghiên cứu riêng → bản ghi theo từng bên → calibration/reviewer/revision
   └ Admin: tab theo chức năng; bảng dữ liệu có vùng cuộn ngang riêng, không làm tràn toàn trang
```

Đây là mô tả kiểm soát bố cục hiện có, không phải đề xuất thay đổi workflow lâm sàng. Mobile hiện được xác minh không tràn ngang; chưa đánh giá thao tác mobile bằng bác sĩ.

## Cách kiểm tra và nghiệm thu

- Ma trận comprehensive: `dashboard`, `intake`, `viewer`, `report`, `admin` tại 1440×900, 768×1024 và 390×844. Hai vòng đã pass; screenshot tạm được dọn sau khi ghi kết quả vào [test log](test-log.md).
- Hai vòng Playwright liên tiếp: không pageerror, console error, request failure, HTTP 4xx không mong đợi hoặc HTTP 5xx.
- Test API/DB xóa ca có UI event synthetic; kiểm tra Study, ảnh và telemetry liên quan được dọn đúng transaction.
- Test gửi UI telemetry cho case đã xóa không tạo FK exception hoặc HTTP 500.
- Unit/integration chạy trong DB tạm; browser E2E chạy qua `tests/serve_isolated_app.py` và `APP_DATA_DIR` riêng.
- Chưa nghiệm thu performance vì PO/IT chưa đặt SLO p95 và tải đồng thời. Đã có baseline kỹ thuật synthetic 50 lượt trên RTX 3050 4 GB (pipeline preprocessing + inference + postprocessing: p50 340,02 ms, p95 353,39 ms); benchmark này không gồm HTTP, DB, nhiều client, thao tác bác sĩ hoặc dữ liệu lâm sàng. Xem log tại `../artifacts/audit_remediation_2026_10_28/evidence/gpu-full-pipeline-distinct-synthetic-soak-2026-10-29.log`.

Evidence và test count cuối cùng nằm trong [test log](test-log.md), checklist trong [test checklist](test-checklist.md), ticket trong [developer backlog](developer-backlog.md), roadmap trong [roadmap](workstation-roadmap.md).
