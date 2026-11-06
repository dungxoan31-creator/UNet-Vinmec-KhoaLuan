# Master Remediation & System Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan package-by-package. Steps use checkbox (`- [ ]`) syntax for tracking. Apply `ponytail` (minimal diffs, root-cause fixes, reuse existing codebase helpers, standard library first, zero unrequested bloat).

**Goal:** Triển khai toàn bộ 7 gói khắc phục (Gói 0 đến Gói 6) đóng triệt để 14 phát hiện audit (F01–F14), chuẩn hóa RBAC/tenant isolation, hoàn thiện CDSS O-RADS v2022/đa tổn thương, an toàn preprocessing/model registry, sửa race frontend/correction, audit trail/PostgreSQL, và vệ sinh dữ liệu/mã nguồn.

**Architecture:** Tách biệt rõ hai mốc: Mốc Kỹ thuật (RUO, kiểm chứng tự động và E2E) và Mốc Chuyên môn (chuyên gia có thẩm quyền phê duyệt). Giữ vững letterbox 512×512, Combo Loss, không tạo Patient ID giả, bảo toàn dirty worktree, và triển khai từng gói độc lập theo thứ tự nghiêm ngặt.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Pytest, Node.js (Playwright/Node test), SQLite / PostgreSQL.

**Spec:** `artifacts/deep_audit_20261101/REPORT.md`, `AGENTS.md`, và yêu cầu người dùng.

## Global Constraints
- Không reset repository hoặc sửa database hiện hữu để ép test xanh.
- Tách hai mốc: Mốc Kỹ thuật đạt chuẩn RUO; Mốc Chuyên môn cần hội đồng/chuyên gia thẩm định trước khi ký duyệt lâm sàng.
- Không suy Patient ID giả (`ANON-UPLOAD-*`, `BN-*`).
- Giữ letterbox 512×512, hình học mask, Combo Loss ($L_{\text{Dice}} + L_{\text{BCE}}$).
- Tạm khóa tự động inpainting caliper cho đến khi có cơ chế marker mask xác nhận và đối chuẩn chuyên môn đạt.
- Tính năng thiếu đầu vào hoặc chưa hỗ trợ phải trả trạng thái rõ ràng (`UNSUPPORTED_PATTERN`, `unavailable`), không tự suy thành "bình thường".
- Ponytail: Ưu tiên tái sử dụng hàm có sẵn trong codebase (`check_facility_access`, `get_current_user`, `require_admin`, `BaseModelAdapter`, etc.), stdlib trước thư viện ngoài, sửa đúng nguyên nhân gốc thay vì vá bề mặt.

## Review Focus
1. **F01 & F11 (Tenant Security & Global Admin):** Đảm bảo `is_global_admin` chỉ cấp qua cấu hình/manifest server; facility admin tuyệt đối không đổi mật khẩu, không sửa dữ liệu, không đọc số liệu cơ sở khác (trả 404/403).
2. **F02 & F13 (CDSS O-RADS & Multi-lesion):** Ngưỡng $100\text{ mm}$ không được hạ bậc xuống O-RADS 2; đa tổn thương phải có ID bền vững, trả `overall_category` chỉ khi toàn bộ lesion hợp lệ.
3. **F03 & F05 (Preprocessing & SRAD Keyword):** Khóa auto-inpainting an toàn; sửa `num_iter` thành `n_iter`; enum denoise `Literal["none", "lee", "srad", "median"]`.
4. **F04 & F08 (Frontend Race & Correction Cardinality):** Preprocess sequence counter loại bỏ hoàn toàn race condition; correction hỗ trợ 1–20 ảnh thay vì ép cứng đúng 2 ảnh.
5. **F06 & F12 (Audit Immutability & Indexes):** SQLite trigger chặn UPDATE/DELETE audit logs; bổ sung index `(facility_id, status, created_at)`; migration PostgreSQL có kiểm soát.
6. **F07, F09, F10, F14 (Data Split, Demo & Cleanup):** Hash file bytes thay vì tên đường dẫn; demo runtime có allowlist và cô lập secret; chuẩn hóa fixture test factory; dọn 29 ruff lint findings.

---

## Gói 0: Chốt Baseline & Chuyển Phát Hiện Thành Kiểm Thử Hồi Quy

- [ ] **Task 0.1: Ghi nhận Snapshot Baseline Manifest & Phân loại Test Failures**
  - Chốt thông tin git branch, HEAD commit hash (`12aa0763...`), dirty status vào `docs/evaluation/baseline_remediation_manifest_20261101.json`.
  - Phân loại 189 fail và 19 setup error theo nguyên nhân gốc: fixture tenant thiếu facility, contract thay đổi, logic ứng dụng.
