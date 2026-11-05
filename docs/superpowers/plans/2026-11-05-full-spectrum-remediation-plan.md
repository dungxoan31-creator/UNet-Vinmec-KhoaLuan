# Full-Spectrum Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task, only after separate execution authorization. Steps use checkbox (`- [ ]`) syntax for tracking. This turn authorizes planning only; do not execute these steps now.

**Goal:** Khắc phục 35 finding qua 8 gate và xây workflow hồ sơ lâm sàng tập trung, revision bất biến và phát hành có thẩm quyền trên database dùng chung.

**Architecture:** Giữ FastAPI/SQLAlchemy/PyTorch/vanilla JS; policy và ownership theo cơ sở được kiểm tra cả query, service, constraint và export. PostgreSQL là mục tiêu vận hành; SQLite được kiểm chứng riêng. ClinicalRevision, ReportSnapshot và policy evidence bổ sung workflow, không biến RUO thành clinical-ready bằng boolean.

**Tech Stack:** Python hiện có trong `.venv`, FastAPI, SQLAlchemy, pytest, Node test runner, playwright-core đã cài; không mặc định thêm dependency/service.

**Spec:** [Thiết kế APPROVED](../specs/2026-11-05-full-spectrum-remediation-design.md).

**Plan status:** DRAFT FOR REVIEW — thiết kế đã duyệt, implementation plan chưa được duyệt/thực thi. File này và tám gate plan là một bộ; không thực hiện gate riêng mà bỏ qua contract/safety prelude.

## Global Constraints

- **PLANNING ONLY:** Không chạy các lệnh test, bootstrap, migration, backup/restore hay triển khai trong giai đoạn viết kế hoạch. Mọi checkbox dưới đây chưa thực hiện.
- Không production DB, dữ liệu bệnh nhân thật, deploy, đổi weights, cài dependency hoặc commit worktree chưa rà soát diff. Sau duyệt plan vẫn cần quyền thực thi riêng.
- Migration vẫn cần cho phép rõ ràng riêng; duyệt thiết kế không cấp quyền chạy migration. Mọi task migrate legacy chỉ được viết/kiểm tra tĩnh cho tới khi có quyền chạy trên sandbox đích đã xác minh.
- Giữ FastAPI, SQLAlchemy, PyTorch và SPA JavaScript hiện có; không xây framework tenancy/RBAC hoặc service mới ngoài nhu cầu.
- Giữ image-level split có khử trùng lặp SHA-256, letterbox 512×512 và HITL. Patient-level independence chưa được xác minh.
- Core training scope là Dice+BCE. Không đổi manifest để giả lineage, không tự huấn luyện lại.
- Không tạo PID bệnh nhân giả; ca nghiên cứu không định danh không yêu cầu patient ID. Fixture tổng hợp phải được gắn nhãn riêng.
- Review, attestation nội bộ, verified digital signature, release và clinical readiness là các trạng thái khác nhau. Thiếu evidence thì clinical release fail closed.
- Bảo toàn thay đổi sẵn có. Spec/plan audit 25 finding ở `audit/2026-11-04/` không thay thế bộ AUD-001–035 tại `artifacts/full_spectrum_audit_20261104/`.
- Mỗi task: RED có nguyên nhân xác định → thay đổi nhỏ nhất tại owner → GREEN có log → diff/checkpoint; không tự commit. Nếu behavior đã pass từ thay đổi trước, ghi characterization pass và bổ sung test cho gap, không cố tạo failure giả.

## Review Focus

1. **Authorization thay đổi giữa request:** revoke quyền/policy sau preflight phải ngăn commit release — T15/T17/T18.
2. **Ca nhiều ảnh/revision:** history không làm tăng số ca và không tái dùng region/calibration cũ — T14/T19/T21.
3. **Định danh không đơn giản:** PID có số 0 đầu, dấu phân cách, nhiều issuer hoặc key rotation không gộp/ngắt liên kết người — T03/T04.
4. **Mất mạng/ACK không rõ:** retry không tạo visit, snapshot, chữ ký hay upload trùng; draft không đi sang bệnh nhân kế tiếp — T05/T17/T18/T26.
5. **Directory đổi sau finalization:** demographics lịch sử và artifact đã phát hành giữ nguyên — T06/T13/T19/T20.

## Quy mô, đơn vị công việc và file ownership

