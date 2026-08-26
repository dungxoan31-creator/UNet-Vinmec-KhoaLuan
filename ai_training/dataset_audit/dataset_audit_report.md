# BÁO CÁO TOÀN DIỆN AUDIT DỮ LIỆU THỰC TẾ (DATASET AUDIT REPORT)
**Dự án:** Hệ thống AI Hỗ trợ Phân đoạn Tổn thương Buồng trứng trên Ảnh Siêu âm  
**Thực hiện:** Nguyễn Hữu Dũng (MIS 65A - NEU) | Senior Medical AI & CV Engineer  
**Thư mục dữ liệu gốc:** `C:\Users\PeaceD_Dung\Documents\Khóa luận\dataset\dataset`  
**Ngày Audit:** 26/08/2026  

---

## 1. TỔNG QUAN DỮ LIỆU (DATASET OVERVIEW)
Dataset thực tế trong thư mục là tập chuẩn học thuật **OTU (Ovarian Tumor Ultrasound Dataset)** thuộc benchmark **MMOTU** được công bố cho bài toán phân đoạn tổn thương buồng trứng:
* **Tổng số cặp dữ liệu hợp lệ (Matched Image-Mask Pairs):** **1,372 cặp** (100% có Mask tương ứng).
* **Định dạng ảnh:** JPEG (`.JPG`) RGB / Grayscale.
* **Định dạng nhãn Mask:** PNG (`.PNG`) 8-bit Binary Grayscale (`0` và `255`).
* **Không có file hỏng (0 Corrupted Files)**, không có ảnh mất mask (0 Missing Masks).

---

## 2. CẤU TRÚC THƯ MỤC CHI TIẾT (FOLDER STRUCTURE)
```text
dataset/dataset/
├── OTU_2D/
│   ├── train/
│   │   ├── train_image/            # 820 ảnh siêu âm 2D huấn luyện (.JPG)
│   │   └── train_label/label/      # 820 mặt nạ Ground Truth tương ứng (.PNG)
│   └── test/
│       ├── image/                  # 382 ảnh siêu âm 2D kiểm thử độc lập (.JPG)
│       └── label/black_write/      # 382 mặt nạ Ground Truth tương ứng (.PNG)
└── OTU_CEUS/
    ├── image/                      # 170 ảnh siêu âm cản âm CEUS (.JPG)
    └── label/                      # 170 mặt nạ Ground Truth tương ứng (.PNG)
```

---

## 3. THỐNG KÊ CHI TIẾT THEO PHÂN LỚP DỮ LIỆU

| Phân lớp (Subset) | Số lượng ảnh | Số lượng Mask | Tỷ lệ ghép cặp | Độ phân giải phổ biến | Unique Mask Values | Trạng thái |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **OTU_2D Train** | 820 | 820 | 100% (820/820) | $958\times 534$, $959\times 532$ | `{0, 255}` (Binary) | Hoàn hảo |
| **OTU_2D Test** | 382 | 382 | 100% (382/382) | $959\times 535$, $958\times 534$ | `{0, 255}` (Binary) | Hoàn hảo |
| **OTU_CEUS** | 170 | 170 | 100% (170/170) | $553\times 550$, $553\times 553$ | `{0, 255}` (Binary) | Hoàn hảo |
| **TỔNG CỘNG** | **1,372** | **1,372** | **100% (1,372/1,372)** | — | **Binary Target** | **Sẵn sàng Train** |

---

## 4. QUY TẮC GHÉP CẶP (IMAGE-MASK PAIRING RULE)
* **OTU_2D Train:** `train_image/{ID}.JPG` $\Longleftrightarrow$ `train_label/label/{ID}.PNG` (VD: `1.JPG` $\leftrightarrow$ `1.PNG`).
* **OTU_2D Test:** `image/{ID}.JPG` $\Longleftrightarrow$ `label/black_write/{ID}.PNG` (VD: `3.JPG` $\leftrightarrow$ `3.PNG`).
* **OTU_CEUS:** `image/{ID}.JPG` $\Longleftrightarrow$ `label/{ID}.PNG` (VD: `1.JPG` $\leftrightarrow$ `1.PNG`).
* **Toàn bộ 1,372 file đã được xác minh đối khớp 1-1 bằng script tự động và xuất bảng CSV tại:**  
  `ai_training/dataset_audit/image_mask_pairing_audit.csv`.

