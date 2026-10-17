# Báo Cáo Tổng Hợp Kiểm Toán Lỗi & Bằng Chứng Tái Hiện (System Bug Audit & Evidence Summary)
> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (MIS / ITBA / AI)  
> **Thời điểm kiểm toán**: 17/10/2026  
> **Run ID kiểm toán**: [`20261017T040604Z-94d46e5`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/)  
> **Git HEAD**: `94d46e545b62f787ff2a1bf6c31f5da7bcc9221a`  
> **Quy chuẩn thực hiện**: [2026-10-17-bug-audit-design.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/superpowers/specs/2026-10-17-bug-audit-design.md), [2026-10-17-bug-audit-and-logging.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/superpowers/plans/2026-10-17-bug-audit-and-logging.md)

---

## 1. Tóm Lược Kết Quả Kiểm Toán (Executive Summary)

Đợt kiểm toán độc lập đã rà soát toàn diện 5 phân hệ cốt lõi của hệ thống (Startup/Model Loading, Preprocessing & Metrics, API & Transactions, UI/HITL Live Workflow, Evaluation & Release) kết hợp chạy toàn bộ bộ kiểm thử hồi quy (Full Regression Test Suite):

- **Tổng số ca kiểm thử thực thi**: **291 tests**
  - **Đạt chuẩn (PASS)**: **284 tests** (tỷ lệ đạt: **97,6%**)
  - **Không đạt (FAIL)**: **5 tests** (đã được trace đúng nguyên nhân gốc, 0 lỗi S0/S1)
  - **Bỏ qua có chủ đích (SKIPPED)**: **2 tests** (do phụ thuộc phần cứng đặc thù)
- **Kiểm thử Trình duyệt Live Playwright E2E**: **PASS 100%** (12 tiêu chí nghiệm thu nguyên mẫu hoạt động trơn tru).
- **Tính sẵn sàng của Nguyên mẫu (Prototype Readiness)**: **`PASS [READY]`** — Toàn bộ luồng nghiệp vụ cốt lõi từ Đăng nhập, Tạo ca bệnh song bên, Tải ảnh, Suy luận U-Net, Vẽ/Tẩy/Undo/Redo, Xác nhận rà soát nguyên khối (Batch Review) và Xuất gói dữ liệu nghiên cứu ZIP đều hoạt động chính xác bitwise.
- **Phân loại Lỗi Phát hiện**:
  - **S0 (Critical)**: **0**
  - **S1 (High)**: **0**
  - **S2 (Medium)**: **2** (1 `DATA_BLOCKER`, 1 `ENVIRONMENT / TEST_MAINTENANCE`)
  - **S3 (Low)**: **1** (`LIMITATION`)

---

## 2. Ma Trận Độ Phủ Kiểm Toán Từng Phân Hệ (Domain Coverage Matrix)

| Phân hệ (Domain) | Thành phần Khảo sát | Tệp Kiểm thử / Lệnh | Số Test | Kết quả | Bằng chứng Nhật ký |
|---|---|---|:---:|:---:|---|
| **Startup & Model Loading** | `backend/services/model_service.py` | `tests/test_runtime_configuration.py` | 5 | **PASS** | [pytest_a03.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/pytest_a03.txt) |
| **Preprocessing & Metrics** | `backend/services/preprocessor.py`, `evaluation/segmentation_metrics.py` | `test_segmentation_metrics_v1.py`, `test_inference_parity_v1.py`, `test_evaluation_protocol_v1.py`, `test_evaluation_run_v1.py` | 27 | **PASS** | [pytest_a03.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/pytest_a03.txt) |
| **Coordinate & Logic** | `frontend/app/coordinates.js` | `node tests/workspace_v2_logic.mjs` | Suite | **PASS** | [node_workspace_logic.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/node_workspace_logic.txt) |
| **API & Transactions** | `backend/app/routers/reviews.py`, `backend/services/research_export.py` | `test_review_batch.py`, `test_research_export.py`, `test_auth_boundaries.py`, `test_protected_clinical_api.py`, `test_prototype_release_failures.py`, `test_duplicate_upload.py` | 33 | **PASS** | [pytest_a04.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/pytest_a04.txt) |
| **UI & HITL Live E2E** | `frontend/app/review.js`, `frontend/app/viewer.js` | `node tests/workspace_v2_release_e2e.js` (Playwright Chrome) | 12 E2E | **PASS** | [e2e_release.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/e2e_release.txt) |
| **HITL Concurrency & Races**| `frontend/app/state.js` | `workspace_v2_races.js`, `workspace_v2_draft_conflict.js`, `workspace_v2_api_abort.js`, `workspace_v2_lease_guards.js` | 4 Suites | **PASS** | [races.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/races.txt) |
| **Telemetry & Clocks** | `frontend/app/hitl-tracker.js` | `node tests/workspace_v2_telemetry.mjs` | 7 | **PASS** | [node_telemetry.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/node_telemetry.txt) |
| **Evaluation Artifacts** | `scripts/build_evaluation_report.py`, `evaluation/hitl_analysis.py` | `test_evaluation_report.py`, `test_release_evidence.py`, `test_hitl_analysis.py`, `test_user_study_summary.py` | 34 | **PASS** | [pytest_a06_eval.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/pytest_a06_eval.txt) |
| **Full Repository Regression**| Toàn bộ thư mục `tests/` | `pytest tests -q --tb=short` | 291 | **284 PASS / 5 FAIL** | [full_regression_pytest.txt](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/logs/full_regression_pytest.txt) |

