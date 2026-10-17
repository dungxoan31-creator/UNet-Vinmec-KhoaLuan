# Bug Audit and Evidence Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Lượt lập plan chưa thực hiện audit, chưa tạo bug thật và chưa sửa code.

**Goal:** Audit hệ thống segmentation/HITL đang có và bàn giao bug log có thể giao trực tiếp cho coding agent tái hiện, sửa và retest.

**Architecture:** Dùng test/API/browser hiện có, audit từng miền và lưu raw evidence theo run. Finding Markdown là nguồn chuẩn; CSV chỉ là index, không xây thêm issue tracking application. Audit discovery và bug fixing là hai giai đoạn tách biệt.

**Tech Stack:** pytest, Node assertions, playwright-core, PowerShell, CSV/Markdown/JSON; dùng package hiện có.

**Spec:** `docs/superpowers/specs/2026-10-17-bug-audit-design.md`; phạm vi đề tài theo `docs/superpowers/specs/2026-10-17-thesis-core-scope-design.md`.

## Global Constraints

- Chỉ audit luồng segmentation/HITL và các thành phần ảnh hưởng trực tiếp.
- Không sửa product code khi discovery; không tuning bằng Test, không tạo session/nhận xét bác sĩ giả.
- Không overwrite evaluation/report/source/split/checkpoint hiện có; run ID mới mỗi lần.
- Không dùng production DB/credentials hoặc phát tán PHI/secrets trong raw logs.
- Không lấy ledger “complete”, test source tồn tại hay report PASS làm bằng chứng chạy hiện tại.
- Working tree bẩn: ghi cả HEAD và source-file SHA256 của đường chạy; không reset/stash/commit thay đổi của người dùng.

## Review Focus

1. Server cũ chiếm port và test nhầm phiên bản: kiểm tra PID/runtime/hash trước browser test — A01/A05.
2. Test helper hardcode runtime đã có dữ liệu: chỉ chạy khi bảo đảm runtime là disposable; nếu chưa đủ isolation thì BLOCKED, không tự xóa — A01.
3. Mask có cùng diện tích nhưng sai vị trí: bitwise comparison khi undo/reopen/export, không chỉ sum pixels — A03/A05.
4. Sinh report ghi đè bug index hoặc current_run: canonical log nằm ngoài generated report, không gọi build/publish trong discovery — A02/A06.
5. Test thiếu dữ liệu bị gán product bug: phân biệt ENVIRONMENT/DATA_BLOCKER và BUG bằng repro/trace — A02/A07.

## 1. Hiện trạng đã khảo sát

HEAD lúc lập plan: `94d46e5`; nhiều file vẫn modified/deleted/untracked. `evaluation/milestone_3_final/report/open_issues.csv` có ISS-01…05 nhưng trộn independent gate, clinician unavailable, near-duplicate risk, calibration và giới hạn single-machine. Không nhập chúng nguyên trạng thành bug đã xác nhận.

`scripts/verify_evaluation_release.ps1` hiện có `-TestScope full|selected`, default selected, `-BaselineOnly`, `-SkipBrowser`, `-PrototypeOnly`, `-OutputDir`. Script helper `tests/serve_isolated_app.py` vẫn có runtime mặc định `artifacts/review-e2e-runtime`; phải kiểm tra isolation trước chạy. Các vấn đề đã nêu ở plan trước có thể đã được sửa trong commit mới; revalidate, không khẳng định còn lỗi.

Audit đầu tiên dự kiến 6–9 giờ nếu môi trường sẵn sàng; thời gian tái hiện lỗi ngẫu nhiên và xử lý môi trường UNKNOWN. Sửa bug không nằm trong estimate này.

## 2. Log contract và severity

Canonical: `docs/audit/findings/AUD-0001.md`; index `docs/audit/bug_index.csv`; raw evidence `evaluation/bug_audit/<run_id>/`. Chỉ tạo finding khi phát hiện thực tế, không tự điền danh sách bug mẫu như kết quả.

