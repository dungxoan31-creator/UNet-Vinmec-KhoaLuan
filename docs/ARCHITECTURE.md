# ARCHITECTURE OVERVIEW & SPECIFICATION
## Ovarian Ultrasound AI Decision Support & HITL Clinical Review System
> **Dự án**: Khóa luận Tốt nghiệp — Trường Công nghệ & Kinh tế số, Đại học Kinh tế Quốc dân (NEU)  
> **Đề tài**: *“Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”*  
> **Sinh viên**: Nguyễn Hữu Dũng — MSV: 11235559 — Lớp: HTTTQL 65A  
> **Cán bộ hướng dẫn**: ThS. Trần Thanh Hải  
> **Bối cảnh & Dữ liệu lâm sàng**: Bệnh viện Đa khoa Quốc tế Vinmec Times City  
> **Bản chất phần mềm**: Bản mẫu nghiên cứu thực nghiệm (Academic Research Prototype)

---

## 1. System Overview & Core Objectives

Hệ thống **Ovarian Ultrasound AI System** là một bản mẫu nghiên cứu thực nghiệm (Research/Experimental Prototype) được phát triển trong khuôn khổ Khóa luận Tốt nghiệp. Toàn bộ bối cảnh nghiệp vụ, quy trình lâm sàng, bộ dữ liệu siêu âm, nhãn chú thích và mặt nạ Ground Truth được thu thập và thẩm định từ **Bệnh viện Đa khoa Quốc tế Vinmec Times City**. 

Hệ thống hoạt động như một công cụ **hỗ trợ phân đoạn tổn thương và đo đạc kích thước u buồng trứng theo mô hình Human-in-the-Loop (HITL)**, tuyệt đối không tự động chẩn đoán bệnh thay bác sĩ.

Hệ thống bao gồm 6 trụ cột kỹ thuật:
1. **Automated Deep Learning Segmentation**: Kiến trúc mô hình đường cơ sở bắt buộc (**Standard U-Net**, `checkpoints/baseline_unet_best.pth`) và mô hình so sánh thực nghiệm (**Attention U-Net**, `checkpoints/best_attention_unet.pth`).
2. **Automated Quality & Modality Verification (IQA)**: Tiền kiểm định chất lượng 4 lớp trước suy luận (chống mờ, lệch tương phản, bão hòa màu, sai dạng siêu âm B-mode).
3. **Automated Caliper & Geometric Extraction**: Tự động ước lượng hộp bao xoay, trích xuất cặp đường kính trực giao ($D_{max}, D_{orth}$), diện tích bề mặt ($\text{mm}^2$) và thể tích elip khối ($V$).
4. **Human-in-the-Loop Doctor Review & Interactive Editing**: Giao diện Dual-Layer Canvas cho phép bác sĩ rà soát, dùng cọ vẽ/tẩy xóa hiệu chỉnh bờ viền tổn thương trước khi ký duyệt (`ACCEPTED_RAW`, `MODIFIED`).
5. **Standardized Clinical Reporting**: Tự động kết xuất phiếu kết quả siêu âm định dạng A4 chuẩn Vinmec Hospital với tỷ lệ 1:1, mã QR tra cứu và thông tin cơ sở.
6. **Regulatory Governance & Traceability**: Lưu vết kiểm toán (Audit Trail) bất biến, bảo toàn dữ liệu Ground Truth sau hiệu chỉnh để phục vụ tái huấn luyện và đánh giá mô hình.

---

## 2. Architectural Layers

The codebase is organized into clean, decoupled layers following Separation of Concerns and Domain-Driven design:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER (UI)                         │
│   Single Page Application (SPA) - Modular Vanilla JS + CSS Tokens      │
│   ├── Screens: Dashboard, HITL Workspace, Case History, Admin Portal  │
│   ├── Viewports: Medical Canvas, Zoom/Pan Engine, Caliper Tools        │
│   └── Stylesheets: Theme Tokens, Layout, Components, Viewer, Admin     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST API (JSON & Multipart)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        APPLICATION LAYER (FASTAPI)                     │
│   backend/app/                                                         │
│   ├── main.py       : Lean app initialization, CORS, static mounts     │
│   ├── config.py     : Environment config, file storage paths, singletons│
│   └── routers/                                                         │
│       ├── health.py    : /api/health, /api/stats (Live Telemetry)      │
│       ├── cases.py     : /api/cases (CRUD), /api/samples               │
│       ├── inference.py : /api/upload, /api/validate-image, /api/predict│
│       ├── reviews.py   : /api/review, /api/generate-report             │
│       ├── auth.py      : /api/auth/users, /api/auth/switch-role        │
│       └── admin.py     : /api/admin/models, /api/admin/audit-logs      │
└───────────────────┬──────────────────────────────────┬─────────────────┘
                    │                                  │
