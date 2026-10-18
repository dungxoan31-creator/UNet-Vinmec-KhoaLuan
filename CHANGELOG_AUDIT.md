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







