# Milestone 1 split snapshot

These four files were recovered byte-for-byte from `origin/main` at commit `0155b9a` (2026-09-18). They document the Milestone 1 dataset and are kept separate from the October 3 retraining split and the later synthetic PID mapping.

| File | Rows | SHA-256 |
| --- | ---: | --- |
| `train.csv` | 215 | `f008f1169e67bc82c3c41d43b4afa4443c3cdb334accd5827092083fecbd2c6d` |
| `val.csv` | 46 | `6596f673b9dfedffb87d9fa0374ff4aae637b04bff0426e82719e42759f120b8` |
| `test.csv` | 46 | `b3ddebc86023344c1727cd3b7011dcbb762ed61e53ca37aa0932c38858591c90` |
| `kltn_ground_truth_307.csv` | 307 | `9534bab535c87d8d2f78d65c65e5498a5e33e11483ec401d87fea21bb6c01f52` |

None of these files matches the `original_split_sha` values in `checkpoints/retrain_2d_2026-10-03_stable/run_config.json`. Do not use this archive to claim bit-for-bit reproduction of the October 3 training run.
