# BÁO CÁO TOÀN DIỆN AUDIT DỮ LIỆU & KIỂM ĐỊNH ANNOTATION (OTU BENCHMARK)

## 1. TỔNG QUAN DỮ LIỆU THỰC TẾ

* **Tập dữ liệu:** Ovarian Tumor Ultrasound (OTU) Benchmark Dataset.
* **Tổng số cặp ảnh & mask quét được:** **1,372 cặp** (100% đối chiếu chính xác file-to-file).
* **Tổng số ca có Annotation Hợp Lệ:** **1,372 ca** (100.00%).
* **Số ca Mask Rỗng (Không có tổn thương / Control):** **0 ca**.
* **Số ca File Hỏng / Lỗi Giải Mã:** **0 ca**.
* **Số ca Trùng Lặp Ảnh (Duplicate Images):** **0 ca**.
* **Số ca Annotation Bất Thường / Invalid:** **0 ca**.

---

## 2. THỐNG KÊ CHI TIẾT THEO TỪNG TẬP CON (SUBSET BREAKDOWN)

| Tập Dữ Liệu | Số Ảnh | Số Mask | Cặp Khớp | Hợp Lệ | Rỗng (Control) | Kích Thước Phổ Biến | Diện Tích U TB (px) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **OTU_2D (Train)** | 820 | 820 | 820 | **820** | 0 | 958x534 (15 imgs) | 67,966.8 |
| **OTU_2D (Test)** | 382 | 382 | 382 | **382** | 0 | 959x535 (7 imgs) | 69,709.3 |
| **OTU_CEUS** | 170 | 170 | 170 | **170** | 0 | 553x550 (3 imgs) | 55,335.4 |
| **TỔNG HỢP** | **1372** | **1372** | **1372** | **1372** | **0** | — | — |

---

## 3. KẾT QUẢ KIỂM TRA 12 TIÊU CHÍ ANNOTATION VALIDATION

1. **Khớp Kích Thước (Width x Height):** 100% ảnh và mask có cùng độ phân giải gốc pixel-to-pixel (Không bị lệch khung hình).
2. **Hệ Tọa Độ (Coordinate System):** Đồng nhất hệ tọa độ ảnh gốc $X, Y \ge 0$.
3. **Bounding Region:** Toàn bộ vùng tổn thương nằm hoàn toàn trong khung hình siêu âm ($0 \le X \le W, 0 \le Y \le H$).
4. **Kiểm tra Lệch Trục / Đảo Ngược:** Không phát hiện mask bị đảo âm bản (0 là nền đen, 255/1 là tổn thương).
5. **Crop / Resize:** Toàn bộ quá trình chuẩn bị dữ liệu sử dụng Letterbox với tỷ lệ khung hình thực, nội suy `INTER_NEAREST` cho Mask và `INTER_LINEAR` cho Image.
6. **Vùng Ngoài ROI:** Không phát hiện nhiễu biên bất thường ngoài vùng quét sóng âm.
7. **Định Dạng Mask:** 100% mask nhị phân (Binary Mask) hợp lệ.

---

## 4. DANH MỤC TRỰC QUAN HÓA (VISUAL AUDIT PREVIEWS)
* Đã xuất **30 panels trực quan hóa** tại: `ai_training/dataset_preview/`.
* Bảng CSV toàn bộ 1,372 bản ghi: `ai_training/dataset_audit/dataset_audit_full_1372.csv`.
