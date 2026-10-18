# Kiểm tra lại tình trạng sửa 40 lỗi — 17/10/2026

## Kết quả dễ đọc

**28 lỗi đã sửa trong phạm vi kiểm tra; 11 lỗi còn tồn tại hoặc sửa chưa đủ; 1 mục chưa đủ bằng chứng để đóng toàn bộ luồng.** Không thể kết luận “đã fix hết” dù bộ pytest hiện tại xanh.

- Bộ pytest hiện tại: **296 pass, 2 skip**, không failure.
- Kiểm tra logic JavaScript hiện có: PASS.
- Đã chạy lại các phép thử độc lập cho giao dịch, HITL, ZIP, backup, AI và browser.
- Không sửa mã sản phẩm hoặc database thật. Chỉ thêm script/log/báo cáo kiểm tra trong `artifacts` và tài liệu này; giữ nguyên báo cáo cũ.
- Audit trên HEAD `6e5ac4116eff86becf193214ff92273a94ba02ef` cộng working tree hiện tại. Có nhiều thay đổi chưa commit.
- **Docker:** đã kiểm tra nguồn COPY, manifest và volume/env; daemon không chạy nên chưa xác minh build/start/recreate container. “Đã sửa” ở BUG-31–34 chỉ nói về lỗi cấu hình cũ, không xác nhận triển khai thành công hay an toàn.

## 11 mục chưa đóng

| ID cũ | Còn vấn đề gì? | Bằng chứng mới |
|---|---|---|
| **BUG-06** | Hash event vẫn bỏ prediction_id, client_utc và session_elapsed_ms | Đổi riêng các trường này trên replay vẫn 200; các trường type/task/seq đã bị 409 đúng |
| **BUG-09** | Phiên đã gắn review bị che trạng thái ABORTED | DB lưu ABORTED, GET trả INCOMPLETE; phiên chưa gắn review đã đúng |
| **BUG-13** | O-RADS vẫn mất khi lưu/tải lại; mô tả hình thái mới cũng không được lưu | L/R đã tách trong RAM, nhưng draft và review payload thiếu orads/morphologyDesc |
| **BUG-19** | Report của review đã có số đo mm vẫn mất caliper | Nhánh đo lại có 4 nét đúng; nhánh review có số đo vật lý thay object measurements và làm mất lesions/endpoints: browser xác nhận 0 nét |
| **BUG-21** | Chỉ tăng trần danh sách từ 50 lên 200 | Tạo 201 study, API mặc định trả 200 và thiếu study cũ nhất; tra PID vẫn lọc mảng tải sẵn |
| **BUG-26** | Reload trọng số làm mất threshold đã chọn | Khởi tạo 0,8 đúng; gọi adapter.load_weights → 0,5. Chưa tìm caller reload trong luồng sản phẩm hiện tại |
| **BUG-29** | Backup vẫn resolve APP_DB_PATH/APP_DATA_DIR tương đối theo cwd, khác app theo project root | Đường dẫn tuyệt đối đã backup và restore đúng marker/data; đường dẫn tương đối cho hai vị trí khác nhau khi cwd khác root |
| **BUG-30** | Hai backup đồng thời vẫn có thể ghi chung archive | Gọi tuần tự cùng giây đã có hậu tố; ép hai caller cùng chọn tên trước lúc mở archive: cả hai SUCCESS nhưng chỉ 1 backup_path |
| **BUG-35** | Đổi/reset mật khẩu chưa hoạt động đúng | UI gửi current_password, backend đọc old_password → 400; reset với token sai trả SUCCESS mà hash không đổi. Refresh đã hoạt động |
| **BUG-36** | Quản trị còn lệch contract và thao tác giả/thất bại | Audit/metadata trả array nhưng UI cần items/total; tạo user 500 do import sai; register model trả SUCCESS nhưng không lưu; nhiều mutation/settings PUT chưa có |
| **BUG-37** | Thông báo đã hết 404 nhưng góp ý chưa được tiếp nhận thực tế | Notifications trả [] và UI hiển thị rỗng; feedback trả SUCCESS không có lưu trữ/dispatch hoặc side effect |

“Sửa chưa đủ” không có nghĩa bản sửa không có tác dụng: nhiều trường hợp chính đã đúng, nhưng vẫn còn nhánh tái hiện được nên chưa đóng toàn bộ mục.

## 1 mục chưa đủ bằng chứng để đóng toàn bộ luồng

| ID | Kết quả và lý do chưa đóng |
|---|---|
| BUG-18 | Ký khi capability tắt đã được chặn đúng; browser mock xác nhận print không gọi API workspace thiếu và đi tới window.print. Tuy nhiên E2E thật sau hai lượt lưu bị timeout khi chuyển sang report, hash quay về viewer; chưa xác định nguyên nhân. Vì vậy chưa chứng nhận toàn bộ luồng in thật đã hoạt động. Log: reaudit-live-workflow.txt. |

