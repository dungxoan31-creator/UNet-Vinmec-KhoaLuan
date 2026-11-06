# Nhật ký kiểm thử

## Nhiều vùng trong một ảnh — persistence caliper/CDSS — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Region clinical tests | PASS — 19 passed; hai component có ID, D1 caliper và assessment CDSS độc lập, tải lại không chéo dữ liệu. | [`region tests`](../artifacts/audit_remediation_2026_10_28/evidence/multi-region-caliper-isolation-2026-10-29.log) |
| Full Python suite | PASS — 1.349 passed, 0 failed/skipped; 1 Pillow `DecompressionBombWarning` có chủ đích do test oversized-image rejection. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-multi-region-caliper-cdss-2026-10-29.log) |
| Clinical accuracy / PostgreSQL | BLOCKED / NOT TESTED — synthetic persistence test không thay thế expert-approved CDSS validation, segmentation/region reference hoặc PostgreSQL integration. | [`Go-live assessment`](../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) |

## P1 — report ảnh: giới hạn canvas và ổn định số ảnh — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Report preview regression | PASS — 9 tests; cạnh report tối đa 2.048 px, timeout decoder, source-dimension/mask guards, concurrency ≤2, dừng lịch ảnh sau lỗi, số ảnh theo thứ tự trang. | [`targeted report`](../artifacts/audit_remediation_2026_10_28/evidence/report-preview-image-memory-hardening-2026-10-29.log) |
| Frontend suite / syntax | PASS — 136 passed, 0 failed/skipped; syntax-check 53 module. | [`frontend tests`](../artifacts/audit_remediation_2026_10_28/evidence/frontend-report-image-memory-hardening-2026-10-29.log), [`syntax`](../artifacts/audit_remediation_2026_10_28/evidence/frontend-report-image-memory-hardening-syntax-2026-10-29.log) |
| Browser roundtrip | PASS — live API/model/SQLite, 2 ảnh synthetic, region/caliper/CDSS persistence/reload, report/print 3 trang, 0 page errors; canvas fault injection xác nhận cleanup/retry và source-dimension guard không chặn snapshot hợp lệ. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-after-report-image-decode-timeout-2026-10-29.log) |
| Safety E2E / release docs | PASS — 27 safety checks trên 3 viewport, 0 page errors; 6 release-document tests. | [`safety E2E`](../artifacts/audit_remediation_2026_10_28/evidence/safety-e2e-after-report-image-decode-timeout-2026-10-29.log), [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-report-image-memory-hardening-2026-10-29.log) |
| Markdown / `git diff --check` | PASS — không có trailing whitespace; diff check exit 0 (Git có thông báo chuẩn hóa LF/CRLF). | [`Markdown`](../artifacts/audit_remediation_2026_10_28/evidence/markdown-whitespace-after-report-image-memory-hardening-2026-10-29.log), [`diff check`](../artifacts/audit_remediation_2026_10_28/evidence/git-diff-check-after-report-image-memory-hardening-2026-10-29.log) |
| PostgreSQL / RAM boundary / clinical validation | BLOCKED / NOT TESTED: không có PostgreSQL test service; chưa đo RSS với ảnh 25 MP/số ảnh tối đa; chưa có phantom/caliper reference, CDSS case set được chuyên gia duyệt hoặc phê duyệt lâm sàng/site. | [`Go-live assessment`](../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) |

## P1 — caller-supplied clinical narrative trong PDF helper RUO — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Report/security regression | PASS — 45 passed; PDF helper không in diagnosis, mô tả hoặc conclusion tùy ý từ payload. | [`targeted tests`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-clinical-text-ruo-targeted-2026-10-29.log) |
| Full Python suite | PASS — 1.348 passed, 0 failed, 0 skipped; một Pillow warning có chủ đích trong kiểm thử ảnh oversized. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-report-clinical-text-ruo-2026-10-29.log) |
| Browser roundtrip | PASS — 2 ảnh synthetic, API/model/SQLite, persistence/reload, PDF 3 trang, 0 page errors; đường hiện hành không gọi PDF helper này. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-after-report-clinical-text-ruo-2026-10-29.log) |
| Ruff / docs / whitespace | PASS — Ruff 0 findings, release docs 6 passed, Markdown sạch và `git diff --check` exit 0. | [`Ruff`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-clinical-text-ruo-ruff-2026-10-29.log), [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-report-clinical-text-ruo-2026-10-29.log), [`Markdown`](../artifacts/audit_remediation_2026_10_28/evidence/markdown-whitespace-after-report-clinical-text-ruo-2026-10-29.log), [`diff`](../artifacts/audit_remediation_2026_10_28/evidence/git-diff-check-after-report-clinical-text-ruo-2026-10-29.log) |
| PostgreSQL / clinical validation | BLOCKED / NOT TESTED. | [`Go-live assessment`](../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) |

