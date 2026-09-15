# Kế Hoạch Triển Khai Chi Tiết Mốc 1: Dữ Liệu, Preprocessing Pipeline & Mô Hình U-Net Baseline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện 100% pipeline phân đoạn ảnh siêu âm buồng trứng từ đầu đến cuối (Raw Image/Mask → Preprocessing → Baseline Training → Prediction → Metrics) và đóng gói trọn bộ Báo cáo Minh chứng Khoa học Mốc 1 (06/09 – 20/09) gửi TS. Trần Thanh Hải.

**Architecture:** Xây dựng mô hình `Standard U-Net` (4 tầng đối xứng, base_filters=32, direct skip connections) làm đối chuẩn cắt bỏ (Ablation Study) cho `Attention U-Net`. Khóa Protocol 1 (700 Train / 120 Val / 382 Held-out Test) từ 1.372 ảnh MMOTU, tiền xử lý Letterbox 512x512 + Nearest Mask + CLAHE, huấn luyện với Mixed Precision (AMP fp16) trên GPU NVIDIA RTX 3050, và chuẩn hóa đo lường MICCAI Foreground Dice/IoU/Recall + Specificity.

**Tech Stack:** Python 3.12, PyTorch (CUDA 12.x), Torchvision, OpenCV, NumPy, SciPy, Pandas, python-docx, Matplotlib.

**Spec:** [docs/KLTN_THESIS_EXECUTION_PLAN.md](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/docs/KLTN_THESIS_EXECUTION_PLAN.md) & [MODEL_CARD.md](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/MODEL_CARD.md).

## Global Constraints
- Phân chia tập dữ liệu nghiêm ngặt theo Patient ID / Case ID (Zero Data Leakage).
- Letterbox 512x512 bảo toàn tỷ lệ khung hình (Aspect Ratio Preservation). Mask nội suy bằng `cv2.INTER_NEAREST`.
- Không sử dụng các chỉ số giả mạo (Dice=1.0000 do mask rỗng); bắt buộc phân tách Foreground Dice trên ca có u và Specificity trên ca bình thường.
- Tuyệt đối bảo toàn mã nguồn hiện tại của `Attention U-Net` và `CDSS Reasoning Engine`.
- Mọi đường dẫn file trong báo cáo và log đều phải là clickable link (`file:///...`).

---

### Task 1: Thiết lập & Xác minh Môi trường PyTorch CUDA cho NVIDIA RTX 3050

**Files:**
- Create: `scripts/verify_gpu_env.py`
- Modify: `pyproject.toml`
- Test: `tests/test_gpu_environment.py`

**Interfaces:**
- Consumes: Phần cứng NVIDIA GeForce RTX 3050 Laptop GPU (Driver 592.00, CUDA 13.1/12.x compatible).
- Produces: Môi trường thực thi PyTorch kích hoạt CUDA (`device = torch.device('cuda')`), hỗ trợ AMP fp16 (`torch.cuda.amp.autocast`).

- [ ] **Step 1.1: Tạo virtual environment và cài đặt PyTorch với CUDA**
  Tạo môi trường `.venv` và cài đặt PyTorch CUDA wheels cùng các thư viện bổ trợ:
  ```powershell
  python -m venv .venv
  .venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
  .venv\Scripts\pip install opencv-python pandas scipy matplotlib tqdm python-docx pytest
  ```

- [ ] **Step 1.2: Viết script kiểm tra môi trường GPU (`scripts/verify_gpu_env.py`)**
  Tạo file kiểm tra thông số VRAM, CUDA runtime và khả năng tính toán tensor trên GPU:
  ```python
  import torch

  def check_env():
      cuda_avail = torch.cuda.is_available()
      print(f"[ENV] PyTorch Version: {torch.__version__}")
      print(f"[ENV] CUDA Available: {cuda_avail}")
      if cuda_avail:
          device_name = torch.cuda.get_device_name(0)
          vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
          print(f"[ENV] Device 0: {device_name} ({vram_gb:.2f} GB VRAM)")
          # Test tensor allocation and mixed precision
          x = torch.randn(2, 1, 512, 512, device="cuda")
          with torch.cuda.amp.autocast():
              y = x * 2.0
          print(f"[ENV] Test Tensor Allocation & AMP: PASS (Output shape: {y.shape})")
          return True
      return False

  if __name__ == "__main__":
      assert check_env(), "CUDA is not functional!"
  ```

