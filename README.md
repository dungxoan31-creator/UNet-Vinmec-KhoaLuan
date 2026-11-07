---
title: Ovarian Ultrasound RUO Research Workstation
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# Ovarian Ultrasound RUO Research Workstation
> **Hệ thống nghiên cứu phân đoạn siêu âm buồng trứng Human-in-the-Loop**
> Dự án Khóa luận Tốt nghiệp Hệ thống Thông tin Quản lý (MIS / ITBA / AI) – Trường Đại học Kinh tế Quốc dân (NEU).  
> Dữ liệu được kiểm tra cho model được chọn trong workspace này là MMOTU 2D ở mức ảnh; workspace không có ảnh/mặt nạ Vinmec và không báo cáo hiệu năng trên dữ liệu Vinmec. Repository chưa có tài liệu xác nhận tài trợ, ủy quyền hoặc endorsement của Vinmec; tên repository và lịch sử dự án không chứng minh liên kết chính thức.

> **Trạng thái bằng chứng:** RUO research prototype. Xem manifest `evaluation/selected_model.json` và [Model Card](MODEL_CARD.md) để biết ứng viên đang chọn, cấu hình và chỉ số validation image-level; đây không phải kết quả test độc lập hay bằng chứng hiệu quả lâm sàng. Tính độc lập theo bệnh nhân chưa được xác minh; cổng đánh giá độc lập đang BLOCKED và chưa có clinician validation. Xem [release runbook](docs/evaluation/release_runbook.md) để biết phạm vi kiểm thử được phép và các cổng Go-live.

> **Giới hạn triển khai:** Cơ sở dữ liệu hiện tại là SQLite; PostgreSQL chưa được triển khai/kiểm thử. DICOM chỉ hỗ trợ ảnh siêu âm 2D một frame với tập định dạng pixel giới hạn; cine và nhiều ảnh xám 12/16-bit chưa được hỗ trợ. CDSS đối chiếu một tập quy tắc nghiên cứu, không bao phủ toàn bộ O-RADS; trường hợp ngoài phạm vi phải để bác sĩ đánh giá. Policy nang noãn của dự án dùng `<30 mm`, khác ngưỡng `≤30 mm` trong ACR. Kích thước từ mask là proxy 2D và số vùng Watershed chưa được xác nhận là số nang toàn buồng trứng.

> **Giới hạn suy luận:** Một tiến trình ứng dụng mặc định cho phép một tác vụ suy luận chạy và hai tác vụ chờ tối đa 10 giây; vượt giới hạn trả HTTP 503. Các biến `APP_INFERENCE_MAX_RUNNING`, `APP_INFERENCE_MAX_WAITING`, `APP_INFERENCE_WAIT_SECONDS` cấu hình giới hạn. Đây là giới hạn **trong từng tiến trình**, không điều phối giữa các worker; cấu hình nhiều worker dùng cùng GPU chưa được bảo vệ và chưa được kiểm thử. Dùng một worker cho cấu hình GPU hiện tại.

---

## 1. Giới thiệu Tổng quan & Bài toán Giải quyết

### 1.1. Bối cảnh & Thách thức Y tế
Chẩn đoán hình ảnh siêu âm buồng trứng (phát hiện nang, u nang, khối u đặc/hỗn hợp) là kỹ thuật phổ biến nhưng phụ thuộc lớn vào kinh nghiệm chủ quan của bác sĩ chuyên khoa. Các tổn thương buồng trứng thường có ranh giới phức tạp, độ tương phản mô mềm thấp, nhiễu âm (speckle noise) và biến dạng giải phẫu lớn giữa các bệnh nhân.

### 1.2. Giải pháp của Dự án
Dự án xây dựng bản mẫu phần mềm hỗ trợ ra quyết định lâm sàng (**Clinical Decision Support System - CDSS**), kết hợp mô hình học sâu phân đoạn ảnh y tế và giao diện máy trạm lâm sàng (Clinical Workstation):
- **Phân đoạn tự động bằng Deep Learning**: Model registry hiện chọn ứng viên nghiên cứu U-Net++/ResNet34; Standard U-Net được giữ làm baseline. Mask chỉ là kết quả phân đoạn, không xác định bệnh lý.
- **Đo hình học tham khảo**: Proxy hộp bao 2D cho $d_1, d_2$, chu vi và diện tích; không suy ra thể tích 3D. Số đo vật lý cần hiệu chuẩn và bác sĩ xác nhận.
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
| **Artifact container**| Dockerfile, Docker Compose, Nginx | - | Có cấu hình trong repository; build image, runtime và triển khai chưa được xác minh |

