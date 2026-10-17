# SDD Progress Ledger — 2026-10-17-core-scope-evidence-closure

**Plan**: `docs/superpowers/plans/2026-10-17-core-scope-evidence-closure.md`  
**Spec**: `docs/superpowers/specs/2026-10-17-thesis-core-scope-design.md`  
**Branch**: `accuracy-experiments-2026-10-09`  
**Base commit**: `25af869`  

## Tasks Overview
- [x] Task C01: Đối chiếu ba mốc trước với bằng chứng có thật (`docs/evaluation/milestone_scope_matrix.csv`)
- [ ] Task C02: Một policy nghiệm thu chung, bỏ default tạo bằng chứng giả (`scripts/build_evaluation_report.py`, `scripts/verify_evaluation_release.ps1`, tests)
- [ ] Task C03: Phân loại provenance session và đếm người tham gia đúng (`evaluation/hitl_analysis.py`, `scripts/export_hitl_sessions.py`, `docs/evaluation/hitl_session_provenance.csv`, tests)
- [ ] Task C04: Full regression hiện hành thay vì bốn file được chọn (`scripts/verify_evaluation_release.ps1`, `tests/test_release_evidence.py`)
- [ ] Task C05: Giữ independent Test gate và chốt nhánh dữ liệu (`docs/evaluation/milestone_scope_matrix.csv`, `docs/evaluation/test_access_ledger.csv`)
- [ ] Task C06: Nghiệm thu manual/demo và đối chiếu artifact trước đóng mốc (`docs/evaluation/manual_acceptance.md`, `docs/evaluation/release_runbook.md`, `MODEL_CARD.md`, `docs/evaluation/2026-10-18-core-acceptance.md`)
- [ ] Task C07: Báo cáo KLTN và bảo vệ từ 19/10 (`docs/evaluation/thesis_handoff.md`, `docs/evaluation/milestone_scope_matrix.csv`)

## Progress Log
- Task C01: complete — mapped all 16 milestone requirements across 4 periods (06/09–20/09, 21/09–05/10, 06/10–18/10, Từ 19/10) to verified artifacts, blockers, and limitations in `docs/evaluation/milestone_scope_matrix.csv`.

