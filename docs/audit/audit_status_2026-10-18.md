# Audit lại ngày 18/10/2026

## Kết luận

Trong **40 mã lỗi ban đầu**: **29 đã sửa trong phạm vi kiểm tra, 11 còn tồn tại/sửa chưa đủ, không còn mục in/report chưa xác minh**.

So với lần kiểm tra trước:

- **BUG-18 đã xác minh bằng trình duyệt thật:** upload hai ảnh → AI → lưu → sửa mask → lưu lần hai đạt revision2 → mở report → gọi window.print thành công.
- **R-02 đã sửa:** fallback đo không còn giả định0,1mm/px; các số đo mm/cm² được để null và calibrated=false khi không đủ dữ liệu.
- **11 lỗi cũ còn lại vẫn tái hiện.** Khóa JWT mặc định công khai trong Docker vẫn còn.
- Pytest hiện tại: **296 pass, 2 skip**, không failure. Các phép thử bổ sung vẫn tái hiện lỗi ngoài bộ test hiện có.

Không sửa mã sản phẩm, không thay database thật, không commit. Chỉ thêm artifacts và báo cáo của lượt kiểm tra này. HEAD vẫn `6e5ac4116eff86becf193214ff92273a94ba02ef`; kết luận áp dụng working tree chưa commit hiện tại, không chỉ nội dung HEAD.

## 11 lỗi vẫn còn

| ID | Lỗi còn lại | Bằng chứng ngày18/10 |
|---|---|---|
| BUG-06 | Hash replay event thiếu prediction_id/client_utc/session_elapsed_ms | Đổi riêng các trường đó vẫn200 duplicate thay vì conflict |
| BUG-09 | GET che trạng thái ABORTED của phiên đã liên kết review | DB ABORTED nhưng response INCOMPLETE |
| BUG-13 | O-RADS và mô tả hình thái mới chưa được lưu đầy đủ | Browser: tách L/R trong RAM đúng nhưng draft/review payload thiếu trường, tải lại mất |
| BUG-19 | Report có số đo vật lý làm mất caliper | Nhánh review có số đo mm thay object measurements, mất lesions/endpoints; browser0 nét thay vì4 |
| BUG-21 | Danh sách vẫn bị cắt200 ca | DB tạm201 study; API trả200, không có study cũ nhất; tra PID frontend vẫn lọc dữ liệu tải sẵn |
| BUG-26 | Reload adapter bỏ threshold đã chọn | Startup0,8 đúng; load_weights→0,5 và pixel xác suất0,6 đổi từ nền sang foreground. Chưa tìm caller reload trong luồng phục vụ hiện tại |
| BUG-29 | Backup resolve đường dẫn tương đối theo cwd thay project root | cwd khác root: APP_DB_PATH tương đối trỏ hai file khác nhau. Backup với đường dẫn tuyệt đối đã restore marker/data đúng |
| BUG-30 | Backup đồng thời có thể ghi chung archive | Hai caller cùng timestamp/chọn tên trước lúc mở file:2SUCCESS nhưng chỉ1backup_path |
| BUG-35 | Đổi/reset mật khẩu chưa thực hiện đúng | UI current_password≠backend old_password→400; invalid reset token vẫn SUCCESS nhưng hash không đổi |
| BUG-36 | Quản trị lệch contract và còn thao tác không thực hiện | create-user500; audit/metadata array≠items/total; settingsPUT405; register model200 nhưng registry không thay đổi |
| BUG-37 | Gửi góp ý chỉ báo thành công | Response200/SUCCESS, không có lưu trữ/dispatch; source không có side effect. Notifications[] đã hết404 nhưng là placeholder |

Root cause và vị trí mã nguồn cụ thể: [backend](../../artifacts/audit18-backend.md), [frontend](../../artifacts/audit18-frontend.md), [AI](../../artifacts/audit18-ai.md). Vị trí backup/config: [backup_service.py](../../backend/services/backup_service.py), [docker-compose.yml](../../docker-compose.yml).

## 29 mã đã sửa hoặc vẫn giữ hành vi đã sửa

| Phạm vi | ID | Bằng chứng hiện tại |
|---|---|---|
| Backend |01,02,03,04,05,07,08,10,11 | Probe mới trên DB tạm: không tự cấp ADMIN; concurrent200/409; lưu nhiều lần; ZIP hash/tên đúng; dedup; completion hai ca cũ; xóa cascade; idempotency/session và prediction membership |
| Frontend |12,14,15,16,17,18,20,22,38 | Browser mock đối chiếu contract thật; riêng18 thêm E2E thật qua hai lần lưu và in. Ngày địa phương kiểm tra source |
| AI/đo đạc |23,24,25,27,28 | Thực thi handler/engine hiện tại:80mm/32cm², đúng trục200/100, đúng padding64/height384, hash cấu hình thật, đúng HD95 |
| Docker/config |31,32,33,34 | Source COPY có đủ, evaluation/manifest được copy/mount, DB/backups có volume, env auth được wire. **Chưa build/start Docker**, và cách dùng secret fallback vẫn có rủi ro riêng R-01 |
| Hạ tầng test |39,40 | Hai failure cũ không còn; full suite296pass2skip |

“Đã sửa” không phải chứng nhận mọi nhánh của module: BUG-14 kiểm tra đúng trigger nhầm số đo giữa hai ảnh; BUG-15 xác minh ngăn session khác study, chưa chứng nhận mọi tình huống cross-user; BUG-23 không tự backfill số đo snapshot cũ; workflow duyệt hai cấp vẫn chưa được kích hoạt.

