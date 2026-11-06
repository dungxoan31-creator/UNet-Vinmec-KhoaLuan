# Kế hoạch Triển khai: Đọc ảnh, Phân đoạn Mask và Phân loại Bệnh học (Image-Mask-Disease Classification Pipeline)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Xây dựng và tích hợp trọn gói pipeline đa nhánh: Đọc ảnh siêu âm $\rightarrow$ Phân đoạn trích xuất Mask tổn thương $\rightarrow$ Phân loại bệnh học 8 nhóm MMOTU kết hợp lập luận lâm sàng CDSS và trực quan hóa trên giao diện bác sĩ.

**Architecture:** Sử dụng mô hình phân loại ResNet-34 8-class MMOTU đã huấn luyện tối ưu (`trial_02_balanced_256_finetune_lr5e5`), kết hợp tiền xử lý CLAHE/Letterbox chuẩn ImageNet và bộ suy luận `DiagnosticReasoningEngine` để trích xuất đặc trưng hình thái từ Mask và phân loại bệnh học với cơ chế từ chối tự động (Abstain) khi độ tin cậy thấp. Kết nối dữ liệu vào `InferenceEngine`, API `/api/predict/{image_id}`, script CLI độc lập `predict_image_mask_disease.py`, và hiển thị trực quan trên Workstation UI.

**Tech Stack:** PyTorch 2.6.0+cu124, torchvision, OpenCV, FastAPI, SQLAlchemy, Vanilla ES6 JavaScript, HTML5 Canvas.

**Spec:** [docs/superpowers/plans/2026-11-02-image-mask-disease-classification.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/superpowers/plans/2026-11-02-image-mask-disease-classification.md), [metadata/mmotu_2d_classifier_labels.json](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/metadata/mmotu_2d_classifier_labels.json), [frontend/app/image-classification.js](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/frontend/app/image-classification.js).

## Global Constraints
- Bảo toàn dirty diff hiện hữu trên nhánh `temp/ui-e2e-remediation-20261029`; không reset hay thất thoát file.
- Tuyệt đối giữ ranh giới Nghiên cứu Tiền lâm sàng (Research Use Only - RUO); kết quả AI là tham khảo, không thay thế bác sĩ.
- Giữ vững hình học chuẩn Letterbox 512×512 cho phân đoạn và 256×256 cho phân loại ResNet-34.
- Không tạo mã định danh bệnh nhân giả (Synthetic Patient ID).
- Đảm bảo 100% test pass trên toàn bộ regression suites.

## Review Focus
1. Checkpoint classifier nạp an toàn trên CPU lẫn GPU (CUDA fallback CPU).
2. Xử lý trường hợp ảnh không có tổn thương (Mask rỗng / toàn số 0) hoặc kích thước bất thường mà không bị crash chia cho 0.
3. Hợp đồng dữ liệu `ai_diagnosis` tương thích hoàn toàn với hàm `classificationText()` trong `frontend/app/image-classification.js`.
4. Cơ chế Abstain kích hoạt chính xác khi xác suất Top-1 $< 0.60$ hoặc khoảng cách $p_1 - p_2 < 0.15$.
5. Nút Quick-Fill trên giao diện tự động điền nhãn bệnh tiếng Việt vào trường mô tả của bác sĩ mà không làm mất dữ liệu sẵn có.

---

### Task 1: Xây dựng Module Dịch vụ Phân loại Bệnh học (`DiseaseClassifierService`)

**Files:**
- Create: `backend/services/disease_classifier.py`
- Modify: `backend/services/inference_engine.py`
- Test: `tests/test_disease_classification_pipeline.py`

**Steps:**
- [x] 1. Viết failing unit test trong `tests/test_disease_classification_pipeline.py` kiểm tra việc nạp checkpoint ResNet-34, tiền xử lý ảnh và dự đoán xác suất 8 lớp bệnh.
- [x] 2. Tạo `backend/services/disease_classifier.py`:
  - Định nghĩa `DiseaseClassifierService` dạng singleton/service.
  - Tự động tìm kiếm checkpoint tốt nhất tại `checkpoints/mmotu_8class_accuracy_search_2026-10-27/trial_02_balanced_256_finetune_lr5e5/mmotu_resnet34_8class_best.pth`.
  - Hàm `predict_disease(image_rgb_or_bgr: np.ndarray, mask: np.ndarray | None = None, pixel_spacing_mm: float | None = None) -> dict`:
    + Trích xuất ROI từ mask nếu có hoặc dùng ảnh toàn cảnh.
    + Tiền xử lý: chuyển sang LAB, áp dụng CLAHE lên kênh L, Letterbox resize 256×256, chuẩn hóa ImageNet mean & std.
    + Forward pass qua ResNet-34, tính softmax 8 lớp.
    + Tích hợp `DiagnosticReasoningEngine.fuse_and_evaluate()` để tính toán Top-3, nhãn tiếng Việt, và kiểm tra điều kiện Abstain.
    + Chuẩn hóa payload đầu ra khớp hợp đồng `image-classification.js`.
