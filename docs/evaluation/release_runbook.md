# Sổ tay Vận hành & Triển khai Thử nghiệm Giám sát (Clinical & Technical Runbook)
> **Phiên bản**: Milestone 3 v1  
> **Áp dụng**: Prototype Nghiên cứu Hỗ trợ Phân vùng Siêu âm Buồng trứng Human-in-the-Loop  
> **Môi trường mục tiêu**: Windows 10/11 x64, PowerShell 5.1+

---

## 1. Yêu cầu Hệ thống (System Requirements)
- **Hệ điều hành**: Microsoft Windows 10/11 64-bit
- **Shell**: Windows PowerShell 5.1 hoặc PowerShell 7+
- **Python**: Python 3.12.x (khuyến nghị môi trường ảo `.venv`)
- **Trình duyệt**: Google Chrome (phiên bản ổn định) phục vụ giao diện và kiểm thử Playwright
- **Phần cứng**: Tối thiểu 8 GB RAM, khuyến nghị GPU NVIDIA (CUDA 12+) để suy luận U-Net dưới 100ms; CPU mode được hỗ trợ tự động (dưới 1500ms).

---

## 2. Thiết lập Biến Môi trường Bảo mật (Security Secrets)
Trước khi khởi chạy hệ thống, quản trị viên bắt buộc phải thiết lập 3 biến môi trường bảo mật:

```powershell
# 1. Khóa ký JWT (tối thiểu 32 ký tự ngẫu nhiên)
$env:APP_JWT_SECRET = "your-strong-jwt-secret-key-at-least-32-chars-long-2026"

# 2. Mật khẩu cho tài khoản Bác sĩ (vai trò DOCTOR)
$env:APP_DOCTOR_PASSWORD = "DoctorSecurePassword2026!"

# 3. Mật khẩu cho tài khoản Quản trị viên (vai trò ADMIN)
$env:APP_ADMIN_PASSWORD = "AdminSecurePassword2026!"
```

> [!CAUTION]
> Tuyệt đối không hardcode hoặc commit mật khẩu vào mã nguồn Git. Trình khởi chạy `run_prototype.ps1` sẽ từ chối khởi động (Exit code 2) nếu thiếu bất kỳ biến nào trong 3 biến trên.

---

## 3. Khóa & Xác thực Trọng số Mô hình (Model Checkpoint Verification)
Trọng số mô hình U-Net baseline đã được khóa cố định theo giao thức Milestone 3:
- **Đường dẫn**: `checkpoints\unified_vinmec_refine_2026-10-06\lr_3e-04\baseline_unet_best.pth`
- **Mã băm SHA-256**: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`

Lệnh kiểm tra mã băm độc lập trên PowerShell:
```powershell
Get-FileHash -Path "checkpoints\unified_vinmec_refine_2026-10-06\lr_3e-04\baseline_unet_best.pth" -Algorithm SHA256
```

---

## 4. Khởi chạy Hệ thống với `scripts/run_prototype.ps1`

### 4.1. Chế độ Kiểm tra Tiên quyết (Pre-flight Check Only)
Chạy kiểm tra toàn bộ môi trường, Python, checkpoint và biến bảo mật mà không kích hoạt server hay ghi đè CSDL:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -CheckOnly
```
*Kết quả mong đợi*: Báo cáo `[Launcher] Pre-flight readiness check PASSED` với mã thoát `0`.

### 4.2. Khởi chạy Thử nghiệm Giám sát (Supervised Launch)
Khởi chạy dịch vụ backend trên thư mục runtime cô lập và cổng mặc định 8000:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -RuntimeDir "artifacts/prototype-runtime" -Port 8000
```
Truy cập giao diện nghiên cứu: `http://127.0.0.1:8000`

---

## 5. Quy trình Sao lưu & Phục hồi CSDL (Backup & Restore)
Dữ liệu ca bệnh, mặt nạ đã rà soát và telemetry được lưu trữ bền vững tại file SQLite trong thư mục runtime:
- **Đường dẫn CSDL**: `<RuntimeDir>/ovarian_ai.db`

### 5.1. Sao lưu Trực tuyến An toàn (Online Backup)
Sử dụng API sao lưu SQLite chuẩn (không khóa tiến trình đọc/ghi):
```powershell
.venv\Scripts\python.exe -c "import sqlite3; src = sqlite3.connect('artifacts/prototype-runtime/ovarian_ai.db'); dst = sqlite3.connect('artifacts/backup_ovarian_ai.db'); src.backup(dst); dst.close(); src.close(); print('Backup complete!')"
```

### 5.2. Phục hồi vào Runtime Mới (Restore to Fresh Runtime)
1. Dừng tiến trình prototype.
2. Sao chép file backup vào thư mục runtime mới:
```powershell
Copy-Item "artifacts/backup_ovarian_ai.db" "artifacts/fresh-runtime/ovarian_ai.db"
```
3. Khởi chạy prototype trỏ tới runtime mới:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -RuntimeDir "artifacts/fresh-runtime" -Port 8000
```

---

## 6. Ranh giới Y tế & Giới hạn Nghiệp vụ (Clinical Boundaries)
1. **Mục đích Nghiên cứu**: Prototype được thiết kế để hỗ trợ bác sĩ rà soát hình thái tổn thương buồng trứng; tuyệt đối không dùng kết quả phân vùng tự động làm chẩn đoán bệnh lý độc lập.
2. **Abnormal != Malignant**: Vùng phân đoạn phản ánh ranh giới hình thái âm học của tổn thương buồng trứng, không đồng nghĩa với khối u ác tính.
3. **Phạm vi Dữ liệu**: Chỉ hỗ trợ ảnh siêu âm 2D B-mode (1 khung hình); các định dạng ngoài phạm vi (CT, MRI, 3D/4D multi-frame) sẽ bị từ chối tự động với mã lỗi HTTP 400.
4. **Human-in-the-Loop**: Bác sĩ luôn là người kiểm soát tối cao (Ground Truth Provider). Mọi mặt nạ phải được rà soát, chỉnh sửa bằng công cụ cọ/tẩy và xác nhận nguyên khối trước khi xuất gói dữ liệu nghiên cứu ZIP.
