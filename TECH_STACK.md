# DANH MỤC CÔNG NGHỆ & QUY TẮC LỰA CHỌN KIẾN TRÚC (TECH STACK & ARCHITECTURE GUIDELINES)
> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (MIS / ITBA / AI)  
> **Cập nhật**: 2026-09-17  
> **Mục đích**: Tài liệu nguồn sự thật (Single Source of Truth) về toàn bộ công nghệ, thư viện và quy tắc chọn stack khi viết code, xây dựng model, tiền xử lý và phát triển API. **Tất cả AI Agent / Lập trình viên PHẢI đọc file này trước khi code.**

---

## 1. MÔI TRƯỜNG PHẦN CỨNG & RUNTIME CHUẨN

* **Hệ điều hành**: Windows (PowerShell / CMD).
* **Python Runtime**: Python 3.12.10 (Môi trường ảo cô lập tại `.venv/`).
* **Phần cứng Tăng tốc AI (Hardware Acceleration)**:
  * **GPU**: `NVIDIA GeForce RTX 3050 Laptop GPU`.
  * **CUDA Version**: `12.4` (PyTorch driver `torch==2.6.0+cu124`, `torchvision==0.21.0+cu124`).
  * **Quy tắc thiết bị trong code**:
    ```python
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ```
    *Tuyệt đối không hardcode `"cuda"` hoặc `"cpu"`.*

---

## 2. BẢNG TRA CỨU CÔNG NGHỆ THEO PHÂN TẦNG KIẾN TRÚC