- [ ] **Step 1.3: Chạy script xác minh môi trường GPU**
  Run: `.venv\Scripts\python scripts/verify_gpu_env.py`
  Expected: In ra `CUDA Available: True`, nhận diện `NVIDIA GeForce RTX 3050 Laptop GPU`, và `Test Tensor Allocation & AMP: PASS`.

- [ ] **Step 1.4: Viết unit test xác minh môi trường (`tests/test_gpu_environment.py`)**
  Run: `.venv\Scripts\pytest tests/test_gpu_environment.py -v`
  Expected: PASS

---

### Task 2: Xác Thực Thống Kê Dataset & Khóa Chặt Protocol 1 Zero-Leakage

**Files:**
- Create: `scripts/audit_and_lock_splits.py`
- Modify: `ai_training/splits/split_summary.json`
- Test: `tests/test_dataset_splits_leakage.py`

**Interfaces:**
- Consumes: Thư mục ảnh `dataset/dataset/OTU_2D` và `dataset/dataset/OTU_CEUS`.
- Produces: Các tệp CSV phân chia chính thức: `ai_training/splits/train.csv` (700), `ai_training/splits/val.csv` (120), `ai_training/splits/test.csv` (382), `ai_training/splits/ceus_test.csv` (170).

- [ ] **Step 2.1: Viết test kiểm tra tính toàn vẹn và Zero Leakage (`tests/test_dataset_splits_leakage.py`)**
  ```python
  import os
  import pandas as pd

  def test_splits_zero_leakage():
      train_df = pd.read_csv("ai_training/splits/train.csv")
      val_df = pd.read_csv("ai_training/splits/val.csv")
      test_df = pd.read_csv("ai_training/splits/test.csv")

      # 1. Check counts for Protocol 1
      assert len(train_df) == 700, f"Expected 700 train, got {len(train_df)}"
      assert len(val_df) == 120, f"Expected 120 val, got {len(val_df)}"
      assert len(test_df) == 382, f"Expected 382 test, got {len(test_df)}"

      # 2. Check no overlap in image_path
      train_imgs = set(train_df["image_path"])
      val_imgs = set(val_df["image_path"])
      test_imgs = set(test_df["image_path"])

      assert len(train_imgs.intersection(val_imgs)) == 0, "Data Leakage: Train & Val overlap!"
      assert len(train_imgs.intersection(test_imgs)) == 0, "Data Leakage: Train & Test overlap!"
      assert len(val_imgs.intersection(test_imgs)) == 0, "Data Leakage: Val & Test overlap!"

      # 3. Verify file existence on disk
      for p in train_df["image_path"].head(10):
          assert os.path.exists(p), f"File not found: {p}"
  ```

- [ ] **Step 2.2: Viết script tạo và khóa dữ liệu (`scripts/audit_and_lock_splits.py`)**
  Duyệt toàn bộ 1.372 ca trong `dataset/dataset/`, đối chiếu kích thước ảnh gốc, định dạng ảnh (.PNG/.JPG), ánh xạ cặp ảnh-mask và xuất các file split CSV chuẩn hóa.

- [ ] **Step 2.3: Chạy script và kiểm tra unit test**
  Run: `.venv\Scripts\python scripts/audit_and_lock_splits.py`
  Run: `.venv\Scripts\pytest tests/test_dataset_splits_leakage.py -v`
  Expected: PASS toàn bộ các bài test kiểm tra rò rỉ dữ liệu.

---

### Task 3: Hoàn Thiện & Trực Quan Hóa Kiểm Tra Preprocessing Pipeline

**Files:**
- Create: `scripts/audit_preprocessing_pairs.py`
- Modify: `backend/services/preprocessor.py`
- Outputs: `evaluation/preprocessing_audit/*.png`, `evaluation/preprocessing_audit/audit_report.json`
- Test: `tests/test_preprocessing_pipeline.py`

**Interfaces:**
- Consumes: Cặp `(image_raw, mask_raw)` từ `dataset/`.
- Produces: Tensor chuẩn hóa `(1, 512, 512)` float [0, 1] và Mask nhị phân `(1, 512, 512)` {0, 1} không bị nhòe viền.

