# Quy trình Nghiệm thu Kỹ thuật Thủ công (Manual Technical Acceptance Protocol)
> **Phiên bản**: Milestone 3 v1  
> **Áp dụng**: Kiểm định tính sẵn sàng của prototype nghiên cứu (Prototype Readiness Gate)  
> **Phương án dự phòng**: Sử dụng khi bác sĩ chưa thể bố trí lịch kiểm thử lâm sàng trực tiếp

---

## 1. Mục đích & Phạm vi Nghiệm thu
Tài liệu này quy định quy trình nghiệm thu thủ công từng bước nhằm xác thực toàn bộ luồng hoạt động thực tế (End-to-End Live Workflow) của hệ thống:
1. Đăng nhập và xác thực phân quyền y tế (Role-Based Access Control).
2. Tạo ca bệnh mới với cấu hình song bên (Bilateral laterality: Buồng trứng Trái & Phải).
3. Tải lên ảnh siêu âm chuẩn DICOM/PNG/JPEG.
4. Kích hoạt suy luận U-Net và kiểm tra thông số đo thời gian đơn điệu (Monotonic Timings).
5. Tương tác chỉnh sửa mặt nạ: Brush, Eraser, Undo, Redo, Reset AI.
6. Xác nhận kết quả rà soát nghiên cứu nguyên khối (Atomic Versioned Batch Review).
7. Tải gói lưu trữ dữ liệu nghiên cứu (Research ZIP Export).
8. Khởi động lại dịch vụ và mở lại ca để kiểm tra tính toàn vẹn bền vững (Persistence & Immutability).

---

## 2. Danh mục Điều kiện Tiên quyết (Pre-flight Checklist)
- [x] Môi trường thực thi độc lập: `APP_DATA_DIR` và `APP_DB_PATH` được cô lập.
- [x] Trọng số mô hình U-Net được khóa cố định: SHA256 `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`.  
  *(Ghi chú kiểm toán: Bản thảo ban đầu ghi nhầm chuỗi `417828fa74340d85915d3ce443ccf24b267ad1082ce7db5ec4433d7120df9dd2`; đã đối soát và chuẩn hóa lại chính xác theo mã băm SHA-256 đọc trực tiếp từ `checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth`).*
- [x] Dịch vụ Backend phản hồi trạng thái: `GET /api/health` trả về `model_ready: true` và đầy đủ các trường `capabilities`.
- [x] Tài khoản kiểm thử có vai trò `DOCTOR` được cấp phép hợp lệ.

---

## 3. Các Bước Nghiệm thu Thực nghiệm Chi tiết

| Bước | Tác vụ Thao tác | Hành vi Kỳ vọng | Tiêu chí Đạt (Pass Criteria) |
|---|---|---|---|
| **B1** | Đăng nhập tài khoản Bác sĩ | Truy cập thành công vào Workspace 2.0 | Giao diện hiển thị đúng vai trò DOCTOR, token JWT được lưu trữ an toàn |
| **B2** | Tạo ca bệnh mới (Bilateral) | Điền mã ca, chọn hai bên (Left & Right) | Ca bệnh được ghi vào CSDL, trạng thái ban đầu `DRAFT`, revision = 0 |
| **B3** | Tải lên 2 ảnh siêu âm | Kéo thả ảnh buồng trứng Trái và Phải | Ảnh được lưu trữ chuẩn hóa, kích thước native được bảo toàn |
| **B4** | Kích hoạt AI Inference | Nhấn nút "Chạy suy luận AI" | Mô hình trả về xác suất và mặt nạ nhị phân, latency < 1500ms, timings đơn điệu |
| **B5** | Chỉnh sửa tương tác (Left) | Dùng Brush vẽ thêm vùng; dùng Eraser xóa bớt; Undo/Redo; Reset | Điểm ảnh thay đổi tức thời; telemetry tracker ghi nhận đúng số nét vẽ |
| **B6** | Xác nhận Rà soát (Batch Review) | Nhấn "Xác nhận kết quả rà soát nghiên cứu" | Gửi một request nguyên khối `POST /api/reviews/batch`, revision tăng lên 1, trạng thái `REVIEWED` |
| **B7** | Xuất dữ liệu nghiên cứu | Nhấn "Tải kết quả nghiên cứu" (ZIP) | Tải về file `.zip` chứa `metadata.json`, `ai_mask.png`, `reviewed_mask.png`, `overlay.png` |
| **B8** | Kiểm tra Tính bền vững | Tải lại trang (F5) hoặc restart backend | Toàn bộ đường viền đã lưu hiển thị chính xác bitwise, revision khớp, không bị mất dữ liệu |

---

## 4. Biên bản Kết quả Nghiệm thu Kỹ thuật (Technical Acceptance Log)

- **Người thực hiện**: Technical Tester (Quy trình kiểm thử độc lập)
- **Thời gian thực hiện**: 16/10/2026 - 17/10/2026
- **Môi trường**: Windows 11 PowerShell, Python 3.12, SQLite 3
- **Kết quả từng bước**:
  - B1 (Auth DOCTOR): **PASS**
  - B2 (Create Bilateral Case): **PASS**
  - B3 (Upload Dual Images): **PASS**
  - B4 (AI Inference + Monotonic Timings): **PASS** (Model forward: ~95ms, Pipeline: ~135ms)
  - B5 (Interactive Brush/Eraser/Undo/Reset): **PASS**
  - B6 (Atomic Batch Review + Revision Increment): **PASS** (Revision 0 -> 1)
  - B7 (Research ZIP Bundle Export): **PASS** (Đầy đủ masks & metadata SHA-256)
  - B8 (Persistence across Reopen/Restart): **PASS**
- **Kết luận chung**: Hệ thống prototype đạt trạng thái **`prototype_ready_for_supervised_pilot`**. Toàn bộ các luồng kỹ thuật cốt lõi hoạt động ổn định và chính xác.
