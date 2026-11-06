# System-Wide Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Correct the 25 findings from the 2026-11-04 audit and gather isolated verification evidence for the blocked workflows without overstating clinical readiness.

**Architecture:** Reuse the current FastAPI, SQLAlchemy, and vanilla JavaScript architecture. Implement shared facility-scoped identity and authorization at backend boundaries, preserve existing RUO/HITL review contracts, and test browser/report behavior through the existing test harness.

**Tech Stack:** Python, FastAPI, SQLAlchemy, SQLite test fixtures, vanilla JavaScript, Node test runner, Playwright when the existing environment permits.

**Spec:** `docs/superpowers/specs/2026-11-04-system-wide-remediation-design.md`; binding audit scope: `audit/2026-11-04/ISSUE_REGISTER.md`.

## Global Constraints

- Preserve image-level split with SHA-256 deduplication; do not require or fabricate patient IDs for AI training.
- Preserve Letterbox 512x512 preprocessing, Dice+BCE core training scope, and HITL physician review.
- Keep RUO and model uncertainty visible; software verification is not clinical validation.
- Do not access or mutate production data, run live migrations, make backups outside a disposable test directory, install dependencies, commit, or deploy.
- Use temporary databases, synthetic fixtures, and test-only files for every write workflow.
- Preserve the 245-path dirty checkout as found; no reset, stash, cleanup, or broad file replacement.

## Review Focus

1. Two facilities submit the same source identifier; the resulting patient records and study links must remain separate, including legacy backfill cases.
2. A facility administrator tries global settings, backup, restore, or another facility's directory; access must fail before side effects.
3. Concurrent patient-store edits, logout, and empty-list hydration must not leak or silently discard records.
4. Missing clinical descriptors, exactly 30 mm, and missing laterality/status must not become unverified diagnoses or confirmed findings.
5. Interrupted report saves, print pagination, and narrow viewports must preserve saved data and expose the correct clinical state.

---

## Sprint 1 — Identity, authorization, and account security

### Task 1: Facility-scoped patient identity (AUD-001)

**Files:** `backend/core/patient_identity.py`, `backend/services/patient_identity.py`, `backend/db/database.py`, `backend/app/routers/cases.py`, `backend/app/routers/inference.py`, `backend/app/routers/visits.py`, `tests/test_patient_identity.py`, migration tests.

- [x] Add a failing regression for equal source IDs in two facilities and same-facility idempotent resolution.
- [x] Run it and confirm the cross-facility identity assertion fails.
- [x] Add facility scope to the HMAC input and persisted uniqueness contract; thread the verified facility through every identity creation path.
- [x] Add migration tests for old records, including a patient linked to studies from multiple facilities; preserve case relationships and pseudonyms without using production data.
- [x] Run the identity and schema migration tests.

### Task 2: Scope admin settings and backup/restore authorization (AUD-002, AUD-003; unblock backup/restore)

**Files:** `backend/app/routers/admin.py`, `backend/services/backup_service.py`, admin request schemas, `tests/test_tenant_admin_hardening.py`, backup integration tests.

- [x] Add failing role-matrix tests for scoped/global settings reads and writes, backup creation/list, and no side effect on denial. No restore endpoint exists; record it as unavailable rather than adding a destructive API.
- [x] Confirm failing authorization tests against the current handlers (global settings lacked scope, admin metadata was unscoped, backup audit failure left an archive behind).
- [x] Store facility settings by facility; restrict whole-database backup creation/listing to a verified global admin.
- [x] Create and restore a synthetic SQLite archive only inside `tmp_path`; validate every generated archive member resolves inside the restore directory and verify the restored row.
- [x] Run authorization and backup tests.

### Task 3: Preserve current session after password change (AUD-006)

**Files:** `frontend/app/personal.js`, `frontend/app/auth.js`, `tests` account/session tests.

- [x] Add a failing browser test for applying the returned access token and expiry after password change.
- [x] Confirm the next authenticated request fails under the old token in the test.
- [x] Update session state from the validated token response using the existing auth helper.
- [x] Run the focused session test and JavaScript syntax checks.

### Task 4: Preserve changed bootstrap passwords (AUD-007)

**Files:** `backend/db/database.py`, `tests` bootstrap/auth tests.

- [x] Add a failing isolated restart test where an existing account password differs from the bootstrap environment value.
- [x] Confirm current initialization resets the existing password.
- [x] Restrict environment passwords to initial account creation; keep explicit reset flows separate and audited.
- [x] Run bootstrap and authentication tests.

## Sprint 2 — Patient directory, data minimization, and intake

### Task 5: Server patient-directory contract and concurrency (AUD-004, AUD-008)

**Files:** `backend/db/database.py`, `backend/schemas/schemas.py`, a focused patient router or existing router, `frontend/app/intake-session.js`, `frontend/app/intake.js`, API/store tests.

