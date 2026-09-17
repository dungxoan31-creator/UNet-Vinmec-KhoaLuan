# HƯỚNG DẪN TÁI LẬP QUY TRÌNH HUẤN LUYỆN AI (REPRODUCIBILITY GUIDE)

> **Khóa luận Tốt nghiệp**: *“Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”*  
> **Sinh viên**: Nguyễn Hữu Dũng — MSV: 11235559 — Lớp: HTTTQL 65A, ĐH Kinh tế Quốc dân  
> **Cán bộ hướng dẫn**: ThS. Trần Thanh Hải  
> **Bối cảnh & Dữ liệu lâm sàng**: Bệnh viện Đa khoa Quốc tế Vinmec Times City  
> **Bản chất phần mềm**: Bản mẫu nghiên cứu thực nghiệm (Academic Research Prototype)

---

## 1. THIẾT LẬP MÔI TRƯỜNG (ENVIRONMENT SETUP)
* **Python:** $\ge 3.10$ (Khuyến nghị 3.12).
* **Framework:** PyTorch $\ge 2.1.0$, Torchvision, OpenCV, Albumentations, ReportLab, FastAPI, Uvicorn.
* **Cài đặt thư viện phụ thuộc:**
  ```powershell
  pip install torch torchvision opencv-python numpy reportlab fastapi uvicorn pydantic scikit-learn pytest
  ```

---

## 2. VỊ TRÍ TẬP DỮ LIỆU THỰC TẾ (DATASET LOCATION)
Tập dữ liệu lâm sàng niêm phong tại:
`dataset/vinmec_ovarian/` (kèm `vinmec_dataset_manifest.json` ghi nhận 5 số liệu niêm phong: 1.387 ảnh tổng, 417 có mask, 307 Ground Truth từ 185 bệnh nhân, 110 pending, 970 unlabelled).
* `OTU_2D/train/`: 820 cặp ảnh và mask.
* `OTU_2D/test/`: 382 cặp ảnh và mask độc lập.
* `OTU_CEUS/`: 170 cặp ảnh và mask siêu âm cản âm.

---

## 3. CÁC BƯỚC THỰC THI (STEP-BY-STEP WORKFLOW)

### Bước 1: Audit & Kiểm tra Ghép cặp Dữ liệu
```powershell
python scripts/audit_real_dataset.py
```
* Báo cáo chi tiết được sinh tại: `ai_training/dataset_audit/dataset_audit_report.md`
* Bảng ghép cặp toàn bộ 1,372 file: `ai_training/dataset_audit/image_mask_pairing_audit.csv`

### Bước 2: Tạo Phân chia Tập dữ liệu Phân tầng Bệnh nhân (Patient-Level Splits)
```powershell
python scripts/create_official_splits.py
# Hoặc chia theo 307 Ground Truth:
python scripts/create_patient_level_splits.py
```
* Tập Train (700 ảnh): `ai_training/splits/train.csv`
* Tập Val (120 ảnh): `ai_training/splits/val.csv`
* Tập Test độc lập (382 ảnh): `ai_training/splits/test.csv`

### Bước 3: Huấn luyện Mô hình Baseline (Standard U-Net) & Attention U-Net
```powershell
# 1. Huấn luyện Baseline U-Net (Bắt buộc)
python scripts/train_unet_baseline.py
# Lưu checkpoint tại checkpoints/baseline_unet_best.pth

# 2. Huấn luyện Attention U-Net (So sánh)
python scripts/train_real_dataset.py
# Lưu checkpoint tại checkpoints/best_attention_unet.pth
```

### Bước 4: Chạy Suy luận Độc lập (Standalone Inference)
```powershell
python ai_training/inference.py --image "dataset/vinmec_ovarian/OTU_2D/test/image/3.JPG" --output "result.png"
```

### Bước 5: Khởi động Web Server Bản Mẫu Nghiên Cứu
```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Truy cập: `http://127.0.0.1:8000/` để tải ảnh, chạy phân đoạn AI, đo Calipers và xuất báo cáo PDF.
