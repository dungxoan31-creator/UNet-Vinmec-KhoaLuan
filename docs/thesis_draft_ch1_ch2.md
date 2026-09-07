# CHƯƠNG 1: TỔNG QUAN BÀI TOÁN VÀ CƠ SỞ LÝ LUẬN

## 1.1 Đặt vấn đề và tính cấp thiết
Trong quy trình chẩn đoán siêu âm phụ khoa, việc phát hiện và đánh giá tổn thương buồng trứng phụ thuộc lớn vào kinh nghiệm trực quan của bác sĩ. Khối lượng công việc tăng cao dễ dẫn đến mệt mỏi, làm tăng rủi ro bỏ sót các tổn thương nhỏ hoặc đánh giá sai ranh giới hình thái (morphology). Dù Trí tuệ Nhân tạo (AI) đã được ứng dụng nhiều trong y tế, các mô hình Deep Learning truyền thống thường đóng vai trò "hộp đen" (Black-box), chỉ đưa ra dự đoán mà không giải thích trực quan, thiếu cơ chế để chuyên gia y tế kiểm chứng và can thiệp.

Đề tài **"Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop"** được thực hiện nhằm giải quyết bài toán trên. Thay vì thay thế bác sĩ, hệ thống áp dụng kỹ thuật Phân đoạn ảnh (Image Segmentation) để khoanh vùng tự động (mask/overlay) vùng nghi ngờ tổn thương. Từ đó, bác sĩ chuyên khoa đóng vai trò trung tâm (Human-in-the-Loop) trong việc đối chiếu, chỉnh sửa và xác nhận kết quả cuối cùng.

## 1.2 Mục tiêu và phạm vi nghiên cứu
### 1.2.1 Mục tiêu nghiên cứu
- **Mục tiêu lý thuyết**: Ứng dụng các chuẩn y khoa quốc tế (ACR O-RADS US v2022, IOTA Lexicon) làm hệ quy chiếu cho bài toán phân đoạn ảnh siêu âm buồng trứng.
- **Mục tiêu thực hành**: Huấn luyện thành công mô hình Deep Learning (U-Net Baseline và Attention U-Net) cho bài toán phân đoạn. Xây dựng Functional Prototype (Web Application) khép kín luồng tương tác: Upload $\rightarrow$ Inference $\rightarrow$ Overlay Viewer $\rightarrow$ Interactive Canvas (Chỉnh sửa) $\rightarrow$ Doctor Confirm.

### 1.2.2 Phạm vi nghiên cứu
- **Dữ liệu**: Trọng tâm sử dụng tập dữ liệu MMOTU với 307 ảnh Ground Truth (từ 185 bệnh nhân). Phân chia tập dữ liệu (Train/Val/Test) nghiêm ngặt theo mức độ bệnh nhân (Patient-level) để chống rò rỉ dữ liệu (Data Leakage).
- **Thuật toán**: Baseline là mạng Standard U-Net, đối sánh với Attention U-Net. Hàm mất mát sử dụng là Combo Loss ($L_{\text{Dice}} + L_{\text{BCE}}$).
- **Ràng buộc Y khoa**: 
  - Hệ thống chỉ "hỗ trợ phân đoạn tổn thương", không đưa ra nhãn chẩn đoán bệnh tự động.
  - Phân định rõ "Bất thường" không đồng nghĩa với "Ác tính" (Abnormal $\neq$ Malignant). Các nang có kích thước $<30\text{ mm}$ thường là nang noãn sinh lý.
  - Tuân thủ thao tác chuẩn hóa ảnh: ROI Fan-beam Cropping và Letterbox Resize $512 \times 512$.

## 1.3 Cơ sở lý luận
### 1.3.1 Kiến thức chuẩn về Siêu âm Buồng trứng
Siêu âm là phương pháp hình ảnh đầu tay trong đánh giá phần phụ. Tổn thương buồng trứng được phân loại theo các hệ thống chuẩn mực như IOTA (Simple Rules, ADNEX) và ACR O-RADS US v2022. Các đặc trưng hình thái (độ hồi âm, ranh giới, vách ngăn, phần đặc, bóng cản âm) quyết định hướng can thiệp. Ví dụ, bóng cản âm (acoustic shadowing) là chỉ điểm đặc trưng của u lành tính (u bì/thecoma). 

### 1.3.2 Mạng Nơ-ron Tích chập (CNN) và U-Net
Mạng U-Net (Ronneberger et al., 2015) là kiến trúc kinh điển trong phân đoạn ảnh y tế. U-Net gồm hai nhánh chính: nhánh nén (Encoder) trích xuất đặc trưng ngữ cảnh, và nhánh giải nén (Decoder) khôi phục độ phân giải. Đặc trưng cốt lõi của U-Net là các kết nối tắt (Skip Connections) giúp kết hợp thông tin chi tiết (low-level) và thông tin ngữ nghĩa (high-level), tối ưu hóa việc phân định ranh giới tổn thương.

### 1.3.3 Mô hình Human-in-the-Loop (HITL)
Trong y tế, HITL là mô hình thiết kế hệ thống trong đó AI thực hiện phân tích tự động, nhưng quyết định cuối cùng và thao tác hiệu chỉnh thuộc về con người. Cơ chế này giải quyết vấn đề thiếu tin cậy của mô hình "hộp đen", cho phép bác sĩ rà soát và điều chỉnh đường biên mask trực tiếp (Interactive Canvas) trước khi lưu kết quả (Doctor Confirm).

---

# CHƯƠNG 2: PHÂN TÍCH NGHIỆP VỤ VÀ ĐẶC TẢ YÊU CẦU HỆ THỐNG

