# Kế hoạch Thực thi Vòng lặp Tìm Bug & Sửa Bug Toàn diện (/goal)
> **Phạm vi**: UI, UX, Frontend (FE), Backend (BE), REST API, và Toàn trình luồng lâm sàng (Flow)
> **Mục tiêu**: Quét triệt để, phát hiện toàn bộ lỗi tiềm ẩn, race condition, lỗi giao diện, lệch dữ liệu, và khắc phục tận gốc theo phương pháp Systematic Debugging. Chỉ kết thúc khi toàn bộ hệ thống không còn lỗi.

---

## 1. HẠNG MỤC RÀ SOÁT ĐA TẦNG (BUG HUNTING SCOPE)

### Tầng 1: Frontend & UI/UX (Client-side)
- [ ] Chạy toàn bộ các test frontend (`.mjs`, `.js`, `.cjs`) bao gồm cả E2E smoke tests.
- [ ] Rà soát các tệp frontend: `viewer.js`, `report-preview.js`, `review.js`, `state.js`, `intake.js`, `cases.js`, `cdss-panel.js`:
  - Bắt lỗi unhandled promise rejection / null reference khi ca bệnh chưa có ảnh hoặc chưa có mask.
  - Rà soát sự kiện bàn phím khi người dùng mở modal/dialog không bị xung đột với phím tắt workstation.
  - Rà soát CSS/layout hiển thị trên các màn hình có độ phân giải khác nhau, đảm bảo độ tương phản phòng đọc ảnh (A11y Contrast).

### Tầng 2: Backend API & Validation (Server-side)
- [ ] Chạy toàn diện 1,226+ backend tests và kiểm tra chi tiết các cảnh báo (warnings), deprecation, và test flakiness.
- [ ] Rà soát router endpoints (`backend/app/routers/`):
  - Lỗi 422 vs 400 vs 500 khi payload không hợp lệ hoặc thiếu token.
  - Lỗi rò rỉ ngoại lệ chưa bắt (Unhandled 500 Internal Server Error).
  - Race condition trong cơ chế khóa ca (Case Leases) và Region Assignments.
  - Quản lý transaction database SQLAlchemy (`db.rollback()` khi xảy ra exception).

### Tầng 3: Động cơ Lâm sàng & CDSS Logic (Medical Safety)
- [ ] Rà soát các bộ quy tắc trong `backend/services/cdss_engine.py` và `clinical_templates.py`:
  - Đảm bảo tính nhất quán tuyệt đối giữa gợi ý template và bộ quy tắc tất định.
  - Không cho phép giá trị NaN, Infinite hoặc kích thước âm lọt vào bộ tính toán Caliper.
  - Xác thực ngưỡng kích thước nang sinh lý (<30mm theo policy nghiên cứu).

### Tầng 4: Luồng Toàn trình (End-to-End Workflow Testing)
- [ ] Luồng 1: Tiếp nhận (Intake) -> Upload DICOM/PNG -> Tự động xác định bên (Laterality hint) -> Tạo ca.
- [ ] Luồng 2: Mở ca trên Workstation -> AI Segmentation -> Sửa nét vẽ cọ/tẩy -> Caliper d1/d2 -> Click Smart Macro -> Gán O-RADS.
- [ ] Luồng 3: Lưu ca -> Tạo Báo cáo Kép (Clinician Master Report + Patient-Friendly Summary) -> In báo cáo -> Xuất bản ghi nghiên cứu.

---

## 2. TIẾN ĐỘ THỰC THI & SỬA LỖI (LOOP PROGRESS)
- [ ] Vòng 1: Quét toàn bộ test suite và logs, phát hiện danh sách bug đầu tiên.
- [ ] Vòng 2: Phân tích nguyên nhân gốc (Root Cause Analysis) và khắc phục triệt để từng bug.
- [ ] Vòng 3: Tái kiểm thử và quét tiếp vòng sâu hơn (Adversarial edge cases, null injections, boundaries).
- [ ] Vòng 4: Xác minh xanh toàn diện (100% test pass, 0 bug, 0 regression).
