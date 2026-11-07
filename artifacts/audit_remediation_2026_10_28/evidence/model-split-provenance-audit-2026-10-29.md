# Audit evidence — selected checkpoint split provenance (2026-10-29)

## Observed artifact state

- `evaluation/selected_model.json` points to `checkpoints/boosted_unetplusplus_scse_2026-10-27/run_summary.json` for training and selection evidence.
- That run summary contains checkpoint hash, initialization checkpoint, loss, epoch counts, and validation metrics. It does not contain `split_dir`, `split_integrity`, train/validation/test CSV hashes, or a split manifest hash.
- The legacy summary has `test_split_accessed: false`. This field alone does not define whether test files were read for integrity checks or used to train/select the model.
- The exact historical input split cannot be reconstructed from this artifact. No split metadata was added retroactively.

## Current source behavior

- `ai_training/train_baseline_unet.py::validate_training_split_integrity()` iterates `train`, `val`, and `test`. It opens each CSV, resolves each image and mask, hashes both files, decodes them, checks dimensions/binary masks, and rejects cross-split duplicate image content.
- `ai_training/train_boosted_unetplusplus.py::run_training()` builds training and validation loaders only; optimization, checkpoint selection, and threshold calibration run on train/validation. It does not construct a test loader or compute test metrics.
- The generic trainer now writes the split directory plus SHA-256 hashes for `manifest.json`, `train.csv`, `val.csv`, and `test.csv`; `split_integrity` names inspected partitions, and `test_split_used_for_training_or_selection` is explicitly false.
- The official MMOTU directory `ai_training/splits/mmotu_2d_official_2026-10-27` contains its train/validation partitions but no `test.csv`. Running the generic validator against it exited 1 with `Required test split is missing`; the MMOTU Stage 1 pipeline uses its own validator for the official train/validation lists and does not read a test partition.

## Interpretation

The generic trainer's source data audit reads the held-out test partition to verify image-level integrity, while model fitting and selection remain restricted to train/validation. Reports must describe those as separate facts. The selected checkpoint's legacy boolean and missing split hashes are insufficient to prove its historical data use or reproduce its input split, so its training provenance remains **BLOCKED**.