Index columns:

```text
id,type,severity,priority,status,component,title,first_seen_run,last_seen_run,head_sha,source_hash_manifest,reproducibility,owner,record_path,evidence_path,duplicate_of,fix_commit,regression_test,verified_run,next_action
```

Finding record bắt buộc:

```markdown
# AUD-NNNN — Tiêu đề mô tả trigger và hậu quả
Type / Severity / Priority / Status:
Run ID / UTC timestamp / HEAD / source manifest:
Component / source location / config / checkpoint hash:
Expected behavior + nguồn yêu cầu/protocol/test:
Actual behavior:
Input: mã khử định danh, hash, shape; không ghi PHI:
Preconditions:
Reproduction steps: các bước đánh số, từ trạng thái ban đầu xác định:
Command / API request đã bỏ credentials:
Evidence: log path + dòng/trace, screenshot, request ID, mask hashes:
Observed frequency: số lần lỗi / số lần thử:
Impact / workaround:
Root cause: UNKNOWN | HYPOTHESIS | CONFIRMED; trace chứng minh:
Owner / next action:
Regression test: file::test_name hoặc NOT_YET_WRITTEN:
Fix commit / retest run / result:
History: UTC, old→new status, người thao tác, evidence:
```

Không để UNKNOWN biến thành kết luận. Với static issue có trace chắc chắn ghi `reproducibility=static_proof`; dynamic issue ghi số lần thử, browser/device và dữ liệu. Không chạy lặp vô hạn: tối đa3 lần có kiểm soát cho nghi vấn flaky rồi ghi số lần thật/NEEDS_INVESTIGATION.

| Severity | Điều kiện | Priority mặc định |
|---|---|---|
| S0 Critical | Lộ dữ liệu/secret, phá dữ liệu thật, ghi mask nhầm người/ca, xác nhận sai có ảnh hưởng toàn vẹn nghiêm trọng | P0, dừng thao tác gây hại |
| S1 High | Luồng upload/predict/edit/save/reopen/export bị chặn; sai mask/metric/provenance hoặc readiness sai nghiêm trọng | P0/P1 theo ảnh hưởng |
| S2 Medium | Lỗi công cụ/timing/logging hoặc recovery có workaround, không phá dữ liệu | P1/P2 |
| S3 Low | Hiển thị/copy/layout không chặn tác vụ và không làm hiểu sai kết quả | P2 |

Severity mô tả ảnh hưởng; priority quyết định thứ tự sửa. Data blocker/limitation có impact/priority nhưng không giả severity product bug. UNKNOWN frequency không được ghi “luôn xảy ra”.

Lifecycle: `NEW → TRIAGED → CONFIRMED → IN_PROGRESS → FIXED_PENDING_VERIFICATION → VERIFIED → CLOSED`; nhánh `NEEDS_INFO`, `BLOCKED`, `DUPLICATE`, `NOT_A_BUG`, `DEFERRED`, `REOPENED`. Audit này thường dừng ở TRIAGED/CONFIRMED/BLOCKED. Chỉ agent thực sự sửa mới ghi fix_commit; chỉ retest sau fix mới VERIFIED. Duplicate giữ hồ sơ và trỏ canonical ID, không xóa bằng chứng.

## 3. Tasks và dependency

### A01: Khóa baseline và runtime audit an toàn

**Files:** Read `scripts/verify_evaluation_release.ps1`, `tests/serve_isolated_app.py`, `backend/app/config.py`, `backend/db/database.py`, `evaluation/selected_model.json`; Create artifacts `evaluation/bug_audit/<run_id>/{run_manifest.json,source_hashes.csv,coverage.csv,commands.csv}`. Modify product: none.

