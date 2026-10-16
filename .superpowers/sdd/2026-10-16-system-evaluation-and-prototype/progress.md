# SDD ledger — plan: docs/superpowers/plans/2026-10-16-system-evaluation-and-prototype.md

## Pre-flight interface scan
Pre-flight scan:
- T01 establishes baseline and test harness runner `verify_evaluation_release.ps1` with isolated environment.
- T02 creates `evaluation/protocol.py`, `protocols/milestone3_v1.json`, manifests for validation/legacy and gates.
- T03 creates `evaluation/segmentation_metrics.py` (consumed by T05 evaluator and T14 HITL analysis).
- T04 modifies `InferenceEngine` to provide `predict_binary` / shared probabilities for evaluator and API serving.
- T05 integrates T02, T03, T04 into `evaluation/run_evaluation.py`.
- T06 adds freeze lock to T05 runner and performs validation / retrospective test runs.
- T07 builds `evaluation/error_analysis.py` consuming T05 run output.
- T08 adds environment-based runtime isolation (`APP_DATA_DIR`, `APP_DB_PATH`) and health/capabilities fallback.
- T09 adds `review_revision` to StudyModel and `provenance_json` to PredictionModel.
- T10 adds `POST /api/reviews/batch` with transaction rollback, idempotency, revision guard and frontend adoption.
- T11 adds `POST /api/cases/{study_id}/research-export` producing pinned ZIP bundle.
- T12 adds `HITLSessionModel` & `HITLEventModel` + `/api/hitl/sessions` endpoints.
- T13 adds frontend `hitl-tracker.js` and monotonic timings instrumentation.
- T14 adds `evaluation/hitl_analysis.py` and `scripts/export_hitl_sessions.py`.
- T15 prepares clinician protocol, questionnaire, and fallback handling.
- T16 implements comprehensive live E2E (`tests/workspace_v2_release_e2e.js`).
- T17 implements negative tests & failure boundary guards.
- T18 packages Windows launcher `scripts/run_prototype.ps1` and runbook.
- T19 builds report generator `scripts/build_evaluation_report.py` and updates evaluation UI.
- T20 runs final release verification via `scripts/verify_evaluation_release.ps1` and gathers release evidence.

Pre-flight ruling: All interfaces match spec and plan specifications.

Task 1: complete — commit e26b11e "test: establish isolated evaluation baseline"
- baseline verification script `scripts/verify_evaluation_release.ps1`
- baseline artifacts recorded in `evaluation/milestone_3_final/baseline/`
- isolated pytest + node checks pass
- requirement traceability initialized

Task 2: complete — commit 5558bc8 "test: lock evaluation protocol and data gates"
- frozen protocol `evaluation/protocols/milestone3_v1.json`
- protocol loader and auditor `evaluation/protocol.py`
- manifests generated for validation (541) and legacy test (402)
- data independence gate blocks unverified cohorts without patient-level evidence
- evaluation protocol document `docs/evaluation/evaluation_protocol.md`
- all protocol and gate tests passing

Task 3: complete — commit a2e89db "feat: add versioned segmentation metrics and oracles"
- `evaluation/segmentation_metrics.py` implemented with hand-computed arithmetic oracles
- empty masks agreement contract and null reasons
- symmetric surface HD95 in pixel units without bogus defaults
- exact integer confusion counts and auxiliary pixel fractions
- deterministic stats, patient-level macro, and 2,000-iteration cluster bootstrap CI
- all 22 tests passing (unit + regression)

Task 4: complete — commit 56eeea4 "fix: share locked inference path with evaluation"
- `InferenceEngine.forward_probabilities` and `predict_binary` implemented
- shared single model forward pass between serving and evaluation
- locked threshold >= 0.5 without morphology
- native inverse letterbox preserves source geometry
- all 19 tests passing (unit + regression)

Task 5: complete — commit 682de3a "feat: add reproducible native-space evaluation runner"
- implemented `evaluation/run_evaluation.py` and CLI
- atomic run lifecycle: RUNNING -> COMPLETE / PARTIAL
- per-image metrics, per-case metrics, summary statistics, and dice distribution histogram
- native-space binary prediction PNG generation with SHA-256 readback verification
- verified on 541-case validation cohort (Primary Dice Mean: 0.6717)
- unit tests passing

Task 6: complete — commit 6c0492e "test: enforce frozen evaluation access protocol"
- protocol freeze CLI `--freeze` generating `protocol_lock.json`
- locked evaluation requiring matching protocol/manifest/checkpoint hashes
- enforcement that cohorts with prior test access cannot be labeled independent
- test access ledger tracked in `docs/evaluation/test_access_ledger.csv`
- retrospective test replay completed with locked protocol (Primary Dice Mean: 0.7289)
- data independence gate strictly preserves BLOCKED status for unverified holdout