32 task T00–T31, gồm preflight an toàn, 8 gate và nghiệm thu tổng. Các sprint là nhóm phụ thuộc, không phải cam kết thời lượng.

| Sprint | Task/gate | Điều kiện vào | Điều kiện ra |
|---|---|---|---|
| S0 | T00 — môi trường/check startup an toàn | Quyền thực thi source/test riêng | Không import-migrate; runner từ chối DB không cô lập |
| S1 | T09–T10/G3 nền tảng + T01–T05/G1 | S0 | Dialect/schema mới trên sandbox và tenancy/identity/visit guard |
| S2 | T06–T08/G2 + T11–T12/G3 | G1 + G3 nền tảng | Directory/episode/tài khoản và API/export contract |
| S3 | T13–T20/G4 | G1–G3 | Revision, finalization, policy, amendment, report an toàn |
| S4 | T21–T22/G5 + T23–T26/G6 | G4; task UI độc lập có thể sớm hơn | Metric hiện hành, print và thao tác E2E |
| S5 | T27–T28/G7 + T29–T30/G8 | G3; G7 review bắt đầu từ S0 | Model provenance trung thực; backup scope/restore evidence |
| S6 | T31 — nghiệm thu tổng | Các gate nội bộ hoàn tất | Báo cáo phần mềm; external blocker không bị đóng giả |

| Kế hoạch | Files/services sở hữu chính |
|---|---|
| [G1](2026-11-05-remediation-g1-tenancy-identity.md) | `facility_service.py`, `patient_identity.py`, `visits.py`, ownership constraints và locked-write guard |
| [G2](2026-11-05-remediation-g2-intake-accounts.md) | `patient_directory.py`, `intake.js`, episode snapshot, bootstrap account và permissions |
| [G3](2026-11-05-remediation-g3-database-verification.md) | startup schema contract, dialect helper, fixture, CSV download, deployment truth |
| [G4](2026-11-05-remediation-g4-clinical-revisions.md) | ClinicalRevision/ReportSnapshot, authorization/policy/release/amendment services và API |
| [G5](2026-11-05-remediation-g5-analytics.md) | analytics service và `admin-reports.js`, snapshot/filter/denominator contract |
| [G6](2026-11-05-remediation-g6-clinical-ux.md) | report template/CSS, intake/ADNEX, shortcut map, responsive/offline lifecycle |
| [G7](2026-11-05-remediation-g7-model-governance.md) | registry/provenance/ruleset declaration; không sửa weights |
| [G8](2026-11-05-remediation-g8-backup-operations.md) | backup service/manifest, admin backup presentation; không thêm destructive restore UI |

`backend/db/database.py`, `backend/schemas/schemas.py` và `backend/app/main.py` là file dùng chung: không giao hai task sửa đồng thời. Thêm entity/service theo task sở hữu; không chia lại toàn bộ module cũ cho đẹp. Tên file mới trong các plan là đề xuất cần tạo khi thực thi, không phải file đã tồn tại.

Thứ tự tuần tự hợp lệ khi thực thi native: **T00 → T09 → T10 → T01–T08 → T11–T26 → T27–T30 → T31**. Không thực hiện theo số task đơn thuần trước khi đọc dependencies. T12 giữ clinical status blocked và không import service policy chưa được tạo; T16 mới tích hợp policy vào capability. G7 đọc source/lineage từ đầu, implementation T27–T28 có thể sau G4 để kiểm tra integration đúng contract.

## Hợp đồng schema/API xuyên gate

Đích schema có sentinel `app_schema_state(version="full-spectrum-20261105-v1")`. Chỉ provision **database mới, trống và cô lập** mới được dùng `Base.metadata.create_all`; không gọi `init_db()` hoặc helper migration cũ. Schema của DB hiện có không tự được thay đổi khi start. DB legacy/dữ liệu mơ hồ là blocker migration riêng.

