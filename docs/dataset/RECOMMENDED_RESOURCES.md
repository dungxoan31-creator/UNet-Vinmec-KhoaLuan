# RECOMMENDED RESOURCES & ARCHITECTURAL ROADMAP
## Ovarian Ultrasound AI Decision Support & Clinical Review System
**Author:** Principal Software Architect & Lead Medical AI Scientist  
**Date:** 2026-08-26  
**Target:** Safe, Scalable, Maintainable, Clinically Accurate Medical AI Decision Support

---

## 1. ARCHITECTURAL BASELINE & ASSESSMENT

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CURRENT ARCHITECTURAL POSTURE                      │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ KEY STRENGTHS                        │ KEY WEAKNESSES & RISKS               │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ 1. Lean, decoupled FastAPI + SPA     │ 1. Not a Git repository (No VC)      │
│ 2. Sub-second CPU inference (131ms)  │ 2. No dependency lockfile            │
│ 3. Deterministic CDSS & Clinical KB  │ 3. Mock Authentication (No JWT)      │
│ 4. Comprehensive test suite (27/27)  │ 4. Single-file SQLite (No Alembic)   │
│ 5. IQA filtering & Shannon Entropy   │ 5. Hardcoded pixel spacing (0.1mm)   │
│ 6. Full clinical audit trail logging │ 6. 4/5 Model Adapters are stubs      │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

## 2. RESOURCE CLASSIFICATION MATRIX

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4-TIER RESOURCE CLASSIFICATION                                              │
├─────────────────┬───────────────────────────────────────────────────────────┤
│ MUST HAVE (P0)  │ Git, Lockfile, PyJWT + Passlib, Pydicom 0018,6011 tag,    │
│                 │ MONAI metrics integration.                                │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ SHOULD HAVE(P1) │ Dockerfile + Compose, Alembic, PostgreSQL, UltraSAM /     │
│                 │ DS2Net weights, Structlog + Sentry, GitHub Actions CI.    │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ OPTIONAL (P2)   │ Redis + ARQ queue, Qdrant Hybrid RAG, Playwright E2E,     │
│                 │ ONNX Runtime export.                                      │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ DO NOT NEED(P3) │ Kubernetes, OHIF Viewer, General SAM ViT-H without fine-  │
│                 │ tuning, Triton Inference Server, MedPy (GPL License).     │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

---

## 3. DETAILED RECOMMENDATIONS BY CATEGORY

### 3.1. Recommended Open-Source Repositories

#### 1. [cv516Buaa/MMOTU_DS2Net](https://github.com/cv516Buaa/MMOTU_DS2Net)
* **Purpose:** Dual-Stream Spectral and Spatial Network for multi-modality ovarian tumor segmentation.
* **Why:** Written specifically by the authors of the MMOTU benchmark dataset for OTU_2D and OTU_CEUS.
* **License:** Apache 2.0 (Commercial & academic safe).
* **Repo Health:** Published MICCAI paper, stable PyTorch codebase.
* **Integration Difficulty:** Low (Standard PyTorch module into `backend/models/ds2net.py`).
* **Classification:** **SHOULD HAVE (P1)**.

#### 2. [CAMMA-public/UltraSam](https://github.com/CAMMA-public/UltraSam)
* **Purpose:** Foundation Model for Ultrasound Image Segmentation.
* **Why:** Pre-trained on 280,000+ ultrasound frames across 43 datasets, solving the acoustic speckle boundary problem that natural SAM models fail at.
* **License:** Open Research / Apache 2.0.
* **Repo Health:** Active research lab (MICCAI 2024).
* **Integration Difficulty:** Moderate (Requires SAM ViT backbone + UltraSAM weights).
* **Classification:** **SHOULD HAVE (P1)**.

#### 3. [Project-MONAI/MONAI](https://github.com/Project-MONAI/MONAI)
* **Purpose:** Healthcare Deep Learning Architecture, Transforms, Losses, and Evaluation Metrics.
* **Why:** Standardized medical imaging algorithms, eliminating custom metric approximation bugs.
* **License:** Apache 2.0.
* **Repo Health:** Tier-1 Gold Standard (backed by NVIDIA and Consortium).
* **Integration Difficulty:** Minimal (Already installed in environment: v1.6.0).
* **Classification:** **MUST HAVE (P0)**.

---

