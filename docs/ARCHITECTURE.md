# ARCHITECTURE OVERVIEW & SPECIFICATION
## Ovarian Ultrasound AI Decision Support & HITL Clinical Review System

---

## 1. System Overview & Core Objectives

The **Ovarian Ultrasound AI System** is a production-grade, human-in-the-loop (HITL) clinical decision support platform for gynecological ultrasound analysis. The system combines:
1. **Automated Deep Learning Inference**: Deep supervision segmentation using an Attention U-Net neural network architecture.
2. **Automated Quality & Modality Verification (IQA)**: Pre-inference screening against blur, saturation, non-ultrasound modalities, and contrast degradation.
3. **Automated Caliper & Geometric Extraction**: Bounding rotated calipers ($D_{max}$, $D_{orth}$), orthogonal third-axis estimation ($D_3$), lesion surface area, and ellipsoidal volume calculations.
4. **Human-in-the-Loop Doctor Sign-Off**: Interactive canvas workstation allowing radiologists and gynecologists to accept raw AI results, manually edit segmentation contours, or record discrepancy notes.
5. **Standardized Clinical Reporting**: Automated generation of official Vinmec Hospital PDF reports with 1:1 A4 scaling, QR codes, and institutional branding.
6. **Regulatory & Telemetry Governance**: Complete audit trails, model registry versioning, doctor productivity analytics, and ground truth dataset export for continuous model retraining.

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
Khóa luận/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # Entry point: CORS, router registration, static mounts
│   │   ├── config.py                # File paths, singletons, baseline statistics
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py            # Healthcheck & live dashboard telemetry
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
│   │   ├── attention_unet.py        # PyTorch Attention U-Net network architecture
│   │   ├── losses.py                # ComboLoss, DiceLoss, FocalLoss
│   │   └── metrics.py               # Dice, IoU, HD95 calculations
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py               # Pydantic schemas for request/response serialization
│   └── services/
│       ├── __init__.py
│       ├── preprocessor.py          # Ultrasound preprocessing, aspect preserving resize, IQA
│       ├── inference_engine.py      # Neural inference, RLE masks, caliper extraction
│       ├── model_service.py         # Model lifecycle, adapter registry & telemetry
│       └── report_generator.py      # Standardized ReportLab medical PDF generator
│
├── frontend/
│   ├── index.html                   # Clean, semantic SPA HTML layout
│   ├── vinmec_logo.svg              # Vinmec official vector logo
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
│   ├── CLEANUP_REPORT.md            # Refactoring, modularization and cleanup report
│   ├── CLEANUP_CANDIDATES.md        # File deletion/keep audit rationale
│   ├── TECHNICAL_DEBT.md            # Documented technical debt and future considerations
│   ├── ovarian-ultrasound-ai/       # Product and SRS specifications
│   └── thesis_proposal/             # Thesis proposal documents and document generator
│
├── ai_training/                     # Training experiments, splits, evaluations, previews
├── checkpoints/                     # Model weights (best_attention_unet.pth)
├── scripts/                         # Operational training, evaluation & preprocessing scripts
├── tests/                           # Unit, pipeline & E2E clinical workflow test suite
├── data/                            # Uploads, reports, sample cases & runtime data
├── pyproject.toml                   # Project metadata & Ruff linter configuration
├── MODEL_CARD.md                    # AI Model Card (Attention U-Net v1.2)
└── ovarian_ai.db                    # Production SQLite Database
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
