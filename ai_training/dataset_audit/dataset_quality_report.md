# Báo Cáo Chất Lượng & Kiểm Định Dữ Liệu Thực Tế (Dataset Quality Report)

## 1. Bảng Tổng Hợp Kiểm Định Dữ Liệu (Dataset Quality Table)

| Phân Vùng Dữ Liệu | Số Ảnh | Dạng Siêu Âm | Nhãn Ranh Giới (Mask) | Nhãn Hợp Lệ | Nhãn Bị Lỗi/Hỏng | Tình Trạng Ground Truth |
|---|---|---|---|---|---|---|
| **OTU_2D (Train Set)** | 820 | B-Mode 2D qua ngả âm đạo/bụng | 820 (100%) | 820 | 0 | Đã xác thực mask ranh giới u nang |
| **OTU_2D (Test Set)** | 382 | B-Mode 2D qua ngả âm đạo/bụng | 382 (100%) | 382 | 0 | Đã xác thực mask ranh giới u nang |
| **OTU_CEUS (Contrast)** | 170 | Siêu âm tương phản vi mạch (CEUS) | 170 (100%) | 170 | 0 | Đã xác thực mask ranh giới u nang |
| **TỔNG CỘNG HỆ THỐNG** | **1.372** | **B-Mode 2D & CEUS** | **1.372 (100%)** | **1.372** | **0** | **100% Khớp ảnh - mask nhị phân** |

---

## 2. Phân Chia Phân Vùng Độc Lập Không Rò Rỉ (Patient/Study-Level Splitting)

| Tập Dữ Liệu | Số Lượng Ảnh | Tỷ Lệ (%) | B-Mode 2D | CEUS | Mục Đích Sử Dụng |
|---|---|---|---|---|---|
| **Train Set (v2)** | 960 | 70.0% | 847 | 113 | Huấn luyện mô hình Attention U-Net |
| **Validation Set (v2)** | 206 | 15.0% | 185 | 21 | Chọn lọc checkpoint tối ưu & Early Stopping |
| **Independent Test (v2)** | 206 | 15.0% | 170 | 36 | Đánh giá độc lập & Phân tích lỗi (Error Analysis) |

---

## 3. Đánh Giá Độ Tin Cậy & Ranh Giới Chẩn Đoán (Clinical Ground Truth Audit)

1. **Về Bài Toán Phân Đoạn (Lesion Segmentation):**
   * **ĐỦ DỮ LIỆU ĐÁNG TIN CẬY:** Toàn bộ 1.372 ca bệnh đều có ground truth mask chuẩn xác, phân định rõ ràng giữa khối u nang ($255$) và nhu mô lành ($0$).
   * Cho phép mô hình học sâu (Deep Learning) trích xuất chính xác tọa độ ranh giới, đường kính trục lớn $D_1$, đường kính trực giao $D_2$, diện tích mặt cắt và thể tích 3D elip.

2. **Về Bài Toán Phân Loại Mô Bệnh Học (Pathology Histological Biopsy):**
   * **CHƯA ĐỦ NHÃN SINH THIẾT GỐC ĐỂ HUẤN LUYỆN MODEL CLASSIFIER TRỰC TIẾP:** Dataset công khai OTU nguyên bản chỉ cung cấp mask phân đoạn, không đóng gói bảng nhãn sinh thiết giải phẫu bệnh (Biopsy pathology labels).
   * **NGUYÊN TẮC Y KHOA TUÂN THỦ:** Không được tự ý gán nhãn giả (pseudo-labels) hay huấn luyện mô hình phân loại mò.
   * **GIẢI PHÁP THỰC TẾ:** Áp dụng hệ thống **CDSS (Clinical Decision Support System)** trích xuất các dấu ấn sinh học âm học khách quan (Acoustic Biomarkers: Trống âm, Giảm âm, Kính mờ, Hỗn hợp, Nút Rokitansky, Chỉ số bóng cản) kết hợp thang điểm **ACR O-RADS v2022** và **IOTA Simple Rules** để đưa ra phân tầng nguy cơ và gợi ý chẩn đoán phân biệt đi kèm mức độ tin cậy và cảnh báo bất định.