### 3.2. Recommended Models & Foundation Backbones

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RECOMMENDED MODEL ZOO                            │
├─────────────────────┬──────────────────┬─────────────────┬──────────────────┤
│ Model Architecture  │ Primary Task     │ Pretrained On   │ Deployment Role  │
├─────────────────────┼──────────────────┼─────────────────┼──────────────────┤
│ Attention U-Net     │ 2D Segmentation  │ OTU-2D Dataset  │ Primary Active   │
│ DS²Net Dual-Stream  │ Multi-Modality   │ OTU-2D + CEUS   │ Specialized US   │
│ UltraSAM (ViT-B)    │ Promptable Click │ 43 US Datasets  │ HITL Interactive │
│ RadImageNet ResNet50│ O-RADS Feature   │ 1.35M Radiology │ Feature Backbone │
└─────────────────────┴──────────────────┴─────────────────┴──────────────────┘
```

---

### 3.3. Recommended Datasets (External Validation)

To prove model generalizability and avoid single-institution overfitting, the following external validation datasets are recommended:

1. **IOTA-5 Multicenter Benchmark Cohort:**
   * Modality: 2D Transvaginal Ultrasound (TVUS) of adnexal masses.
   * Ground Truth: Histopathology confirmed following surgical resection.
   * Value: Gold standard international benchmark across 17 European centers.
2. **Kaggle / Figshare MMOTU Independent Test Partition (382 cases):**
   * Currently partitioned in `ai_training/splits/test.csv`.
   * Evaluated: Mean DSC $0.7615$, Mean IoU $0.6560$, $HD_{95} = 3.50\text{ mm}$.
3. **Vinmec Multicenter Clinical Test Cohort (In-hospital validation):**
   * Multi-vendor scans (GE Voluson E10, Mindray Resona 7, Philips Epiq Elite).
   * Verified by Senior Radiologists.

---

### 3.4. Recommended Tools & Services

| Tool | Category | License | Why We Need It | Alternative Evaluated & Rejected |
|---|---|---|---|---|
| **Pydicom** (Installed: 3.0.2) | Medical Imaging | MIT | Parse ultrasound calibration tags (`0018,6011` PhysicalDeltaX/Y) to replace hardcoded 0.1 mm/px. | SimpleITK (Heavier for simple 2D tag extraction) |
| **Passlib + PyJWT** | Security | BSD / MIT | Cryptographic JWT token auth, bcrypt password hashing for DOCTOR and ADMIN roles. | Custom session in-memory dict (Vulnerable to spoofing) |
| **Alembic** | Database | MIT | Schema migration management for SQLAlchemy (auto-generate DB migration scripts). | Manual `PRAGMA table_info` scripts (Brittle, unversioned) |
| **Loguru / Structlog** | Observability | MIT / Apache 2.0 | Structured JSON logging with request IDs, inference timings, and error traceback. | Standard `print()` statements (No log rotation, hard to parse) |
| **Playwright** | QA Testing | Apache 2.0 | Automated end-to-end browser testing for Canvas drawing, brush editing, and slider interactions. | Selenium (Slower, heavier) |
| **Docker & Docker Compose** | DevOps | Apache 2.0 | Standardized container packaging with Nginx reverse proxy and Gunicorn/Uvicorn workers. | Bare-metal execution (Environment divergence risk) |

---

## 4. RISK AUDIT & MITIGATION

### 4.1. License Risks
* **GPL / AGPL Avoidance:** Do NOT incorporate GPL-licensed libraries (e.g. MedPy GPL-3.0) into proprietary or closed-source hospital deployments if distribution is required. Use Apache 2.0 (MONAI, OpenCV, PyTorch) and MIT (Pydicom, FastAPI, Pydantic) libraries.
* **Pretrained Weights Licenses:** Verify academic vs commercial clauses for foundation models. UltraSAM and SAM-Med2D are Apache 2.0.

### 4.2. Medical AI Clinical Safety Risks
* **Risk 1: Hardcoded Physical Spacing (0.1 mm/px).**
  * *Clinical Consequence:* If a doctor uploads a zoomed scan with $0.05\text{ mm/px}$, AI will report a $20\text{mm}$ cyst as $40\text{mm}$, leading to unnecessary surgical intervention.
  * *Mitigation:* Read DICOM sequence `(0018,6011)` or enforce mandatory doctor verification of ultrasound depth ruler scale.
* **Risk 2: Edge-Case Acoustic Shadowing.**
  * *Clinical Consequence:* Rokitansky nodule in dermoid cyst creates an acoustic shadow, causing under-segmentation of the cyst floor.
  * *Mitigation:* Shannon entropy uncertainty alert triggers automatic "High Uncertainty" flag on dermoid scans, prompting manual caliper inspection.

### 4.3. Security Risks
* **Risk 1: Role Spoofing.** `/api/auth/switch-role` currently allows arbitrary role escalation without password.
  * *Mitigation:* Implement standard OAuth2 JWT token bearer headers.
* **Risk 2: Unrestricted CORS.** `allow_origins=["*"]` allows any web origin to interact with the backend API.
  * *Mitigation:* Restrict CORS to configured hospital domain origins in `backend/app/config.py`.

---

## 5. STEP-BY-STEP IMPLEMENTATION & INSTALLATION ROADMAP

### Phase 1: Immediate Stabilization & Governance (P0 - Days 1–3)
1. **Initialize Git Repository & `.gitignore`:**
   ```powershell
   git init
   git add .
   git commit -m "feat(core): initialize ovarian ultrasound AI decision support repository"
   ```
2. **Generate Formal Dependencies File (`requirements.txt` / `pyproject.toml`):**
   * Pin exact compatible versions for PyTorch, FastAPI, MONAI, Pydicom, OpenCV, ReportLab, Pydantic, SQLAlchemy.
3. **Secure Authentication & Session Middleware:**
   * Implement `passlib[bcrypt]` + `PyJWT` in `backend/app/routers/auth.py`.
   * Add `get_current_user` dependency to protect `/api/admin/*` and `/api/review`.
4. **Implement DICOM Calibration Tag Parser:**
   * Update `backend/app/routers/inference.py` to extract `PhysicalDeltaX` and `PhysicalDeltaY` from `.dcm` files when present.

### Phase 2: Architecture & Deployment Hardening (P1 - Days 4–7)
5. **Containerization:**
   * Create `Dockerfile` (Multi-stage Python 3.12-slim build) and `docker-compose.yml` (FastAPI app + PostgreSQL + Nginx).
6. **Database Migration Pipeline:**
   * Initialize Alembic (`alembic init backend/db/migrations`) to track database schema revisions.
7. **Model Registry Activation:**
   * Integrate real `DS2Net` and `UltraSAM` weights into `backend/services/model_service.py` to replace empty stub methods.
8. **Structured Observability:**
   * Replace `print()` with structured JSON logger (`loguru`) and configure Sentry error telemetry.
9. **CI/CD Automation:**
   * Add `.github/workflows/ci.yml` to automatically run `ruff check` and `python -m unittest discover -s tests` on every push.

### Phase 3: Advanced Capabilities & Evaluation (P2 - Days 8–14)
10. **ONNX Runtime Acceleration:**
    * Export `best_attention_unet.pth` to `model.onnx` and integrate ONNX Runtime CPU/CUDA Execution Provider to reduce inference latency to $<85\text{ms}$.
11. **Semantic Literature RAG Integration:**
    * Connect installed `qdrant-client` to index full-text PDF guideline papers for conversational guideline search.
12. **Playwright E2E UI Test Suite:**
    * Write automated browser tests verifying canvas brush, eraser, zoom, and caliper recalculation.

---

## 6. SELF-AUDIT & PRUNING OF OVER-ENGINEERING

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OVER-ENGINEERING PRUNING LOG                          │
├─────────────────────────┬──────────────────┬────────────────────────────────┤
│ Candidate Component     │ Initial Idea     │ Final Pruned Verdict           │
├─────────────────────────┼──────────────────┼────────────────────────────────┤
│ Kubernetes (K8s)        │ Deploy to K8s    │ PRUNED: Overkill for single-   │
│                         │ cluster          │ hospital deployment. Compose OK│
├─────────────────────────┼──────────────────┼────────────────────────────────┤
│ Triton Inference Server │ Standalone Model │ PRUNED: In-process PyTorch /   │
│                         │ Server           │ ONNX Runtime is faster & simpler│
├─────────────────────────┼──────────────────┼────────────────────────────────┤
│ OHIF Medical Viewer     │ Replace SPA      │ PRUNED: High complexity. Custom│
│                         │ with OHIF        │ Canvas SPA is tailored for 2D. │
├─────────────────────────┼──────────────────┼────────────────────────────────┤
│ Large LLM Fine-Tuning   │ Fine-tune Llama3 │ PRUNED: Deterministic CDSS     │
│                         │ for reports      │ engine guarantees 0% hallucina-│
│                         │                  │ tion on medical parameters.    │
└─────────────────────────┴──────────────────┴────────────────────────────────┘
```
