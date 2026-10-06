# Unified Vinmec Dataset Audit and Training Plan

> Execution follows the owner's 12-step repository audit and training request.

**Goal:** Validate mappings across the six named Vinmec roots, then train/evaluate the existing Standard U-Net only if target provenance and leakage-safe splits are demonstrable.

**Architecture:** Extend the existing sample-ID audit rather than replace loaders or model code. Preserve each source path and split snapshot; create audit outputs and a canonical index only for unambiguous image-target pairs. Training and metrics are gated on complete mapping, source overlap, and split validation.

**Tech Stack:** Python, PyTorch, OpenCV, pandas, existing Standard U-Net and evaluation code.

**Spec:** User request in the current conversation; project constraints in `AGENTS.md`.

## Global Constraints

- Never modify or delete source dataset files.
- Never pair by directory order; use verified IDs/metadata and record ambiguous cases.
- Never include Test in training or model/threshold selection.
- Do not treat duplicate copies or synthetic identifiers as independent patients.
- Record the limitation explicitly: source Patient/Case IDs are unavailable, so this run establishes image-hash separation only.
- Do not stage raw datasets, credentials, caches, or unrelated working-tree changes.

## Review Focus

- Nested and duplicated source trees: identify exact content duplicates before aggregation.
- Multiple annotation variants per stem: no choice without verified equivalence/canonical rule.
- M1 derived empty masks: preserve as flagged artifacts; do not treat as clinical negatives.
- Missing patient identity: sample-level separation is not patient-level leakage control.
- Dataset-specific preprocessing/channel differences: verify against existing loaders before training.

## Tasks

### Task 1: Inventory and trace existing pipeline

- [x] Inspect root structure, Git status/remotes, dependencies, README, split snapshots, U-Net, loaders, training and evaluation entrypoints.
- [x] Inspect all six dataset roots and existing audit outputs for exact source-specific directory conventions.

### Task 2: Dataset validation and canonical mapping

- [x] Add `scripts/validate_vinmec_datasets.py` using explicit observed directory adapters and the existing audit helper.
- [x] Report inventory, mapping/readability/shape issues, duplicate content, split conflicts, and exact affected rows under `reports/dataset_validation*`.
- [x] Create `dataset/index.csv` and a baseline-compatible split manifest with one verified binary target per image, preserving source paths and roles.
- [x] Exclude the 35 images associated with M1 fallback masks; validate duplicate-source targets agree after binarization.

### Task 3: Split and leakage gate

- [x] Audit existing manifests, source lists, M1 CSVs, and exact image hashes without rewriting any split; record manifest hashes and conflicts.
- [x] Resolve split conflicts with conservative precedence `Test > Validation > Train`; no image hash crosses splits.
- [x] Record that source Patient/Case IDs remain unavailable; split independence is image-level only.

### Task 4: Conditional training and evaluation

- [x] Run the existing U-Net on Train and select the best checkpoint on Validation only; hold Test until final model selection.
- [x] Save a new run directory, best/last checkpoint, config and history; historical checkpoints were not overwritten.
- [x] Evaluate once on the held-out Test split after model selection; compute overall/per-source metrics and trace predictions.

### Task 5: Verification and Git delivery

- [x] Verify training mappings, hash-disjoint split, checkpoints, metrics and prediction masks.
- [ ] Run tests, review Git diff and selectively commit/push only intended artifacts; preserve unrelated working-tree changes.