## P1 — calibration gate cho PDF report helper RUO — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Report security + structured report + follicle + patient report | PASS — 44 passed; gồm spacing thiếu/0/âm/NaN/Infinity/sai kiểu, calibrated flag/source, số đo sai kiểu/cực lớn và giữ số đo hợp lệ. | [`targeted report tests`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-calibration-security-targeted-2026-10-29.log) |
| Full Python suite | PASS — 1.347 passed, 0 failed, 0 skipped; một Pillow warning có chủ đích từ kiểm thử oversized image rejection. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-report-calibration-hardening-2026-10-29.log) |
| Live browser roundtrip | PASS — 2 synthetic images; API/model/SQLite persistence & reload region/caliper/CDSS; PDF 3 trang, 0 page errors. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-after-report-calibration-hardening-2026-10-29.log) |
| Ruff | PASS — 0 findings. | [`Ruff`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-calibration-security-ruff-2026-10-29.log) |
| Release docs / Markdown / `git diff --check` | PASS — 6 docs tests; no trailing whitespace; diff check exit 0 (Git reported LF/CRLF normalization notices). | [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-report-calibration-hardening-2026-10-29.log), [`Markdown`](../artifacts/audit_remediation_2026_10_28/evidence/markdown-whitespace-after-report-calibration-hardening-2026-10-29.log), [`diff check`](../artifacts/audit_remediation_2026_10_28/evidence/git-diff-check-after-report-calibration-hardening-2026-10-29.log) |
| PostgreSQL / clinical validation | BLOCKED / NOT TESTED; không có test service, phantom/reference hay bộ ca CDSS được chuyên gia phê duyệt. | [`Go-live assessment`](../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) |

## P1 — RUO report helper input validation — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Report, follicle, patient report và security regression | PASS — 34 passed; kiểm tra side injection, object lồng sai kiểu, count không hợp lệ (kể cả boolean/zero), số cực lớn và trường chẩn đoán không tin cậy. | [`focused report tests`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-untrusted-fields-targeted-2026-10-29.log) |
| Full Python suite | PASS — 1.337 passed, 0 failed, 0 skipped; một Pillow warning có chủ đích trong kiểm thử từ chối ảnh oversized. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-report-input-hardening-2026-10-29.log) |
| Live browser roundtrip | PASS — API/model/SQLite, 2 ảnh synthetic, region/caliper/CDSS lưu và tải lại, report PDF 3 trang, 0 page errors. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-after-report-input-hardening-2026-10-29.log) |
| Ruff | PASS — 0 findings trên helper và regression tests. | [`Ruff`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-input-hardening-ruff-2026-10-29.log) |
| Release documentation tests | PASS — 6 passed. | [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-report-input-hardening-2026-10-29.log) |
| Markdown whitespace / `git diff --check` | PASS — không có trailing whitespace; diff check exit 0 (Git có cảnh báo chuẩn hóa LF/CRLF trên Windows). | [`Markdown`](../artifacts/audit_remediation_2026_10_28/evidence/markdown-whitespace-after-report-input-hardening-2026-10-29.log), [`diff check`](../artifacts/audit_remediation_2026_10_28/evidence/git-diff-check-after-report-input-hardening-2026-10-29.log) |
| PostgreSQL, clinical validation | BLOCKED / NOT TESTED — thiếu driver/server test; chưa có phantom/reference caliper hoặc CDSS case set được chuyên gia phê duyệt. | [`Go-live assessment`](../artifacts/audit_remediation_2026_10_28/go-live-assessment.md) |