---

## 5. Cấu trúc Thư mục Dự án (Final Clean Architecture)

`	ext
UNet-Vinmec-KhoaLuan/
├── backend/                 # Máy chủ dịch vụ FastAPI Backend
│   ├── app/                 # Điểm khởi chạy API (main.py), định tuyến routers/, cấu hình (config.py)
│   ├── core/                # Xử lý hình ảnh cấp thấp, phân tích danh tính an toàn (image_utils.py)
│   ├── db/                  # Khởi tạo cơ sở dữ liệu SQLAlchemy (database.py)
│   ├── models/              # Kiến trúc mạng nơ-ron (unet.py, attention_unet.py, losses.py)
│   ├── schemas/             # Pydantic Schemas kiểm thực dữ liệu đầu vào/ra
│   └── services/            # Dịch vụ nghiệp vụ: InferenceEngine, Preprocessor, CDSS, MorphologyExtractor
├── frontend/                # Giao diện Web Workstation dành cho bác sĩ
│   ├── app/                 # Logic giao diện ứng dụng (viewer.js, cases.js, navigation.js, etc.)
│   ├── assets/              # Tài nguyên đồ họa, font chữ Inter và logo Vinmec
│   ├── css/                 # Giao diện Dark Mode tối ưu cho phòng đọc ảnh siêu âm
│   ├── js/                  # Thư viện client API
│   └── index.html           # Trang giao diện chính của hệ thống
├── ai_training/             # Pipeline huấn luyện mô hình PyTorch
│   ├── dataset_loader.py    # Dataloader ảnh siêu âm kèm Letterbox & CLAHE
│   ├── loss.py              # Combo Loss (Dice + BCE), Focal Tversky, Advanced Hybrid Loss
│   ├── metrics_clinical.py  # Bộ đo phân đoạn ở mức pixel (Dice, IoU, Recall, Specificity)
│   ├── splits/              # Cấu hình phân chia tập dữ liệu huấn luyện, thẩm định và kiểm thử
│   └── train_unetplusplus_resnet34.py # Huấn luyện mô hình U-Net++ ResNet34
├── dataset/                 # Thư mục dữ liệu ảnh gốc (Chỉ đọc - Read Only)
│   ├── 2d/                  # Ảnh siêu âm 2D B-mode (images/ và masks/)
│   ├── 3d/                  # Ảnh siêu âm đa lát cắt 2D
│   ├── index.csv            # Chỉ mục mẫu đủ điều kiện theo manifest split
│   └── external_manifest_mmotu.json # Khai báo định danh tập dữ liệu nghiên cứu
├── checkpoints/             # Trọng số mô hình đã thẩm định mã băm SHA-256 (.pth)
│   ├── unetplusplus_resnet34_2026-10-06/ # Checkpoint U-Net++ sản xuất (Được manifest chọn)
│   ├── unified_vinmec_refine_2026-10-06/ # Checkpoint Standard U-Net baseline đối chuẩn
│   ├── mmotu_8class_accuracy_search_2026-10-27/ # Model phân loại bệnh học nghiên cứu (trial_02)
│   └── boosted_unetplusplus_scse_2026-10-27/    # Model nghiên cứu U-Net++ scSE
├── evaluation/              # Minh chứng kiểm thử kỹ thuật và metric phân đoạn
│   ├── selected_model.json  # Manifest chỉ định mô hình phục vụ với mã băm SHA-256
│   └── protocols/           # Giao thức đánh giá chuẩn hóa
├── docs/                    # Tài liệu học thuật & kỹ thuật
│   ├── thesis/              # Tài liệu Khóa luận Tốt nghiệp & phụ lục
│   │   └── report/          # Toàn văn Khóa luận (PDF, DOCX, MD, mẫu phiếu kết quả siêu âm)
│   ├── architecture/        # Thiết kế kiến trúc hệ thống
│   ├── clinical_validation/ # Ma trận luật tất định O-RADS v2022 & IOTA Simple Rules
│   └── deployment/          # Hướng dẫn triển khai, vận hành & bảo mật
├── data/                    # Thư mục runtime & demo workspace
│   └── demo_workspace/      # Không gian demo độc lập, an toàn với synthetic data
├── scripts/                 # Bộ công cụ xử lý dữ liệu, kiểm toán và khởi chạy demo
│   ├── run_demo_workspace.ps1   # Khởi chạy bản demo hoàn chỉnh với dữ liệu synthetic
│   ├── seed_demo_workspace.py   # Tự động khởi tạo CSDL và tài khoản demo an toàn
│   └── run_all_verifications.py # Kịch bản xác minh toàn diện hệ thống
├── tests/                   # Bộ kiểm thử tự động (Unit / Integration / E2E)
├── Dockerfile               # File container hóa ứng dụng
├── docker-compose.yml       # Cấu hình container đa dịch vụ
├── MODEL_CARD.md            # Báo cáo kỹ thuật mô hình (Model Card)
├── pyproject.toml           # Cấu hình Pytest và Ruff linter
├── requirements.txt         # Khai báo phụ thuộc Python
├── requirements-lock.txt    # Khóa phiên bản phụ thuộc chính xác (Python 3.12)
├── .gitignore               # Cấu hình loại trừ tệp tự sinh
└── README.md                # Tài liệu hướng dẫn sử dụng & vận hành
`

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