- [ ] **Step 3.1: Viết test kiểm định Preprocessing (`tests/test_preprocessing_pipeline.py`)**
  Kiểm tra:
  1. Kích thước đầu ra đúng chuẩn 512x512.
  2. Mask sau resize chỉ chứa giá trị nhị phân {0, 1} (dùng `cv2.INTER_NEAREST`, không nội suy bilinear sinh viền xám).
  3. Padding letterbox đối xứng ở 2 phía.

- [ ] **Step 3.2: Viết script trực quan hóa cặp ảnh-mask (`scripts/audit_preprocessing_pairs.py`)**
  Trích xuất 16 cặp mẫu đại diện (8 ảnh 2D, 4 ảnh CEUS, 4 ảnh u nang nhỏ/lớn):
  - Cột 1: Ảnh thô gốc kèm viền Ground Truth.
  - Cột 2: Ảnh sau Letterbox 512x512 + CLAHE.
  - Cột 3: Mặt nạ Mask nhị phân sau Letterbox.
  - Cột 4: Lớp phủ Overlay màu ngọc bích (Cyan) minh chứng không lệch viền.
  Lưu ảnh lưới vào `evaluation/preprocessing_audit/grid_sample_verification.png`.

- [ ] **Step 3.3: Chạy script trực quan hóa và kiểm tra kết quả**
  Run: `.venv\Scripts\python scripts/audit_preprocessing_pairs.py`
  Expected: Tạo ảnh lưới kiểm tra độ chuẩn xác của contour, không biến dạng hình thái học.

---

### Task 4: Triển Khai Kiến Trúc Mô Hình Standard U-Net Baseline

**Files:**
- Create: `backend/models/unet.py`
- Modify: `backend/models/__init__.py`
- Test: `tests/test_standard_unet_architecture.py`

**Interfaces:**
- Consumes: Tensor đầu vào `(B, 1, 512, 512)`.
- Produces: Logits đầu ra `(B, 1, 512, 512)`.
- Architecture: 4 tầng Encoder-Decoder, Base Filters = 32 `[32, 64, 128, 256, 512]`, Double ConvBlock, MaxPool2d(2), ConvTranspose2d(2), Direct concatenation `torch.cat([x, skip], dim=1)` (không Attention Gate).

- [ ] **Step 4.1: Viết test kiến trúc mô hình Standard U-Net (`tests/test_standard_unet_architecture.py`)**
  ```python
  import torch
  from backend.models.unet import StandardUNet
  from backend.models.attention_unet import AttentionUNet

  def test_unet_shape_and_parameters():
      model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
      x = torch.randn(2, 1, 512, 512)
      out = model(x)
      assert out.shape == (2, 1, 512, 512), f"Expected (2, 1, 512, 512), got {out.shape}"

      # Verify parameter count is strictly less than AttentionUNet
      attn_model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32)
      unet_params = sum(p.numel() for p in model.parameters())
      attn_params = sum(p.numel() for p in attn_model.parameters())

      print(f"Standard U-Net Params: {unet_params:,} | Attention U-Net Params: {attn_params:,}")
      assert unet_params < attn_params, "Standard U-Net should have fewer parameters than Attention U-Net"
  ```

- [ ] **Step 4.2: Cài đặt lớp `StandardUNet` trong `backend/models/unet.py`**
  Tái sử dụng lớp `ConvBlock` chuẩn, cài đặt đường truyền trực tiếp giữa encoder và decoder.

- [ ] **Step 4.3: Chạy test kiến trúc**
  Run: `.venv\Scripts\pytest tests/test_standard_unet_architecture.py -v`
  Expected: PASS, hiển thị rõ số lượng tham số để đưa vào bảng đối chuẩn Ablation Study.

---

### Task 5: Sửa Lỗi Tính Chỉ Số & Chuẩn Hóa Module Đo Lường MICCAI

**Files:**
- Create: `ai_training/metrics_clinical.py`
- Modify: `backend/models/metrics.py`
- Test: `tests/test_clinical_metrics.py`

**Interfaces:**
- Consumes: Tensor `logits` (hoặc numpy mask) và `targets`.
- Produces: Dictionary chứa `foreground_dice`, `foreground_iou`, `sensitivity_recall`, `specificity`, `precision`, và flag cảnh báo mask rỗng.