## P0 — structured RUO report fail-closed — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| Regression trước sửa | RED — 9 failed, 5 passed: untrusted O-RADS/abstain text và invalid pixel spacing lọt vào report helper. | [`report RED`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-untrusted-output-red-2026-10-29.log) |
| Report/follicle/patient report | PASS — 21 passed; không echo diagnosis fields, không in physical measurement/range count nếu spacing thiếu hoặc sai; spacing hợp lệ giữ được count-in-range. | [`focused tests`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-range-calibration-focused-final-2026-10-29.log) |
| Full Python suite | PASS — 1.330 passed, 0 failed, 0 skipped; một warning Pillow dự kiến do test oversized image. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-ruo-report-hardening-final-2026-10-29.log) |
| Browser roundtrip sau sửa | PASS — 2 ảnh synthetic, region/caliper/calibration/CDSS persistence/reload, report/print PDF 3 trang, 0 page errors. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-after-report-generator-ruo-hardening-2026-10-29.log) |
| Ruff và syntax | PASS. | [`Ruff`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-range-calibration-ruff-green-2026-10-29.log), [`py_compile`](../artifacts/audit_remediation_2026_10_28/evidence/report-generator-range-calibration-syntax-final-2026-10-29.log) |
| Release documentation tests | PASS — 6 passed. | [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-report-generator-hardening-2026-10-29.log) |

## Revalidation — clinical workflow và full suite — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_region_clinical.py -q` | PASS — 18 passed. | [`region clinical`](../artifacts/audit_remediation_2026_10_28/evidence/region-clinical-revalidation-current-turn-2026-10-29.log) |
| `npm run test:e2e:roundtrip` | PASS — 2 ảnh synthetic; live API/model/SQLite; region/caliper/calibration/CDSS persistence/reload/history; report 3 trang; 0 page errors. | [`roundtrip`](../artifacts/audit_remediation_2026_10_28/evidence/roundtrip-region-caliper-cdss-current-turn-2026-10-29.log) |
| `npm run test:e2e:safety` | PASS — 27 checks, 3 viewport, 0 page errors; synthetic approval queue fixture remains read-only. | [`safety E2E`](../artifacts/audit_remediation_2026_10_28/evidence/safety-e2e-current-continuation-2026-10-29.log) |
| `.venv/Scripts/python.exe -m pytest -q` | PASS — 1.319 passed, 0 failed, 0 skipped, 239,66 giây. Một Pillow `DecompressionBombWarning` được tạo có chủ đích bởi test từ chối ảnh 100 MP. | [`Python full`](../artifacts/audit_remediation_2026_10_28/evidence/python-full-after-current-turn-audit-2026-10-29.log) |
| `npm test` | PASS — 133 passed, 0 failed, 0 skipped. | [`frontend full`](../artifacts/audit_remediation_2026_10_28/evidence/frontend-full-after-current-turn-audit-2026-10-29.log) |
| `npm run syntax-check` | PASS — 53 modules qua `node --check`; không phải type-check. | [`frontend syntax`](../artifacts/audit_remediation_2026_10_28/evidence/frontend-syntax-after-current-turn-audit-2026-10-29.log) |
| PostgreSQL/Docker environment probes | BLOCKED — PostgreSQL URL/driver/listener thiếu; Docker Engine pipe không tồn tại. | [`PostgreSQL probe`](../artifacts/audit_remediation_2026_10_28/evidence/postgresql-probe-current-turn-2026-10-29.log), [`Docker probe`](../artifacts/audit_remediation_2026_10_28/evidence/docker-engine-probe-current-turn-2026-10-29.log) |

## Revalidation — recovery runbook demo synthetic — 2026-10-29

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| `tests/test_release_documentation.py` | PASS — 6 passed; kiểm tra ranh giới recovery synthetic và không đánh đồng với backup/restore lâm sàng. | [`release docs`](../artifacts/audit_remediation_2026_10_28/evidence/release-doc-tests-after-recovery-procedure-2026-10-29.log) |
| `npm run test:e2e:harness-cleanup` | PASS — fault-inject browser close acknowledgement; backend dừng, listener được xác nhận đóng, runtime được dọn sau xác minh. | [`cleanup recovery E2E`](../artifacts/audit_remediation_2026_10_28/evidence/demo-recovery-harness-cleanup-e2e-2026-10-29.log) |
| Manual stuck-process/database recovery | NOT TESTED / BLOCKED — không giả lập process treo hoặc khôi phục DB; runbook yêu cầu NO-GO nếu PID/port/marker không khớp. | Chưa có môi trường an toàn để xác minh recovery ngoài harness cleanup. |

## Revalidation — GPU synthetic inference soak — 2026-10-29