Task 7: complete — commit e91f1d9 "feat: render traceable segmentation error analysis"
- implemented `evaluation/error_analysis.py` with multi-group ranking (best, median, worst, fp, fn, under, over, boundary)
- 5-column case panel rendering (Original, GT, Prediction, Overlay, Difference: TP green, FP red, FN blue)
- offline interactive `index.html` report with HTML escaping
- `groups.csv` and `error_annotations.csv` separating factual observations from hypotheses
- generated 29 case panels on legacy test run
- unit tests passing







Task 8: complete — commit 8683a7f "fix: connect workspace to supported live runtime"
- environment variable isolation via `APP_DATA_DIR` and `APP_DB_PATH`
- `GET /api/health` reports `model_ready`, `checkpoint_sha256`, and system `capabilities`
- `GET /api/capabilities` endpoint added for client compatibility
- `frontend/app/cases.js:getCases()` falls back to `/api/cases` when `case_workflow !== true`
- `frontend/app/main.js` bootstraps system capabilities
- isolated test server runner `tests/serve_isolated_app.py` uses configured env vars
- unit tests `tests/test_runtime_configuration.py` and regression checks passing
- Playwright E2E live and capability probe tests passing

Task 9: complete — commit 47b081d "feat: persist prediction provenance and review revision"
- added `review_revision` column to `StudyModel` and `provenance_json` to `PredictionModel`
- idempotent schema migrations in `init_db()` for existing databases
- `run_ai_prediction` builds and persists JSON-friendly `provenance_payload` (checkpoint_sha256, serving_config_sha256, threshold, native_shape, transform)
- `GET /api/cases/{study_id}` exposes `review_revision` and exact persisted provenance without fabricating hashes on legacy records
- unit tests in `tests/test_prediction_provenance.py` and regression tests passing

Task 10: complete — commit aeeeb9a "feat: persist atomic versioned research reviews"
- `ReviewBatchModel` for idempotency and replay caching
- schema `BatchReviewRequest`, `BatchReviewResponse`, and `ReviewSummaryItem`
- `persist_review_batch` with DOCTOR check, optimistic revision guard, bilateral/laterality checks, and atomic commit/rollback
- `POST /api/reviews/batch` endpoint and legacy `/api/review` delegation
- `frontend/app/review.js:saveResearchReview` single atomic batch request adoption
- full unit & regression suite passing (28 tests)

Task 11: complete — commit dae56d2 "feat: export pinned research masks and provenance"
- `backend/services/research_export.py:build_research_bundle` packaging ZIP with metadata.json, native ai_mask.png, reviewed_mask.png, overlay.png
- `POST /api/cases/{study_id}/research-export` endpoint validating revision and pinned review IDs
- `GET /api/images/{image_id}/mask.png` supporting explicit pinned review_id and prediction_id with 422 mismatch validation
- UI action "Tải kết quả nghiên cứu" in viewer and report preview
- unit tests `tests/test_research_export.py` and regression suites passing (10 tests)



Task 12: complete — commit 5bf6be7 "feat: record authenticated HITL sessions and events"
- `HITLSessionModel` and `HITLEventModel` in database schema with unique constraints
- Schemas `HITLSessionRequest`, `HITLEventItem`, `HITLEventBatch`, `HITLSessionResponse` with finite duration validators and client event limits (max 100 per batch, max 10,000 per session)
- `backend/app/routers/hitl.py` implementing `POST /api/hitl/sessions`, `POST /api/hitl/sessions/{id}/events`, `GET /api/hitl/sessions/{id}`
- Review batch linking: `persist_review_batch` emits server-authoritative `CONFIRM_SUCCEEDED` with `seq=0` and flags session `INCOMPLETE` until matching `CONFIRM_ACK` is received
- Comprehensive unit tests in `tests/test_hitl_events.py` (8 passing tests)
- Full regression tests passing (33 tests)

Task 13: complete — commit d3c219c "feat: instrument live correction tasks and monotonic timing"
- `frontend/app/hitl-tracker.js` pure telemetry tracker with monotonic `performance.now()`, event queuing, stroke/edit counting, pause/resume, and watermarked batch flushing
- `tests/workspace_v2_telemetry.mjs` Node tests (7/7 passing) verifying exact timing arithmetic (roundtrip 100ms, active_edit 40ms, review_elapsed 630ms, correction_elapsed 500ms, task_total 750ms), session isolation, idempotency, retry deduplication, pause/resume, and non-zero edit after reset
- Integration into `upload.js`, `intake.js`, `viewer.js`, `review.js`: participant metadata in intake, inference timing boundaries, decoded viewing markers, edit commit tracking, visibility change pause/resume, and watermarked confirm ACKs
- Backend monotonic timers: `time.perf_counter()` and `torch.cuda.synchronize()` in `InferenceEngine.forward_probabilities` and `run_ai_prediction` returning `timings: {model_forward_ms, server_pipeline_ms}`
- Schema update: `PredictionResponse.timings` and nullable `DoctorReviewRequest.time_spent_seconds` with `ReviewModel.time_spent_seconds` nullable in SQLite
- Verified with `pytest tests/test_inference_parity_v1.py -v` (5/5 passing) and regression suite (32 passing)

