# Milestone 3 evidence closure implementation plan

**Goal:** Audit and complete the verifiable technical deliverables without inventing clinical evidence.
**Architecture:** Read existing split snapshots, checkpoints, logs and reports; write a new timestamped evidence package. Reuse the dataset loader and inference engine. Keep historical results and source datasets intact.
**Tech stack:** Python standard library, existing PyTorch/OpenCV/Pillow/FastAPI, pytest and Playwright Core.
**Spec:** User's Evidence → Verification → Analysis → Decision → Documentation protocol, 2026-10-06.

## Constraints

- No new patient identifiers or reference labels; no dataset, split or weight changes.
- No new Test inference, threshold search or training using Test results.
- Preserve historical metrics and distinguish reference-label agreement from clinical validation.
- Back up documents/configurations before edits; no Git reset or bulk restore.
- Patient identity, expert label approval and professional HITL require external evidence.

## Tasks

- [x] Inventory current artifacts with hashes, Git status/history and latest-commit deletions; compare deleted blobs with existing copies and identify the official M2 DOCX.
- [x] Audit image/mask readability, content hashes, split intersections, all 35 fallback records and source identifiers without changing data.
- [x] Record selection criteria before new inference; verify existing Standard U-Net / U-Net++ Validation evidence and freeze a versioned research model lock.
- [x] Reuse the loader/engine for Validation error analysis; retain prediction, reference and overlay paths plus execution provenance.
- [x] Benchmark a deterministic Validation sample with warm-up and hardware metadata; measure components and client API time separately.
- [x] Run pytest and browser smoke against the frozen selected research model; retain raw logs and timestamps. No clinical participant results are inferred. Full suite has 8 failures; executing this check does not mean its gate passed.
- [x] Back up and reconcile README, MODEL_CARD, M2/M3 reports and project_status; preserve historical test counts with log references. M2 deletion was retained; reviewed DOCX is versioned inside the audit package.
- [x] Write the twelve-section audit report and readiness checklist; verify protected hashes and the final Git diff.

## Review focus

Missing historical provenance is recorded, never reconstructed as an original. A hash only proves byte identity. Matching labels do not establish clinician approval. Anonymous group IDs do not establish source patients. API `inference_time_ms` does not include the complete HTTP response. Existing Test metrics belong only to their recorded checkpoint. Final selection among existing runs is retrospective and single-seed, not preregistered.

## Execution ledger

Initial inspection: working tree clean at `383def17be49c62f172017cb96af308438c7eaad`; previous commit contains 469 deletions. Active default selection is Standard U-Net `417828fa…`; U-Net++ `ce758032…` has a separate candidate manifest. M2 provenance's old path is absent and must be investigated. User authorized direct execution; no additional plan approval is required.

Execution findings: 461 deleted blobs have identical current copies; eight unique summaries/CSV files were selectively recovered. All 1,604 canonical pairs read successfully; 1,881 historical duplicate target references are absent, with no disagreement in available target copies. The first diagnostic audit conflated absent copies with disagreement; corrected output is `verified_data/` and the diagnostic pass is explicitly superseded.

Ruling: During the audit, M1 dataset folders, dataset/index.csv and three M2 documents disappeared through an external action not identified by this agent. Owner then requested continuation only with Vinmec_2d and Vinmec_3d. Keep original split and source bytes, preserve exact Git snapshots of documents/index, and export a new versioned two-source index; do not undo owner deletions or create fallback masks. Cost: eight M1-dependent legacy tests remain failing and original M1 dataset cannot currently be replayed.

Verification: both model configurations replay all 541 Validation samples with metrics exactly matching run histories. U-Net++ research lock `ce758032…` remains separate from default Standard manifest. 15 Validation error panels created; 24 images × three requests after one warm-up per image yielded 72 successful requests, browser smoke exit 0. Full pytest: 67 passed, 8 failed, 3 warnings; no assertions changed or tests skipped. New audit scripts pass Ruff and compilation. Closure preservation check: 170 protected artifacts and 1,639 source image/target pairs unchanged, frozen split changes zero, git diff --check exit zero.

Remaining evidence: source patient/case mapping, expert label approval, independent new cohort, real professional HITL feedback. No training/selected-model Test inference or clinical result creation occurred in this audit. Final report intentionally concludes NOT FULLY READY.