| Phân tầng (Layer) | Công nghệ / Thư viện | Phiên bản | Vai trò & Mục đích sử dụng | Khi nào sử dụng? |
| :--- | :--- | :--- | :--- | :--- |
| **Deep Learning Core** | `torch`, `torchvision` | 2.6.0+cu124 | Nền tảng huấn luyện & suy luận tensor trên GPU. | Dựng model, forward pass, tính gradient, inference. |
| **Medical Deep Learning** | `monai` | >= 1.6.0 | Medical Open Network for AI (NVIDIA). | Hàm loss y tế, transforms chuẩn không gian y khoa, trích xuất đặc trưng. |
| **Segmentation Backbones** | `segmentation-models-pytorch` | >= 0.5.0 | Thư viện U-Net, FPN, DeepLabV3+ có pretrained encoder. | Dùng làm **Baseline & Benchmark thực nghiệm** (so sánh với mô hình đề xuất). |
| **Model Tự xây dựng (Core)** | `backend/models/attention_unet.py` | v1.2.0 | **Attention U-Net Dual Attention Gates** (Mô hình trọng tâm của KLTN). | Mô hình sản xuất chính (Production Model) phục vụ suy luận chẩn đoán. |
| **Model Đối chuẩn (Baseline)** | `backend/models/unet.py` | v1.2.0 | Standard U-Net chuẩn 4 tầng encoder-decoder. | Đối chuẩn baseline trong bài báo cáo khóa luận. |
| **Metrics Đánh giá** | `torchmetrics`, `backend/models/metrics.py` | >= 1.9.0 | Đo lường định lượng: Dice Score, mIoU, Precision, Recall, Specificity. | Đánh giá checkpoint, test set, kiểm thử hồi quy. |
| **Định dạng Ảnh Y tế** | `pydicom` | >= 3.0.0 | Đọc cấu trúc tệp DICOM (`.dcm`), bóc tách tags y tế. | Khi đọc ảnh thô từ máy siêu âm, lấy `PixelSpacing` (mm/pixel). |
| **Xử lý Khối Y tế** | `simpleitk`, `nibabel` | Latest | Xử lý ảnh y khoa đa chiều, định dạng NIfTI. | Xử lý volume 3D hoặc chuỗi frame siêu âm liên tục. |
| **Thị giác Máy tính** | `opencv-python`, `scikit-image`, `Pillow` | OpenCV 5.x | Xử lý hình thái (Morphology), tìm đường bao (Contour), đo Caliper. | Đo $D_{\max}, D_{\text{orth}}$, tính chu vi, diện tích, độ lồi lõm tổn thương. |
| **Data Augmentation** | `albumentations` | >= 1.4.0 | Tăng cường dữ liệu y tế (Shift, Scale, Rotate, Elastic, GridDistortion). | Chỉ dùng trong Training Pipeline (giữ nguyên giải phẫu, không làm biến dạng mô học). |
| **Tính toán & Dữ liệu** | `numpy`, `pandas`, `scipy`, `scikit-learn` | Numpy 2.x, Pandas 3.x | Xử lý ma trận pixel, thống kê ca khám, phân cụm, ROC/AUC curve. | Bảng dữ liệu lâm sàng, ma trận nhầm lẫn (Confusion Matrix). |
| **Web API Backend** | `fastapi`, `uvicorn`, `starlette` | FastAPI >= 0.141 | RESTful API phi đồng bộ (Asynchronous Endpoints) phục vụ chẩn đoán. | Tiếp nhận ảnh tải lên, trả kết quả JSON + Mask RLE + Phân loại O-RADS. |
| **Validation & Schemas** | `pydantic`, `pydantic-settings` | Pydantic v2 | Kiểm thực kiểu dữ liệu đầu vào/ra, đọc biến cấu hình môi trường (`.env`). | Mọi Request/Response model và Settings cấu hình hệ thống. |
| **Cơ sở dữ liệu & ORM** | `SQLAlchemy`, `alembic` | 2.0+ | Quản lý schema database quan hệ, migration bảng. | Quản lý bệnh nhân, ca siêu âm, lịch sử duyệt mask (HITL audit trail). |
| **Cơ sở dữ liệu thực tế** | SQLite (`ovarian_ai.db`) | Local file | Lưu trữ toàn bộ dữ liệu ca khám, kết quả suy luận và chỉnh sửa. | Database mặc định cục bộ của hệ thống. |
| **Báo cáo Kết quả Y tế** | `reportlab` | >= 5.0.0 | Sinh tài liệu PDF Phiếu Siêu âm / Chẩn đoán Lâm sàng tự động. | Khi bác sĩ ấn nút "Xuất kết quả PDF" trong module `report_generator.py`. |
| **Bảo mật & Phân quyền** | `PyJWT`, `cryptography` | Latest | Mã hóa mật khẩu, cấp và xác thực JSON Web Token. | Đăng nhập bác sĩ / kỹ thuật viên, bảo mật bệnh án. |
| **Quản lý Thực nghiệm** | `wandb`, `tensorboard` | Latest | Theo dõi đồ thị hàm mất mát (Loss curve), tham số huấn luyện. | Quá trình train model, lưu lại artifact weights `.pt`/`.pth`. |
| **Kiểm thử & QA** | `pytest`, `pytest-asyncio` | Latest | Kiểm thử đơn vị (Unit test) và kiểm thử tích hợp (Integration test). | Viết test cho endpoint API, độ chính xác của hàm đo Caliper và hàm Loss. |
| **Code Style & Linting** | `ruff` | >= 0.16.8 | Định dạng code tự động, kiểm tra lỗi PEP8 (Line length: 120). | Chạy trước khi commit code hoặc hoàn tất module. |

---

## 3. QUY TẮC LỰA CHỌN CÔNG NGHỆ KHI PHÁT TRIỂN (DECISION RULES)

### Quy tắc 1: Chọn Model Segmentation
* **Mặc định trong CDSS Engine**: Dùng [`backend/models/attention_unet.py`](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/backend/models/attention_unet.py). Đây là mô hình chính thức với cơ chế Attention Gates giúp tập trung vào vùng biên nang/u buồng trứng, giảm nhiễu tiếng dội siêu âm (acoustic speckle).
* **Khi nào dùng `segmentation-models-pytorch` (SMP)**: Chỉ sử dụng trong các script thử nghiệm benchmark (`experiments/` hoặc `notebooks/`) để tạo bảng so sánh hiệu năng giữa mô hình Attention U-Net đề xuất với các backbone chuẩn (ResNet-34, EfficientNet-B2).