## Những rủi ro bổ sung từ lần trước

| ID bổ sung | Trạng thái18/10 | Bằng chứng |
|---|---|---|
| **R-01 — P0 nếu dùng cấu hình Docker mặc định** | **Còn** | Secret/password fallback vẫn công khai trong Compose. App/DB tạm cấu hình đúng secret mặc định: tự ký JWT sub=admin, không login, gọi admin audit được200. Không thử vào runtime thật |
| R-02 — fallback giả định spacing | **Đã sửa** |6ca thực thi biểu thức fallback hiện tại: có/không spacing, mask rỗng/không rỗng đều mm/cm²=null và calibrated=false khi fallback |
| R-03 — retry event trước nâng cấp | **Còn** | Event lưu bằng payload hash cũ, replay nguyên event trên code mới trả409 |
| R-04 — session COMPLETED gắn review mới chưa ACK | **Còn** | Save batch mới200, review_batch_id đổi nhưng status vẫn COMPLETED trước ACK batch mới |
| R-05 — đổi password tài khoản env không xác minh password cũ | **Còn** | Token hợp lệ + old password sai + new password1ký tự vẫn200; login bằng password1ký tự200 |

## Phát hiện thêm: giới hạn event chặn cả retry hợp lệ

**N-18-01 — P2:** khi session đã có đúng10.000 event, gửi lại nguyên một event đã lưu nhận **422** thay vì idempotent duplicate200. Kiểm tra giới hạn thực hiện trước khi tính event mới/trùng. Retry không làm tăng số event nhưng vẫn bị chặn. Đã tái hiện trên DB tạm, không tạo10.000 event ở runtime thật. Chi tiết ở [backend report](../../artifacts/audit18-backend.md).

Không cộng R-01..05/N-18-01 vào mẫu số40; đó là nhóm theo dõi bổ sung để tránh thay đổi ý nghĩa số lượng giữa các đợt.

## Sửa kết luận về luồng in/report lần trước

Lần trước BUG-18 để chưa xác minh vì script chuyển report trong khi thao tác save còn busy, bị navigation guard đưa lại viewer. Trace mới ghi nhận script cũ in thông báo “revision2” sớm dù state thực tế còn revision0/busy=true; do cách chờ trạng thái bất đồng bộ của harness. **Đây là lỗi đồng bộ của phép thử, không đủ căn cứ quy thành lỗi điều hướng sản phẩm.**

Harness mới lấy state trước rồi chờ bằng predicate đồng bộ. Log thành công có **hai lượt save**, `PRE_REPORT revision=2, busy=false, dirty=false`, route=report và `window.print()` đã được gọi. Bản trace lỗi cũ được giữ riêng: [async-wait failure](../../artifacts/audit18-frontend-asyncwait-failure.log). Đóng BUG-18 dựa trên phép thử mới, không dựa trên thông báo PASS sớm của harness cũ.

## Bằng chứng thực thi

| Kiểm tra | Kết quả | Log |
|---|---|---|
| Full pytest |296pass,2skip; exit0 |[pytest](../../artifacts/audit18-pytest.txt) |
| Syntax/logic Node hiện có |PASS |[Node](../../artifacts/audit18-node.txt) |
| Backend isolated probe |Exit0; thực thi cả ca fixed và still-present |[log](../../artifacts/audit18-backend.log), [script](../../artifacts/audit18-backend.py) |
| Frontend browser mock |Exit0; kiểm tra mất O-RADS/caliper và contract |[log](../../artifacts/audit18-frontend-mock.log), [script](../../artifacts/audit18-frontend-mock.cjs) |
| Frontend E2E thật, runtime riêng8039 |Upload/AI/save1/edit/save2/report/print PASS |[log](../../artifacts/audit18-frontend-live.log), [script](../../artifacts/audit18-frontend-live.cjs) |
| AI handler/engine check |Exit0;5fixed1still |[log](../../artifacts/audit18-ai-checks.txt), [script](../../artifacts/audit18-ai-checks.py) |
| Fallback + report geometry |Exit0;6fallback cases đúng, caliper nhánh physical vẫn mất |[log](../../artifacts/audit18-ai-client-checks.txt), [script](../../artifacts/audit18-ai-client-checks.cjs) |
| Backup/201ca/default-secret |Exit0; xác nhận cả fixed và residual |[log](../../artifacts/audit18-storage.txt), [script dùng lại không sửa](../../artifacts/reaudit_storage_checks.py) |

Script kiểm chứng residual có thể exit0 vì nó kiểm tra đúng triệu chứng lỗi vẫn tồn tại; không dùng exit0 của probe để kết luận mọi lỗi đã được sửa.

Docker daemon vẫn unavailable khi chạy `docker version`; chưa nghiệm thu build, phân quyền volume hoặc recreate container. Đây là audit chức năng và contract của snapshot hiện tại, không phải thẩm định lâm sàng/kiểm thử tải dài hạn.

## Thứ tự xử lý ngắn gọn

1. Bỏ secret/password mặc định công khai trong Compose; rotate nếu môi trường đã dùng chúng.
2. Sửa lưu O-RADS, caliper report, password và API quản trị thực sự có tác dụng.
3. Đóng lỗi backup/concurrency, replay/session state và danh sách bị cắt200.
