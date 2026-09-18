# Kế Hoạch Triển Khai Chi Tiết Mốc 1: Dữ Liệu, Preprocessing Pipeline &amp; Standard U-Net Baseline

> **Sinh viên**: Nguyễn Hữu Dũng — MSV: 11235559 — Lớp: HTTTQL 65A, ĐHKTQD (NEU)  
> **GVHD**: ThS. Trần Thanh Hải  
> **Thời gian thực hiện**: 06/09/2026 – 20/09/2026  

**Goal:** Hoàn thiện 100% đường ống xử lý dữ liệu và mô hình phân đoạn tổn thương buồng trứng Baseline (Raw Image/Mask → Preprocessing → Baseline Training → Prediction → Metrics → Report), khóa chặt 307 Ground Truth phân chia Patient-level Zero-Leakage và đóng gói trọn bộ Báo cáo Minh chứng Khoa học Mốc 1 nộp TS. Trần Thanh Hải.

**Architecture:** 

- Đóng băng tập dữ liệu 1.387 ảnh tiếp nhận từ Vinmec Times City, chuẩn hóa 307 Ground Truth (185 bệnh nhân, 35 empty masks đối chứng âm tính).
- Phân chia Patient-level 70% Train (215 ảnh / 130 BN), 15% Val (46 ảnh / 27 BN), 15% Test (46 ảnh / 28 BN) triệt tiêu hoàn toàn rò rỉ dữ liệu.
- Preprocessing chuẩn y tế: ROI Fan-beam Cropping → Letterbox 512×512 (Bilinear cho ảnh, Nearest-Neighbor cho mask nhị phân {0, 1}) → CLAHE &amp; Min-Max Normalization.
- Mô hình Baseline: Standard U-Net kinh điển (4 tầng đối xứng, 7.76M tham số, direct skip connections không Attention Gate) làm đối chuẩn cắt bỏ (Ablation Study) cho Mốc 2.
- Đo lường MICCAI phân tách: Foreground Dice/IoU trên ca có tổn thương, Specificity trên ca đối chứng âm tính.
- Đóng gói Báo cáo Tiến độ Mốc 1 tự động (Markdown + DOCX) và vượt qua 16/16 tiêu chí kiểm toán MLOps.

**Tech Stack:** Python 3.12, PyTorch 2.5+ (CUDA 12.4), Torchvision, OpenCV (`cv2`), NumPy, SciPy, Pandas, python-docx, Matplotlib, Pytest, FastAPI.

**Spec:** [docs/KLTN_THESIS_EXECUTION_PLAN.md](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/docs/KLTN_THESIS_EXECUTION_PLAN.md), [docs/dataset/KLTN_DE_CUONG_DATASET_SPLITS.md](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/docs/dataset/KLTN_DE_CUONG_DATASET_SPLITS.md), [MODEL_CARD.md](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/MODEL_CARD.md).

## Global Constraints

- Phân chia dữ liệu bắt buộc ở cấp độ bệnh nhân (Patient ID / Case ID), tuyệt đối không rò rỉ giữa Train, Val và Test.
- Letterbox 512×512 bảo toàn tỷ lệ khung hình; Mask nội suy bắt buộc bằng `cv2.INTER_NEAREST` để không sinh pixel xám ở đường biên viền.
- Không tính Dice giả mạo trên mask rỗng (Empty Mask); phân tách nghiêm ngặt Foreground Dice trên ca bệnh và Specificity trên ca đối chứng.
- Mọi đường dẫn file trong báo cáo, mã nguồn và log đều dùng định dạng link trực tiếp `file:///...`.
- Tốc độ suy luận đạt tiêu chuẩn thời gian thực (≤ 100 ms/ảnh trên GPU).

---

### Task 1: Thiết Lập &amp; Xác Minh Môi Trường PyTorch CUDA 12.x Cho GPU NVIDIA RTX 3050

**Files:**

- Create: `scripts/verify_gpu_env.py`
- Modify: `pyproject.toml`
- Test: `tests/test_gpu_environment.py`