## 28 mục đã sửa

| ID | Kết quả xác minh hiện tại |
|---|---|
| BUG-01 | Đăng ký ADMIN công khai trả 403, không tạo user; đăng ký thường vẫn DOCTOR |
| BUG-02 | Hai writer đồng thời: một 200, một 409; DB một review, revision 1 |
| BUG-03 | Ba lần lưu liên tiếp cùng phiên đều 200; sequence server 0,−1,−2 không đụng nhau |
| BUG-04 | Xuất hai review cùng ảnh: tên ZIP duy nhất, hash metadata đều khớp |
| BUG-05 | Event trùng trong cùng batch được dedup; xung đột task/seq trả 409 |
| BUG-07 | ACK đầu tiên được tính ngay; task mới chưa ACK giữ INCOMPLETE cho đúng hai tình huống cũ |
| BUG-08 | Xóa ca dọn session/event/batch; append session đã xóa trả 404 |
| BUG-10 | Replay thay session hoặc watermark trả 409 |
| BUG-11 | Prediction không tồn tại/thuộc ảnh khác trả 422; đúng ảnh trả 200 |
| BUG-12 | Worklist dùng fallback /api/cases và render được thay vì gọi route workspace thiếu |
| BUG-14 | Ca tái hiện cũ L88mm → R empty-mask/API500 không giữ số đo trái; R hiện 0px. Xem rủi ro fallback không rỗng bên dưới |
| BUG-15 | Tracker ca khác không bị gắn vào batch; tránh lỗi cross-study422 cũ. Chưa chứng nhận toàn bộ lifecycle cross-user |
| BUG-16 | Mở lại cùng ca có GET mới và restore draft, không trả cache sớm |
| BUG-17 | ACK telemetry lỗi sau commit vẫn giữ revision/review mới và dirty=false |
| BUG-20 | So sánh sắp xếp theo thời gian, before=ca cũ, after=ca mới |
| BUG-22 | Tạo ngày khảo sát và đếm hôm nay dùng getter ngày địa phương thay UTC ISO |
| BUG-23 | Prediction/v1/calibration mới đều báo 80mm/32cm² cho ví dụ nguồn1024px, thay vì40mm/8cm² |
| BUG-24 | Dmax200 có endpoint dài200, orthogonal100 |
| BUG-25 | Nguồn640×480 lưu pad_h64/new_h384 đúng |
| BUG-27 | Hash config chứa manifest thật, thay normalization làm hash đổi |
| BUG-28 | Helper HD95 dùng percentile surface; outlier0, dịch3px ở0,2mm/px ra0,6mm |
| BUG-31 | knowledge/ hiện tồn tại, không còn source COPY bị thiếu |
| BUG-32 | Dockerfile copy evaluation/; Compose mount evaluation cùng checkpoints |
| BUG-33 | DB được đặt /app/data và persist volume data; backups có mount riêng |
| BUG-34 | Compose đã truyền các biến xác thực; **cách thêm giá trị mặc định tạo rủi ro bảo mật mới bên dưới** |
| BUG-38 | Dashboard tính cả ANALYZED/PENDING; browser hai bản ghi có counter2 |
| BUG-39 | Test migration cũ chạy qua sau guard bảng users không tồn tại; chưa coi đây là chứng nhận mọi migration/schema |
| BUG-40 | Test chấp nhận DB trong TempDirectory và kiểm tra không trùng DB sản phẩm; full suite không fail assertion đường dẫn cũ |

Các verdict “đã sửa” áp dụng trigger cũ, không xác nhận mọi nhánh của cả module. Ví dụ: số đo prediction mới đã đúng nhưng chưa thấy backfill các snapshot cũ; các ca lịch sử không tự được sửa số đo khi đổi code.

## Các vấn đề bổ sung phát hiện khi kiểm tra bản sửa

### R-01 — P0, cấu hình Docker mặc định: khóa JWT và mật khẩu công khai

- Nguồn: [docker-compose.yml](../../docker-compose.yml), kiểm tra tại [reaudit_storage_checks.py](../../artifacts/reaudit_storage_checks.py).
- Compose bổ sung APP_JWT_SECRET/APP_ADMIN_PASSWORD/APP_DOCTOR_PASSWORD bằng literal fallback cố định trong repository.
- Với **đúng secret mặc định đó** trên app/database tạm, tự ký JWT `sub=admin` không đăng nhập rồi GET admin audit nhận **200**.
- BUG-01 đã sửa; đường này là cấu hình triển khai khác. Không khẳng định runtime thật đang dùng secret mặc định vì audit không truy cập credentials/database thật.
- Cần bỏ fallback công khai, bắt operator cấp secret/password riêng và đổi các giá trị đó nếu môi trường đã chạy bằng mặc định.

### R-02 — P1: fallback đo trên viewer tự giả định 0,1mm/px

