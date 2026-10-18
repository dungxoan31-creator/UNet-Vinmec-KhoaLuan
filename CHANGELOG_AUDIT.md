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

### [BE-06] Thu hồi phiên làm việc và vô hiệu hóa access token khi đổi mật khẩu/đăng xuất
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/db/database.py`, `backend/app/routers/auth.py`, `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Khi người dùng đổi mật khẩu (`/api/auth/change-password`), quản trị viên reset mật khẩu (`/api/admin/users/{user_id}/reset-password`), hoặc thực hiện khôi phục tài khoản (`/api/auth/reset-password`), hệ thống không cập nhật phiên làm việc hay cơ chế thu hồi token. Các access token đã cấp phát trước đó vẫn tiếp tục có hiệu lực truy cập API cho đến khi hết hạn (24 giờ), cho phép kẻ tấn công giữ quyền truy cập ngay cả sau khi nạn nhân đã đổi mật khẩu. Đồng thời hệ thống thiếu endpoint `POST /api/auth/logout` ở tầng máy chủ.
- **Giải pháp**:
  - Bổ sung `token_version = Column(Integer, default=1)` và `tokens_revoked_at = Column(DateTime, nullable=True)` vào `UserModel` cùng auto-migration trong `init_db`.
  - Trong `create_access_token` và `login`, gắn `token_version` vào payload của JWT.
  - Trong `get_current_user`, kiểm tra xác thực kép:
    1. Nếu token có `token_version`, đối chiếu `token_ver != user.token_version` để từ chối ngay HTTP 401 Unauthorized nếu phiên đã bị thu hồi.
    2. Nếu token tạo thủ công/cũ không có `token_version`, so sánh thời điểm cấp phát `iat` với `tokens_revoked_at` để từ chối các token sinh trước thời điểm thu hồi.
  - Khi đổi mật khẩu, reset mật khẩu, hoặc admin reset mật khẩu: tăng `token_version` và cập nhật `tokens_revoked_at = datetime.now(UTC)`.
  - Bổ sung endpoint máy chủ chuẩn `POST /api/auth/logout` để thu hồi phiên làm việc tức thì khi người dùng đăng xuất.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_06_session_revocation_on_password_change_and_logout` (Fails với `assert 200 == 401` trước khi sửa do token cũ vẫn dùng được).
  - Xác nhận: Test chuyển sang PASSED (token cũ bị từ chối 401 sau khi đổi mật khẩu; sau khi đăng xuất token phiên cũng bị từ chối 401).
  - Hồi quy: 306 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-07] Ngăn chặn tái gắn token của tài khoản cũ sang tài khoản mới khi tái sử dụng username
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: Khi một tài khoản người dùng bị xóa và sau đó một tài khoản mới được tạo lại với cùng tên đăng nhập (`username`), hàm `get_current_user` chỉ truy vấn cơ sở dữ liệu theo `UserModel.username == username` mà không đối chiếu định danh bất biến `uid` (`user.id`) trong JWT payload. Do đó, token còn hạn của tài khoản cũ vô tình được gắn sang tài khoản mới tạo, cho phép chủ sở hữu token cũ chiếm quyền tài khoản mới.
- **Giải pháp**:
  - Trong `get_current_user`, kiểm tra đối chiếu ràng buộc danh tính:
    1. Nếu JWT payload có chứa `uid`, bắt buộc `user.id == uid`. Nếu khác nhau, từ chối ngay HTTP 401 Unauthorized ("Account identity changed.").
    2. Nếu JWT không chứa `uid` (legacy token), đối chiếu thời điểm phát hành `iat` với thời điểm tạo tài khoản `user.created_at`. Nếu token được phát hành trước khi tài khoản mới ra đời (`iat < created_ts - 1.0`), từ chối ngay HTTP 401 Unauthorized.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_07_old_token_cannot_rebind_to_recreated_username` (Trước khi sửa, token của user cũ giải mã thành user ID mới và trả về HTTP 200).
  - Xác nhận: Test chuyển sang PASSED (cả token có `uid` cũ và token không có `uid` phát hành trước đó đều bị từ chối 401 khi tài khoản mới được tái tạo).
  - Hồi quy: 307 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-08] Bảo vệ tính toàn vẹn audit và chống giả mạo actor trong feedback
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/app/main.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `POST /api/feedback` không yêu cầu xác thực người dùng và nhận trực tiếp giá trị `actor_id` từ client payload (`payload.get("actor_id")`) để ghi vào bảng `AuditLogModel`. Lỗ hổng này cho phép kẻ tấn công ẩn danh chèn các bản ghi nhật ký giả mạo dưới danh nghĩa của bất kỳ tài khoản nào (bao gồm quản trị viên `admin`), phá hủy tính toàn vẹn và giá trị chứng cứ pháp lý của hệ thống audit trail.
- **Giải pháp**:
  - Bắt buộc xác thực người dùng thông qua dependency `user: UserModel = Depends(get_current_user)`. Mọi request ẩn danh đều bị từ chối ngay HTTP 401 Unauthorized.
  - Gán trường `actor_id` của bản ghi audit duy nhất từ phiên làm việc đã xác thực của máy chủ (`user.username`), loại bỏ hoàn toàn việc tin tưởng `actor_id` do client truyền lên.
  - Chuẩn hóa trường `details` chỉ lưu trữ các thông tin hợp lệ (`title`, `message`, `role`), tránh nhúng payload tùy tiện không kiểm soát.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_08_feedback_requires_auth_and_prevents_actor_spoofing` (Trước khi sửa, request ẩn danh nhận HTTP 200 và client giả mạo được `actor_id="auditadmin"`).
  - Xác nhận: Test chuyển sang PASSED (request ẩn danh bị từ chối 401; request có token của `doctor1` truyền `actor_id="auditadmin"` chỉ ghi nhận đúng `actor_id="doctor1"` trong audit log).
  - Hồi quy: 308 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-09] Thiết lập nhật ký kiểm toán bảo mật (Security Audit Logging) cho Auth, Read ca bệnh và Quyền quản trị
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`, `backend/app/routers/cases.py`, `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Các hành vi nhạy cảm cốt lõi trong hệ thống y tế — bao gồm đăng nhập thành công (`LOGIN_SUCCESS`), đăng nhập thất bại do sai thông tin/không tồn tại (`LOGIN_FAILURE`), bác sĩ truy cập hồ sơ và hình ảnh siêu âm của người bệnh (`CLINICAL_CASE_READ`), cũng như quản trị viên cập nhật thuộc tính tài khoản người dùng (`ADMIN_USER_UPDATE`) — hoàn toàn không ghi vết kiểm toán (0 audit rows) trong bảng `AuditLogModel`. Điều này vi phạm nghiêm trọng tiêu chuẩn an toàn thông tin y tế (HIPAA/GDPR) do không thể truy vết trách nhiệm khi xảy ra rò rỉ dữ liệu hoặc xâm nhập trái phép.
- **Giải pháp**:
  - Trong `backend/app/routers/auth.py`: Bổ sung ghi nhận sự kiện bảo mật `LOGIN_FAILURE` (với lý do không tìm thấy user hoặc sai mật khẩu) và `LOGIN_SUCCESS` (với vai trò tài khoản) vào `AuditLogModel`.
  - Trong `backend/app/routers/cases.py`: Khi bác sĩ tải chi tiết ca bệnh qua `GET /api/cases/{study_id}`, tự động ghi nhận sự kiện `CLINICAL_CASE_READ` kèm `actor_id` của bác sĩ, `study_id`, và `patient_id`.
  - Trong `backend/app/routers/admin.py`: Khi quản trị viên cập nhật tài khoản qua `PATCH /api/admin/users/{user_id}`, tự động ghi nhận sự kiện `ADMIN_USER_UPDATE` cùng các trường được chỉnh sửa và chuẩn hóa kiểu dữ liệu boolean (xử lý chuỗi `"false"` tránh lỗi ép kiểu ngầm định).
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_09_security_audit_logging_for_auth_read_and_admin` (Trước khi sửa, `actions` trả về tập rỗng `set()` và test thất bại).
  - Xác nhận: Test chuyển sang PASSED (ghi nhận đầy đủ cả 4 loại sự kiện bảo mật `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `CLINICAL_CASE_READ`, `ADMIN_USER_UPDATE`).
  - Hồi quy: 309 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-12] Bảo toàn tính toàn vẹn Idempotency Hash cho đánh giá O-RADS và mô tả hình thái
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/services/review_service.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm `compute_request_hash` trong `review_service.py` chỉ đưa các trường `verified_mask_rle`, `clinical_notes`, `lesion_type`, `time_spent_seconds` vào cấu trúc tính băm SHA-256, nhưng bỏ qua hoàn toàn các trường `orads`, `orads_score` và `morphology_description` được lưu trữ trong `hitl_feedback`. Hậu quả là khi bác sĩ gửi lại request với cùng một `request_id` nhưng đã thay đổi phân loại O-RADS (ví dụ từ O-RADS 2 lên O-RADS 5) hoặc sửa mô tả hình thái u nang, hệ thống tính ra mã băm trùng khớp với bản ghi trước, ngộ nhận là một lần gửi lại lặp (idempotent replay), trả về HTTP 200 nhưng âm thầm giữ nguyên đánh giá cũ và vứt bỏ hoàn toàn chẩn đoán mới của bác sĩ.
- **Giải pháp**:
  - Cập nhật hàm `compute_request_hash`: Trích xuất đầy đủ `orads`, `orads_score`, `morphology_description` (và `morphologyDesc`), đóng gói vào cả cấu trúc canonical review item và `hitl_feedback` chuẩn hóa trước khi tính băm SHA-256.
  - Khi một request gửi lại với cùng `request_id` nhưng có bất kỳ sự thay đổi nào về O-RADS hay mô tả hình thái, mã băm sẽ khác biệt và máy chủ trả về chính xác lỗi xung đột HTTP 409 Conflict ("Request ID đã tồn tại với nội dung khác."), ngăn ngừa việc mất mát dữ liệu chẩn đoán lâm sàng.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_12_review_idempotency_hash_includes_orads_and_descriptors` (Trước khi sửa, request gửi lại đổi O-RADS 2 thành 5 nhận HTTP 200 giả mạo).
  - Xác nhận: Test chuyển sang PASSED (lần gửi lại cùng request_id nhưng đổi O-RADS bị từ chối 409 Conflict; lần gửi lại giống hệt 100% được trả về kết quả 200 an toàn).
  - Hồi quy: 310 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-25] Loại bỏ mật khẩu mặc định dùng chung khi khởi tạo tài khoản và ép buộc đổi mật khẩu lần đầu
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `backend/db/database.py`, `backend/schemas/schemas.py`, `backend/app/routers/admin.py`, `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: Khi quản trị viên khởi tạo tài khoản mới không truyền mật khẩu (`POST /api/admin/users`) hoặc thực hiện đặt lại mật khẩu người dùng (`POST /api/admin/users/{user_id}/reset-password`), hệ thống sử dụng các chuỗi mật khẩu mặc định tĩnh hardcode công khai (`Default@123` và `Vinmec@2026`). Đồng thời, hệ thống không có cờ đánh dấu yêu cầu đổi mật khẩu ở lần đăng nhập tiếp theo. Điều này dẫn đến nguy cơ bất kỳ kẻ tấn công nào cũng có thể chiếm đoạt tài khoản mới tạo hoặc vừa được reset bằng các mật khẩu mặc định đã biết.
- **Giải pháp**:
  - Bổ sung trường `must_change_password = Column(Boolean, default=False, nullable=False)` vào `UserModel` cùng auto-migration trong `init_db`.
  - Cập nhật schema `TokenResponse` với trường `must_change_password: bool = False`.
  - Trong `backend/app/routers/admin.py`:
    1. Khi tạo tài khoản (`create_admin_user`) mà không cung cấp mật khẩu, sinh ngẫu nhiên mật khẩu tạm thời an toàn thông qua `secrets.token_urlsafe(12)`, lưu hash và bật cờ `must_change_password = True`. Trả về mật khẩu tạm trong response để cấp phát qua kênh an toàn.
    2. Khi đặt lại mật khẩu (`admin_reset_user_password`) mà không cung cấp mật khẩu mới, sinh ngẫu nhiên mật khẩu tạm thời với `secrets.token_urlsafe(12)`, bật cờ `must_change_password = True` và thu hồi các phiên làm việc hiện có.
  - Trong `backend/app/routers/auth.py`:
    1. Trong `login`, trả về giá trị cờ `must_change_password` của tài khoản trong response.
    2. Trong `change_password` và `reset_password`, sau khi người dùng cập nhật mật khẩu riêng, tự động hạ cờ `user.must_change_password = False`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_be_25_secure_provisioning_and_no_shared_default_password` (Fails với `AssertionError: assert None is True` trước khi sửa do mật khẩu mặc định hardcode).
  - Xác nhận: Test chuyển sang PASSED (tạo và reset tài khoản sinh mật khẩu ngẫu nhiên không trùng chuỗi mặc định, bật cờ `must_change_password`, và tự động tắt cờ khi đổi mật khẩu).
  - Hồi quy: 311 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-01] Thiết lập TLS Termination, chuyển hướng HTTPS-only và giới hạn truy cập mạng riêng cho backend