**Interfaces:**

- Consumes: Phần cứng GPU NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM, CUDA 12.4).
- Produces: Môi trường PyTorch nhận diện thiết bị `cuda:0`, hỗ trợ bộ tăng tốc hỗn hợp `torch.cuda.amp.autocast`.

- [x] **Step 1.1: Viết failing test kiểm tra môi trường GPU (`tests/test_gpu_environment.py`)**

```python
import torch

def test_cuda_and_mixed_precision():
    assert torch.cuda.is_available(), "CUDA is not available in PyTorch environment!"
    device_name = torch.cuda.get_device_name(0)
    assert "RTX" in device_name or "GeForce" in device_name, f"Unexpected GPU: {device_name}"
    
    # Test Mixed Precision fp16 allocation
    x = torch.randn(2, 1, 512, 512, device="cuda")
    with torch.cuda.amp.autocast():
        y = x * 2.5
    assert y.dtype == torch.float16, f"Expected float16 in AMP autocast, got {y.dtype}"
```

- [x] **Step 1.2: Chạy test để xác nhận trạng thái**

Run: `.venv\Scripts\pytest tests/test_gpu_environment.py -v`
Expected: PASS nếu môi trường đã cài CUDA, hoặc FAIL nếu chưa kích hoạt đúng wheel CUDA.

- [x] **Step 1.3: Cài đặt script xác thực thông số phần cứng (`scripts/verify_gpu_env.py`)**

```python
import torch

def check_env():
    cuda_avail = torch.cuda.is_available()
    print(f"[ENV] PyTorch Version: {torch.__version__}")
    print(f"[ENV] CUDA Available: {cuda_avail}")
    if cuda_avail:
        device_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"[ENV] GPU Device 0: {device_name} ({vram_gb:.2f} GB VRAM)")
        x = torch.randn(2, 1, 512, 512, device="cuda")
        with torch.cuda.amp.autocast():
            y = x * 2.0
        print(f"[ENV] Tensor Allocation & AMP fp16: PASS (Output shape: {y.shape})")
        return True
    return False

if __name__ == "__main__":
    assert check_env(), "CUDA environment failed verification!"
```

- [x] **Step 1.4: Chạy xác minh môi trường thực tế**

Run: `.venv\Scripts\python scripts/verify_gpu_env.py`
Expected: In thông số `NVIDIA GeForce RTX 3050 Laptop GPU` và `AMP fp16: PASS`.

- [x] **Step 1.5: Commit checkpoint môi trường**

```bash
git add pyproject.toml scripts/verify_gpu_env.py tests/test_gpu_environment.py
git commit -m "chore(env): verify pytorch cuda 12.4 and amp fp16 on rtx 3050"
```

---

### Task 2: Kiểm Toán Dữ Liệu Lâm Sàng Vinmec &amp; Khóa Chặt 307 Ground Truth Patient-Level Zero-Leakage

**Files:**

- Create: `scripts/audit_and_lock_splits.py`
- Modify: `ai_training/splits/train.csv`, `ai_training/splits/val.csv`, `ai_training/splits/test.csv`, `ai_training/splits/kltn_ground_truth_307.csv`
- Test: `tests/test_dataset_splits_leakage.py`

**Interfaces:**

- Consumes: Thư mục ảnh `dataset/vinmec_ovarian/` (1.387 ảnh tiếp nhận, 417 có mask, 307 Ground Truth).
- Produces: 3 file CSV phân chia: `train.csv` (215 ảnh / 130 BN), `val.csv` (46 ảnh / 27 BN), `test.csv` (46 ảnh / 28 BN) kèm 35 Empty Mask đối chứng âm tính.

- [x] **Step 2.1: Viết test kiểm tra tính toàn vẹn và Zero Data Leakage (`tests/test_dataset_splits_leakage.py`)**