- [ ] **Step 5.1: Viết test cho module đo lường chuẩn y tế (`tests/test_clinical_metrics.py`)**
  Kiểm tra 4 tình huống lâm sàng:
  1. Ca có u: Khớp hoàn toàn $\to$ Dice = 1.0.
  2. Ca có u: Khớp 50% $\to$ Dice $\approx 0.5$.
  3. Ca có u: Mô hình dự đoán rỗng $\to$ Dice = 0.0 (không được trả về 1.0 ảo!).
  4. Ca bình thường (không có u): Mô hình dự đoán rỗng $\to$ Specificity = 1.0, không tính vào Foreground Dice.

- [ ] **Step 5.2: Triển khai module `ai_training/metrics_clinical.py`**
  Cài đặt logic phân tách rõ ràng:
  - `compute_foreground_metrics`: Chỉ tính toán trên các ca Ground Truth có tổn thương ($GT > 0$).
  - `compute_specificity_on_normal`: Đo lường tỷ lệ phát hiện đúng ca âm tính sinh lý.

- [ ] **Step 5.3: Chạy test module chỉ số**
  Run: `.venv\Scripts\pytest tests/test_clinical_metrics.py -v`
  Expected: PASS 100% các tình huống biên.

---

### Task 6: Huấn Luyện Standard U-Net Baseline trên GPU RTX 3050 (AMP fp16)

**Files:**
- Create: `ai_training/train_baseline_unet.py`
- Outputs: `checkpoints/baseline_unet_best.pth`, `ai_training/production_model/baseline_training_log.json`
- Test: `tests/test_baseline_training_pipeline.py`

**Interfaces:**
- Consumes: `ai_training/splits/train.csv` (700) và `val.csv` (120).
- Produces: Checkpoint `checkpoints/baseline_unet_best.pth` và nhật ký từng epoch `baseline_training_log.json`.
- Hyperparameters: Batch size = 4 (hoặc 8), Epochs = 10, LR = $1\times 10^{-4}$, Optimizer = AdamW, Loss = Hybrid (0.4 BCE + 0.4 Dice + 0.2 Focal), AMP = True.

- [ ] **Step 6.1: Viết script huấn luyện `ai_training/train_baseline_unet.py`**
  Tích hợp `torch.cuda.amp.GradScaler()` để bật Mixed Precision fp16, giảm 50% VRAM sử dụng và tăng gấp 3 tốc độ trên nhân Tensor Cores của RTX 3050. Ghi nhận thời gian thực thi (duration_sec) và metrics chuẩn xác sau mỗi epoch.

- [ ] **Step 6.2: Chạy smoke-test huấn luyện 1 epoch trên subset nhỏ**
  Run: `.venv\Scripts\python ai_training/train_baseline_unet.py --smoke-test`
  Expected: Chạy trơn tru 1 epoch trong $< 30$ giây, xác nhận checkpoint lưu thành công.

- [ ] **Step 6.3: Thực hiện huấn luyện toàn diện 10 epochs**
  Run: `.venv\Scripts\python ai_training/train_baseline_unet.py --epochs 10 --batch-size 4`
  Expected: Hoàn tất 10 epochs trong ~15-20 phút, lưu `baseline_unet_best.pth` và xuất file log `baseline_training_log.json`.

---

### Task 7: Đánh Giá Độc Lập Trên Test Set Held-Out & Xuất Lưới Ảnh Trực Quan Hóa

**Files:**
- Create: `evaluation/evaluate_baseline_testset.py`
- Outputs: `evaluation/baseline_test_metrics.json`, `evaluation/baseline_visualizations/*.png`
- Test: `tests/test_evaluation_output.py`

**Interfaces:**
- Consumes: `checkpoints/baseline_unet_best.pth` và `ai_training/splits/test.csv` (382 ca test held-out).
- Produces: Bảng metrics trung bình $\pm$ độ lệch chuẩn, cùng 3 nhóm ảnh: Best (top 4 Dice cao nhất), Average (4 ca quanh median), Worst (4 ca Dice thấp nhất).

- [ ] **Step 7.1: Viết script đánh giá độc lập (`evaluation/evaluate_baseline_testset.py`)**
  Nạp mô hình baseline, chạy inference trên 382 ảnh test held-out, trích xuất:
  - Mean $\pm$ Std: Foreground Dice, IoU, Sensitivity/Recall, Specificity.
  - Sắp xếp thứ hạng các ca để chọn ra Best, Average, Worst matches.