- [ ] **Task 0.2: Xây dựng Factory Dùng Chung cho Positive Fixtures (`tests/helpers/fixture_factory.py`)**
  - Tạo factory chuẩn tạo `facility`, `user`, `study`, `image`, `lease`, `correction` trong cùng một database session, thỏa mãn 100% ràng buộc khóa ngoại (FK) và tenant constraints.
- [ ] **Task 0.3: Chuyển các Probe Bug trong `tests/audit_reproductions_20261101.py` Thành Regression Tests Hợp lệ**
  - Đảm bảo các assertions kiểm tra hành vi ĐÚNG (khi lỗi được sửa thì test pass), giữ probe cũ trong thư mục audit evidence.

---

## Gói 1: Khóa Toàn Bộ Đường Vượt Cơ Sở & Leo Quyền (F01, F11)

- [ ] **Task 1.1: Bổ sung Thuộc tính `is_global_admin` cho `UserModel`**
  - Trong `backend/db/database.py`, thêm cột `is_global_admin = Column(Boolean, default=False, nullable=False)`.
  - Đảm bảo migration an toàn trên SQLite và PostgreSQL (mặc định `False`).
  - Chỉ định tài khoản `admin` hệ thống hợp lệ trong cấu hình bootstrap mới được set `is_global_admin = True`.
- [ ] **Task 1.2: Bảo vệ Toàn diện Tuyến Quản trị Người dùng (`backend/app/routers/admin.py`)**
  - Sửa `reset_user_password`, `update_user`, `delete_user`, `create_user`:
    - Yêu cầu `current_user = Depends(require_admin)`.
    - Kiểm tra `check_facility_access(current_user, target_user.facility_id)`.
    - Facility admin chỉ được quản lý user cùng cơ sở (`facility_id = current_user.facility_id`), cố tình gán cơ sở khác hoặc tạo global admin bị từ chối 403.
    - User không tìm thấy hoặc ngoài phạm vi cơ sở trả 404 (chống dò quét danh tính).
    - Chặn tự xóa/tự vô hiệu hóa tài khoản và chặn xóa global admin cuối cùng.
- [ ] **Task 1.3: Giới hạn Phạm vi Thống kê Cơ sở (`backend/app/routers/health.py`)**
  - Trong `/api/stats`, inject `current_user` và lọc toàn bộ count/aggregate (`StudyModel`, `ImageModel`, `ReviewModel`) theo `facility_id` của người dùng. Global admin thấy toàn bộ, facility user chỉ thấy của cơ sở mình.

---

## Gói 2: Sửa Lỗi CDSS & Hoàn Thiện Quy Tắc O-RADS v2022 / Đa Tổn Thương (F02, F13)

- [ ] **Task 2.1: Khắc phục Ngưỡng Biên $100\text{ mm}$ trong CDSS Engine (`backend/services/cdss_engine.py`)**
  - Sửa điều kiện nang đơn giản: loại $100\text{ mm}$ khỏi O-RADS 2 (`30 < diameter < 100`).
  - Nang nhẵn $\ge 100\text{ mm}$ phân tầng vào O-RADS 3 khi các đặc trưng mô tả đầy đủ; nếu thiếu đặc trưng trả `UNSUPPORTED_PATTERN` (fail-closed, không tự suy O-RADS 2).
  - Viết test kiểm tra các mốc biên: 29.9 mm, 30.0 mm, 30.1 mm, 99.9 mm, 100.0 mm, 100.1 mm, NaN, Inf.
- [ ] **Task 2.2: Hợp đồng Đa Tổn Thương Hoàn chỉnh (Multi-Lesion Worst-Case Aggregation)**
  - Cập nhật `evaluate_case` và schema để nhận danh sách `lesions` (mỗi lesion có ID, revision, descriptors).
  - Tính toán `overall_category`: chỉ kết luận khi toàn bộ lesions đang hoạt động có đánh giá hợp lệ. Nếu có lesion `UNSUPPORTED_PATTERN` hoặc chưa hoàn tất, giữ `highest_known_category` làm tham chiếu và cờ `assessment_complete = False`.
  - Cập nhật giao diện `frontend/app/cdss-panel.js` hiển thị chi tiết từng tổn thương và cảnh báo khi ca chưa phân tầng đầy đủ.

---

## Gói 3: An Toàn Preprocessing, Tensor & Model Registry (F03, F05)

- [ ] **Task 3.1: Khóa Tạm Thời Chế độ Tự động Xóa Caliper (Fail-Closed Caliper Safety)**
  - Tạm khóa auto-inpainting trong `backend/services/preprocessor.py` khi chưa có xác nhận marker mask từ bác sĩ; luôn giữ ảnh gốc làm căn cứ pháp lý và lâm sàng.
  - Cập nhật `frontend/app/viewer.js` giải thích rõ trạng thái xác nhận vùng marker mask trước khi tạo ảnh dẫn xuất.
