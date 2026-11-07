# Caliper history current-flag regression — 2026-10-29

- Regression setup: save D1 revision 1 and D2 revision 1 for the same confirmed region, then save D1 revision 2 and read the region snapshot/history again.
- Before the fix, the new assertion failed: two D1 history rows had current=true although only revision 2 was the latest D1 measurement.
- Root cause: _caliper_event_json() checked only whether the region/review assignment and calibration matched. It did not check whether an older event had been superseded by a later revision of the same label. Idempotent replay of an older request returned the same misleading current/usable flags.
- Fix: identify the latest event independently for each label; mark only that event current, and permit CDSS usability only for that latest event. Replays of superseded requests now return current=false and usable_for_cdss=false. Historical rows remain persisted and readable.
- Verification: the initial API regression failed with D1 current-event count 2; after the fix, tests/test_region_clinical.py passed 11/11, full Python suite passed 1,265/0 skipped, and the browser/API/SQLite roundtrip passed with independent D1/D2 source-coordinate calipers, calibration and reload.
- Clinical accuracy remains unverified; this test only checks revision semantics, persistence and source-coordinate handling on synthetic data.

## Follow-up: response superseded between commit and response construction

- A second fault-injection regression committed D1 revision 2 after revision 1's commit returned but before the first request constructed its response. Before the follow-up fix, the successful-save branch called `_caliper_event_json()` with its default `latest_revision=True`; it therefore reported the now-superseded revision 1 as current and usable for CDSS.
- The successful-save branch now checks `_is_latest_caliper_revision()` after refreshing the committed row and passes that state into response serialization. The older event remains in history but is marked `current=false` and `usable_for_cdss=false`.
- Evidence: development regression failed before the fix at the `current` assertion (`caliper-save-response-superseded-development-failure-2026-10-29.log`); after the fix, `tests/test_region_clinical.py` passed 12/12 (`region-clinical-caliper-response-current-final-2026-10-29.log`), browser/API/SQLite roundtrip passed (`roundtrip-caliper-current-history-final-2026-10-29.log`), and full Python suite passed 1,266/0 skipped in 192.92 seconds (`python-full-after-caliper-response-current-fix-2026-10-29.log`).
- This verifies response currentness under a SQLite test race only. PostgreSQL concurrency and clinical measurement accuracy remain unverified.
