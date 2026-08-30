# BÁO CÁO ĐÁNH GIÁ & KIỂM ĐỊNH MÔ HÌNH MEDICAL AI (INDEPENDENT TEST SET)
**Hệ thống Hỗ trợ Phân tích Siêu âm Phụ khoa (Ovarian Ultrasound CDSS)**

* **Thời điểm kiểm định:** `2026-08-28T15:01:15Z`
* **Model Version:** `v1.2.0-verified`
* **Kiến trúc mạng:** Attention U-Net (Dual Spatial & Channel Attention Gates, 7.85M parameters)
* **Weights Checksum (SHA-256):** `5a7692d61c7c3eeebbd11c9e86bc154461b5d9024deb3b4d7742033a2aa6ff6e`
* **Tập kiểm thử độc lập (Held-out Test):** 206 ca (Zero Patient Overlap)

---

## 1. BẢNG TỔNG HỢP HIỆU NĂNG SEGMENTATION ĐỘC LẬP

| Chỉ số Đánh giá (Metric) | Giá trị Trung bình (Mean) | Độ lệch chuẩn (Std) | Đơn vị / Tỷ lệ | Ý nghĩa Lâm sàng |
|---|:---:|:---:|:---:|---|
| **Dice Similarity Coefficient (DSC)** | **0.7122** | ± 0.2456 | **71.22%** | Mức độ trùng khớp thể tích vùng tổn thương AI vs Chuyên gia |
| **Intersection over Union (IoU / Jaccard)** | **0.6010** | ± 0.2574 | **60.10%** | Tỷ lệ diện tích giao trên diện tích hợp của mặt nạ |
| **Precision (Positive Predictive Value)** | **0.7396** | — | **73.96%** | Tỷ lệ điểm ảnh AI dự đoán dương tính thực sự là mô bệnh lý |
| **Recall (Sensitivity)** | **0.7953** | — | **79.53%** | Độ nhạy bắt tổn thương (giảm thiểu tối đa bỏ sót u buồng trứng) |
| **Specificity (True Negative Rate)** | **0.9661** | — | **96.61%** | Khả năng loại trừ chính xác mô lành và cấu trúc giải phẫu xung quanh |
| **95% Hausdorff Distance (HD95)** | **3.77** | — | **mm** | Khoảng cách sai lệch lớn nhất tại đường biên 95% (độ chính xác bờ viền) |
| **Thời gian suy luận trung bình (TTA Latency)** | **1305.2** | — | **ms / image** | Độ trễ suy luận thời gian thực với Test-Time Augmentation |

---

## 2. MA TRẬN NHẦM LẪN CẤP ĐỘ ĐIỂM ẢNH (PIXEL-LEVEL CONFUSION MATRIX)

* **True Positive (TP):** `1,381,427` pixels (Điểm ảnh vùng u được phát hiện chính xác)
* **False Positive (FP):** `405,680` pixels (Điểm ảnh nhận nhầm là u ngoài vùng tổn thương)
* **False Negative (FN):** `326,525` pixels (Điểm ảnh u bị bỏ sót)
* **True Negative (TN):** `11,386,784` pixels (Điểm ảnh nền và mô lành phân loại chính xác)

---

## 3. PHÂN TÍCH LỖI HỆ THỐNG (SYSTEMATIC ERROR ANALYSIS)

| Phân loại Lỗi (Error Category) | Số lượng Ca | Tỷ lệ (%) | Đặc điểm Lâm sàng & Kỹ thuật |
|---|:---:|:---:|---|
| **EXCELLENT MATCH (DSC ≥ 0.85)** | **80** | **38.8%** | Ranh giới khối u sắc nét, hồi âm điển hình, chất lượng ảnh cao |
| **GOOD MATCH (0.70 ≤ DSC < 0.85)** | **58** | **28.2%** | Sai lệch nhỏ ở vùng ngoại vi hoặc vách ngăn mỏng |
| **FALSE NEGATIVE (Under-segmentation)** | **38** | **18.4%** | Độ tương phản kém, ranh giới mờ, suy giảm chùm tia siêu âm ở lớp sâu |
| **FALSE POSITIVE (Over-segmentation)** | **28** | **13.6%** | Bao gồm nhầm cụm nang noãn nhỏ kế cận hoặc bóng cản âm lưng |
| **MODERATE DEVIATION** | **2** | **1.0%** | Khối u đa thùy có cấu trúc hình học dị dạng phức tạp |

---

## 4. BẢNG CHI TIẾT CÁC CA KHÓ & DỰ ĐOÁN CHÊNH LỆCH (WORST CASES)

| Case ID | Tên File | Dice | IoU | Precision | Recall | Loại Lỗi | Nguyên Nhân Khả Dĩ |
|---|---|:---:|:---:|:---:|:---:|---|---|
| OTU_2D_test_776 | `776.JPG` | 0.0000 | 0.0000 | 1.0000 | 0.0000 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_train_308 | `308.JPG` | 0.0000 | 0.0000 | 1.0000 | 0.0000 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_train_1043 | `1043.JPG` | 0.0004 | 0.0002 | 1.0000 | 0.0002 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_CEUS_154 | `154.JPG` | 0.0080 | 0.0040 | 0.6429 | 0.0040 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_CEUS_54 | `54.JPG` | 0.0227 | 0.0115 | 0.9737 | 0.0115 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_test_585 | `585.JPG` | 0.0367 | 0.0187 | 0.1511 | 0.0209 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_test_377 | `377.JPG` | 0.0466 | 0.0238 | 0.0371 | 0.0626 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_train_1429 | `1429.JPG` | 0.0631 | 0.0326 | 1.0000 | 0.0326 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_test_925 | `925.JPG` | 0.0705 | 0.0366 | 0.0553 | 0.0973 | FALSE_NEGATIVE_UNDERSEGMENT | Độ tương phản thấp, ranh giới mờ, suy giảm tín hiệu chùm sóng âm sâu |
| OTU_2D_train_599 | `599.JPG` | 0.1603 | 0.0871 | 0.0871 | 1.0000 | FALSE_POSITIVE_OVERSEGMENT | Bao gồm nhầm cụm nang noãn nhỏ kế cận hoặc bóng cản âm lưng |

---

## 5. THƯ MỤC MINH CHỨNG TRỰC QUAN (VISUAL VALIDATION DIRECTORY)
* 24 bộ ảnh 4 khung hình (Original, Ground Truth, AI Mask, Overlay) được lưu trữ độc lập tại:
  `evaluation/`
* Mỗi file ảnh thể hiện rõ đường viền thực tế Ground Truth (Màu Xanh Lá) và AI Prediction (Màu Vàng).
