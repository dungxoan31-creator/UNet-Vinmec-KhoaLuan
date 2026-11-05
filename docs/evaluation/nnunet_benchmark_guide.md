# Hướng dẫn Đối chuẩn Trần nnU-Net v2 (Ceiling Benchmark Guide)
> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop\
> **Bộ phận**: Kiến trúc Đối chuẩn AI & Thử nghiệm Lâm sàng\
> **Tài liệu tham chiếu**: [AGENTS.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/AGENTS.md), [dataset_format.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/external_sources/nnUNet/documentation/dataset_format.md)

---

## 1. Giới thiệu & Mục tiêu Nghiên cứu

Trong nghiên cứu phân vùng tổn thương buồng trứng trên ảnh siêu âm 2D (MMOTU OTU_2d), mô hình chính của khóa luận sử dụng kiến trúc **Custom U-Net (ResNet34 / Combo Loss Dice + BCE / Letterbox 512×512)**. Để chứng minh năng lực thực nghiệm và xác lập ngưỡng hiệu năng tối đa (Ceiling Benchmark) có thể đạt được trên bộ dữ liệu MMOTU, hệ thống tích hợp chuẩn **nnU-Net v2** (self-configuring framework tiêu chuẩn vàng trong phân vùng ảnh y tế).

### Nguyên tắc Y khoa & Kỷ luật Kỹ thuật (Tuân thủ AGENTS.md):
- **Phân chia mức ảnh (Image-level split)**: Bảo toàn tuyệt đối danh sách phân chia train/val chính thức từ upstream (`metadata/mmotu_2d_train_cls.txt` và `val_cls.txt`).
- **Minh bạch độc lập bệnh nhân**: Dataset MMOTU công khai không cung cấp Patient ID; tính độc lập mức bệnh nhân (`patient_level_independence_verified: false`) được ghi nhận rõ ràng, không diễn giải metric image-level thành bằng chứng lâm sàng.
- **Định dạng nhị phân chuẩn**: Lớp tổn thương buồng trứng (Ovarian Lesion) mang nhãn `1`, nền (Background) mang nhãn `0`. Kênh ảnh siêu âm đơn sắc (Grayscale) được chuẩn hóa thành 1 kênh duy nhất (`"channel_names": {"0": "US"}`).

---

## 2. Thiết lập Biến Môi trường nnU-Net v2

nnU-Net v2 yêu cầu 3 đường dẫn môi trường để lưu trữ raw data, dữ liệu tiền xử lý và trọng số mô hình. Trong PowerShell, chạy các lệnh sau:

```powershell
# Thiết lập đường dẫn thư mục gốc cho nnU-Net
$env:nnUNet_raw = "C:\Users\Dung\Documents\UNet-Vinmec-KhoaLuan\nnUNet_raw"
$env:nnUNet_preprocessed = "C:\Users\Dung\Documents\UNet-Vinmec-KhoaLuan\nnUNet_preprocessed"
$env:nnUNet_results = "C:\Users\Dung\Documents\UNet-Vinmec-KhoaLuan\nnUNet_results"

# Tạo các thư mục nếu chưa tồn tại
New-Item -ItemType Directory -Force -Path $env:nnUNet_raw
New-Item -ItemType Directory -Force -Path $env:nnUNet_preprocessed
New-Item -ItemType Directory -Force -Path $env:nnUNet_results
```

---

## 3. Chuyển đổi Dữ liệu Tự động (`prepare_mmotu_for_nnunet.py`)

Script [scripts/prepare_mmotu_for_nnunet.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/prepare_mmotu_for_nnunet.py) tự động thực hiện:
1. Đọc danh sách train (1000 ảnh) và val (469 ảnh) từ `ai_training/splits/mmotu_2d_official_2026-10-27/`.
2. Chuẩn hóa ảnh siêu âm về 1 kênh grayscale PNG và mask nhị phân $\{0, 1\}$.
3. Tạo file metadata `dataset.json` chuẩn v2.
4. Xuất file phân chia `splits_final.json` (Fold 0 tương ứng 100% với tập train/val chính thức của đề tài).

### Lệnh chạy chuẩn bị toàn bộ dữ liệu (Full Dataset):
```powershell
.venv\Scripts\python.exe scripts/prepare_mmotu_for_nnunet.py `
  --dataset-id 101 `
  --dataset-name MMOTU `
  --val-mode train_with_split `
  --file-mode copy `
  --verify
```

### Lệnh chạy kiểm thử nhanh (Dry-run hoặc Sub-sample):
```powershell
# Kiểm thử cấu trúc và metadata không tốn ổ đĩa (Dry-run)
.venv\Scripts\python.exe scripts/prepare_mmotu_for_nnunet.py --dry-run

