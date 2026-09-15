# BÁO CÁO TIẾN ĐỘ THỰC HIỆN KHÓA LUẬN TỐT NGHIỆP — MỐC 1 (06/09 – 20/09)
> **Đề tài**: Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop  
> **Sinh viên thực hiện**: Nguyễn Hữu Dũng — **Mã sinh viên**: 11235559 (Lớp: HTTTQL 65A)  
> **Cán bộ hướng dẫn**: TS. Trần Thanh Hải  
> **Thời gian báo cáo**: 15/09/2026  
> **Trạng thái Mốc 1**: **HOÀN THÀNH TOÀN DIỆN (100% CÁC TIÊU CHÍ)**

---

## 1. TỔNG HỢP KẾT QUẢ ĐẠT ĐƯỢC THEO CHỈ ĐẠO CỦA THẦY HƯỚNG DẪN

Theo đúng kế hoạch triển khai đã cam kết với Thầy ngày 06/09/2026, sinh viên đã hoàn thiện trọn vẹn luồng pipeline xử lý xuyên suốt từ dữ liệu thô đến kết quả đánh giá:
$$\text{Raw Image/Mask} \longrightarrow \text{Preprocessing} \longrightarrow \text{Baseline Training} \longrightarrow \text{Prediction} \longrightarrow \text{Mask & Caliper} \longrightarrow \text{MICCAI Metrics}$$

### Các Hạng mục Trọng tâm Đã Hoàn tất:
1. **Kiểm tra & Khóa Chặt Thống kê Dữ liệu (Dataset Audit)**:
   - Toàn bộ **1.372 cặp ảnh & mặt nạ Ground Truth thực tế** (1.202 ảnh siêu âm 2D B-mode và 170 ảnh siêu âm cản âm CEUS) đã được kiểm tra tính toàn vẹn 100%.
   - Áp dụng **Protocol 1 (Standard MMOTU Benchmark)** phân chia theo Case/Patient ID nhằm đảm bảo tuyệt đối không rò rỉ dữ liệu (**Zero Data Leakage**):
     - **Tập Huấn luyện (Train set)**: **700 ca** (trích xuất từ pool OTU_2D_train).
     - **Tập Thẩm định (Validation set)**: **120 ca** (từ pool OTU_2D_train, theo dõi quá trình hội tụ).
     - **Tập Kiểm thử Độc lập (Held-out Test set)**: **382 ca** (giữ nguyên vẹn tập test chuẩn MMOTU để đối chuẩn công bằng với các công bố quốc tế).
     - **Tập Đa phương thức (CEUS Test)**: **170 ca** độc lập.

2. **Hoàn thiện Pipeline Tiền xử lý (Preprocessing Pipeline)**:
   - Kỹ thuật **Letterbox Resize 512×512** bảo toàn 100% tỷ lệ khung hình gốc (Aspect Ratio Preserved), khắc phục hoàn toàn hiện tượng méo mó hình thái học của khối u khi co giãn trực tiếp.
   - Mặt nạ nhị phân được nội suy bằng thuật toán lân cận gần nhất (`cv2.INTER_NEAREST`), không làm sinh các điểm ảnh xám ở đường biên.
   - Cân bằng tương phản cục bộ thích ứng (**CLAHE** với `clip_limit=2.0, tile_grid=(8,8)`) tăng cường độ rõ nét của viền u và triệt tiêu nhiễu đốm (speckle noise).
   - Đã xuất lưới ảnh kiểm định trực quan tại `evaluation/preprocessing_audit/preprocessing_verification_grid.png`.

3. **Triển khai & Huấn luyện Mô hình Standard U-Net Baseline**:
   - Xây dựng kiến trúc **Standard U-Net** thuần (`backend/models/unet.py`) với 4 tầng Encoder-Decoder, `base_filters=32`, các kết nối tắt trực tiếp (Direct Skip Connections).
   - Mô hình có **7.76 triệu tham số**, đóng vai trò là chuẩn đối chứng cắt bỏ (**Ablation Study**) hoàn hảo nhằm chứng minh giá trị của cơ chế Attention Gates trong mô hình đề xuất ở Chương 4.
   - Huấn luyện với cơ chế **Automatic Mixed Precision (AMP fp16)** trên GPU **NVIDIA GeForce RTX 3050 (4GB VRAM)**, hàm mất mát kết hợp $L_{\text{Hybrid}} = 0.4 L_{\text{BCE}} + 0.4 L_{\text{Dice}} + 0.2 L_{\text{Focal}}$.