**Interfaces:** consumes repo/config/runtime; produces run_id `YYYYMMDDTHHMMSSZ-<short-head>` cùng HEAD, dirty status, selected source hashes, environment, runtime/port/checkpoint identity. Command rows `command_id,redacted_command,started_utc,ended_utc,exit_code,scope,stdout_path,stderr_path`.

- [ ] 1. Đọc git status/HEAD và cấu hình runtime, ghi đường dẫn production và technical runtime; kiểm tra DB nào có dữ liệu phải giữ. Không dump env toàn bộ.
- [ ] 2. Chọn fresh evidence folder, xác nhận absolute path thuộc workspace; snapshot hash source liên quan, manifest/checkpoint/split. Không lưu patch chứa secret ra folder chia sẻ.
- [ ] 3. Xác minh test helper/script không chuyển DB về production hoặc ghi đè artifact lịch sử; runtime phải disposable. Nếu helper hiện tại không hỗ trợ fresh runtime, ghi ENVIRONMENT/BLOCKED và lập prerequisite isolation nhỏ, không sửa lén source/clear DB để tiếp tục.
- [ ] 4. Kiểm tra port8027/PID/command line được phép; chỉ khởi động/stop process audit sở hữu. Ghi model hash health và source version tương ứng; không kill service của người dùng.
- [ ] 5. Kiểm tra manifest/commands/coverage mở được và source hashes đầy đủ. Không claim chạy test nếu chưa chạy.

**Acceptance:** raw artifacts nằm folder mới; runtime an toàn xác minh được hoặc test write BLOCKED. **Dependency:** none. **Estimate:** 30–45 phút.

### A02: Chuẩn hóa registry và triage các issue lịch sử

**Files:** Create `docs/audit/{README.md,bug_index.csv,bug_template.md}`; Read generated `evaluation/milestone_3_final/report/open_issues.csv`. Create findings chỉ khi có observation.

**Interfaces:** consumes contract phần2, historical issues; produces canonical registry + quy tắc ID/source/evidence/history. Không sửa report generator trong audit.

- [ ] 1. Tạo template/index header theo contract, không điền bug giả. README chỉ dẫn quy trình NEW→CONFIRMED→retest.
- [ ] 2. Triage ISS-01…05: phân loại data blocker, conditional study gap, similarity risk hoặc limitation; link ID nguồn, không tự đổi thành BUG.
- [ ] 3. Với nghi vấn còn phù hợp, đối chiếu code/current artifact rồi đưa vào hàng đợi test ở A03–A06. Đã sửa thì ghi historical finding không tái hiện ở version hiện tại, không ghi OPEN giả.
- [ ] 4. Kiểm tra ID unique, record paths tồn tại, CSV quoting đúng với dấu phẩy/xuống dòng; record không chứa secret/PHI. Chưa có observation có thể giữ index header-only.

**Acceptance:** registry không phụ thuộc file report có thể bị generate lại; issue types không bị trộn. **Dependency:** A01. **Estimate:** 30–45 phút.

### A03: Audit preprocessing, model, coordinate và metrics

**Files:** Read `backend/services/{preprocessor,inference_engine}.py`, `backend/core/dataset_paths.py`, `evaluation/{protocol,segmentation_metrics,run_evaluation}.py`, `frontend/app/coordinates.js`; Test existing `tests/test_segmentation_metrics_v1.py`, `tests/test_inference_parity_v1.py`, `tests/test_evaluation_protocol_v1.py`, `tests/test_evaluation_run_v1.py`, `tests/workspace_v2_logic.mjs`.

**Interfaces:** consumes locked protocol and synthetic/Validation samples được phép; produces coverage rows, raw test logs, observed finding records. Không chạy lại independent Test hoặc training.

