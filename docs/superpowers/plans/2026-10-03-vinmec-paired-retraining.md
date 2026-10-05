# Vinmec 2D paired retraining implementation plan

> Execution: implement sequentially in the current workspace, as requested. Use executing-plans, test-driven-development and verification-before-completion. Preserve existing uncommitted changes; do not commit.

**Goal:** Train a new Standard U-Net from the supplied Vinmec 2D train images and their same-stem masks, compare validation evidence and integrate only an improved checkpoint.

**Architecture:** Reuse the existing audited split builder, loader, Standard U-Net and native-resolution evaluator. Keep the source test set out of training and model selection. Write all new run artifacts separately from the currently selected checkpoint.

**Tech stack:** PyTorch/CUDA AMP, OpenCV, Albumentations, FastAPI, existing browser smoke test.

**Spec:** User request on 2026-10-03: `train_image/1.JPG` must match `train_label/label/1.PNG`; retrain the unstable segmentation model.

## Constraints
- Letterbox 512x512; bilinear image resize, nearest-neighbor binary mask resize; CLAHE; divide by 255.
- Combo loss BCE + Dice; Standard U-Net base filters 32.
- No verified patient IDs: declare image-level split, leave PID blank.
- No test-set tuning, no use of full-data/CEUS checkpoints as initialization.
- Seed 42; fresh initialization; batch size 2 if GPU memory permits; learning rate 0.0003; maximum 30 epochs; patience 8; gradient norm clip 1.0.
- Compare old/new native-resolution validation Dice at threshold 0.5; retain old model if the new one does not improve.

## Review focus
- Pairing by filename stem, never directory iteration position.
- Incorrect/non-binary/unreadable masks and mismatched dimensions must fail the audit.
- Validation metric must weight cases equally, including a partial final batch.
- Persist history every epoch so long runs are inspectable.
- UI model name must reflect API provenance.

## Task 1: Pair and preprocessing audit
- [x] Run `scripts.prepare_vinmec.prepare_splits` into `ai_training/splits/vinmec_2d_retrain_2026-10-03`.
- [x] Check source counts, no exact decoded duplicates and unchanged train/val/test membership. Train/val CSV SHA-256 matches previous manifests.
- [x] Export a pair audit CSV and six ground-truth overlays after letterboxing; inspect them.
- [x] Verify preprocessing parity between dataset loader and inference on all 820 source train images.

## Task 2: Stable, observable training
Files: `ai_training/train_baseline_unet.py`, `ai_training/dataset_loader.py`, `tests/test_retraining.py`.
- [x] Write failing checks for case-wise Dice, reproducible augmentation and per-epoch training artifacts using a small real network. RED: 3 failures reproduced.
- [x] Add fixed random seeds, case-weighted validation, gradient clipping, float32 loss arithmetic and patience stopping.
- [x] Save history and run configuration each epoch, retain best checkpoint and emit periodic batch progress.
- [x] Run targeted regression tests. GREEN: 5 passed, 2 dependency warnings.

Review checkpoint: independent reviewer identified that the previously permitted Albumentations 1.4.0 lacks `Compose.set_random_seed`. Pin `requirements.txt` to the installed and tested Albumentations 2.0.8. CUDA AMP overflow regression and scheduler guard passed; full suite after runtime fixes: 47 passed, 3 dependency warnings. Browser model-heading regression: RED hardcoded Attention U-Net versus Standard U-Net; GREEN complete HITL smoke.

## Task 3: New training run and validation comparison
- [x] Train into `checkpoints/retrain_2d_2026-10-03_stable` with the audited split, capturing console log. Completed 30 epochs, 1989.65 seconds, exit 0; best epoch 27. The first run in `checkpoints/retrain_2d_2026-10-03` stopped during epoch 4: strict gradient clipping raised on AMP overflow before GradScaler could skip/back off. A real CUDA overflow regression reproduced the failure and now passes; the interrupted run is retained.
- [x] Run existing evaluator on validation and export Dice 0.8233030566 / IoU 0.7298131589 / Recall 0.8653061599, 123 masks and 5 overlays.
- [x] Re-evaluate the old checkpoint on the same validation manifest and compare. Old Dice reproduced exactly: 0.6051128973.
- [x] Select the new checkpoint only if validation Dice improves; save the old selection manifest in the run artifacts.

## Task 4: Prototype and evidence
Files: `frontend/index.html`, `frontend/js/modules/viewer.js`, browser smoke test as appropriate.
- [x] Replace the selected workstation's hardcoded Attention U-Net heading with API model provenance.
- [x] Restart the local prototype if selection changes; verify HTTP 200, model loaded, checkpoint hash and real inference. Browser checksum check first reproduced stale server weights, then passed after restart.
- [x] Run Python regression suite and browser Upload → Predict → Edit → Confirm smoke. 47 passed, 3 dependency warnings; browser PASS. Reset double-history regression reproduced and fixed by delegating once to ACCEPTED_RAW; report button remains disabled pending validation.
- [x] Write a concise retraining report with actual results, selected checkpoint, pairing evidence and remaining limitations; update the milestone 2 report to reference the new checkpoint and metrics.
