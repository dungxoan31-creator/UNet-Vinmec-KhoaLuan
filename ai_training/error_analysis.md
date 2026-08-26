# PHÂN TÍCH LỖI VÀ GIỚI HẠN MÔ HÌNH (ERROR ANALYSIS REPORT)
**Dự án:** Phân đoạn u buồng trứng trên ảnh siêu âm 2D (OTU Dataset)  
**Tác giả:** Nguyễn Hữu Dũng | Senior Medical AI & CV Engineer  

---

## 1. PHÂN LOẠI CÁC TRƯỜNG HỢP SAI LỆCH (FAILURE MODES)

Qua đánh giá trực quan trên 382 ca kiểm thử độc lập (Test Set), các trường hợp sai lệch được phân loại thành 4 nhóm chính:

### 1.1. Dưới phân đoạn (Under-segmentation)
* **Đặc điểm:** AI chỉ khoanh vùng phần lõi trung tâm của khối u nang, bỏ sót một phần ranh giới ngoại vi.
* **Nguyên nhân y khoa:**
  * Vùng ranh giới ngoài của u nang có độ tương phản giảm dần (hồi âm đẳng âm - isoechoic) tiệm cận với mô đệm buồng trứng (stroma).
  * Chùm tia siêu âm bị suy giảm năng lượng theo độ sâu (attenuation artifact).

### 1.2. Quá phân đoạn (Over-segmentation)
* **Đặc điểm:** AI khoanh vùng lấn sang các cấu trúc giảm âm lân cận (quai ruột chứa dịch, bàng quang hoặc mạch máu chậu).
* **Nguyên nhân y khoa:**
  * Các khoang chứa dịch bình thường cũng có đặc tính giảm âm (anechoic) tương tự dịch u nang thanh dịch.

### 1.3. Nhiễu bóng cản âm (Acoustic Shadowing Distortion)
* **Đặc điểm:** Ranh giới mask bị khuyết một vệt thẳng phía sau cấu trúc tăng âm.
* **Nguyên nhân:**
  * U bì buồng trứng (Dermoid) thường chứa nốt Rokitansky (mô mỡ, tóc, vôi hóa) hấp thụ toàn bộ sóng âm, tạo ra bóng cản đen hoàn toàn phía sau khiến AI mất thông tin cấu trúc đáy.

### 1.4. Ranh giới răng cưa / Dải sợi mạng nhện (Internal Septations / Fibrin Reticulum)
* **Đặc điểm:** U lạc nội mạc tử cung hoặc nang xuất huyết có nhiều vách ngăn xơ hóa hoặc dải sợi fibrin bên trong khiến mask bị phân mảnh nếu không có bước hậu xử lý hình thái học (Morphological Closing).

---

## 2. BIỆN PHÁP KHẮC PHỤC TRONG HỆ THỐNG (MITIGATION STRATEGY)
1. **Hậu xử lý hình thái học (Morphological Filtering):**
   * Áp dụng `cv2.morphologyEx` với phép đóng (Closing) kernel $5\times 5$ để lấp đầy các khoảng trống do vách ngăn bên trong u nang.
   * Lọc bỏ các đốm nhiễu nhỏ có diện tích $< 50\text{ px}$.
2. **Cổng Chú Ý (Attention Gates):**
   * Giúp tập trung gradient vào tâm khối u và giảm thiểu bắt nhầm các cấu trúc nền ngoài góc quét siêu âm.
3. **Quy trình Bác sĩ hiệu chỉnh tương tác (Human-in-the-Loop Safeguard):**
   * Mọi trường hợp nghi ngờ hoặc ảnh có bóng cản phức tạp đều được đưa lên giao diện Dual-Layer Canvas để bác sĩ dùng công cụ cọ vẽ/tẩy xóa hiệu chỉnh lại ranh giới trước khi ký duyệt chính thức.