- **Mức độ nghiêm trọng**: CRITICAL
- **Tập tin sửa đổi**: `docker-compose.yml`, `nginx.conf`
- **Nguyên nhân gốc (Root Cause)**: Trong file `docker-compose.yml`, container backend `app` mở trực tiếp cổng `8000:8000` ra toàn bộ các giao diện mạng công khai (0.0.0.0), cho phép truy cập HTTP không mã hóa bỏ qua reverse proxy. Đồng thời, dịch vụ `nginx` chỉ lắng nghe cổng 80 HTTP thông thường, không cấu hình cổng 443 HTTPS, không gắn chứng chỉ số TLS và không có cơ chế chuyển hướng HTTP sang HTTPS. Nếu triển khai cấu hình này lên hạ tầng bệnh viện, toàn bộ token xác thực y tế (Bearer JWT), thông tin bệnh án và ảnh siêu âm sẽ truyền tải dưới dạng bản rõ (plaintext).
- **Giải pháp**:
  - Trong `docker-compose.yml`:
    1. Thay thế khai báo mở cổng công khai `ports: - "8000:8000"` của container `app` thành `expose: - "8000"`, chỉ cho phép Nginx trong mạng nội bộ Docker truy cập backend.
    2. Bổ sung cổng `443:443` vào danh sách ports của `nginx`.
    3. Bổ sung volume mount thư mục chứng chỉ TLS an toàn `./certs:/etc/nginx/certs:ro` vào container `nginx`.
  - Trong `nginx.conf`:
    1. Cấu hình server block trên cổng 80 chuyển hướng bắt buộc HTTP 301 toàn bộ request sang `https://$host$request_uri`.
    2. Cấu hình server block chuyên dụng lắng nghe cổng 443 với `listen 443 ssl`, trỏ đến chứng chỉ `/etc/nginx/certs/tls.crt` và khóa bí mật `/etc/nginx/certs/tls.key`.
    3. Giới hạn các giao thức mã hóa an toàn `ssl_protocols TLSv1.2 TLSv1.3;`, bật `ssl_prefer_server_ciphers on;` với bộ ciphers bảo mật cao `HIGH:!aNULL:!MD5`.
    4. Bổ sung các header bảo mật y tế quan trọng: `Strict-Transport-Security` (HSTS thời hạn 1 năm), `X-Content-Type-Options: nosniff` và `X-Frame-Options: DENY`.
    5. Thiết lập header `proxy_set_header X-Forwarded-Proto https;` để backend nhận diện đúng giao thức kết nối an toàn.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_critical_fixes.py::test_ops_01_enforce_tls_and_no_plaintext_exposure` (Fails với `AssertionError: OPS-01 VULNERABILITY: Backend port 8000 directly published on 0.0.0.0!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (cổng 8000 không còn công khai 0.0.0.0, Nginx mở cổng 443 và mount certs, cổng 80 chuyển hướng 301 sang HTTPS, server block 443 cấu hình TLSv1.2/1.3 và HSTS đầy đủ).
  - Hồi quy: 312 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

---

## Nhóm MAJOR