- [x] Add failing tests for facility-scoped create/list/update/delete and concurrent updates from two clients.
- [x] Confirm the current browser-only store has no server persistence and can lose a stale-cache update.
- [x] Add the smallest facility-scoped API and connect intake to it; persist only approved minimum fields and do not store raw source identifiers.
- [x] Reject cross-facility reads/writes and stale updates without silently overwriting the last saved value.
- [x] Run API, store, and intake tests (`20` Python API/identity/visit tests; `11/11` focused JavaScript tests).

### Task 6: Remove non-demo seeds and preserve empty lists (AUD-005, AUD-009)

**Files:** `frontend/app/intake.js`, `frontend/app/intake-session.js`, patient-store tests.

- [x] Add failing tests for a clean non-demo directory and an intentionally empty saved list.
- [x] Confirm seeds appear or rehydrate in the current behavior.
- [x] Restrict synthetic seed data to demo mode and distinguish absent storage from a valid empty list.
- [x] Run patient-store tests (`11/11` focused JavaScript tests).

### Task 7: Clear local demographic data on logout (AUD-010)

**Files:** `frontend/app/auth.js`, `frontend/app/navigation.js`, intake-store tests.

- [x] Add a failing test that local-only patient demographics are removed on logout/account switch while unrelated preferences remain.
- [x] Clear only the account-scoped patient data using the existing store key contract.
- [x] Run auth and store tests (`11/11` focused JavaScript tests; logout/draft behavior separately covered by synthetic E2E).

### Task 8: Reduce intake burden and clarify identifiers (AUD-011, AUD-012)

**Files:** `frontend/app/intake.js`, `frontend/app/intake-session.js`, `frontend/app/upload.js`, `backend/schemas/schemas.py`, case display components and tests.

- [x] Add failing tests for required-field purpose, age propagation, and distinct source/local ID versus research pseudonym labels.
- [x] Remove unneeded required fields; carry only validated age/context needed by case workflows.
- [x] Display the local/source identifier and server pseudonym with distinct names and scope.
- [x] Run intake/case/report contract tests (`11/11` focused JavaScript tests; related Python suites listed in the final report).

## Sprint 3 — Clinical report, analytics, and terminology

### Task 9: Report laterality/status and facility header (AUD-016, AUD-017)

**Files:** `frontend/app/report-preview.js`, report data contract, facility settings API, report tests.

- [x] Add failing report tests for NOT_VISUALIZED, SURGICALLY_ABSENT, and facility header propagation.
- [x] Use the persisted contralateral status and authorized facility header in the report.
- [x] Run report preview and print-handler tests (`41` focused Python report tests and `12` report-preview frontend tests; current full browser print flow remains checkpoint-blocked).

### Task 10: Prioritize clinical report content and keep identifiers legible (AUD-018, AUD-025)

**Files:** `frontend/app/report-preview.js`, `frontend/css/workspace.css`, report tests and print artifact harness.

- [x] Add failing DOM/print tests for first-page clinical summary and unbroken pseudonym display.
- [x] Reorder saved physician findings, O-RADS, and images before technical provenance while keeping RUO/provenance available.
- [x] Verify print page count/text and a narrow metadata layout using the actual print handler where a saved synthetic review is available; current live inference-dependent browser path remains blocked.
- [x] Run report tests (`41` focused Python report tests and `12` report-preview frontend tests).

### Task 11: Distinguish missing analytics from measured zero (AUD-019)

**Files:** analytics aggregation in `backend/app/routers/admin.py`, dashboard rendering, API/UI tests.

- [x] Add failing tests for no observations, observed zero, and nonzero denominator.
- [x] Preserve null/denominator information through API and render N/A for missing observations.
- [x] Run analytics tests (`2` focused analytics Python tests; report UI tests included in the 33-test JS group).

### Task 12: Align O-RADS copy and boundaries (AUD-020)

**Files:** `backend/services/cdss_engine.py`, `frontend/app/viewer.js`, analytics terminology, existing O-RADS tests and copy tests.

- [x] Add failing tests for `<30 mm`, exactly `30 mm`, interval labels, and missing physiology context.
- [x] Reuse the current versioned project rule and make all user-facing labels consistent; do not infer O-RADS 1 from size alone.
- [x] Keep disagreement with source guideline explicit and do not claim independent clinical approval.
- [x] Run CDSS and copy tests (`143` focused CDSS/copy tests passed).

### Task 13: Reconcile selected model loss provenance (AUD-024)

**Files:** selected model manifest, training/provenance docs, model-loading tests.

- [x] Add a failing contract test that selected checkpoint provenance matches the declared loss or is blocked from serving.
- [x] Do not relabel weights or claim Dice+BCE training without evidence. Keep mismatched historical checkpoints explicitly unverified and unavailable for a claim of core-scope training.
- [x] Run manifest/model-loading tests; no retraining or weight changes (`96` tests in the focused runtime/provenance/DICOM/correction group passed; selected model remains unavailable).

