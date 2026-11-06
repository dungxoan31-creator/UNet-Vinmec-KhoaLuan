# Gate 5 — Operational Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. All task steps remain NOT RUN during planning.

**Goal:** Đóng AUD-018–020 bằng đơn vị đếm rõ, latest revision và filter/CSV thống nhất.

**Architecture:** Một service analytics chọn dataset đã scope; current state tách history, image/review/study/person không dùng thay nhau.

**Tech Stack:** SQLAlchemy aggregate/query, FastAPI DTO, existing admin JS và test runner.

**Spec:** [Approved design §9](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master](2026-11-05-full-spectrum-remediation-plan.md), T01 scope, T09 dialect, T13–T19 snapshot state. No migration/production/commit. Không gọi case count là patient-independent count.

## Review Focus

Hai ảnh/hai bên/multiple reviews một Study, null khác O-RADS0, reviewer legacy khác facility, timezone khoảng ngày và chart-filter khác CSV. Được kiểm tra T21/T22.

## T21 — Current projection và metric có denominator

**Files:** Create `backend/services/operational_analytics.py`, `tests/test_current_analytics_projection.py`; Modify `backend/app/routers/admin.py`, `backend/schemas/schemas.py`; Extend `tests/test_admin_reports.py`.

**Interfaces:** `current_study_projection(db,user,*,filters: AnalyticsFilters) -> list[dict]`; `build_operational_summary(rows: list[dict]) -> dict`; `AnalyticsFilters` DTO `facility_id,from_utc,to_utc,doctor_id,status,orads,lesion_type`. Metric fields: `study_count`, `reviewed_study_count`, `finalized_study_count`, `released_study_count`, `image_count`, `review_revision_count`, `orads_image_distribution`, `orads_case_distribution`, `missingness`, `generated_at`, `scope`, `denominators`. No distinct-person metric khi không có reliable identity.

- [ ] **RED:** `test_latest_review_only_for_current_distribution`, `test_two_images_and_amendment_do_not_increase_study_count`, `test_unsigned_review_not_counted_as_finalized`, `test_orads_zero_is_not_missing`, `test_legacy_reviewer_obeys_scope`.
  ```python
  assert summary["study_count"] == 1
  assert summary["review_revision_count"] == 3
  assert summary["finalized_study_count"] == 0
  assert summary["orads_image_distribution"]["O-RADS 0"] == 1
  ```
- [ ] **Verify RED:** `P tests/test_current_analytics_projection.py`; seed one Study/two synthetic images/three append-only reviews và explicit null/0 data, không dùng model inference để sinh classification test này.
- [ ] **Implement:** latest review per image deterministically `created_at,id`, current released/finalized pointers from G4. Case-level O-RADS chỉ khi clinician case summary xác nhận; chưa có thì denominator case-unclassified, không tự max ảnh. History metric giữ riêng. Query scope/filters trước aggregate.
- [ ] **GREEN:** P/PG targets + `tests/test_admin_reports.py tests/test_tenant_admin_hardening.py`; verify zero rows và ratios no divide-by-zero/NaN, scope identity included.
- [ ] **Checkpoint:** nếu tên response legacy phải giữ tương thích thì ghi deprecation/meaning rõ, không còn UI gọi signed_count là ca đã ký khi nguồn chỉ review rows.

## T22 — Filter, drilldown, CSV và copy cùng một hợp đồng

**Files:** Modify `frontend/app/admin-reports.js`, `backend/app/routers/admin.py`; Extend `tests/test_admin_analytics_ui.mjs`; Create `tests/test_analytics_export_consistency.py`, `tests/admin_analytics_filters_e2e.cjs`.

**Interfaces:** `normalize_analytics_filters(payload: dict, *, facility_timezone: str) -> AnalyticsFilters` trong operational_analytics.py, ngày người dùng chuyển UTC interval `[start,end)` bằng timezone đã cấu hình; `renderExecutiveMetrics(summary)` hiện có nhận metric/denominator mới; CSV dùng projection/filter service T21 và download helper T11.

- [ ] **RED:** `test_drilldown_and_csv_match_summary_scope_and_filters`, `test_midnight_boundary_uses_configured_timezone`, `test_missing_timezone_is_explicit_not_machine_local`, `test_unknown_and_orads_zero_are_separate_buttons`.
  ```python
  assert csv_study_ids == drilldown_study_ids
  assert summary["denominators"]["studies"] == len(drilldown_study_ids)
  ```
- [ ] **Verify RED:** P/N targets; use UTC instants ở hai phía midnight và timezone test facility rõ ràng, không dùng clock máy để tạo expected result.
- [ ] **Implement:** UI label ca đã rà soát/hoàn tất/phát hành theo metric thật, O-RADS0 option độc lập; lower-level image/history charts có đơn vị tương ứng; CSV áp đúng mọi filter, show generated_at/scope/missingness.
- [ ] **GREEN:** P/PG consistency + N UI và B filters drilldown/download, kiểm tra cập nhật filter không ghép response stale từ request trước. No-global screenshot tables từ facility actor khác scope.
- [ ] **Checkpoint G5:** thông tin thời gian là telemetry scope được đo, không báo thời gian khám bệnh thật; docs không coi “đồng thuận mask” là hiệu quả chẩn đoán.
