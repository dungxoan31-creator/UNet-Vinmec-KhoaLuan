# Xác minh email OTP khi đăng ký

## Mục tiêu

Luồng đăng ký bác sĩ yêu cầu địa chỉ email hợp lệ, gửi OTP tự động tới địa chỉ đó và chỉ kích hoạt tài khoản sau khi OTP được xác minh. Tài khoản đã tồn tại và tài khoản quản trị được bootstrap tiếp tục dùng luồng đăng nhập hiện tại.

## Hiện trạng

- `frontend/app/auth.js` hiển thị form đăng ký nhưng chưa có trường email.
- `POST /api/auth/register` tạo tài khoản `is_active=False`, không gửi thư và trả kiểu phản hồi đăng nhập.
- `UserModel` chưa lưu email. `init_db()` có cơ chế tự bổ sung cột SQLite cho schema cũ.
- Dự án chưa có SMTP client hoặc luồng OTP đăng ký. Python standard library đủ để gửi SMTP qua TLS.

## Quyết định

Dùng SMTP qua thư viện chuẩn `smtplib` và `email.message`, cấu hình bằng biến môi trường. Không thêm nhà cung cấp email hoặc dependency mới.

### Luồng đăng ký

1. Form yêu cầu username, họ tên, email, khoa/phòng ban và mật khẩu; trình duyệt kiểm tra định dạng email.
2. Backend chuẩn hóa email, kiểm tra username và email chưa được tài khoản khác sử dụng, sau đó tạo tài khoản chưa kích hoạt.
3. Backend tạo OTP sáu chữ số, lưu HMAC của mã cùng thời điểm hết hạn và số lần thử, rồi gửi email.
4. Nếu cấu hình SMTP thiếu hoặc gửi thất bại, giao dịch đăng ký bị rollback và API trả lỗi có thể hiển thị được cho người dùng.
5. Giao diện chuyển sang màn xác minh email và yêu cầu mã OTP.
6. `POST /api/auth/verify-registration-otp` kiểm tra mã, thời hạn và số lần thử. Mã hợp lệ đánh dấu email đã xác minh và kích hoạt tài khoản; mã hết hạn hoặc vượt số lần thử không kích hoạt tài khoản.
7. Sau xác minh, người dùng được đưa về đăng nhập. Không tự đăng nhập bằng tài khoản vừa xác minh.

OTP có hiệu lực 10 phút, tối đa 5 lần nhập. Mỗi đăng ký chỉ có một OTP còn hiệu lực cho email đó. API không trả OTP trong response hoặc log. OTP được HMAC bằng `APP_JWT_SECRET`, vốn đã bắt buộc trong môi trường chạy.

Màn xác minh cho phép gửi lại mã. Giới hạn gửi lại là tối đa một thư mỗi 60 giây và ba lần cho mỗi challenge; mỗi lần gửi lại thay mã cũ, đặt lại bộ đếm nhập sai và gia hạn thêm 10 phút. Cơ chế này cho phép khôi phục khi mã hết hạn hoặc thư chưa đến, đồng thời giới hạn số thư có thể gửi.

## Dữ liệu và migration

- Thêm `email` nullable vào `users` để tương thích các tài khoản cũ; email bắt buộc ở schema đăng ký.
- Thêm `email_verified` mặc định false. Người dùng cũ không bị vô hiệu hóa hoặc buộc xác minh lại.
- Bảo đảm email duy nhất không phân biệt hoa thường cho các địa chỉ có giá trị.
- Thêm bảng challenge đăng ký chứa email chuẩn hóa, mã HMAC, hạn dùng, số lần thử, số lần gửi lại, thời điểm gửi gần nhất và thời điểm tạo; xóa challenge sau khi xác minh thành công.
- Bổ sung migration SQLite trong `init_db()` theo mẫu hiện tại, không sửa hoặc xóa dữ liệu tài khoản cũ.

## Cấu hình SMTP

Ứng dụng đọc `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` và `SMTP_FROM`. Port mặc định là 587. Kết nối SMTP luôn dùng STARTTLS. Tài khoản gửi mail và host phải được cấu hình khi chạy ứng dụng. Tài liệu triển khai sẽ nêu rõ các biến này và hành vi báo lỗi khi thiếu cấu hình.

## Giao diện và API

- Màn đăng ký thêm input email `type="email"`, `required`, `autocomplete="email"`.
- Màn OTP đăng ký hiển thị địa chỉ nhận đã che một phần và input OTP sáu chữ số.
- Bổ sung route giao diện `verify-email`, tách khỏi OTP đăng nhập hiện có.
- `POST /api/auth/register` trả challenge id và email đã che; `POST /api/auth/verify-registration-otp` nhận challenge id và mã OTP, rồi trả kết quả xác minh.
- `POST /api/auth/resend-registration-otp` nhận challenge id và gửi mã mới nếu challenge còn trong giới hạn gửi lại.
- Lỗi đăng ký và xác minh được hiển thị trong form, không làm mất mật khẩu đã nhập ngoài hành vi hiện tại của trình duyệt.

## Xử lý lỗi và bảo mật

- Email trùng hoặc username trùng trả lỗi rõ ràng; tài khoản không được kích hoạt trước xác minh.
- OTP sai tăng bộ đếm thử; OTP hết hạn hoặc challenge đạt 5 lần thử thì không thể xác minh cho đến khi gửi lại mã trong giới hạn cho phép.
- Endpoint gửi lại tuân thủ thời gian chờ và giới hạn số lần gửi.
- Lỗi SMTP không để lại tài khoản pending hoặc OTP không thể gửi.
- Không ghi password, OTP, hoặc SMTP credentials vào log/API response.
- Gửi qua SMTP dùng STARTTLS; nếu xác thực SMTP được cấu hình thì sử dụng credentials tương ứng.

## Kiểm chứng

- Kiểm thử schema và migration trên database mới lẫn database cũ.
- Kiểm thử email bắt buộc, trùng email không phân biệt hoa thường, tạo challenge, OTP đúng/sai/hết hạn/quá số lần thử.
- Mock SMTP để kiểm tra email được gửi và lỗi gửi thư rollback đăng ký mà không cần tài khoản email thật.
- Kiểm tra thời gian chờ gửi lại, giới hạn gửi lại và mã mới vô hiệu hóa mã cũ.
- Kiểm thử giao diện đăng ký chuyển sang xác minh; OTP đúng kích hoạt tài khoản và đăng nhập hoạt động sau đó.

## Ngoài phạm vi

- OTP cho đăng nhập hoặc khôi phục mật khẩu.
- Đổi email, quản trị nhà cung cấp email, hoặc dashboard theo dõi email.
- Tự động đăng nhập người dùng sau khi xác minh email.