### Quy tắc 2: Chọn thư viện xử lý ảnh
* **Khi đọc ảnh đầu vào**:
  * Nếu tệp là `.dcm` (DICOM): **Bắt buộc** dùng `pydicom` để lấy `PixelSpacing` và mảng ảnh đã chuyển đổi sang Hounsfield/Grayscale chuẩn.
  * Nếu tệp là `.png`, `.jpg`, `.bmp`: Dùng `cv2.imread(..., cv2.IMREAD_GRAYSCALE)` hoặc `PIL.Image`.
* **Khi trích xuất số đo lâm sàng**:
  * Dùng [`backend/services/morphology_extractor.py`](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/backend/services/morphology_extractor.py) kết hợp `cv2.findContours`, `cv2.minAreaRect`, `cv2.fitEllipse` để tính $D_{\max}$ (đường kính lớn nhất) và $D_{\text{orth}}$ (đường kính vuông góc).
  * Quy đổi pixel sang millimeter (mm) bằng công thức: $\text{mm} = \text{pixels} \times \text{PixelSpacing}$.

### Quy tắc 3: Chọn hàm Loss & Đánh giá Y tế
* **Hàm mất mát (Loss Function)**:
  * Tuyệt đối không dùng CrossEntropy đơn thuần.
  * Bắt buộc dùng **Combo Loss** ($L_{\text{Dice}} + L_{\text{BCE}}$) có trong [`backend/models/losses.py`](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/backend/models/losses.py) để cân bằng giữa độ chính xác từng pixel và giải quyết hiện tượng mất cân bằng lớp (vùng nang/u nhỏ hơn nhiều so với nền ảnh siêu âm).
* **Độ đo đánh giá (Evaluation Metrics)**:
  * Bộ 3 chỉ số cốt lõi: **Dice Similarity Coefficient (DSC)**, **Intersection over Union (IoU)**, và **Recall (Sensitivity)** nhằm tránh bỏ sót tổn thương ác tính.

### Quy tắc 4: Tiền xử lý ảnh (Preprocessing)
* **Kích thước ảnh chuẩn**: $512 \times 512$.
* **Phương pháp resize**: **Letterbox Padding** (giữ nguyên tỷ lệ khung hình - Aspect Ratio, thêm padding viền đen) qua [`backend/services/preprocessor.py`](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/backend/services/preprocessor.py). **Cấm co dãn ảnh tự do (Stretching)** vì sẽ làm sai lệch tỷ lệ đo kích thước nang buồng trứng của bác sĩ.

### Quy tắc 5: Cơ chế Human-in-the-Loop (HITL)
* Mọi kết quả do AI dự đoán (mặt nạ phân đoạn, phân loại O-RADS) chỉ mang tính chất **Đề xuất (Recommendation)**.
* Giao diện và API luôn phải cho phép bác sĩ dùng công cụ vẽ lại/tẩy xóa (Brush/Eraser) để hiệu chỉnh mask.
* Phiên bản mask sau khi bác sĩ phê duyệt sẽ được lưu vào cơ sở dữ liệu `ovarian_ai.db` với cờ `is_verified=True` làm Ground Truth phục vụ Active Learning.

---

## 4. BỘ LỆNH VẬN HÀNH CHUẨN

* **Kích hoạt môi trường**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
* **Chạy Web API Backend**:
  ```powershell
  .\.venv\Scripts\uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
  ```
* **Chạy Kiểm thử Toàn diện**:
  ```powershell
  .\.venv\Scripts\pytest -v
  ```
* **Kiểm tra và sửa lỗi Code Style**:
  ```powershell
  .\.venv\Scripts\ruff check . --fix
  ```
