---
title: Vinmec Ovarian Ultrasound AI Workstation
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# Hệ thống Phân đoạn Siêu âm Buồng trứng Human-in-the-Loop (CDSS)
> **Ovarian Ultrasound AI Decision Support System**  
> Dự án Khóa luận Tốt nghiệp Hệ thống Thông tin Quản lý (MIS / ITBA / AI) – Trường Đại học Kinh tế Quốc dân (NEU).  
> Dữ liệu nghiên cứu thực nghiệm: Bệnh viện Đa khoa Quốc tế Vinmec Times City.

> **Trạng thái bằng chứng 21/10/2026:** RUO research prototype. Manifest hiện chọn ứng viên U-Net++/ResNet34 với horizontal-flip TTA và threshold 0.4; Validation Dice 0.8185 trên 541 ảnh, không phải ước lượng test độc lập. Patient ID nguồn chưa xác minh, 59 cặp ảnh gần trùng được ghi nhận giữa split, ảnh `dataset/2d/images/1456.JPG` đang thiếu và cổng patient-level independent test bị BLOCKED. Chưa có clinician validation. Xem [Model Card](MODEL_CARD.md), [kiểm toán kiến trúc](docs/ARCHITECTURE_AUDIT_2026-10-21.md) và [hồ sơ inventory](docs/SYSTEM_INVENTORY_2026-10-21.md).

---

## 1. Giới thiệu Tổng quan & Bài toán Giải quyết

### 1.1. Bối cảnh & Thách thức Y tế
Chẩn đoán hình ảnh siêu âm buồng trứng (phát hiện nang, u nang, khối u đặc/hỗn hợp) là kỹ thuật phổ biến nhưng phụ thuộc lớn vào kinh nghiệm chủ quan của bác sĩ chuyên khoa. Các tổn thương buồng trứng thường có ranh giới phức tạp, độ tương phản mô mềm thấp, nhiễu âm (speckle noise) và biến dạng giải phẫu lớn giữa các bệnh nhân.

### 1.2. Giải pháp của Dự án
Dự án xây dựng bản mẫu phần mềm hỗ trợ ra quyết định lâm sàng (**Clinical Decision Support System - CDSS**), kết hợp mô hình học sâu phân đoạn ảnh y tế và giao diện máy trạm lâm sàng (Clinical Workstation):
- **Phân đoạn tự động bằng Deep Learning**: Model registry hiện chọn ứng viên nghiên cứu U-Net++/ResNet34; Standard U-Net được giữ làm baseline. Mask chỉ là kết quả phân đoạn, không xác định bệnh lý.
- **Trích xuất thông số hình thái tự động (Morphometry)**: Đo lường đường kính tổn thương (Caliper $d_1, d_2$), chu vi, diện tích và thể tích phỏng định theo khuyến cáo ISUOG.
- **Cơ chế Human-in-the-Loop (HITL)**: Bác sĩ rà soát kết quả phân đoạn và có thể tinh chỉnh đường viền bằng Brush/Eraser. Lưu review nghiên cứu được hỗ trợ; workflow ký duyệt chính thức và xuất PDF lâm sàng hiện đang tắt.

> [!IMPORTANT]
> **Tuyên bố Phạm vi Lâm sàng (Clinical Disclaimer)**: Hệ thống là bản mẫu nghiên cứu thực nghiệm (Research Prototype). Kết quả phân đoạn đường viền và đo đạc hình thái đóng vai trò hỗ trợ tham khảo; hệ thống không đưa ra kết luận chẩn đoán bệnh học tự động và không thay thế quyết định chuyên môn của bác sĩ.

---

## 2. Các Chức năng Chính của Hệ thống

1. **Quản lý Ca khám & Ảnh siêu âm (Case Management)**:
   - Tiếp nhận thông tin bệnh nhân, mã hồ sơ (PID) và quản lý ảnh siêu âm độc lập cho hai bên buồng trứng (Phải - Right / Trái - Left).
   - Hỗ trợ định dạng ảnh đồ họa tiêu chuẩn (JPG, PNG) và định dạng chuẩn y tế DICOM (`.dcm`), tự động trích xuất thông số tỷ lệ vật lý (Pixel Spacing).