Task 14: complete — commit afb49e2 "feat: analyze measured HITL sessions and paired mask quality"
- `scripts/export_hitl_sessions.py` read-only SQLite URI export (`mode=ro`) to `sessions.csv`, `events.jsonl`, `sessions.json` without PHI
- `evaluation/hitl_analysis.py` implementing `summarize_timeline`, `analyze_hitl`, and CLI
- `tests/test_hitl_analysis.py` covering timing oracle, incomplete timelines, exact prediction pairing, reference independence, role/origin isolation, paired delta quality, and session wall time vs image sum (7/7 passing)
- Exported sessions and events from database to `evaluation/milestone_3_final/hitl/raw/`
- Ran analysis CLI producing `per_session.csv`, `per_task.csv`, `summary.json` in `evaluation/milestone_3_final/hitl/analysis/`
- All regression suites passing (28 pytest, 7 node)

Task 15: complete — commit fce9344 "docs: formalize clinician evaluation protocol and questionnaire"
- `docs/evaluation/clinician_protocol.md` formalizing protocol, ethics, instructions, dimensions, and fallback
- `docs/evaluation/questionnaire.csv` defining 7 Likert items and 4 qualitative feedback prompts
- `docs/evaluation/manual_acceptance.md` defining step-by-step technical acceptance checklist and recording PASS verdict for prototype readiness
- `evaluation/hitl_analysis.py` extended with `summarize_questionnaire` and CLI options `--questionnaire`, `--participants`, `--user-study-output`, `--study-status`
- `tests/test_user_study_summary.py` covering Likert oracles, deduplication, N/A exclusion, role separation, HTML escaping, and status preservation (4/4 passing)
- Generated `evaluation/milestone_3_final/user_study/` with `study_status.json` honestly recording `NOT_CONDUCTED` (clinician count 0, technical tester 1) without fabricated doctor ratings
- All unit & regression tests passing (19 passing)

Task 16: complete — commit b71f186 "test: cover live save export restart and case isolation"
- `tests/workspace_v2_release_e2e.js` comprehensive live E2E test verifying: doctor auth, bilateral case creation, upload & prediction, deliberate brush stroke, undo/redo bitwise assertions, reset AI confirmation, atomic batch review save, research ZIP export (7 files in ZIP with metadata SHA256), unsupported clinical sign-off guard (501), reopen persistence across sessions, and Case 2 multi-case isolation
- Parameterized `tests/workspace_v2_live.js` with `E2E_BASE_URL`, `CHROME_PATH`, `APP_DOCTOR_PASSWORD`, `APP_ADMIN_PASSWORD`
- Configured `tests/serve_isolated_app.py` with `sys.path` and configurable port/host
- Extended `scripts/verify_evaluation_release.ps1` to launch isolated server and execute `workspace_v2_release_e2e.js` when browser testing is enabled
- All live browser tests passed with zero page errors

Task 17: complete — commit 4dd3cd1 "test: enforce prototype failure and access boundaries"
- `tests/test_prototype_release_failures.py` verifying negative inputs & failure modes: empty files (0 bytes), invalid extensions (.exe), oversized files (>20 MiB returning HTTP 413), corrupt image bytes, unauthenticated calls (401), invalid laterality (422), non-existent image/study (404), non-doctor review rejection (403), and database state integrity on prediction failures (11/11 passing)
- `backend/app/routers/inference.py` updated to return HTTP 413 for uploads exceeding 20MB and bounded decoded raster limit at 25 million pixels
- Comprehensive regression pytest suite passing (70/70 passing) and all Node suites passing

Task 18: complete — commit pending "docs: package reproducible supervised prototype run"
- `scripts/run_prototype.ps1` native PowerShell launcher and pre-flight readiness runner validating Python virtualenv, external checkpoint SHA-256 hash (`417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`), and required environment secrets (`APP_JWT_SECRET` >= 32 chars, `APP_DOCTOR_PASSWORD`, `APP_ADMIN_PASSWORD`), supporting `-CheckOnly` and isolated `-RuntimeDir` execution
- `docs/evaluation/release_runbook.md` comprehensive operator runbook detailing system prerequisites, security secrets configuration, checkpoint verification, supervised launch commands, SQLite online backup/restore procedures, and clinical boundaries
- Updated `README.md` and `frontend/README.md` with standardized launcher instructions
- `tests/test_runtime_configuration.py` expanded with 4 launcher unit tests (missing secrets, missing checkpoint, clean CheckOnly, no secret leaks) — all 7 tests passing