- Thay benchmark forward-only bằng pipeline tuần tự trên ảnh synthetic tạo trong RAM: preprocessing production (letterbox + CLAHE), model registry/checkpoint đã đối chiếu SHA-256, segmentation postprocessing và dựng response; 5 lượt warmup + 50 ảnh synthetic khác nhau.
- RTX 3050 Laptop 4 GB: preprocessing p50 13,66 ms; inference pipeline p50 326,54 ms; tổng p50 340,02 ms, p95 nearest-rank 353,39 ms, max 382,70 ms. Peak allocated 585.305.088 byte; sau GC allocated trở về baseline, delta 0 byte; không CPU fallback. Calibration/pixel spacing không truyền vào.
- Unit benchmark: **6 passed**; `py_compile` **PASS**; Ruff **All checks passed**. Raw evidence: [`GPU soak`](../artifacts/audit_remediation_2026_10_28/evidence/gpu-full-pipeline-distinct-synthetic-soak-2026-10-29.log), [unit](../artifacts/audit_remediation_2026_10_28/evidence/gpu-soak-unit-after-distinct-fixtures-2026-10-29.log), [syntax](../artifacts/audit_remediation_2026_10_28/evidence/gpu-soak-syntax-after-distinct-fixtures-2026-10-29.log), [Ruff](../artifacts/audit_remediation_2026_10_28/evidence/gpu-soak-ruff-after-distinct-fixtures-2026-10-29.log).
- Giới hạn: đây không phải HTTP/API latency, concurrency, multi-worker GPU contention, tải PostgreSQL, thao tác người dùng hay xác thực lâm sàng. KI-006 vẫn mở một phần cho tới khi PO/IT đặt SLO và benchmark môi trường đích hoàn tất.

## Baseline — 2026-10-25, nhánh `main`

| Lệnh | Kết quả | Bằng chứng |
|---|---|---|
| `node scripts/type_check.js` | PASS — 49 JS modules qua `node --check`; đây là syntax check, không phải static type analysis. | Kết quả được ghi ở bảng này; raw log tạm đã được dọn ngày 2026-10-26. |
| `npm test` | PASS — 83 pass, 0 fail, 0 skip. | Kết quả được ghi ở bảng này; raw log tạm đã được dọn ngày 2026-10-26. |
| `.venv/Scripts/ruff.exe check .` | PASS — All checks passed. | Kết quả được ghi ở bảng này; raw log tạm đã được dọn ngày 2026-10-26. |
| `.venv/Scripts/python.exe -m pytest -q` | FAIL — 1.057 pass, 4 fail, 2 skip. Các lỗi: report dataset thiếu, Docker copy source thiếu, hai tài liệu release thiếu. | Kết quả baseline được ghi ở bảng này; raw log tạm đã được dọn ngày 2026-10-26. |
| Playwright E2E | Chưa chạy baseline. Cần thay các nguồn ảnh split/dataset thật bằng fixture trước khi chạy. | Chờ sửa QA-001. |

## Lưu ý an toàn dữ liệu

Baseline pytest đã thực thi các test có đọc ảnh từ split/dataset thật. Không chạy lại pytest hoặc E2E cho đến khi `tests/` không còn đường đi lấy ảnh test từ `dataset/`/`ai_training/`. Các lần chạy tiếp theo chỉ dùng fixture tổng hợp do `scripts/generate_synthetic_e2e_fixtures.py` sinh ra hoặc dữ liệu synthetic được tạo trong `tmp_path` cho unit test.

## Các vòng sau

| Vòng | Lệnh/phạm vi | Kết quả | Log | Bug mới/sửa |
|---|---|---|---|---|
| 0 | Baseline | Hoàn tất; xem bảng trên. Raw log tạm đã dọn ngày 2026-10-26. | Tóm tắt được lưu trong tài liệu này. | QA-001–QA-005 |
| 1 | Sửa và xác minh | PASS cho JS, pytest, Ruff, API smoke, các E2E hiện hành; 2 comprehensive pass liên tiếp. Raw log/screenshot tạm đã dọn ngày 2026-10-26. | Tóm tắt được lưu trong tài liệu này. | QA-001–QA-009 đã sửa; KI-006 còn SLO cần xác nhận |

## Vòng 1 — xác minh sau sửa

### Kiểm tra tự động