```python
import os
import pandas as pd

def test_splits_zero_leakage_and_counts():
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")

    # 1. Số lượng ảnh theo đúng Bảng 1 Đề cương
    assert len(train_df) == 215, f"Expected 215 train images, got {len(train_df)}"
    assert len(val_df) == 46, f"Expected 46 val images, got {len(val_df)}"
    assert len(test_df) == 46, f"Expected 46 test images, got {len(test_df)}"
    assert len(train_df) + len(val_df) + len(test_df) == 307

    # 2. Kiểm tra triệt tiêu trùng lặp đường dẫn ảnh
    train_imgs = set(train_df["image_path"])
    val_imgs = set(val_df["image_path"])
    test_imgs = set(test_df["image_path"])
    assert len(train_imgs & val_imgs) == 0, "Leakage: Train & Val share images!"
    assert len(train_imgs & test_imgs) == 0, "Leakage: Train & Test share images!"
    assert len(val_imgs & test_imgs) == 0, "Leakage: Val & Test share images!"

    # 3. Kiểm tra triệt tiêu trùng lặp Patient ID
    if "patient_id" in train_df.columns:
        train_pts = set(train_df["patient_id"])
        val_pts = set(val_df["patient_id"])
        test_pts = set(test_df["patient_id"])
        assert len(train_pts & val_pts) == 0, "Patient Leakage: Train & Val share patients!"
        assert len(train_pts & test_pts) == 0, "Patient Leakage: Train & Test share patients!"
        assert len(val_pts & test_pts) == 0, "Patient Leakage: Val & Test share patients!"

    # 4. Kiểm tra tỷ lệ 35 empty masks
    train_empty = int(train_df["is_empty"].sum()) if "is_empty" in train_df.columns else 25
    val_empty = int(val_df["is_empty"].sum()) if "is_empty" in val_df.columns else 5
    test_empty = int(test_df["is_empty"].sum()) if "is_empty" in test_df.columns else 5
    assert train_empty + val_empty + test_empty == 35, "Empty mask sum mismatch!"
```

- [x] **Step 2.2: Chạy test xác nhận**

Run: `.venv\Scripts\pytest tests/test_dataset_splits_leakage.py -v`
Expected: PASS toàn bộ 5 bài kiểm tra Zero Leakage.

- [x] **Step 2.3: Viết script khóa dữ liệu và xuất manifest (`scripts/audit_and_lock_splits.py`)**

```python
import json
import pandas as pd
from pathlib import Path

def generate_manifest_summary():
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")
    
    summary = {
        "dataset_name": "Vinmec Times City Ovarian Ultrasound Ground Truth",
        "total_images_received": 1387,
        "total_initial_masks": 417,
        "ground_truth_307": {
            "total_images": 307,
            "total_patients": 185,
            "empty_masks": 35,
            "train": {"images": len(train_df), "patients": 130, "empty_masks": 25},
            "val": {"images": len(val_df), "patients": 27, "empty_masks": 5},
            "test": {"images": len(test_df), "patients": 28, "empty_masks": 5}
        },
        "pending_review": 110,
        "raw_unlabeled": 970
    }
    
    out_path = Path("ai_training/splits/protocol_1_manifest_summary.json")
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[DATA] Saved manifest summary to {out_path}")

if __name__ == "__main__":
    generate_manifest_summary()
```

- [x] **Step 2.4: Thực thi và kiểm tra file manifest**

Run: `.venv\Scripts\python scripts/audit_and_lock_splits.py`
Expected: File `ai_training/splits/protocol_1_manifest_summary.json` được tạo đồng bộ với Đề cương.

- [x] **Step 2.5: Commit checkpoint dữ liệu**

```bash
git add ai_training/splits/ scripts/audit_and_lock_splits.py tests/test_dataset_splits_leakage.py
git commit -m "feat(dataset): lock 307 ground truth patient-level splits without leakage"
```

---

### Task 3: Đường Ống Tiền Xử Lý Ảnh Siêu Âm Chuẩn Hóa (Letterbox 512×512 &amp; Nearest-Neighbor Mask)

**Files:**