## 2.1 Phân tích hiện trạng (Quy trình As-Is)
Trong quy trình hiện tại, bác sĩ thực hiện siêu âm và quan sát tổn thương bằng mắt thường trên màn hình máy siêu âm. 
- **Bước 1**: Máy siêu âm tạo hình ảnh. Bác sĩ quan sát, tự động ước lượng ranh giới tổn thương.
- **Bước 2**: Bác sĩ tự đo đạc các chiều kích thước (D1, D2, D3) thủ công bằng công cụ caliper của máy siêu âm.
- **Bước 3**: Nhập kết quả đo đạc và chẩn đoán vào hệ thống HIS/RIS.
- **Hạn chế**: Quy trình lặp lại, tốn thời gian. Đường biên tổn thương bị nhòe (do nhiễu speckle) dễ làm sai lệch kết quả đo đạc thủ công.

## 2.2 Đề xuất giải pháp (Quy trình To-Be tích hợp AI)
Hệ thống đề xuất đóng vai trò là Trợ lý phân đoạn hình ảnh (Decision Support System) nằm giữa bước thu nhận ảnh và kết luận.
- **Bước 1**: Bác sĩ tải ảnh siêu âm định dạng tiêu chuẩn (DICOM/PNG/JPG) lên hệ thống Web.
- **Bước 2**: Backend (PyTorch/Inference Engine) thực hiện tiền xử lý (ROI Crop, Letterbox Resize) và chạy suy luận sinh ra Mask ranh giới (thời gian $\le 1.0\text{s}$).
- **Bước 3**: Frontend hiển thị Mask dưới dạng lớp phủ (Overlay) có thể điều chỉnh độ trong suốt.
- **Bước 4 (HITL)**: Bác sĩ dùng công cụ Brush/Eraser để chỉnh sửa đường biên phân đoạn bị sai lệch do nhiễu.
- **Bước 5**: Bác sĩ nhấn "Confirm" để lưu kết quả và xuất báo cáo thông số kỹ thuật phục vụ lưu trữ.

## 2.3 Đặc tả yêu cầu hệ thống (Software Requirements Specification)

### 2.3.1 Yêu cầu chức năng (Functional Requirements)
1. **Module Quản lý Dữ liệu**:
   - Cho phép upload ảnh siêu âm (đơn lẻ hoặc theo ca bệnh).
   - Hiển thị danh sách ảnh đang chờ xử lý.
2. **Module Suy luận AI (AI Inference)**:
   - Tự động chạy mô hình U-Net/Attention U-Net để sinh mặt nạ phân đoạn (Segmentation Mask).
   - Tự động thực hiện pipeline tiền xử lý (ROI Cropping, Letterbox Resize 512x512, Normalization).
3. **Module Không gian thao tác Y tế (Clinical Canvas / HITL)**:
   - Cung cấp giao diện xem ảnh (Original vs Overlay Mask).
   - Hỗ trợ công cụ Brush (cọ vẽ thêm mask) và Eraser (tẩy mask thừa).
   - Hỗ trợ điều chỉnh Opacity, Zoom, Pan.
4. **Module Trích xuất Báo cáo**:
   - Lưu trữ lịch sử rà soát của bác sĩ.
   - Xuất phiếu tóm tắt thông số phân đoạn phục vụ nghiên cứu lâm sàng.

### 2.3.2 Yêu cầu phi chức năng (Non-Functional Requirements)
- **Hiệu năng (Performance)**: Thời gian phản hồi cho mỗi lượt suy luận ảnh $\le 1.0$ giây.
- **Bảo mật (Security)**: Toàn bộ dữ liệu bệnh nhân tải lên phải được coi là đã ẩn danh, hệ thống không lưu trữ trực tiếp thông tin nhận diện cá nhân (PHI).
- **Độ chính xác (Accuracy Baseline)**: Thuật toán AI cần đạt ngưỡng tối thiểu đánh giá qua hệ số Dice và IoU trên tập Test Set độc lập.
- **Khả dụng (Usability)**: Giao diện tối màu (Dark mode) độ tương phản cao, phù hợp với môi trường phòng đọc ảnh siêu âm; hỗ trợ thao tác mượt mà.

## 2.4 Mô hình hóa Hệ thống

### 2.4.1 Luồng xử lý nghiệp vụ chính (BPMN / Activity Diagram)
```mermaid
flowchart TD
    A[Bác sĩ tải ảnh siêu âm] --> B[Hệ thống Tiền xử lý]
    B --> C["Cắt ROI & Letterbox Resize (512x512)"]
    C --> D[Mô hình Deep Learning Dự đoán Mask]
    D --> E[Giao diện Overlay Viewer]
    E --> F{"Bác sĩ kiểm tra ranh giới?"}
    F -- "Đồng ý" --> H[Bác sĩ Xác nhận (Confirm)]
    F -- "Sai lệch" --> G["Chỉnh sửa bằng Canvas (Brush/Eraser)"]
    G --> H
    H --> I[Xuất báo cáo lưu trữ]
```

### 2.4.2 Kiến trúc Hệ thống Tổng thể
Hệ thống được thiết kế theo kiến trúc Micro-core:
- **Frontend (UI/UX)**: HTML5/JS với Canvas API xử lý thao tác vẽ/tẩy trực tiếp trên trình duyệt.
- **Backend**: FastAPI xử lý định tuyến (Routing) và kết nối I/O.
- **Inference Engine**: PyTorch thực thi các Model (U-Net) đã qua huấn luyện, nạp sẵn trọng số (Weights) vào VRAM/RAM để đảm bảo độ trễ thấp. 
- **Storage**: SQLite/Local Storage lưu trữ metadata thực nghiệm.
