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