| Entity/contract đích | Fields/constraint bắt buộc |
|---|---|
| Patient identity | Giữ `PatientModel`; thêm `issuer_id`, `directory_id` nullable; unique `(facility_id, issuer_id, source_pid_hmac)` và link directory cùng facility; digest version/key ID; không persist raw PID |
| Episode | Study lưu `episode_identity_json`, `episode_version`; source directory/version và độ chính xác tuổi; patient binding không tự đổi theo directory |
| ClinicalRevision | `id, study_id, number, parent_snapshot_id, state, version, reason, created_by`; unique `(study_id,number)`; tối đa một draft/amendment đang mở mỗi Study |
| RevisionImage | `clinical_revision_id, image_id, source_hash, review_id, calibration_revision_id`; ownership/checksum xác minh; unique revision/image; không clone Study để sửa báo cáo |
| CalibrationRevision | Image, version, source/spacing/confirmed-by/time; append-only; revision cũ không được cập nhật theo spacing mới |
| ReportSnapshot | `id, clinical_revision_id, canonical_json, content_sha256, author_id, attested_at`; unique finalized clinical revision; không update/delete nội dung |
| ReportReleaseEvent | `id, snapshot_id, request_id, kind, provider_event_id, status, evidence_version_refs, created_at`; append-only; unique request/provider event theo namespace |
| ReleaseRequest | Job/outbox `id, snapshot_id, idempotency_key, payload_hash, expected_policy_version, state, provider_ref`; mutable job state được CAS; không gọi provider trong transaction DB |
| ClinicalAuthorization | Actor/facility/permission/evidence reference/effective bounds/version/revoked_at; mọi grant cần kiểm tra thẩm quyền nguồn, không tự cấp qua profile |
| FacilityReleasePolicyVersion | Facility/version/state/signature_requirement/evidence refs/accepted model-schema-template versions/approver; approved content bất biến, revoke là event/version guard |
| EvidenceRecord | Type/scope/version/document hash/reference/effective bounds, registration actor; no PII document trong artifact dev; đăng ký không đồng nghĩa thẩm định |

Các entity mới đặt trong `backend/db/clinical_models.py`, import đăng ký từ cuối `database.py` sau Base/models hiện có để giữ `Base.metadata` duy nhất; không import router/service ngược vào ORM. Constraint baseline-revision/backfill của DB cũ chỉ được **thiết kế** ở task migration, không tự chạy.

API đích mới trong `backend/app/routers/clinical_workflow.py`: `GET /api/cases/{study_id}/clinical-revisions`, `POST /api/cases/{study_id}/clinical-revisions/{revision_id}/finalize`, `POST /api/cases/{study_id}/amendments`, `POST /api/cases/{study_id}/clinical-revisions/{revision_id}/cancel`, `POST /api/report-snapshots/{snapshot_id}/release`, `GET /api/report-snapshots/{snapshot_id}/artifact`. API policy trong `clinical_governance.py`: evidence registration, authorization grant/revoke, policy draft/approve/revoke và trạng thái read-only. Provider callback chỉ khi có contract thật được cho phép; hiện kiểm chứng handler nội bộ bằng transport double **test-only**, production chưa cấu hình trả 503/NOT_CONFIGURED.

DTO write luôn có `request_id`, `expected_revision_version`, lease/page context khi sửa clinical workspace; finalization dùng `current_password: SecretStr` transient verify credential hiện hành, không log/lưu/hash secret hoặc chấp nhận boolean “đã xác thực”. Request dùng hash canonical + actor/facility/action để idempotent. Dùng enum `SURGICALLY_ABSENT` hiện có. Status artifact/release tách khỏi enum Study; `ClinicalRevision.state=DRAFT|FINALIZED|CANCELLED`, release events xác định trạng thái phát hành/superseded.

## T00 — Runner cô lập và startup không sửa schema

**Files:** Create `scripts/run_isolated_checks.py`, `backend/db/schema_contract.py`, `qa_isolated/test_startup_boundary.py`, `tests/helpers/clinical_scenario.py`; Modify `backend/app/main.py`, `tests/conftest.py`, `tests/serve_isolated_app.py`, `tests/helpers/isolated_browser.cjs`; Test mới dùng unittest trước, không import pytest conftest cũ.

**Interfaces:** `assert_supported_schema(engine: Engine) -> None` chỉ SELECT, mismatch làm readiness fail; `provision_empty_test_schema(engine: Engine, *, run_id: str) -> None` trong test helper, từ chối DB không trống. Runner CLI `--engine sqlite|postgresql --suite unit|pytest|node|browser --run-id <UUID> -- <test paths>` tạo cwd/storage mới, ép env trước mọi import; ghi commands/exit codes/logs có scope.