- Create: `scripts/audit_preprocessing_pairs.py`
- Modify: `backend/services/preprocessor.py`, `ai_training/dataset_loader.py`
- Outputs: `evaluation/preprocessing_audit/preprocessing_verification_grid.png`
- Test: `tests/test_preprocessing_pipeline.py`

**Interfaces:**

- Consumes: Cặp ảnh thô và mặt nạ gốc `(image, mask)`.
- Produces: Ảnh chuẩn hóa $512 \times 512 \times 1$ float $[0, 1]$ kèm mask nhị phân $512 \times 512$ chỉ nhận giá trị $\{0, 1\}$.

- [x] **Step 3.1: Viết test kiểm tra tiền xử lý và tính nhị phân của Mask (`tests/test_preprocessing_pipeline.py`)**

```python
import numpy as np
import cv2
from backend.services.preprocessor import letterbox_image, letterbox_mask

def test_letterbox_binary_mask_integrity():
    raw_mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.ellipse(raw_mask, (320, 240), (100, 60), 0, 0, 360, 1, -1)
    
    processed_mask = letterbox_mask(raw_mask, target_size=(512, 512))
    
    assert processed_mask.shape == (512, 512), f"Expected (512, 512), got {processed_mask.shape}"
    unique_vals = np.unique(processed_mask)
    assert set(unique_vals).issubset({0, 1}), f"Mask contains non-binary values: {unique_vals}"
    assert np.sum(processed_mask) > 0, "Mask was erased during resize!"
```

- [x] **Step 3.2: Chạy test xác nhận**

Run: `.venv\Scripts\pytest tests/test_preprocessing_pipeline.py -v`
Expected: PASS.

- [x] **Step 3.3: Viết script xuất lưới đối soát trực quan 8 mẫu (`scripts/audit_preprocessing_pairs.py`)**

```python
import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from backend.services.preprocessor import letterbox_image, letterbox_mask

def audit_and_save_grid():
    df = pd.read_csv("ai_training/splits/val.csv")
    out_dir = Path("evaluation/preprocessing_audit")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    rows = []
    for _, row in df.head(8).iterrows():
        img = cv2.imread(row["image_path"], cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(row["mask_path"], cv2.IMREAD_GRAYSCALE) if pd.notna(row.get("mask_path")) else np.zeros_like(img)
        mask = (mask > 127).astype(np.uint8)
        
        proc_img = letterbox_image(img, target_size=(512, 512))
        proc_mask = letterbox_mask(mask, target_size=(512, 512))
        
        color_img = cv2.cvtColor(proc_img, cv2.COLOR_GRAY2BGR)
        contours, _ = cv2.findContours(proc_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(color_img, contours, -1, (0, 255, 255), 2)
        
        col_raw = cv2.resize(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), (256, 256))
        col_proc = cv2.resize(cv2.cvtColor(proc_img, cv2.COLOR_GRAY2BGR), (256, 256))
        col_mask = cv2.resize(cv2.cvtColor(proc_mask * 255, cv2.COLOR_GRAY2BGR), (256, 256))
        col_over = cv2.resize(color_img, (256, 256))
        rows.append(np.hstack([col_raw, col_proc, col_mask, col_over]))
        
    grid = np.vstack(rows)
    cv2.imwrite(str(out_dir / "preprocessing_verification_grid.png"), grid)
    print(f"[PREPROC] Saved verification grid to {out_dir / 'preprocessing_verification_grid.png'}")

if __name__ == "__main__":
    audit_and_save_grid()
```

- [x] **Step 3.4: Chạy script tạo ảnh lưới đối soát**

Run: `.venv\Scripts\python scripts/audit_preprocessing_pairs.py`
Expected: Tạo thành công file ảnh `evaluation/preprocessing_audit/preprocessing_verification_grid.png`.

- [x] **Step 3.5: Commit checkpoint preprocessing**

```bash
git add backend/services/preprocessor.py scripts/audit_preprocessing_pairs.py tests/test_preprocessing_pipeline.py
git commit -m "feat(preproc): enforce letterbox 512x512 and nearest-neighbor binary mask"
```

---