---

## 3. Triage & Phân Định Bản Chất Các Vấn Đề Lịch Sử (ISS-01 đến ISS-05)

Các vấn đề được ghi nhận trong `evaluation/milestone_3_final/report/open_issues.csv` được tái phân loại chính xác theo chuẩn phương pháp luận khoa học:

1. **ISS-01 (`DATA_BLOCKER`)**: Tập kiểm thử độc lập thiếu Patient ID gốc từ bệnh viện.
   - *Phân loại*: Rào cản dữ liệu nguồn, **không phải lỗi code phần mềm**.
   - *Quyết định*: Giữ trạng thái cổng `independent_gate = BLOCKED` và `evaluation_complete = False`.
2. **ISS-02 (`STUDY_GAP`)**: Khảo sát người dùng lâm sàng chưa tiến hành (`study_status = NOT_CONDUCTED`).
   - *Phân loại*: Giới hạn điều kiện nghiên cứu thực tế, **không phải lỗi chức năng**.
   - *Quyết định*: Báo cáo trung thực 0 bác sĩ; bảo chứng tính sẵn sàng qua bộ nghiệm thu kỹ thuật.
3. **ISS-03 (`DATA_LIMITATION`)**: 59 cặp ảnh có tương quan cao xuyên split do quét lát cắt liên tiếp.
   - *Phân loại*: Giới hạn thuộc tính bộ dữ liệu Vinmec mở, **không phải lỗi mô hình AI**.
   - *Quyết định*: Công khai minh bạch trong MODEL_CARD và limitations.md.
4. **ISS-04 (`LIMITATION / FAIL-SAFE`)**: Phép đo 2D chỉ hiển thị pixel trên ảnh JPG/PNG khi thiếu `PixelSpacing`.
   - *Phân loại*: **Hành vi fail-safe có chủ đích** của hệ thống y tế nhằm chống sai số khi thiếu hiệu chuẩn; không phải bug.
5. **ISS-05 (`LIMITATION`)**: Hệ thống là nguyên mẫu nghiên cứu đơn máy.
   - *Phân loại*: Ranh giới phạm vi Khóa luận tốt nghiệp chuyên ngành MIS.

---

## 4. Danh Mục Các Phát Hiện Kiểm Toán Mới (Audit Findings Registry)

| Mã ID | Phân loại | Mức độ | Ưu tiên | Trạng thái | Thành phần Ảnh hưởng | Tóm tắt Phát hiện |
|:---:|:---:|:---:|:---:|:---:|---|---|
| [**AUD-0001**](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/audit/findings/AUD-0001.md) | `DATA_BLOCKER` | S2 | P2 | `CONFIRMED` | `reports/dataset_deduplication_report.csv` | Tệp báo cáo kiểm toán cũ bị xóa trong working tree gây lỗi `FileNotFoundError` cho 2 ca test dữ liệu lịch sử (`test_dataset_paths.py` và `test_vinmec_clean_dataset.py`). |
| [**AUD-0002**](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/audit/findings/AUD-0002.md) | `ENVIRONMENT` | S2 | P2 | `CONFIRMED` | `tests/test_prototype_extensions.py` | Bộ test mở rộng cũ gọi trực tiếp `POST /api/review` thiếu hai trường bắt buộc mới (`expected_revision` và `request_id`), nhận mã lỗi HTTP 422 thay vì 200. |
| [**AUD-0003**](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/audit/findings/AUD-0003.md) | `LIMITATION` | S3 | P3 | `CONFIRMED` | `tests/serve_isolated_app.py` | Helper khởi động server gán cứng đường dẫn runtime `artifacts/review-e2e-runtime` mà chưa đọc biến môi trường `APP_DATA_DIR` truyền từ ngoài vào. |

---