2. **Kiểm định Chất lượng Ảnh (Image Quality Assessment - IQA)**:
   - Xác thực tỷ lệ khung hình, độ tương phản và kiểm tra tính hợp lệ của ảnh siêu âm trước khi đưa vào mô hình học sâu.
3. **Phân đoạn Tổn thương Tự động (Automated U-Net Inference)**:
   - Tiền xử lý chuẩn y tế: Cân bằng biểu đồ độ sáng cục bộ CLAHE, Letterbox giữ nguyên tỷ lệ khung hình $512 \times 512$.
   - Suy luận qua model được chọn trong manifest. Cấu hình hiện tại là ứng viên U-Net++/ResNet34; Standard U-Net là baseline. Kết quả là mặt nạ nhị phân và lớp phủ trực quan, không phải nhãn chẩn đoán.
4. **Máy trạm Rà soát Tương tác Human-in-the-Loop (Interactive Workstation)**:
   - Canvas đa lớp thời gian thực: Hiển thị song song ảnh gốc, lớp phủ AI và công cụ vẽ tay.
   - Bộ công cụ chỉnh sửa lâm sàng: Bút vẽ viền (Brush), Tẩy (Eraser), điều chỉnh kích thước nét, tùy chỉnh độ mờ (Opacity slider), Hoàn tác / Làm lại (Undo/Redo).
5. **Đo đạc Hình thái Tổn thương (Morphology Extraction)**:
   - Tự động trích xuất bao lồi, chu vi và đo 2 trục đường kính vuông góc lớn nhất ($d_1, d_2$). Quy đổi ra milimet (mm) chính xác nếu ảnh có gắn nhãn DICOM spacing.
6. **Xuất Phiếu Kết quả Siêu âm (Medical Report Generation)**:
   - Workstation tạo preview bản nháp RUO từ ảnh, số đo và nhận xét. API PDF/server report trả 501; chưa có xác thực người duyệt lâm sàng tin cậy.
7. **Kiểm toán Hệ thống & Quản trị (Admin & Audit Trails)**:
   - Audit log ghi nhận các thao tác như tải ảnh, đọc ca, suy luận và review. Ký duyệt chính thức chưa được bật.

---

## 3. Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế theo kiến trúc phân tầng dạng Client - Server với tính mô-đun hóa cao:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      CLINICAL FRONTEND WORKSTATION                     │
│  (HTML5 / CSS3 Dark Mode / Canvas Multilayer / Vanilla JavaScript ES6) │
│  - Case Navigator      - Multi-layer Canvas       - Brush / Eraser     │
│  - Measurement Overlay - HITL Doctor Review Panel - Medical Report UI  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / RESTful API (JSON & Multipart)
┌───────────────────────────────────▼────────────────────────────────────┐
│                       BACKEND API SERVICE (FastAPI)                    │
│  - Routers: /cases, /inference, /reviews, /admin, /evaluation          │
│  - Core Services: Preprocessor (Letterbox/CLAHE), MorphologyExtractor  │
│  - Security & Storage: Input validation, Audit trails, SQLite Database │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PyTorch Tensor Pipeline
┌───────────────────────────────────▼────────────────────────────────────┐
│                    MODEL CORE & CLINICAL REASONING                     │
│  - Model Registry: Checkpoint SHA-256 Verification                     │
│  - Current research candidate: U-Net++ (ResNet34); Standard U-Net baseline │
│  - Inference Engine: Automatic CPU / CUDA Device Selection             │
│  - Morphometry Engine: Caliper (d1, d2), Area, Perimeter Calculation   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Công nghệ Sử dụng (Tech Stack)