- [ ] **RED:** Viết `test_import_main_does_not_call_init_or_migration` và `test_runner_rejects_inherited_database_url_before_import` trong `qa_isolated/test_startup_boundary.py`; kiểm tra subprocess bằng module doubles import-safe, không gọi app thật trên DB hiện có. Assertion: migration/init call count `==0`; URL chưa được cấp riêng bị từ chối trước process child.
- [ ] **Verify RED:** `.venv/Scripts/python.exe -B -m unittest discover -s qa_isolated -p test_startup_boundary.py -v`. Chỉ assertion failure đúng nguyên nhân được chấp nhận; import error/log thiếu không tính RED hợp lệ.
- [ ] **Implement:** bỏ `init_db()` và retry mutation ở import main; startup chỉ kiểm tra schema/readiness. Test provision fresh empty DB rồi mới import app; không dùng production env toggle để bỏ policy. Runner refuse `.db` gốc repo, DSN kế thừa, path ngoài run directory và migration-related test nodeid mặc định. PostgreSQL cần DSN sandbox được operator cấp và run marker xác nhận; không tự cài/chạy Postgres/Docker.
- [ ] **GREEN:** lặp unittest, rồi qua runner chạy một API liveness test mới trên empty schema đã provision bằng helper test. Ghi hash/schema count trước/sau startup chứng minh không DDL/row mutation.
- [ ] **Checkpoint S0:** diff chỉ thuộc task; không commit. Khai báo `ClinicalScenario.request(actor, method, path, *, json=None, headers=None) -> httpx.Response` dùng JWT thật, không auth override; fixture có `case_a/case_b` với `study_id,visit_id,image_id,review_id,directory_id` tổng hợp, `lease_headers(actor,study_id)`; credential/secret chỉ giữ transient. Test request mới không dùng helper `init_db` legacy.

## Cách đọc các lệnh kiểm chứng trong gate

Sau T00, quy ước **P** là `.venv/Scripts/python.exe -B scripts/run_isolated_checks.py --engine sqlite --suite pytest --run-id <UUID-MỚI> --`; **PG** tương tự với `--engine postgresql`; **N** với `--suite node`; **B** với `--suite browser`. Khi thực thi phải thay UUID mới, không dùng chung runtime giữa hai run. Runner tự chọn pytest `-p no:cacheprovider`, basetemp/JUnit/log trong run dir; node chạy `node --test`; browser chạy entry đã chỉ định với host loopback. Những ký hiệu này không là alias đã cài.

Mỗi RED/GREEN dùng cùng test target trên DB mới; không sửa test assertion chỉ để xanh. Test legacy có chữ migration/schema-upgrade chỉ viết/đọc tĩnh cho tới quyền riêng, không lách qua test runner. Full-suite sẽ BLOCKED nếu còn test không thể chạy an toàn; không bỏ qua mà gọi full pass.

## T31 — Nghiệm thu tích hợp và bàn giao

**Files:** Modify test suites liên quan ở các gate; Create `tests/full_spectrum_acceptance_e2e.cjs`, `docs/evaluation/full-spectrum-remediation-status-2026-11-05.md`; logs/screenshots chỉ dưới `artifacts/full_spectrum_remediation/<run_id>/` khi được thực thi.

**Consumes:** acceptance APIs, `ClinicalScenario`, runner và 8 checkpoint. **Produces:** ledger 35 issue gồm trạng thái/bằng chứng mới, software acceptance tách external readiness.

- [ ] **RED:** thêm E2E `test_two_facilities_two_patients_finalize_amend_reopen` và `test_revoke_during_release_never_publishes`; assertions: case A/B không lẫn, snapshot cũ không đổi byte/hash, amendment cùng study_id, native PDF/source mapping đúng, clinical capability vẫn false khi evidence external thiếu.
- [ ] **Verify RED:** `B tests/full_spectrum_acceptance_e2e.cjs`; failure phải chỉ ra invariant, không bỏ case hoặc cấp quyền ngầm cho fixture.
- [ ] **Implement integration only:** sửa mapping/router/DTO drift tại owner task, không viết shim bỏ guard để xuyên gate; issue đã sửa sẵn phải có regression evidence mới.
- [ ] **GREEN/regression:** chạy targeted P/PG theo từng gate, `N tests/*.mjs`, syntax checker hiện có và browser workstation/roundtrip/safety sau preflight T00. Đánh giá mỗi test legacy về side effect trước mở rộng suite; báo đủ fail/error/skipped/blocked. PostgreSQL/physical mic/PACS/provider chưa có ghi BLOCKED, không giả pass.
- [ ] **Handoff:** rà soát diff từng task và toàn bộ phần thực thi được phép; không stage/commit hỗn hợp worktree. Ghi rõ migration, deploy, model replacement và sử dụng bệnh nhân thật chưa được cho phép. Người dùng chọn cách thực thi sau khi duyệt plan; mọi bước tại đây hiện NOT RUN.

