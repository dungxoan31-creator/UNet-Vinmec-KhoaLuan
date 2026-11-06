# Maximum Accuracy & Reliability AI Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Optimize ovarian ultrasound lesion segmentation and research classification on the available development cohort while preserving RUO scope, data-isolation controls, and human-in-the-loop safeguards. Software metrics in this plan do not establish clinical safety or performance.

**Architecture:**
1. Enhanced U-Net++ with scSE (Spatial and Channel Squeeze-and-Excitation) attention decoder and multi-scale feature aggregation.
2. Advanced Hybrid Loss combining Focal-Tversky (penalizing False Negatives on small lesions < 30 mm, β=0.7), Soft-Dice, and BCE.
3. Two-stage ultrasound domain pretraining (MMOTU 2D 1,000 pairs) followed by target fine-tuning with differential learning rate schedules.
4. Validation threshold calibration, test-time augmentation (TTA), and multi-model ensembling.

**Tech Stack:** PyTorch 2.6, segmentation-models-pytorch 0.5.0, MONAI, Albumentations, OpenCV, CUDA 12.4.

**Spec:** `MODEL_CARD.md`, `AGENTS.md`, `docs/v21-acceptance-baseline.md`.

## Global Constraints
- Preserve image-level split deduplication with SHA-256. Do not create or invent patient IDs.
- Preserve 512x512 Letterbox preprocessing with aspect ratio preservation and CLAHE enhancement (clip limit 2.0, grid 8x8).
- Do not access or evaluate on the test split during model development and tuning.
- All external dependencies and repositories live in `external_sources/` or `.venv`.
- Production inference path must retain complete compatibility with FastAPI `/inference` and clinical workstation canvas.

## Review Focus
1. Memory limit on 4GB VRAM GPU: Batch size 2 with gradient accumulation step 2 keeps peak VRAM < 3.7GB without paging.
2. Metric consistency: Maintain exactly identical evaluation formulas for Dice, IoU, Recall, Precision across experiments.
3. Checkpoint verification: Verified SHA-256 (`67624bbb0e50e236df7b5c82736eaadab1ff1fff5547c5e813bca545c2dd2045`) recorded in `evaluation/selected_model.json`.
4. Small-region pixel recall: Focal-Tversky uses asymmetric false-negative weighting ($\beta=0.7$); the available aggregate validation summary does not establish performance by physical lesion size.
5. Regression suite: Record exact test counts and evidence for each run; investigate failures and never treat a passing software suite as proof of zero defects or clinical safety.

---

### Task 1: Baseline Audit & Loss Function Engineering
- [x] Verify baseline performance of U-Net++ ResNet34 with TTA (Val Dice: 0.8185, IoU: 0.7338, Recall: 0.8533, Precision: 0.8335).
- [x] Implement `AdvancedHybridLoss` in `ai_training/loss.py` incorporating Focal-Tversky ($\alpha=0.3, \beta=0.7, \gamma=0.75$), Soft-Dice, and BCE.
- [x] Verify loss differentiability and gradient stability via unit tests in `tests/test_advanced_loss.py` (4/4 passed).

### Task 2: Architecture Exploration (scSE Attention & Backbone Comparison)
- [x] Implement `build_scse_unetplusplus` supporting ResNet34 with scSE attention in `ai_training/train_boosted_unetplusplus.py`.
- [x] Train candidate models on training partition with Mixed Precision (`torch.amp.autocast`) and gradient accumulation.
- [x] Record validation metrics (Dice, IoU, Recall, Precision) on all 541 validation images. Native Dice reached 0.8313 (+1.43%).

### Task 3: Stage-wise Ultrasound Domain Pre-training & Target Fine-tuning
- [x] Nạp trọng số Stage 1 từ MMOTU 2D (1,000 images pre-training, SHA-256: `095f80479e31798bc62721eb17c21f99c70079d694277f0fd987c92cfa75333f`).
- [x] Fine-tune on target training split using Differential Learning Rates (Encoder: 2e-5, Decoder: 1e-4).
- [x] Apply Cosine Annealing with Warmup for smooth convergence; early stopping triggered at Epoch 13 (converged at Epoch 7).
- [x] Compare validation curves against ImageNet-only initialization (+1.71% Dice improvement).

### Task 4: Inference Optimization & Threshold Grid Search
- [x] Implement multi-threshold grid search (0.30 to 0.50 in steps of 0.05) with Horizontal-Flip TTA.
  - Threshold 0.50: Peak standalone Dice **0.8356**, IoU **0.7538**, Recall **0.8650**, Precision **0.8508**.
  - Threshold 0.40: Validation-set segmentation pixel recall **0.8726**, Dice **0.8351**, IoU **0.7526**, Precision **0.8430**.
- [x] Evaluate ensembling strategies (averaging prediction probabilities of complementary architectures).
  - Highest recorded validation metrics among evaluated configurations (0.5 scSE + 0.5 Baseline, threshold 0.45): Dice **0.8431**, IoU **0.7622**, Recall **0.8752**, Precision **0.8533**.
- [x] Select a validation operating point using the development metrics; this selection is not a clinical safety determination.

### Task 5: Experimental 8-Class Classifier Accuracy Boost
- [x] Train enhanced ResNet34 classifier on MMOTU 8-class with label smoothing and balanced sampling (`ai_training/search_classifier_8class.py`).
- [x] Evaluate validation macro-F1, accuracy, and per-class recall:
  - Best trial (Trial 2): Accuracy **0.6844** (up from baseline 0.4499 / 0.5821), Macro-F1 **0.6056**, High-Grade Serous Recall **0.6000**. Checkpoint SHA-256: `35737b75c89b983a5b51846aba45aebea3144b8d09f70f1e3cfc1f08b1118a92`.

### Task 6: Comprehensive Verification & System-wide Integration
- [x] Generate comparative before/after scoreboard.
- [x] Save best verified checkpoint with SHA-256 hash (`67624bbb0e50e236df7b5c82736eaadab1ff1fff5547c5e813bca545c2dd2045`).
- [x] Update `evaluation/selected_model.json` and `MODEL_CARD.md`.
- [x] Update `backend/services/inference_engine.py` to seamlessly auto-detect scSE decoder blocks and load checkpoints.
- [x] Run the recorded test battery; investigate failures and report exact counts. Passing software tests do not prove zero regressions or clinical validation.
