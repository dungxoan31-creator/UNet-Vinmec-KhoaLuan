# Gate 4 — Clinical Revisions and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. Do not implement while preparing this plan.

**Goal:** Đóng AUD-014–015, AUD-017, AUD-033–034 và xây clinical revision/finalization/amendment/release có thẩm quyền theo spec đã duyệt.

**Architecture:** Clinical workspace và snapshot tách biệt; finalized revision bất biến; policy/authorization version kiểm tra lại ở commit; signature provider nằm ngoài transaction.

**Tech Stack:** FastAPI/SQLAlchemy, canonical JSON/SHA-256 stdlib, existing viewer/region/report services, pytest/Playwright.

**Spec:** [Approved design §8, §14.3](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master schema/API contract](2026-11-05-full-spectrum-remediation-plan.md), T00, G1–G3. Clinical workflow là phần mở rộng mới, không chỉ UI sửa label. Schema mới chỉ provision sandbox fresh; migrations tồn tại và external clinical evidence cần grant/đầu vào riêng. Không fake chữ ký/provider/evidence production.

## Review Focus

Baseline workspace không đổi sau finalize; source calibration/region revision không stale; policy/author revoke trước commit; provider callbacks out-of-order/replay; directory edit không đổi report cũ. Tests T13–T20 pin các trường hợp này.

## T13 — Clinical revision model và owner workspace

**Files:** Create `backend/db/clinical_models.py`, `backend/services/clinical_revision_service.py`, `tests/test_clinical_revision_contract.py`; Modify `backend/db/database.py`, `backend/schemas/schemas.py`, `backend/services/study_write_access.py`, existing clinical mutation routers.

**Interfaces:** models theo master; `get_working_revision(db,user,study_id: str,revision_id: str | None) -> ClinicalRevision`; `require_editable_revision(db,user,revision_id: str,expected_version: int) -> ClinicalRevision`; `create_baseline_revision(db,user,study_id: str) -> ClinicalRevision`. Services không auto commit; baseline tạo trong transaction create Study của T05/T07.

- [ ] **RED:** `test_finalized_workspace_rejects_every_legacy_write`, `test_revision_image_must_belong_to_same_study`, `test_only_one_draft_revision_per_study`, `test_directory_changes_do_not_rebind_revision_identity`.
  ```python
  lease = scenario.lease_headers("doctor_a", scenario.case_a["study_id"])
  scenario.seed_finalized_snapshot(scenario.case_a["study_id"])
  assert scenario.request("doctor_a","POST",f"/api/images/{scenario.case_a['image_id']}/calibrate?pixel_spacing_mm=0.1",headers=lease).status_code == 409
  ```
- [ ] **Verify RED:** `P tests/test_clinical_revision_contract.py`; thêm helper test `seed_finalized_snapshot(study_id: str) -> dict` ghi synthetic snapshot/revision rõ vào DB đã cô lập (không auth override hay production shortcut); lấy lease trước khi freeze. Phải kiểm tra đúng denial reason, không chấp nhận 422 do gửi sai contract query/body hoặc fixture không lấy được lease.
- [ ] **Implement:** revision-image and calibration references, append-only data constraints, write guard current revision/lease/expected_version. Update new image/review/region writes mang revision context; finalized baseline thiếu amendment_id trả conflict, không fallback. Giữ immutable source files/checksum.
- [ ] **GREEN:** P/PG target + review/lease/correction tests đã chuyển context; make_scenario từ T10 seed baseline DRAFT và DTO expose clinical_revision_id/version.
- [ ] **Checkpoint:** schema sentinel kiểm tra required tables/columns và version; chưa migration DB cũ, chưa bật clinical capability.

## T14 — Region/caliper visibility, provenance và calibration revision

**Files:** Modify `frontend/app/assessment-layout.js`, `viewer.js`, `region-review.js`, `cdss-panel.js`, `backend/services/region_assignment_service.py`, `region_clinical_service.py`, `calibration_service.py`, `source_measurements.py`, `backend/app/routers/inference.py`; Create `tests/test_region_revision_safety.py`, `tests/clinical_region_recovery_e2e.cjs`; Extend `tests/test_spacing_numeric_safety.py`.