## Sprint 4 — Layout, accessibility, and feedback

### Task 14: Prevent action-bar overlap and fix mobile fields/table (AUD-013, AUD-014, AUD-015)

**Files:** `frontend/css/workspace.css`, `frontend/app/intake.js`, existing responsive browser tests.

- [x] Add failing viewport assertions for the supported intake sizes; screenshots and scroll geometry were captured at 1366x768 and adjacent sizes.
- [x] Allocate layout space for the upload action and readable date/name controls.
- [x] Run browser tests at relevant viewport sizes (`clinical_safety_e2e.js` passed; mobile 390x844 probe verifies patient labels/name and datetime geometry; the primary upload CTA remains below the fold and requires main-panel scrolling at 1366x768).

### Task 15: Make admin chart drilldown keyboard accessible (AUD-021)

**Files:** admin chart renderer and tests.

- [x] Add failing keyboard/semantic assertions for drilldown controls.
- [x] Use native interactive controls or equivalent role, focus, and keyboard behavior.
- [x] Run DOM/keyboard tests (`tests/admin_reports_keyboard_e2e.js` passed).

### Task 16: Correct save toast and localize network errors (AUD-022, AUD-023)

**Files:** `frontend/app/review.js`, `frontend/app/api.js` or existing error boundary, `frontend/app/i18n.js`, review/network tests.

- [x] Add failing tests for saved-side count and connection failure copy.
- [x] Report only persisted sides/images and give concise Vietnamese recovery guidance.
- [x] Run save and network-error tests (`33/33` focused JavaScript tests passed).

## Sprint 5 — Blocked workflow evidence and governance

### Task 17: DICOM PHI-cleaning and spacing sandbox

**Files:** existing DICOM inspection/cleaning modules and isolated DICOM tests.

- [x] Build synthetic DICOM fixtures with metadata, burned-in pixel text, absent/zero/anisotropic spacing.
- [x] Verify PHI cleaning and spacing extraction without real patient files; mark pixel-level burned-in detection limits explicitly.

### Task 18: Reviewer approval and technician correction verification

**Files:** `backend/app/routers/reviews.py`, corrections modules, existing review/correction tests.

- [x] Exercise reviewer approval, stale revisions, technician draft correction, and separation of roles with synthetic records.
- [x] Confirm technician actions cannot finalize physician review (`clinical_safety_e2e.js` and correction tests passed).

### Task 19: Evaluation screen permission verification

**Files:** evaluation router and frontend route guard, role matrix tests.

- [x] Exercise authorized and unauthorized roles against isolated data; do not export research data (`clinical_safety_e2e.js`, evaluation API/UI tests passed).

### Task 20: Bilateral consecutive-patient workflow

**Files:** intake/upload/session modules and existing browser harness.

- [ ] Exercise the complete left/right review, patient switch, interruption, save/reopen, and report sequence using synthetic images and isolated server data. **BLOCKED at inference:** the selected checkpoint returns the verified provenance-gate HTTP 503 before viewer/review/report steps.
- [x] Record measured interaction/time only from runtime output; full workflow interaction/time are **NOT MEASURED**. Partial intake geometry and synthetic API evidence are linked in the final report.

### Task 21: Final regression, review, and evidence report

**Files:** `audit/2026-11-04/ISSUE_REGISTER.md`, `issues.csv`, new `REMEDIATION_REPORT.md`, operation/evaluation docs as justified.

- [x] Run focused tests after each task; full Python suite passed 1,614/1,614; top-level Node suite passed 173/173; safety browser E2E passed; bilateral/doctor E2Es are explicitly BLOCKED at the verified model provenance gate.
- [ ] Inspect every line of the full diff against the already-dirty baseline and perform a complete independent review. Critical identity, authorization, persistence, report, model-gate, migration, and mobile paths were reviewed; the starting 245-path dirty worktree prevents attributing/reviewing every unrelated diff line in this pass.
- [x] Update issue dispositions only with direct test/runtime evidence; preserve unresolved clinical and model gates.
- [x] Report exact coverage, test results, limitations and NO-GO clinical readiness in `audit/2026-11-04/REMEDIATION_REPORT.md`; do not state staging-pilot readiness.

## Workspace and ledger rulings

- **Ruling:** Work in the supplied feature-branch checkout — the user selected this repository, the current 103 tracked-file diff contains relevant code, and recreating it in a clean worktree risks omitting those changes. No reset, stash, commit, or deployment.
- **Ruling:** Keep patient-data migrations test-only — production database access and mutation are outside the task's safe boundary; migration behavior must be proven with synthetic temporary databases.
- **Ruling:** The final readiness label is evidence-gated — model validation, clinical approval, native PostgreSQL/Docker, and deployment evidence were not available in the audit, so code remediation alone cannot establish clinical deployment readiness.