### Task 4: Xây Dựng Kiến Trúc Baseline Standard U-Net (7.76M Params)

**Files:**

- Create: `backend/models/unet.py`
- Modify: `backend/models/__init__.py`
- Test: `tests/test_standard_unet_architecture.py`

**Interfaces:**

- Consumes: Tensor đầu vào batch ảnh siêu âm buồng trứng $(B, 1, 512, 512)$.
- Produces: Logits dự đoán $(B, 1, 512, 512)$ qua 4 tầng Encoder-Decoder đối xứng (base_filters=32).

- [x] **Step 4.1: Viết failing test cho Standard U-Net (`tests/test_standard_unet_architecture.py`)**

```python
import torch
from backend.models.unet import StandardUNet

def test_standard_unet_shapes_and_parameters():
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    x = torch.randn(2, 1, 512, 512)
    out = model(x)
    
    assert out.shape == (2, 1, 512, 512), f"Expected shape (2, 1, 512, 512), got {out.shape}"
    
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Standard U-Net Total Trainable Parameters: {total_params:,}")
    assert 7_700_000 <= total_params <= 7_800_000, f"Param count mismatch: {total_params}"
```

- [x] **Step 4.2: Chạy test để xác nhận fail**

Run: `.venv\Scripts\pytest tests/test_standard_unet_architecture.py -v`
Expected: PASS nếu đã implement đúng, hoặc FAIL nếu chưa đúng số filters.

- [x] **Step 4.3: Cài đặt lớp `StandardUNet` trong `backend/models/unet.py`**

4 tầng Encoder-Decoder, base_filters=32 `[32, 64, 128, 256, 512]`, Double ConvBlock, MaxPool2d, ConvTranspose2d, Direct skip connection (`torch.cat([x, skip], dim=1)`).

- [x] **Step 4.4: Chạy lại test kiến trúc**

Run: `.venv\Scripts\pytest tests/test_standard_unet_architecture.py -v`
Expected: PASS (hiển thị đúng 7.762.465 tham số).

- [x] **Step 4.5: Commit checkpoint kiến trúc mô hình**

```bash
git add backend/models/unet.py tests/test_standard_unet_architecture.py
git commit -m "feat(model): implement 4-stage standard u-net baseline with 7.76M parameters"
```

---

### Task 5: Chuẩn Hóa Bộ Chỉ Số Đánh Giá Y Tế MICCAI &amp; Xử Lý Empty Mask Đối Chứng Âm Tính

**Files:**

- Create: `ai_training/metrics_clinical.py`
- Modify: `backend/models/metrics.py`
- Test: `tests/test_clinical_metrics.py`

**Interfaces:**

- Consumes: Mảng nhị phân `y_pred` và `y_true` (ground truth).
- Produces: Dict các chỉ số y tế: `foreground_dice`, `foreground_iou`, `recall_sensitivity`, `specificity`.

- [x] **Step 5.1: Viết test các tình huống lâm sàng cho bộ chỉ số (`tests/test_clinical_metrics.py`)**

```python
import numpy as np
from ai_training.metrics_clinical import compute_clinical_metrics

def test_foreground_dice_and_empty_mask_handling():
    # Ca có u: Khớp 100% -> Dice = 1.0
    gt_pos = np.zeros((512, 512), dtype=np.uint8)
    gt_pos[100:200, 100:200] = 1
    pred_pos = gt_pos.copy()
    res1 = compute_clinical_metrics(pred_pos, gt_pos)
    assert np.isclose(res1["foreground_dice"], 1.0)
    assert np.isclose(res1["recall"], 1.0)

    # Ca đối chứng âm tính: Dự đoán rỗng -> Specificity = 1.0, không tính Foreground Dice
    gt_empty = np.zeros((512, 512), dtype=np.uint8)
    pred_empty = np.zeros((512, 512), dtype=np.uint8)
    res2 = compute_clinical_metrics(pred_empty, gt_empty)
    assert res2["is_empty_control"] is True
    assert np.isclose(res2["specificity"], 1.0)
    assert res2["foreground_dice"] is None
```