| Lệnh | Kết quả | Bằng chứng |
|---|---|---|
| `node scripts/type_check.js` | PASS — cú pháp 49 JS modules; không phải static type analysis. | Kết quả được ghi ở bảng này. |
| `npm test` | PASS — 83 pass, 0 fail. | Kết quả được ghi ở bảng này. |
| `.venv/Scripts/python.exe -m pytest -q` | PASS — 1.059 passed, 2 skipped, 0 failed; 68,39 giây. Suite sau sửa chạy trên DB pytest tạm; nguồn ảnh API/E2E đã là fixture tổng hợp hoặc `tmp_path`. | Kết quả được ghi ở bảng này. |
| `.venv/Scripts/ruff.exe check .` | PASS — All checks passed. | Kết quả được ghi ở bảng này. |
| Docker image build | NOT RUN — Docker CLI is present, but Docker Desktop Linux engine is unavailable (`docker version` cannot open `dockerDesktopLinuxEngine`). Pytest's Docker build-context source check passed as part of the full suite; actual image build remains unverified. | Ghi nhận môi trường kiểm thử ngày 2026-10-25. |
| API smoke | PASS — 2 tests. | Kết quả được ghi ở bảng này. |
| Regression test ảnh tổng hợp/data boundary | PASS — 25 tests. | Kết quả được ghi ở bảng này. |
| Xóa Study/telemetry | PASS — 13 tests. | Kết quả được ghi ở bảng này. |

### Browser/API E2E trên fixture tổng hợp

Server dùng `tests/serve_isolated_app.py` với SQLite/runtime riêng; không dùng `ovarian_ai.db`. Các lượt E2E cũ dùng port 8027; `test_live_ui_features.js` hiện tự mở loopback port động qua `tests/helpers/isolated_browser.cjs`, chờ server dừng rồi dọn runtime. Log kiểm định được lưu trong `artifacts/audit_remediation_2026_10_28/evidence/`; dữ liệu dùng là fixture tổng hợp.

| Luồng | Kết quả | Bằng chứng |
|---|---|---|
| Comprehensive workstation — pass 1 | PASS — năm route, ba viewport, cleanup HTTP 200; không có console/page error hoặc request/status lỗi không mong muốn. | Kết quả và ma trận được ghi ở đây; screenshot tạm đã dọn. |
| Comprehensive workstation — pass 2 liên tiếp | PASS — cùng ma trận và điều kiện lỗi. | Kết quả và ma trận được ghi ở đây; screenshot tạm đã dọn. |
| Clinical round-trip | PASS — upload hai fixture, model/review/DB/reopen/report; revision 1, 2 ảnh, 0 page error. | Kết quả được ghi ở đây; log/fixture tạm đã dọn. |
| Clinical safety | PASS — 13 kiểm tra, bao gồm laterality, placeholder, stale revision, quota fallback; 0 page error. | Kết quả được ghi ở đây; log tạm đã dọn. |
| Viewer/HITL | PASS — 4 viewport; 0 page error, 0 unexpected writes. | Kết quả được ghi ở đây; log tạm đã dọn. |
| Browser HITL smoke | PASS — fixture tổng hợp, 0 API write, 0 console/page error. | Kết quả được ghi ở đây; log tạm đã dọn. |
| Doctor workflow | PASS — luồng khám và dọn ca HTTP 200. | Kết quả được ghi ở đây; log tạm đã dọn. |
| Live UI | PASS — login, upload fixture, segmentation, review, worklist, report. | Kết quả được ghi ở đây; log tạm đã dọn. |

Các script legacy `frontend_workflow_e2e.js` và `prototype_modules_e2e.js` không thuộc scripts E2E hiện hành và phụ thuộc endpoint/DOM prototype cũ; không đưa vào pipeline của vòng này cho tới khi audit nguồn dữ liệu/route hoàn tất. SLO p50/p95, concurrency và usability study chưa được đo; không coi kết quả test chức năng là bằng chứng hiệu năng hoặc nghiệm thu lâm sàng.