- [ ] **Step 7.2: Chạy script đánh giá và trích xuất ảnh trực quan**
  Run: `.venv\Scripts\python evaluation/evaluate_baseline_testset.py`
  Expected:
  - Xuất bảng số liệu `evaluation/baseline_test_metrics.json`.
  - Sinh các ảnh trực quan hóa 4 cột: `Ảnh gốc | Ground Truth | Dự đoán Baseline | Overlay viền so sánh`.

- [ ] **Step 7.3: Kiểm tra tính hoàn thiện của ảnh trực quan**
  Xác minh 12 ảnh đại diện đã được lưu trữ đúng thư mục để chuẩn bị đưa vào báo cáo.

---

### Task 8: Kiểm Thử Thông Suốt Pipeline End-to-End (Smoke Test Tích Hợp)

**Files:**
- Create: `tests/test_end_to_end_pipeline.py`

**Interfaces:**
- Consumes: Đường dẫn ảnh siêu âm thô bất kỳ (`.png` hoặc `.jpg`).
- Produces: Mặt nạ phân đoạn, tọa độ Caliper $D_{\max}, D_{\text{orth}}$ và thời gian phản hồi (latency).

- [ ] **Step 8.1: Viết test luồng End-to-End (`tests/test_end_to_end_pipeline.py`)**
  Kiểm tra luồng xử lý hoàn chỉnh:
  `Raw Image -> Preprocessor -> Baseline Model Inference -> Caliper & Morphology Extraction -> Final Mask`.

- [ ] **Step 8.2: Chạy test End-to-End**
  Run: `.venv\Scripts\pytest tests/test_end_to_end_pipeline.py -v`
  Expected: PASS, độ trễ xử lý 1 ca $< 100\text{ ms}$ trên GPU.

---

### Task 9: Đóng Gói Trọn Gói Báo Cáo Minh Chứng Khoa Học Mốc 1 (Markdown + DOCX)

**Files:**
- Create: `scripts/generate_milestone_1_report.py`
- Outputs: `docs/reports/Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.md`, `docs/reports/Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.docx`
- Modify: `docs/progress_report_phase1.md`, `docs/KLTN_THESIS_EXECUTION_PLAN.md`

**Interfaces:**
- Consumes: Toàn bộ kết quả thực nghiệm từ Task 2, 3, 6, 7.
- Produces: File báo cáo học thuật chuẩn mực nộp TS. Trần Thanh Hải trước ngày 20/09.

- [ ] **Step 9.1: Viết script tự động biên soạn báo cáo (`scripts/generate_milestone_1_report.py`)**
  Tự động đọc `baseline_training_log.json`, `baseline_test_metrics.json`, chèn các bảng thống kê và nhúng các ảnh trực quan hóa vào tệp Markdown và DOCX:
  1. **Mục 1**: Bảng thống kê dữ liệu 1.372 ca & cấu trúc chia tập Zero-Leakage (Protocol 1).
  2. **Mục 2**: Minh chứng quy trình Preprocessing (Letterbox 512x512 + CLAHE).
  3. **Mục 3**: Kiến trúc mô hình Standard U-Net Baseline & Log huấn luyện thực tế trên RTX 3050.
  4. **Mục 4**: Bảng kết quả định lượng chuẩn MICCAI trên 382 ca Test Held-out.
  5. **Mục 5**: Lưới ảnh trực quan hóa phân đoạn (Best / Average / Worst cases).
  6. **Mục 6**: Kế hoạch hành động Mốc 2 (So sánh với Attention U-Net & Tích hợp Web HITL).

- [ ] **Step 9.2: Chạy script xuất bản báo cáo DOCX và Markdown**
  Run: `.venv\Scripts\python scripts/generate_milestone_1_report.py`
  Expected: Tạo thành công 2 file `Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.md` và `.docx`.

- [ ] **Step 9.3: Đồng bộ tiến độ vào tài liệu quản lý dự án**
  Cập nhật trạng thái Mốc 1 thành `DONE` trong `docs/KLTN_THESIS_EXECUTION_PLAN.md` và cập nhật bản tóm tắt tại `docs/progress_report_phase1.md`.
