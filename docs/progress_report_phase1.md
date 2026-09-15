# Báo Cáo Tiến Độ Giai Đoạn 1 (06/09 - 20/09)
**Kính gửi:** Thầy Hải  
**Dự án:** Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop

## 1. Kết Quả Đạt Được

* **Phân tách Dữ liệu:** Đã hoàn tất kiểm định 1.372 cặp ảnh MMOTU. Khóa Protocol 1 (Standard Benchmark: 700 Train / 120 Val / 382 Held-out Test + 170 CEUS Test) với phân chia nghiêm ngặt theo Case/Patient ID (Zero Data Leakage đã được kiểm chứng 100%).
* **Tiền xử lý (Preprocessing):** Hoàn thiện pipeline tiền xử lý ảnh và mask: Letterbox Resize 512×512 bảo toàn tỷ lệ khung hình, nội suy lân cận gần nhất (`cv2.INTER_NEAREST`) cho mask chống lem viền, tăng tương phản thích ứng CLAHE. Đã xuất lưới ảnh kiểm tra đối chuẩn.
* **Huấn luyện Mô hình Baseline:** Triển khai kiến trúc Standard U-Net thuần (7.76M tham số) đối chuẩn cắt bỏ (Ablation Study) cho Attention U-Net. Đã hoàn tất huấn luyện 10 epochs với Mixed Precision (AMP fp16) trên card đồ họa NVIDIA GeForce RTX 3050 (4GB VRAM).
* **Kết quả Thực nghiệm Thực tế (trên 382 ca Held-out Test độc lập):**
  * **Foreground Dice (Mean ± Std):** `0.7504 ± 0.2092` (đạt 0.91 – 0.97 trên các ca u điển hình)
  * **Foreground IoU (Mean ± Std):** `0.6402 ± 0.2399`
  * **Độ nhạy (Sensitivity / Recall):** `0.8942` (89.42% — độ bao phủ tổn thương cao)
  * **Độ đặc hiệu (Specificity):** `0.9557` (95.57% — loại trừ mô lành chính xác)
  * Đã sửa triệt để lỗi hiển thị `Dice: 1.0000` ảo trên ca rỗng từ log cũ.
* **Minh chứng Đính kèm:**
  * Báo cáo tiến độ hoàn chỉnh: `docs/reports/Bao_Cao_Tien_Do_Moc_1_NguyenHuuDung.docx` và `.md`
  * Lưới ảnh phân đoạn trực quan (Best / Average / Worst): `evaluation/baseline_visualizations/`

## 2. Kế Hoạch Giai Đoạn 2 (21/09 – 05/10)

* **Huấn luyện Mô hình Attention U-Net:** Chạy thực nghiệm trên cùng tập Protocol 1 để hoàn thành bảng phân tích đối chuẩn (Ablation Analysis).
* **Tích hợp Web Human-in-the-Loop:** Hoàn thiện giao diện Canvas vi chỉnh (Brush / Eraser) và kết nối API suy luận Backend FastAPI.
* **Tiếp nhận Dữ liệu Bệnh viện:** Sẵn sàng nạp bộ 307 ảnh Ground Truth chính thức khi bệnh viện bàn giao để tiến hành fine-tuning bổ sung.
