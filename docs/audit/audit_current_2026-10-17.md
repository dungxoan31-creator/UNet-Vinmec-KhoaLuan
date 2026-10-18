# Kiểm toán lỗi trên working tree hiện tại — 17/10/2026

## Kết quả và giới hạn

**40 phát hiện có căn cứ: 38 lỗi ứng dụng/cấu hình/tích hợp, 2 lỗi hạ tầng kiểm thử.** Trong đó có lỗi chỉ kích hoạt khi đổi cấu hình, triển khai Docker hoặc gọi helper cũ; phạm vi được ghi tại từng mục. Không coi toàn bộ 40 mục là lỗi luôn xảy ra trên màn hình hiện tại.

Audit trên HEAD `6e5ac4116eff86becf193214ff92273a94ba02ef` **cộng toàn bộ thay đổi chưa commit đang có**. HEAD không đủ để tái tạo working tree này. Không sửa mã sản phẩm, không commit, không dùng database thật để tạo ca thử nghiệm. Các script bổ sung dùng database tạm hoặc API giả lập; E2E thật dùng runtime riêng `artifacts/audit-current-browser-runtime`.

Đây là danh sách đầy đủ các phát hiện xác định được trong đợt rà soát này, **không phải bảo chứng đã tìm mọi bug**. Không kiểm thử tải kéo dài, mọi thiết bị DICOM, phục hồi backup trên môi trường bệnh viện hay triển khai Docker thực tế. Docker daemon không chạy; các kết luận Docker là kiểm tra cấu hình/source, không phải log build container.

Mức độ: **P0** = vượt ranh giới bảo mật nghiêm trọng; **P1** = sai/mất tính toàn vẹn dữ liệu hoặc chặn luồng chính; **P2** = sai chức năng, trạng thái, khả năng truy vết hoặc vận hành trong điều kiện xác định.

## Bằng chứng thực thi