## Vòng 2 — PID, Visit No và in báo cáo A4 (2026-10-26)

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| `node scripts/type_check.js` | PASS — 49 module qua `node --check`; đây là syntax check, không phải static type analysis. | Chạy sau cập nhật report UI. |
| `npm test` | PASS — 83 pass, 0 fail. | `tests/test_fe_02_report_preview.mjs` kiểm tra O-RADS không lặp nhãn, số đo/đơn vị, phân cấp chữ và header hai bên, Reviewer ID ở mục hỗ trợ cuối trang, cùng quy tắc ngắt trang A4. |
| `.venv/Scripts/python.exe -m pytest -q` | PASS — 1.060 passed, 2 skipped, 0 failed; 69,76 giây. | Gồm migration legacy Visit No, PID ổn định qua hai phiên TestClient, tạo lượt đồng thời, privacy contract và toàn bộ regression suite. |
| `.venv/Scripts/ruff.exe check .` | PASS — All checks passed. | Chạy trên repo sau cập nhật backend/tests. |
| `npm run test:e2e:roundtrip` | PASS — upload, rà soát, mở lại ca và in PDF; xác nhận PID/Visit, hai bên, trạng thái đã rà soát, Reviewer ID chỉ ở mục hỗ trợ cuối; 2 ảnh tổng hợp, PDF đúng 2 trang A4, preview 390×844 không tràn ngang, 0 page error. | `tests/clinical_roundtrip_e2e.js`; DB và ảnh test tổng hợp cô lập. |
| `npm run test:e2e:safety` | PASS — 13 safety gates; persisted reviewer/revision, unreviewed overlay state, stale revision, failed-save print gate; 0 page error. | `tests/clinical_safety_e2e.js`; browser và DB cô lập. |
| `npm run test:e2e:live` | PASS — đăng nhập, intake song phương, inference, review, worklist thumbnails, mở lại, report/print path. | `tests/test_live_ui_features.js` tự khởi chạy `startIsolatedBrowser`: loopback port động, SQLite/runtime tạm riêng và cleanup sau test; đăng ký email dùng phản hồi giả lập, luồng intake/inference/review dùng backend thật với ảnh synthetic. |

Không đo hiệu năng p50/p95 hoặc nghiệm thu lâm sàng trong vòng này. PDF và screenshot chỉ dùng fixture tổng hợp; không lấy ảnh nguồn bệnh nhân.

## Vòng 3 — intake đa ảnh, caliper và report RUO (2026-10-27)

Vòng này xác minh các thay đổi workstation sau khi review sản phẩm v2.1. Browser/API E2E dùng ảnh synthetic, server cô lập và SQLite riêng; không huấn luyện model hoặc đọc ảnh bệnh nhân. Trong round-trip, caliper D1 được bác sĩ đặt trên ảnh nguồn, lưu ở đơn vị pixel khi không có calibration và được khôi phục trong report.

| Lệnh/phạm vi | Kết quả | Bằng chứng |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | PASS — 1.122 passed, 2 skipped, 0 failed; 74,20 giây. | Toàn bộ suite sau cập nhật backend/schema và fail-closed clinical copy. |
| `npm test` | PASS — 90 passed, 0 failed. | Bao gồm draft mask/caliper theo từng ảnh và phân trang A4 động. |
| `npm run syntax-check` | PASS — 49 JavaScript modules qua `node --check`; không phải static type analysis. | Chạy sau sửa intake readiness và telemetry caliper. |
| `npm run test:e2e:roundtrip` | PASS — đăng nhập, intake, upload hai ảnh synthetic, inference, đặt/lưu D1, review, mở lại và in; revision 1, 2 ảnh, đúng 3 trang A4, 0 pageerror/error toast. | `tests/clinical_roundtrip_e2e.js`; ảnh chưa hiệu chuẩn được ghi `px`, không bịa mm; screenshot desktop/mobile và hai trang in được sinh trong `artifacts/qa-clinical-fixed/`. |
| `npm run test:e2e:safety` | PASS — 15 kiểm tra, 0 pageerror; xác nhận intake mơ hồ/lệch bên, swap, ca một bên, lưu/in, draft và revision. | `tests/clinical_safety_e2e.js`; mọi ghi lâm sàng dùng fixture tổng hợp hoặc mock có chủ ý. |
| `git diff --check` | PASS — không có whitespace error; Git phát cảnh báo quy tắc đổi LF/CRLF trên working tree Windows. | Cảnh báo line ending không làm thay đổi kết quả test. |

Trong vòng này, E2E phát hiện và đã sửa bốn lỗi: CTA intake bị khóa do trạng thái ảnh chỉ tính một lần lúc render; đặt caliper gọi nhầm API telemetry gây pageerror; cặp ảnh gốc/lớp phủ xếp dọc làm report tràn khỏi số trang dự kiến; thao tác “Ca tiếp theo” báo lỗi giả khi request bị hủy do điều hướng bình thường. Không đo hiệu năng p50/p95 và không có xác thực lâm sàng. Cổng huấn luyện classifier vẫn `BLOCKED` do identity/nhãn độc lập chưa được xác minh; xem [Model Card](../MODEL_CARD.md) và [known issues](known-issues.md).