| Thành phần | Công nghệ / Thư viện | Phiên bản | Vai trò & Mục đích sử dụng |
|---|---|---|---|
| **Ngôn ngữ lõi** | Python | 3.12+ | Môi trường thực thi toàn bộ Backend và Pipeline AI |
| **API Framework** | FastAPI, Starlette, Uvicorn | 0.141+ | Cung cấp dịch vụ RESTful API tốc độ cao, xử lý đa tiến trình |
| **Học sâu (Deep Learning)**| PyTorch, Torchvision | 2.8.0+ | Huấn luyện mô hình và thực thi suy luận mạng U-Net / U-Net++ |
| **Kiến trúc mở rộng** | segmentation-models-pytorch | 0.5.0+ | Hỗ trợ cấu hình mạng phân đoạn U-Net++ với pretrained backbone |
| **Xử lý ảnh Y tế** | OpenCV (`cv2`), Pillow, Albumentations | 5.0+ | Đọc ảnh, tiền xử lý Letterbox, thuật toán CLAHE, tăng cường dữ liệu |
| **Chuẩn ảnh DICOM** | pydicom | 3.0+ | Giải mã ảnh định dạng DICOM và trích xuất thẻ siêu âm (Pixel Spacing) |
| **Cơ sở dữ liệu** | SQLite, SQLAlchemy, Pydantic v2 | 2.1+ | Lưu trữ thông tin ca bệnh, lịch sử đánh giá và kiểm thực dữ liệu vào/ra |
| **Giao diện Người dùng**| HTML5, CSS3, JavaScript (Canvas API) | Native ES6 | Workstation mượt mà, không phụ thuộc nặng framework client |
| **Kiểm thử & Chất lượng**| Pytest, Playwright, Ruff | 9.1+ | Kiểm thử tự động (Unit / Integration / E2E Browser) và linting |
| **Triển khai Container**| Docker, Docker Compose, Nginx | - | Đóng gói môi trường và cấu hình Reverse Proxy phục vụ vận hành |

---

## 5. Cấu trúc Thư mục Dự án

```text
UNet-Vinmec-KhoaLuan/
├── backend/                 # Máy chủ dịch vụ FastAPI Backend
│   ├── app/                 # Điểm khởi chạy API (main.py), định tuyến routers/, cấu hình (config.py)
│   ├── core/                # Xử lý hình ảnh cấp thấp (image_utils.py)
│   ├── db/                  # Khởi tạo cơ sở dữ liệu SQLAlchemy (database.py)
│   ├── models/              # Kiến trúc mạng nơ-ron (unet.py, attention_unet.py, losses.py)
│   ├── schemas/             # Pydantic Schemas kiểm thực dữ liệu đầu vào/ra
│   └── services/            # Dịch vụ nghiệp vụ: InferenceEngine, Preprocessor, MorphologyExtractor
├── frontend/                # Giao diện Web Workstation dành cho bác sĩ
│   ├── css/                 # Giao diện Dark Mode tối ưu cho phòng chẩn đoán hình ảnh
│   ├── js/modules/          # Module xử lý Canvas, API, tương tác HITL, vẽ đo đạc
│   └── index.html           # Trang giao diện chính của hệ thống
├── ai_training/             # Pipeline huấn luyện mô hình PyTorch
│   ├── dataset_loader.py    # Dataloader ảnh siêu âm kèm Letterbox & CLAHE
│   ├── metrics_clinical.py  # Bộ đo lường phân đoạn lâm sàng (Dice, IoU, Recall, Specificity)
│   ├── splits/              # Cấu hình phân chia tập dữ liệu huấn luyện, thẩm định và kiểm thử
│   └── train_baseline_unet.py # Huấn luyện mô hình U-Net cơ sở
├── dataset/                 # Thư mục dữ liệu ảnh gốc (Chỉ đọc - Read Only)
│   ├── 2d/                  # Ảnh siêu âm 2D B-mode (images/ và masks/)
│   ├── 3d/                  # Thư mục nguồn tên 3d; pipeline hiện xử lý từng ảnh 2D
│   └── index.csv            # Chỉ mục mẫu đủ điều kiện theo manifest split; không gồm ảnh fallback bị loại
├── metadata/                # Metadata lịch sử của 307 bản ghi Mốc 1
│   ├── kltn_ground_truth_307.csv # Nhãn tham chiếu lịch sử; phê duyệt chuyên gia chưa xác minh
│   ├── train.csv, val.csv, test.csv # Phân chia lịch sử; Patient ID nguồn chưa xác minh
│   └── thesis_exports/      # File CSV tiếng Việt phục vụ phụ lục khóa luận
├── checkpoints/             # Trọng số mô hình đã huấn luyện (.pth)
│   ├── unified_vinmec_refine_2026-10-06/ # Checkpoint Standard U-Net baseline / lịch sử
│   └── unetplusplus_resnet34_2026-10-06/ # Checkpoint ứng viên U-Net++ đang được manifest chọn
├── evaluation/              # Minh chứng kiểm thử kỹ thuật và metric phân đoạn; chưa thẩm định lâm sàng
│   ├── selected_model.json  # Manifest chỉ định mô hình phục vụ với mã băm SHA-256
│   └── archive/             # Kho lưu trữ kết quả thực nghiệm các mốc trước
├── scripts/                 # Bộ công cụ xử lý dữ liệu, kiểm toán và xuất báo cáo
├── templates/               # Mẫu HTML phiếu kết quả siêu âm
├── tests/                   # Bộ kiểm thử tự động (Pytest & Playwright)
├── data/                    # Thư mục runtime cục bộ (uploads tạm và reports sinh ra)
├── MODEL_CARD.md            # Báo cáo kỹ thuật mô hình (Model Card)
├── TECH_STACK.md            # Thông số chi tiết các phiên bản thư viện
├── pyproject.toml           # Cấu hình Pytest và Ruff
├── Dockerfile               # File build container Docker
└── docker-compose.yml       # Cấu hình khởi chạy hệ thống cùng Nginx
```

