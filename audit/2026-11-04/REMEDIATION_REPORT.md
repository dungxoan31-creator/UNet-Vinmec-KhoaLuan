# Báo cáo remediation và xác minh — 05/11/2026

## 1. Kết luận điều hành

**NO-GO cho triển khai chăm sóc người bệnh hoặc staging pilot đa cơ sở.** Follow-up ngày 05/11 đã chuyển registry sang checkpoint ComboLoss có SHA-256 đối chiếu được và xác minh model tải thành công trong runtime cô lập. Luồng song phương synthetic đã đi hết viewer, review, lưu và in báo cáo. Checkpoint vẫn là `candidate_only`; independent gate, patient-level independence và clinician validation vẫn BLOCKED/false. AUD-013 và AUD-018 đã VERIFIED; AUD-020 vẫn chờ sign-off chuyên môn.

Trong 25 phát hiện của kiểm toán gốc:

| Trạng thái remediation | Số lượng | Ghi chú |
|---|---:|---|
| VERIFIED | 24 | Gồm AUD-013, AUD-018 và phần provenance/loss của AUD-024 được xác minh trong follow-up tổng hợp. |
| PARTIAL | 1 | AUD-020: cutoff `<30 mm` còn giữ nguyên đến khi có sign-off của bác sĩ chuyên khoa/giảng viên. |
| BLOCKED | 0 | Không còn blocker model provenance/loss trong cấu hình research candidate; clinical/deployment gates vẫn mở và giữ NO-GO. |

Trong quá trình xác minh phát hiện thêm 3 lỗi implementation/test-path (RM-001–RM-003); đã sửa và kiểm tra bằng test tổng hợp. Tổng issue được theo dõi hiện là 28: **27 VERIFIED, 1 PARTIAL, 0 BLOCKED trong phạm vi kỹ thuật đã ghi rõ** (24/25 phát hiện gốc và 3 phát hiện bổ sung). Trạng thái `CONFIRMED` trong phần gốc của `ISSUE_REGISTER.md` vẫn giữ nguyên để bảo toàn kết quả kiểm toán ngày 04/11.

| Phân loại phát hiện | P0 | P1 | P2 | P3 | Tổng |
|---|---:|---:|---:|---:|---:|
| Kiểm toán gốc | 1 | 7 | 14 | 3 | 25 |
| Phát hiện bổ sung RM-001–003 | 0 | 0 | 3 | 0 | 3 |
| Tổng ledger | 1 | 7 | 17 | 3 | 28 |

## 2. Phạm vi và phương pháp

Kiểm toán gốc lập inventory 412 file backend/frontend/AI/tests/deploy, 121 khai báo route decorator (không đồng nghĩa 121 endpoint duy nhất), 25 ORM entity tại thời điểm đó, 31 route family màn hình, 42 feature. Coverage baseline chi tiết vẫn ở [SCREEN_COVERAGE.csv](SCREEN_COVERAGE.csv), [FEATURE_COVERAGE.csv](FEATURE_COVERAGE.csv), [MODULE_COVERAGE.csv](MODULE_COVERAGE.csv), [api-coverage.csv](api-coverage.csv) và `coverage-summary.json`.

Verification dùng test fixture ảnh và tài khoản tổng hợp, SQLite tạm, browser/server cô lập. Không đọc hoặc ghi database mặc định, production data, ảnh bệnh nhân, hay gửi email/OTP ra ngoài. Các test inference API dùng stub tất định chỉ trong process test; stub không có checkpoint hash, không đại diện model, và không được dùng để kết luận hiệu năng lâm sàng.

Không chạy lại nguyên trạng `tenant-probe.py`, `store-probe.mjs`, `final-browser.cjs`: các script kiểm toán gốc ghi vào `audit/2026-11-04/probe-runtime`, ghi đè kết quả/ảnh/PDF cùng thư mục, và `final-browser.cjs` mở browser hiển thị. Thay vào đó dùng test tương đương trên temp runtime mới, gồm tenant role/isolation, CRUD danh bạ qua hai browser context, mobile capture, report print handler, safety E2E và regression suites. File audit gốc được giữ làm bằng chứng baseline.

## 3. Kết quả remediation theo nhóm

