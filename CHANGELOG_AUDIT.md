# Nhật Ký Sửa Lỗi Audit An Toàn Lâm Sàng (CHANGELOG_AUDIT.md)

Tài liệu ghi nhận chi tiết từng bản vá lỗi hệ thống y tế theo quy trình xác minh 6 lớp (Kiểm thử tái hiện đỏ -> Sửa mã tối thiểu -> Kiểm thử xanh -> Kiểm tra hồi quy toàn diện -> Linter/Build -> Git diff tối thiểu).

---

## Nhóm BLOCKER

### [BE-01] Khắc phục rò rỉ token đặt lại mật khẩu trong response công khai
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `POST /api/auth/forgot-password` trả trực tiếp `reset_token` trong JSON response body cho người dùng chưa xác thực, cho phép kẻ tấn công chiếm quyền mọi tài khoản kể cả admin.
- **Giải pháp**: Loại bỏ `reset_token` khỏi dictionary trả về trong response body. Khi tài khoản tồn tại, chỉ tiếp nhận yêu cầu an toàn, gửi thông báo qua kênh ngoài luồng (out-of-band delivery) và giữ nguyên thông điệp phản hồi trung tính để chống enum user.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_be_01_forgot_password_does_not_leak_reset_token` (Fails với token lộ trong response trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa.
  - Hồi quy: 297 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-02] Phân tách mục đích token: Từ chối token đặt lại mật khẩu làm access token
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: `get_current_user` chỉ giải mã JWT và lấy `sub` mà không kiểm tra trường `purpose` hoặc `type`. Do đó một reset token (với `sub=admin`) được chấp nhận làm Bearer token hợp lệ để truy cập toàn bộ API người dùng và quản trị viên.
- **Giải pháp**: Gán rõ ràng `"purpose": "access", "type": "access"` khi cấp phát access token trong `create_access_token`. Trong `get_current_user`, kiểm tra và từ chối ngay lập tức HTTP 401 ("Invalid token type.") đối với bất kỳ token nào có `purpose == "reset_password"` hoặc `type == "reset"`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_be_02_reset_token_rejected_as_access_token` (Fails với status 200 OK trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (HTTP 401) sau khi sửa.
  - Hồi quy: 298 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-04] Bắt buộc phê duyệt quản trị đối với tài khoản bác sĩ tự đăng ký
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`, `tests/test_auth_registration.py`
- **Nguyên nhân gốc (Root Cause)**: Khi người dùng bên ngoài tự đăng ký tài khoản qua `POST /api/auth/register`, hệ thống khởi tạo ngay `is_active=True` và cấp phát Bearer `access_token` hoạt động, cho phép đối tượng ngoài luồng truy cập lập tức vào dữ liệu và ghi chú lâm sàng của các ca bệnh trong bệnh viện mà chưa qua kiểm tra danh tính.
- **Giải pháp**:
  1. Đặt `is_active=False` mặc định khi người dùng tự đăng ký, chuyển tài khoản sang trạng thái chờ quản trị viên xác minh và kích hoạt.
  2. Không cấp phát access token hoạt động (`access_token=""`) trong response đăng ký.
  3. Mọi nỗ lực đăng nhập hoặc truy cập tài nguyên lâm sàng trước khi được duyệt đều bị từ chối HTTP 401 Unauthorized.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_be_04_self_registered_doctor_requires_admin_approval` (Fails với `assert True is False` do user bị kích hoạt ngay trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa.
  - Cập nhật test nghiệp vụ: `tests/test_auth_registration.py` kiểm tra chặt chẽ luồng: đăng ký -> chờ duyệt (401 khi đăng nhập) -> quản trị viên kích hoạt -> đăng nhập thành công 200.
  - Hồi quy: 299 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-05] Ngăn chặn bypass ranh giới lâm sàng qua endpoint xuất ZIP nghiên cứu
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/reviews.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `POST /api/cases/{study_id}/research-export` sử dụng dependency `Depends(get_current_user)` thay vì `Depends(require_clinical)`. Do đó, người dùng có vai trò quản trị viên (ADMIN) hoặc thư ký (SECRETARY) vốn bị chặn truy cập ảnh và hồ sơ bệnh nhân qua GET thông thường vẫn có thể tải trọn bộ file ZIP chứa pixel gốc, mask overlay, mô tả hình thái và ghi chú lâm sàng riêng tư.
- **Giải pháp**:
  - Áp dụng kiểm soát truy cập đồng nhất bằng cách đổi dependency thành `current_user: UserModel = Depends(require_clinical)`.
  - Mọi yêu cầu xuất ZIP từ các tài khoản không phải `DOCTOR` (như `ADMIN`, `SECRETARY`) lập tức bị từ chối HTTP 403 Forbidden ("Tài khoản quản trị viên hoặc phi lâm sàng không có quyền truy cập hồ sơ và hình ảnh người bệnh.").
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_be_05_admin_and_non_clinical_roles_cannot_export_research_bundle` (Fails với status 404 thay vì 403 trước khi sửa do vượt qua tầng RBAC).
  - Xác nhận: Test chuyển sang PASSED (HTTP 403 Forbidden cho cả Admin và Thư ký).
  - Hồi quy: 300 passed, 2 skipped, 0 regressions trên toàn bộ test suite (bao gồm 8 test trong `tests/test_research_export.py`).

### [BE-13] Loại bỏ race condition khi tải lên đồng thời hai ảnh cùng bên buồng trứng
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/db/database.py`, `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Kiểm tra trùng lặp bên buồng trứng (`laterality="R"` hoặc `"L"`) chỉ được thực hiện bằng câu lệnh `SELECT` trước khi upload, thiếu ràng buộc tính toàn vẹn cấp cơ sở dữ liệu. Khi có hai request upload gửi đồng thời cho cùng một ca bệnh và cùng một bên buồng trứng, cả hai đều thấy bên đó còn trống và cùng chèn thành công (HTTP 200), dẫn đến việc một ca bệnh có 2 ảnh cùng bên buồng trứng, gây nhầm lẫn lâm sàng nghiêm trọng khi bác sĩ đọc kết quả.
- **Giải pháp**:
  - Bổ sung `Index("uq_study_laterality", "study_id", "laterality", unique=True, sqlite_where=text("laterality IS NOT NULL"))` vào ORM model `ImageModel` và auto-migration trong `init_db`.
  - Trong `upload_image`, xử lý `IntegrityError` đối với vi phạm constraint `uq_study_laterality`: rollback transaction, xóa file ảnh tạm khỏi đĩa và trả về HTTP 409 Conflict ("Ca khám đã có ảnh cho bên khảo sát này.").
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_be_13_concurrent_laterality_upload_race` (Dùng đa luồng `ThreadPoolExecutor` gửi 2 upload cùng `laterality="R"`, trước khi sửa cả hai đều 200 và tạo 2 ảnh right).
  - Xác nhận: Test chuyển sang PASSED (Một request thành công 200, request cạnh tranh còn lại nhận 409 Conflict; DB lưu đúng 1 ảnh duy nhất cho bên R).
  - Hồi quy: 301 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-01] Loại bỏ đơn vị thời gian và vận tốc trong Sequence hiệu chuẩn DICOM
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm `extract_dicom_calibration_spacing` chấp nhận `unit_x in (3, 4)` và gán `scale = 1` nếu `unit_x == 4`. Theo chuẩn DICOM PS3.3 C.8.5.5.1, `PhysicalUnits=4` là đơn vị thời gian (giây) của Doppler/M-mode chứ không phải khoảng cách không gian. Việc gán 1 giây = 1 mm làm sai lệch hoàn toàn kích thước Dmax/Dorth và phân loại nguy cơ O-RADS.
- **Giải pháp**: Bắt buộc chỉ chấp nhận `PhysicalUnitsXDirection == 3` và `PhysicalUnitsYDirection == 3` (Centimeters, scale 10.0 mm/cm). Mọi đơn vị thời gian (4: seconds), vận tốc (5: cm/s), nhịp tim (7: bpm) đều bị từ chối triệt để.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_ai_01_dicom_rejects_time_unit_physical_units_4` (Fails với `0.05 is not None` trước khi sửa do chấp nhận PhysicalUnits=4).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa.
  - Hồi quy: 303 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-02] Xác thực định dạng không gian 2D và kiểm tra biên vùng hiệu chuẩn DICOM
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm `extract_dicom_calibration_spacing` giả định mù quáng vùng hiệu chuẩn đầu tiên `us_regions[0]` áp dụng cho toàn bộ ảnh mà không kiểm tra `RegionSpatialFormat`. Khi máy siêu âm ghi nhận Sequence gồm vùng M-mode waveform (`RegionSpatialFormat=2`) ở vị trí đầu tiên, server dùng sai scale của M-mode để đo khối u 2D.
- **Giải pháp**:
  - Duyệt toàn bộ `SequenceOfUltrasoundRegions`, bắt buộc kiểm tra `RegionSpatialFormat == 1` (2D Tissue Ultrasound).
  - Kiểm tra tính hợp lệ của tọa độ bao phủ hình học vùng (`min_x0 < max_x1` và `min_y0 < max_y1`).
  - Khi có nhiều vùng 2D, kiểm tra tính đồng nhất của calibration; nếu có mâu thuẫn thì từ chối để tránh áp sai scale.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_ai_02_dicom_rejects_non_2d_region_or_picks_correct_2d_region` (Fails với `0.1 is not None` trước khi sửa do lấy bừa us_regions[0] của M-mode).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa.
  - Hồi quy: 303 passed, 2 skipped, 0 regressions trên toàn bộ test suite (bao gồm 7 test trong `tests/test_dicom_scope_guard.py`).