---

## 6. Luồng Hoạt động Cốt lõi (Workflow)

```mermaid
sequenceDiagram
    autonumber
    actor BacSi as "Bác sĩ Siêu âm"
    participant UI as "Web Workstation (Frontend)"
    participant API as "FastAPI Backend"
    participant DL as "Inference Engine (model candidate in manifest)"
    participant Morph as "Morphology Extractor"
    participant DB as "SQLite Database"

    BacSi->>UI: "Tải ảnh siêu âm (JPG/PNG/DICOM) buồng trứng P/T"
    UI->>API: "POST /api/upload"
    API->>API: "Tiền xử lý grayscale + CLAHE + Letterbox 512x512"
    API->>DB: "Lưu bản ghi ảnh và ca khám"
    API-->>UI: "Trả image_id và thông tin ban đầu"

    BacSi->>UI: "Yêu cầu phân đoạn AI"
    UI->>API: "POST /api/predict/{image_id}"
    API->>DL: "Suy luận model được chọn; hiện là U-Net++/ResNet34 + flip TTA"
    DL-->>API: "Mặt nạ phân đoạn 512x512"
    API->>API: "Inverse Letterbox về kích thước ảnh gốc"
    API->>Morph: "Trích xuất caliper d1/d2, diện tích và chu vi"
    Morph-->>API: "Số đo hình thái tham khảo"
    API-->>UI: "Trả kết quả phân đoạn, overlay và số đo tham khảo"

    BacSi->>UI: "Rà soát và tinh chỉnh đường viền HITL"
    Note over BacSi,UI: "Review được lưu ở chế độ RUO; không phải phê duyệt lâm sàng"
    BacSi->>UI: "Lưu review"
    UI->>API: "POST /api/review"
    API->>DB: "Lưu mask review và audit event"
    API-->>UI: "Review đã lưu; workflow ký duyệt và PDF đang tắt"
```

---

## 7. Yêu cầu Môi trường & Hướng dẫn Cài đặt

### 7.1. Yêu cầu Hệ thống
- **Hệ điều hành**: Windows 10/11, Ubuntu 20.04+, hoặc macOS.
- **Python**: Phiên bản `>= 3.10` (khuyến nghị `Python 3.12`).
- **Phần cứng đề xuất**: RAM tối thiểu 8 GB; có GPU NVIDIA (VRAM $\ge 4\text{ GB}$) nếu muốn huấn luyện hoặc tối ưu độ trễ suy luận (hệ thống tự động chạy trên CPU nếu không có CUDA).

### 7.2. Cài đặt Môi trường Cục bộ

1. **Clone repository về máy**:
   ```bash
   git clone https://github.com/dungxoan31-creator/UNet-Vinmec-KhoaLuan.git
   cd UNet-Vinmec-KhoaLuan
   ```

2. **Khởi tạo và kích hoạt môi trường ảo (Virtual Environment)**:
   - **Trên Windows PowerShell**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Trên Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Cài đặt các gói thư viện phụ thuộc**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

### 8.1. Khởi chạy Chuẩn hóa bằng PowerShell Launcher (Khuyến nghị)
Sử dụng script launcher chính thức `scripts/run_prototype.ps1` để tự động kiểm tra tính hợp lệ của trọng số checkpoint, Python virtualenv và cấu hình bảo mật trước khi khởi động:

```powershell
# 1. Thiết lập 4 biến môi trường bảo mật bắt buộc
$env:APP_JWT_SECRET = '<chuoi-bi-mat-ngau-nhien-toi-thieu-32-ky-tu>'
$env:APP_PATIENT_PID_HMAC_SECRET = '<khoa-HMAC-ngau-nhien-rieng-toi-thieu-32-byte-va-can-sao-luu-an-toan>'
$env:APP_ADMIN_PASSWORD = '<mat-khau-admin-rieng>'
$env:APP_DOCTOR_PASSWORD = '<mat-khau-bac-si-rieng>'

# 2. Kiểm tra điều kiện tiên quyết (CheckOnly)
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -CheckOnly

# 3. Khởi chạy thử nghiệm có giám sát trên runtime độc lập
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -RuntimeDir "artifacts/prototype-runtime" -Port 8000
```

Xem hướng dẫn chi tiết về vận hành, sao lưu và phục hồi CSDL tại [docs/evaluation/release_runbook.md](docs/evaluation/release_runbook.md).

* **Giao diện Web Workstation (Bác sĩ)**: Mở trình duyệt và truy cập: `http://127.0.0.1:8000/`
* **Cổng Quản trị Hệ thống (Admin Portal)**: `http://127.0.0.1:8000/admin`
* **Tài liệu API Tương tác (Swagger UI)**: `http://127.0.0.1:8000/docs`
* **Tài liệu API Thay thế (ReDoc)**: `http://127.0.0.1:8000/redoc`

### 8.2. Biến môi trường bổ sung
Ba biến xác thực ở mục 8.1 là bắt buộc khi đăng nhập. Biến chọn mô hình sau đây là tùy chọn:
- `MODEL_SELECTION_MANIFEST`: Đường dẫn đến file manifest lựa chọn mô hình (mặc định: `evaluation/selected_model.json`). Manifest hiện chọn U-Net++/ResNet34; chỉ thay bằng manifest có checkpoint SHA-256 và nguồn đánh giá đã kiểm chứng.

### 8.3. Khởi chạy bằng Docker & Docker Compose
Hệ thống đã cấu hình sẵn container hóa:

```bash
docker-compose up --build
```
Dịch vụ sẽ khởi chạy qua cổng `80` (Nginx Reverse Proxy) và chuyển tiếp tới FastAPI Backend tại cổng `8000`.
Compose cấp checkpoint và artifact đánh giá qua volume chỉ đọc; các thư mục này không được gửi vào Docker build context hoặc đóng gói trong image. Dataset nguồn không được mount mặc định. Gallery mẫu đánh giá sẽ báo HTTP 503 nếu ảnh/mask nguồn chưa được cấp trong môi trường chạy; chỉ cấp nguồn dữ liệu đã được phê duyệt và khử định danh phù hợp.
Môi trường phát triển/huấn luyện dùng `requirements.txt`; image chỉ cài dependency runtime đã khóa cho Linux/Python 3.12 trong `requirements-lock.txt`.

---

## 9. Kiểm thử & Đảm bảo Chất lượng (Testing & QA)

Dự án tích hợp bộ kiểm thử toàn diện bảo đảm tính toàn vẹn của pipeline:

1. **Chạy toàn bộ kiểm thử Unit & Integration Tests (Pytest)**:
   ```powershell
   pytest
   ```
   *(Cấu hình `pyproject.toml` đã tự động nạp `pythonpath = ["."]`, không cần cấu hình biến môi trường thủ công).*

2. **Kiểm tra định dạng và chuẩn mã nguồn (Ruff Linter)**:
   ```powershell
   ruff check .
   ```

3. **Kiểm thử Frontend & Trình duyệt E2E (Node & Playwright)**:
   ```bash
   # Kiểm thử Unit & Module Workstation (59 tests)
   npm test

   # Kiểm thử Workstation Viewer E2E toàn diện
   npm run test:e2e:workstation

   # Kiểm thử luồng thao tác đầy đủ của Bác sĩ (Doctor E2E Flow)
   npm run test:e2e:doctor

   # Kiểm thử Smoke tiền kiểm màn hình tiếp nhận
   npm run test:smoke
   ```
   Toàn bộ kịch bản kiểm thử mô phỏng chính xác tương tác lâm sàng, cơ chế khóa phiên (Case Lease Lock), và kiểm định giao diện tương tác HITL.