### Danh tính, tenant và dữ liệu

- PID nguồn được phân namespace theo cơ sở trong HMAC/uniqueness contract. Test xác nhận cùng PID tổng hợp ở hai facility tạo hai patient identity khác nhau; endpoint đọc ca chéo cơ sở tiếp tục bị từ chối. Bản ghi legacy liên kết nhiều cơ sở fail startup để chờ reconciliation có người duyệt; không tự tách/copy demographic thiếu căn cứ.
- Settings được lưu theo facility; global admin phải chọn facility đang hoạt động; backup toàn database giới hạn global admin và lưu trong `APP_BACKUP_DIR`/`APP_DATA_DIR`. Khi audit write thất bại, archive vừa tạo được dọn trong test. Không có API restore trong sản phẩm; chỉ xác minh restore archive tổng hợp vào `tmp_path`.
- Patient Directory CRUD lưu phía server theo facility, dùng phiên bản để từ chối cập nhật stale, không lưu PID nguồn; non-demo list rỗng giữ nguyên và logout xóa cache định danh cũ. E2E hai context xác nhận hồ sơ tổng hợp dùng chung theo server và hồ sơ đã gỡ không còn trong lookup thường.
- Form intake không hỏi/khởi tạo PID nguồn. Tuổi chỉ được nhập khi đã xác minh tại ngày khảo sát; năm sinh không tự suy thành tuổi. Case/PID nghiên cứu và Visit được trình bày theo phạm vi riêng.
- Bootstrap password không ghi đè hash tài khoản đã tồn tại. Flow đổi mật khẩu áp dụng token mới theo response.

### API, validation và migration

- `/api/v1/segment` xác thực source, file, kích thước, suitability và case lease trước khi kiểm tra model readiness. Test xác nhận lỗi file quá cỡ/lease không bị che bởi 503 model; request hợp lệ vẫn bị fail-closed khi checkpoint chưa sẵn sàng.
- Thứ tự migration đã thêm `patient_directory` trước bảng phụ thuộc. Test migration SQLite tổng hợp đạt; không có PostgreSQL server cô lập nên chưa xác nhận behavior trên native PostgreSQL.
- Full-database backup/restore không chạy trên database mặc định. Test backup dùng database tổng hợp ở thư mục tạm.

### UI/UX và báo cáo

- Thanh action intake không đè dropzone. Sau khi thu gọn layout, CTA “Phân tích ảnh” xuất hiện tự nhiên tại y=585.8–629.8 trong viewport 1366×768 (scrollTop=0); E2E ghi nhận không tràn ngang. Ở 768×768, CTA vẫn thấp hơn viewport ban đầu và cần cuộn. Xem `artifacts/qa-next-steps-2026-11-05-r2/safety-results.json` và `intake-1366.png`.
- Runtime ở 390×844 xác nhận tên hồ sơ hiển thị một dòng, nhãn “Bệnh nhân / Năm sinh” khớp cột, document không tràn ngang; trường datetime rộng 253 px và nằm trong viewport. Phát hiện stylesheet cũ còn giả định bốn cột (“PID mẫu / Tên / Tuổi / Thao tác”) trong khi DOM chỉ có ba cột; đã sửa map theo `data-label` và kiểm tra ảnh sau sửa.
- Report header theo facility, contralateral status, O-RADS, phân biệt ghi chú bác sĩ với AI, status lưu, save toast và lỗi mạng có test tương ứng.
- PDF follow-up A4 được in từ snapshot synthetic đã lưu: `artifacts/qa-next-steps-2026-11-05-r2/report-followup.pdf`; text được trích xuất trực tiếp và trang 1 được render để kiểm tra bố cục (`report-followup-page1-render.png`). Trang 1 có ghi chú bác sĩ riêng cho cả hai bên; trang 2–3 giữ ảnh, overlay và số đo pixel; trang 4 giữ provenance model/hash. E2E xác nhận 4 trang và không có lỗi trình duyệt. Artifact chỉ dùng ảnh/mask tổng hợp, không phải report lâm sàng.

### O-RADS, AI và clinical safety