- [ ] **Task 3.2: Chuẩn hóa Keyword SRAD & Enum Denoise**
  - Sửa caller trong `preprocessor.py:416` từ `num_iter` thành `n_iter=8`.
  - Chuẩn hóa contract `denoise_method: Literal["none", "lee", "srad", "median"] = "none"`, giá trị khác trả HTTP 422.
  - Chuẩn hóa đầu vào ảnh 2D grayscale trước khi gọi bộ lọc âm học SRAD.
- [ ] **Task 3.3: Minh bạch Hợp đồng Model Registry (Native vs Fallback vs Unavailable)**
  - Trả về rõ ràng: `requested_model`, `executed_model`, `adapter_mode`, `checkpoint_hash`, `device`.

---

## Gói 4: Frontend Bất Đồng Bộ & Luồng Yêu cầu Chỉnh sửa (F04, F08)

- [ ] **Task 4.1: Xóa bỏ Race Condition trên Viewer Canvas (`frontend/app/viewer.js`)**
  - Thêm biến đếm chuỗi duy nhất `preprocessSequence = 0`.
  - Mỗi thao tác toggle/reset tăng sequence counter trước khi gửi request.
  - Khi response trả về, kiểm tra `sequence !== preprocessSequence || disposed`. Nếu cũ, đóng `ImageBitmap` và hủy vẽ.
  - Xử lý lỗi trong `catch`: hiển thị toast lỗi và khôi phục trạng thái nút bấm đã xác nhận.
- [ ] **Task 4.2: Mở rộng Hỗ trợ 1–20 Ảnh cho Correction Workflow (`corrections.py` & `corrections.js`)**
  - Bỏ ép cứng `len(expected_image_ids) == 2` trong `backend/app/routers/corrections.py`. Chấp nhận danh sách 1 đến 20 ảnh theo đúng schema.
  - Cập nhật `frontend/app/corrections.js` cho phép submit ca có 1, 2, hoặc nhiều ảnh.
  - Điều hướng kỹ thuật viên về danh sách công việc hợp lệ sau khi SUBMITTED.

---

## Gói 5: Bất Biến Hóa Audit Trail & Hỗ Trợ PostgreSQL Thực Tế (F06, F12)

- [ ] **Task 5.1: Bất biến hóa Audit Trail & Bổ sung Trường Sự kiện**
  - Tạo trigger SQLite `audit_no_update` và `audit_no_delete` ngăn chặn mọi hành vi UPDATE/DELETE trên bảng `audit_logs`.
  - Bổ sung ghi `AuditLogModel` trong transaction của `create_correction` và `submit_correction`.
  - Thêm trường `client_ip` vào bảng audit, lấy từ trusted proxy headers.
- [ ] **Task 5.2: Bổ sung Index Hiệu năng & Hỗ trợ PostgreSQL**
  - Tạo migration Alembic bổ sung index `ix_studies_facility_status_created` trên `studies(facility_id, status, created_at)`.
  - Cấu hình dialect-agnostic cho SQLite và PostgreSQL trong Alembic migrations.

---

## Gói 6: Vệ Sinh Dữ Liệu, Demo Bền Vững & Dọn Dẹp Mã Nguồn (F07, F09, F14)

- [ ] **Task 6.1: Sửa Lỗi Audit Split Hashing (`audit_patient_independence_leakage.py`)**
  - Thay thế băm chuỗi đường dẫn bằng hàm băm bytes nội dung ảnh thật (`hashlib.file_digest`).
  - Kiểm tra tồn tại của ảnh và manifest, trả `INCOMPLETE` nếu thiếu dữ liệu.
- [ ] **Task 6.2: Cô lập Môi trường Demo Bền Vững & Bảo mật Bí mật**
  - Đảm bảo `run_demo_workspace.ps1` chạy với `APP_SYNTHETIC_DEMO_MODE=1` và so khớp hash allowlist.
  - Đưa toàn bộ secrets/credentials ra file cấu hình độc lập được gitignore.
- [ ] **Task 6.3: Dọn dẹp 29 Cảnh báo Ruff Lint (Unused Imports & Variables)**
  - Rà soát từng file được liệt kê trong `ruff.log` và xóa các import/biến thừa an toàn, không có side effects.

---

## Xác nhận Hoàn thành & Nghiệm thu
- Toàn bộ unit tests và integration tests pass 100% (0 fail, 0 error).
- E2E Playwright chạy thật trên backend không mock DB.
- Xuất báo cáo nghiệm thu kỹ thuật RUO độc lập.