4. **Xác minh Toàn diện Bàn giao & Đóng gói Bằng chứng Thực nghiệm (Release Verification Pipeline)**:
   ```powershell
   # Xác minh toàn bộ các cổng kỹ thuật (Git, Checkpoint SHA, Node, Playwright E2E, Pytest isolated, Report build):
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_evaluation_release.ps1 -TestScope full

   # Hoặc kiểm tra nhanh với bộ selected release smoke tests:
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_evaluation_release.ps1 -TestScope selected

   # Hoặc kiểm tra riêng tính sẵn sàng của nguyên mẫu (bỏ qua cổng holdout độc lập đang chờ dữ liệu):
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_evaluation_release.ps1 -PrototypeOnly
   ```
   Toàn bộ bằng chứng bàn giao, ma trận truy vết và biên bản kiểm toán được lưu trữ tại `evaluation/milestone_3_final/report/`.

---

## 10. Danh mục API Chính (Key REST Endpoints)

| Phân hệ | Phương thức | Endpoint | Mô tả chức năng |
|---|---|---|---|
| **Hệ thống** | `GET` | `/api/health` | Kiểm tra tình trạng hoạt động và kết nối database |
| **Quản lý Ca** | `GET` | `/api/cases` | Lấy danh sách các ca khám gần nhất |
| **Quản lý Ca** | `POST` | `/api/cases` | Tạo mới hồ sơ ca khám bệnh nhân |
| **Ảnh & AI** | `POST` | `/api/upload` | Tải ảnh siêu âm lên, kiểm định IQA và lưu trữ |
| **Ảnh & AI** | `POST` | `/api/predict/{image_id}` | Chạy model trong manifest, trả mask/overlay và số đo tham khảo |
| **Human-in-the-Loop**| `POST` | `/api/review` | Lưu mặt nạ đã hiệu chỉnh và review nghiên cứu của bác sĩ |
| **Báo cáo** | `POST` | `/api/generate-report` | Tạm tắt; trả HTTP 501 cho tới khi có workflow phê duyệt tin cậy |
| **Thẩm định** | `GET` | `/api/evaluation/metrics` | Truy vấn các chỉ số phân đoạn thực nghiệm trên tập mẫu |
| **Quản trị** | `GET` | `/api/admin/audit-logs` | Xem nhật ký kiểm toán hành vi lâm sàng |

---

## 11. Hướng dẫn Phát triển & Đóng góp Tiếp theo

Khi tiếp tục mở rộng và phát triển dự án, các nhà phát triển cần tuân thủ các nguyên tắc sau:
1. **Kỷ luật Kiểm soát Mô hình (Model Integrity)**: Khi cập nhật hoặc huấn luyện mô hình mới, bắt buộc phải cập nhật file `evaluation/selected_model.json` đi kèm mã băm SHA-256 hợp lệ; API Backend sẽ từ chối nạp mô hình nếu mã băm không trùng khớp.
2. **Bảo toàn Dữ liệu Gốc**: Thư mục `dataset/` phải luôn được xem là nguồn dữ liệu chỉ đọc (read-only), không ghi đè hoặc can thiệp trực tiếp vào ảnh gốc.
3. **Quy tắc Kiểm thử**: Luôn chạy `pytest` và `ruff check .` để đảm bảo hệ thống đạt trạng thái xanh (Pass) trước khi tạo commit mới.

## Cấu hình gửi OTP đăng ký qua email

Đăng ký bác sĩ công khai cần SMTP hoạt động. Cấu hình các biến môi trường sau trước khi sử dụng:

- `SMTP_HOST`: tên máy chủ SMTP.
- `SMTP_PORT`: cổng SMTP, mặc định `587` và kết nối bằng STARTTLS.
- `SMTP_USERNAME` và `SMTP_PASSWORD`: thông tin xác thực tùy chọn; nếu dùng thì phải cấu hình cả hai.
- `SMTP_FROM`: địa chỉ email gửi.

Với Docker Compose, truyền các biến này vào môi trường chạy ứng dụng. Ứng dụng vẫn khởi động khi chưa có cấu hình SMTP, nhưng đăng ký sẽ báo lỗi cho đến khi gửi email được cấu hình. Tài khoản mới được kích hoạt và đăng nhập ngay sau khi xác minh OTP.
