# Gate 2 — Intake and Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. Steps remain unchecked during planning.

**Goal:** Khắc phục AUD-006–010, AUD-012–013 bằng directory trung tâm tối thiểu, episode snapshot và tài khoản đúng cơ sở.

**Architecture:** Tái sử dụng patient-directory/API có sẵn; server là nguồn chuẩn, dữ liệu lịch sử không join demographics mutable để in lại.

**Tech Stack:** FastAPI/SQLAlchemy, vanilla JS, pytest/Node/Playwright hiện có.

**Spec:** [Approved design §5.4/§6](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master](2026-11-05-full-spectrum-remediation-plan.md), T00 và G1. Không database thật/migration/commit. Existing patient-directory đã có thay đổi chưa được chứng minh; không viết API thứ hai.

## Review Focus

Directory sửa/deactivate không đổi episode cũ; same version update conflict; server offline không biến local thành synced; synthetic seeds không vào clinical roster; restart không reset password hay tăng global quyền.

## T06 — Directory và episode demographics snapshot

**Files:** Modify `backend/app/routers/patient_directory.py`, `cases.py`, `backend/db/database.py`, `backend/schemas/schemas.py`; Create `backend/services/episode_identity.py`, `tests/test_episode_identity_snapshot.py`; Extend `tests/test_patient_directory_api.py`.

**Interfaces:** `snapshot_episode_identity(directory: PatientDirectoryModel | None, *, patient: PatientModel | None, study_date: str) -> dict`; `correct_draft_episode_identity(db, user, study_id: str, *, expected_version: int, corrected_demographics: dict, reason: str) -> dict`. Lưu schema/precision/source/version trong `episode_identity_json`; chỉ sửa demographics cùng người khi chưa finalized/locked, không đổi binding.

- [ ] **RED:** `test_directory_update_is_prospective`, `test_deactivate_keeps_historical_episode_readable`, `test_stale_directory_patch_is_409`, `test_directory_cannot_rebind_existing_episode`.
  ```python
  before = scenario.request("doctor_a","GET",f"/api/cases/{scenario.case_a['study_id']}").json()["episode_identity"]
  scenario.update_directory("A", display_name="Synthetic corrected name")
  assert scenario.request("doctor_a","GET",f"/api/cases/{scenario.case_a['study_id']}").json()["episode_identity"] == before
  ```
- [ ] **Verify RED:** `P tests/test_episode_identity_snapshot.py`; bổ sung `ClinicalScenario.update_directory(facility: str, **patch) -> httpx.Response` trong helper T00, dùng API/version thật.
- [ ] **Implement:** snapshot khi create Study, explicit correction + reason/audit cho draft cùng identity, expected episode_version; read/report lấy episode copy. Hủy ca sai danh tính có disposition/lý do, không hard delete hay auto merge theo name/year.
- [ ] **GREEN:** P/PG targets + directory regressions, hai browser context cùng roster; năm sinh không thành tuổi chính xác, birth_year=None không thành 0 tuổi.
- [ ] **Checkpoint:** G4 finalized snapshot giữ episode copy; patient-ID mapping T03 là nguồn liên kết, không invent external PID để đầy form.

## T07 — Intake server-first, demo isolation và create-episode

**Files:** Modify `frontend/app/intake.js`, `intake-session.js`, `upload.js`, `state.js`, `auth.js`, `backend/app/routers/cases.py`, `backend/schemas/schemas.py`; Create `tests/test_intake_directory_contract.mjs`, `tests/intake_server_identity_e2e.cjs`; Extend `tests/test_patient_store_crud.mjs`.

**Interfaces:** `createPatientDirectoryClient(request) -> {list,create,update,deactivate}` trong `intake-session.js`, methods trả Promise server DTO có version; `clearPatientDirectoryCache({userId,facilityId}) -> void`. Create-episode API `POST /api/clinical-episodes` nhận request_id, directory_id hoặc source identity exclusive, study_date, side dispositions; trả visit_id/visit_code + study_id/study_code/visit_no một transaction.

- [ ] **RED:** `test_empty_server_list_stays_empty`, `test_server_failure_never_claims_local_save`, `test_logout_clears_only_identity_scoped_roster_cache`, `test_no_seed_or_random_patient_pid_in_normal_mode`.
  ```javascript
  assert.deepEqual(await client.list(), {items: [], total: 0, limit: 100, offset: 0});
  await assert.rejects(client.create({display_name: 'Synthetic'}));
  assert.equal(localFallbackWrites.length, 0);
  ```
