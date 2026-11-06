# Gate 3 — Database and Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. No test execution is authorized by this planning document alone.

**Goal:** Đóng AUD-011, AUD-016, AUD-031–032 và xác định đúng failure bootstrap bằng bằng chứng cô lập.

**Architecture:** Session-bound dialect helper; fresh schema provision ngoài startup; JWT/actor fixtures không sửa semantics production.

**Tech Stack:** SQLAlchemy dialect PostgreSQL/SQLite, pytest, Node, stdlib subprocess; không thêm migration framework.

**Spec:** [Approved design §7](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master/T00](2026-11-05-full-spectrum-remediation-plan.md). T09/T10 là phần nền tảng chạy trước G1 integration. Không gọi old init_db hoặc migration tests; existing-data upgrade vẫn cần quyền riêng. Lệnh P/PG/N/B chỉ áp dụng sau T00.

## Review Focus

Session đang bind engine khác global; transaction rollback/retry upsert; fixture null/false còn nguyên; người dùng bấm CSV không gửi bearer qua anchor; nhiều inference worker có thể vượt process-local admission. Có test ở T09–T12.

## T09 — SQL đúng dialect từ session thực thi

**Files:** Create `backend/db/dialect.py`, `tests/test_session_dialect_contract.py`; Modify `backend/app/routers/auth.py`, `backend/services/patient_identity.py`, `case_lease_service.py`, `backend/db/database.py` tại sequence upsert/query.

**Interfaces:** `insert_for(db: Session, table_or_model) -> Insert` chọn `db.get_bind().dialect.name`; unsupported raises ValueError trước write. Caller giữ conflict target, where/CAS và transaction. `next_study_visit_no(db: Session) -> str` giữ six-digit technical Study code, không phải Visit identity.

- [ ] **RED:** `test_insert_uses_session_not_global_engine`, `test_auth_lease_identity_upserts_execute_on_each_dialect`, `test_sequence_concurrency_is_unique_and_capacity_fails_closed`, `test_unsupported_dialect_never_falls_back`.
  ```python
  assert insert_for(postgres_session, PatientModel).__class__.__module__.startswith("sqlalchemy.dialects.postgresql")
  assert len(set(synthetic_visit_numbers)) == len(synthetic_visit_numbers)
  ```
- [ ] **Verify RED:** P/PG `tests/test_session_dialect_contract.py`; compile assertions chỉ hỗ trợ chẩn đoán, RED/GREEN endpoint phải execute trên DB sandbox.
- [ ] **Implement:** thay SQLite insert tại mọi caller được `rg -n 'sqlite_insert|on_conflict|returning' backend -g '*.py'` tìm thấy; validate constraint targets khớp schema T03. Test transactions không dùng unsupported RETURNING/JSON/date semantics âm thầm khác nhau.
- [ ] **GREEN:** P/PG target + auth limiter, case lease, patient identity/idempotency regressions; hai concurrent requests cùng key chỉ một record, mismatch payload 409, rollback không tiêu thụ visit_no sai ngoài contract.
- [ ] **Checkpoint:** PG không được cấp sandbox thì ghi BLOCKED, không sửa capability postgresql_supported=true chỉ vì SQLite xanh.

## T10 — Fixture explicit và bootstrap lỗi có nguyên nhân

**Files:** Modify `tests/conftest.py`, `tests/helpers/fixture_factory.py`, `tests/fixture_factory.py`, `tests/helpers/clinical_scenario.py`, `tests/serve_isolated_app.py`; Create `tests/test_fixture_identity_contract.py`, `qa_isolated/test_bootstrap_facility_selection.py`; Modify các test authorization liên quan nếu đang dựa default quyền.

**Interfaces:** `make_actor(db, *, role: str, facility_id: str | None, is_global_admin: bool=False, is_active: bool=True) -> UserModel`; `make_study(db, *, facility_id: str, **fields) -> StudyModel`; `make_scenario(engine, *, run_id: str) -> ClinicalScenario`. Fixture không listener sửa constructor/SQL, không defaults ADMIN global. Real JWT encode và DB current-user check.

- [ ] **RED:** `test_explicit_null_facility_false_global_stay_unchanged`, `test_facility_insert_is_not_replace`, `test_bootstrap_other_facility_does_not_satisfy_configured_facility`, `test_dependency_overrides_are_empty_for_tenant_tests`.
  ```python
  actor = make_actor(db, role="ADMIN", facility_id=None, is_global_admin=False)
  assert actor.facility_id is None and actor.is_global_admin is False
  assert app.dependency_overrides == {}
  ```