- [ ] 1. Chạy named tests bằng isolated pytest bootstrap đã xác minh ở A01; lệnh lựa chọn `pytest.main(['tests/test_segmentation_metrics_v1.py','tests/test_inference_parity_v1.py','tests/test_evaluation_protocol_v1.py','tests/test_evaluation_run_v1.py','-q','--tb=long'])`. Node: `node tests/workspace_v2_logic.mjs`; lưu stdout/stderr/exit code.
- [ ] 2. Đối chiếu oracle GT `[[1,1],[0,0]]`, pred `[[1,0],[1,0]]`: Dice=.5, IoU=1/3, Recall=Precision=.5; kiểm tra 3 empty combinations theo protocol và shape/NaN reject. Chưa có test cụ thể thì ghi coverage gap, không dùng PASS tổng để suy đã test.
- [ ] 3. Trace grayscale/letterbox512/CLAHE/normalize/threshold>=.5/inverse mask; chọn ảnh non-square Validation để kiểm tra native-size/mask coordinate. Chụp expected/actual masks và hash; không sửa GT/resize lỗi để làm test xanh.
- [ ] 4. Kiểm tra serving/evaluator checkpoint, threshold, postprocess cùng protocol; HD95 đúng percentile/surface/đơn vị px, không gọi maximum Hausdorff là HD95.
- [ ] 5. Lỗi test → ghi symptom/input/trace; chỉ ghi root cause CONFIRMED khi trace đúng branch/caller. Model mask kém với pipeline đúng → MODEL_ERROR, không mặc nhiên BUG.

**Acceptance:** metric/shape/coordinate/model-loading có coverage thực; mọi failure có file::test/input/evidence. **Dependency:** A01–A02. **Estimate:** 60–90 phút.

### A04: Audit API, transaction, auth và input boundaries

**Files:** Read `backend/app/routers/{inference,reviews,cases,auth,hitl}.py`, `backend/services/{review_service,research_export}.py`; Test `tests/test_review_batch.py`, `tests/test_research_export.py`, `tests/test_auth_boundaries.py`, `tests/test_protected_clinical_api.py`, `tests/test_prototype_release_failures.py`, `tests/test_duplicate_upload.py`.

**Interfaces:** disposable DB + known requests→before/after DB assertions, HTTP status, request IDs và evidence.

- [ ] 1. Chạy nhóm pytest tương ứng qua bootstrap A01; giữ full traceback, không in JWT/password/request PHI.
- [ ] 2. Kiểm tra wrong/missing/corrupt image, wrong RLE shape, missing model/hash mismatch; expected controlled400/404/422/503 theo API spec hiện hành, không false success/prediction row.
- [ ] 3. Trace hai ảnh batch: ảnh thứ2 invalid phải rollback cả batch; stale revision409; retry cùng ID/body tạo một batch; ID trùng/body khác409; wrong image/prediction không được lưu.
- [ ] 4. Kiểm tra no-token/wrong-role/cross-case ownership theo contract; verify viewed/exported mask đúng persisted review/prediction ID và native shape. Thiếu policy ownership rõ thì NEEDS_INVESTIGATION, không tự bịa spec.
- [ ] 5. Lưu response đã redact và rowcount/revision/hash trước-sau; nếu phát hiện ghi sai ca/lộ dữ liệu dừng thao tác liên quan và triage S0/S1 ngay.

**Acceptance:** failure không để partial data hoặc fake confirmation; every confirmed finding có request và DB evidence. **Dependency:** A01–A02. **Estimate:** 60–90 phút.

### A05: Audit UI/HITL thật và race conditions

**Files:** Read `frontend/app/{upload,viewer,review,state,hitl-tracker,cases,report-preview}.js`; Test `tests/workspace_v2_release_e2e.js`, `tests/workspace_v2_races.js`, `tests/workspace_v2_draft_conflict.js`, `tests/workspace_v2_api_abort.js`, `tests/workspace_v2_lease_guards.js`, `tests/workspace_v2_telemetry.mjs`.

**Interfaces:** server audit đúng PID/hash + browser/test account→screenshots, console/pageerror, request sequence, persisted/export mask comparisons. Mock API tests ghi mock scope riêng, không thay live E2E.