- Nguồn: [viewer.js](../../frontend/app/viewer.js), đoạn fallback quanh dòng347–351.
- Khi request đo thất bại, ảnh có flag calibrated nhưng image.pixel_spacing_mm thiếu, code dùng `image.pixel_spacing_mm || 0.1`.
- Metadata đo có spacing0,2, worker trục200/100px: fallback báo20/10mm thay vì40/20mm, vẫn calibrated=true.
- Bằng chứng: [Node repro](../../artifacts/reaudit-viewer-fallback.txt). Đây là kiểm tra biểu thức JavaScript hiện tại; chưa chạy tích hợp browser với lỗi mạng cho đúng nhánh nonempty-mask này.
- Phải giữ pixel/không xác định nếu không đủ spacing hợp lệ; không suy mm từ giá trị giả định.

### R-03 — P2: retry event lưu trước nâng cấp có thể bị từ chối

- Sửa hash event không kèm compatibility/migration cho payload_hash cũ.
- Fixture lưu event với hash payload-only của phiên bản cũ; replay nguyên event ở code mới nhận409.
- Phạm vi: upgrade có event pending retry; phiên mới không chịu tình huống này.

### R-04 — P2: phiên COMPLETED vẫn COMPLETED sau khi gắn review mới chưa ACK

- Review A đã ACK và COMPLETED; lưu B cùng session/revision mới nhận200.
- Session đổi review_batch_id sang B nhưng status vẫn COMPLETED dù không có ACK(B).
- BUG-07 hai tình huống ban đầu đã đúng; đây là nhánh completion khác còn tồn tại, không khẳng định mới được đưa vào code bởi bản sửa.

### R-05 — P2: đổi mật khẩu tài khoản dùng biến môi trường không kiểm tra mật khẩu cũ

- Bootstrap user chưa có password_hash nên change-password bỏ qua verify cũ.
- Token hợp lệ + old_password sai + new_password một ký tự `x` vẫn200; login bằng `x` sau đó200 trên DB tạm.
- Không phải chiếm quyền khi chưa đăng nhập; đây là bỏ bước tái xác thực và thiếu kiểm tra độ dài.

Reset-password giả thành công và admin create500 đã nằm trong BUG-35/36, không đếm lại thành lỗi mới riêng.

## Log và mức độ bằng chứng

| Kiểm tra | Kết quả / giới hạn | Bằng chứng |
|---|---|---|
| Full pytest |296pass,2skip; exit0 |[pytest](../../artifacts/reaudit-pytest.txt) |
| Node syntax/logic hiện có |PASS |[Node](../../artifacts/reaudit-node.txt) |
| Backend fresh probe |Exit0; xác nhận cả fixed lẫn residual; DB tạm, concurrency thật hai Session |[log](../../artifacts/reaudit-backend.log), [phân tích](../../artifacts/reaudit-backend.md) |
| Browser mock mới |Exit0; contract mock đối chiếu GET app thật port8038 |[log](../../artifacts/reaudit-frontend-repro.log), [phân tích](../../artifacts/reaudit-frontend.md) |
| AI fresh caller checks |Exit0; thực thi body handler hiện tại, decoder/forward/DB có kiểm soát; không phải clinical validation |[log](../../artifacts/reaudit-ai-checks.txt), [phân tích](../../artifacts/reaudit-ai.md) |
| Backup +201ca +JWT mặc định |Exit0; backup restore marker, collision đồng thời, DB tạm |[log](../../artifacts/reaudit-storage.txt) |
| E2E cũ workspace_v2_live.js |**Fail** do còn chờ modal submit ký, trong khi code mới chặn capability trước modal. Không quy timeout này thành lỗi lưu hoặc signoff bypass |[log](../../artifacts/reaudit-browser.txt) |
| E2E mới cho luồng đã thay đổi |Upload/AI/lưu lần1/lưu chỉnh sửa lần2 đạt revision2; ký bị chặn đúng. **Fail ở bước chuyển report**, chưa có kết luận root cause. BUG-18 giữ chưa đủ bằng chứng |[log](../../artifacts/reaudit-live-workflow.txt), [script](../../artifacts/reaudit-live-workflow.cjs) |
| Docker build/runtime |Chưa chạy: Docker daemon unavailable |Chỉ source/config verification cho BUG-31–34 |

Các script/log audit cũ vẫn giữ nguyên để so sánh. Report này là trạng thái mới; không sửa đè kết luận ở lần audit trước.

## Ưu tiên tiếp theo

1. Bỏ secret/password mặc định công khai trong Compose; sửa nhánh fallback đo để không tự suy mm.
2. Sửa lưu O-RADS/mô tả; làm đúng đổi/reset password và quản trị đang hiện trên UI.
3. Đóng các mục event/session/backup còn lại; thay trần200 bằng contract tải/tra cứu đầy đủ.

Không có bản sửa sản phẩm nào được áp dụng trong lượt kiểm tra này.