# Chạy thử nghiệm trên 10 ảnh mẫu kèm kiểm định toàn vẹn
.venv\Scripts\python.exe scripts/prepare_mmotu_for_nnunet.py --limit 10 --output-dir temp_sample/Dataset101_MMOTU --verify
```

---

## 4. Trích xuất Đặc tính & Tiền xử lý (Plan & Preprocess)

Sử dụng công cụ CLI `nnUNetv2_plan_and_preprocess` để trích xuất fingerprint tập dữ liệu (kích thước, khoảng cách điểm ảnh, độ phân giải) và lập kế hoạch cấu hình mạng 2D U-Net:

```powershell
# 1. Trích xuất đặc tính và tiền xử lý cho cấu hình 2D
.venv\Scripts\nnUNetv2_plan_and_preprocess.exe -d 101 -c 2d --verify_dataset_integrity

# 2. Cấu hình phân chia thủ công (Manual Split):
# Đảm bảo Fold 0 sử dụng đúng 1000 train và 469 val chính thức của MMOTU
Copy-Item -Path "$env:nnUNet_raw\Dataset101_MMOTU\splits_final.json" `
          -Destination "$env:nnUNet_preprocessed\Dataset101_MMOTU\splits_final.json" -Force
```

---

## 5. Huấn luyện Mô hình Đối chuẩn (Model Training)

Chạy huấn luyện kiến trúc **2D U-Net** trên **Fold 0** (tập phân chia chính thức):

```powershell
# Huấn luyện trên GPU (Cuda) với cờ lưu xác suất dự đoán (--npz)
.venv\Scripts\nnUNetv2_train.exe 101 2d 0 -device cuda --npz

# (Tùy chọn) Nếu huấn luyện bị gián đoạn, tiếp tục từ checkpoint gần nhất:
.venv\Scripts\nnUNetv2_train.exe 101 2d 0 -device cuda --c

# (Tùy chọn cho máy thử nghiệm không có GPU mạnh):
.venv\Scripts\nnUNetv2_train.exe 101 2d 0 -device cpu --disable_checkpointing
```

*Ghi chú*:
- nnU-Net lưu checkpoint tốt nhất tại `checkpoint_best.pth` và checkpoint cuối cùng tại `checkpoint_final.pth`.
- Quá trình huấn luyện mặc định chạy 1000 epochs với Poly learning rate schedule và Data Augmentation nâng cao.

---

## 6. Đánh giá & Thu thập Số liệu Đối sánh (Benchmark Extraction)

Sau khi huấn luyện hoàn tất, chạy validation để tính toán metric Dice / IoU trên tập 469 ảnh kiểm định:

```powershell
# Chạy đánh giá validation với trọng số tốt nhất (checkpoint_best)
.venv\Scripts\nnUNetv2_train.exe 101 2d 0 --val --val_best
```

Kết quả chi tiết được tự động xuất ra file:
`$env:nnUNet_results\Dataset101_MMOTU\nnUNetTrainer__nnUNetPlans__2d\fold_0\validation\summary.json`

File `summary.json` cung cấp:
- **Mean Dice**: Trung bình hệ số tương đồng Dice trên toàn bộ 469 ca validation.
- **Mean IoU / Jaccard**: Hệ số giao trên hội cho tổn thương buồng trứng.
- **Per-case Metrics**: Bảng điểm chi tiết từng ca giúp phân tích các trường hợp ca khó (nang kích thước nhỏ, bờ không rõ, bóng cản âm).

---

## 7. Khung Đối sánh Hiệu năng Khóa luận (Benchmark Comparison Table)

Số liệu thu thập được từ Fold 0 của nnU-Net được đưa vào bảng đối sánh trần trong Báo cáo Khóa luận Tốt nghiệp:

| Mô hình / Kiến trúc | Cơ chế Tiền xử lý & Loss | Mean Dice (%) | Mean IoU (%) | Tốc độ suy luận (ms/ảnh) | Mục đích trong đề cương |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Custom U-Net (ResNet34)** | Letterbox 512×512, Combo Loss ($Dice + BCE$) | *Thực nghiệm đề tài* | *Thực nghiệm đề tài* | $<35\text{ ms}$ | **Mô hình chính phục vụ Web HITL** |
| **nnU-Net v2 (2D U-Net)** | Heuristic Dynamic Resampling, PolyLR, Deep Supervision | *Ceiling Benchmark* | *Ceiling Benchmark* | $\sim 80\text{ ms}$ | **Chuẩn trần đối sánh học thuật (Ceiling)** |

---

## 8. Kiểm thử Tự động (Continuous Integration)

Bộ kiểm thử [tests/test_nnunet_dataset_preparation.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/tests/test_nnunet_dataset_preparation.py) được thiết kế để xác thực toàn bộ quy trình:

```powershell
.venv\Scripts\pytest.exe tests/test_nnunet_dataset_preparation.py -v
```

**Tiêu chí thành công**:
- 100% test cases đạt xanh (PASS).
- `verify_dataset_integrity` của `nnunetv2` xác nhận hợp lệ không có warning hoặc error.