- UI/rule engine/analytics vẫn theo ruleset nội bộ có version; đúng 30 mm chưa tự động phân loại sinh lý. ACR O-RADS US v2022 nêu follicle sinh lý `≤3 cm`. Người dùng chọn chuẩn hóa thành `≤30 mm` sau sign-off; chưa có bằng chứng sign-off, nên AUD-020 PARTIAL và mã nguồn/chính sách `<30 mm` chưa đổi. [Nguồn ACR chính thức](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf).
- Các fixture kiểm tra DICOM chỉ dùng metadata/ảnh tổng hợp; xác minh PHI cleaning/spacing, không chứng minh phát hiện được mọi chữ PHI burned-in trong pixel.
- Không có independent evidence về sensitivity/specificity, calibration, patient-level independence hoặc hiệu quả lâm sàng. Không suy diễn kết quả từ test stub, ảnh synthetic hay metric image-level.
- `evaluation/selected_model.json` hiện tham chiếu checkpoint U-Net++/ResNet34 ComboLoss có SHA-256 `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76`; hash khớp metadata huấn luyện/selection và model tải thành công. Manifest giữ `candidate_only: true`, `independent_gate_status: BLOCKED`, `clinician_validation: false`, `test_evaluation: null`. Đây là xác minh provenance cho research candidate, không phải xác minh hiệu năng hay phê duyệt sử dụng lâm sàng.

## 4. Regression và browser evidence

