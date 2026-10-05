# Hoàn thiện sản phẩm lõi theo yêu cầu GVHD — Implementation Plan

> **For agentic workers:** Execute tasks in order; each checkbox needs direct evidence. Do not commit or push without an explicit request.

**Goal:** Deliver a reproducible, honest research prototype for raw image/mask → preprocessing → Standard U-Net → mask/overlay/metrics → upload → review/edit/confirm → reopen.

**Architecture:** Keep the existing FastAPI/PyTorch/Canvas stack and selected validation checkpoint. Add only safeguards and evidence needed for a reliable Mốc 2 handoff. Preserve image-level dataset labeling and never present simulated reviewer activity as clinician validation.

**Tech Stack:** Python 3.12, PyTorch, OpenCV, FastAPI, SQLite, JavaScript Canvas, pytest, headless Chrome.

**Spec:** `docs/superpowers/specs/2026-09-28-moc-2-gvhd-requirements.md` and the teacher's milestone message provided by the user.

## Constraints

- No verified Patient IDs or participating doctor have been supplied as of 01/10/2026; those requirements cannot be completed by inventing data or identities.
- Do not tune on the source test set; it was already viewed on 29/09, so it cannot be called a fresh independent patient-level test.
- Keep letterbox 512×512, grayscale/CLAHE, Dice+BCE training loss, selected checkpoint SHA-256, and editable RLE mask flow.
- Do not add diagnosis/LLM/report suggestions while core segmentation and HITL evidence remain the priority.
- Work in the current dirty workspace to retain local checkpoint and uncommitted changes. No destructive cleanup, branch, commit, or push.

## Tasks

- [x] 1. Audit the teacher's requirements against code, tests, data, and artifacts; record a pass/partial/external-blocker matrix with source paths.
- [x] 2. Add a failing API test for upload with a nonexistent study; fix orphaned file creation and verify no file/DB row remains.
- [x] 3. Add failing tests for review action/mask consistency and invalid action; enforce the same contract for both review endpoints without claiming a simulated reviewer is a doctor.
- [x] 4. Remove fabricated default patient/reviewer identity from the core upload/review flow; record elapsed Canvas review time instead of fixed zero; verify browser submission and saved case.
- [x] 5. Update handoff documentation: checkpoint availability/checksum, current validation/API evidence, false historical claims, remaining external prerequisites, and run commands.
- [x] 5a. Disable legacy clinical PDF export that can fill missing measurements with fabricated defaults; verify UI and API cannot export it.
- [x] 5b. Keep simulated reviews out of doctor-approved and confirmed-ground-truth dashboard counts; test with a stored simulated review.
- [x] 6. Run focused tests, full pytest, Ruff/JS syntax, validation-only E2E, and browser smoke on an isolated port; publish results and mark only evidenced tasks complete.

## External acceptance gates — not software tasks

- Verified source mapping from `image_id` to real anonymized Patient ID is required before patient-level split or patient-independent metrics can be claimed.
- A consenting clinician and a documented protocol are required before reporting doctor acceptance, review time, or clinical usefulness.
- Truly independent evaluation requires a suitable unseen dataset, ideally external with verified grouping and normal controls; the already viewed Vinmec 2D test set is not a fresh blind test.
