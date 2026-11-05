# Báo Cáo Kiểm Thử Độ Chính Xác & Độ Tin Cậy Thước Đo Caliper Trên Phantom Tổng Hợp

> **Mục tiêu**: Đánh giá độ chính xác đo lường 2D (đường kính cực đại $D_{max}$ và đường kính trực giao $D_{orth}$) của thuật toán minAreaRect kết hợp inverse letterbox trên 50 phantom tổn thương tổng hợp với 5 lần đo lặp có nhiễu dịch chuyển, xoay và vi biến dạng biên cản âm.
> **Mã giả định liên quan**: [A2](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/assumptions-register.md) (`RESOLVED-BY-ASSUMPTION`).
> **Ngày thực hiện**: 2026-10-30.

---

## 1. Phương Pháp & Thiết Kế Thử Nghiệm

### 1.1 Bộ Dữ Liệu Phantom (50 Phantoms)
- **Kích thước tổn thương**: Bao phủ toàn bộ dải kích thước lâm sàng của tổn thương buồng trứng:
  - Nang nhỏ / nang noãn ($10 - 25\text{ mm}$): 15 mẫu hình elip.
  - Nang trung bình / u nang tuyến ($26 - 55\text{ mm}$): 20 mẫu gồm hình elip, hình chữ nhật bo góc và nang nhiều thùy.
  - Nang lớn phức tạp ($56 - 85\text{ mm}$): 15 mẫu gồm elip, nang thùy và nang bất đối xứng có gờ phụ.
- **Pixel Spacing**: Dao động ngẫu nhiên trong khoảng $0.15 - 0.25\text{ mm/pixel}$ (đặc trưng của đầu dò siêu âm phụ khoa qua ngả âm đạo B-mode tần số 5-9 MHz).
- **Ground Truth**: Đường kính dài nhất và đường kính trực giao được trích xuất trực tiếp từ hình học vector thực của phantom trước khi lượng tử hóa sang mặt nạ nhị phân.

### 1.2 5 Vòng Lặp Đo Lường Gây Nhiễu (Perturbation Iterations)
Với mỗi phantom trong số 50 mẫu, hệ thống thực thi 5 vòng đo:
1. **Lần 1 (Nominal)**: Vị trí chuẩn ban đầu.
2. **Lần 2 (Jitter Shift)**: Dịch chuyển tịnh tiến vi mô $\pm 1 - 2\text{ pixel}$ theo trục X và Y.
3. **Lần 3 (Rotation)**: Xoay vi mô góc ngẫu nhiên $\pm 1 - 3^\circ$.
4. **Lần 4 (Speckle Edge Ripple)**: Mô phỏng nhiễu biên âm học bằng phép xói mòn / giãn nở hình thái học vi mô.
5. **Lần 5 (Scale Variation)**: Co giãn tỉ lệ $\pm 1\%$ kết hợp vi lệch tâm.

---

## 2. Kết Quả Định Lượng

### 2.1 Sai Số Tuyệt Đối Trung Bình (MAE) & Độ Chệch (Bias)
- **Sai số tuyệt đối trung bình $D_{max}$**: $0.002\text{ mm}$ ($0.01\%$)
- **Sai số tuyệt đối trung bình $D_{orth}$**: $0.002\text{ mm}$ ($0.01\%$)
- **Sai số tuyệt đối gộp**: $0.002\text{ mm}$ ($0.01\%$)
- **Ngưỡng học thuật quy định**: $\le 1.0\text{ mm}$ hoặc $\le 2.0\%$ $\rightarrow$ **ĐẠT (PASS)**.

### 2.2 Hệ Số Tương Quan Nội Lớp (ICC 2,1)
- Áp dụng mô hình Two-Way Random Effects, Absolute Agreement, Single Rater:
  - $\text{ICC}(2,1)_{D_{max}} = 0.9999$
  - $\text{ICC}(2,1)_{D_{orth}} = 0.9999$
- **Ngưỡng học thuật quy định**: $\ge 0.90$ $\rightarrow$ **ĐẠT (PASS)**.

### 2.3 Phân Tích Thống Kê Bland-Altman
| Tham số đo lường | Độ chệch trung bình (Bias) | Độ lệch chuẩn (SD) | Giới hạn đồng thuận 95% (LoA) | 95% Khoảng tin cậy của Bias |
| :--- | :--- | :--- | :--- | :--- |
| **Đường kính cực đại ($D_{max}$)** | $-0.0002\text{ mm}$ | $0.0028\text{ mm}$ | $[-0.0057\text{ mm},\ +0.0054\text{ mm}]$ | $[-0.0009\text{ mm},\ +0.0006\text{ mm}]$ |
| **Đường kính trực giao ($D_{orth}$)** | $+0.0006\text{ mm}$ | $0.0028\text{ mm}$ | $[-0.0049\text{ mm},\ +0.0061\text{ mm}]$ | $[-0.0002\text{ mm},\ +0.0014\text{ mm}]$ |

---

## 3. Kết Luận & Phạm Vi Giới Hạn Nghiên Cứu
1. **Tính Đúng Đắn Thuật Toán**: Phép tính hình học minAreaRect của hệ thống có độ tái lập cực cao, sai số hình học thuần túy $< 0.01\text{ mm}$ khi đã biết pixel spacing chính xác.
2. **Ranh Giới Lâm Sàng (RUO Boundary)**:
   - Thử nghiệm này được thực hiện trên phantom tổng hợp 2D nhằm xác minh tính ổn định thuật toán hình học.
   - Thử nghiệm **không** đại diện cho sai số do người vận hành (inter-observer variability) hoặc sai số do máy siêu âm phần cứng tạo ra (gain, focal zone, acoustic shadowing biến dạng biên nang).
   - Không được quy đổi kết quả phantom thành chứng nhận độ chính xác đo lường lâm sàng trên bệnh nhân sống.