---

## 5. PHÂN TÍCH ĐẶC TÍNH MẶT NẠ (MASK INSPECTION)
* **Loại phân đoạn:** **Binary Lesion Segmentation** (Phân đoạn nhị phân tổn thương u nang buồng trứng).
  * `0`: Nền mô lành buồng trứng / Khoang chậu / Khung đen viền ngoài siêu âm.
  * `255` (hoặc `1` khi chuẩn hóa tensor): Toàn bộ khối u nang buồng trứng (Ovarian Lesion / Cyst Body).
* **Kiểm tra Mask rỗng (Empty Masks):** $0$ ca trong tập nhãn dương tính này; các ca đều có tổn thương xác thực từ chuyên gia.

---

## 6. PHÒNG NGỪA RÒ RỈ DỮ LIỆU (DATA LEAKAGE PREVENTION & SPLIT STRATEGY)
* Tập dữ liệu chuẩn **OTU_2D** đã được nhà phát hành chia tách độc lập và nghiêm ngặt:
  * **Train Set:** 820 ảnh (Tập huấn luyện).
  * **Validation Set:** Trích xuất 120 ảnh từ Train Set (15% theo Stratified Seed cố định) để điều chỉnh siêu tham số và lưu Checkpoint tốt nhất.
  * **Hold-out Test Set:** **382 ảnh độc lập tuyệt đối** (Tập kiểm thử cuối cùng không bao giờ được tham gia vào quá trình backward gradient hay tune epoch).

---

## 7. ĐỀ XUẤT PIPELINE TIỀN XỬ LÝ & TĂNG CƯỜNG (PREPROCESSING & AUGMENTATION)
1. **Letterbox Resize với Aspect Ratio Preservation:**
   * Do ảnh có tỷ lệ khung hình trung bình $1.42$, việc resize thẳng $512\times 512$ sẽ làm méo u nang.
   * Sử dụng thuật toán **Letterboxing + Zero-padding** đưa về kích thước chuẩn $(512, 512)$.
   * **Cực kỳ quan trọng:** Đối với Mask, bắt buộc sử dụng nội suy `cv2.INTER_NEAREST` để tuyệt đối không sinh ra giá trị pixel mờ biên nhân tạo.
2. **Contrast Limited Adaptive Histogram Equalization (CLAHE):**
   * Áp dụng CLAHE ($clip\_limit=2.0, tile\_grid\_size=(8,8)$) để cân bằng phổ tương phản cho mô mềm âm đạo.
3. **Augmentation chuyên biệt cho Siêu âm:**
   * Horizontal Flip ($p=0.5$).
   * Small Rotation ($\pm 10^\circ$).
   * Random Contrast & Brightness ($\pm 10\%$).
   * Gaussian Speckle Noise Simulation ($p=0.2$).

---

## 8. LỰA CHỌN MÔ HÌNH HỌC SÂU (MODEL SELECTION & ROADMAP)
1. **Baseline Model:** Standard U-Net (ResNet-34 Encoder).
2. **Primary Production SOTA Model:** **Attention U-Net** (Dual Spatial & Channel Attention Gates tích hợp tại Skip Connections để triệt tiêu nhiễu đốm siêu âm).
3. **Hàm mất mát (Loss Function):** Combo Loss kết hợp:
   $$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{Dice}} + 0.3 \cdot \mathcal{L}_{\text{Focal}} + 0.2 \cdot \mathcal{L}_{\text{BCE}}$$
