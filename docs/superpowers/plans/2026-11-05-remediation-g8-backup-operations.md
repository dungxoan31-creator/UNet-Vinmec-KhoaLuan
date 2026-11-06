# Gate 8 — Backup Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. No backup/restore job runs during planning.

**Goal:** Đóng AUD-035 và chứng minh backup scope/manifest/restore an toàn trong phần mở rộng vận hành.

**Architecture:** UI trình bày records rõ; whole-database backup global-only; database/media/snapshot checksum cùng manifest, không suy restore success từ file tồn tại.

**Tech Stack:** Existing BackupService, SQLAlchemy, stdlib archive/hash/subprocess, frontend JS; PostgreSQL native tooling chỉ nếu đã có và được cho phép trên sandbox.

**Spec:** [Approved design §12](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master](2026-11-05-full-spectrum-remediation-plan.md), T00, G1 global scope, G3 dialect/readiness và G4 snapshot manifest. Không tạo destructive restore/delete UI; không chạy production backup, retention deletion hay native Postgres command chưa được cho phép.

## Review Focus

Archive legacy thiếu metadata, metadata-only không có ảnh, archive traversal, PG cấu hình nhưng SQLite backup cũ và backup file còn khi audit fail. T29/T30 kiểm tra riêng.

## T29 — Backup history như dữ liệu vận hành có trạng thái thật

**Files:** Modify `frontend/app/admin.js`, `backend/app/routers/admin.py`, `backend/services/backup_service.py`; Create `tests/test_backup_history_ui.mjs`, `tests/backup_history_e2e.cjs`; Extend `tests/test_tenant_admin_hardening.py`.

**Interfaces:** `renderBackupHistory(items: Array<BackupHistoryItem>) -> string`; DTO `id,created_at,size_bytes,scope,kind,schema_version,status,verification_status`; missing legacy fields nullable, verification_status='UNVERIFIED', không đoán full/restore success. UI time/capacity format đọc được, empty/error/retry accessible.

- [ ] **RED:** `test_legacy_archive_is_unverified_not_restorable_success`, `test_history_has_headers_not_raw_json`, `test_facility_admin_cannot_list_global_archives`, `test_missing_manifest_fields_render_as_unknown`.
  ```javascript
  assert.ok(html.includes('Thời gian') && html.includes('Dung lượng'));
  assert.ok(html.includes('Chưa xác minh'));
  assert.equal(html.includes('"backup_filename":'), false);
  ```
- [ ] **Verify RED:** N target + P scope; no archive real content mở để sinh UI test; use synthetic BackupHistoryItem records.
- [ ] **Implement:** render table/native semantics, bytes formatting, no visible filesystem absolute paths; list global-only policy T01, protected API fail before side effect. Không thêm giả version/trạng thái vào archive legacy.
- [ ] **GREEN:** N/P/PG and B admin history empty/legacy/new/error synthetic; keyboard navigation và date sorting ổn định.
- [ ] **Checkpoint AUD-035:** UI pass chỉ đóng trình bày, không đóng restore/HA/readiness.

## T30 — Backup manifest, consistency và sandbox restore contract

**Files:** Modify `backend/services/backup_service.py`, `backend/app/routers/admin.py`; Create `backend/services/backup_manifest.py`, `tests/test_backup_manifest_contract.py`, `qa_isolated/test_archive_restore_boundary.py`, `docs/deployment/full-spectrum-backup-restore-runbook.md`; Extend `tests/test_backup_service_sandbox.py`.

**Interfaces:** `build_backup_manifest(db_snapshot: dict, media_entries: list[dict], artifact_entries: list[dict]) -> dict`; `validate_backup_manifest(manifest: dict, *, expected_scope: str) -> list[str]`; `restore_to_empty_sandbox(archive: Path, sandbox_root: Path, *, run_id: str) -> dict` chỉ test/operator tool ngoài app startup, từ chối target không trống/outside root/symlink/traversal. Live restore cần quyền riêng, không có API tự động production.

- [ ] **RED:** `test_metadata_only_not_complete_media_restore`, `test_archive_traversal_and_symlink_rejected_before_extract`, `test_postgres_backend_never_reads_sqlite_db_path`, `test_failed_audit_commit_has_no_successful_backup_record`, `test_restored_revision_media_hashes_match`.
  ```python
  assert validate_backup_manifest(metadata_only, expected_scope="FULL_SYSTEM")
  assert restore_result["snapshot_hashes"] == original_snapshot_hashes
  assert restore_result["patient_mapping_count"] == original_mapping_count
  ```
- [ ] **Verify RED:** unit runner/P targets trên synthetic archive/fresh empty test DB only. PG native dump/restore không available/authorized thì test ghi BLOCKED, không mock production tooling rồi gọi restored.
- [ ] **Implement:** manifest gồm schema/app/model/template versions, snapshot DB identity, media/artifact hashes, loại/phạm vi, encryption-layer declaration. SQLite online backup đúng connection; PG native dump theo quyền cung cấp, không DB_PATH fallback. Atomic staged archive + audit job/outbox trạng thái rõ; failure không báo success, orphan cleanup chỉ run-owned artifact khi được phép.
- [ ] **GREEN:** bounded synthetic SQLite restore counts/FKs/source media/report hash; PostgreSQL restore thật chỉ vào disposable DB được cấp riêng và fresh marker; no app startup/migration legacy. No-retention deletion trong job mặc định.
- [ ] **Checkpoint G8:** runbook có key custody/encryption/retention/restore evidence owner còn cần cơ sở phê duyệt; không tạo số liệu RPO/RTO hoặc claim encrypted từ filename.