- [ ] **Verify RED:** `N tests/test_intake_directory_contract.mjs tests/test_patient_store_crud.mjs`; browser target sau API G1/G2 sẵn sàng.
- [ ] **Implement:** bỏ seed/PID generator khỏi normal-mode path, giữ anonymous research Study độc lập. UI chọn directory UUID hoặc nhập PID theo issuer; không gửi cả hai mâu thuẫn. Không tự import local roster cũ; show explicit local/research-only status khi mode đó được chọn. `POST /api/clinical-episodes` gọi transaction service T05, không loop tạo Visit rồi Study không có idempotency.
- [ ] **GREEN:** `N` targets và `B tests/intake_server_identity_e2e.cjs`: hai account/cơ sở, hai context cùng tài khoản, empty list reload, duplicate retry, unilaterality + opposite status, failed-upload resume không đổi identity. Chụp màn 1440/1366/390.
- [ ] **Checkpoint:** cache key user/facility, no raw PID in localStorage/log/URL; data upload và finalization vẫn synthetic trong test.

## T08 — Bootstrap, credential lifecycle và quyền được giao rõ ràng

**Files:** Modify `backend/db/database.py`, `backend/app/security.py`, `backend/app/routers/admin.py`, `backend/app/routers/auth.py`, `backend/app/routers/corrections.py`, `backend/services/correction_access.py`, `backend/schemas/schemas.py`, `frontend/app/admin-users.js`, `frontend/app/state.js`, `frontend/app/i18n.js`, `frontend/app/navigation.js`, `frontend/app/corrections.js`, `docker-compose.postgres.yml`; Create `backend/services/account_bootstrap.py`, `tests/test_bootstrap_account_contract.py`, `tests/account_facility_onboarding_e2e.cjs`.

**Interfaces:** `bootstrap_accounts(db: Session, *, configured_facility_id: str | None, credentials: dict) -> None` chỉ chạy operator/test provisioning rõ, không startup; existing accounts không sửa password/facility/global flag. `validate_account_scope(role: str, facility_id: str | None, is_global_admin: bool) -> None`. Roles đích DOCTOR/REVIEWER/TECHNICIAN/ADMIN; legacy SENIOR/TK cần mapping evidence, không tự nâng role.

- [ ] **RED:** `test_existing_password_and_global_flag_survive_bootstrap`, `test_missing_configured_facility_fails_before_creating_user`, `test_global_admin_onboarding_requires_facility_for_doctor`, `test_clinical_roles_not_granted_through_free_text`.
  ```python
  before = scenario.account_security_state("admin_unassigned")
  scenario.bootstrap_existing_accounts()
  assert scenario.account_security_state("admin_unassigned") == before
  ```
- [ ] **Verify RED:** `P tests/test_bootstrap_account_contract.py`; helper `account_security_state(actor)->dict` đọc hash/token/global fields trong test DB; `bootstrap_existing_accounts()->None` chỉ gọi new bootstrap service, không init_db/migrate.
- [ ] **Implement:** exact configured facility lookup, fail-fast message, no `.first()` fallback; modal global admin bắt chọn facility, server ép scope admin cơ sở. Wire DOCTOR/REVIEWER/TECHNICIAN/ADMIN nhất quán auth DTO, frontend role map/navigation và correction service; không coi REVIEWER/TECHNICIAN có quyền ký. Existing SENIOR/TK chưa đối soát được giữ legacy restricted, không tự chuyển quyền hoặc sửa user rows ở startup. Account invite/reset có audit/revocation/temp-password handover; role alias migration chỉ thiết kế bảng đối soát. Compose yêu cầu operator cung cấp `APP_DOCTOR_FACILITY_ID`, không mặc định tên bệnh viện.
- [ ] **GREEN:** P/PG targets + auth reset/revocation tests đã được preflight; `B tests/account_facility_onboarding_e2e.cjs` tạo tổng hợp→handover→first-password→case cùng cơ sở→restart readonly→password mới vẫn hợp lệ. Không gửi email/credential thật.
- [ ] **Checkpoint G2:** source path bootstrap không còn được gọi từ import/lifespan, doctor/reviewer/technician scopes tách; chưa cấp clinical author/approver bằng role đơn thuần.