- [ ] **Verify RED:** unittest qua runner cho bootstrap pure/empty-db test; `P tests/test_fixture_identity_contract.py`; thu full trace, không chạy `test_migration_is_idempotent` khi chưa có quyền.
- [ ] **Implement:** bỏ global init/after_create/INSERT OR REPLACE hooks, giữ setup explicit và cleanup chỉ run-owned resources. Reproduce FK semantics bằng fresh schema với facility X tồn tại nhưng configured facility Y không tồn tại; xác định missing referenced row, không thêm no_autoflush để che bug. Startup/schema checks T00 không gọi migration.
- [ ] **GREEN:** P/PG factory/tenant targets, synthetic account lifecycle T08 khi sẵn; fixture migration cũ ghi blocked cho tới grant riêng. Không bulk-rewrite assertion 403→200 hoặc gán facility cho negative test để pass.
- [ ] **Checkpoint:** inventory test còn phụ thuộc constructor magic và chia nhóm chuyển đổi; full suite chưa an toàn thì không gọi green toàn repo. S0 test guard phải tiếp tục pass sau thay conftest.

## T11 — Download CSV authenticated và lỗi không thành file thành công

**Files:** Modify `frontend/app/api.js`, `frontend/app/admin-reports.js`, `backend/app/routers/admin.py`; Create `tests/test_authenticated_download.mjs`, `tests/admin_csv_download_e2e.cjs`, `tests/test_admin_csv_scope.py`.

**Interfaces:** `downloadAuthenticated(path: string, filename: string, {signal}={}) -> Promise<void>` dùng state bearer hiện có, validate status/content-type trước blob, sanitize filename, revoke ObjectURL; server `render_safe_csv(rows: list[dict], columns: tuple[str,...]) -> str` escape formula-prefix cells không sửa clinical source.

- [ ] **RED:** `test_download_uses_bearer_and_no_query_token`, `test_401_response_is_error_not_csv`, `test_object_url_revoked_on_success_and_abort`, `test_csv_cannot_export_other_facility`.
  ```javascript
  await assert.rejects(downloadAuthenticated('/api/admin/reports/cases/export-csv', 'cases.csv'));
  assert.equal(downloadClicks.length, 0);
  assert.equal(capturedUrl.includes('token='), false);
  ```
- [ ] **Verify RED:** `N tests/test_authenticated_download.mjs`; `P tests/test_admin_csv_scope.py`. Mocks tạo capturedUrl/downloadClicks ngay trong test, không production browser global fake.
- [ ] **Implement:** thay cả hai anchor export handler, UI busy/error; filter query giống chart/drilldown; scope T01 và CSV injection protection. Không lấy password/token từ localStorage hoặc ghi JWT vào URL.
- [ ] **GREEN:** N/P/PG targets và `B tests/admin_csv_download_e2e.cjs`, kiểm tra download event/content fixture, 401/revoked session không có file, no cross-facility row.
- [ ] **Checkpoint AUD-016:** trước dùng link trong report, helper xử lý API-session mismatch/abort đúng pattern hiện có; không mở export research đang bị khóa.

## T12 — Deployment truth, readiness và resource admission

**Files:** Modify `backend/app/routers/health.py`, `backend/services/model_service.py`, `deploy/systemd/ovarian-ai-backend.service`, `docker-compose.postgres.yml`, `docs/deployment/HOSPITAL_DEPLOYMENT_GUIDE.md`, `docs/clinical_validation/CLINICAL_VALIDATION_PACKET.md`; Create `tests/test_deployment_capability_contract.py`, `docs/deployment/full-spectrum-capability-matrix.md`.

**Interfaces:** `runtime_capabilities(db, user=None) -> dict` tách software/runtime support với clinical release policy G4; giữ clinical flags false khi thiếu evidence. Inference admission vẫn bounded; cấu hình worker không vượt số process được đo an toàn, không mặc định chạy 4 model GPU.

- [ ] **RED:** `test_schema_mismatch_readiness_is_503_without_ddl`, `test_postgres_not_advertised_from_compile_only`, `test_clinical_gate_not_implied_by_healthy_model`, `test_inference_process_budget_matches_deployment_config`.
  ```python
  assert response.json()["clinical_production_ready"] is False
  assert startup_sql_mutations == []
  ```
- [ ] **Verify RED:** `P tests/test_deployment_capability_contract.py`; startup_sql_mutations được thu bằng instrumentation trên DB fresh, không tắt guard.
- [ ] **Implement:** capability matrix implemented/verified/blocked cho PACS/HIS/RLS/signature/restore; remove misleading wording, không thêm connector giả. Cấu hình default một process inference cho tới test VRAM/CPU/admission budget có bằng chứng; vẫn giữ concurrency queue bounded.
- [ ] **GREEN:** P/PG và syntax/config static checks; resource benchmark tổng hợp bounded chỉ sau quyền thực thi và giới hạn tài nguyên cụ thể, không stress production. Không có GPU benchmark thì đánh dấu NOT TESTED, không ghi throughput giả.
- [ ] **Checkpoint G3:** runbook có exact safe startup/provision distinction; metrics/capabilities không chứng nhận lâm sàng. Diff review; không chạy Docker/deploy/commit trong planning.