| Kiểm tra | Kết quả thực tế | Log |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest tests -q --tb=short` | **289 pass / 2 fail / 2 skip**, 293 test | [pytest](../../artifacts/audit-current-pytest.txt) |
| Chạy riêng hai test fail | Cùng hai lỗi được tái hiện độc lập | [failures](../../artifacts/audit-current-pytest-failures.txt) |
| `scripts/verify_workspace_v2.ps1 -SkipBrowser` | PASS: syntax module và 3 suite logic | [Node](../../artifacts/audit-current-node.txt) |
| `node tests/workspace_v2_live.js`, server riêng port 8037 | PASS luồng đăng nhập → hai ảnh → AI → sửa/undo/redo → lưu; test **chủ động chấp nhận ký sơ bộ thất bại** | [live E2E](../../artifacts/audit-current-browser.txt) |
| `node artifacts/audit-frontend-repro.cjs` | Tái hiện 3 lỗi giao diện bằng browser/API giả lập | [frontend repro](../../artifacts/audit-current-frontend-checks.txt) |
| `node tests/workspace_v2_api_abort.js` | PASS bảo vệ JSON response bị hủy | [API abort](../../artifacts/audit-current-api-abort.txt) |
| `node tests/workspace_v2_draft_conflict.js` | Không thực thi được: script cố định port 8027, khác server audit 8037 | [draft conflict](../../artifacts/audit-current-draft-conflict.txt) |
| `.venv/Scripts/python.exe -W ignore::UserWarning -m artifacts.audit_backend_probe` | Exit 0; tái hiện 11 lỗi backend trên database tạm | [backend repro](../../artifacts/audit-current-backend-checks.txt) |
| `.venv/Scripts/python.exe artifacts/audit_ai_checks.py` | PASS các assertion xác nhận 6 bất nhất AI/đo đạc | [AI repro](../../artifacts/audit-current-ai-checks.txt) |
| `.venv/Scripts/python.exe artifacts/audit_current_checks.py` | Tái hiện backup, missing API, cắt 50 ca, lệch trạng thái; kiểm tra Docker source | [cross-system repro](../../artifacts/audit-current-checks.txt) |
| Ruff chỉ chọn `F821,F823,F811,F601,F602` trên backend | PASS; không phải kết luận toàn bộ lint sạch | Output: `All checks passed!` |

PASS của script tái hiện lỗi nghĩa là **đã xác nhận lỗi tồn tại**, không phải lỗi đã được sửa. PASS của E2E hiện có không bao phủ hết hành vi trong báo cáo.

## A. Bảo mật, giao dịch, HITL và xuất dữ liệu

Chi tiết từng bước, root cause và dòng nguồn của nhóm này: [báo cáo backend](../../artifacts/audit-current-backend.md). Harness: [audit_backend_probe.py](../../artifacts/audit_backend_probe.py).

### BUG-01 — P0 — Người chưa đăng nhập tự tạo được tài khoản ADMIN

- **Nguồn:** [auth.py:93](../../backend/app/routers/auth.py#L93), gán quyền tại dòng 112.
- **Tái hiện:** POST `/api/auth/register` không có Authorization, gửi `role: "ADMIN"` cùng username/password/full_name hợp lệ.
- **Thực tế:** trả 200, cấp JWT role ADMIN; dùng JWT gọi `/api/admin/audit-logs` nhận 200.
- **Nguyên nhân:** backend tin trường role do client cung cấp và kích hoạt tài khoản ngay.
- **Ảnh hưởng:** vượt toàn bộ kiểm soát quản trị, có thể đọc danh sách người dùng/nhật ký, xóa ca và tạo backup. JWT secret mạnh không chặn được đường này.

### BUG-02 — P1 — Hai lượt lưu đồng thời đều vượt kiểm tra revision

- **Nguồn:** [review_service.py:84](../../backend/services/review_service.py#L84), cập nhật tại dòng 203.
- **Tái hiện:** hai SQLAlchemy Session cùng lưu một study, hai request_id khác nhau, cùng `expected_revision=0`; đồng bộ tại biên validate để cả hai đọc revision trước khi ghi.
- **Thực tế:** cả hai trả revision 1; database có hai review nhưng revision vẫn 1, thay vì một yêu cầu bị 409.
- **Nguyên nhân:** so sánh revision bằng Python rồi UPDATE theo primary key, không có điều kiện revision trong UPDATE.
- **Ảnh hưởng:** xung đột ghi không bị phát hiện; revision không còn đại diện đúng số lần cập nhật. Barrier trong harness chỉ ép thứ tự đọc, không thay đổi câu SQL hoặc logic lưu.

### BUG-03 — P1 — Sửa rồi lưu lần hai trong cùng phiên HITL gây HTTP 500

- **Nguồn:** [review_service.py:239](../../backend/services/review_service.py#L239), `seq=0` tại dòng 252; unique constraint ở `database.py:212`.
- **Tái hiện:** phiên HITL có task event; lưu revision 0 thành công, sửa mask và lưu bằng request_id mới/revision 1 trong cùng phiên.
- **Thực tế:** lần một 200, lần hai 500 và rollback.
- **Nguyên nhân:** mỗi lần lưu đều thêm `CONFIRM_SUCCEEDED` với cùng `(session_id, task_id, seq=0)`.
- **Ảnh hưởng:** thao tác lưu hợp lệ tiếp theo không ghi được chỉnh sửa.

### BUG-04 — P1 — ZIP xuất nhiều review của cùng ảnh làm trùng file và sai hash

- **Nguồn:** [research_export.py:54](../../backend/services/research_export.py#L54), ghi ZIP tại dòng 116.
- **Tái hiện:** tạo hai review khác mask cho cùng image; xuất cả hai review_id với revision đúng.
- **Thực tế:** HTTP 200, ZIP có 7 entry nhưng chỉ 4 tên duy nhất; một hash reviewed_mask trong metadata không khớp nội dung đọc theo đường dẫn.
- **Nguyên nhân:** tên file chỉ chứa image_id, không chứa review_id; không cấm nhiều review cùng ảnh trong request.
- **Ảnh hưởng:** giải nén ghi đè lịch sử, bundle không còn bảo toàn snapshot như metadata công bố.

### BUG-05 — P2 — Event trùng trong cùng batch làm hỏng cả batch telemetry

- **Nguồn:** [hitl.py:106](../../backend/app/routers/hitl.py#L106), commit dòng 188.
- **Tái hiện:** gửi `{events: [E, E]}` với E hợp lệ.
- **Thực tế:** 500, không event nào được lưu; retry nguyên batch tiếp tục lỗi.
- **Nguyên nhân:** `autoflush=False`, truy vấn chống trùng không nhìn thấy event vừa `db.add`; unique constraint chỉ nổ lúc commit và không được xử lý.

### BUG-06 — P2 — Replay event đổi loại/task/thời gian vẫn được coi là trùng hợp lệ

- **Nguồn:** [hitl.py:103](../../backend/app/routers/hitl.py#L103).
- **Tái hiện:** lưu E; gửi lại cùng event_id/payload nhưng đổi event_type, task_id, seq và elapsed_ms.
- **Thực tế:** 200, `duplicate_count=1`, không báo xung đột.
- **Nguyên nhân:** hash chỉ bao phủ `payload`, bỏ các trường xác định nội dung event.
- **Ảnh hưởng:** client được xác nhận cho bản ghi khác với dữ liệu thực tế server giữ.

### BUG-07 — P2 — Hoàn tất phiên tính từ tập task cũ nên có cả false COMPLETE và false INCOMPLETE

- **Nguồn:** [hitl.py:151](../../backend/app/routers/hitl.py#L151).
- **Tái hiện A:** task đầu tiên gửi ACK sau linked review; lần đầu INCOMPLETE, replay cùng ACK mới COMPLETED.
- **Tái hiện B:** gửi ACK(task A) cùng event đầu tiên chưa ACK của task B; server vẫn COMPLETED.
- **Nguyên nhân:** query distinct task trước khi flush event mới; ACK được cộng thủ công nhưng non-ACK task mới không được tính.
- **Ảnh hưởng:** sai điều kiện chọn phiên hoàn thành cho nghiên cứu và thống kê HITL.

### BUG-08 — P2 — Xóa ca để lại session/batch mồ côi; gửi event tiếp gây 500

- **Nguồn:** [cases.py:260](../../backend/app/routers/cases.py#L260), [hitl.py:93](../../backend/app/routers/hitl.py#L93).
- **Tái hiện:** tạo ca/session/event/review, xóa ca bằng admin rồi append event vào session cũ.
- **Thực tế:** xóa trả 200 nhưng còn session, event và review batch; append trả 500.
- **Nguyên nhân:** thiếu quan hệ/cascade cho session và batch, SQLite không bật foreign_keys; code dereference `sess.study.images` khi study đã mất.
- **Ảnh hưởng:** dữ liệu tham chiếu đứt, API phiên cũ crash. Nếu cần giữ audit lịch sử thì vẫn phải mô hình hóa và xử lý ca đã xóa rõ ràng.

### BUG-09 — P2 — SESSION_ABORTED không đổi trạng thái phiên

- **Nguồn:** [hitl.py:145](../../backend/app/routers/hitl.py#L145).
- **Tái hiện:** tạo session, gửi event `SESSION_ABORTED`, đọc session.
- **Thực tế:** event được nhận nhưng status vẫn `IN_PROGRESS`.
- **Nguyên nhân:** ingestion chỉ cập nhật nhánh COMPLETED, không xử lý abort.
- **Phạm vi:** lỗi hợp đồng event/status; không khẳng định mọi điều hướng giao diện hiện tại đã gọi abort.

### BUG-10 — P2 — Idempotency bỏ qua thay đổi phiên HITL liên kết

- **Nguồn:** [review_service.py:34](../../backend/services/review_service.py#L34), replay return dòng 70–76.
- **Tái hiện:** lưu batch không session; gửi lại request_id với review giữ nguyên nhưng thêm hitl_session_id hợp lệ.
- **Thực tế:** 200 SUCCESS nhưng session vẫn `review_batch_id=null`.
- **Nguyên nhân:** request hash bỏ `hitl_session_id`/`telemetry_tasks`, trả response cũ trước kiểm tra/liên kết phiên.
- **Ảnh hưởng:** yêu cầu thay đổi ngữ cảnh bị xác nhận thành công mà không thực hiện hoặc báo conflict.

### BUG-11 — P2 — Telemetry nhận prediction_id không tồn tại/không thuộc ảnh

- **Nguồn:** [hitl.py:99](../../backend/app/routers/hitl.py#L99), cột tại `database.py:199`.
- **Tái hiện:** event có image hợp lệ nhưng `prediction_id="nonexistent-prediction"`.
- **Thực tế:** 200, ID sai được lưu.
- **Nguyên nhân:** chỉ kiểm tra image membership, không kiểm tra PredictionModel hoặc quan hệ prediction→image.
- **Ảnh hưởng:** mất khả năng chứng minh bác sĩ đã quan sát prediction nào.

## B. Giao diện, trạng thái ca và thao tác bác sĩ

Chi tiết nguồn/caller và inventory API: [báo cáo frontend](../../artifacts/audit-current-frontend.md). Ba lỗi BUG-13/14/16 đã chạy browser với mock; các lỗi còn lại được trace xuyên caller/schema/backend.

### BUG-12 — P1 — Màn hình danh sách ca gọi API không tồn tại

- **Nguồn:** [worklist.js:170](../../frontend/app/worklist.js#L170).
- Mở `#cases`: luôn GET `/api/workspace/cases` → **404**. Backend có `/api/cases`, capability `case_workflow=false`, nhưng worklist bỏ qua fallback đã có trong `getCases()`.
- Danh sách, bộ lọc và phân trang của màn hình đều không hoạt động.

