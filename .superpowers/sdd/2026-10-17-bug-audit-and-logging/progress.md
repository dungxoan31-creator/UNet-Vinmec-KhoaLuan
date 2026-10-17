# SDD Progress Ledger — 2026-10-17-bug-audit-and-logging

**Plan**: `docs/superpowers/plans/2026-10-17-bug-audit-and-logging.md`  
**Spec**: `docs/superpowers/specs/2026-10-17-bug-audit-design.md`  
**Branch**: `accuracy-experiments-2026-10-09`  
**Base commit**: `94d46e5`  

## Tasks Overview
- [x] Task A01: Khóa baseline và runtime audit an toàn (`evaluation/bug_audit/<run_id>/`)
- [x] Task A02: Chuẩn hóa registry và triage các issue lịch sử (`docs/audit/`)
- [x] Task A03: Audit preprocessing, model, coordinate và metrics (`backend/services/`, `evaluation/`)
- [x] Task A04: Audit API, transaction, auth và input boundaries (`backend/app/routers/`, `backend/services/`)
- [x] Task A05: Audit UI/HITL thật và race conditions (`frontend/app/`, `tests/workspace_v2_*.js`)
- [x] Task A06: Audit evaluation artifacts, báo cáo và full regression (`scripts/`, `evaluation/`, `tests/`)
- [x] Task A07: Triage, kiểm tra bug log và bàn giao backlog sửa (`docs/audit/audit_summary_2026-10-17.md`)

## Progress Log
- Baseline initialized on HEAD 94d46e5.
- Task A01: complete — established fresh audit run directory `evaluation/bug_audit/20261017T040604Z-94d46e5/`; verified port 8027 free; verified isolation of production DB `ovarian_ai.db` from disposable `artifacts/review-e2e-runtime`; generated `run_manifest.json`, `source_hashes.csv` (27 key files with SHA-256 and UTC timestamps), initial `coverage.csv` (13 domain components), and `commands.csv`.
- Task A02: complete — created `docs/audit/README.md` with lifecycle states and severity definitions; triaged historical ISS-01..05 as non-product-bugs (DATA_BLOCKER, STUDY_GAP, LIMITATION); created canonical `docs/audit/bug_template.md` and initialized canonical `docs/audit/bug_index.csv`; ensured `docs/audit/findings/` exists.
- Task A03: complete — audited preprocessing, model inference, coordinate transformations, and segmentation metrics; executed named pytest suite (`test_segmentation_metrics_v1.py`, `test_inference_parity_v1.py`, `test_evaluation_protocol_v1.py`, `test_evaluation_run_v1.py` — 27 passed in 2.00s); executed Node logic assertions (`tests/workspace_v2_logic.mjs` — PASS); confirmed oracle metrics (Dice 0.5, IoU 1/3, Recall/Precision 0.5), empty mask contracts, nonsquare letterbox inverse mapping, and monotonic timings; recorded logs in `logs/pytest_a03.txt` and `logs/node_workspace_logic.txt`.
- Task A04: complete — audited API boundaries, transactions, auth roles, and input validation; executed 33 tests across `test_review_batch.py`, `test_research_export.py`, `test_auth_boundaries.py`, `test_protected_clinical_api.py`, `test_prototype_release_failures.py`, `test_duplicate_upload.py` (33 passed in 2.11s); confirmed atomic rollback on invalid batch image, 409 on stale revision/duplicate mismatch, controlled 400/404/422 on corrupted inputs, and strict absence of PHI in exported research bundles; recorded logs in `logs/pytest_a04.txt`.
- Task A05: complete — audited UI/HITL live workflow, concurrency, races, and lease guards on isolated server (`serve_isolated_app.py` on port 8027); executed full live Playwright suite `tests/workspace_v2_release_e2e.js` (PASS, brush area change 18163->18980, atomic review, ZIP export, persistence, multi-case isolation); executed `workspace_v2_races.js` (PASS), `workspace_v2_draft_conflict.js` (PASS), `workspace_v2_api_abort.js` (PASS), `workspace_v2_lease_guards.js` (PASS), and `workspace_v2_telemetry.mjs` (PASS — 7 tests); shut down audit server with no port leaks; recorded logs in `logs/e2e_release.txt`, `logs/races.txt`, `logs/draft_conflict.txt`, `logs/api_abort.txt`, `logs/lease_guards.txt`, `logs/node_telemetry.txt`.
- Task A06: complete — audited evaluation artifacts, report consistency, and full regression test suite; executed evaluation pytest suite (34 passed in 28.04s); executed full repository pytest suite across all 291 tests in `tests/` (284 passed, 5 failed, 2 skipped in 72.51s); isolated and triaged all 5 failures (2 DATA_BLOCKER due to missing deleted `reports/dataset_deduplication_report.csv`, 3 TEST_MAINTENANCE due to missing `expected_revision`/`request_id` in `test_prototype_extensions.py`); recorded findings AUD-0001, AUD-0002, AUD-0003 and logged full output in `logs/full_regression_pytest.txt`.
- Task A07: complete — generated `evaluation/bug_audit/20261017T040604Z-94d46e5/summary.json` and `checksums.csv` (16 files); created canonical findings `docs/audit/findings/{AUD-0001,AUD-0002,AUD-0003}.md`; updated canonical `docs/audit/bug_index.csv`; authored comprehensive executive summary report `docs/audit/audit_summary_2026-10-17.md` with domain coverage matrix, historical triage, root-cause analyses, and exact remediation instructions for coding agents; full plan execution completed.