- [ ] 1. Rehearse Upload→AI→Original/Mask/Overlay→brush/erase→undo/redo/reset→confirm→reload→export, L/R và 2 case. Expected pixel equality sau undo/reopen/export; pan/opacity không đổi mask.
- [ ] 2. Kiểm tra zoom rồi vẽ, đổi side, đổi case/logout khi request cũ chưa xong; offline khi save, timeout-after-commit retry, token expiry và draft khôi phục. Expected không ghi state sang ca/user khác, không success toast giả.
- [ ] 3. Chạy các Node/Playwright scripts ở danh sách file trên khi preflight xác minh runtime/endpoint đúng. Script nào hardcode port/credentials/expected old contract thì ENVIRONMENT/test-maintenance finding, không chỉnh test để che product bug.
- [ ] 4. Thu request ID/console error/screenshot và minimal repro; screenshot không có credential/dữ liệu định danh. Nếu không tái hiện ổn định, tối đa3 lượt rồi ghi frequency và chưa xác minh.
- [ ] 5. Kiểm tra session/time/editcount: monotonic clocks, stroke count1, undo/reset riêng, initial/final mask equality, missing event/ACK không được thành complete hay duration0. No-GT before/after phải null.

**Acceptance:** có live evidence và coverage của failure/race; không suy từ ảnh chụp đẹp là luồng đúng. **Dependency:** A01–A02; A04 nên chạy trước. **Estimate:** 90–150 phút.

### A06: Audit evaluation artifacts, báo cáo và full regression

**Files:** Read `scripts/{build_evaluation_report.py,verify_evaluation_release.ps1}`, `evaluation/hitl_analysis.py`, `evaluation/current_run.json`, current report/HITL/study artifacts; Test `tests/test_evaluation_report.py`, `tests/test_release_evidence.py`, `tests/test_hitl_analysis.py`, `tests/test_user_study_summary.py`.

**Interfaces:** artifact/hash/role registry + current source→consistency findings và test scope report.

- [ ] 1. Cross-check current model hash/run kind/metric resolution, CSV counts/summary/table/UI; retrospective không được gọi independent; clinical participant phải dựa nguồn xác minh, không role string.
- [ ] 2. Kiểm tra fallback và evaluation_complete đúng spec; generated_at từ execution thật; unknown hash/count/null không bị default giả; report/final_checks không mâu thuẫn.
- [ ] 3. Trace registry/open_issues generation: logging không bị overwrite khi generate report. Không gọi report CLI có publish/--set-current trong discovery; test generator bằng tmp fixture và output mới.
- [ ] 4. Chạy full isolated pytest `pytest.main(['tests','-q','--tb=long'])` qua bootstrap A01, lưu logs vào run hiện tại. Hoặc dùng verifier `-TestScope full -BaselineOnly -SkipBrowser -OutputDir <fresh_run/full_regression>` chỉ sau khi đọc lại và xác nhận không publish/overwrite. `BaselineOnly`/`SkipBrowser` không đủ chứng minh live readiness.
- [ ] 5. Ghi collected/passed/failed/skipped/exitcode; lỗi môi trường/phụ thuộc dữ liệu để riêng; full suite fail vẫn bàn giao audit report trung thực, không yêu cầu sửa tất cả mới được ghi log.

**Acceptance:** mọi status được giới hạn đúng scope; full regression có raw log hoặc BLOCKED với lý do; artifact cũ không bị đổi. **Dependency:** A01–A02; final coverage sau A03–A05. **Estimate:** 60–90 phút + runtime suite.

### A07: Triage, kiểm tra bug log và bàn giao backlog sửa

**Files:** Create `docs/audit/audit_summary_2026-10-17.md`; Update actual `docs/audit/findings/*.md`, `docs/audit/bug_index.csv`; Create run `coverage.csv`, `checksums.csv`, `summary.json`.

