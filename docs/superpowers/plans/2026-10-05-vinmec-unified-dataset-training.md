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
- Do not train while annotation/label/mask mapping or patient/case separation is unresolved.
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
- [x] Withhold `dataset/index.csv`: the required four distinct paths are not present in the observed schema; ambiguous records are listed and training is blocked.

### Task 3: Split and leakage gate

- [x] Audit existing manifests, source lists, M1 CSVs, and exact image hashes without rewriting any split; record manifest hashes and conflicts.
- [x] Stop: source patient/case identities are unverified, and 936 exact image hashes have incompatible split assignments.

### Task 4: Conditional training and evaluation

- [ ] Only after Tasks 2–3 pass, run the existing U-Net entrypoint on Train with Validation-only checkpoint/threshold selection.
- [ ] Save a new run directory, best/last checkpoint, config and history; do not overwrite historical checkpoints.
- [ ] Evaluate once on the sealed Test split after model selection; compute overall/per-source metrics and trace predictions.

### Task 5: Verification and Git delivery

- [ ] Verify training mappings, leakage, checkpoints and metrics. **Not applicable until blockers are resolved.**
- [ ] Run code tests and review Git state. Commit/push only a validated deliverable when the working tree is safe; current tree contains unrelated deletions and prior untracked work, so do not stage or push this partial audit.
