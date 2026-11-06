# Gate 1 — Tenancy and Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development, after execution authorization. All steps use unchecked checkboxes; do not execute during planning.

**Goal:** Đóng AUD-001–005 bằng policy chung, identity namespace, ownership và visit immutability.

**Architecture:** Shared DB; scope theo actor và parent-chain, constraint chống cross-link; legacy identity không tự merge.

**Tech Stack:** FastAPI, SQLAlchemy, HMAC stdlib, pytest trên SQLite/PostgreSQL cô lập.

**Spec:** [Approved design §5](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa toàn bộ [master constraints, schema contract và P/PG commands](2026-11-05-full-spectrum-remediation-plan.md). S0 và G3 T09/T10 là nền tảng. Không chạy migration/production hoặc commit tự động. Tests dùng ClinicalScenario/JWT thật.

## Review Focus

Global flag + facility không null không mở rộng quyền; parent ID khác tenant không lộ tồn tại; PID không mất số 0; rotated key không tạo người mới; lock/write race không vượt guard. Mỗi điều kiện được gắn test dưới đây.

## T01 — Policy và scope mọi đường đọc

**Files:** Modify `backend/services/facility_service.py`, `backend/app/security.py`, `backend/app/routers/admin.py`, `visits.py`, `cases.py`, `health.py`, `hitl.py`, `patient_directory.py`, `backend/services/correction_access.py`; Create `tests/test_tenant_policy_contract.py`.

**Interfaces:** `is_global_operator(user: UserModel) -> bool`; `require_facility_actor(db: Session, user: UserModel) -> str`; `scope_studies(query: Query, db: Session, user: UserModel, *, facility_id: str | None = None) -> Query`; không commit trong policy. Clinical item query scoped trả 404 nếu ngoài phạm vi, actor thiếu facility 403. Global admin chỉ metadata, không tự được đọc ảnh/note.

- [ ] **RED:** `test_unassigned_admin_is_forbidden_on_all_aggregates`, `test_global_flag_with_facility_is_invalid`, `test_facility_admin_never_sees_other_reviewer_fallback`, `test_revoked_scope_uses_current_database_identity`.
  ```python
  r = scenario.request("admin_unassigned", "GET", "/api/admin/analytics/summary")
  assert r.status_code == 403
  assert scenario.request("doctor_b", "GET", f"/api/cases/{scenario.case_a['study_id']}").status_code == 404
  ```
- [ ] **Verify RED:** `P tests/test_tenant_policy_contract.py`; kiểm tra trace route thực, không override auth hay chấp nhận AttributeError là failure đúng.
- [ ] **Implement:** tái sử dụng policy signatures ở trên cho list/detail/aggregate/CSV/audit/notifications/media và reviewer legacy; bỏ `hasattr(user,'dependency')` bypass. Query review join tập Study đã scope trước aggregation.
- [ ] **GREEN:** `P tests/test_tenant_policy_contract.py tests/test_facility_isolation_p0.py tests/test_tenant_admin_hardening.py`; PG cùng targets sau T09/T10, xác minh inactive user/facility, role clinical vs metadata và no-side-effect on denial.
- [ ] **Checkpoint:** liệt kê mọi caller đã thay, so sánh HTTP contract 401/403/404/409/422 và update test legacy đúng nghĩa; diff review, không commit.

## T02 — Settings, departments và metadata có owner

**Files:** Modify `backend/app/routers/admin.py`, `backend/db/database.py`, `backend/schemas/schemas.py`, `frontend/app/admin.js`, `frontend/app/admin-directory.js`; Create `backend/services/facility_settings.py`, `tests/test_facility_settings_versions.py`, `tests/test_admin_settings_versions.mjs`.

**Interfaces:** `read_facility_settings(db, user, facility_id: str | None) -> dict`; `write_facility_settings(db, user, facility_id: str, patch: dict, expected_version: int) -> dict`. Dùng `FacilityModel.config` hiện có và `config_version` integer cho CAS, không tạo file JSON tenant mới; departments trong cùng scope. System settings global-only tách endpoint `/api/admin/system-settings`.

- [ ] **RED:** `test_settings_a_cannot_change_b`, `test_department_membership_counts_are_scoped`, `test_two_patches_same_version_only_one_commits`, `test_global_settings_require_explicit_facility`.
  ```python
  assert scenario.request("admin_a", "PUT", "/api/admin/settings", json={"facility_id": "B", "expected_version": 1, "report_header": "Synthetic"}).status_code == 403
  ```
- [ ] **Verify RED:** `P tests/test_facility_settings_versions.py`; setup facility A/B là fixture thật, không dựa `.first()`.
- [ ] **Implement:** versioned config/department writes, field allowlist và audit cùng transaction; global không được sửa cơ sở ngầm. DTO read trả facility/version, UI gửi expected_version và hiển thị conflict.
- [ ] **GREEN:** P/PG target và `N tests/test_admin_settings_versions.mjs` (Create): stale edit hiện lỗi, không toast success hoặc ghi đè dữ liệu mới.
- [ ] **Checkpoint:** map setting thực sự dùng trên report snapshot; legacy JSON import là thao tác migration riêng, chưa chạy hay xóa file.

## T03 — PID theo issuer, HMAC có version và lookup rotation

**Files:** Modify `backend/core/patient_identity.py`, `backend/services/patient_identity.py`, `backend/db/database.py`, `backend/schemas/schemas.py`, `backend/app/routers/cases.py`, `visits.py`; Create `tests/test_patient_issuer_identity.py`.

**Interfaces:** `patient_identity_digest(source_pid: str, *, facility_id: str, issuer_id: str, secret: bytes) -> str` canonical JSON tuple UTF-8 + domain `patient-id:issuer-v1`; `resolve_patient_identity(db, user, *, issuer_id: str, source_pid: str, directory_id: str | None = None) -> PatientModel`. Issuer từ facility config allowlist, không arbitrary normalization. Adapter legacy giữ function cũ chỉ cho lookup scope-version cũ trong task T04.

- [ ] **RED:** `test_same_pid_different_issuer_or_facility_never_merges`, `test_pid_leading_zeros_and_separator_tuples_are_preserved`, `test_previous_key_lookup_keeps_patient_id`, `test_binding_identity_to_second_directory_is_conflict`.
  ```python
  assert patient_identity_digest("000123", facility_id="A", issuer_id="HIS", secret=b"x"*32) != patient_identity_digest("123", facility_id="A", issuer_id="HIS", secret=b"x"*32)
  ```
- [ ] **Verify RED:** `P tests/test_patient_issuer_identity.py`; mọi PID trong fixture là chuỗi tổng hợp có nhãn, không khai thác source patient data.
- [ ] **Implement:** unique `(facility_id,issuer_id,source_pid_hmac)`, relation directory cùng owner và keyring active/previous explicit test secrets; lookup candidates rồi update digest có khóa/CAS để giữ identity. Key không có trong keyring → quarantine/error, không tự tạo người mới. Pseudonym giữ ngẫu nhiên; no raw PID logs/URL/storage.
- [ ] **GREEN:** P/PG targets + `tests/test_patient_identity.py tests/test_facility_isolation_p0.py`; roundtrip issuer/source lookup, ambiguous/mismatched directory 409, blank research PID không tạo patient.
- [ ] **Checkpoint:** xác minh serializers/error/audit không lộ raw PID; không sửa pseudonym trên report cũ.

## T04 — Ownership constraints và báo cáo legacy không ghi DB

**Files:** Modify `backend/db/database.py`; Create `backend/services/legacy_identity_inventory.py`, `tests/test_owner_constraints.py`, `qa_isolated/test_legacy_identity_inventory.py`, `docs/deployment/full-spectrum-schema-transition.md`.

**Interfaces:** `inventory_legacy_identities(rows: list[dict]) -> dict` là pure function trả `resolvable`, `quarantine`, `counts`, `mapping_proposals`; không connect/mutate. Composite FK Study patient/directory/visit theo facility; child references xác minh prediction-image/review/region owner. Schema contract trong master là đích, không live ALTER.

- [ ] **RED:** `test_cross_facility_foreign_keys_rejected`, `test_missing_issuer_never_guesses_link`, `test_shared_legacy_patient_requires_mapping_review`.
  ```python
  result = inventory_legacy_identities([{"patient_id":"legacy", "facility_id":"A", "issuer_id":None}])
  assert len(result["quarantine"]) == 1
  assert result["mapping_proposals"] == []
  ```
- [ ] **Verify RED:** unit qua runner + `P tests/test_owner_constraints.py` trên schema mới, không gọi `_migrate_patient_facility_scope`.
- [ ] **Implement:** FK/index trong schema đích, inventory immutable mapping manifest và runbook kiểm tra counts/checksum; phân biệt backfill xác định với record mơ hồ. Unique digest global cũ không được để giữ constraint vô tình trái namespace mới.
- [ ] **GREEN:** unit/P/PG như trên, verify delete/deactivate không cascade mất clinical history. Mọi migration execution/migration test ghi `BLOCKED_PERMISSION` đến khi được phép riêng.
- [ ] **Checkpoint:** runbook có preflight, backup prerequisite, mapping review, stop condition và forward/rollback verification; không auto-run ở startup.

## T05 — Visit idempotency, linkage và locked-write guard

**Files:** Modify `backend/app/routers/visits.py`, `cases.py`, `inference.py`, `reviews.py`, `corrections.py`, `backend/services/review_service.py`, `region_clinical_service.py`, `case_lease_service.py`; Create `backend/services/study_write_access.py`, `tests/test_visit_immutability_contract.py`.

**Interfaces:** `require_writable_revision(db, user, study_id: str, *, revision_id: str | None, expected_version: int | None = None) -> tuple[StudyModel, object | None]` kiểm tra locked Visit và finalized workspace, không tự commit. `attach_study_once(db, user, *, study_id: str, visit_id: str, request_id: str) -> StudyModel`; lock order Visit→Study→children.

- [ ] **RED:** `test_attach_twice_returns_409_even_unlocked`, `test_visit_lock_vs_attach_has_single_valid_winner`, `test_every_mutation_is_blocked_under_locked_visit`, `test_retry_create_episode_does_not_duplicate_visit`.
  ```python
  assert scenario.request("doctor_a", "POST", "/api/v1/visits", json={"study_id":scenario.case_a["study_id"], "request_id":"synthetic-retry"}).status_code == 409
  ```
- [ ] **Verify RED:** `P tests/test_visit_immutability_contract.py`; race dùng barrier/hai connection thật, không sleep suy đoán.
- [ ] **Implement:** service transaction/CAS cho attach/lock/create-episode, reject reparent; trước T13 guard dùng Study/Visit và status-final hiện có, trả `(study,None)` cho RUO legacy chưa có clinical workspace và từ chối revision_id chưa được hỗ trợ. T13 mở rộng cùng signature sang ClinicalRevision, không import model chưa tồn tại. Guard tất cả upload/delete/predict/calibrate/intake-side/review/correction/region writes. PostgreSQL row locks; SQLite write transaction có retry bounded chỉ khi replay an toàn.
- [ ] **GREEN:** P/PG target + leases/review/correction regressions. Test rollback không để Visit trống hoặc audit thiếu; optional telemetry retry không được mở ghi clinical cũ.
- [ ] **Checkpoint G1:** đầy đủ role/owner/race matrix; chặn finalize/lock clinical cho tới checklist G4 được tích hợp, không tự đánh dấu clinical-ready.