### BUG-13 — P1 — IOTA/O-RADS không lưu và hiển thị lẫn hai bên

- **Nguồn:** [viewer.js:79](../../frontend/app/viewer.js#L79).
- Chọn IOTA/O-RADS 5 ở bên trái, chuyển phải: select vẫn O-RADS 5; state ảnh không có giá trị và `dirty=false`. Save/reload làm mất lựa chọn.
- Chỉ render select, không binding, không serialize, không load theo image. Đây là lỗi lưu và trình bày thông tin, không phải đánh giá tính đúng đắn y khoa của category.

### BUG-14 — P1 — Ảnh phải giữ số đo mm của ảnh trái khi API đo thất bại

- **Nguồn:** [viewer.js:264](../../frontend/app/viewer.js#L264), đổi ảnh tại dòng 357.
- L trả 88 mm; chọn R và cho API R trả 500: ảnh R vẫn hiển thị 88 mm cùng badge hiệu chuẩn cũ.
- Strip đo chỉ cập nhật khi request thành công; không xóa/reset khi đổi bên. Có thể gán nhầm số đo giữa hai ảnh.

### BUG-15 — P1 — Tracker của ca trước làm ca sau lưu lỗi 422

- **Nguồn:** [review.js:100](../../frontend/app/review.js#L100), tạo session chỉ ở [upload.js:100](../../frontend/app/upload.js#L100).
- Upload/lưu A, mở ca B có sẵn từ dashboard/lịch sử, xem hai ảnh và lưu: payload gắn session A; backend từ chối `Phiên HITL không thuộc ca khảo sát`.
- `openCase`/logout không reset singleton tracker; đổi người dùng cũng có thể giữ session cũ.

### BUG-16 — P1 — Mở lại cùng ca giữ cache cũ, bỏ refresh revision và kiểm tra xung đột draft

- **Nguồn:** [cases.js:100](../../frontend/app/cases.js#L100).
- Mở A, rời viewer, sửa A từ tab khác rồi quay lại A: `openCase` trả nguyên state.case, không gọi server/restoreDraft.
- Hiển thị mask/status/revision cũ; có thể nhận 409 khi lưu nhưng thao tác mở lại cùng ca vẫn không tải bản mới.

### BUG-17 — P1 — Lưu server thành công nhưng telemetry sau lưu lỗi làm UI báo thất bại, giữ revision cũ

- **Nguồn:** [review.js:136](../../frontend/app/review.js#L136).
- Cho `/api/reviews/batch` thành công, sau đó POST ACK telemetry thất bại.
- Frontend await `tracker.flush()` trước khi cập nhật review_revision/review và xóa draft; catch báo lỗi dù review đã commit.
- Retry có thể dùng request_id mới nếu thời gian/payload thay đổi, dẫn tới 409 với revision cũ. Điều kiện kích hoạt là lỗi telemetry sau response thành công, không phải mọi lần lưu.

### BUG-18 — P2 — Ký/duyệt/in vẫn mở dù workflow capability bị tắt

- **Nguồn:** [review.js:206](../../frontend/app/review.js#L206), [report-preview.js:163](../../frontend/app/report-preview.js#L163).
- Ký sơ bộ gọi `/api/workspace/cases/{id}/sign-preliminary`; nút In gọi `/report-export` trước `window.print()`; backend không có các route này.
- Người dùng đi đến cuối luồng rồi luôn gặp unavailable; hộp thoại in không được mở.
- Lỗi là UI phơi bày hành động không khả dụng mà không kiểm tra capability. Backend `/api/generate-report` trả **501 có chủ đích**, không được gán là lỗi vô tình của API đó.

### BUG-19 — P2 — Phiếu kết quả không vẽ caliper dù backend có điểm đo

- **Nguồn:** [report-preview.js:53](../../frontend/app/report-preview.js#L53), [source_measurements.py:42](../../backend/services/source_measurements.py#L42).
- Frontend tìm `measurements.caliper_dmax_points` ở root; dữ liệu thật ở `measurements.lesions[].caliper_dmax_points`.
- Với mask có lesion, vòng vẽ bỏ qua cả hai trục; số đo có thể hiện nhưng ảnh thiếu đường đo.

### BUG-20 — P2 — So sánh hai lần khảo sát mặc định đảo trước/sau

- **Nguồn:** [patient-compare.js:5](../../frontend/app/patient-compare.js#L5), backend sắp xếp ở [cases.py:101](../../backend/app/routers/cases.py#L101).
- API trả mới nhất trước; UI gán index 0 là Lần trước, index 1 là Lần sau và tính B−A.
- Ca cũ 10 mm, ca mới 20 mm có thể mặc định trình bày thay đổi −10 mm. Người dùng phải tự đổi thứ tự để sửa.

### BUG-21 — P2 — Dashboard/tra PID âm thầm bỏ ca ngoài 50 bản ghi mới nhất

- **Nguồn:** [cases.js:20](../../frontend/app/cases.js#L20), [cases.py:101](../../backend/app/routers/cases.py#L101), [patients.js:17](../../frontend/app/patients.js#L17).
- Tạo 51 ca: GET `/api/cases` chỉ trả 50; không pagination hoặc total. UI lọc PID/tính tổng từ mảng này như dữ liệu đầy đủ.
- Ca/PID cũ biến mất khỏi tra cứu và thống kê. Lỗi này độc lập với worklist 404: ảnh hưởng cả fallback đang hoạt động.

### BUG-22 — P2 — Ngày khảo sát và bộ đếm hôm nay dùng UTC thay cho ngày địa phương

- **Nguồn:** [upload.js:93](../../frontend/app/upload.js#L93), [cases.js:145](../../frontend/app/cases.js#L145).
- `toISOString().slice(0,10)` lấy ngày UTC. Tại UTC+7 trong khoảng 00:00–06:59, ngày ghi cho ca mới là hôm trước.
- Ca có ngày địa phương đúng cũng bị bỏ khỏi bộ đếm hôm nay. Đây là lỗi chuyển đổi ngày xác định được từ code.

## C. AI, số đo và provenance

Chi tiết phương pháp/tái hiện: [báo cáo AI](../../artifacts/audit-current-ai.md), [script](../../artifacts/audit_ai_checks.py).

### BUG-23 — P1 — API prediction dùng spacing ảnh gốc để đo mask 512×512

- **Nguồn:** [inference_engine.py:437](../../backend/services/inference_engine.py#L437); caller `inference.py:512`, `:668`, `v1_endpoints.py:80`.
- Nguồn 1024×1024, spacing 0,2 mm/px, mask chữ nhật: đường prediction báo **40 mm / 8 cm²**; helper inverse-letterbox báo **80,2 mm / 32,24 cm²**. Phần lẻ thêm do khôi phục raster.
- Thiếu bù scale khi đo mask model; ảnh hưởng response và measurements lưu ở PredictionModel, API v1 và calibration.
- **Giới hạn:** viewer hiện tại gọi helper source-coordinate riêng nên không kết luận mọi số đo viewer đều sai.

### BUG-24 — P2 — Caliper Dmax của engine nằm trên trục ngắn

- **Nguồn:** [inference_engine.py:303](../../backend/services/inference_engine.py#L303).
- Hình chữ nhật 200×100 px: số Dmax=200 nhưng khoảng cách hai endpoint Dmax=100; trục orthogonal dài 200.
- Gán nhầm cặp trung điểm cạnh; overlay prediction vẽ trục ngắn với nhãn D1 lớn.
- `source_measurements.py` có bù riêng cho kết quả của helper, không sửa đường overlay/prediction của engine.

### BUG-25 — P2 — Transform letterbox lưu sai padding và kích thước vùng ảnh

- **Nguồn:** [inference.py:522](../../backend/app/routers/inference.py#L522), producer `preprocessor.py:83`.
- Ảnh 640×480 có pad_y=64, active height=384; route đọc key không tồn tại và ghi pad_h=0/new_h=512.
- Provenance sai hình học. Export mask hiện có tự tính lại transform nên đây chưa phải bằng chứng pixel export bị lệch.

### BUG-26 — P2 — Manifest chọn threshold khác 0,5 nhưng registry bỏ qua

- **Nguồn:** [model_service.py:337](../../backend/services/model_service.py#L337), tạo engine dòng 76–82.
- Manifest threshold=0,8 nhưng engine vẫn 0,5; xác suất 0,6 vẫn thành foreground.
- Không truyền threshold qua adapter. **Có điều kiện:** manifest hiện tại là 0,5, nên ca đang chạy chưa chịu sai khác từ mục này.

### BUG-27 — P2 — Hash serving config luôn mô tả `{}`

- **Nguồn:** [model_service.py:337](../../backend/services/model_service.py#L337), [inference.py:534](../../backend/app/routers/inference.py#L534).
- Registry không gán `self.model_selection`; consumer luôn fallback `{}` để hash.
- Kiến trúc/normalization/cấu hình khác nhau không được phân biệt bởi `serving_config_sha256`. Cùng nhóm truyền manifest với BUG-26 nhưng khác lỗi quan sát được.

### BUG-28 — P2, helper cũ — HD95 thực chất là Hausdorff cực đại

- **Nguồn:** [metrics.py:64](../../backend/models/metrics.py#L64).
- Code dùng max directed Hausdorff, không percentile 95. Mặt nạ trùng nhau cộng một pixel xa: helper báo 70,7107, hàm HD95 surface hiện tại của dự án báo 0.
- **Giới hạn:** chưa tìm caller ngoài `evaluate_batch` cùng file; pipeline đánh giá chính dùng module khác. Không quy lỗi này cho tất cả metric đã công bố.

## D. Sao lưu, tích hợp API và triển khai

Harness nhóm này: [audit_current_checks.py](../../artifacts/audit_current_checks.py), log [cross-system repro](../../artifacts/audit-current-checks.txt).

### BUG-29 — P1 — Backup bỏ qua database/data_dir đang cấu hình và vẫn báo SUCCESS

- **Nguồn:** [admin.py:94](../../backend/app/routers/admin.py#L94), [backup_service.py:17](../../backend/services/backup_service.py#L17).
- Cấu hình APP_DB_PATH/APP_DATA_DIR riêng rồi tạo backup: route vẫn khởi tạo `BackupService()` với `ovarian_ai.db`/`data` theo cwd.
- Tái hiện database đang hoạt động có thật nhưng archive chỉ chứa thư mục rỗng, `contains_database=false`, response **SUCCESS**.
- Có thể sao lưu nhầm dữ liệu cũ hoặc bỏ sót toàn bộ dữ liệu cần phục hồi. UI gọi metadata-only cũng chịu lỗi chọn DB này.
- **Hướng sửa:** truyền đường dẫn runtime thật và không xác nhận backup database thành công nếu nguồn không tồn tại.

### BUG-30 — P2 — Hai backup cùng giây ghi đè cùng archive

- **Nguồn:** [backup_service.py:30](../../backend/services/backup_service.py#L30).
- Tên archive/temp chỉ chính xác tới giây. Hai lần tạo cùng timestamp trả cùng backup_path, cuối cùng chỉ còn một file.
- Harness cố định datetime để tái hiện định danh trùng, không cần ghi dữ liệu thật. Hai request đồng thời còn dùng chung temp directory và có thể can thiệp vào nhau.
- **Hướng sửa:** dùng tên duy nhất cho cả temp và archive.

### BUG-31 — P1, Docker — Dockerfile COPY thư mục không tồn tại

- **Nguồn:** [Dockerfile:29](../../Dockerfile#L29).
- `COPY knowledge/ /app/knowledge/` trong khi working tree không có `knowledge/`.
- Build context hiện tại thiếu source bắt buộc của COPY. Đây là blocker xác định bằng source inventory; **chưa chạy build** do daemon Docker không hoạt động.

### BUG-32 — P1, Docker — Image không chứa manifest chọn model mặc định

- **Nguồn:** [Dockerfile:26](../../Dockerfile#L26), [config.py:47](../../backend/app/config.py#L47).
- Dockerfile copy checkpoints nhưng không copy `evaluation/selected_model.json`, cũng không mount/pass manifest trong Compose.
- Config mặc định đọc manifest đó; thiếu file thì selected checkpoint=None và model không sẵn sàng dù trọng số có trong image.
- **Điều kiện:** sau khi khắc phục BUG-31 và khởi chạy container theo cấu hình hiện tại.
- **Hướng sửa:** đóng gói manifest cần thiết hoặc mount manifest cùng checkpoint được tham chiếu.

### BUG-33 — P1, Docker — Database và thư mục backup không được persist

- **Nguồn:** [docker-compose.yml:16](../../docker-compose.yml#L16), [database.py:32](../../backend/db/database.py#L32).
- Compose chỉ mount uploads/reports/checkpoints; database mặc định ở `/app/ovarian_ai.db` và backup ở `/app/backups`, cả hai ở writable layer container.
- Khi recreate container, metadata người dùng/ca/review/telemetry và backup mất; ảnh mount ngoài vẫn còn nhưng mất liên kết.
- **Bằng chứng:** mapping đường dẫn/mount; chưa thực hiện thử xóa/recreate container.
- **Hướng sửa:** persist DB và backup tại volume rõ ràng, khớp APP_DB_PATH và backup_dir.

### BUG-34 — P1, Docker — Compose không truyền cấu hình xác thực bắt buộc

- **Nguồn:** [docker-compose.yml:13](../../docker-compose.yml#L13), [auth.py:37](../../backend/app/routers/auth.py#L37), bootstrap `database.py:289`.
- `environment` chỉ có PORT/PYTHONUNBUFFERED; không APP_JWT_SECRET, APP_ADMIN_PASSWORD, APP_DOCTOR_PASSWORD và không env_file.
- Theo hướng dẫn `docker-compose up --build`, container không nhận các biến host chỉ vì chúng tồn tại ngoài host. Thiếu secret làm phát hành token trả 503; thiếu password cũng không bootstrap tài khoản mặc định.
- **Điều kiện:** triển khai đúng Compose đang lưu sau khi sửa blocker build; không phải lỗi khi operator đã cung cấp override ngoài repo.
- **Hướng sửa:** wire biến/secret qua cấu hình Compose và kiểm tra cấu hình trước khi nhận thao tác đăng ký.

### BUG-35 — P2 — Quên/đổi/reset mật khẩu và gia hạn phiên đều gọi route chưa triển khai

- **Nguồn:** [auth.js:180](../../frontend/app/auth.js#L180), [auth.js:234](../../frontend/app/auth.js#L234), [personal.js:62](../../frontend/app/personal.js#L62).
- POST `/api/auth/forgot-password`, `/reset-password`, `/change-password`, `/refresh` đều **404** trong app thật dùng runtime tạm.
- Link Quên mật khẩu, form đổi mật khẩu và nút gia hạn được hiển thị nhưng không thể hoàn thành. OTP cũng có caller nhưng backend hiện không kích hoạt challenge; không đếm OTP thành lỗi riêng đang tác động.
- **Hướng sửa:** đồng bộ phạm vi tính năng/capability của UI và API; không chỉ sửa chuỗi URL khi chưa có nghiệp vụ tương ứng.

### BUG-36 — P2 — Nhiều tab quản trị và thao tác quản trị không có API tương ứng

- **Nguồn:** [admin-audit.js:37](../../frontend/app/admin-audit.js#L37), [admin.js:61](../../frontend/app/admin.js#L61), `admin-directory.js`, `admin-metadata.js`, `admin-users.js`, `admin-models.js`.
- Audit UI gọi `/api/admin/audit-events` trong khi backend chỉ có `/audit-logs`; tab audit không tải được dù dữ liệu tồn tại.
- Departments, metadata ca và settings gọi `/api/admin/departments`, `/api/admin/cases`, `/api/admin/settings`: chưa có route.
- Danh sách user/model đọc được; thêm/sửa/khóa/xóa/reset user và đăng ký/deploy/remove model gọi mutation route chưa có.
- **Ảnh hưởng:** nhiều màn hình/tab hiện diện nhưng lỗi ngay khi mở hoặc bấm lưu. Gom thành một nhóm lệch contract quản trị, không nhân mỗi URL thành một bug.
- **Hướng sửa:** dùng contract đọc hiện hữu khi phù hợp; ẩn/giải thích tính năng chưa hỗ trợ hoặc triển khai đầy đủ theo đặc tả.

### BUG-37 — P2 — Thông báo và gửi góp ý đều trỏ API chưa có

- **Nguồn:** [notifications.js:25](../../frontend/app/notifications.js#L25), [personal.js:103](../../frontend/app/personal.js#L103).
- GET `/api/notifications`, POST `/api/notifications/read`, POST `/api/feedback` đều **404**.
- Màn hình thông báo không hoạt động; form báo lỗi của chính ứng dụng không gửi được phản hồi.
- **Hướng sửa:** công bố capability đúng và đồng bộ UI/API cho các hành động đang hiển thị.

### BUG-38 — P2 — Dashboard bỏ qua trạng thái thật của backend

- **Nguồn:** [cases.js:138](../../frontend/app/cases.js#L138), fallback `cases.js:22`, backend [inference.py:570](../../backend/app/routers/inference.py#L570).
- Backend lưu `PENDING`/`ANALYZED`; fallback giữ nguyên status. Dashboard chỉ tính pending trong `IN_REVIEW`, `AI_DONE`, `REJECTED`.
- Harness tạo 51 study ANALYZED, API trả 50, phép lọc dashboard ra **0**. Caller prediction thật đổi PENDING→ANALYZED.
- **Ảnh hưởng:** ca đã AI nhưng chưa review không hiện ở Tiếp tục công việc; số Đang rà soát bị thiếu. Không đồng nhất với BUG-21: ngay cả dưới 50 ca vẫn sai status mapping.
- **Hướng sửa:** chuẩn hóa trạng thái qua contract hoặc adapter dùng chung.

## E. Lỗi bộ kiểm thử

Hai mục dưới đây giải thích hai failure hiện tại; **không gán chúng thành hai lỗi runtime của ứng dụng**.

### BUG-39 — P2, QA — Test migration đổi DB_PATH nhưng không đổi engine

- **Nguồn:** [test_prediction_provenance.py:60](../../tests/test_prediction_provenance.py#L60), [database.py:216](../../backend/db/database.py#L216).
- Test tạo legacy DB rồi chỉ đổi DB_PATH/DATABASE_URL. `Base.metadata.create_all(bind=engine)` vẫn trỏ DB cũ; sqlite migration trỏ DB mới chưa có `users`.
- **Thực tế:** `sqlite3.OperationalError: no such table: users` tại ALTER users, được bọc RuntimeError.
- **Hướng sửa:** fixture phải thay engine/session nhất quán và restore đầy đủ; sau đó mới kết luận migration thực sự có lỗi ứng dụng hay không.

### BUG-40 — P2, QA — Test yêu cầu DB nằm dưới artifacts xung đột fixture TempDirectory

- **Nguồn:** [test_release_evidence.py:17](../../tests/test_release_evidence.py#L17), [conftest.py:7](../../tests/conftest.py#L7), [serve_isolated_app.py:9](../../tests/serve_isolated_app.py#L9).
- Conftest chủ động dùng TempDirectory; helper đọc APP_DATA_DIR đó. Test lại assert `"artifacts" in runtime_db.parts`.
- **Thực tế:** DB ở `%TEMP%/ova-pytest-.../data/technical_test.sqlite3`, test fail dù đó là đường dẫn cô lập an toàn.
- Import helper còn thay engine/SessionLocal toàn cục; fixture cần quản lý khôi phục thay vì import có side effect.
- **Hướng sửa:** kiểm tra khác DB sản phẩm và nằm trong runtime được fixture cấp, không ép tên thư mục cố định.

## Những điều chưa đủ căn cứ để gọi là bug mới

- **Patient-level split chưa được xác minh:** split hiện tại có 661 train, 541 val, 402 test; toàn bộ patient_id trống. Raw SHA-256 giao nhau giữa các split là 0. Điều này không chứng minh độc lập bệnh nhân, cũng không chứng minh thực sự có cùng bệnh nhân xuyên split. Giữ là blocker bằng chứng dữ liệu.
- **Thiếu spacing trên PNG/JPG:** trả pixel và không suy mm là fail-safe đúng phạm vi, không tính thành bug.
- **Quick login chứa mật khẩu cố định trong static JS:** chắc chắn có chuỗi literal tại `auth.js:109–120`; helper E2E dùng đúng mật khẩu đó. Mức độ chiếm quyền trên môi trường người dùng phụ thuộc password thực tế. Không khẳng định mật khẩu đó đăng nhập được database thật vì audit không thử vào runtime thật.
- **PDF generator cũ có dữ liệu mặc định bệnh nhân/kết luận:** mã còn ở `report_generator.py`, nhưng API generate-report chủ động 501, UI hiện tại dùng luồng khác. Là rủi ro nếu tái kích hoạt, không ghi thành lỗi phát hành PDF đang diễn ra.
- **v1 async gọi inference đồng bộ:** có dấu hiệu chiếm event loop; chưa có thử nghiệm concurrency/timing nên không tính là một lỗi hiệu năng đã đo.
- **Health readiness:** khi model thiếu, health trả 200/healthy và model_ready=false; Docker curl healthcheck không kiểm tra body. Đây là khoảng trống readiness cần xử lý cùng BUG-32, chưa gán thành bug liveness riêng vì endpoint có thể chủ đích chỉ báo process sống.
- **Đổi bên tải ảnh lỗi giữ cờ selecting:** source cho thấy không có finally reset, có thể chặn vẽ cho đến chọn bên thành công. Chưa chạy phép thử riêng nên để ở diện cần xác minh tiếp, không cộng vào 40 phát hiện.
- **DICOM inspect/frame selection chưa hỗ trợ:** caller có kiểm tra capability và fallback single-frame, nên không coi mọi DICOM upload đều hỏng chỉ vì thiếu `/api/uploads/inspect`.
- **Metric API cấp đầu là lịch sử:** checkpoint cấp validation/test khác model hiện tại, nhưng UI có banner lịch sử và phần current_run riêng. Chưa đủ căn cứ coi đây là bug số liệu mới.
- **Guideline/CDSS:** đã đọc logic bảo thủ hiện có; chưa xác thực độc lập toàn bộ O-RADS/IOTA từ tài liệu chính thức trong đợt này, không công bố kết luận clinical validation.

## Thứ tự khắc phục đề xuất

1. **BUG-01:** khóa đường tự cấp ADMIN; test người không xác thực không thể xin quyền quản trị.
2. **BUG-02/03/04/29:** bảo toàn revision, lưu nhiều lần, snapshot ZIP và backup đúng database.
3. **BUG-13/14/15/16/17/23:** bảo toàn lựa chọn, số đo đúng ảnh, session đúng ca, trạng thái sau commit và đơn vị vật lý.
4. **BUG-12/18/21/35/36/37/38:** khớp API/capability/status với những chức năng UI đang hiển thị.
5. **BUG-05–11/19/20/22/24–28/30:** hoàn thiện tính toàn vẹn event, biểu diễn đo, provenance và các tình huống biên.
6. **BUG-31–34:** sửa cấu hình trước khi nghiệm thu triển khai Docker; chạy build/start/recreate sau khi daemon sẵn sàng.
7. **BUG-39/40:** sửa fixture và thêm các ca hồi quy tương ứng lỗi vừa xác nhận. Chạy lại suite xanh chưa thay thế việc tái hiện riêng các lỗi P0/P1.

Audit chưa áp dụng bản sửa nào. Báo cáo cũ `audit_summary_2026-10-17.md` thuộc snapshot/run khác; kết luận “không có lỗi nghiêm trọng” ở đó không đại diện cho working tree và các tình huống biên kiểm tra lần này.
