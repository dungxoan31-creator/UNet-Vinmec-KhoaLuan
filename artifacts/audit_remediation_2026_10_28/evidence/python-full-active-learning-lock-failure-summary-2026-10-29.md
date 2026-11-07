# Initial full-suite failure summary — 2026-10-29

This is a concise record of the first full-suite console output, not a raw pytest log.

- Command: `.venv/Scripts/python.exe -m pytest -q`
- Result before fix: `1 failed, 1,254 passed, 2 skipped` in 196.45 seconds.
- Failing test: `tests/test_v21_active_learning_review.py::test_log_active_learning_sample_is_jsonl_safe_across_processes`.
- Exception: Windows `PermissionError: [Errno 13]` at `lock_file.flush()` while competing spawned processes initialized the same empty `.lock` sidecar before acquiring the OS byte-range lock.
- Fix: remove the unprotected sidecar initialization write; acquire the Windows byte-range lock at offset 0 on the empty sidecar.
- Retest: the concurrency test passed five consecutive runs; the full suite then passed `1,255 passed, 2 skipped` in 193.09 seconds. The two skipped tests remain unverified.
