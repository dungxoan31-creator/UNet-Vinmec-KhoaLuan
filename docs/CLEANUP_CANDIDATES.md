# CLEANUP CANDIDATES AUDIT REPORT

This document audits all files in the repository to identify candidates for deletion, migration, reorganization, or retention, following strict safety and dependency verification rules.

## Decision Criteria
- **DELETE**: No reference + No runtime dependency + No build dependency + No test dependency + Duplicate or obsolete artifact.
- **MOVE / REORGANIZE**: Valid asset, thesis documentation, or template that belongs in a structured sub-directory rather than root.
- **REFACTOR / SPLIT**: God files or monolithic components with multiple responsibilities.
- **KEEP**: Active production code, models, datasets, configs, or tests.

---

## File Audit Matrix

| File / Path | Category | Reason / Analysis | Dependency Check | Decision |
|---|---|---|---|---|
| `backend/app/main.py` | GOD FILE / CORE | 882 lines combining all routers, static mounts, utilities, auth, and logic. | Referenced by tests, uvicorn entry point. | **REFACTOR & SPLIT** into modular routers and config. |
| `frontend/index.html` | GOD FILE / UI | 5,945 lines combining 2,414 lines CSS, 1,857 lines JS, and 1,674 lines HTML. | Primary frontend entry point. | **REFACTOR & SPLIT** into CSS stylesheets, JS modules, and clean HTML. |
| `TEMPLATE_GIAY_CHAN_DOAN_Y_KHOA.html` | TEMPLATE / DUPLICATE | Near-exact clone of medical diagnosis HTML report in root. | Static document / template. | **MERGE / MOVE** to `templates/medical_report/vinmec_diagnosis_template.html`. |
| `BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC - PHIẾU KẾT QUẢ CHẨN ĐOÁN.html` | TEMPLATE / DOC | Medical diagnosis HTML report in root with Unicode filename. | Static document / template. | **CONSOLIDATE** into `templates/medical_report/`. |
| `Phieu_Ket_Qua_Sieu_Am_4c899512-45e1-47ca-93a6-dde1a5395ff4.pdf` | ARTIFACT / SAMPLE | Sample generated PDF sitting in project root. | Sample output. | **MOVE** to `data/reports/`. |
| `generate_de_cuong.py` | SCRIPT / THESIS | Script generating student thesis proposal docx. | Generates thesis proposal documents. | **MOVE** to `docs/thesis_proposal/`. |
| `MSV_11235559_NguyenHuuDung_DeCuongSoBo_KLTN.docx` | DOC / THESIS | Academic thesis proposal document. | Academic deliverable. | **MOVE** to `docs/thesis_proposal/`. |
| `MSV_11235559_NguyenHuuDung_DeXuatKLTN_Vong1.docx` | DOC / THESIS | Academic thesis proposal round 1 document. | Academic deliverable. | **MOVE** to `docs/thesis_proposal/`. |
| `NguyenHuuDung_11235559_KLTN_V2.docx` | DOC / THESIS | Academic thesis proposal v2 document. | Academic deliverable. | **MOVE** to `docs/thesis_proposal/`. |
| `v1_content.txt` | DOC / THESIS | Raw thesis proposal draft text. | Academic deliverable. | **MOVE** to `docs/thesis_proposal/`. |
| `v2_content.txt` | DOC / THESIS | Raw thesis proposal draft v2 text. | Academic deliverable. | **MOVE** to `docs/thesis_proposal/`. |
| `backend/services/report_generator.py` | SERVICE | PDF Medical Report generator using ReportLab. | Used by main app & test suite. | **KEEP & REFACTOR** imports. |
| `backend/services/inference_engine.py` | SERVICE | Attention U-Net inference engine & caliper extractor. | Used by main app & test suite. | **KEEP & REFACTOR** imports. |
| `backend/services/model_service.py` | SERVICE | Model service & registry abstractions. | Used by main app. | **KEEP & REFACTOR** imports. |
| `backend/services/preprocessor.py` | SERVICE | Ultrasound preprocessor and IQA quality filter. | Used by main app & test suite. | **KEEP & REFACTOR** imports. |
| `backend/db/database.py` | DATA / DB | SQLAlchemy SQLite database models & session management. | Used across backend. | **KEEP & REFACTOR** imports. |
| `backend/models/attention_unet.py` | MODEL | Attention U-Net neural network architecture. | Used in inference engine & training. | **KEEP & REFACTOR** imports. |
| `backend/models/losses.py` | MODEL / LOSS | ComboLoss and DiceLoss definitions. | Used in training & tests. | **KEEP & REFACTOR** imports. |
| `backend/models/metrics.py` | MODEL / METRIC | Dice, IoU, and Hausdorff distance 95. | Used in training & tests. | **KEEP & REFACTOR** imports. |
| `backend/schemas/schemas.py` | SCHEMA | Pydantic request/response schemas. | Used across API routers. | **KEEP & REFACTOR** imports. |
| `checkpoints/best_attention_unet.pth` | ARTIFACT / MODEL | Best checkpoint for production Attention U-Net. | Loaded by model service & tests. | **KEEP**. |
| `ovarian_ai.db` | DATABASE | SQLite database file. | Live application database. | **KEEP**. |
| `dataset.zip` | DATASET / ARCHIVE | Dataset compressed backup. | Local training archive. | **KEEP**. |
