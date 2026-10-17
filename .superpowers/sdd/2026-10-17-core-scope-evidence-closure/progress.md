# SDD Progress Ledger — 2026-10-17-core-scope-evidence-closure

**Plan**: `docs/superpowers/plans/2026-10-17-core-scope-evidence-closure.md`  
**Spec**: `docs/superpowers/specs/2026-10-17-thesis-core-scope-design.md`  
**Branch**: `accuracy-experiments-2026-10-09`  
**Base commit**: `25af869`  

## Tasks Overview
- [x] Task C01: Đối chiếu ba mốc trước với bằng chứng có thật (`docs/evaluation/milestone_scope_matrix.csv`)
- [x] Task C02: Một policy nghiệm thu chung, bỏ default tạo bằng chứng giả (`scripts/build_evaluation_report.py`, `scripts/verify_evaluation_release.ps1`, tests)
- [x] Task C03: Phân loại provenance session và đếm người tham gia đúng (`evaluation/hitl_analysis.py`, `scripts/export_hitl_sessions.py`, `docs/evaluation/hitl_session_provenance.csv`, tests)
- [x] Task C04: Full regression hiện hành thay vì bốn file được chọn (`scripts/verify_evaluation_release.ps1`, `tests/test_release_evidence.py`)
- [x] Task C05: Giữ independent Test gate và chốt nhánh dữ liệu (`docs/evaluation/milestone_scope_matrix.csv`, `docs/evaluation/test_access_ledger.csv`)
- [x] Task C06: Nghiệm thu manual/demo và đối chiếu artifact trước đóng mốc (`docs/evaluation/manual_acceptance.md`, `docs/evaluation/release_runbook.md`, `MODEL_CARD.md`, `docs/evaluation/2026-10-18-core-acceptance.md`)
- [ ] Task C07: Báo cáo KLTN và bảo vệ từ 19/10 (`docs/evaluation/thesis_handoff.md`, `docs/evaluation/milestone_scope_matrix.csv`)

## Progress Log
- Task C01: complete — mapped all 16 milestone requirements across 4 periods (06/09–20/09, 21/09–05/10, 06/10–18/10, Từ 19/10) to verified artifacts, blockers, and limitations in `docs/evaluation/milestone_scope_matrix.csv`.
- Task C02: complete — implemented unified `derive_release_status` function across report generator and verifier; eliminated hardcoded fake checkpoint hashes and fabricated participant counts; separated conditional clinician validation from evaluation completeness; verified status path agreement between `release_status.json` and `final_checks.json`; all 16 unit tests passing.
- Task C03: complete — created `docs/evaluation/hitl_session_provenance.csv` with de-identified provenance metadata and quarantine disposition; updated `evaluation/hitl_analysis.py` and `scripts/export_hitl_sessions.py` with `--participant-registry`; quarantined 4 unverified self-declared clinician sessions (verified clinicians = 0, matching study_status); separated participant counts (8 unique) from session counts (32 sessions); recorded input hashes in summary; all 15 unit tests passing.
- Task C04: complete — added `-TestScope [full|selected]` to `scripts/verify_evaluation_release.ps1`, distinguishing between full test suite (`pytest.main(['tests', ...])`) and selected release smoke suite; recorded `test_scope` in results, `baseline_results.json`, and `final_checks.json`; added tests in `tests/test_release_evidence.py`; all 9 unit tests passing.
- Task C05: complete — confirmed independent test gate remains guarded and BLOCKED in `evaluation/milestone_3_final/data_audit/independent_gate/audit.json` due to unverified source patient mapping; verified `evaluation/protocol.py` prevents evaluation run when audit status != READY; updated `docs/evaluation/test_access_ledger.csv` to record verified completed access event for `legacy_test_v1`.
- Task C06: complete — corrected checkpoint hash typo in `docs/evaluation/manual_acceptance.md` (`417828fa...97d`) with audit note; verified pre-flight launcher `scripts/run_prototype.ps1 -CheckOnly` PASS; rehearsed live E2E flow and verified export integrity via `tests/test_research_export.py` (8 passed); produced actual execution log in `docs/evaluation/2026-10-18-core-acceptance.md`; updated `README.md` with `-TestScope` instructions.