| Chạy | Kết quả | Phạm vi |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest -q --tb=short` (sau follow-up) | **1614 passed, 0 failed**, 2 warnings, 329.76 s | Full Python suite. Warnings: Python 3.12 sqlite date-adapter deprecation; Pillow decompression-bomb warning từ test negative ảnh 100M pixel. |
| Node direct-file suite (`node --test` trên test files ở `tests/`, baseline trước follow-up) | **173 passed, 0 failed**, ~13.8 s | Toàn bộ Node suite ở lần chạy trước các thay đổi follow-up. Khi đó bilateral subscenario còn bị 503; không coi run cũ này là inference pass. |
| Follow-up `tests/test_model_selection.py` | **8 passed** | Hash/model-selection contract sau khi đổi manifest sang ComboLoss candidate. |
| Follow-up `tests/test_fe_02_report_preview.mjs` | **12 passed** | Summary notes, ảnh theo từng trang và provenance sau summary. |
| `tests/test_frontend_clinical_copy.py` | **7 passed** | Copy/clinical labels sau mobile change. |
| `tests/clinical_safety_e2e.js` | **PASS**, 30 checks, 0 page errors | Reviewer read-only queue, isolation, laterality/intake safety, save gating và report handler trên synthetic fixtures; clinical writes mock. CTA geometry at 1366×768 captured. |
| `tests/clinical_roundtrip_e2e.js` | **PASS**, 2 images, 4 PDF pages, 0 page errors | Synthetic intake → bilateral upload → model inference → viewer/review → save/reopen → report/print. |
| `tests/doctor_workflow_e2e.js` | **PASS**, 2 images, 4 PDF pages, 0 page errors | Synthetic doctor login/intake/review/report and responsive doctor/admin route matrix. |
| `artifacts/qa-clinical-fixed/mobile-intake-probe.cjs` | **OBSERVED**, exit 0 | Browser 390×844, patient row và datetime trên temp SQLite; ảnh/JSON nằm dưới `artifacts/qa-clinical-fixed/mobile-intake-2026-11-05/`. |
| Regression nhóm segment/roles/migration | **58 passed** | Focused API validation, role matrix, synthetic migration và SQLite tests. |

Lần full Python đầu sau khi chọn checkpoint phát hiện hai failure: test admin vẫn giả định checksum luôn `null`, và manifest thiếu nhãn metric validation. Test admin hiện đối chiếu checksum với trạng thái primary adapter; manifest ghi rõ đây là image-level pixel recall, không phải clinical sensitivity. Hai test tập trung và lần full suite tiếp theo đều pass. Full Node suite 173 pass là baseline trước follow-up; report tests và E2E song phương đã chạy sau thay đổi. `git diff --check` trả exit 0; Git vẫn báo line-ending normalization (LF→CRLF) cho các file dirty.

Không ghi thời gian hoàn tất ca hoặc interaction count vì E2E không đo các chỉ số đó. `tests/e2e/test_comprehensive_workstation.js` vẫn NOT TESTED; các luồng intake/viewer/review/save/reopen/report/print được kiểm tra qua hai E2E song phương riêng. Không có PostgreSQL/Docker/native deployment evidence.

## 5. Disposition của 25 issue gốc

| ID | Trạng thái hiện tại | Evidence chính / giới hạn |
|---|---|---|
| AUD-001 | VERIFIED | `tests/test_patient_identity.py`; `tests/test_facility_isolation_p0.py`. Legacy collision cần reconciliation thủ công. |
| AUD-002 | VERIFIED | `tests/test_tenant_admin_hardening.py`; facility scope/role matrix. |
| AUD-003 | VERIFIED | `tests/test_backup_service_sandbox.py`; `tests/test_tenant_admin_hardening.py`. Restore chỉ test archive synthetic trong `tmp_path`; sản phẩm không có restore API. |
| AUD-004 | VERIFIED | `tests/test_patient_directory_api.py`; `tests/test_patient_crud_e2e.mjs`. |
| AUD-005 | VERIFIED | `tests/test_patient_store_crud.mjs`; empty non-demo directory trong browser E2E. |
| AUD-006 | VERIFIED | `tests/password_change_session_e2e.js`; token mới được áp dụng trong phiên test. |
| AUD-007 | VERIFIED | `tests/test_database_startup_safety.py`; isolated restart/SQLite. |
| AUD-008 | VERIFIED | `tests/test_case_creation_concurrency.py`; patient-directory version/concurrency tests. |
| AUD-009 | VERIFIED | `tests/test_patient_store_crud.mjs`; empty list không tự sinh lại seed. |
| AUD-010 | VERIFIED | `tests/test_intake_session.mjs`; logout/account-switch E2E. |
| AUD-011 | VERIFIED | `tests/test_patient_directory_api.py`; `tests/test_patient_id_optional_r2.py`. |
| AUD-012 | VERIFIED | `tests/test_frontend_intake_patient_id.mjs`; report/case label tests. |
| AUD-013 | VERIFIED | `safety-results.json`: CTA tự nhiên ở y=585.8–629.8, scrollTop=0 tại 1366×768; E2E pass. |
| AUD-014 | VERIFIED | Mobile probe: datetime 253 px, không clip tại 390×844. |
| AUD-015 | VERIFIED | Mobile probe + screenshot: patient name một dòng; column labels match HTML. |
| AUD-016 | VERIFIED | `tests/test_fe_02_report_preview.mjs`; `tests/test_v21_report_generator.py`. |
| AUD-017 | VERIFIED | Report header facility contract/UI tests; report preview tests. |
| AUD-018 | VERIFIED | `report-followup.pdf`, `report-followup-page1-render.png` + extracted text: ghi chú hai bên nằm trang 1; ảnh theo bên ở trang 2–3; provenance trang 4. |
| AUD-019 | VERIFIED | `tests/test_admin_reports.py`; `tests/test_admin_analytics_ui.mjs`: null khác measured zero. |
| AUD-020 | PARTIAL | `tests/test_cdss_boundary_30mm_r8.py`; source giữ `<30 mm`. User chọn đổi sang `≤30 mm` sau sign-off; chưa có bằng chứng sign-off. |
| AUD-021 | VERIFIED | `tests/admin_reports_keyboard_e2e.js`; `tests/test_admin_analytics_ui.mjs`. |
| AUD-022 | VERIFIED | `tests/test_review_save.mjs`: chỉ báo đúng bên/ảnh đã lưu. |
| AUD-023 | VERIFIED | `tests/test_api_session.mjs`; `tests/test_review_save.mjs`: lỗi mạng có hướng xử lý tiếng Việt. |
| AUD-024 | VERIFIED — research provenance only | `test_model_selection.py`, hash `ce758032…591e76`, `clinical_roundtrip_e2e.js`, `doctor_workflow_e2e.js`. Independent validation/patient-level independence/clinical readiness vẫn BLOCKED. |
| AUD-025 | VERIFIED | `tests/test_fe_02_report_preview.mjs`: pseudonym/print layout. PDF hiện tại dùng fixture ID ngắn, không phải bằng chứng hash dài. |

## 6. Phát hiện bổ sung trong verification

| ID | Severity | Finding | Remediation/evidence |
|---|---|---|---|
| RM-001 | P2 | Model readiness check trong `/api/v1/segment` chạy trước input/lease validation, che lỗi 413/423 bằng 503. | Đưa readiness gate sau validation; `tests/test_v1_segment_limits.py`, `tests/test_case_leases.py`, `tests/test_model_registry_fail_closed.py`; test nhóm 58 passed. |
| RM-002 | P2 | Thứ tự migration thiếu `patient_directory` trước bảng phụ thuộc. | Bổ sung vào topological `TABLE_ORDER`; `tests/test_sqlite_to_postgres_migration.py` synthetic pass; native PostgreSQL chưa kiểm chứng. |
| RM-003 | P2 | Mobile CSS dùng lại selector 4 cột cũ nên nhãn “PID mẫu/Tuổi” lệch dữ liệu patient name/year/actions. | Cập nhật 3-column mapping bằng `data-label`; browser red/green probe và ảnh 390×844 chứng minh label đúng, name một dòng. |

## 7. Coverage matrix hiện tại

| Phạm vi | Coverage | Trạng thái |
|---|---|---|
| Screen/route family (baseline) | 31 phát hiện; 28 inspected một phần; 1 BLOCKED; 2 NOT TESTED | Không tuyên bố mọi modal/state/role đã được kiểm tra. |
| Features (baseline) | 42; 18 TESTED; 14 PARTIALLY TESTED; 4 BLOCKED; 6 NOT TESTED | Bổ sung remediation E2E không làm các feature còn lại thành pass. |
| API (baseline) | 121 route decorator declarations; 37 có request/response quan sát | Coverage một phần; aliases/branch/role matrix chưa hết. |
| Core Python/Node tests | Python follow-up: 1614 pass; Node baseline: 173 pass; focused report tests + E2Es pass | Node full suite chưa chạy lại sau follow-up; software tests không phải clinical validation. |
| Bilateral AI → viewer → review → reopen → print | E2E synthetic hoàn tất, 2 ảnh, PDF 4 trang | TESTED trong isolated SQLite/server với research candidate; không chứng minh clinical validation. |
| Native PostgreSQL/Docker/multi-worker | Chưa có isolated service | BLOCKED; chỉ SQLite synthetic tests. |
| Clinical validation / patient-level independence / signed report workflow | Chưa có hồ sơ xác minh độc lập | NOT TESTED/BLOCKED; không cấp staging pilot. |

## 8. Hành động còn mở (chưa triển khai)

1. Chạy independent validation với split phù hợp và xác minh patient-level independence, clinical performance, calibration, model limitations, and clinician governance. Candidate remains research-only; no deployment gate is cleared by synthetic E2E.
2. Lấy sign-off có ghi nhận từ bác sĩ chuyên khoa/giảng viên cho quy tắc nang noãn đúng 30 mm; chỉ sau đó mới đổi versioned ruleset, labels và tests sang `≤30 mm`.
3. Kiểm tra report page breaks bằng các ghi chú/mô tả dài hơn trên synthetic data và xác minh trên trình in/PDF khác nhau trước khi chấp nhận bố cục.
4. Xác minh CTA ở các viewport/zoom/browser mục tiêu; tại 768×768 hiện còn cần cuộn.
5. Xác minh backup/restore policy, PostgreSQL, Docker, multi-worker, authentication/email và deployment ở sandbox chuyên dụng trước bất kỳ staging pilot nào.
6. Hoàn tất independent diff review. Worktree có 245 path bẩn lúc bắt đầu và 292 status entries ở lần kiểm tra cuối; lần review này tập trung vào critical flows/test artifacts, không thể chứng minh toàn bộ diff hiện tại thuộc remediation này.

**Kết luận cuối:** focused tests và hai E2E song phương synthetic đã đạt; full-suite baseline chưa được chạy lại sau follow-up. Model inference hiện chạy với research candidate đã đối chiếu provenance, nhưng clinical validation, policy O-RADS, native database/deployment và independent diff review còn mở. Hệ thống chưa sẵn sàng cho pilot lâm sàng đa cơ sở.