### [FE-01] Khắc phục mất thay đổi lâm sàng và xóa nhầm bản nháp khi lưu đồng thời
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `frontend/app/viewer.js`, `frontend/app/review.js`, `tests/test_fe_01_save_race_guard.cjs`
- **Nguyên nhân gốc (Root Cause)**:
  1. Các trường chọn phân loại hình thái IOTA (`#iotaMorphology`) và phân tầng nguy cơ O-RADS (`#oradsScore`) trong `frontend/app/viewer.js` thiếu cơ chế kiểm tra `state.busy` và `readonly`, cho phép người dùng thay đổi lựa chọn trong lúc request lưu batch đang chạy ngầm hoặc khi ca bệnh ở chế độ chỉ đọc.
  2. Trong `frontend/app/review.js`, khi request lưu batch hoàn tất, hệ thống tự động gọi `clearDraft()` và đặt `state.dirty = false` mà không kiểm tra xem người dùng có thực hiện thay đổi nào sau thời điểm chụp snapshot gửi lên máy chủ hay không. Kết quả là UI hiển thị giá trị mới (ví dụ O-RADS 5) trong khi DB chỉ lưu giá trị cũ (O-RADS 2), và cờ cảnh báo chưa lưu bị xóa sạch.
- **Giải pháp**:
  - Vô hiệu hóa (`disabled = true`) cả hai dropdown `#iotaMorphology` và `#oradsScore` khi ở chế độ `readonly`.
  - Bổ sung busy guard `if (state.busy || readonly)` trong `handleIota` và `handleOrads` để từ chối can thiệp giá trị khi hệ thống đang bận ghi nhận phiên lưu.
  - Trong `saveResearchReview`, trước khi xóa bản nháp, đối chiếu trạng thái lâm sàng hiện tại của ca bệnh với snapshot đã gửi; nếu phát hiện có thay đổi mới chưa lưu, giữ nguyên bản nháp và cờ `state.dirty = true` kèm thông báo lâm sàng rõ ràng cho bác sĩ.