**Interfaces:** `calibration_candidate(decoded, metadata: dict) -> dict` trả `status=CANDIDATE|VERIFIED|UNAVAILABLE`, `source`, `spacing_mm`, `calibrated: bool`, `requires_confirmation: bool`; ruler không có đơn vị luôn CANDIDATE/calibrated=false. Existing get_automatic_calibration gọi helper này để giữ contract giữa upload/preflight/replay. `append_calibration_revision(db,user,image_id,revision_id,confirmed_scale: dict) -> CalibrationRevision`; reuse region functions nhưng bắt reference clinical/calibration revision.

- [ ] **RED:** `test_regular_ticks_without_unit_never_verify_mm`, `test_mask_or_calibration_change_invalidates_region_context`, `test_retry_reuses_request_id`, `test_region_assignment_is_keyboard_reachable`.
  ```python
  assert candidate["status"] == "CANDIDATE"
  assert candidate["calibrated"] is False
  assert saved_review["max_diameter_mm"] is None
  ```
- [ ] **Verify RED:** P target và `B tests/clinical_region_recovery_e2e.cjs`; vùng test gồm hai component tổng hợp có mask không rỗng, không chỉ inspect empty-mask panel.
- [ ] **Implement:** chỉ di chuyển control nghiệp vụ khỏi hidden/inert; không unhide tất cả internal data. Measurement đọc đúng source transform/calibration version; thay mask/spacing đánh dấu stale, old review snapshot không đổi. API manual confirmed scale validate finite/positive; chưa hiệu chuẩn chỉ px.
- [ ] **GREEN:** P/PG region/spacing/source-mask targets + browser fail request→retry→reload; no AI label/O-RADS tự ghi như bác sĩ xác nhận.
- [ ] **Checkpoint:** nguồn units/descriptor và owner-chain có trong saved assessment; calibration unverified không leak mm qua response extras hoặc report.

## T15 — ClinicalAuthorization và EvidenceRecord

**Files:** Extend `backend/db/clinical_models.py`, `backend/schemas/schemas.py`; Create `backend/services/clinical_authority.py`, `backend/app/routers/clinical_governance.py`, `tests/test_clinical_authority.py`; Modify `backend/app/main.py` router registration.

**Interfaces:** `require_clinical_authorization(db,user,facility_id: str,permission: str,*,at: datetime) -> ClinicalAuthorization`; `register_evidence(db,user,payload: dict) -> EvidenceRecord`; `grant_clinical_authorization(db,user,payload: dict) -> ClinicalAuthorization`; `revoke_clinical_authorization(db,user,authorization_id: str,expected_version: int,reason: str) -> dict`. UTC aware timestamps, allowed permissions only clinical_report_author/facility_clinical_approver.

- [ ] **RED:** `test_doctor_role_alone_has_no_clinical_authorization`, `test_missing_expired_revoked_evidence_does_not_grant`, `test_profile_cannot_self_promote`, `test_authority_revoked_after_preflight_is_rechecked`. Integration finalize race nằm ở T17 để T15 không phụ thuộc endpoint chưa tồn tại.
  ```python
  with pytest.raises(HTTPException) as exc:
      require_clinical_authorization(db, doctor_a, "A", "clinical_report_author", at=now)
  assert exc.value.status_code == 403
  ```
- [ ] **Verify RED:** `P tests/test_clinical_authority.py`; add helper `report_snapshots(study_id=None)->list[dict]` đọc test DB; seed only explicit test evidence with run marker, not ordinary role factory auto grant.
- [ ] **Implement:** API `/api/admin/clinical-evidence`, `/api/admin/clinical-authorizations` và `/{id}/revoke`; operator registration đòi reference quyết định có thẩm quyền đã xác minh theo quy trình cơ sở, không user-supplied is_verified. Tách quyền operator do deployment provision trusted, không dựa profile. Bản chưa verified chỉ evidence draft.
- [ ] **GREEN:** P/PG boundary expiry exactly-now, grant/revoke CAS, current DB role after JWT old; important audit cùng transaction, no PII/secret log.
- [ ] **Checkpoint:** Không có nguồn xác minh institutional evidence thì production grant bị chặn. Tests không được coi là xác nhận tư cách bác sĩ thật.