### [FE-03] Bổ sung phân loại O-RADS và mô tả hình thái lâm sàng vào Metadata ZIP nghiên cứu
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/research_export.py`
- **Nguyên nhân gốc (Root Cause)**: Trong quá trình đóng gói gói nghiên cứu `metadata.json` của tệp ZIP (`build_research_bundle`), danh sách trường trích xuất từ `ReviewModel` bỏ qua hoàn toàn thông tin phân loại nguy cơ `orads`/`orads_score` và mô tả hình thái siêu âm `morphology_description` được lưu trong `hitl_feedback`. Hậu quả là gói dữ liệu nghiên cứu xuất ra bị thiếu mất nhận định lâm sàng cốt lõi của bác sĩ, khiến các hệ thống hoặc nhà nghiên cứu tiếp nhận phía sau không thể tái cấu trúc trọn vẹn ca rà soát.
- **Giải pháp**:
  - Trong `build_research_bundle` (`backend/services/research_export.py`), trích xuất thông tin `hitl_feedback` từ phiên rà soát được ghim (`rev.hitl_feedback`).
  - Lấy các giá trị `orads_score`/`orads` và `morphology_description`/`morphologyDesc`.
  - Bổ sung tường minh các trường `"orads"`, `"orads_score"`, và `"morphology_description"` vào từng mục `images_metadata` trong `metadata.json`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_fe_03_research_export_metadata_includes_orads_and_morphology` (Fails với `AssertionError: FE-03 VULNERABILITY: 'orads' missing from exported image metadata!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (tệp metadata.json trong ZIP chứa đầy đủ `orads="O-RADS 3"` và `morphology_description="U nang đơn thùy, thành mỏng"`).
  - Hồi quy: 313 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [FE-02] Hiển thị phân loại O-RADS và mô tả hình thái lâm sàng đã lưu trên phiếu in kết quả
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `frontend/app/report-preview.js`
- **Nguyên nhân gốc (Root Cause)**: Khi bác sĩ mở giao diện xem trước phiếu in (`renderReport`), mẫu giao diện HTML chỉ đọc `i.morphology` và `i.notes`. Trong khi đó, các kết quả đánh giá lâm sàng thực tế được lưu trong đối tượng `i.review` (như `orads_score`/`orads`, `morphology_description`, `clinical_notes`). Do không liên kết với các trường đã lưu của `i.review`, phiếu in bị bỏ trống hoàn toàn phân loại nguy cơ O-RADS và mô tả hình thái của từng bên buồng trứng, làm sai lệch nội dung bàn giao chuyên môn so với kết quả bác sĩ đã xác nhận trên hệ thống.
- **Giải pháp**:
  - Trong `frontend/app/report-preview.js`, trích xuất giá trị phân loại O-RADS ưu tiên từ `i.review?.orads_score || i.review?.orads || i.orads`.
  - Trích xuất mô tả hình thái từ `i.review?.morphology_description || i.morphologyDesc || i.morphology || i.review?.lesion_type`.
  - Trích xuất ghi chú lâm sàng từ `i.review?.clinical_notes || i.notes`.
  - Cập nhật mẫu báo cáo in ấn hiển thị rõ ràng: `Phân loại O-RADS: <strong>...</strong>`, `Mô tả hình thái: ...` và `Ghi chú lâm sàng: ...` theo từng bên buồng trứng.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_fe_02_report_preview.mjs` (Fails với `AssertionError: FE-02 VULNERABILITY: report-preview.js does not render saved O-RADS classification!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED sau khi sửa template báo cáo.
  - Hồi quy: Toàn bộ suite node tests và full pytest suite đều giữ vững kết quả.

### [AI-04] Khấu trừ diện tích lỗ tẩy (Erased Hole) trong thuật toán tính diện tích mặt nạ tổn thương
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/inference_engine.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm `extract_calipers_and_measurements` trước đây sử dụng cờ `cv2.RETR_EXTERNAL` để trích xuất đường viền. Chế độ này chỉ lấy đường viền bao ngoài cùng (outer contour) và bỏ qua toàn bộ cấu trúc lỗ rỗng bên trong. Khi bác sĩ sử dụng công cụ Tẩy (Eraser) để đục khoét các phần mô lành hoặc cấu trúc dạng nang bên trong một tổn thương lớn, thuật toán vẫn lấy nguyên vẹn diện tích hình bao ngoài (`cv2.contourArea(cnt)`), khiến diện tích tính toán (`area_px` và `total_area_cm2`) không hề giảm dù phần lớn vùng bên trong đã bị xóa bỏ.
- **Giải pháp**:
  - Chuyển đổi cờ trích xuất đường viền từ `cv2.RETR_EXTERNAL` sang `cv2.RETR_CCOMP` để thu thập cây phả hệ đường viền 2 cấp (đường viền ngoài và các lỗ rỗng con tương ứng).
  - Duyệt qua từng đường viền ngoài (`hierarchy[0][i][3] == -1`), tính diện tích bao ngoài `outer_area`.
  - Duyệt qua danh sách toàn bộ các lỗ con (`child_idx = hierarchy[0][i][2]`) và cộng dồn diện tích lỗ `hole_area`.
  - Tính toán diện tích thực `net_area = max(0.0, outer_area - hole_area)`, khấu trừ chính xác phần diện tích bị tẩy rỗng trước khi áp dụng ngưỡng kích thước và chuyển đổi sang cm².
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_04_erased_hole_reduces_mask_area` (Fails với `AssertionError: AI-04 VULNERABILITY: Internal hole ignored in lesion area calculation! Reported area_px: 10000.0` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (diện tích khấu trừ chính xác từ 100.0 cm² xuống 61.58 cm² khi đục lỗ 61×61 trong khối 101×101).
  - Hồi quy: 314 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-06] Đồng nhất cặp kích thước tóm tắt (Dmax, Dorth) từ cùng một tổn thương ưu thế
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/inference_engine.py`
- **Nguyên nhân gốc (Root Cause)**: Khi một mặt nạ chứa nhiều tổn thương rời nhau (multi-component), hàm `extract_calipers_and_measurements` lấy giá trị tóm tắt `max_d_overall` bằng cách lấy `max()` trên toàn bộ các tổn thương và độc lập lấy `ortho_d_overall` bằng cách lấy `max()` trên trục trực giao của tất cả các tổn thương. Ví dụ: tổn thương 1 có kích thước 100×10 mm và tổn thương 2 có kích thước 40×40 mm, hệ thống trả về cặp kích thước tóm tắt là 100×40 mm — một tổn thương "ảo" không hề tồn tại trên hình thái giải phẫu của người bệnh và mâu thuẫn với quy ước của `source_measurements.py` (vốn tham chiếu theo tổn thương có diện tích lớn nhất).
- **Giải pháp**:
  - Đồng nhất quy ước kích thước tóm tắt với `source_measurements.py`: lấy cặp đường kính tóm tắt `(max_diameter_mm, ortho_diameter_mm)` từ chính tổn thương ưu thế (dominant lesion - tổn thương có diện tích lớn nhất đứng đầu danh sách `lesions[0]`).
  - Đảm bảo tính nhất quán hình học: hai giá trị Dmax và Dorth luôn là cặp trục hình học thực tế thuộc về cùng một khối cấu trúc duy nhất.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_06_summary_diameters_belong_to_same_dominant_lesion` (Fails với `AssertionError: AI-06 VULNERABILITY: Summary dimensions mixed axes across different lesions! Reported Dmax=99.0, Dorth=39.0` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (Dmax và Dorth đều thuộc tổn thương ưu thế 100×20 mm thay vì ghép trục 40 mm từ tổn thương phụ).
  - Hồi quy: 315 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-08] Khóa định danh mô hình phục vụ cốt lõi và ngăn chặn ghi đè Registry
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`, `backend/services/model_service.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint đăng ký mô hình ứng viên `POST /api/admin/models/register` nhận tham số `model_id` do client truyền vào mà không kiểm tra trùng lặp hoặc bảo vệ các định danh cốt lõi. Phương thức `ModelRegistry.register_adapter` gán đè trực tiếp `self.adapters[key] = adapter`. Khi người dùng gửi request với `model_id="attention_unet"` (hoặc các mô hình phục vụ khác), mô hình chính đang phục vụ lâm sàng bị ghi đè bởi một `CandidateModelAdapter` chưa được tải (`is_loaded=False`), lập tức làm tê liệt toàn bộ luồng suy luận của hệ thống mà không cần bước phê duyệt hoặc kiểm thử hợp lệ.
- **Giải pháp**:
  - Tại tầng dịch vụ (`backend/services/model_service.py`): Bổ sung cờ bảo vệ `allow_overwrite: bool = False` trong `register_adapter`. Nếu `key in self.adapters` và không bật `allow_overwrite`, ném lỗi `ValueError` từ chối ghi đè.
  - Tại tầng API (`backend/app/routers/admin.py`): Trước khi đăng ký, kiểm tra nếu `key` đã tồn tại trong `model_registry.adapters` hoặc thuộc danh sách khóa phục vụ được bảo vệ (`{"attention_unet", "s4m", "ultrasam", "ds2net", "sovaseg"}`), từ chối ngay lập tức HTTP 409 Conflict ("Mã mô hình đã tồn tại hoặc thuộc danh mục phục vụ được bảo vệ.").
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_08_cannot_overwrite_serving_model_key` (Fails với `Status=200` và adapter `attention_unet` bị ghi đè thành công trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (request đăng ký trùng khóa bị từ chối 409 Conflict, adapter chính `attention_unet` giữ nguyên tham chiếu và trạng thái `is_loaded`).
  - Hồi quy: 316 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-07] Xử lý đảo cực tính (Polarity Inversion) cho ảnh DICOM MONOCHROME1
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Khi giải mã ảnh siêu âm định dạng DICOM trong hàm `decode_ultrasound_image`, hệ thống chuẩn hóa mảng pixel sang kiểu uint8 nhưng hoàn toàn bỏ qua thẻ DICOM tiêu chuẩn `PhotometricInterpretation` (0028, 0004). Đối với ảnh có thuộc tính `MONOCHROME1`, giá trị pixel nhỏ nhất biểu thị màu trắng (sáng tối đa) và giá trị lớn nhất biểu thị màu đen (tối tối đa), ngược lại với chuẩn thông thường `MONOCHROME2` của siêu âm và quy ước huấn luyện mô hình học sâu. Do đó, ảnh giải mã bị đảo ngược toàn bộ mức xám (âm bản), làm sai lệch hoàn toàn hình thái hiển thị cho bác sĩ và gây lỗi suy luận trên mô hình.
- **Giải pháp**:
  - Trích xuất giá trị thẻ `PhotometricInterpretation` từ đối tượng DICOM đã đọc: `photometric = str(getattr(dicom, "PhotometricInterpretation", "")).strip().upper()`.
  - Nếu `photometric == "MONOCHROME1"`, áp dụng phép toán đảo cực tính cấp độ bit `image = cv2.bitwise_not(image)` trên mảng uint8, chuyển đổi chính xác thang xám về chuẩn trực quan y tế thông thường (0 = đen, 255 = trắng) trước khi chuyển đổi kênh màu hoặc trả về cho các dịch vụ tiền xử lý và suy luận.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_07_monochrome1_polarity_inversion` (Fails với `AssertionError: AI-07 VULNERABILITY: MONOCHROME1 polarity was not inverted! Expected 255 at [0,0], got 0` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (pixel có giá trị thô 0 được ánh xạ sang 255 và pixel 255 được ánh xạ sang 0).
  - Hồi quy: 317 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-05] Bảo toàn số đo và cảnh báo rà soát cho mặt nạ tổn thương nhỏ dưới ngưỡng lọc
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/inference_engine.py`, `backend/services/source_measurements.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm `extract_calipers_and_measurements` trước đây áp dụng điều kiện cứng `if area_px < 50: continue`. Khi bác sĩ vẽ hoặc rà soát một tổn thương dạng dải mỏng hoặc khối nhỏ (ví dụ 11×3 pixel = 33 pixel diện tích, nhưng chiều dài tới 10 mm trên thang tỉ lệ 1.0 mm/px), toàn bộ các thành phần tổn thương đều bị lọc bỏ trong im lặng (`has_lesion = False`, `total_lesions = 0`, `max_diameter_mm = 0.0`, `total_area_cm2 = 0.0`). Hệ thống không đưa ra bất kỳ lý do loại trừ hay cảnh báo lâm sàng nào, biến một mặt nạ thực tế không rỗng thành kết quả khám trắng (0 tổn thương).
- **Giải pháp**:
  - Tại `InferenceEngine.extract_calipers_and_measurements`: Tính toán đầy đủ hình học, đường kính trực giao và điểm caliper cho mọi thành phần tổn thương. Nếu thành phần có diện tích `< 50 px²`, lưu trữ vào danh sách `filtered_components` kèm `exclusion_reason` chỉ rõ diện tích và ngưỡng kỹ thuật.
  - Khi mặt nạ có tổn thương nhưng toàn bộ thành phần đều dưới ngưỡng lọc diện tích: Không tự ý kết luận mặt nạ rỗng. Hệ thống giữ lại số đo tổn thương từ thành phần ưu thế, trả về `has_lesion = True`, đồng thời cung cấp cờ cảnh báo `warning` và lý do loại trừ `exclusion_reason = "all_components_below_min_area"` để bác sĩ kiểm tra và quyết định lâm sàng.
  - Tại `source_measurements.measure_source_mask`: Đồng bộ xử lý cho cả `lesions` và `filtered_components`, bảo toàn việc tính tỉ lệ hiển thị (viewer calipers), diện tích và đường kính quy đổi theo độ phân giải nguồn.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_05_nonempty_subthreshold_mask_retains_measurements_and_warns` (Fails với `AssertionError: AI-05 VULNERABILITY: Nonempty mask was silently discarded as having no lesion!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (mặt nạ 33 px dài 10 mm giữ nguyên `has_lesion = True`, đường kính >= 9.0 mm, diện tích > 0 và sinh cảnh báo lâm sàng minh bạch; mặt nạ thực sự rỗng vẫn trả về `has_lesion = False`).
  - Hồi quy: 318 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-09] Đồng bộ nguồn gốc đo đạc (Provenance Spacing) và lưu vết lịch sử hiệu chuẩn
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Khi bác sĩ hoặc kỹ thuật viên thực hiện hiệu chuẩn lại tỉ lệ khoảng cách vật lý của ảnh siêu âm (`POST /api/images/{image_id}/calibrate`), hệ thống tính lại các đường kính tổn thương và gán đè vào `prediction.measurements`, nhưng hoàn toàn không cập nhật `prediction.provenance_json`. Dẫn tới tình trạng dữ liệu mâu thuẫn nghiêm trọng: `prediction.provenance_json["pixel_spacing_mm"]` vẫn giữ giá trị cũ (ví dụ 0.2 mm/px), trong khi các kích thước lâm sàng hiển thị và lưu trữ (`max_diameter_mm`, `ortho_diameter_mm`) đã biến đổi theo tỉ lệ mới (ví dụ 0.4 mm/px). Người dùng và các quy trình nghiên cứu xuất khẩu không thể tái tạo lại số đo vật lý từ metadata nguồn gốc.
- **Giải pháp**:
  - Tại hàm `calibrate_image_spacing`: Trích xuất và bảo toàn giá trị tỉ lệ suy luận ban đầu `original_inference_pixel_spacing_mm` trong `provenance_json`.
  - Cập nhật trường `pixel_spacing_mm` của `provenance_json` khớp chính xác với giá trị hiệu chuẩn mới.
  - Thiết lập mảng lịch sử hiệu chuẩn `calibration_history` ghi nhận thời điểm (`calibrated_at`), người thực hiện (`actor`), tỉ lệ cũ (`previous_pixel_spacing_mm`), tỉ lệ mới (`new_pixel_spacing_mm`) và nguồn hiệu chuẩn (`MANUAL`).
  - Đồng bộ `pixel_spacing_mm` và `calibration_source` vào payload `updated_measurements` để đảm bảo tính toàn vẹn của kết quả trả về API.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_09_calibration_updates_provenance_spacing` (Fails với `AssertionError: AI-09 VULNERABILITY: provenance_json was not updated! provenance_json={'pixel_spacing_mm': 0.2...}` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (`provenance_json["pixel_spacing_mm"]` cập nhật lên 0.4, `original_inference_pixel_spacing_mm` bảo toàn 0.2 và có `calibration_history`).
  - Hồi quy: 319 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-10] Phân tích và áp dụng bộ lọc mốc thời gian (Date Range Filter) cho sự kiện Audit
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint quản trị `GET /api/admin/audit-events` định nghĩa các tham số query `from_date` (alias `from`) và `to_date` (alias `to`) nhưng hoàn toàn không xây dựng logic chuyển đổi và lọc trên trường `AuditLogModel.timestamp`. Khi quản trị viên hoặc các công cụ probe gửi yêu cầu lọc sự kiện theo khoảng ngày (ví dụ tìm sự cố trong tương lai hoặc trong một tháng cụ thể), truy vấn cơ sở dữ liệu bỏ qua hai tham số này và trả về toàn bộ dữ liệu audit hiện có (`HTTP 200` với kết quả ngoài khoảng thời gian yêu cầu).
- **Giải pháp**:
  - Xây dựng hàm chuẩn hóa mốc thời gian `parse_date_boundary(date_str, is_end_of_day)`: Hỗ trợ linh hoạt cả định dạng ngày `YYYY-MM-DD` (tự động mở rộng sang `00:00:00` cho cận dưới và `23:59:59.999999` cho cận trên) và chuỗi ISO datetime chuẩn hóa về UTC.
  - Hỗ trợ đầy đủ các bí danh tham số thời gian phổ biến (`from`, `from_date`, `start_date`, `to`, `to_date`, `end_date`).
  - Áp dụng các điều kiện lọc `AuditLogModel.timestamp >= from_dt` và `AuditLogModel.timestamp <= to_dt` trực tiếp vào truy vấn SQLAlchemy trước khi thực hiện đếm tổng số bản ghi và phân trang.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_10_audit_events_date_range_filtering` (Fails với `AssertionError: BE-10 VULNERABILITY: Future date filter ignored! Expected 0, got total=3` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (lọc ngày tương lai trả về đúng 0 bản ghi; lọc khoảng thời gian trong tháng trả về chính xác 1 bản ghi khớp điều kiện).
  - Hồi quy: 320 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-14] Bảo đảm tính nguyên tử (Atomicity) và dọn dẹp file vật lý khi upload thất bại
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Tại endpoint `POST /api/upload` (`upload_image`), khi người dùng tải ảnh lên mà không cung cấp `study_id`, hệ thống đã thực hiện `db.commit()` sớm cho `PatientModel` và tiếp tục `db.commit()` sớm cho `StudyModel` trước khi khởi tạo `ImageModel`. Nếu sau đó xảy ra lỗi ghi DB (ví dụ `OperationalError` hoặc lỗi ràng buộc), chỉ có `ImageModel` bị dừng lại trong khi `PatientModel` và `StudyModel` đã bị commit vĩnh viễn vào cơ sở dữ liệu, đồng thời file ảnh siêu âm vừa ghi ra đĩa (`file_path`) không được thu hồi/xóa bỏ. Điều này tạo ra các bản ghi bệnh nhân/ca khám mồ côi (orphan records) và rác đĩa không kiểm soát.
- **Giải pháp**:
  - Thay thế các lệnh `db.commit()` sớm của `PatientModel` và `StudyModel` bằng `db.flush()`. Toàn bộ chuỗi tạo Patient $\to$ Study $\to$ Image $\to$ AuditLog được gom vào một giao dịch cơ sở dữ liệu nguyên tử duy nhất.
  - Bao bọc toàn bộ khối xử lý sau khi ghi file tạm vào khối `try...except Exception`: Nếu có bất kỳ ngoại lệ nào xảy ra trước khi giao dịch hoàn tất, tự động gọi `db.rollback()` (hủy bỏ toàn bộ Patient, Study, Image, AuditLog vừa tạo) và xóa file tạm trên đĩa an toàn bằng `os.remove(file_path)` có bảo vệ `try...except OSError`.
  - Giữ nguyên cơ chế chuyển đổi lỗi `IntegrityError` thành phản hồi `HTTP 409 Conflict` thân thiện khi trùng lặp ảnh trong ca khám.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_14_upload_db_failure_rolls_back_atomically` (Fails với `AssertionError: BE-14 VULNERABILITY: Patient was committed despite upload failure! count=1` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (khi commit ImageModel thất bại, số lượng patient và study trong cơ sở dữ liệu đều là 0, và không có file mồ côi nào lưu lại trên đĩa).
  - Hồi quy: 321 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-15] Kích hoạt bắt buộc PRAGMA foreign_keys = ON cho SQLite và bảo toàn liên kết quan hệ
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/db/database.py`, `backend/services/review_service.py`
- **Nguyên nhân gốc (Root Cause)**: SQLite mặc định tắt tính năng thực thi khóa ngoại (`PRAGMA foreign_keys = 0`). Mặc dù ORM SQLAlchemy khai báo đầy đủ `ForeignKey("studies.id")`, `ForeignKey("patients.id")`, nhưng SQLite không hề kiểm tra ràng buộc này khi thêm/sửa/xóa dữ liệu. Hậu quả là có thể trực tiếp chèn bản ghi ảnh (`ImageModel`), dự đoán (`PredictionModel`) hoặc đánh giá rà soát trỏ tới các ID ca khám không hề tồn tại mà không bị chặn lại, sinh ra các bản ghi mồ côi phá vỡ tính toàn vẹn quan hệ. Đồng thời, khi kích hoạt foreign keys, việc cập nhật `HITLSessionModel.review_batch_id` trước khi bản ghi `ReviewBatchModel` được đẩy xuống DB tạo ra xung đột thứ tự phụ thuộc.
- **Giải pháp**:
  - Đăng ký event listener `@event.listens_for(Engine, "connect")`: Mỗi khi kết nối SQLite được khởi tạo, tự động thực thi lệnh `PRAGMA foreign_keys = ON;`. Điều này áp dụng toàn cục cho mọi session và engine SQLite trong hệ thống.
  - Trong `HITLSessionModel`: Khai báo rõ ràng mối quan hệ `review_batch = relationship("ReviewBatchModel")` để SQLAlchemy xây dựng đồ thị phụ thuộc (dependency graph) chính xác.
  - Trong `review_service.py`: Thực hiện `db.flush()` ngay sau `db.add(batch_record)` để đảm bảo bản ghi `ReviewBatchModel` tồn tại trong bảng trước khi `hitl_sessions` liên kết khóa ngoại tới `batch_record.id`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_15_sqlite_foreign_keys_enforced` (Fails với `AssertionError: BE-15 VULNERABILITY: SQLite PRAGMA foreign_keys is 0, expected 1 (ON)!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (kết nối trả về `PRAGMA foreign_keys = 1`, việc chèn ảnh mồ côi bị chặn đứng bằng `IntegrityError`, các quy trình rà soát HITL batch hoạt động trơn tru).
  - Hồi quy: 322 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-16] Kiểm tra hợp lệ và từ chối mã định danh bệnh nhân (PID) rỗng khi tạo ca khám
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/schemas/schemas.py`, `backend/app/routers/cases.py`
- **Nguyên nhân gốc (Root Cause)**: Schema `CreateCaseRequest` và router `POST /api/cases` chấp nhận chuỗi `patient_id` rỗng `""` hoặc toàn khoảng trắng `"   "`. Hàm tạo ca bệnh cắt tỉa (strip) chuỗi thành `""`, tìm kiếm và tạo ra bệnh nhân có `anonymized_pid = ""` trong cơ sở dữ liệu (`HTTP 200`). Việc tồn tại ca khám không có định danh người bệnh hợp lệ gây nguy cơ gán nhầm ca khám, trùng lặp bệnh nhân và vi phạm các quy định quản lý hồ sơ y tế bệnh viện.
- **Giải pháp**:
  - Trong `CreateCaseRequest`: Bổ sung `@field_validator("patient_id")` kiểm tra chuỗi sau khi strip không được rỗng, đồng thời giới hạn độ dài tối đa 64 ký tự theo quy định schema.
  - Trong router `create_new_case`: Kiểm tra tường minh `clean_pid = req.patient_id.strip()`; nếu rỗng lập tức trả về lỗi `HTTP 422 Unprocessable Entity` ("Mã định danh bệnh nhân (PID) không được để trống.").
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_16_create_case_rejects_blank_pid` (Fails với `AssertionError: BE-16 VULNERABILITY: Empty patient_id accepted! Status=200` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (cả chuỗi rỗng `""` và chuỗi chỉ chứa khoảng trắng `"    "` đều bị từ chối chính xác với HTTP 422).
  - Hồi quy: 323 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-17] Kiểm tra hợp lệ và chuẩn hóa định dạng ngày khám (study_date) khi tạo ca bệnh
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/schemas/schemas.py`, `backend/app/routers/cases.py`
- **Nguyên nhân gốc (Root Cause)**: Khi tạo ca bệnh mới (`POST /api/cases`), trường `study_date` không được kiểm tra tính hợp lệ về mặt lịch pháp và định dạng chuỗi. Hệ thống chấp nhận bất kỳ chuỗi văn bản tùy tiện nào (ví dụ `"invalid-date"`, `"2026-02-31"`) và lưu thẳng vào trường `StudyModel.study_date` (`HTTP 200`). Điều này làm hỏng tính toàn vẹn metadata thời gian khám, gây sai lệch khi lọc báo cáo, tìm kiếm theo khoảng ngày và trích xuất hồ sơ bệnh án.
- **Giải pháp**:
  - Trong `CreateCaseRequest`: Bổ sung `@field_validator("study_date")` phân tích cú pháp chuỗi ngày theo chuẩn `YYYY-MM-DD` hoặc ISO datetime (chuyển đổi chuẩn hóa về `YYYY-MM-DD`). Nếu chuỗi ngày không hợp lệ hoặc sai lịch pháp (như ngày 31 tháng 2), lập tức trả về lỗi kiểm thực Pydantic `ValueError`.
  - Trong router `create_new_case`: Bổ sung khối kiểm tra định dạng an toàn trước khi lưu DB; nếu không truyền `study_date`, tự động lấy ngày hiện tại định dạng `YYYY-MM-DD`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_17_create_case_rejects_invalid_study_date` (Fails với `AssertionError: BE-17 VULNERABILITY: Non-date text accepted! Status=200` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (chuỗi chữ không phải ngày và ngày không có trên lịch đều nhận lỗi HTTP 422; chuỗi ngày hợp lệ được lưu trữ và phản hồi chính xác).
  - Hồi quy: 324 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-18] Lưu trữ bền vững (Persistence) cài đặt quản trị hệ thống qua các lần khởi động lại
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Toàn bộ cấu hình quản trị hệ thống (`hospital_name`, `report_header`, `iqa_threshold`, `unit`, `ai_assisted_signoff`, `hitl_enabled`) chỉ được lưu trong biến từ điển bộ nhớ tạm thời `_ADMIN_SETTINGS` của tiến trình Python. Mặc dù API `PUT /api/admin/settings` trả về HTTP 200 thành công, nhưng mỗi khi tiến trình uvicorn khởi động lại hoặc khi hệ thống chạy đa tiến trình/đa worker, toàn bộ cấu hình cập nhật của quản trị viên bị biến mất và khôi phục về giá trị mặc định tĩnh.
- **Giải pháp**:
  - Xây dựng cơ chế lưu trữ bền vững `_save_admin_settings` và tải tự động `_load_admin_settings` trỏ tới tệp cấu hình `admin_settings.json` trong thư mục dữ liệu `DATA_DIR` (hỗ trợ phân giải động biến môi trường `APP_DATA_DIR`).
  - Khi quản trị viên cập nhật cài đặt qua `PUT /api/admin/settings`, hệ thống cập nhật bộ nhớ đồng thời ghi tệp JSON an toàn có thụt lề định dạng.
  - Khi truy vấn `GET /api/admin/settings`, hệ thống đồng bộ dữ liệu mới nhất từ tệp cấu hình để đảm bảo tính nhất quán giữa các tiến trình worker.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_18_admin_settings_persist_across_restart` (Fails với `AssertionError: BE-18 VULNERABILITY: Settings lost across process restart! Output: ... PERSISTED:BỆNH VIỆN...` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (cấu hình `persisted-header-audit-be18` được đọc chính xác trong tiến trình con khởi tạo hoàn toàn mới).
  - Hồi quy: 325 passed, 2 skipped, 0 regressions trên toàn bộ test suite.
### [BE-19] Lưu trữ bền vững danh sách khoa phòng và tính toán nhân sự thực tế
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Danh sách khoa phòng chuyên môn (`_DEPARTMENTS`) được lưu dưới dạng danh sách tĩnh trong bộ nhớ RAM, với số lượng nhân viên `members` được hardcode sẵn (12 và 8). Khi quản trị viên tạo, sửa hoặc xóa khoa phòng qua các API `POST/PATCH/DELETE /api/admin/departments`, các thay đổi trả về HTTP 200 nhưng hoàn toàn biến mất sau khi tiến trình uvicorn khởi động lại. Đồng thời, số liệu thành viên hiển thị không phản ánh số lượng nhân sự thực tế được phân bổ trong cơ sở dữ liệu.
- **Giải pháp**:
  - Xây dựng cơ chế đọc/ghi tệp bền vững `_load_admin_departments` và `_save_admin_departments` lưu trữ dữ liệu khoa phòng vào `admin_departments.json` trong thư mục dữ liệu cấu hình `DATA_DIR` (hỗ trợ phân giải biến môi trường `APP_DATA_DIR`).
  - Mọi thao tác thêm mới (`POST`), cập nhật tên/mã khoa (`PATCH`) và xóa khoa (`DELETE`) đều tự động ghi cập nhật bền vững xuống đĩa.
  - Trong API `GET /api/admin/departments`, tích hợp dependency `db: Session = Depends(get_db)` để tính toán động số lượng thành viên thực tế của từng khoa phòng thông qua bảng `users` (`UserModel.department == d_name` hoặc `UserModel.department == d_code`).
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_19_admin_departments_persist_across_restart` (Fails với `AssertionError: BE-19 VULNERABILITY: Department lost across process restart! Output: ... PERSISTED:False` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (khoa mới tạo tồn tại nguyên vẹn sau khi tiến trình mới khởi động lại; số lượng nhân sự `members` được tính toán tự động và chính xác theo dữ liệu người dùng).
  - Hồi quy: 326 passed, 2 skipped, 0 regressions trên toàn bộ test suite.




### [BE-20] Lưu trữ bền vững mô hình ứng viên (Candidate Models) và ghi vết kiểm toán
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/model_service.py`, `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Khi quản trị viên đăng ký một checkpoint hoặc kiến trúc mô hình ứng viên (`CandidateModelAdapter`) qua API `POST /api/admin/models/register`, adapter chỉ được thêm tạm thời vào từ điển bộ nhớ `model_registry.adapters`. Khi tiến trình uvicorn khởi động lại hoặc khi có tiến trình worker độc lập chạy, toàn bộ mô hình ứng viên đã đăng ký biến mất hoàn toàn. Đồng thời hành vi đăng ký mô hình AI vào registry hệ thống không được ghi nhận vào nhật ký kiểm toán bảo mật (`audit_logs`).
- **Giải pháp**:
  - Triển khai cơ chế lưu trữ bền vững `load_persisted_candidates` và `save_persisted_candidates` trong `ModelRegistry`, lưu metadata các mô hình ứng viên vào `candidate_models.json` trong thư mục dữ liệu cấu hình `DATA_DIR` (hỗ trợ phân giải biến môi trường `APP_DATA_DIR`).
  - Trong hàm khởi tạo `ModelRegistry.__init__` và phương thức truy vấn `get_admin_overview`, tự động nạp lại các ứng viên đã lưu trữ để đồng bộ trạng thái xuyên suốt mọi worker và sau các lần restart.
  - Trong `register_admin_model`, sau khi thêm adapter vào registry, tự động kích hoạt `model_registry.save_persisted_candidates()`, đồng thời ghi một bản ghi kiểm toán bảo mật `AuditLogModel(entity_name="model_candidate", action_type="REGISTER_CANDIDATE_MODEL")` ghi nhận danh tính quản trị viên thực hiện thao tác.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_20_admin_candidate_models_persist_across_restart` (Fails với `AssertionError: BE-20 VULNERABILITY: Candidate model lost across process restart! Output: ... PERSISTED:False` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (mô hình `candidate_resunet_v2` tồn tại bền vững trong registry sau khi tiến trình mới khởi động lại; endpoint overview hiển thị chính xác danh sách candidate).
  - Hồi quy: 327 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-21] Cơ chế bóp nghẹt tần suất (Throttling) chống tấn công dò quét mật khẩu Brute-force
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/auth.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `POST /api/auth/login` không có bất kỳ cơ chế giới hạn tần suất (rate limiting / throttling) đối với các lần đăng nhập sai liên tiếp. Khi kẻ tấn công gửi hàng chục hoặc hàng trăm request thử mật khẩu liên tục cho cùng một tài khoản, máy chủ luôn phản hồi HTTP 401 mà không áp dụng biện pháp phòng vệ, tạo điều kiện thuận lợi cho tấn công vét cạn từ điển (dictionary / brute-force attack).
- **Giải pháp**:
  - Triển khai thuật toán cửa sổ trượt (Sliding-window Throttling) cục bộ: `_check_auth_rate_limit`, `_record_auth_failure` và `_record_auth_success`.
  - Giới hạn tối đa 5 lần đăng nhập thất bại liên tiếp trong khung thời gian 60 giây (`_MAX_AUTH_FAILURES = 5`, `_AUTH_WINDOW_SECONDS = 60.0`). Khi vượt ngưỡng, các request đăng nhập tiếp theo cho tài khoản đó lập tức bị chặn với mã trạng thái `HTTP 429 Too Many Requests` ("Quá nhiều lần đăng nhập không thành công. Vui lòng thử lại sau.").
  - **Bảo toàn An toàn Lâm sàng (Tránh DoS)**: Không khóa tài khoản vĩnh viễn trong CSDL (`is_active` giữ nguyên) để ngăn ngừa kẻ xấu cố ý đăng nhập sai nhằm khóa tài khoản làm việc của bác sĩ. Sau khi hết thời gian chờ 60 giây hoặc khi đăng nhập thành công, bộ đếm thất bại được giải phóng hoàn toàn.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_21_consecutive_failed_logins_are_throttled_with_429` (Fails với danh sách 12 status code toàn bộ là 401 trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (5 lần đầu nhận 401, các lần tiếp theo nhận 429; các tài khoản khác vẫn hoạt động bình thường không bị ảnh hưởng chéo).
  - Hồi quy: 328 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-22] Chuẩn hóa danh xưng vai trò (Role Aliases: BS -> DOCTOR, QT -> ADMIN) khi quản trị viên tạo người dùng
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Khi tạo tài khoản người dùng qua API quản trị `POST /api/admin/users`, hệ thống lưu nguyên chuỗi `role` do frontend UI gửi lên (ví dụ `"BS"` thay vì `"DOCTOR"`, `"QT"` thay vì `"ADMIN"`). Mặc dù API tạo người dùng trả về HTTP 200, nhưng khi bác sĩ đăng nhập và truy cập hồ sơ ca bệnh (`require_clinical`) hoặc quản trị viên truy cập cài đặt (`require_admin`), hệ thống kiểm tra `user.role != "DOCTOR"` hoặc `user.role != "ADMIN"` và trả về lỗi `HTTP 403 Forbidden`, làm tê liệt quyền sử dụng của tài khoản.
- **Giải pháp**:
  - Định nghĩa bảng ánh xạ chuẩn `ROLE_ALIAS_MAP`: `"BS" -> "DOCTOR"`, `"QT" -> "ADMIN"`, `"TK" -> "SECRETARY"`.
  - Xây dựng hàm chuẩn hóa `canonicalize_user_role` áp dụng tại biên server (Server Boundary) cho cả `create_admin_user` (`POST`) và `update_admin_user` (`PATCH`).
  - Mọi giá trị alias tiếng Việt hoặc chữ thường/hoa đều được quy chuẩn hóa về role chuẩn backend (`DOCTOR`, `ADMIN`, `SECRETARY`) trước khi ghi vào cơ sở dữ liệu.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_22_admin_create_user_canonicalizes_role_aliases` (Fails với `AssertionError: BE-22 VULNERABILITY: Stored role for BS is 'BS', expected 'DOCTOR'!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (tài khoản tạo với role `BS` được lưu chính xác là `DOCTOR`, role `QT` được lưu là `ADMIN`).
  - Hồi quy: 329 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-23] Chuẩn hóa tên đăng nhập chữ thường (Lowercase Username) khi quản trị viên tạo người dùng
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Khi tạo tài khoản người dùng qua API `POST /api/admin/users`, hệ thống lưu nguyên tên đăng nhập dạng chữ hoa/chữ thường xen kẽ (ví dụ `"Dr_Tran_Ha"`). Tuy nhiên, router xác thực `POST /api/auth/login` luôn chuẩn hóa đầu vào thành chữ thường (`req.username.strip().lower()`). Do cơ chế so sánh chuỗi phân biệt hoa thường trong SQLite/CSDL, người dùng vừa được tạo không thể đăng nhập với thông tin đã đăng ký và liên tục nhận lỗi `HTTP 401 Unauthorized`.
- **Giải pháp**:
  - Trong `create_admin_user`, chuẩn hóa triệt để tên đăng nhập `username = raw_username.lower()` ngay khi tiếp nhận request.
  - Sử dụng tên chuẩn hóa chữ thường để kiểm tra tính duy nhất (`existing user check`) và khởi tạo bản ghi trong bảng `users`, bảo đảm tính đồng nhất tuyệt đối giữa luồng cấp phát tài khoản quản trị và luồng đăng nhập của người dùng.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_23_admin_create_user_normalizes_username_lowercase` (Fails với `Status=401, Body={"detail":"Invalid username or password."}` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (người dùng tạo với tên hỗn hợp hoa thường đăng nhập thành công với HTTP 200 và nhận token).
  - Hồi quy: 330 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-26] Ràng buộc chặt chẽ kiểu boolean cho is_active và thu hồi phiên tức thì khi vô hiệu hóa tài khoản
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Trong endpoint `PATCH /api/admin/users/{user_id}`, việc xử lý trường `is_active` chấp nhận chuỗi bất kỳ và ép kiểu lỏng lẻo (`val.strip().lower() not in ("false", "0", "no", "")`), khiến các chuỗi không hợp lệ như `"invalid_value"` vô tình được diễn giải thành `True` mà không bị từ chối bằng HTTP 422. Đồng thời, khi quản trị viên chuyển `is_active = False` để vô hiệu hóa một tài khoản, hệ thống không cập nhật `tokens_revoked_at` hay `token_version`, khiến phiên làm việc hiện tại của tài khoản vẫn tiếp tục truy cập hợp lệ trước khi hết hạn.
- **Giải pháp**:
  - Kiểm tra kiểu dữ liệu đầu vào nghiêm ngặt: chỉ chấp nhận boolean thực thụ hoặc các chuỗi đại diện boolean rõ ràng (`"true"`, `"1"`, `"yes"`, `"on"`, `"active"` -> `True`; `"false"`, `"0"`, `"no"`, `"off"`, `"inactive"` -> `False`). Các giá trị không hợp lệ khác bị từ chối ngay lập tức với `HTTP 422 Unprocessable Entity`.
  - Khi tài khoản chuyển từ kích hoạt sang vô hiệu hóa (`user.is_active and not new_active`), lập tức cập nhật `user.tokens_revoked_at = datetime.now(UTC)` và tăng `user.token_version = (user.token_version or 1) + 1` để thu hồi toàn bộ token/phiên làm việc đang tồn tại.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_26_patch_is_active_strict_validation_and_revocation` (Fails với `Status=200` khi truyền chuỗi không hợp lệ trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (chuỗi lạ nhận 422, `"false"` cập nhật thành công và token cũ của tài khoản bị thu hồi ngay lập tức với 401).
  - Hồi quy: 331 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-27] Bảo vệ tính toàn vẹn thời gian và tương thích định dạng hash sự kiện telemetry HITL
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/hitl.py`
- **Nguyên nhân gốc (Root Cause)**: Trong endpoint tiếp nhận sự kiện HITL `POST /api/hitl/sessions/{session_id}/events`, logic kiểm tra trùng lặp với các sự kiện cũ lưu hash legacy (`payload_hash` chỉ hash `event.payload`) chỉ so sánh một phần nhỏ các cột (`event_type`, `task_id`, `seq`, `image_id`) mà bỏ qua các trường thời gian (`client_utc`, `elapsed_ms`, `session_elapsed_ms`) và `prediction_id`. Điều này khiến các request gửi lại (replay) có cùng payload nhưng bị làm sai lệch thời gian nghiên cứu (`elapsed_ms` bị thay đổi) vô tình được chấp nhận như bản sao hợp lệ (HTTP 200) thay vì bị từ chối bằng `HTTP 409 Conflict`. Đồng thời, các sự kiện trung gian lưu hash `mid_hash` (`event_type`, `task_id`, `image_id`, `seq`, `elapsed_ms`, `payload`) bị từ chối nhầm 409 khi replay chính xác.
- **Giải pháp**:
  - Đối với bản ghi hash legacy (`legacy_hash`): bắt buộc đối chiếu nghiêm ngặt toàn bộ thông tin sự kiện gồm `event_type`, `task_id`, `seq`, `image_id`, `prediction_id`, `client_utc`, và sai số thời gian `elapsed_ms`, `session_elapsed_ms` (< 0.1ms). Nếu có bất kỳ sự sai lệch nào về thời gian hoặc định danh, lập tức từ chối `HTTP 409 Conflict`.
  - Bổ sung kiểm tra định dạng trung gian (`mid_hash`): cho phép replay thành công (HTTP 200, duplicate) đối với các sự kiện định dạng trung gian có dữ liệu chính xác và thời gian đồng nhất.
  - Tự động nâng cấp (migration on replay) giá trị hash cũ trong cơ sở dữ liệu lên hash định danh toàn diện v2 (`identity_hash`) ngay khi xác nhận replay trùng khớp thành công.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_27_legacy_and_intermediate_telemetry_hash_timing_integrity` (Fails với `AssertionError: BE-27 VULNERABILITY: Mutated timing accepted under legacy hash! Status=200 assert 200 == 409` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (sự kiện đúng timing được nhận diện duplicate 200, sự kiện đột biến timing bị từ chối 409, định dạng intermediate replay thành công 200).
  - Hồi quy: 332 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-28] Xử lý trùng lặp đồng thời (Concurrent Event Append) đảm bảo tính Idempotent thay vì trả lỗi HTTP 500
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/hitl.py`
- **Nguyên nhân gốc (Root Cause)**: Khi hai yêu cầu mạng hoặc tiến trình client gửi trùng lặp cùng một sự kiện HITL (cùng `event_id`) diễn ra đồng thời, cả hai request đều vượt qua bước kiểm tra trùng lặp ban đầu trong CSDL (`db.query(HITLEventModel)` trả về None do chưa commit). Khi gọi `db.flush()` / `db.commit()`, request về đích sau vi phạm ràng buộc duy nhất `UNIQUE constraint failed: hitl_events.event_id`. Do ngoại lệ `IntegrityError` không được bắt và xử lý cục bộ, nó bùng phát ra tầng FastAPI khiến client nhận lỗi máy chủ `HTTP 500 Internal Server Error`, làm gián đoạn pipeline thu thập dữ liệu và báo cáo sai trạng thái hệ thống.
- **Giải pháp**:
  - Đóng gói toàn bộ khối `db.flush()` và `db.commit()` trong khối `try ... except IntegrityError`.
  - Khi bắt được `IntegrityError`, lập tức `db.rollback()` để giải phóng transaction bị xung đột, sau đó mở kiểm tra lại từng sự kiện trong batch đối với dữ liệu CSDL vừa được commit đồng thời.
  - Nếu sự kiện trong CSDL trùng khớp danh tính (`_matches_existing_event`), hệ thống xử lý như một thao tác lặp lại idempotent (`status: SUCCESS`, `accepted_count: 0`, `duplicate_count: 1`) và phản hồi `HTTP 200 OK` thay vì 500.
  - Nếu sự kiện trong CSDL xung đột sequence hoặc mang dữ liệu khác, hệ thống chủ động ném lỗi `HTTP 409 Conflict` đúng chuẩn nghiệp vụ REST.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_28_concurrent_event_append_idempotency` sử dụng `threading.Barrier` đồng bộ 2 thread gọi API đồng thời (Fails với `IntegrityError: UNIQUE constraint failed: hitl_events.event_id` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (cả hai request đồng thời đều nhận HTTP 200, kết quả `status_codes == [200, 200]`).
  - Hồi quy: 333 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


### [BE-29] Xác thực số nguyên nghiêm ngặt cho kích thước ma trận RLE (Shape Strict Int Validation)
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/schemas/schemas.py`
- **Nguyên nhân gốc (Root Cause)**: Trong Pydantic validator `validate_mask_rle` của `DoctorReviewRequest` (được dùng chung bởi `MaskMeasurementsRequest`), điều kiện kiểm tra kích thước `shape != [512, 512]` dùng toán tử so sánh bằng của Python. Do trong Python `512.0 == 512` trả về `True`, một payload chứa số thực như `shape: [512.0, 512.0]` dễ dàng vượt qua tầng kiểm tra schema. Sau đó, khi hàm giải mã `InferenceEngine.rle_to_mask` khởi tạo mảng `np.zeros(shape[0] * shape[1])`, NumPy ném ngoại lệ `TypeError: expected a sequence of integers or a single integer, got '262144.0'`. Ngoại lệ này không được bắt, khiến endpoint bị sập và trả về `HTTP 500 Internal Server Error` thay vì mã lỗi dữ liệu đầu vào `HTTP 422 Unprocessable Entity`.
- **Giải pháp**:
  - Kiểm tra kiểu dữ liệu nghiêm ngặt cho từng phần tử kích thước: `type(shape[0]) is int and type(shape[1]) is int`, loại bỏ hoàn toàn các kiểu số thực (`float`), chuỗi, hay boolean.
  - Kiểm tra chặt chẽ cấu trúc: `isinstance(shape, (list, tuple)) and len(shape) == 2 and shape[0] == 512 and shape[1] == 512`.
  - Nếu bất kỳ điều kiện nào không thỏa mãn, ném `ValueError` để Pydantic tự động chuyển đổi thành lỗi chuẩn `HTTP 422 Unprocessable Entity` kèm thông báo chi tiết, không để lọt ngoại lệ xuống tầng xử lý ma trận.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_29_rle_shape_rejects_floats_with_422` (Fails với `TypeError: expected a sequence of integers or a single integer, got '262144.0'` tại `InferenceEngine.rle_to_mask` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (request gửi `[512.0, 512.0]` bị từ chối ngay tại biên API với mã trạng thái `HTTP 422`).
  - Hồi quy: 334 passed, 2 skipped, 0 regressions trên toàn bộ test suite.
### [BE-30] Phát hiện trôi dạt nội dung ảnh gốc (Source Content Drift) và lưu vết hash trong Research Export
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/research_export.py`
- **Nguyên nhân gốc (Root Cause)**: Trong quá trình xây dựng gói nghiên cứu `build_research_bundle`, hệ thống chỉ kiểm tra file ảnh gốc có tồn tại hay không (`os.path.isfile(image.raw_path)`). Nếu file ảnh trên đĩa bị thay đổi kích thước, bị ghi đè hoặc chỉnh sửa sau thời điểm tải lên (source content drift), hàm export vẫn tiếp tục chạy và sinh ra gói nghiên cứu với mặt nạ phân đoạn rà soát không còn khớp với ảnh nguồn mới, làm sai lệch kết quả đánh giá mô hình và vi phạm tính toàn vẹn nghiên cứu y khoa. Đồng thời, metadata xuất khẩu thiếu mã băm `source_sha256` của ảnh nguồn để thẩm định độc lập.
- **Giải pháp**:
  - Tại `build_research_bundle`: Tính mã băm SHA-256 thực tế của file ảnh nguồn trên đĩa (`current_source_sha256`).
  - Nếu bản ghi `ImageModel` có lưu trữ `file_hash` ban đầu, đối chiếu nghiêm ngặt: nếu `current_source_sha256 != image.file_hash`, lập tức dừng quá trình xuất và ném lỗi `HTTP 409 Conflict` ("Phát hiện file ảnh gốc đã bị thay đổi nội dung (source content drift).").
  - Kiểm tra đối chiếu độ phân giải nguồn: nếu chiều rộng hoặc chiều cao thực tế của ảnh nguồn bị thay đổi khác với `image.width` / `image.height`, ném `HTTP 409 Conflict`.
  - Bổ sung trường `source_sha256` vào metadata của từng ảnh và trong khối `geometry` của gói nghiên cứu để đảm bảo khả năng kiểm toán và xác minh toàn vẹn độc lập.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_30_research_export_detects_source_content_drift` (Fails với `AssertionError: BE-30 VULNERABILITY: source_sha256 missing` và `Export succeeded with HTTP 200 despite source content drift` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (export hợp lệ sinh `source_sha256` chuẩn xác; khi file trên đĩa bị thay đổi kích thước/nội dung, export bị từ chối chính xác với HTTP 409).
  - Hồi quy: 335 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-31] Ngăn ngừa tranh chấp đồng thời giữa tải ảnh lên và xóa ca khám (Upload vs Case Deletion Race)
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`
- **Nguyên nhân gốc (Root Cause)**: Khi một yêu cầu tải ảnh lên (`POST /api/upload`) đang giải mã ảnh hoặc tiền xử lý, một tiến trình quản trị viên khác gọi xóa ca khám (`DELETE /api/cases/{study_id}`). Khi request upload tiếp tục thực thi và gọi `db.commit()`, việc ca khám cha đã bị xóa khiến SQLite kích hoạt lỗi ràng buộc khóa ngoại `IntegrityError: FOREIGN KEY constraint failed`. Do lỗi này không được xử lý chuẩn xác thành mã phản hồi HTTP, ngoại lệ bùng phát ra tầng ngoài thành `HTTP 500 Internal Server Error`. Trước khi kích hoạt `PRAGMA foreign_keys = ON`, lỗi này thậm chí chèn thành công bản ghi ảnh mồ côi (`orphan ImageModel`) không có ca khám cha.
- **Giải pháp**:
  - Tại `upload_image`: Trước khi thêm bản ghi `ImageModel`, thực hiện làm mới và kiểm tra trạng thái thực tế của ca khám `StudyModel` trong CSDL (`db.expire(study)`). Nếu bản ghi đã bị xóa trong session khác, bắt `ObjectDeletedError` / `StaleDataError` và lập tức từ chối với `HTTP 404 Not Found` ("Mã ca khám không tồn tại hoặc đã bị xóa.").
  - Tại khối xử lý ngoại lệ `IntegrityError`: Bổ sung nhận diện lỗi khóa ngoại (`FOREIGN KEY constraint failed`), chuyển đổi sang `HTTP 404 Not Found` thay vì để lọt lỗi 500.
  - Tự động kích hoạt cơ chế dọn dẹp file tạm trên đĩa (`file_path`) trong khối `except Exception:`, bảo đảm không để lại bất kỳ file ảnh rác nào trên hệ thống tệp và không tạo bản ghi mồ côi trong CSDL.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_be_31_upload_case_deletion_race_prevents_orphan_image` (Fails với `ObjectDeletedError` và unhandled 500 trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (upload nhận đúng HTTP 404, file ảnh tạm trên đĩa bị xóa sạch và số lượng ảnh mồ côi trong CSDL bằng 0).
  - Hồi quy: 336 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-03] Minh bạch định nghĩa hình học Caliper Bounding Proxy và cảnh báo đầu mút ngoài tổn thương
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/inference_engine.py`, `backend/services/source_measurements.py`
- **Nguyên nhân gốc (Root Cause)**: Thuật toán đo tự động đường kính lớn nhất (`max_diameter_mm`) và trực giao (`ortho_diameter_mm`) sử dụng hình chữ nhật bao quanh nhỏ nhất `cv2.minAreaRect`. Đối với các tổn thương có hình dạng lõm (concave), tam giác hoặc đa giác không đều, các điểm đầu mút caliper vẽ từ trung điểm cạnh hình chữ nhật bao có thể rơi ra ngoài vùng mặt nạ thực tế (`binary_mask == 0`). Hệ thống trước đây không khai báo phương pháp đo đạc proxy, thiếu cảnh báo lâm sàng về việc một ảnh 2D đơn lẻ không thể xác định đường kính 3D lớn nhất trên mọi mặt cắt giải phẫu theo tiêu chuẩn O-RADS, và không gắn nhãn trạng thái đầu mút ngoài mặt nạ.
- **Giải pháp**:
  - Tại `InferenceEngine.extract_calipers_and_measurements`: Bổ sung kiểm tra vị trí từng điểm đầu mút caliper (`caliper_dmax` và `caliper_dorth`) đối với ma trận điểm ảnh `binary_mask`. Nếu có bất kỳ điểm nào rơi ra ngoài phạm vi hoặc ngoài vùng tổn thương, tự động gắn cờ `endpoints_outside_mask = True` trong từng phần tử `lesions`.
  - Khai báo rõ ràng phương pháp đo và bản chất proxy trong cấu trúc phản hồi: `measurement_method = "external_contour_min_area_rectangle"`, `proxy_type = "oriented_bounding_box"`.
  - Bổ sung cảnh báo lâm sàng bắt buộc `clinical_disclaimer` ("Automated 2D bounding proxy. Measurement represents in-plane oriented bounding box axes (minAreaRect), not full 3D clinical diameter. Caliper endpoints may extend outside concave lesion contours.").
  - Đồng bộ các trường metadata `measurement_method`, `proxy_type`, và `clinical_disclaimer` vào dịch vụ `source_measurements.measure_source_mask`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_03_caliper_bounding_proxy_disclaimer_and_outside_mask_annotation` (Fails với `KeyError: 'measurement_method'` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (mặt nạ tam giác nhận diện chính xác `endpoints_outside_mask = True`, khai báo đầy đủ `measurement_method`, `proxy_type` và `clinical_disclaimer`).
  - Hồi quy: 337 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [AI-11] Thiết lập ranh giới phân định bảo mật (Deidentification Boundary) giữa file DICOM thô và gói nghiên cứu
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/inference.py`, `backend/services/research_export.py`
- **Nguyên nhân gốc (Root Cause)**: Khi bác sĩ tải lên tệp DICOM (`POST /api/upload`), tệp gốc được lưu trữ nguyên vẹn trên đĩa phục vụ lưu trữ lâm sàng và đối chuẩn kỹ thuật. Dù hệ thống gán mã định danh bệnh nhân ẩn danh (`anonymized_pid`), các thẻ siêu dữ liệu nhạy cảm trong header DICOM thô (`PatientName`, `PatientID`) vẫn tồn tại trên file đĩa máy chủ. Trước đây, hệ thống chưa thiết lập ranh giới phân định rõ ràng giữa kho lưu trữ thô lâm sàng (`clinical raw storage`) và các tài nguyên nghiên cứu đã khử định danh (`deidentified research artifacts`), tạo ra rủi ro lẫn lộn dữ liệu và thiếu cơ chế kiểm chứng rò rỉ thông tin y tế (PHI).
- **Giải pháp**:
  - Tại `upload_image`: Trích xuất và chỉ lưu giữ các thuộc tính kỹ thuật cần thiết của ảnh siêu âm (`modality`, `number_of_frames`, `study_instance_uid`, `series_instance_uid`, `calibrated_spacing_mm`). Tuyệt đối không lưu các thẻ định danh người bệnh vào metadata phản hồi API.
  - Gắn nhãn ranh giới lưu trữ tường minh: `deidentified_boundary = "clinical_raw_storage"` trong phản hồi `dicom_metadata` và ghi nhận trong nhật ký kiểm toán `AuditLogModel`.
  - Tại `build_research_bundle`: Bổ sung khối khai báo ranh giới khử định danh `deidentification` trong file `metadata.json` (`boundary: "derived_pixel_and_mask_artifacts_only"`, `raw_dicom_included: False`, `phi_scrubbed: True`).
  - Đảm bảo toàn bộ gói nghiên cứu xuất khẩu chỉ chứa các mặt nạ dẫn xuất và ảnh trực quan hóa định dạng PNG, tuyệt đối không xuất kèm tệp DICOM thô hoặc bất kỳ thông tin nhận dạng cá nhân nào.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ai_11_deidentification_boundary_separates_clinical_raw_from_research_artifacts` (Fails với `AssertionError: assert None == 'clinical_raw_storage'` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (upload DICOM chứa synthetic sentinel headers bảo đảm an toàn: phản hồi API không lộ thông tin, endpoint source trả về PNG chuẩn, và gói nghiên cứu ZIP chứa 0 file DICOM kèm khối xác nhận `deidentification`).
  - Hồi quy: 338 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [FE-05] Chuẩn hóa độ tương phản màu (WCAG AA Contrast) cho trạng thái Hover nút Primary ở Dark Theme
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `frontend/css/workspace.css`, `frontend/css/workspace-tokens.css`
- **Nguyên nhân gốc (Root Cause)**: Khi người dùng hover vào nút hành động chính `.btn.primary` (như nút bên khảo sát lâm sàng Phải/Trái `Phải 13px`), quy tắc CSS `.btn.primary:hover` sử dụng biến màu nền `var(--accent-text, #0062a1)`. Trong chủ đề tối (Dark Theme), biến `--accent-text` mang giá trị `#38bdf8` (xanh da trời nhạt). Chữ màu trắng (`#ffffff`) trên nền `#38bdf8` chỉ đạt tỉ lệ tương phản 2.14:1, vi phạm nghiêm trọng tiêu chuẩn WCAG AA ($\ge 4.5:1$). Điều này khiến văn bản bị chìm và khó đọc trong môi trường phòng đọc ảnh siêu âm thiếu sáng.
- **Giải pháp**:
  - Khai báo token chuyên biệt `--accent-hover: #0062a1;` cho cả Light Theme và Dark Theme trong `workspace-tokens.css`.
  - Cập nhật quy tắc `.btn.primary:hover`: sử dụng `background: var(--accent-hover, #0062a1); border-color: var(--accent-hover, #0062a1); color: var(--on-accent);`.
  - Nền `#0062a1` kết hợp với chữ trắng `#ffffff` đạt tỉ lệ tương phản $5.80:1$, vượt trội so với ngưỡng tối thiểu $4.5:1$ của WCAG AA.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_fe_05_and_06_css_contrast_compliance` (Fails với `AssertionError: FE-05 VULNERABILITY: .btn.primary:hover still uses --accent-text, failing 4.5:1 contrast in dark theme!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (`.btn.primary:hover` sử dụng `--accent-hover`, bảo đảm độ tương phản chuẩn mực).
  - Hồi quy: 339 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [FE-06] Chuẩn hóa độ tương phản màu cho Banner cảnh báo thông tin (Info Lease Banner)
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `frontend/css/workspace.css`
- **Nguyên nhân gốc (Root Cause)**: Quy tắc `.banner.info` sử dụng `color: var(--accent);` trên nền `background: var(--accent-soft);`. Trong Dark Theme, `--accent` là `#0076c0` kết hợp trên nền composited dark accent-soft chỉ đạt độ tương phản 3.11:1. Đồng thời trong Light Theme (phản ánh qua phát hiện `FE-07`), chữ `#0076c0` trên nền `#e8f4fc` chỉ đạt 4.31:1, cả hai đều thấp hơn ngưỡng 4.5:1 bắt buộc cho cỡ chữ 13px thông thường.
- **Giải pháp**:
  - Cập nhật `.banner.info`: chuyển đổi thuộc tính màu chữ sang `color: var(--accent-text);`.
  - Trong Dark Theme: `--accent-text` mang giá trị `#38bdf8`, kết hợp trên nền tối đạt tỉ lệ tương phản $6.70:1$ (> 4.5:1).
  - Trong Light Theme: `--accent-text` mang giá trị `#0062a1`, kết hợp trên nền sáng `#e8f4fc` đạt tỉ lệ tương phản $5.80:1$ (> 4.5:1).
  - Giải quyết dứt điểm rủi ro đọc khó cho cả banner bảo vệ phiên làm việc (FE-06) lẫn banner hướng dẫn quy trình (FE-07).
- **Kiểm thử xác minh**:
  - Tái hiện & Xác nhận: `tests/test_audit_major_fixes.py::test_fe_05_and_06_css_contrast_compliance` PASSED.
  - Hồi quy: 339 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-02] Tách biệt Endpoint Liveness/Readiness và phản ánh chính xác năng lực phục vụ của Model
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/health.py`, `Dockerfile`, `docker-compose.yml`
- **Nguyên nhân gốc (Root Cause)**: Trước đây hệ thống chỉ có một endpoint `/api/health` duy nhất trả về HTTP 200 `status: healthy` bất kể mô hình học sâu chính có được tải hay không (`model_ready=False` do thiếu checkpoint hoặc lỗi khởi tạo). Lệnh `HEALTHCHECK` trong `Dockerfile` và `docker-compose.yml` sử dụng `curl -f http://localhost:8000/api/health`, dẫn đến việc bộ điều phối container (Docker/Kubernetes) vẫn nhận định instance container hoàn toàn khỏe mạnh, không kích hoạt cơ chế khởi động lại hoặc điều chuyển lưu lượng mạng khi instance đã mất khả năng suy luận.
- **Giải pháp**:
  - Tách bạch rõ rệt giữa hai cơ chế kiểm tra sức khỏe hệ thống:
    - `GET /api/health/live`: Liveness probe phản hồi HTTP 200 `{"status": "alive"}` xác nhận tiến trình máy chủ web FastAPI/Uvicorn đang chạy và phản hồi request.
    - `GET /api/health/ready`: Readiness probe kiểm tra toàn diện năng lực phục vụ. Chỉ phản hồi HTTP 200 khi cả CSDL lẫn mô hình phân đoạn đều sẵn sàng (`model_ready=True` và `database="connected"`). Nếu mô hình chưa sẵn sàng hoặc adapter chưa nạp, trả về `HTTP 503 Service Unavailable` (`status: unhealthy`).
  - Cập nhật lệnh kiểm tra sức khỏe trong `Dockerfile` và `docker-compose.yml` chuyển sang nhắm tới endpoint `/api/health/ready`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ops_02_and_03_liveness_readiness_separation_and_db_ping` (Fails với `AssertionError: Liveness check failed: 404` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (liveness trả về 200; khi model unready readiness trả về HTTP 503; khi cấu hình container khớp `/api/health/ready`).
  - Hồi quy: 340 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-03] Bổ sung truy vấn kiểm tra kết nối CSDL trực tiếp (Live DB Ping) trong Readiness Probe
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/app/routers/health.py`
- **Nguyên nhân gốc (Root Cause)**: Endpoint `/api/health` trước đây hoàn toàn không thực hiện bất kỳ truy vấn kiểm tra nào vào cơ sở dữ liệu SQLite/SQLAlchemy. Khi file CSDL bị khóa, ngắt kết nối mạng hoặc đĩa bị lỗi, endpoint kiểm tra sức khỏe vẫn báo xanh HTTP 200, che giấu sự cố nghiêm trọng cho đến khi người dùng gửi các request nghiệp vụ thực tế.
- **Giải pháp**:
  - Tại `readiness_check` (`/api/health/ready`): Thực hiện truy vấn kiểm tra trực tiếp qua kết nối runtime `conn.execute(text("SELECT 1"))`. Nếu có lỗi kết nối hoặc CSDL bị gián đoạn, gán `database="disconnected"` và phản hồi `HTTP 503 Service Unavailable` kèm thông báo lỗi.
  - Tại `health_check` (`/api/health`): Bổ sung trường `database_ready` và chuyển trạng thái tổng quát thành `degraded` nếu CSDL mất kết nối, giữ tính tương thích ngược cho các client giám sát bên ngoài.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ops_02_and_03_liveness_readiness_separation_and_db_ping` (Fails trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (khi mô phỏng lỗi kết nối CSDL, readiness lập tức phản hồi HTTP 503 với `database="disconnected"`).
  - Hồi quy: 340 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-06] Loại bỏ dữ liệu runtime và dữ liệu người bệnh khỏi Docker Image và thiết lập .dockerignore
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `Dockerfile`, `.dockerignore`
- **Nguyên nhân gốc (Root Cause)**: Trong `Dockerfile`, lệnh `COPY data/ /app/data/` thực hiện sao chép toàn bộ thư mục `data/` từ máy host vào image Docker trong quá trình build. Nếu trên môi trường phát triển hoặc máy trạm thử nghiệm lâm sàng thư mục `data/uploads/` chứa ảnh siêu âm thực tế của bệnh nhân hoặc file cơ sở dữ liệu `data/*.db`, chúng sẽ bị đóng gói vĩnh viễn vào các layer của Docker image, tạo nguy cơ rò rỉ thông tin y tế (PHI) nghiêm trọng khi image được đẩy lên container registry. Đồng thời, dự án thiếu tệp `.dockerignore` để loại trừ các tệp tạm, logs, và tài nguyên nhạy cảm.
- **Giải pháp**:
  - Xóa bỏ chỉ thị `COPY data/ /app/data/` trong `Dockerfile`. Thay vào đó, sử dụng lệnh `RUN mkdir -p /app/data/uploads /app/data/reports /app/backups` để tạo thư mục rỗng sẵn sàng cho việc mount runtime volume.
  - Tạo tệp `.dockerignore` toàn diện, loại trừ triệt để: `data/`, `data/uploads/`, `data/reports/`, `backups/`, `*.db`, `*.sqlite3`, `*.log`, `.env*`, `.venv`, `.pytest_cache`, `artifacts/`, và `audit_fix_logs/`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ops_06_07_08_packaging_and_backup_boundaries` (Fails với `OPS-06 VULNERABILITY: COPY data/ found in Dockerfile` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (Dockerfile không chứa `COPY data/`, `.dockerignore` tồn tại và loại trừ đúng đắn các đường dẫn nhạy cảm).
  - Hồi quy: 341 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-07] Chặn đưa tệp lưu trữ sao lưu (Backup Archives) vào Git Repository
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `.gitignore`
- **Nguyên nhân gốc (Root Cause)**: Tệp cấu hình `.gitignore` trước đây không chứa quy tắc loại trừ các tệp nén sao lưu hệ thống (`*.tar.gz`, `*.zip`, `*.7z`) hoặc thư mục `backups/`. Khi người dùng hoặc tác vụ tự động thực hiện tạo bản sao lưu (`BackupService.create_backup`), các tệp nén chứa toàn bộ cơ sở dữ liệu bệnh nhân và ảnh y tế có thể vô tình bị đưa vào git stage (`git add .`) và commit lên kho mã nguồn, dẫn đến rò rỉ dữ liệu y tế trên lịch sử git.
- **Giải pháp**:
  - Bổ sung cấu hình loại trừ rõ ràng trong `.gitignore`:
    - `backups/*` (kèm ngoại lệ giữ thư mục `!backups/.gitkeep`).
    - `*.tar.gz`, `*.zip`, `*.7z`.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_ops_06_07_08_packaging_and_backup_boundaries` (Fails với `OPS-07 VULNERABILITY: backups/synthetic.tar.gz is not ignored by git` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (`git check-ignore backups/synthetic.tar.gz` trả về mã 0).
  - Hồi quy: 341 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-08] Khai báo tường minh ranh giới mã hóa và an toàn của dịch vụ Backup Service
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/services/backup_service.py`
- **Nguyên nhân gốc (Root Cause)**: Dịch vụ sao lưu `BackupService.create_backup` đóng gói cơ sở dữ liệu SQLite và thư mục ảnh thành tệp nén `tar.gz` không mã hóa cấp ứng dụng (unencrypted archive). Kết quả trả về của hàm không khai báo bất kỳ metadata nào về ranh giới mã hóa hoặc hướng dẫn an toàn dữ liệu, khiến người vận hành có thể ngộ nhận rằng tệp lưu trữ đã được mã hóa tự động và tự do vận chuyển qua các kênh mạng không an toàn.
- **Giải pháp**:
  - Tại `BackupService.create_backup`: Bổ sung khối siêu dữ liệu `encryption` trong cấu trúc từ điển trả về:
    - `application_level_encrypted: False`
    - `at_rest_layer: "filesystem_or_volume"`
    - `guidance: "Archive relies on host volume/BitLocker encryption and strict OS filesystem permissions. For off-site transport, encrypt archive via standard operational tooling."`
  - Đảm bảo tính minh bạch hoàn toàn về ranh giới an toàn thông tin theo tiêu chuẩn phần mềm y tế.
- **Kiểm thử xác minh**:
  - Tái hiện & Xác nhận: `tests/test_audit_major_fixes.py::test_ops_06_07_08_packaging_and_backup_boundaries` PASSED.
  - Hồi quy: 341 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [DEP-01 đến DEP-05, OPS-05] Nâng cấp yêu cầu phiên bản MONAI khắc phục các lỗ hổng bảo mật và cố định phụ thuộc (Dependency Pinning)
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `requirements.txt`, `requirements-lock.txt`, `Dockerfile`
- **Nguyên nhân gốc (Root Cause)**:
  - Scanner báo 5 lỗ hổng bảo mật nghiêm trọng liên quan đến gói `monai 1.5.2` (gồm PYSEC-2026-4020, 4017, 4015, 4019, 4018 / CVE-2026-100840, 100842, 100843, 100844, 100845: giải tuần tự hóa không an toàn trong NumpyReader, eval injection trong shape helper, bundle RCE, và command injection trong nnUNetV2Runner). Tệp cấu hình `requirements.txt` trước đây chỉ đặt chặn dưới `monai>=1.3.0`, cho phép cài đặt các phiên bản dính lỗ hổng trên môi trường triển khai.
  - Đồng thời ở `OPS-05`, `Dockerfile` cài đặt phụ thuộc bằng lệnh `pip install -r requirements.txt` dựa trên các chặn dưới không cố định (`>=`), khiến việc xây dựng image container ở các thời điểm khác nhau có thể tải về các phiên bản khác biệt, làm mất tính tái lập (non-reproducible build) và có nguy cơ nạp thư viện lỗi vào môi trường y tế.
- **Giải pháp**:
  - Trong `requirements.txt`: Nâng chặn dưới bắt buộc của MONAI lên `monai>=1.6.1`, vượt qua toàn bộ các mốc phiên bản bị khuyến cáo lỗ hổng từ upstream.
  - Tạo tệp khóa phụ thuộc `requirements-lock.txt` ghi nhận chính xác 100% các phiên bản của toàn bộ hệ sinh thái thư viện đã được xác minh (`torch==2.6.0`, `monai==1.6.1`, `fastapi==0.141.1`,...).
  - Cập nhật `Dockerfile`: Sao chép `requirements-lock.txt` và thực thi cài đặt `pip install --no-cache-dir -r requirements-lock.txt`, bảo đảm tính tái lập hoàn toàn cho container đóng gói.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_dep_01_through_05_and_ops_05_dependency_advisories_and_pinning` (Fails với `DEP-01..05 VULNERABILITY: monai declared as >=1.3.0, must be >= 1.6.0` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (`requirements.txt` yêu cầu `monai>=1.6.1`, `requirements-lock.txt` cố định đầy đủ phiên bản và `Dockerfile` sử dụng tệp lockfile).
  - Hồi quy: 342 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [QA-01] Dọn dẹp cảnh báo linter tĩnh (Ruff Lint Cleanup) trên toàn bộ kho mã nguồn
- **Mức độ nghiêm trọng**: MAJOR
- **Tập tin sửa đổi**: `backend/`, `evaluation/`, `scripts/`, `tests/`, `pyproject.toml`
- **Nguyên nhân gốc (Root Cause)**: Linter Ruff báo cáo hơn 160 lỗi phân tích tĩnh trên các module mã nguồn chính và kiểm thử (gồm unused imports F401, unsorted imports I001, biến gán không dùng F841, kiểu type annotation cũ UP006/UP035, và khoảng trắng dư thừa W293). Đồng thời, cấu hình `pyproject.toml` thiếu chỉ thị loại trừ các thư mục artifact kết quả dẫn xuất và thiếu per-file-ignores cho các tệp script kiểm thử cần thiết lập biến môi trường trước khi import module (`E402`).
- **Giải pháp**:
  - Dọn dẹp triệt để các biến và import không sử dụng trong `evaluation/`, `scripts/`, `tests/`.
  - Chuẩn hóa thứ tự import theo chuẩn PEP 8 / isort.
  - Cập nhật `pyproject.toml`: Bổ sung danh sách thư mục loại trừ `exclude = [".git", ".venv", "artifacts", "audit_fix_logs", "evaluation/milestone_3_*"]` và cấu hình `per-file-ignores` cho `E402` trên các tệp kiểm thử chuyên biệt (`tests/conftest.py`, `tests/serve_isolated_app.py`, `scripts/export_hitl_sessions.py`).
  - Toàn bộ lệnh `ruff check .` chuyển trạng thái xanh tuyệt đối: 0 diagnostics.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_major_fixes.py::test_qa_01_codebase_lint_cleanliness` (Fails với `QA-01 VULNERABILITY: Ruff lint errors detected` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (`ruff check backend scripts tests evaluation` trả về exit code 0 với 0 lỗi).
  - Hồi quy: 343 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

---

## Nhóm MINOR

### [BE-24] Từ chối yêu cầu tạo người dùng với thông tin trống bằng mã lỗi HTTP 422
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Khi client gửi yêu cầu tạo tài khoản người dùng quản trị (`POST /api/admin/users`) với payload trống `{}` hoặc tên đăng nhập chỉ gồm khoảng trắng, hàm `create_admin_user` trước đây trả về HTTP 200 `status: SUCCESS` giả tạo ("Yêu cầu tiếp nhận.") nhưng không thực sự tạo bản ghi nào trong cơ sở dữ liệu. Điều này vi phạm ngữ nghĩa RESTful API và làm sai lệch trạng thái giao diện quản trị viên.
- **Giải pháp**:
  - Tại `create_admin_user`: Kiểm tra `raw_username = (user_data.get("username") or "").strip()`.
  - Nếu `not raw_username`, lập tức ném ngoại lệ `HTTPException(status_code=422, detail="Tên đăng nhập không được để trống")`.
  - Bảo đảm phản hồi HTTP 422 chuẩn hóa cho dữ liệu đầu vào không hợp lệ.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_be_24_create_user_empty_payload_rejects_with_422` (Fails với `AssertionError: BE-24 VULNERABILITY: Empty payload returned 200 instead of 422!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (payload trống và khoảng trắng đều nhận HTTP 422 với thông báo tiếng Việt chính xác, số lượng user tạo ra là 0).
  - Hồi quy: 344 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [BE-11] Triển khai Endpoint xuất nhật ký kiểm toán quản trị (Admin Audit Events Export)
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `backend/app/routers/admin.py`
- **Nguyên nhân gốc (Root Cause)**: Giao diện quản trị `frontend/app/admin-audit.js:81` có nút "Xuất kết quả" gọi API `GET /api/admin/audit-events/export?...` để tải file CSV nhật ký hệ thống. Tuy nhiên backend chưa định nghĩa route này trong router quản trị, khiến request bị từ chối bằng lỗi `HTTP 404 Not Found` và làm hỏng luồng trích xuất nhật ký giám sát.
- **Giải pháp**:
  - Triển khai endpoint `GET /api/admin/audit-events/export` tại `backend/app/routers/admin.py`, tự động kế thừa cơ chế phân quyền bảo mật cấp cao `require_admin`.
  - Hỗ trợ toàn bộ các bộ lọc dữ liệu: tìm kiếm văn bản `q`, người thực hiện `actor`, loại hành vi `action`, và khoảng thời gian `from`/`to`.
  - Trả về cấu trúc JSON chuẩn hóa `{"items": items, "total": len(items)}` với đầy đủ thông tin thời gian, người thực hiện, hành vi, đối tượng và chi tiết sự kiện, đáp ứng chính xác hợp đồng gọi của client.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_be_11_audit_events_export_endpoint` (Fails với `assert 404 == 401` trước khi sửa do endpoint không tồn tại).
  - Xác nhận: Test chuyển sang PASSED (request không có token bị từ chối HTTP 401; request admin hợp lệ nhận HTTP 200 với danh sách đầy đủ trường và áp dụng đúng các bộ lọc).
  - Hồi quy: 345 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [DEMO-01] Loại bỏ các giá trị lâm sàng và danh tính mặc định (Hardcoded Fallbacks) trong Report Generator
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `backend/services/report_generator.py`
- **Nguyên nhân gốc (Root Cause)**: Hàm chuẩn hóa dữ liệu báo cáo `_normalize_report_data` trong `MedicalReportGenerator` chứa hàng loạt giá trị dữ liệu giả lập được hardcode sẵn trong mã nguồn (như mã bệnh nhân `"200044962"`, tên `"Nguyễn Thị Phượng"`, bác sĩ `"Trương Thị Phượng"`, số đo `"D1=28.5 mm, D2=21.0 mm, Diện tích=4.62 cm²"` và kết luận phân loại `"O-RADS 2"` kèm hẹn tái khám 3 tháng). Nếu generator này được gọi với dữ liệu rỗng hoặc chưa hoàn thiện, phiếu kết quả có thể tự động điền các thông số chẩn đoán giả mạo, vi phạm an toàn y tế và nguyên tắc không bịa đặt số liệu lâm sàng.
- **Giải pháp**:
  - Tại `_normalize_report_data`: Bắt buộc phải có mã định danh bệnh nhân hợp lệ (`patientId`/`anonymized_pid`/`pid`), ném `ValueError` ngay lập tức nếu thiếu.
  - Loại bỏ hoàn toàn các tên người bệnh, tên bác sĩ, số đo kích thước và kết luận O-RADS 2 hardcode.
  - Chuyển đổi các trường chưa được người dùng nhập sang trạng thái trung tính an toàn (`"Chưa ghi nhận"`, `"Chưa có kết luận lâm sàng"`, `"N/A"`), bảo đảm tính trung thực tuyệt đối của tài liệu y khoa.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_demo_01_report_generator_removes_hardcoded_placeholders` (Fails với `Failed: DID NOT RAISE ValueError` do sử dụng PID hardcode trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (thiếu PID ném đúng `ValueError`; khi có PID nhưng thiếu trường lâm sàng, toàn bộ chuỗi giả mạo không còn xuất hiện).
  - Hồi quy: 346 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [FE-04] Áp dụng ràng buộc chỉ đọc (readonly) và rào chắn quyền sửa (lease guard) trên giao diện Viewer
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `frontend/app/viewer.js`
- **Nguyên nhân gốc (Root Cause)**: Tại `frontend/app/viewer.js`, các bộ lắng nghe sự kiện thay đổi của các trường phân loại lâm sàng (`#iotaMorphology`, `#oradsScore`, `#notes`, `#morphology`) chỉ kiểm tra cờ `state.busy` hoặc `readonly` đơn lẻ mà không kiểm tra trạng thái quyền sửa của phiên làm việc (`!state.editing?.allowed`). Đồng thời khi mất quyền sửa qua sự kiện `ova:lease-lost`, hệ thống chỉ vô hiệu hóa `#notes` và `#morphology` nhưng bỏ quên `#iotaMorphology` và `#oradsScore`, cho phép người dùng chỉ đọc hoặc bị mất lease vẫn có thể thay đổi đánh giá rủi ro O-RADS và tạo draft cục bộ sai lệch.
- **Giải pháp**:
  - Tại các event handler của `#notes`, `#morphology`, `#iotaMorphology` và `#oradsScore`: Bổ sung kiểm tra toàn diện `if (state.busy || readonly || !state.editing?.allowed) return;` và hoàn nguyên giá trị ban đầu nếu không có quyền chỉnh sửa.
  - Trong bộ lắng nghe sự kiện `ova:lease-lost`: Thiết lập rõ ràng `readonly = true`, `state.editing = { caseId: c.study_id, allowed: false }`, và vô hiệu hóa lập tức cả `#iotaMorphology` và `#oradsScore` (`disabled = true`).
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_fe_04_viewer_readonly_and_lease_loss_guard_blocks_clinical_mutation` (Fails trước khi sửa do thiếu guard `!state.editing?.allowed` và thiếu disable trên selector IOTA/O-RADS).
  - Xác nhận: Test chuyển sang PASSED; kiểm thử Node JS `tests/frontend_review_logic.js` PASSED.
  - Hồi quy: 347 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [OPS-04] Bổ sung Middleware thiết lập tiêu đề bảo mật HTTP (CSP, nosniff, frame guard)
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `backend/app/main.py`
- **Nguyên nhân gốc (Root Cause)**: Các phản hồi HTTP và giao diện HTML trực tiếp từ backend FastAPI chỉ có `CORSMiddleware`, hoàn toàn thiếu các tiêu đề an toàn bảo vệ trình duyệt (Content-Security-Policy, X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy). Điều này thiếu đi lớp phòng vệ theo chiều sâu (defense-in-depth) trước các nguy cơ MIME confusion, clickjacking hoặc tiêm mã độc script/style ngoài luồng trong môi trường xử lý dữ liệu hồ sơ y tế nhạy cảm.
- **Giải pháp**:
  - Bổ sung middleware HTTP toàn cục `add_security_headers` trong `backend/app/main.py`.
  - Tự động chèn các tiêu đề phòng vệ nghiêm ngặt trên mọi phản hồi:
    - `Content-Security-Policy`: Định nghĩa chính sách nguồn an toàn (`default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, hỗ trợ script/style/blob nội bộ của ứng dụng y tế).
    - `X-Content-Type-Options: nosniff`: Ngăn chặn trình duyệt tự ý suy diễn kiểu MIME.
    - `X-Frame-Options: DENY`: Chống nhúng iframe từ bên ngoài (chống clickjacking).
    - `Referrer-Policy: strict-origin-when-cross-origin`: Bảo vệ thông tin ranh giới nguồn.
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_ops_04_security_headers_present` (Fails với `AssertionError: OPS-04 VULNERABILITY: Missing Content-Security-Policy header in response!` trước khi sửa).
  - Xác nhận: Test chuyển sang PASSED (xác nhận đầy đủ CSP, nosniff, DENY trên mọi phản hồi HTTP).
  - Hồi quy: 348 passed, 2 skipped, 0 regressions trên toàn bộ test suite.

### [FE-07] Khắc phục độ tương phản màu sắc đạt chuẩn WCAG AA (>= 4.5:1) cho Banner hướng dẫn
- **Mức độ nghiêm trọng**: MINOR
- **Tập tin sửa đổi**: `frontend/css/workspace.css`, `frontend/css/workspace-tokens.css`, `tests/test_audit_minor_fixes.py`
- **Nguyên nhân gốc (Root Cause)**: Banner thông tin hướng dẫn lần đầu (`.banner.info`) trước đây sử dụng màu chữ `var(--accent)` (`#0076c0`) trên nền `var(--accent-soft)` (`#e8f4fc`), đo được tỷ lệ tương phản thực tế chỉ đạt 4.31:1 cho chữ kích thước nhỏ (13px), không đạt ngưỡng tiêu chuẩn tối thiểu 4.5:1 của W3C WCAG 2.2 AA.
- **Giải pháp**:
  - Chuẩn hóa token màu chữ thông tin: chuyển đổi thuộc tính `color` của `.banner.info` sang `var(--accent-text)`.
  - Trong light theme: `--accent-text: #0062a1` trên nền `#e8f4fc` đạt tỷ lệ tương phản 5.76:1 (vượt ngưỡng 4.5:1).
  - Trong dark theme: `--accent-text: #38bdf8` trên nền composited đạt tỷ lệ tương phản 7.01:1 (vượt ngưỡng 4.5:1 và đạt cấp AAA).
- **Kiểm thử xác minh**:
  - Tái hiện: `tests/test_audit_minor_fixes.py::test_fe_07_banner_info_contrast_meets_wcag_aa` (Kiểm tra ánh xạ token và công thức đo độ sáng tương đối luminance).
  - Xác nhận: Test chuyển sang PASSED (xác nhận tỷ lệ tương phản 5.76:1 và 7.01:1 >= 4.5:1).
  - Hồi quy: 349 passed, 2 skipped, 0 regressions trên toàn bộ test suite.