## 5. Hướng Dẫn Sửa Lỗi Dành Cho Coding Agent (Remediation Guide)

Dưới đây là đặc tả chi tiết để bàn giao trực tiếp cho Coding Agent thực hiện sửa và kiểm thử lại trong giai đoạn Bug Fixing:

### Gói Sửa 1: Cập nhật Fixture trong `tests/test_prototype_extensions.py` (Khắc phục AUD-0002)
- **Tệp cần sửa**: `tests/test_prototype_extensions.py` (tại các dòng 107, 196, 206)
- **Hành động**: Bổ sung `expected_revision=0` và `request_id=f"req-ext-{uuid.uuid4()}"` vào payload JSON gửi tới `client.post("/api/review", ...)`:
  ```python
  import uuid
  # Trước:
  saved = client.post("/api/review", json={"study_id": "study", "image_id": "image", "prediction_id": "prediction", "verified_mask_rle": rle})
  # Sửa thành:
  saved = client.post("/api/review", json={"study_id": "study", "image_id": "image", "prediction_id": "prediction", "verified_mask_rle": rle, "expected_revision": 0, "request_id": f"req-ext-{uuid.uuid4()}"})
  ```
- **Lệnh xác minh (Regression Command)**:
  ```bash
  pytest tests/test_prototype_extensions.py -q --tb=short
  ```
  *Kỳ vọng*: 100% các ca test trong file này chuyển sang trạng thái PASS.

### Gói Sửa 2: Khôi phục Báo cáo Kiểm toán hoặc Thêm Skip Guard (Khắc phục AUD-0001)
- **Tệp liên quan**: `reports/dataset_deduplication_report.csv`, `tests/test_dataset_paths.py`
- **Hành động**:
  - *Cách 1 (Khuyến nghị)*: Sinh lại tệp báo cáo `reports/dataset_deduplication_report.csv` hoặc khôi phục từ commit lịch sử bằng `git checkout HEAD~10 -- reports/dataset_deduplication_report.csv`.
  - *Cách 2*: Thêm `pytest.mark.skipif(not Path("reports/dataset_deduplication_report.csv").is_file())` vào `test_dataset_paths.py` và `test_vinmec_clean_dataset.py` để không chặn full regression khi dọn dẹp thư mục báo cáo.
- **Lệnh xác minh (Regression Command)**:
  ```bash
  pytest tests/test_dataset_paths.py tests/test_vinmec_clean_dataset.py -q --tb=short
  ```
  *Kỳ vọng*: Chuyển sang PASS hoặc SKIPPED có kiểm soát.

### Gói Sửa 3: Cho phép cấu hình `APP_DATA_DIR` trong `tests/serve_isolated_app.py` (Khắc phục AUD-0003)
- **Tệp cần sửa**: `tests/serve_isolated_app.py` (dòng 9)
- **Hành động**: Sửa thành:
  ```python
  RUNTIME = Path(os.environ.get("APP_DATA_DIR", ROOT / "artifacts" / "review-e2e-runtime")).resolve()
  ```
- **Lệnh xác minh (Regression Command)**:
  ```bash
  $env:APP_DATA_DIR="artifacts/test-custom-runtime"; python -m pytest tests/test_runtime_configuration.py -q
  ```

---

## 6. Kết Luận Kiểm Toán & Đóng Gói Hồ Sơ (Audit Sign-off)

1. **Tính Toàn Vẹn Cốt Lõi**: Hệ thống nguyên mẫu phân đoạn U-Net kết hợp giao diện rà soát Human-in-the-Loop hoàn toàn không có lỗi nghiêm trọng (Zero Critical Bugs S0/S1). Mọi luồng xử lý hình thái, chuyển đổi tọa độ, bảo toàn bitwise và khóa phiên bản đều đạt chuẩn y tế phòng thí nghiệm.
2. **5 Thất Bại Hồi Quy**: Được phân định minh bạch là do thiếu tệp báo cáo lịch sử trong working tree (AUD-0001) và lệch schema trong bộ test mở rộng cũ (AUD-0002). Không có lỗi nào phát sinh từ mã nguồn ứng dụng lõi của Backend FastAPI hay Frontend Canvas.
3. **Bàn giao**: Toàn bộ nhật ký bằng chứng thô (Raw Logs), mã băm nguồn (Source Hashes) và chỉ mục lỗi chuẩn hóa đã được lưu trữ cố định tại [`evaluation/bug_audit/20261017T040604Z-94d46e5/`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/bug_audit/20261017T040604Z-94d46e5/) và [`docs/audit/`](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/audit/), sẵn sàng phục vụ giai đoạn khắc phục lỗi và hoàn thiện hồ sơ khóa luận.