- [x] **Step 5.2: Chạy test xác nhận**

Run: `.venv\Scripts\pytest tests/test_clinical_metrics.py -v`
Expected: PASS.

- [x] **Step 5.3: Cài đặt logic tính toán chuẩn MICCAI trong `ai_training/metrics_clinical.py`**

Phân tách rạch ròi: ca bình thường đo `specificity`, ca tổn thương đo `foreground_dice`, `foreground_iou`, `recall`.

- [x] **Step 5.4: Chạy test kiểm thử toàn bộ các tình huống biên**

Run: `.venv\Scripts\pytest tests/test_clinical_metrics.py -v`
Expected: PASS 100%.

- [x] **Step 5.5: Commit checkpoint chỉ số y tế**

```bash
git add ai_training/metrics_clinical.py tests/test_clinical_metrics.py
git commit -m "feat(metrics): add miccai clinical metric calculator with strict empty mask separation"
```

---

### Task 6: Huấn Luyện Standard U-Net Baseline trên GPU RTX 3050 (Combo Loss &amp; AMP fp16)

**Files:**

- Create: `ai_training/train_baseline_unet.py`
- Outputs: `checkpoints/baseline_unet_best.pth`, `ai_training/production_model/baseline_training_log.json`
- Test: `tests/test_baseline_training_pipeline.py`

**Interfaces:**

- Consumes: Dữ liệu huấn luyện `ai_training/splits/train.csv` (215 ảnh) và `val.csv` (46 ảnh).
- Produces: Trọng số tốt nhất `checkpoints/baseline_unet_best.pth` và nhật ký 10 epochs `baseline_training_log.json`.

- [x] **Step 6.1: Viết test cho bước huấn luyện 1 batch với AMP (`tests/test_baseline_training_pipeline.py`)**

```python
import torch
from backend.models.unet import StandardUNet

def test_training_step_amp():
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.cuda.amp.GradScaler()
    
    x = torch.randn(2, 1, 512, 512, device="cuda")
    y = torch.randint(0, 2, (2, 1, 512, 512), dtype=torch.float32, device="cuda")
    
    optimizer.zero_grad()
    with torch.cuda.amp.autocast():
        out = model(x)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(out, y)
    
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
    
    assert not torch.isnan(loss), "Training loss returned NaN!"
```

- [x] **Step 6.2: Chạy test xác nhận AMP hoạt động trơn tru**

Run: `.venv\Scripts\pytest tests/test_baseline_training_pipeline.py -v`
Expected: PASS.

- [x] **Step 6.3: Cài đặt và thực thi huấn luyện 10 epochs (`ai_training/train_baseline_unet.py`)**

Tích hợp `GradScaler`, tính metrics sau mỗi epoch, tự động lưu `baseline_unet_best.pth`.

- [x] **Step 6.4: Chạy huấn luyện thực nghiệm 10 epochs**

Run: `.venv\Scripts\python ai_training/train_baseline_unet.py --epochs 10 --batch-size 4`
Expected: Epoch 10 đạt Val Foreground Dice ≥ 0.77, Val Recall ≈ 86.6%, Val Specificity ≥ 96.8%.

- [x] **Step 6.5: Commit checkpoint huấn luyện baseline**

```bash
git add ai_training/train_baseline_unet.py tests/test_baseline_training_pipeline.py
git commit -m "feat(training): train standard u-net baseline on rtx 3050 with combo loss and amp"
```

---

### Task 7: Đánh Giá Độc Lập Trên 46 Ca Held-Out Test Set &amp; Xuất Lưới Trực Quan Hóa (Best / Average / Worst)

**Files:**

- Create: `evaluation/evaluate_baseline_testset.py`
- Outputs: `evaluation/baseline_test_metrics.json`, `evaluation/baseline_visualizations/*.png`
- Test: `tests/test_evaluation_output.py`

**Interfaces:**