## Ledger đủ 35 finding — task sở hữu và bằng chứng đích

Ledger dưới đây là mapping kế hoạch, không là trạng thái lỗi đã sửa. Cột trạng thái khởi đầu của mọi issue là `REVALIDATE_CURRENT_SOURCE`; khi thực thi chuyển OPEN/EXISTING_CHANGE_UNVERIFIED/VERIFIED_FIXED/BLOCKED_EXTERNAL theo evidence. Giữ nguyên issue register audit gốc.

| Issue | Gate | Task sở hữu | Acceptance chủ đạo |
|---|---|---|---|
| AUD-001 | G1 | T01 | Global=false/null-facility 403; scope query độc lập JWT |
| AUD-002 | G1 | T01 | Reviewer legacy B không xuất hiện trong stats A |
| AUD-003 | G1 | T02 | Settings/departments/metadata scope + CAS |
| AUD-004 | G1 | T05 | Reparent 409, lock/link/write race |
| AUD-005 | G1 | T03,T04 | Facility/issuer/version/rotation + legacy quarantine |
| AUD-006 | G2 | T06,T07 | Directory server, prospective episode snapshot |
| AUD-007 | G2 | T07 | No seeds normal mode |
| AUD-008 | G2 | T07 | No fabricated PID, anonymous research works |
| AUD-009 | G2 | T07 | Empty list reload remains empty |
| AUD-010 | G2 | T08 | First-login doctor facility assignment works |
| AUD-011 | G3 | T09 | Runtime SQLite/PostgreSQL auth/identity/lease/sequence |
| AUD-012 | G2 | T08 | Deploy requires explicit valid bootstrap facility |
| AUD-013 | G2 | T08 | Restart does not reset password/elevate privilege |
| AUD-014 | G4 | T14 | Visible multi-region assignment + stale/retry checks |
| AUD-015 | G4 | T20 | Exact opposite-side status through PDF |
| AUD-016 | G3 | T11 | Authenticated CSV request/file/failure |
| AUD-017 | G4 | T20 | IQA technical, no unsupported clinical claim |
| AUD-018 | G5 | T21 | Review count distinct from finalized/released studies |
| AUD-019 | G5 | T21,T22 | Latest review/denominator and export consistency |
| AUD-020 | G5 | T21,T22 | O-RADS0 distinct from null |
| AUD-021 | G6 | T23 | Clinician summary first, representative image explicit |
| AUD-022 | G6 | T23 | Honest disabled export state |
| AUD-023 | G6 | T25 | C/Shift+C/input focus/help consistent |
| AUD-024 | G6 | T24 | No unnecessary required PII |
| AUD-025 | G6 | T24 | Exam-age provenance/precision/confirmation |
| AUD-026 | G6 | T25 | Tour one-side/exact run action |
| AUD-027 | G6 | T26 | Reachable toolbar/panel/zoom/touch |
| AUD-028 | G6 | T23 | Full readable ID in screen/A4 |
| AUD-029 | G6 | T25 | Keyboard/native drilldown controls |
| AUD-030 | G7 | T27,T28 | Truthful lineage + blocked compliant-artifact requirement |
| AUD-031 | G3 | T10 | Explicit fixture roles, no SQL/constructor hooks |
| AUD-032 | G3 | T12 | Evidence-based deployment capability matrix |
| AUD-033 | G4 | T20 | Pixel privacy boundary and research export remain correct |
| AUD-034 | G4 | T14 | Unverified ruler candidate never reports calibrated mm |
| AUD-035 | G8 | T29 | Readable backup history with honest status |

T13/T15–T19/T30 bổ sung workflow được duyệt ngoài 35 lỗi gốc, không bị bỏ vì không có AUD riêng. T00 và T31 là safety/integration checkpoints.

