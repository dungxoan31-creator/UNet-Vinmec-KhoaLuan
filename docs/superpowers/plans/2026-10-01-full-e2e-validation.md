# Full E2E validation run — 2026-10-01

**Goal:** Verify one complete technical path from a raw Vinmec validation image and mask through preprocessing, U-Net inference, saved prediction/metrics, API, browser editing, confirmation, and reopening.

**Architecture:** Reuse the existing Standard U-Net checkpoint, validation evaluator, FastAPI service, and Canvas frontend. Run in the current dirty workspace so uncommitted code and local checkpoint are included; do not branch, commit, retrain, or use the test set.

**Tech stack:** Python 3.12, PyTorch, OpenCV, FastAPI, pytest, Node.js, Playwright Core, headless Chrome.

**Evidence boundary:** Vinmec has no verified patient identifiers. Its split and metrics are image-level. Synthetic patient IDs are demo-only and are excluded from training, evaluation, and claims. Browser confirmation is an automated simulation, not a clinician review.

## Tasks

- [x] 1. Freeze inputs: verify validation CSV count and first image/mask, selected checkpoint path/hash/threshold, and absence of patient IDs in validation rows.
- [x] 2. Check the raw pair and preprocessing with focused pipeline tests; verify letterbox dimensions and image/mask alignment.
- [x] 3. Evaluate all validation cases into a new output directory; inspect summary, count masks/overlays, and compare checkpoint hash/metrics with selected-model evidence.
- [x] 4. Run the API integration smoke test for upload → predict → review → reopen using temporary storage.
- [x] 5. Benchmark local prediction API on a validation image and save measured latency.
- [x] 6. Start the actual FastAPI server and verify health/model readiness over HTTP. Port 8001 isolates this run from a pre-existing stale server on 8000; legacy admin model key remains `attention_unet` although the loaded checkpoint is Standard U-Net.
- [x] 7. Run headless browser HITL smoke: upload → segmentation → edit → confirm → reopen; stop the server afterward.
- [x] 8. Run full pytest, relevant lint/syntax checks, and diff whitespace check; distinguish unrelated/pre-existing failures.
- [x] 9. Write a concise E2E evidence report with commands, outputs, metrics, limits, and follow-up; mark this plan complete only for verified tasks.

## Success criteria

- 123 validation pairs evaluated with 123 predicted masks and no test-set inference in this run.
- Checkpoint checksum matches `evaluation/selected_model.json`; preprocessing and API/browser flows pass.
- Report explicitly distinguishes automated technical review from real clinician assessment and image-level split from patient-level split.
