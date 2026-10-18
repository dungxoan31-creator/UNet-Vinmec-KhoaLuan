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