## Spec-to-task self-review map

| Spec requirement | Task/contract |
|---|---|
| §1–4 scope, architecture, current drift | Master constraints, T00, ledger revalidation |
| §5.1 authorization + §5.2 ownership | T01,T02,T04,T05 |
| §5.3 identity namespace/rotation | T03,T04 |
| §5.4 prospective directory/episode | T06,T13,T19,T20 |
| §5.5 legacy transition permission | T04 runbook; explicit migration blocker |
| §5.6 visit lifecycle/race | T05,T17,T19 |
| §6 intake/accounts/age | T06–T08,T24 |
| §7 dialect/fixture/CSV/resource truth | T00,T09–T12 |
| §8.1 region/calibration/privacy | T14,T20 |
| §8.2 clinical author/snapshot/release | T15–T18 |
| §8.3 amendment/immutability | T13,T19 |
| §8.4 transition checklist | T17,T19 |
| §9 analytics | T21,T22 |
| §10 report/fields/A11y/recovery | T23–T26 |
| §11 model governance | T27,T28 |
| §12 backup/restore | T29,T30 |
| §13 35-issue traceability | Master ledger above |
| §14.1 software acceptance | T00,T31 + each gate checkpoint |
| §14.2 external release acceptance | T16,T18,T28 + blockers table |
| §14.3 policy authority/revoke | T15,T16,T18 |
| §14.4 execution boundary + §15 inputs | Master constraints/handoff/external blockers |
| §16 reviewer decisions | T06,T13,T15–T20 and associated tests |

## Checkpoint gate và nghiệm thu ngoài phần mềm

| Gate | Acceptance tối thiểu | Không được coi là bằng chứng thay thế |
|---|---|---|
| G1 | JWT role/scope matrix + ownership constraints + race lock/link | Chỉ unit-test utility hoặc fixture tự gán quyền |
| G2 | Hai browser context cùng directory, snapshot cũ nguyên vẹn, account first login/restart | LocalStorage hoặc password được seed lại mỗi start |
| G3 | SQLite và PostgreSQL write/query/lease thực trên sandbox | Compile-only, đổi capability hằng số |
| G4 | Multi-region, finalization, revoke-race, amendment, artifact hash | Tên bác sĩ/ảnh chữ ký/checkbox consent |
| G5 | Latest-review denominator, O-RADS0/null, matching drilldown/CSV | distinct Study được gọi là bệnh nhân độc nhất |
| G6 | 3 desktop sizes, narrow/tablet, keyboard, zoom thật, save failure | Chỉ screenshot hoặc CSS zoom |
| G7 | Manifest/checksum/lineage thật, clinical gate blocked đúng | Sửa text loss hoặc metric validation thành independent |
| G8 | Readable history, global-only full backup, authorized sandbox restore | File archive tồn tại = đã khôi phục được |

External release dependencies: issuer/legacy mapping do cơ sở xác nhận; clinical authority và evidence thật; qualified signature provider/PACS sandbox; chính sách retention/key custody; thẩm định lâm sàng và artifact model đúng scope. Không có đầu vào thì feature nội bộ có thể nghiệm thu synthetic, nhưng phần release tương ứng vẫn BLOCKED_EXTERNAL.

## Self-review và trạng thái kế hoạch

- [x] Tự đối chiếu §1–16 của spec với task/contract và 35 dòng traceability trước bàn giao plan.
- [x] Kiểm tra task IDs/dependency; sửa test T15/T16 không gọi finalize/provider API trước task tạo API, và T05 không import ClinicalRevision trước T13.
- [x] Kiểm tra link, file ownership và planned path; file mới chỉ được tạo khi task được phép, không coi các file dự kiến là đã tồn tại.
- [x] Kiểm tra cấu trúc tài liệu, traceability và source hash; không dùng chúng làm bằng chứng application test pass. Các checkbox execution ở mọi task vẫn chưa thực hiện.

Không dispatch implementer/reviewer agent ở bước viết plan. Skill writing-plans yêu cầu self-review, không yêu cầu chạy code. Phương thức thực thi chưa được chọn; đề xuất native theo gate để giảm context lặp, giữ checkpoint độc lập ở các boundary an toàn trước hợp nhất. Bất kỳ commit nào sau này cũng phải sau rà soát diff và quyền tương ứng.
