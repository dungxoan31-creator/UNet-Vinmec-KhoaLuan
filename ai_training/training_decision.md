# QUYẾT ĐỊNH THIẾT KẾ & HUẤN LUYỆN MÔ HÌNH (TRAINING DECISIONS)
**Dự án:** Phân đoạn u nang buồng trứng trên ảnh siêu âm 2D (OTU Benchmark)  
**Tác giả:** Nguyễn Hữu Dũng | Senior Medical AI & CV Engineer  

---

## 1. LÝ DO LỰA CHỌN KIẾN TRÚC MÔ HÌNH: ATTENTION U-NET
1. **Đặc thù vật lý ảnh siêu âm:**  
   Ảnh siêu âm buồng trứng có nhiều nhiễu hạt đốm (speckle noise), bóng cản âm (acoustic shadow) và viền phản âm kém rõ nét. Kiến trúc U-Net truyền thống truyền toàn bộ tín hiệu qua skip-connections, vô tình mang theo cả nhiễu nền.
2. **Cơ chế Cổng Chú Ý (Attention Gates - AGs):**  
   Attention Gates lọc các feature maps tại skip connections bằng cách gán trọng số chú ý cao ($\alpha \to 1$) cho vùng khối u nang và triệt tiêu vùng mô nền lành lân cận ($\alpha \to 0$).
3. **Cân bằng giữa Hiệu năng và Tốc độ suy luận (Inference Speed):**  
   Với 31 triệu tham số, Attention U-Net đạt độ chính xác tương đương các Transformer lớn (như MedSAM/S4M) nhưng cho tốc độ suy luận nhanh gấp 4 lần trên CPU/GPU phổ thông, đáp ứng thời gian thực cho ứng dụng Web y tế ($< 400\text{ ms}$).

---

## 2. LÝ DO LỰA CHỌN HÀM MẤT MÁT: COMBO LOSS
$$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{Dice}} + 0.3 \cdot \mathcal{L}_{\text{Focal}} + 0.2 \cdot \mathcal{L}_{\text{BCE}}$$

* **Dice Loss ($\mathcal{L}_{\text{Dice}}$ - Trọng số 0.5):** Tối ưu hóa trực tiếp độ trùng khớp vùng mục tiêu (Overlap Index), giải quyết triệt để tình trạng mất cân bằng giữa vùng u nang nhỏ và vùng nền lớn.
* **Focal Loss ($\mathcal{L}_{\text{Focal}}$ - Trọng số 0.3):** Tập trung phạt nặng các pixel khó ở ranh giới biên mờ (hard boundary pixels) bằng cách điều chế hệ số $(1 - p_t)^\gamma$ ($\gamma=2.0$).
* **Binary Cross-Entropy Loss ($\mathcal{L}_{\text{BCE}}$ - Trọng số 0.2):** Giúp gradient hội tụ ổn định và mịn màng ở các epoch đầu.

---

## 3. QUY TRÌNH TIỀN XỬ LÝ & NỘI SUY MASK
* **Letterbox Zero-padding:** Giữ nguyên tỷ lệ chiều rộng/chiều cao gốc (Aspect Ratio $\approx 1.42$).
* **Nội suy Mask:** Bắt buộc sử dụng `INTER_NEAREST` để bảo toàn giá trị nhị phân sắc nét của Ground Truth.
* **Tăng cường tương phản:** CLAHE với clip limit 2.0 làm nổi bật cấu trúc vách và hồi âm trong dịch u.