**Interfaces:** findings/raw evidence→deduplicated queue theo impact/dependency, not automated fixes.

- [ ] 1. Rà mỗi finding: có nguồn expected behavior, exact reproduction, actual result, evidence/source version và kind; thiếu dữ kiện → NEEDS_INFO/UNCONFIRMED, không CONFIRMED.
- [ ] 2. Dedupe theo root cause đã chứng minh; lỗi cùng symptom chưa chắc cùng root cause, giữ separate rồi liên kết nếu chưa đủ evidence. Gán severity/priority và owner chưa biết là UNASSIGNED.
- [ ] 3. Tạo bảng coverage từng miền với PASS/FAIL/NOT_RUN/BLOCKED; tổng counts theo kind/severity/status và known risk. Không tính data blockers vào product bug count.
- [ ] 4. Đối chiếu mỗi ID index có đúng một hồ sơ; paths nằm trong workspace, evidence tồn tại/hash khớp; redact logs shareable; bảo toàn raw private. Không commit patient data/DB/screenshots nhạy cảm.
- [ ] 5. Với mỗi BUG CONFIRMED đề xuất patch scope exact files + regression test tên cụ thể dựa repro; coding agent tạo failing test trước sửa. Retest sau fix phải dùng run ID mới + fix commit/source hashes, nếu còn lỗi REOPENED. Audit không tự chuyển FIXED/VERIFIED.
- [ ] 6. Bàn giao S0/S1 trước, rồi S2/S3; nếu cần commit chỉ stage tài liệu khử định danh/hunks thuộc audit. Không sửa code trong commit audit log.

**Acceptance:** log đủ để agent khác tái hiện không cần đoán; tất cả miền có coverage state; unverified/historical/limitation rõ ràng. **Dependency:** A03–A06. **Estimate:** 45–60 phút.

## 4. Timeline và Definition of Done

Ngày17/10: A01/A02 khoảng1h, A03/A04 khoảng2–3h, A05 khoảng1.5–2.5h. Ngày18/10 hoặc block kế tiếp: A06 khoảng1–1.5h cộng suite runtime; A07 khoảng1h. Ưu tiên startup, sai mask/metric, mất/nhầm dữ liệu, save/export rồi mới giao diện phụ. Nếu chỉ có4h: chạy các luồng ưu tiên và bàn giao PARTIAL coverage; không nói audit toàn hệ thống.

Critical path: isolation→registry→core tests/live repro→triage. Full regression không chặn việc ghi nhận ngay bug nghiêm trọng. Không thêm dashboard, remote issue sync, CI service hoặc framework logging mới.

Audit DONE khi có baseline/current version, scope coverage, findings có evidence, index nhất quán, raw logs và backlog triage; không cần zero bug. Product FIXED là trạng thái khác chỉ sau patch+retest. Timeline sửa từng bug được ước lượng sau audit, không cam kết trước số lượng lỗi.

## 5. Self-review và execution handoff

Đã kiểm tra: phạm vi giữ segmentation/HITL; 7 task có files/interfaces/steps/acceptance; discovery không tự sửa; phân loại symptom/model error/data blocker/limitation; source expectation và no-GT rules rõ; full/selected/mock/live coverage tách riêng; secrets và runtime legacy được kiểm soát; lịch sử report không ghi đè registry. Không có finding thực tế được tạo trong lượt lập plan này.

Plan dùng filesystem log tối thiểu thay vì một subsystem mới; mọi test group dùng file đã tồn tại trong repository lúc khảo sát. Trước thực thi cần preflight lại HEAD/runtime vì repo đang thay đổi. Khuyến nghị native để giữ một ID allocator và một audit runtime; nếu chọn delegation thì chia module readonly, một owner duy nhất ghi registry để tránh trùng ID. Sau review plan mới bắt đầu audit, không suy yêu cầu lập plan là cho phép sửa product.
