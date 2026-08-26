# TECHNICAL DEBT & FUTURE ARCHITECTURAL ROADMAP
## Ovarian Ultrasound AI Decision Support System

This document catalogs technical debt items and proposed engineering enhancements identified during the codebase audit. These items represent future optimizations that fall outside the scope of non-breaking refactoring and code cleanup.

---

## 1. Identified Technical Debt Items

### TD-001: Database Concurrency & Engine Migration (SQLite to PostgreSQL)
- **Current State**: Uses SQLite (`ovarian_ai.db`) with SQLAlchemy synchronous sessions.
- **Impact**: Suitable for single-clinic deployment and local testing. Under high concurrent write loads (e.g. 50+ doctors simultaneously submitting ground truth reviews across 7 Vinmec hospitals), SQLite database write locking (`database is locked`) may cause latency spikes.
- **Recommended Action**: Migrate from SQLite to PostgreSQL with `asyncpg` or `SQLAlchemy 2.0 async engine` when transitioning to multi-hospital enterprise deployment.

---

### TD-002: Asynchronous Background Worker Queue
- **Current State**: Model inference on uploaded images runs synchronously within the FastAPI request cycle (typical latency ~500ms on CPU).
- **Impact**: If users upload large batches of high-resolution 3D ultrasound volume files or multi-frame video cine loops, synchronous request handling could tie up HTTP worker threads.
- **Recommended Action**: Implement an asynchronous task queue (e.g., Redis + Celery / ARQ) with WebSocket or Server-Sent Events (SSE) progress streaming for heavy 3D volume segmentations.

---

### TD-003: DICOM PACS Integration (DICOMweb Standard)
- **Current State**: Clinical ultrasound images are ingested via PNG/JPG/JPEG file upload, with basic DICOM pixel array extraction.
- **Impact**: In hospital PACS environments, images arrive over DICOM network protocols (C-STORE, C-FIND, C-MOVE) or DICOMweb (WADO-RS, STOW-RS).
- **Recommended Action**: Implement a dedicated PACS connector microservice supporting DICOMweb RESTful standards with Orthanc or dcm4chee archives.

---

### TD-004: Frontend TypeScript & Bundler Evolution
- **Current State**: The frontend uses clean, modular vanilla JavaScript (`frontend/js/modules/`) and CSS tokens, running natively in all modern browsers without build dependencies.
- **Impact**: High simplicity and zero build overhead. However, as the UI feature set grows, type annotations and compile-time contract checking with FastAPI OpenAPI schemas would further enhance developer productivity.
- **Recommended Action**: Introduce optional TypeScript declarations (`.d.ts`) or a lightweight Vite bundler configuration if the development team expands.

---

### TD-005: Model Registry Dynamic Hot-Reloading
- **Current State**: Model weights (`best_attention_unet.pth`) are loaded into memory at startup in `backend/app/config.py`.
- **Impact**: Registering a newly trained model checkpoint requires restarting the FastAPI process or triggering manual adapter re-initialization.
- **Recommended Action**: Implement dynamic model hot-reloading with zero-downtime memory swap and GPU VRAM management.

---

## 2. Maintenance & Quality Checklist for Developers

- [x] Run `ruff check backend/ tests/ scripts/` before every commit.
- [x] Run `python -m unittest discover -s tests` to verify 100% test pass rate.
- [x] Use `cv2_imread_unicode` and `cv2_imwrite_unicode` for all image I/O operations.
- [x] Maintain separate routers in `backend/app/routers/` for any new endpoints.
- [x] Maintain separate JS modules in `frontend/js/modules/` for any new UI features.