## 8. Hướng dẫn Khởi chạy Hệ thống & Bản Demo

### 8.1. Khởi chạy Demo Workspace Hoàn chỉnh (Khuyến nghị cho Hội đồng & Giám khảo)

Để trình diễn toàn bộ quy trình làm việc lâm sàng Human-in-the-Loop trên giao diện Web Workstation thực tế:

`powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_demo_workspace.ps1
`

**Đặc điểm không gian Demo:**
- **Dữ liệu an toàn tuyệt đối**: Sử dụng 100% dữ liệu ảnh siêu âm tổng hợp (synthetic-only allowlist); không lưu trữ hay xử lý bất kỳ hồ sơ bệnh nhân thật nào.
- **Tự động khởi tạo**: Tự động sinh CSDL cô lập tại data/demo_workspace/ovarian_ai.db, nạp 80 ca khám mẫu, 4 cơ sở y tế và 40 tài khoản bác sĩ.
- **Bảo mật**: Tự động sinh khóa HMAC và JWT cục bộ (.patient_pid_hmac_secret, .app_jwt_secret).
- **Địa chỉ truy cập**: Mở trình duyệt web tại http://127.0.0.1:8000 (hoặc http://127.0.0.1:8000/index.html).
- **Tài khoản đăng nhập có sẵn**:
  - **Quản trị viên (Admin)**: demo.admin / Mật khẩu: DemoAdmin@2026!
  - **Bác sĩ (Doctor)**: nhpm (hoặc inhvt, cuongdq) / Mật khẩu: 123456@

### 8.2. Khởi chạy Backend Thủ công

Nếu muốn chạy máy chủ Backend độc lập với cấu hình tùy chỉnh:

`powershell
# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# Khởi chạy FastAPI qua Uvicorn
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
`

- Kiểm tra API Docs (Swagger UI): http://127.0.0.1:8000/docs
- Kiểm tra trạng thái hệ thống: http://127.0.0.1:8000/api/v1/health

### 8.3. Bài kiểm thử E2E Scripted

`powershell
npm run test:e2e:roundtrip
`

Harness tự khởi chạy backend cô lập trên loopback, SQLite runtime tạm, fixture tổng hợp đã allowlist và trình duyệt headless; test kiểm tra cờ RUO/synthetic-only và dọn runtime sau khi tiến trình dừng.

### 8.4. Cấu hình Docker & Container hóa

Repository cung cấp Dockerfile và docker-compose.yml phục vụ đóng gói và triển khai containerized:

`ash
docker compose up --build
`

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
