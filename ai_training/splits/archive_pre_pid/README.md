# Split CSV snapshot before synthetic PID assignment

These three CSV files are byte-identical to the `ai_training/splits/vinmec_2d/` CSVs and to the retraining split CSVs immediately before synthetic `patient_id` values were assigned on 2026-10-04. Their SHA-256 values are recorded as `pre_pid_split_sha` in the selected checkpoint's `run_config.json` and as `split_csv_sha256_before_synthetic_metadata` in the retraining manifest.

They are **not verified copies of the CSV files used during training on 2026-10-03**. The training-time hashes recorded in `original_split_sha` differ for all three splits; none of the 342 repository CSV files scanned on 2026-10-04 matched those hashes. Retain the training-time hashes for provenance and do not use this snapshot to claim byte-for-byte reproduction of the training run.

Follow-up search on 2026-10-04 found no additional CSV files under `C:/Users/Dung/Documents`. Five ZIP archives in that directory contained no Vinmec split CSV. The usual VS Code and Cursor local-history directories were absent. Both the interrupted and stable retraining configurations contain the same training-time SHA values. The project owner confirmed there is no other backup containing the three matching CSV files.

## Frozen audit decision — 2026-10-04

> Chấp nhận giới hạn truy vết bit-to-bit của lượt huấn luyện 03/10; toàn bộ quy trình kiểm thử và đánh giá từ 04/10 trở đi được chuẩn hóa trên current_split_sha và checkpoint 5e14be...

The complete checkpoint SHA-256 is `5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e`. The `original_split_sha`, `pre_pid_split_sha` and `current_split_sha` sets remain distinct in `checkpoints/retrain_2d_2026-10-03_stable/run_config.json`. The selected inference threshold is 0.5. This decision accepts a provenance limit; it does not retroactively prove that the archived CSVs were the training inputs, nor does synthetic PID metadata establish source patient independence.

## Remote Git history check — 2026-10-04

Fetched `origin/main` at commit `0155b9a` (dated 2026-09-18) and checked all 34 CSV blobs reachable from that remote branch. None matched any of the three `original_split_sha` values recorded for the 2026-10-03 retraining run. No remote CSV was copied into this archive. The three existing CSVs still match `pre_pid_split_sha`, not `original_split_sha`.

## Local Git object check — 2026-10-04

Checked all local refs and reflogs, then ran `git fsck --full --no-reflogs --unreachable --no-progress` with zero unreachable objects reported. Compared SHA-256 for 1,644 Git blobs between 5,000 and 250,000 bytes, including objects without a `.csv` path, against all three `original_split_sha` values. No match was found. This size-bounded object scan supplements the complete path-based CSV scan above; it does not change the frozen provenance conclusion.