- [x] 3. Chạy test `pytest tests/test_disease_classification_pipeline.py -k test_classifier_loading_and_prediction` và xác nhận PASS.

---

### Task 2: Đấu nối Pipeline vào `InferenceEngine` và API Router

**Files:**
- Modify: `backend/services/inference_engine.py`
- Modify: `backend/app/routers/inference.py`
- Test: `tests/test_disease_classification_pipeline.py`

**Steps:**
- [x] 1. Viết failing integration test kiểm tra route `POST /api/predict/{image_id}` trả về `ai_diagnosis` có đầy đủ thông tin phân loại bệnh học thay vì `None`.
- [x] 2. Trong `backend/services/inference_engine.py`:
  - Khởi tạo `DiseaseClassifierService` và gọi `classify_image_with_mask` trong `run_inference()`.
  - Gắn kết quả vào trường `ai_diagnosis` trong từ điển trả về của `predict()`.
- [x] 3. Trong `backend/app/routers/inference.py`:
  - Gán `response_extras["ai_diagnosis"] = inference_result.get("ai_diagnosis")`.
  - Thêm endpoint `POST /api/images/{image_id}/classify` nhận mask tuỳ chọn để cho phép bác sĩ yêu cầu phân loại lại sau khi chỉnh sửa mask trên Canvas.
- [x] 4. Chạy `pytest tests/test_disease_classification_pipeline.py` và kiểm tra toàn bộ integration tests đạt 100% PASS (10/10 PASS).

---

### Task 3: Phát triển CLI Tool Độc lập `predict_image_mask_disease.py`

**Files:**
- Create: `scripts/predict_image_mask_disease.py`
- Test: `tests/test_disease_classification_pipeline.py`

**Steps:**
- [x] 1. Viết script CLI `scripts/predict_image_mask_disease.py`:
  - Tham số: `--image` (bắt buộc), `--mask` (tuỳ chọn), `--output-json`, `--output-vis`.
  - Nếu không truyền `--mask`, tự động gọi mô hình phân đoạn U-Net để sinh mask tổn thương.
  - Đọc ảnh, trích xuất mask, đo đạc kích thước (caliper), chạy bộ phân loại bệnh học 8 lớp.
  - In ra bảng tổng kết chuẩn ANSI màu sắc với hỗ trợ UTF-8 Windows console.
  - Hỗ trợ `--output-vis`: xuất ảnh ghép 3 khung [Ảnh gốc | Mask & Caliper | Biểu đồ thanh xác suất Top-3].
- [x] 2. Chạy thử nghiệm CLI trên ảnh test và xác minh tạo báo cáo + trực quan hóa thành công.

---

### Task 4: Nâng cấp Giao diện Workstation & Bổ sung Nút "Áp dụng vào Báo cáo"

**Files:**
- Modify: `frontend/app/viewer.js`
- Modify: `frontend/app/image-classification.js`
- Test: `tests/clinical_roundtrip_e2e.js`, `tests/workstation_viewer_e2e.js`

**Steps:**
- [x] 1. Nâng cấp hàm `classificationText()` trong `frontend/app/image-classification.js` để hiển thị định dạng giàu thông tin, phân tách rõ ràng giữa Dự đoán bệnh học, Độ tin cậy (%) và Cảnh báo RUO.
- [x] 2. Trong `frontend/app/viewer.js`:
  - Thêm nút bấm `<button id="btnApplyAiDiagnosis" class="btn small outline" type="button">Áp dụng vào mô tả ca</button>`.
  - Sự kiện click: lấy nhãn tiếng Việt từ chẩn đoán AI tự động điền vào ô `#notes` và trường mô tả để bác sĩ không phải gõ thủ công.
- [x] 3. Kiểm tra cú pháp JavaScript với `node scripts/type_check.js` (56/56 module PASS).
- [x] 4. Chạy kiểm thử trình duyệt `node tests/clinical_roundtrip_e2e.js` và `node tests/workstation_viewer_e2e.js` xác nhận 0 page errors, PASS toàn diện.

---

### Task 5: Rà soát Tổng thể, Chạy Full Regression Suite & Chốt Báo cáo

**Files:**
- Test: `tests/test_disease_classification_pipeline.py` (10/10 PASS)
- Test: `tests/test_audit_remediation_regression.py` (14/14 PASS)
- Test: `tests/clinical_roundtrip_e2e.js` (PASS, 0 page errors)
- Test: `tests/workstation_viewer_e2e.js` (PASS, 4 viewports checked)
- Check: JavaScript syntax 56/56 module PASS

**Steps:**
- [x] 1. Chạy regression test suites xác nhận hệ thống ổn định và các tính năng mới tích hợp mượt mà.
- [x] 2. Kiểm tra `git status --short` để đảm bảo giữ nguyên vẹn dirty diff hiện hữu.
- [x] 3. Tổng hợp báo cáo nghiệm thu gửi người dùng.
