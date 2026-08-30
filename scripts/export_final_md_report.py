import os
import json
import pandas as pd

df = pd.read_csv("ai_training/evaluation_report_per_case.csv")
with open("ai_training/production_model/model_metadata.json", "r", encoding="utf-8") as f:
    meta = json.load(f)

tm = meta["test_metrics"]
err_counts = meta["error_distribution"]

md_content = f"""# BÁO CÁO ĐÁNH GIÁ & KIỂM ĐỊNH MÔ HÌNH MEDICAL AI (INDEPENDENT TEST SET)
**Hệ thống Hỗ trợ Phân tích Siêu âm Phụ khoa (Ovarian Ultrasound CDSS)**

* **Thời điểm kiểm định:** `{meta['exported_at']}`
* **Model Version:** `{meta['model_version']}`
* **Kiến trúc mạng:** Attention U-Net (Dual Spatial & Channel Attention Gates, 7.85M parameters)
* **Weights Checksum (SHA-256):** `{meta['model_sha256']}`
* **Tập kiểm thử độc lập (Held-out Test):** {len(df)} ca (Zero Patient Overlap)

---

## 1. BẢNG TỔNG HỢP HIỆU NĂNG SEGMENTATION ĐỘC LẬP

| Chỉ số Đánh giá (Metric) | Giá trị Trung bình (Mean) | Độ lệch chuẩn (Std) | Đơn vị / Tỷ lệ | Ý nghĩa Lâm sàng |
|---|:---:|:---:|:---:|---|
| **Dice Similarity Coefficient (DSC)** | **{tm['mean_dice']:.4f}** | ± {tm['std_dice']:.4f} | **{tm['mean_dice']*100:.2f}%** | Mức độ trùng khớp thể tích vùng tổn thương AI vs Chuyên gia |
| **Intersection over Union (IoU / Jaccard)** | **{tm['mean_iou']:.4f}** | ± {tm['std_iou']:.4f} | **{tm['mean_iou']*100:.2f}%** | Tỷ lệ diện tích giao trên diện tích hợp của mặt nạ |
| **Precision (Positive Predictive Value)** | **{tm['mean_precision']:.4f}** | — | **{tm['mean_precision']*100:.2f}%** | Tỷ lệ điểm ảnh AI dự đoán dương tính thực sự là mô bệnh lý |
| **Recall (Sensitivity)** | **{tm['mean_recall_sensitivity']:.4f}** | — | **{tm['mean_recall_sensitivity']*100:.2f}%** | Độ nhạy bắt tổn thương (giảm thiểu tối đa bỏ sót u buồng trứng) |
| **Specificity (True Negative Rate)** | **{tm['mean_specificity']:.4f}** | — | **{tm['mean_specificity']*100:.2f}%** | Khả năng loại trừ chính xác mô lành và cấu trúc giải phẫu xung quanh |
| **95% Hausdorff Distance (HD95)** | **{tm['mean_hd95_mm']:.2f}** | — | **mm** | Khoảng cách sai lệch lớn nhất tại đường biên 95% (độ chính xác bờ viền) |
| **Thời gian suy luận trung bình (TTA Latency)** | **{tm['inference_time_cpu_ms']:.1f}** | — | **ms / image** | Độ trễ suy luận thời gian thực với Test-Time Augmentation |

---

## 2. MA TRẬN NHẦM LẪN CẤP ĐỘ ĐIỂM ẢNH (PIXEL-LEVEL CONFUSION MATRIX)

* **True Positive (TP):** `{int(df['tp_px'].sum()):,}` pixels (Điểm ảnh vùng u được phát hiện chính xác)
* **False Positive (FP):** `{int(df['fp_px'].sum()):,}` pixels (Điểm ảnh nhận nhầm là u ngoài vùng tổn thương)
* **False Negative (FN):** `{int(df['fn_px'].sum()):,}` pixels (Điểm ảnh u bị bỏ sót)
* **True Negative (TN):** `{int(df['tn_px'].sum()):,}` pixels (Điểm ảnh nền và mô lành phân loại chính xác)

---

## 3. PHÂN TÍCH LỖI HỆ THỐNG (SYSTEMATIC ERROR ANALYSIS)

| Phân loại Lỗi (Error Category) | Số lượng Ca | Tỷ lệ (%) | Đặc điểm Lâm sàng & Kỹ thuật |
|---|:---:|:---:|---|
| **EXCELLENT MATCH (DSC ≥ 0.85)** | **{err_counts.get('EXCELLENT_MATCH', 0)}** | **{err_counts.get('EXCELLENT_MATCH', 0)/len(df)*100:.1f}%** | Ranh giới khối u sắc nét, hồi âm điển hình, chất lượng ảnh cao |
| **GOOD MATCH (0.70 ≤ DSC < 0.85)** | **{err_counts.get('GOOD_MATCH', 0)}** | **{err_counts.get('GOOD_MATCH', 0)/len(df)*100:.1f}%** | Sai lệch nhỏ ở vùng ngoại vi hoặc vách ngăn mỏng |
| **FALSE NEGATIVE (Under-segmentation)** | **{err_counts.get('FALSE_NEGATIVE_UNDERSEGMENT', 0)}** | **{err_counts.get('FALSE_NEGATIVE_UNDERSEGMENT', 0)/len(df)*100:.1f}%** | Độ tương phản kém, ranh giới mờ, suy giảm chùm tia siêu âm ở lớp sâu |
| **FALSE POSITIVE (Over-segmentation)** | **{err_counts.get('FALSE_POSITIVE_OVERSEGMENT', 0)}** | **{err_counts.get('FALSE_POSITIVE_OVERSEGMENT', 0)/len(df)*100:.1f}%** | Bao gồm nhầm cụm nang noãn nhỏ kế cận hoặc bóng cản âm lưng |
| **MODERATE DEVIATION** | **{err_counts.get('MODERATE_DEVIATION', 0)}** | **{err_counts.get('MODERATE_DEVIATION', 0)/len(df)*100:.1f}%** | Khối u đa thùy có cấu trúc hình học dị dạng phức tạp |

---

## 4. BẢNG CHI TIẾT CÁC CA KHÓ & DỰ ĐOÁN CHÊNH LỆCH (WORST CASES)

| Case ID | Tên File | Dice | IoU | Precision | Recall | Loại Lỗi | Nguyên Nhân Khả Dĩ |
|---|---|:---:|:---:|:---:|:---:|---|---|
"""

worst_10 = df.sort_values(by="dice").head(10)
for _, r in worst_10.iterrows():
    md_content += f"| {r['case_id']} | `{r['image_filename']}` | {r['dice']:.4f} | {r['iou']:.4f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['error_type']} | {r['possible_cause']} |\n"

md_content += """
---

## 5. THƯ MỤC MINH CHỨNG TRỰC QUAN (VISUAL VALIDATION DIRECTORY)
* 24 bộ ảnh 4 khung hình (Original, Ground Truth, AI Mask, Overlay) được lưu trữ độc lập tại:
  `evaluation/`
* Mỗi file ảnh thể hiện rõ đường viền thực tế Ground Truth (Màu Xanh Lá) và AI Prediction (Màu Vàng).
"""

with open("ai_training/evaluation_report.md", "w", encoding="utf-8") as f:
    f.write(md_content)
print("ai_training/evaluation_report.md generated successfully.")