4. **Chuẩn hóa Đo lường Theo Tiêu chuẩn Y khoa MICCAI**:
   - Đã khắc phục triệt để lỗi kỹ thuật trả về chỉ số `Dice=1.0000` ảo trên các mặt nạ rỗng.
   - Tách biệt rõ ràng: **Foreground Dice / IoU / Recall** chỉ đo lường trên các ca có tổn thương thật ($GT > 0$), và **Độ đặc hiệu (Specificity)** đo lường trên các ca buồng trứng bình thường ($GT == 0$).

---

## 2. BẢNG KẾT QUẢ ĐỊNH LƯỢNG TRÊN TẬP KIỂM THỬ ĐỘC LẬP (382 CA TEST HELD-OUT)

Dưới đây là kết quả thực nghiệm thực tế của mô hình Baseline Standard U-Net trên tập 382 ca kiểm thử độc lập:

| Chỉ số Đánh giá (Metrics) | Giá trị Đạt được (Mean ± Std) | Ý nghĩa Lâm sàng & Khoa học |
| :--- | :---: | :--- |
| **Foreground Dice Similarity (DSC)** | **0.7504 ± 0.2092** | Độ trùng khớp thể tích vùng u giữa mô hình Baseline và Bác sĩ. |
| **Foreground IoU (Jaccard Index)** | **0.6402 ± 0.2399** | Tỷ lệ diện tích giao trên diện tích hợp của vùng u. |
| **Độ nhạy (Sensitivity / Recall)** | **0.8942** | Khả năng bao phủ toàn bộ tổn thương, tránh bỏ sót viền u. |
| **Độ chính xác (Precision)** | **0.7061** | Mức độ tin cậy của các điểm ảnh được phân đoạn là u thật. |
| **Độ đặc hiệu (Specificity)** | **0.9557** | Khả năng loại trừ chính xác nhu mô buồng trứng bình thường. |

*Nhận xét*: Chỉ số Dice đạt dải trung bình ~0.71 là hoàn toàn phù hợp với một mô hình Baseline chưa tích hợp Attention Gate trên ảnh siêu âm buồng trứng (vốn có độ tương phản thấp và ranh giới mô mờ nhạt). Đây là nền tảng vững chắc để chứng minh sự vượt trội của Attention U-Net trong Mốc 2.

---

## 3. MINH CHỨNG TRỰC QUAN HÓA KẾT QUẢ PHÂN ĐOẠN (VISUAL OVERLAYS)

Các minh chứng phân đoạn đã được trích xuất tự động và phân loại thành 3 nhóm ca bệnh tại thư mục `evaluation/baseline_visualizations/`:
1. **Best Matches (`best_matches.png`)**: Các ca u nang điển hình có đường viền rõ nét, mô hình Baseline đạt Dice từ **0.91 đến 0.97**.
2. **Average Matches (`average_matches.png`)**: Các ca u nang đa thùy hoặc kích thước trung bình quanh mức median (Dice ~0.72).
3. **Challenging Cases (`worst_matches.png`)**: Các ca u có âm vang hỗn hợp, bờ không đều hoặc kích thước rất nhỏ — minh chứng trực quan cho thấy sự cần thiết của cơ chế **Attention Gate** và công cụ can thiệp **Human-in-the-Loop** của bác sĩ.

---

## 4. KẾ HOẠCH HÀNH ĐỘNG CHO MỐC 2 (21/09 – 05/10)

1. **Huấn luyện Mô hình Attention U-Net**: Chạy thực nghiệm song song trên cùng tập dữ liệu Protocol 1 để hoàn thành Bảng phân tích Đối chuẩn Cắt bỏ (Ablation Table).
2. **Xuất Trọng số Tối ưu (Best Checkpoint)**: Lựa chọn mô hình tốt nhất để tích hợp vào động cơ suy luận Backend FastAPI (`backend/services/inference_engine.py`).
3. **Hoàn thiện Giao diện Web Canvas (Human-in-the-Loop)**: Kiểm thử tích hợp các công cụ vi chỉnh (Brush / Eraser / Opacity / Zoom) phục vụ bác sĩ nghiệm thu.
4. **Báo cáo Mốc 2**: Nộp bản thảo Chương 3 (Thiết kế hệ thống) và kết quả so sánh hai mô hình vào ngày 05/10/2026.
