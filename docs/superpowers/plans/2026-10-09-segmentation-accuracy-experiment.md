# Segmentation Accuracy Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify current image/mask inputs and measure whether a locked U-Net++ checkpoint gains Validation Dice from threshold selection or horizontal-flip test-time augmentation.

**Architecture:** Reuse the existing 512×512 dataset loader and model engine. Write new experiment artifacts to a fresh directory; leave the locked split, checkpoint, Test, and prototype selection unchanged.

**Tech Stack:** Python 3.12, PyTorch 2.6, OpenCV, pytest, RTX 3050 4 GB.

**Spec:** `docs/superpowers/specs/2026-10-09-segmentation-accuracy-evaluation-design.md`

## Global Constraints

- Preserve Letterbox 512×512, CLAHE, grayscale normalization 0.449/0.226, Combo Loss in training, HITL, and all historical artifacts.
- Do not train or select on Test; no Test inference in this plan.
- Do not label image-level scores as patient-level or diagnostic accuracy until source identity and expert mask approval are established.
- Do not print workbook Patient/Case codes or write them to experiment artifacts.
- Reject mismatched checkpoint or Validation CSV hashes before inference.
- Never overwrite an existing output directory.

## Review Focus

- Relocated `dataset/Vinmec/...` paths resolve to current `dataset/2d` and `dataset/3d`; audit must not report false missing files.
- A missing source mask copy is reported separately from binary disagreement of extant masks.
- TTA flip must be undone before averaging with native probabilities.
- Dice scoring must be mean per image at 512×512 and reproduce 0.8170359435 at threshold 0.5 for the locked checkpoint.
- Empty reference masks remain explicit and are never interpreted as clinically negative without source evidence.

### Task 1: Fresh technical data audit

**Files:** Modify `scripts/audit_milestone3_evidence.py`; create `tests/test_accuracy_audit.py`; create new artifacts under `evaluation/accuracy_2026-10-09/data_audit/`.

**Interfaces:** `data_audit(output: Path) -> None` continues to write `dataset_audit.json`; existing `backend.core.dataset_paths.resolve_dataset_path(root, relative)` resolves relocated input paths.

- [ ] Write a failing test with temporary current `dataset/2d` files and canonical old `dataset/Vinmec/Vinmec_2d` paths; assert the audit resolves image, mask and source copies, checks hash, and reports zero errors.
- [ ] Run `./.venv/Scripts/python.exe -m pytest tests/test_accuracy_audit.py -q`; expect the new test to fail because the audit reads old paths directly.
- [ ] Use the existing resolver for canonical and source paths; preserve original paths in artifact fields.
- [ ] Run the targeted test and then `./.venv/Scripts/python.exe -m pytest -q`; expect zero failures.
- [ ] Run `./.venv/Scripts/python.exe scripts/audit_milestone3_evidence.py --data-only --output evaluation/accuracy_2026-10-09/data_audit`; inspect `dataset_audit.json` for counts, errors, overlap, missing copies and empty masks.

### Task 2: Validation-only threshold and flip-TTA comparison

**Files:** Create `scripts/evaluate_accuracy_candidates.py`; create `tests/test_accuracy_candidates.py`; create new artifacts under `evaluation/accuracy_2026-10-09/candidates/`.

**Interfaces:** `score_probabilities(probabilities: np.ndarray, reference: np.ndarray, threshold: float) -> dict` returns per-image Dice, IoU, recall and precision. CLI reads the locked model manifest, checks checkpoint and split SHA-256, and writes `summary.json` plus `per_image.csv` without patient identifiers.

- [ ] Write failing tests for exact threshold behavior, empty-mask scoring, and horizontal-flip alignment using synthetic arrays.
- [ ] Run targeted tests; expect failures because the evaluator does not exist.
- [ ] Implement one Validation pass for native probabilities and one for horizontally flipped images, with flipped outputs aligned back. Evaluate fixed thresholds `0.30, 0.35, ..., 0.70` for native and averaged probabilities. Use the same AMP setting as the historical replay.
- [ ] Refuse existing output directories. Record code commit, checkpoint SHA, Validation CSV SHA, threshold grid, per-candidate mean metrics, and number of images with Dice < 0.5.
- [ ] Run targeted tests and the full pytest suite; expect zero failures.
- [ ] Run evaluator into the fresh candidates directory and compare native threshold 0.5 Dice against historical 0.8170359435 (absolute tolerance 1e-6); if this check fails, do not interpret candidate scores.

### Task 3: Evidence report and review

**Files:** Create `docs/reports/Thu_Nghiem_Cai_Thien_Do_Chinh_Xac_2026-10-09.md`.

- [ ] State exact measured baseline and candidates, checkpoint/split hashes, data-audit status, and Validation-only scope. Recommend a new threshold/TTA candidate only if Dice improves by at least 0.005 absolute and recall drops by no more than 0.02; otherwise keep threshold 0.5 as the operational baseline.
- [ ] Record that the existing Test is previously used, expert mask approval is unknown, and patient identity remains partially verified pending provider confirmation.
- [ ] Check report figures against `summary.json`, run `git diff --check`, and request one independent code review of Task 1–2 changes.