┌───────────────────▼──────────────────┐  ┌────────────▼─────────────────┐
│           SERVICES LAYER             │  │         PERSISTENCE          │
│   backend/services/                  │  │   backend/db/                │
│   ├── preprocessor.py                │  │   ├── database.py            │
│   │   └── IQA & Letterbox Resizing   │  │   └── SQLAlchemy SQLite DB   │
│   ├── inference_engine.py            │  │       ├── PatientModel       │
│   │   └── Attention U-Net & Calipers │  │       ├── StudyModel         │
│   ├── model_service.py               │  │       ├── ImageModel         │
│   │   └── Model Registry & Adapters  │  │       ├── PredictionModel    │
│   └── report_generator.py            │  │       ├── ReviewModel        │
│       └── ReportLab PDF Generator    │  │       ├── AuditLogModel      │
└───────────────────┬──────────────────┘  │       └── UserModel          │
                    │                     └──────────────────────────────┘
┌───────────────────▼──────────────────┐
│             CORE & MODELS            │
│   backend/core/image_utils.py        │
│   backend/models/attention_unet.py   │
│   backend/models/losses.py           │
│   backend/models/metrics.py          │
│   backend/schemas/schemas.py         │
└──────────────────────────────────────┘
```

---

## 3. Directory Layout & Module Responsibilities

```text
├── dataset/
│   └── vinmec_ovarian/              # Niêm phong dữ liệu siêu âm buồng trứng Vinmec Times City
│       ├── vinmec_dataset_manifest.json # Manifest niêm phong 5 số liệu (1.387 ảnh, 307 GT, 185 BN)
│       ├── OTU_2D/                  # Siêu âm 2D B-mode (train, test)
│       └── OTU_CEUS/                # Siêu âm tương phản cản âm (CEUS test)
│
├── knowledge/                       # Cơ sở tri thức lâm sàng siêu âm buồng trứng (IOTA, O-RADS)
│   ├── ovarian_ultrasound_knowledge_base.md
│   └── ovarian_ultrasound_sources.csv
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # Entry point: CORS, router registration, static mounts
│   │   ├── config.py                # File paths, singletons, baseline statistics (Vinmec context)
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py            # Healthcheck & live dashboard telemetry (Research prototype info)
│   │       ├── cases.py             # Clinical studies & sample cases CRUD
│   │       ├── inference.py         # Image upload, IQA quality filter & model inference
│   │       ├── reviews.py           # Doctor sign-off & PDF report generation
│   │       ├── auth.py              # User profiles & RBAC role switching
│   │       └── admin.py             # Model governance, audit logs & dataset export
│   ├── core/
│   │   ├── __init__.py
│   │   └── image_utils.py           # Unicode-safe image read/write helpers (Windows safe)
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py              # SQLite ORM models, session providers & auto-seeding
│   ├── models/
│   │   ├── __init__.py
│   │   ├── unet.py                  # Standard U-Net architecture (Compulsory Baseline)
│   │   ├── attention_unet.py        # PyTorch Attention U-Net network architecture (Comparative)
│   │   ├── losses.py                # ComboLoss, DiceLoss, FocalLoss
│   │   └── metrics.py               # Dice, IoU, HD95 calculations
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic schemas for request/response serialization
│   └── services/
│       ├── __init__.py
│       ├── preprocessor.py          # Ultrasound preprocessing, aspect preserving resize, IQA
│       ├── inference_engine.py      # Dual-model neural inference (Baseline + Attention), calipers
│       ├── model_service.py         # Model lifecycle, adapter registry & telemetry
│       └── report_generator.py      # Standardized ReportLab medical PDF generator
│
├── frontend/
│   ├── index.html                   # Clean, semantic SPA HTML layout (Vinmec Prototype branding)
│   ├── vinmec_logo.svg              # Vinmec vector logo
│   ├── css/
│   │   ├── main.css                 # Master stylesheet aggregator
│   │   ├── theme.css                # Design system tokens, CSS variables, typography
│   │   ├── layout.css               # Header, ribbon, sidebar, containers, footer
│   │   ├── components.css           # Cards, buttons, tables, stepper, modals, toasts
│   │   ├── viewer.css               # HITL workstation canvas, calipers, tools
│   │   ├── admin.css                # Admin portal layout, metrics grid, audit tables
│   │   └── report.css               # Printable A4 physical medical report styles
│   └── js/
│       ├── app.js                   # Application bootstrap & lifecycle orchestrator
│       ├── config.js                # System constants, macro templates, ORADS mappings
│       ├── state.js                 # Central reactive application state
│       ├── api.js                   # Unified async Fetch API client
│       └── modules/
│           ├── auth.js              # User profiles, role switching modal handlers
│           ├── navigation.js        # Screen router, quick search, mobile drawer, shortcuts
│           ├── cases.js             # Case tables, search, filters, case details
│           ├── upload.js            # Image dropzone, file validation & IQA trigger
│           ├── viewer.js            # Canvas rendering, zoom/pan, calipers & mask painting
│           ├── review.js            # Doctor sign-off, draft management, PDF report preview
│           └── admin.js             # Admin tabs, model registry, audit logs, dataset export
│
├── templates/
│   └── medical_report/
│       └── vinmec_diagnosis_template.html  # Standardized clinical report HTML template
│
├── docs/
│   ├── ARCHITECTURE.md              # System architecture and design specification
│   ├── CLINICAL_VALIDATION_STANDARDS.md # Clinical validation & HITL safety standards
│   ├── KLTN_THESIS_EXECUTION_PLAN.md    # 4-milestone thesis execution plan
│   ├── ke_hoach_trien_khai_moc_1.md # Kế hoạch triển khai chi tiết Mốc 1
│   ├── dataset/                     # Báo cáo kiểm kê và đề xuất nguồn dữ liệu
│   │   ├── KLTN_DE_CUONG_DATASET_SPLITS.md
│   │   └── dataset_recommendation.md
│   ├── ovarian-ultrasound-ai/       # Product and SRS specifications
│   ├── reports/                     # Báo cáo tiến độ (Word .docx và Markdown)
│   └── thesis_proposal/             # Đề cương và đề xuất khóa luận (Word .docx)
│
├── ai_training/                     # Training experiments, splits (Patient-level), previews
├── checkpoints/
│   ├── baseline_unet_best.pth       # Standard U-Net weights (31.1 MB - Compulsory Baseline)
│   └── best_attention_unet.pth      # Attention U-Net weights (31.5 MB - Comparative Model)
├── scripts/                         # Operational training, evaluation & preprocessing scripts
├── tests/                           # 87 automated tests (Unit, pipeline & E2E clinical workflow)
├── data/                            # Uploads, reports, sample cases & runtime data
├── pyproject.toml                   # Project metadata & Ruff linter configuration
├── MODEL_CARD.md                    # AI Model Card (Baseline U-Net + Attention U-Net)
└── ovarian_ai.db                    # SQLite Database
```

---

## 4. Architectural Invariants & Rules

1. **Layer Separation**: UI components must never make direct database queries or load PyTorch weights. All backend interaction happens via REST API endpoints.
2. **Unicode Path Safety**: All file I/O operations involving file paths on Windows must use `cv2_imread_unicode` and `cv2_imwrite_unicode` from `backend.core.image_utils`.
3. **Non-Destructive Doctor Override**: Doctor review decisions (`ACCEPTED_RAW`, `MODIFIED`, `REJECTED`) never overwrite raw model predictions; they append a verified `ReviewModel` and create an immutable `AuditLogModel` entry.
4. **Data Isolation**: Datasets, uploaded media, and generated reports reside in `data/`, separated from source code.
5. **Code Style & Formatting**: All Python code conforms to PEP 8 standards enforced via `ruff` with line length 120.

---

## 5. Verification Matrix

| Component | Verification Method | Status |
|---|---|---|
| **API Endpoints (21 Routes)** | `tests/test_api.py` via FastAPI TestClient | PASS (100%) |
| **Model & Metric Pipeline** | `tests/test_pipeline.py` (ComboLoss, Dice, IoU, Calipers) | PASS (100%) |
| **End-to-End User Flow** | `tests/test_user_flow_e2e.py` (10 clinical workflow steps) | PASS (100%) |
| **Static Frontend Delivery** | `scratch/verify_frontend_assets.py` (21 static files) | PASS (100%) |
| **Code Quality & Linting** | `ruff check backend/ tests/ scripts/` | PASS (0 errors) |
