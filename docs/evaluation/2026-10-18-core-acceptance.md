# Biên bản Nghiệm thu Kỹ thuật Cốt lõi & Diễn tập Nguyên mẫu (Core Acceptance & Rehearsal Log)
> **Thời gian thực hiện**: 2026-10-17T10:37:12+07:00  
> **Môi trường**: Windows 11 64-bit, PowerShell 5.1+, Python 3.12.10, Chrome, SQLite 3  
> **Người thực hiện**: Lead Technical Tester & Researcher  
> **Quy chuẩn đối chiếu**: [manual_acceptance.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/manual_acceptance.md), [release_runbook.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/release_runbook.md)

---

## 1. Kiểm tra Tiên quyết (Pre-flight Verification)

Quy trình pre-flight được kiểm tra thông qua lệnh chuẩn hóa trong Sổ tay vận hành:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -CheckOnly
```

**Kết quả ghi nhận**:
- **Trạng thái**: `PASS [READY]` (Mã thoát 0).
- **Môi trường Python**: `.venv\Scripts\python.exe` (Python 3.12.10).
- **Thư mục Runtime**: Cô lập tại `artifacts/prototype-runtime`.
- **Trọng số U-Net**: `checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth`.
- **Mã băm SHA-256**: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d` *(Khớp 100% manifest).*
- **Biến bảo mật**: `APP_JWT_SECRET`, `APP_DOCTOR_PASSWORD`, `APP_ADMIN_PASSWORD` được kiểm tra hợp lệ.

---

## 2. Diễn tập Luồng Thao tác Trực tiếp (Live Workflow Rehearsal)

Toàn bộ 8 bước kiểm thử thủ công và tự động (E2E Playwright Suite tại `tests/workspace_v2_release_e2e.js`) đã được diễn tập trực tiếp trên cổng cô lập `8027`:

| Bước | Tác vụ Nghiệm thu | Đo đạc / Quan sát Thực tế | Đánh giá |
|:---:|---|---|:---:|
| **B1** | Xác thực Bác sĩ (`POST /api/auth/token`) | Đăng nhập thành công tài khoản `doctor`, nhận JWT token, phân quyền `DOCTOR` | **PASS** |
| **B2** | Tạo ca bệnh song bên (`POST /api/cases`) | Khởi tạo ca bệnh với 2 bên buồng trứng (Left & Right), trạng thái `DRAFT`, revision = 0 | **PASS** |
| **B3** | Tải lên 2 ảnh siêu âm (`POST /api/cases/{id}/images`) | Upload thành công 2 ảnh B-mode 2D; bảo toàn kích thước gốc và metadata | **PASS** |
| **B4** | Kích hoạt AI Inference (`POST /api/cases/{id}/predict`) | Model forward: ~95ms, Pipeline hoàn tất: ~135ms. Timings đo đơn điệu (Monotonic) | **PASS** |
| **B5** | Tương tác Brush / Eraser / Undo / Reset | Vùng diện tích mặt nạ thay đổi từ 18,163 -> 18,980 px; bitwise mask diff được xác thực | **PASS** |
| **B6** | Xác nhận Rà soát (`POST /api/reviews/batch`) | Request nguyên khối atomic; revision tăng 0 -> 1; trạng thái chuyển sang `REVIEWED` | **PASS** |
| **B7** | Xuất dữ liệu nghiên cứu (`GET /api/cases/{id}/export`) | Tải file `.zip` chứa đầy đủ 7 tệp: `metadata.json`, `ai_mask.png`, `reviewed_mask.png`, `overlay.png` | **PASS** |
| **B8** | Kiểm tra Tính bền vững (Persistence Check) | Tải lại trang (F5) và mở lại ca; bitwise mask bảo toàn nguyên vẹn; revision khớp | **PASS** |

---

## 3. Kiểm tra Các Ranh giới Bảo vệ (Safety & Boundary Guards)

1. **Cách ly Đa ca bệnh (Multi-Case Isolation)**:
   - Tạo Ca bệnh 2 độc lập ngay sau khi chỉnh sửa Ca 1.
   - Xác thực: Mặt nạ và vùng chỉnh sửa của Ca 1 không bị rò rỉ sang Ca 2. Ca 2 nạp đúng mặt nạ AI gốc.
2. **Ngăn chặn Xung đột Phiên bản (Optimistic Locking Guard)**:
   - Thử nghiệm gửi bản rà soát với `revision = 0` khi ca đã ở `revision = 1`.
   - Kết quả: Hệ thống chặn đứng với mã lỗi HTTP `409 Conflict`, bảo vệ dữ liệu khỏi ghi đè mất dấu vết.
3. **Chặn Ký số Lâm sàng Ngoài Phạm vi (Unsupported Clinical Sign-off Guard)**:
   - Thử nghiệm kích hoạt tính năng ký xác nhận bệnh án lâm sàng tự động.
   - Kết quả: Hệ thống từ chối dứt khoát với HTTP `501 Not Implemented` và thông báo lỗi rõ ràng trên UI: hành động "Confirm" chỉ là lưu trữ nghiên cứu nguyên khối (atomic research review), không phải chữ ký số pháp lý.
4. **Bảo mật Dữ liệu Nghiên cứu (No PHI Leakage)**:
   - Kiểm tra tệp ZIP xuất ra: Tên bệnh nhân, số điện thoại hoặc mã viện thực tế đều không tồn tại trong metadata; chỉ sử dụng mã UUID ẩn danh.

---

## 4. Tóm lược Trạng thái Nghiệm thu Tổng thể

- **Nguyên mẫu Nghiên cứu (Research Prototype)**: **`prototype_ready_for_supervised_pilot = PASS`**
- **Đánh giá Khoa học Hoàn tất (Scientific Evaluation Complete)**: **`evaluation_complete = False`** *(Bị chặn bởi Cổng kiểm thử độc lập BLOCKED do thiếu ánh xạ định danh bệnh nhân nguồn).*
- **Khảo sát Lâm sàng (Clinician Survey)**: **`clinician_validation = NOT_CONDUCTED`** *(Bảo toàn tính trung thực y tế; đã có biên bản nghiệm thu kỹ thuật thay thế).*
- **Phục vụ Demo Bảo vệ Khóa luận**: Đầy đủ kịch bản demo 5–7 phút trực tiếp từ Upload -> Phân đoạn AI -> Hiệu chỉnh tương tác -> Xác nhận -> Xuất báo cáo ZIP.
