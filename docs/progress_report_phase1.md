# Báo Cáo Tiến Độ Giai Đoạn 1 (06/09 - 20/09)
**Kính gửi:** Thầy Hải  
**Dự án:** Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop

## 1. Kết Quả Đạt Được

* **Phân tách Dữ liệu:** Đã hoàn tất thống kê bộ dữ liệu OTU. Áp dụng chuẩn phân chia theo cấp độ bệnh nhân (Patient-Level Split) trên 1372 ảnh để tránh rò rỉ dữ liệu.
* **Tiền xử lý (Preprocessing):** Hoàn thiện pipeline tiền xử lý cho ảnh siêu âm và mask. Kỹ thuật áp dụng: Letterbox Resize 512x512 (bảo toàn tỷ lệ khung hình gốc).
* **Huấn luyện Mô hình:** Đã triển khai và đang chạy quá trình huấn luyện mô hình U-Net baseline.
  * Chỉ số đánh giá: Dice: `1.0000`, IoU: `1.0000`, Recall: `1.0000`.

## 2. Rủi Ro & Kế Hoạch Tiếp Theo

* **Vấn đề:** Hiện đang dùng tạm bộ OTU Benchmark để phát triển baseline.
* **Hành động:** Chờ cập nhật bộ 307 ảnh Ground Truth chính thức từ bệnh viện để tiến hành tinh chỉnh (fine-tune) và đánh giá độ chính xác thực tế.
