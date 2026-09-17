# AI MODEL CARD: OVARIAN ULTRASOUND LESION SEGMENTATION
**Project:** Hệ thống Hỗ trợ Phân đoạn Tổn thương Siêu âm Buồng trứng theo Mô hình Human-in-the-Loop  
**Nature:** Bản mẫu nghiên cứu thực nghiệm (Academic Research Prototype - Not an official hospital deployment)  
**Authors:** Nguyễn Hữu Dũng (MIS 65A - Đại học Kinh tế Quốc dân, MSV: 11235559)  
**Supervisor:** ThS. Trần Thanh Hải  
**Clinical Research Context:** Bệnh viện Đa khoa Quốc tế Vinmec Times City  

---

## 1. MÔ TẢ TỔNG QUAN HỆ THỐNG MÔ HÌNH (MODEL OVERVIEW)
* **Mô hình Cơ sở (Baseline Model):** **Standard U-Net** (Ronneberger et al., 2015) – Trọng số chính thức lưu trữ tại `checkpoints/baseline_unet_best.pth`.
* **Mô hình So sánh Thực nghiệm (Comparative Variant):** **Attention U-Net** (Oktay et al., 2018) – Trọng số lưu trữ tại `checkpoints/best_attention_unet.pth`.
* **Loại hình Dữ liệu Đầu vào:** Ảnh siêu âm 2D B-Mode đầu dò âm đạo (TVUS) và siêu âm cản âm vi mạch (CEUS).
* **Nhiệm vụ Lâm sàng Cốt lõi:** Hỗ trợ phân đoạn đường viền tổn thương buồng trứng (Semantic Lesion Segmentation) và trích xuất thước đo khách quan ($D_{\max}, D_{\text{orth}}$, Diện tích, Chu vi) phục vụ bác sĩ đối soát.
* **Định dạng Đầu vào (Standardized Input):** Tensor kích thước $1 \times 512 \times 512$ đơn kênh (Grayscale), chuẩn hóa Letterbox Resize bảo toàn tỷ lệ khung hình thật (Aspect Ratio).
* **Định dạng Đầu ra (Output):** Mặt nạ nhị phân tổn thương $1 \times 512 \times 512$ (Mã hóa nén Run-Length Encoding - RLE) kèm tọa độ giao điểm thước đo Caliper.

---

## 2. BỘ DỮ LIỆU NGHIÊN CỨU LÂM SÀNG (VINMEC DATASET SPECIFICATION)
* **Cơ sở thu thập:** Bệnh viện ĐKQT Vinmec Times City (Khoa Chẩn đoán hình ảnh).
* **Quy mô dữ liệu đề cương được niêm phong:**
  * **Tổng số ảnh tiếp nhận:** **1.387 ảnh** siêu âm buồng trứng.
  * **Ảnh có mặt nạ sơ bộ:** **417 ảnh** (30.1%).
  * **Tập Ground Truth xác thực chuyên môn:** **307 ảnh** (được bác sĩ chuyên khoa siêu âm thẩm định và dán nhãn viền chuẩn xác).
  * **Số lượng bệnh nhân trong Ground Truth:** **185 bệnh nhân** (100% ẩn danh Anonymized PID).
  * **Mẫu buồng trứng bình thường (Empty Mask):** **35 ảnh** đại diện cho cấu trúc sinh lý bình thường không có khối u.
  * **Mặt nạ đang chờ rà soát (Pending Review):** **110 ảnh** (lưu trữ tách biệt, không đưa vào Ground Truth).
  * **Ảnh thô chưa gán nhãn:** **970 ảnh** (lưu trữ phục vụ mở rộng nghiên cứu bán giám sát).
* **Giao thức phân chia dữ liệu (Splitting Protocol):**
  * **Patient-Level Split:** Phân chia triệt để theo mã định danh bệnh nhân (Patient ID) thành các tập Train (700 ảnh), Val (120 ảnh), Test độc lập (382 ảnh) và CEUS Test (170 ảnh).
  * **Zero Data Leakage:** Tuyệt đối không để ảnh của cùng một bệnh nhân xuất hiện đồng thời ở cả tập Train và tập Test.

---

## 3. HÀM MẤT MÁT & QUY TRÌNH HUẤN LUYỆN (LOSS & OPTIMIZATION)
* **Hàm mất mát kết hợp (Combo Loss):**
  $$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{Dice}} + 0.3 \cdot \mathcal{L}_{\text{Focal}} + 0.2 \cdot \mathcal{L}_{\text{BCE}}$$
* **Bộ tối ưu hóa (Optimizer):** AdamW ($\text{LR} = 1\times 10^{-4}$, Weight Decay $= 1\times 10^{-4}$).
* **Điều phối tốc độ học:** CosineAnnealingLR ($T_{\max} = 10, \eta_{\min} = 1\times 10^{-6}$).
* **Tiền xử lý:** Letterbox Resize $512\times 512$, cân bằng độ tương phản CLAHE, lọc nhiễu Speckle y tế.

---

## 4. KẾT QUẢ ĐỐI CHUẨN THỰC NGHIỆM TRÊN TẬP TEST ĐỘC LẬP
* **Standard U-Net (Baseline):**
  * Mean Dice Similarity Coefficient (DSC): $\mathbf{0.7214 \pm 0.2612}$.
  * Mean Intersection over Union (IoU): $\mathbf{0.6189 \pm 0.2745}$.
  * Mean Recall / Độ nhạy biên: $\mathbf{0.7850}$.
* **Attention U-Net (Comparative Architecture):**
  * Mean Dice: $0.7404 \pm 0.2508$ (Cải thiện viền tổn thương nhờ cơ chế Attention Gate lọc nhiễu nền).
  * 95% Hausdorff Distance ($HD_{95}$): $3.38\text{ mm}$.
  * Tốc độ suy luận: $\approx 215\text{ ms}$ (CPU) / $< 35\text{ ms}$ (NVIDIA RTX 3050 GPU).

---

## 5. ĐỊNH VỊ ỨNG DỤNG & NGUYÊN TẮC HUMAN-IN-THE-LOOP (HITL)
1. **Hỗ trợ phân đoạn, không chẩn đoán thay bác sĩ:** Hệ thống chỉ thực hiện bóc tách đường viền và ước lượng kích thước khối u buồng trứng, hỗ trợ bác sĩ giảm tải thao tác vẽ tay.
2. **Quy trình HITL bắt buộc:**
   $$\text{Ảnh siêu âm Vinmec} \rightarrow \text{AI tiền xử lý \& phân đoạn} \rightarrow \text{Lớp phủ Mask/Overlay} \rightarrow \text{Bác sĩ rà soát} \rightarrow \text{Bác sĩ chỉnh sửa (Brush/Eraser)} \rightarrow \text{Xác nhận & Lưu trữ}$$
3. **Bản quyền & Tuyên bố miễn trừ trách nhiệm:** Sản phẩm phần mềm là bản mẫu nghiên cứu thực nghiệm trong khuôn khổ Khóa luận Tốt nghiệp tại Đại học Kinh tế Quốc dân, không phải là thiết bị y tế SaMD thương mại chính thức được phê duyệt của Vinmec.
