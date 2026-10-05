# Vinmec Unified Dataset Audit — Gate Report

**Status: BLOCKED BEFORE TRAINING**
**Scope:** Read-only validation of the six requested dataset roots. No source data, split manifest, checkpoint, or model weights were changed. No training or evaluation was started.

## Dataset inventory

Counts below are per-root audit records and overlap across directories; they must not be summed as independent samples.

| Dataset root | Audit records* | Readable image–target pairs | Split evidence (Train / Val / Test) | Pair issues |
|---|---:|---:|---:|---|
| `Vinmec` | 1,639 | 1,639 | 1,602 / 948 / 415 | Two annotation files per image; exact copies overlap other roots |
| `Vinmec_2D` | 1,202 | 1,202 | 1,197 / 730 / 410 | Includes source Test; split evidence conflicts with other snapshots |
| `Vinmec_CEUS` | 170 | 170 | 155 / 113 / 5 | Overlaps CEUS sources and split snapshots |
| `vinmec_m1_307` | 307 | 272 | 303 / 196 / 117 | 35 derived masks are empty and have image-shape mismatch |
| `vinmec_ovarian` | 1,407 | 1,372 | 1,352 / 843 / 415 | 35 fallback masks unresolved; native source labels are separate |
| `vinmec_splits` | 307 | 272 | 303 / 196 / 117 | 35 derived masks are empty and have image-shape mismatch |

*The `vinmec_ovarian` audit-record count includes 35 fallback-mask references associated through M1 CSVs; it has 1,372 physical image files. Split-evidence counts include records appearing in multiple manifests and may be conflicted; they are not a proposed split. The authoritative report lists exact source paths and hashes.

## Mapping and data integrity

- The observed schemas provide an image and one target role (`annotation`, `label`, or `mask`). They do not provide four distinct files (`image + annotation + label + mask`) for each sample. No aliases were invented, and `dataset/index.csv` was not created.
- The `Vinmec` annotation folder has 3,278 annotation files for 1,639 images (two variants per numeric ID). Where the existing auditor verified both variants to have equivalent binary masks, it recorded the selected binary path; this does not create additional label/mask artifacts.
- Exact image hashing found 1,372 repeated SHA-256 values and 3,358 additional copied file paths across the adapters. The six roots therefore overlap and cannot be treated as six independent datasets.
- The M1 manifests list 35 empty fallback masks: all 35 files exist, decode, are all-zero 512×512 images. Their archived CSV rows identify the associated image and native label path. All 35 native labels are readable, positive, and match their source image dimensions. The fallback and native target disagree; `dataset/vinmec_ovarian/empty_masks/PROVENANCE.json` is absent. These records remain unresolved and are excluded from a training-ready mapping.
- No verified source patient/case IDs were found. M1 `ANON-VINMEC-PID-*` values are synthetic partition metadata and do not establish patient-level independence.

## Split and training gate

- 936 exact image hashes have incompatible Train/Validation/Test assignments across source lists and existing manifests. Exact examples and all evidence are in `dataset_validation_split_conflicts.csv`.
- The `full_dataset_2026-10-03` split is sample-level, includes source Test images in its input pool, and cannot establish patient-level isolation.
- `ai_training/train_full_unet.py` currently includes the source Test directory in its training pair groups and has no Validation loader; it is not safe for this run.
- Because target mapping, patient/case separation, and split provenance are unresolved, no canonical index, training run, checkpoint, or new metrics were produced. Test images were read only for file, mapping, and split-integrity audit; none were used for training, model selection, or evaluation.

## Evidence files

- `reports/dataset_validation.json` — complete machine-readable audit and blocking conditions.
- `reports/dataset_validation.csv` — per-root counts.
- `reports/dataset_validation_samples.csv` — per-record paths, IDs, split evidence, hashes, and status.
- `reports/dataset_validation_issues.csv` — exact problematic paths and reasons.
- `reports/dataset_validation_duplicates.csv` — duplicate image hashes and paths.
- `reports/dataset_validation_split_conflicts.csv` — conflicting assignments and source evidence.
- `scripts/validate_vinmec_datasets.py` — repeatable read-only validator.

## Software verification

- `PYTHONPATH=. .venv\Scripts\pytest.exe -q`: **61 passed**, 4 upstream/deprecation warnings.
- `ruff check scripts/validate_vinmec_datasets.py`: **passed**.
- `ruff check .`: **failed on 5 pre-existing lint findings** in unrelated working-tree scripts: `scripts/audit_cleanup.py`, `scripts/detailed_inspection.py`, and `scripts/execute_safe_cleanup.py`. These files were not changed in this audit.
- Python compile check for the validator: **passed**.

## Required resolution before training

Obtain source-authorized patient/case mapping and provenance for the 35 disputed labels; decide which dataset artifact is the canonical target for each sample; reconcile the 936 split conflicts into a patient/case-disjoint Train/Validation/Test manifest; then validate the exact loader input schema. Only after those gates pass should the existing U-Net be trained and metrics computed.