- **Kiểm thử xác minh**:
  - Tái hiện: Chạy `artifacts/production-audit-phase1/frontend-save-race.cjs` trên Chrome headless thật, phát hiện O-RADS 2 được gửi trong khi UI là O-RADS 5 và `dirty=false, draft=null`.
  - Xác nhận: Chạy lại probe trên Chrome thật và test `tests/test_fe_01_save_race_guard.cjs`, xác nhận select bị khóa khi bận/readonly và các thay đổi sau snapshot được bảo toàn trọn vẹn.
  - Hồi quy: Toàn bộ suite Node (`frontend_review_logic.js`, `workspace_v2_logic.mjs`, `validation_files.cjs`) và pytest 303 passed, 2 skipped, 0 regressions.

### [AI-10] Thiết lập Clinical Evidence Gate & Gắn nhãn Nghiên cứu Thực nghiệm (RUO)
- **Mức độ nghiêm trọng**: BLOCKER
- **Tập tin sửa đổi**: `backend/app/routers/health.py`
- **Nguyên nhân gốc (Root Cause)**: Hệ thống thiếu tuyên bố rõ ràng về phạm vi pháp lý và giới hạn lâm sàng của bản mẫu nghiên cứu, dễ dẫn tới ngộ nhận là hệ thống chẩn đoán tự động đã sẵn sàng triển khai lâm sàng độc lập (Standalone SaMD) trong khi chưa qua thử nghiệm lâm sàng đa trung tâm có kiểm soát.
- **Giải pháp**:
  - Gắn nhãn chính thức `clinical_status: "RESEARCH_USE_ONLY"` trong endpoint `/api/health`.
  - Bổ sung `clinical_production_ready: False` và `research_use_only: True` vào metadata `/api/capabilities`.
  - Công bố tuyên bố miễn trừ trách nhiệm y tế (Regulatory Disclaimer) chính thức: hệ thống là bản mẫu nghiên cứu thực nghiệm, không tự ý đưa ra kết luận chẩn đoán tự động và bắt buộc phải có bác sĩ chuyên khoa chịu trách nhiệm chuyên môn cao nhất (Human-in-the-Loop).
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_blocker_fixes.py::test_ai_10_system_disclaims_clinical_production_and_enforces_ruo` (Fails với `clinical_status: None` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa.
  - Hồi quy: 304 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

---

## Nhóm CRITICAL

### [BE-03] Chống tấn công lặp lại token đặt lại mật khẩu (Token Replay Attack)
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `POST /api/auth/reset-password` chỉ kiểm tra chữ ký JWT và `purpose == "reset_password"` rồi tiến hành cập nhật mật khẩu người dùng, nhưng không ghi nhận trạng thái đã sử dụng (consume) của token. Do token có thời hạn 1 giờ, kẻ tấn công hoặc bên thứ ba chặn bắt được token có thể tái sử dụng token đó nhiều lần liên tiếp để đổi mật khẩu tài khoản bất kỳ lúc nào trong vòng đời hiệu lực.
- **Giải pháp**:
  - Bổ sung định danh duy nhất `jti` (UUIDv4) vào payload khi tạo token đặt lại mật khẩu trong `create_reset_token`.
  - Trong `reset_password`, tính toán định danh token `token_id` (từ `jti` hoặc SHA-256 fingerprint của token chuỗi).
  - Kiểm tra bảng `AuditLogModel` với `entity_name="consumed_reset_token"` và `entity_id=token_id`. Nếu token đã được dùng, từ chối ngay lập tức HTTP 400 Bad Request ("Token đặt lại mật khẩu đã được sử dụng.").
  - Sau khi đặt lại mật khẩu thành công, lập tức lưu bản ghi tiêu thụ token vào `AuditLogModel` với hành động `TOKEN_CONSUMED` trong cùng transaction cơ sở dữ liệu.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_03_reset_token_cannot_be_reused` (Fails với `assert 200 == 400` do lần gọi thứ hai dùng lại token thành công trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (lần 1 thành công 200, lần 2 dùng lại cùng token bị từ chối 400).
  - Hồi quy: 305 passed, 2 skipped, 0 regressions trên toàn bộ test suite.







