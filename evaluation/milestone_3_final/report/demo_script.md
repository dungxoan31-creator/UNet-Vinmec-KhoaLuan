# Kịch bản Thực nghiệm Trực tiếp (5-7 Phút Rehearsal Demo Script)

Tài liệu này dùng để điều hành buổi thử nghiệm/bảo vệ nguyên mẫu Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop.

---

### Phút 0:00 - 01:00: Khởi động và Kiểm tra Tiền khả thi (Pre-flight Checks)
1. Mở PowerShell trong thư mục gốc của dự án.
2. Thiết lập biến môi trường bảo mật:
   ```powershell
   $env:APP_JWT_SECRET = "super-secret-jwt-key-minimum-32-chars-long"
   $env:APP_DOCTOR_PASSWORD = "DoctorSecurePassword2026!"
   $env:APP_ADMIN_PASSWORD = "AdminSecurePassword2026!"
   ```
3. Chạy lệnh kiểm tra tiền khả thi:
   ```powershell
   .\scripts\run_prototype.ps1 -RuntimeDir artifacts\demo-runtime -CheckOnly
   ```
4. Xác nhận log: Python virtualenv hợp lệ, trọng số checkpoint U-Net khớp SHA-256 (`417828fa...`), các biến môi trường bí mật đã được xác thực mà không bị in lộ.

---

### Phút 01:00 - 02:00: Khởi chạy và Đăng nhập Bác sĩ
1. Khởi chạy máy chủ nguyên mẫu:
   ```powershell
   .\scripts\run_prototype.ps1 -RuntimeDir artifacts\demo-runtime -Port 8000
   ```
2. Mở trình duyệt web truy cập `http://127.0.0.1:8000`.
3. Đăng nhập bằng tài khoản: `doctor` / mật khẩu `$env:APP_DOCTOR_PASSWORD`.
4. Quan sát trang chủ: Trạng thái mô hình AI báo Sẵn sàng (Ready), Checkpoint SHA-256 hiển thị minh bạch.

---

### Phút 02:00 - 03:30: Nạp ca Hai bên (Bilateral Intake) và AI Suy luận
1. Nhấn nút **"Tiếp nhận ca mới"** (New Case).
2. Nhập mã ca bệnh (VD: `CASE-DEMO-01`), chọn quy trình phân tích hai bên (Trái & Phải).
3. Tải lên 2 ảnh siêu âm buồng trứng cho Buồng trứng Trái và Buồng trứng Phải.
4. Nhấn **"Chạy AI phân tích"**:
   - Hệ thống tự động tiền xử lý Letterbox 512×512 và đưa qua mô hình U-Net.
   - Kết quả phân đoạn hiển thị trong không gian phân giải gốc (Native Space) kèm thời gian thực thi (model_forward_ms và server_pipeline_ms).

---

### Phút 03:30 - 05:00: Tương tác HITL (Brush, Erase, Undo, Redo, Reset AI)
1. Quan sát lớp phủ tổn thương (Overlay) trên ảnh Buồng trứng Trái.
2. Chọn công cụ **Brush (Cọ vẽ)**: Vẽ mở rộng thêm một vùng tổn thương.
3. Chọn công cụ **Eraser (Tẩy)**: Xóa bớt một phần viền bị lan ra ngoài.
4. Nhấn **Undo (Hoàn tác)** và **Redo**: Chứng minh lịch sử thao tác được quản lý chính xác từng pixel.
5. Nhấn **Reset AI**: Hộp thoại cảnh báo xuất hiện xác nhận hủy bỏ toàn bộ chỉnh sửa để quay về mask AI gốc. Xác nhận Reset.
6. Vẽ chỉnh sửa hoàn thiện cuối cùng trên cả 2 buồng trứng.

---

### Phút 05:00 - 06:00: Xác nhận Rà soát Atomic và Xuất Gói Nghiên cứu (ZIP Export)
1. Nhập nhận xét chuyên môn của bác sĩ vào ô ghi chú.
2. Nhấn **"Xác nhận kết quả rà soát"** (Confirm Research Review):
   - Hệ thống thực thi giao dịch cơ sở dữ liệu nguyên tử (Atomic Database Transaction), đồng thời lưu cả 2 ảnh và nâng phiên bản `review_revision` từ 0 lên 1.
3. Nhấn **"Tải kết quả nghiên cứu"**:
   - Trình duyệt tải về tệp tin ZIP `research_export_CASE-DEMO-01_rev1.zip`.
   - Mở tệp ZIP minh chứng 7 tệp tin: `metadata.json` (chứa SHA-256 của từng tệp), 2 ảnh gốc, 2 mask do AI dự đoán và 2 mask đã qua bác sĩ rà soát.

---

### Phút 06:00 - 07:00: Đối chiếu Kết quả Đánh giá và Đóng ca
1. Nhấn chuyển sang mục **"Đánh giá mô hình"** (`#evaluation`):
   - Quan sát bảng kết quả của lượt chạy chuẩn hóa `legacy_test_v1` (Dice Mean: 0.7289, HD95: 90.19 px).
   - Quan sát cảnh báo minh bạch: Cổng kiểm thử độc lập ở trạng thái `BLOCKED` do chưa có định danh bệnh nhân nguồn.
   - Mở panel phân tích lỗi đối chiếu 5 cột (Original, GT, Prediction, Overlay, Difference).
2. Kết thúc buổi demo: Tắt máy chủ bằng `Ctrl+C`. Khởi động lại máy chủ và mở lại `CASE-DEMO-01` để chứng minh toàn bộ dữ liệu đã lưu trữ bền vững.
