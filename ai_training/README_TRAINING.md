# HƯỚNG DẪN TÁI LẬP QUY TRÌNH HUẤN LUYỆN AI (REPRODUCIBILITY GUIDE)

Hệ thống AI Hỗ trợ Phân đoạn Tổn thương Buồng trứng trên Ảnh Siêu âm 2D (OTU Benchmark Dataset).

---

## 1. THIẾT LẬP MÔI TRƯỜNG (ENVIRONMENT SETUP)
* **Python:** $\ge 3.10$ (Khuyến nghị 3.12).
* **Framework:** PyTorch $\ge 2.1.0$, Torchvision, OpenCV, Albumentations, ReportLab, FastAPI, Uvicorn.
* **Cài đặt thư viện phụ thuộc:**
  ```powershell
  pip install torch torchvision opencv-python numpy reportlab fastapi uvicorn pydantic scikit-learn
  ```

---

## 2. VỊ TRÍ TẬP DỮ LIỆU THỰC TẾ (DATASET LOCATION)
Tập dữ liệu chuẩn OTU nằm tại:
`dataset/dataset/`
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
* 24 ảnh trực quan hóa mẫu: `ai_training/dataset_preview/`

### Bước 2: Tạo Phân chia Tập dữ liệu (Splits)
```powershell
python scripts/create_official_splits.py
```
* Tập Train (700 ảnh): `ai_training/splits/train.csv`
* Tập Val (120 ảnh): `ai_training/splits/val.csv`
* Tập Test độc lập (382 ảnh): `ai_training/splits/test.csv`

### Bước 3: Huấn luyện & Đánh giá Benchmark Mô hình SOTA
```powershell
python scripts/train_real_dataset.py
```
* Huấn luyện mô hình **Attention U-Net** với Combo Loss.
* Tự động lưu checkpoint tốt nhất tại: `ai_training/production_model/model.pth`.
* Tự động đánh giá trên **382 ca kiểm thử Test set** (Dice, IoU, HD95, Latency).
* Tự động xuất 18 ảnh so sánh trực quan (Best / Average / Worst) tại: `ai_training/evaluation_samples/`.

### Bước 4: Chạy Suy luận Độc lập (Standalone Inference)
```powershell
python ai_training/inference.py --image "dataset/dataset/OTU_2D/test/image/3.JPG" --output "result.png"
```

### Bước 5: Khởi động Web Server & Trải nghiệm
```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Truy cập: `http://127.0.0.1:8000/` để tải ảnh, chạy phân đoạn AI, đo Calipers và xuất báo cáo PDF.