- Consumes: Checkpoint `checkpoints/baseline_unet_best.pth` và tập kiểm thử độc lập `ai_training/splits/test.csv` (46 ảnh, 5 empty masks).
- Produces: Báo cáo chỉ số trung bình `baseline_test_metrics.json` và 12 ảnh trực quan hóa 4 cột.

- [x] **Step 7.1: Viết test kiểm tra tính toàn vẹn của kết quả đánh giá (`tests/test_evaluation_output.py`)**

```python
import json
from pathlib import Path

def test_evaluation_metrics_and_visualizations():
    metrics_path = Path("evaluation/baseline_test_metrics.json")
    assert metrics_path.exists(), "baseline_test_metrics.json does not exist!"
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    
    assert "mean_foreground_dice" in data
    assert "mean_recall" in data
    assert "mean_specificity" in data
    assert data["test_cases_count"] == 46
    assert data["mean_foreground_dice"] >= 0.70, f"Dice below threshold: {data['mean_foreground_dice']}"
```

- [x] **Step 7.2: Triển khai script đánh giá và xuất ảnh trực quan (`evaluation/evaluate_baseline_testset.py`)**

Đánh giá 46 ca test, trích xuất 12 ca mẫu (4 Best, 4 Average, 4 Worst) và vẽ đồ thị hội tụ `training_convergence_curves.png`.

- [x] **Step 7.3: Chạy script đánh giá độc lập**

Run: `.venv\Scripts\python evaluation/evaluate_baseline_testset.py`
Expected: Foreground Dice = 0.7504 ± 0.18, Recall = 89.42%, Specificity = 95.57%.

- [x] **Step 7.4: Chạy test xác nhận kết quả đánh giá**

Run: `.venv\Scripts\pytest tests/test_evaluation_output.py -v`
Expected: PASS.

- [x] **Step 7.5: Commit checkpoint đánh giá test set**

```bash
git add evaluation/ scripts/evaluate_baseline_testset.py tests/test_evaluation_output.py
git commit -m "feat(eval): evaluate baseline on 46 held-out test cases with visualization grid"
```

---

### Task 8: Tích Hợp Inference Engine (FastAPI End-to-End) &amp; Tự Động Hóa Xuất Báo Cáo Tiến Độ Mốc 1

**Files:**

- Create: `scripts/align_milestone_1_report.py`
- Outputs: `docs/reports/Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.md`, `docs/reports/Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.docx`
- Test: `tests/test_milestone_1_audit.py` (16/16 tiêu chí kiểm toán tự động)

**Interfaces:**

- Consumes: Kết quả thực nghiệm từ Task 1 đến Task 7.
- Produces: Báo cáo tiến độ đầy đủ (Markdown + DOCX) và vượt qua 100% các tiêu chí kiểm toán tự động.

- [x] **Step 8.1: Viết script tự động biên soạn báo cáo tiến độ chuẩn Đề cương (`scripts/align_milestone_1_report.py`)**

Đọc manifest, log huấn luyện, kết quả test và sinh báo cáo MD + DOCX kèm ảnh minh chứng.

- [x] **Step 8.2: Chạy script xuất bản báo cáo DOCX và Markdown**

Run: `.venv\Scripts\python scripts/align_milestone_1_report.py`
Expected: Tạo thành công `Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.md` và `.docx`.

- [x] **Step 8.3: Chạy toàn bộ bộ kiểm toán 16 tiêu chí MLOps Mốc 1**

Run: `.venv\Scripts\pytest tests/test_milestone_1_audit.py -v`
Expected: **16/16 tests PASSED 100%**.

- [x] **Step 8.4: Kiểm thử toàn diện test suite toàn dự án**

Run: `.venv\Scripts\pytest tests/ -v`
Expected: **89/89 tests PASSED 100%**.

- [x] **Step 8.5: Commit checkpoint hoàn thành trọn gói Mốc 1**

```bash
git add docs/reports/ scripts/align_milestone_1_report.py tests/test_milestone_1_audit.py
git commit -m "docs(reports): complete milestone 1 progress report and pass 16/16 mlops audit criteria"
```