## T16 — FacilityReleasePolicyVersion và màn hình điều hành

**Files:** Create `backend/services/release_policy.py`, `frontend/app/admin-clinical-governance.js`, `tests/test_release_policy_contract.py`, `tests/test_clinical_governance_ui.mjs`; Extend `clinical_governance.py`, `clinical_models.py`, schemas, `frontend/app/admin.js`.

**Interfaces:** `evaluate_release_policy(db,user,facility_id: str,*,snapshot: dict,at: datetime) -> dict` trả `allowed`, `blockers`, `policy_id`, `policy_version`, `evidence_versions`, `signature_requirement`; `approve_policy(db,user,policy_id,expected_version)->dict`; `revoke_policy(...,reason)->dict`. Policy approved immutable; revoke event/version counter được khóa lúc release.

- [ ] **RED:** `test_admin_can_prepare_but_cannot_medically_approve`, `test_global_operator_may_revoke_but_not_reopen`, `test_policy_requires_exact_model_schema_template_scope`, `test_policy_decision_after_revoke_is_blocked`. Late provider callback test thuộc T18.
  ```python
  assert scenario.request("admin_a","POST",approve_url,json={"expected_version":1}).status_code == 403
  assert decision["allowed"] is False and decision["blockers"]
  ```
- [ ] **Verify RED:** P/N targets; `approve_url` là `/api/admin/clinical-policies/{policy_id}/approve`. Actor clinical_approver_a seed theo T15 mới được approve.
- [ ] **Implement:** endpoint `/api/admin/clinical-policies` create/read + approve/revoke; UI draft/evidence/status/blocker theo role, không thêm arbitrary document manager. Signature requirement INTERNAL_ATTESTATION hoặc VERIFIED_DIGITAL được cơ sở phê duyệt, không tự chọn fallback. UTC expiry kiểm tra mỗi request.
- [ ] **GREEN:** P/PG + N: same-scope policy edits CAS, version approved không overwrite; revoked/missing evidence author thấy lý do chặn, UI không gọi clinical-ready từ healthy model.
- [ ] **Checkpoint:** policy/evidence registration không thay thế thẩm định; mọi mẫu demo thuộc run tổng hợp và không bật vận hành thật.

## T17 — Finalization atomically tạo snapshot bất biến

**Files:** Create `backend/services/clinical_finalization.py`, `backend/app/routers/clinical_workflow.py`, `tests/test_clinical_finalization.py`; Modify `backend/schemas/schemas.py`, `backend/services/review_service.py`, `backend/services/study_write_access.py`, `backend/app/main.py`.

**Interfaces:** `finalize_revision(db,user,study_id: str,revision_id: str,request: FinalizeRevisionRequest,*,now: datetime) -> ReportSnapshot`; `build_report_snapshot(db,revision) -> dict`; `validate_finalization_checklist(db,user,revision,*,now: datetime) -> list[str]`. DTO `request_id: UUID`, `expected_revision_version: int`, `expected_review_revision: int`, lease/page IDs, confirmed conclusion/applicability và `current_password: SecretStr` dùng transient để verify_password với credential DB hiện hành. Không chấp nhận boolean/client proof thay reauthentication, không lưu current_password vào idempotency hash/audit/snapshot/log. Canonical JSON `sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False` UTF-8 SHA256; lists deterministic by stable IDs.

