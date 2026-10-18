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