- [ ] **RED:** `test_stale_or_unseen_image_prevents_finalization`, `test_same_key_same_payload_returns_same_snapshot`, `test_same_key_different_payload_is_409`, `test_revoke_between_check_and_commit_cannot_finalize`, `test_finalize_and_edit_cannot_both_commit`.
  ```python
  assert retry.json()["snapshot_id"] == first.json()["snapshot_id"]
  assert mutation.status_code == 409
  assert snapshot_hash_before == snapshot_hash_after
  ```
- [ ] **Verify RED:** P target; add helpers direct read snapshots/row states; compare bytes/hash persisted, not just toast.
- [ ] **Implement:** transaction order Visit→Study→ClinicalRevision→authority/policy version guards; reread và kiểm credential/token_version DB, validate §8.4 checklist, reauthentication server-side, audit + snapshot + finalized pointers commit once. Redact validation/error output của secret fields; không ghi request body vào trace. Optional analysis telemetry failure warns separately, not fake failed clinical commit. Files/media referenced phải durable trước ACK.
- [ ] **GREEN:** P/PG races, transaction failure injection/ambiguous commit verify by request key; no duplicate snapshots, no partial freeze, unsigned state never called released.
- [ ] **Authority trust-root check:** grant/approve paths không mở chỉ bằng role ADMIN. Initial clinical approver/authority operator phải có quyết định institution được đối soát qua quy trình provisioning riêng; thiếu nguồn xác minh trả NOT_CONFIGURED và giữ clinical mode blocked. Fixture synthetic cấp rõ hai permissions chỉ trong run-owned DB; không có production default trust-root từ demo seed.
- [ ] **Checkpoint:** finalize may succeed internal attestation only within configured permission, but clinical release remains a separate policy/provider operation; no native print implied signature.

## T18 — Release request/outbox, signature event và artifact

**Files:** Create `backend/services/report_release.py`, `backend/services/report_artifact.py`, `tests/test_report_release_events.py`; Extend clinical_workflow router/models/schemas; Modify `report_generator.py`, `health.py`.

**Interfaces:** `request_report_release(db,user,snapshot_id: str,request_id: str,expected_policy_version: int) -> ReleaseRequest`; `record_signature_result(db,*,job_id: str,event_id: str,snapshot_sha256: str,verification: dict) -> ReportReleaseEvent`; `release_artifact(db,user,snapshot_id: str) -> tuple[str,str]` trả approved artifact path/hash. `dispatch_release_job(job_id: str) -> dict` thực I/O ngoài transaction, production NOT_CONFIGURED nếu chưa có provider contract.

- [ ] **RED:** `test_wrong_snapshot_callback_never_releases`, `test_replayed_or_out_of_order_callback_is_idempotent`, `test_provider_timeout_has_no_success_label`, `test_revoke_during_render_or_provider_wait_prevents_publish`.
  ```python
  assert scenario.released_snapshot_ids() == []
  assert callback_result["status"] != "RELEASED"
  assert artifact_sha256 == snapshot_recorded_artifact_sha256
  ```
- [ ] **Verify RED:** `P tests/test_report_release_events.py`; provider double lives only in tests and cannot be selected by production env. No HTTP outbound tới provider thật.
- [ ] **Implement:** verify signature result authenticity qua approved provider contract mới có quyền enable; chưa contract thì chỉ internal handler tests, provider-specific routes BLOCKED_EXTERNAL. Persist staged artifact/checksum, CAS evidence/policy/authority at release commit, outbox retry cùng key, audit access. READ artifact đúng snapshot, không re-render mutable case để in lại.
- [ ] **GREEN:** P/PG injected render/commit/network failure, artifact source images retain checksum/laterality; no DB lock held during I/O. Missing external provider chỉ BLOCKED, không label verified digital.
- [ ] **Checkpoint:** release policy INTERNAL_ATTESTATION không mang nhãn chữ ký số; provider unavailable không fallback sang kiểu ký yếu hơn. Clinical flag per facility/evidence version.

## T19 — Amendment và khóa Visit theo checklist

**Files:** Extend `clinical_revision_service.py`, `clinical_finalization.py`, `clinical_workflow.py`, `study_write_access.py`, `backend/app/routers/visits.py`; Modify `frontend/app/review.js`, `viewer.js`, `cases.js`; Create `tests/test_clinical_amendments.py`, `tests/clinical_amendment_e2e.cjs`.

**Interfaces:** `open_amendment(db,user,study_id: str,parent_snapshot_id: str,reason: str,request_id: str) -> ClinicalRevision`; `cancel_revision(db,user,revision_id: str,expected_version: int,reason: str) -> dict`; `lock_clinical_visit(db,user,visit_id: str,expected_version: int) -> dict`. Một draft amendment/Study; same study_id, parent snapshot immutable; visit locked luôn block amendment trong phiên bản này.

- [ ] **RED:** `test_amendment_does_not_create_new_study`, `test_current_release_unchanged_until_new_revision_released`, `test_calibration_or_mask_edit_creates_new_revision_data`, `test_pending_signature_or_draft_blocks_visit_lock`, `test_locked_visit_rejects_amendment`.
  ```python
  assert amendment["study_id"] == original["study_id"]
  assert old_snapshot_bytes_after == old_snapshot_bytes_before
  assert pending_lock.status_code == 409
  ```
- [ ] **Verify RED:** P target, Browser target sau endpoint; race duplicate amendments unique constraint must yield one active draft.
- [ ] **Implement:** reference/copy-on-write revision assets, no file overwrite, explicit amendment context cho edits và technician assignment; old artifact current đến new valid release. Disposition CANCELLED có actor/reason/audit, không hard delete. Visit lock đánh giá toàn tập studies dưới lock, không bỏ draft bằng query filter.
- [ ] **GREEN:** P/PG + browser finalize→release→amend→new review→release→reopen, old artifact downloadable unchanged; cancelled amendment không tăng case denominator G5.
- [ ] **Checkpoint:** legacy signed statuses chưa có snapshot/evidence không tự trở thành verified release; UI chỉ rõ historical/unverified, không auto unlock để sửa.

## T20 — Report semantic contract và privacy truth

**Files:** Modify `frontend/app/report-preview.js`, `backend/services/report_generator.py`, `dicom_privacy.py`, `research_export.py`, `backend/app/routers/reviews.py`; Extend `tests/test_fe_02_report_preview.mjs`, `test_report_generator_security.py`, `test_dicom_scope_guard.py`; Create `tests/test_report_semantic_contract.py`.

**Interfaces:** `build_report_view(snapshot: dict) -> dict` trong report_artifact.py là nguồn display model chung; `reportContralateralStatus(study, side)` hiện có được giữ enum/domain; RUO browser và server clinical render không tự phát sinh conclusion/risk từ AI. Research export kiểm tra trusted evidence, không checkbox-only.

- [ ] **RED:** `test_all_contralateral_states_survive_preview_and_pdf`, `test_unverified_calibration_never_prints_mm`, `test_directory_edit_never_changes_released_artifact`, `test_metadata_minimization_never_claims_pixels_deidentified`.
  ```python
  assert source_status == saved_status == report_status == "SURGICALLY_ABSENT"
  assert dicom_result.PatientIdentityRemoved == "NO"
  assert "Đủ tiêu chuẩn chẩn đoán" not in report_text
  ```
- [ ] **Verify RED:** P/N targets; images/dicom đều synthetic, no patient archive opened. PDF text extraction chỉ dùng dependency đang có, không cài thêm.
- [ ] **Implement:** exact no-image vs NOT_VISUALIZED vs SURGICALLY_ABSENT mapping; IQA technical label; reviewer/AI attribution, unconfirmed source flags. Publish clinical report chỉ qua snapshot artifact G4, không unguard `/api/generate-report` legacy.
- [ ] **GREEN:** P/PG service/request contracts, Node render cases + browser prepare print, compare extracted PDF text và per-side image checksum/mask identity. Không coi screenshot-only là test provenance pass.
- [ ] **Checkpoint G4:** independent clinical validation, provider và external consent/de-identification evidence thiếu vẫn BLOCKED; UI/DTO phản ánh cùng lý do.
