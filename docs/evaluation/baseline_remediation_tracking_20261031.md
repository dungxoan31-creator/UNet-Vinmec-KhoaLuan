# Bảng Kiểm soát Khắc phục Lỗi Lâm sàng (R0 - R9)

> **Mục tiêu**: Giữ nguyên toàn bộ các thay đổi chưa commit trên nhánh `temp/ui-e2e-remediation-20261029`, phân định rõ quyền sở hữu file của từng gói task, và xác minh thực nghiệm trước khi công bố.

| Gói | Lỗi liên quan | File phụ trách | Test tái hiện trước sửa | Thay đổi dự kiến | Test kiểm chứng sau sửa | Trạng thái | Commit |
|---|---|---|---|---|---|---|---|
| **R0** | Baseline tracking | `docs/evaluation/baseline_remediation_tracking_20261031.md`, `docs/evaluation/baseline_worktree_status_20261031.txt` | N/A | Khóa baseline và lập bảng theo dõi | N/A | **Hoàn thành** | `e5a6b71` |
| **R1** | E2E-SEC-001, E2E-SEC-002 | `backend/services/facility_service.py`, `backend/app/routers/cases.py`, `backend/app/routers/visits.py`, `backend/services/case_lease_service.py` | `tests/test_facility_isolation_p0.py` | Fail-closed tenant isolation | `tests/test_facility_isolation_p0.py` | **Hoàn thành** | `ab6f967`, `30205ad` |
| **R2** | Violate Core Scope | `backend/db/database.py`, `backend/schemas/schemas.py`, `frontend/app/upload.js`, `frontend/app/intake.js` | `tests/test_patient_id_optional_r2.py`, `tests/test_frontend_intake_patient_id.mjs` | Make patient_id optional, drop BN-* | `tests/test_patient_id_optional_r2.py`, `tests/test_frontend_intake_patient_id.mjs` | **Hoàn thành** | `dd72d98`, `ca39015` |
| **R3** | E2E-AUTH-001 | `backend/app/routers/admin.py`, `backend/schemas/schemas.py`, `frontend/app/admin-users.js` | `tests/test_admin_user_onboarding_r3.py` | Credential handover dialog, valid reset JSON | `tests/test_admin_user_onboarding_r3.py` | **Hoàn thành** | `d4d6791` |
| **R4** | Contract Gaps | `backend/schemas/schemas.py`, `backend/app/routers/cases.py`, `frontend/app/notifications.js` | `tests/test_api_contracts_r4.py` | CaseItem response model, graceful capabilities | `tests/test_api_contracts_r4.py` | **Hoàn thành** | `f7aa1fd` |
| **R5** | Orphan Visits, 500 | `backend/app/routers/visits.py`, `backend/app/main.py` | `tests/test_visit_constraints_r5.py` | Study FK check, lock consistency, 500 logging | `tests/test_visit_constraints_r5.py` | **Hoàn thành** | `fa8702c` |
| **R6** | Event loop block, 401 | `backend/app/routers/inference.py`, `frontend/app/api.js` | `tests/test_async_image_decode_r6.py`, `tests/test_api_session.mjs` | run_in_threadpool, dispatch ova:expired on 401 | `tests/test_async_image_decode_r6.py`, `tests/test_api_session.mjs` | **Hoàn thành** | `1691d35` |
| **R7** | E2E-UI-001, E2E-A11Y-* | `frontend/css/workspace.css`, `frontend/app/navigation.js` | `tests/test_viewer_geometry_r7.mjs` | Flex wrap header, min-height, contrast & aria-label | `tests/test_viewer_geometry_r7.mjs` | **Hoàn thành** | `d108a3d` |
| **R8** | Boundary & Copy | `backend/services/cdss_engine.py`, `backend/services/inference_engine.py`, `backend/services/report_generator.py` | `tests/test_cdss_boundary_30mm_r8.py` | <= 30mm support, rename mask confidence | `tests/test_cdss_boundary_30mm_r8.py` | **Hoàn thành** | `a260ca0` |
| **R9** | Payload Bloat | `backend/services/inference_engine.py`, `backend/schemas/schemas.py`, `backend/app/routers/inference.py` | `tests/test_payload_pruning_r9.py` | Make overlay_base64 optional/on-demand | `tests/test_payload_pruning_r9.py` | **Hoàn thành** | `60f93c6` |

---

## Báo cáo Khắc phục Vòng 2 (Remediation Round 2 Verification - 01/11/2026)

Tất cả 10 gói R0 - R9 đã được rà soát sâu, vá triệt để các lỗ hổng rò rỉ cơ sở dữ liệu và hoàn tất xác minh thực nghiệm:

1. **R1 (P0) - Cách ly Cơ sở Tuyệt đối (Fail-Closed Isolation)**:
   - Toàn bộ router ảnh y tế (`viewer-source`, `mask.png`, `source.png`, `measurements`, `calibrate`, `predict`) đều kiểm tra `check_facility_access(current_user, study.facility_id)`.
   - Router rà soát lâm sàng `backend/app/routers/reviews.py` và `review_service.py` bổ sung chốt chặn `_require_study_access` cho tất cả các endpoint: vùng gán nhãn, calipers, CDSS assessments, proposals, candidate, và research export.
   - Endpoint tạo ứng viên phân đoạn `backend/app/routers/v1_endpoints.py` (`POST /api/v1/segment/candidate`) bổ sung dependency `require_clinical` và kiểm tra quyền cơ sở của ca khám.
   - Luồng upload trực tiếp `POST /api/upload` bắt buộc người dùng lâm sàng phải có cơ sở y tế và gán chính xác `study.facility_id`.

2. **R2 (P1) - Bảo toàn Core Scope & Xóa Bỏ Mã Bệnh Nhân Giả**:
   - Loại bỏ hoàn toàn tiền tố tự sinh `ANON-UPLOAD-*` và `BN-*`. Khi upload trực tiếp không kèm định danh bệnh nhân, bản ghi được lưu với `patient_id = None` và `study_code` tiêu chuẩn `STD-YYMMDD-XXXX`.

3. **R3 (P1) - Đồng Bộ Luồng Bàn Giao Tài Khoản & Mật Khẩu Tạm**:
   - Đồng bộ văn bản hướng dẫn trên form `frontend/app/admin-users.js` khớp chính xác với hộp thoại hiển thị mật khẩu tạm một lần duy nhất cho quản trị viên bàn giao cho bác sĩ.

4. **R4 (P1/P2) - Chuẩn Hóa Schema Hợp Đồng API & DTO**:
   - Bổ sung `CaseCreateResponse` và `CaseDetailResponse` (kèm các submodel `CaseDetailImage`, `CaseDetailImagePrediction`, `CaseDetailImageReview`) trong `backend/schemas/schemas.py`.
   - Gắn `response_model` cho `POST /api/cases` và `GET /api/cases/{study_id}`.
   - Xử lý êm endpoint đánh dấu thông báo đã đọc `POST /api/notifications/read`, trả về `{"status": "SUCCESS", "updated": count}` thay vì quăng lỗi 501.

5. **R5 (P2) - Ràng Buộc Ca Khám - Lượt Khám & Xác Thực HMAC Danh Tính**:
   - Tạo visit kiểm tra tính tương thích danh tính bệnh nhân giữa ca khám và lượt khám thông qua keyed HMAC digest (`patient_id_digest`), ngăn ngừa mâu thuẫn bệnh nhân hoặc liên kết nhầm cơ sở.
   - Tự động kế thừa danh tính bệnh nhân hợp lệ khi tạo lượt khám liên kết mà không truyền lại PID.

6. **R6 (P2) - Tránh Nghẽn Event Loop**:
   - Offload toàn bộ quá trình giải mã ảnh raster và trích xuất DICOM calibration spacing sang `run_in_threadpool`.

7. **R7 (P2) - Sửa Ghi Đè CSS Responsive**:
   - Đưa các rule CSS `.viewer-head` trong `frontend/css/workstation-premium.css` vào `@media (min-width: 1025px)` kèm `height: auto; min-height: 48px; flex-wrap: wrap;`, chấm dứt hiện tượng ghi đè làm vỡ layout dạng grid trên máy tính bảng (tablet 641px - 1024px).

8. **R8 (P2) - Rà Soát Ngữ Nghĩa CDSS & Báo Cáo**:
   - CDSS Engine hỗ trợ chuẩn hóa biên $\le 30\text{ mm}$ (nang noãn sinh lý) và các mốc kích thước O-RADS/IOTA.
   - Báo cáo phân định rõ ràng giữa xác suất phân đoạn pixel AI (`mask_pixel_confidence`) và nguy cơ ác tính CDSS, giữ vững phạm vi RUO.

9. **R9 (P3) - Tối Ưu Tải Payload (On-Demand Overlay)**:
   - Duy trì mặc định tương thích ngược `generate_overlay = True` cho các client truyền thống, đồng thời hỗ trợ tham số `generate_overlay=False` giúp giảm tải dung lượng phản hồi AI.

### Kết Quả Kiểm Thử Thực Nghiệm (Vòng 2)
- **Pytest**: 53/53 tests PASS (100% xanh)
- **Node.js**: 29/29 tests PASS (100% xanh)
- **Git Status**: Toàn bộ thay đổi dirty có sẵn trên worktree được bảo toàn nguyên vẹn.

---

## Báo cáo Khắc phục Toàn diện & Đóng Tồn dư (Comprehensive Remediation Closure - 01/11/2026)

Kế hoạch chi tiết tại [docs/superpowers/plans/2026-11-01-comprehensive-remediation-closure.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/superpowers/plans/2026-11-01-comprehensive-remediation-closure.md).

### 1. Chi tiết Khắc phục theo Hạng mục
1. **Tenant Isolation & Admin Hardening (HITL & Audit)**:
   - HITL session detail (`/api/hitl/sessions/{id}`) kiểm tra quyền cơ sở; truy cập chéo cơ sở bị từ chối 403.
   - Batch UI events (`POST /api/hitl/events`) áp dụng chính sách fail-closed: nếu chứa bất kỳ case_id nào ngoài cơ sở, từ chối toàn bộ 403, không ghi một phần.
   - Facility admin chỉ thấy audit logs liên kết với study, image, review, hoặc visit thuộc cơ sở của mình.
   - Endpoint `/api/admin/cases` xử lý nhất quán `offset` và `limit`; fallback `page`/`page_size` khi không truyền.
2. **Schema & Migration (Assignee, Correction Requests, Persistent Notifications)**:
   - Thêm `assignee_id` vào `StudyModel` kèm quan hệ `assignee`.
   - Bổ sung bảng `correction_requests` (lưu draft sửa, ghi chú, trạng thái `PENDING`/`SUBMITTED`/`ACCEPTED`/`REJECTED`).
   - Bổ sung bảng `notifications` lưu thông báo bền vững kèm `dedup_key`.
   - Cung cấp cơ chế migration an toàn lặp lại (idempotent) trong `init_db`.
3. **Phân công Ca (Assignment) & Tự nhận Ca (Claim)**:
   - `POST /api/workspace/cases/{id}/assign`: Admin cơ sở phân công bác sĩ cùng cơ sở; global admin phân công bác sĩ thuộc cơ sở của study; ca đang có lease hợp lệ trả về 409 Conflict mà không thu hồi lease. Gửi notification `CASE_ASSIGNED` trong cùng transaction.
   - `POST /api/workspace/cases/{id}/claim`: Bác sĩ tự nhận ca chưa có assignee bằng cập nhật nguyên tử. Ca đã có người nhận trả về 409. Không gửi thông báo cho chính người claim.
4. **Luồng Yêu cầu Sửa (Correction Workflow) cho Kỹ thuật viên (TK)**:
   - `POST /api/workspace/cases/{id}/corrections`: Bác sĩ yêu cầu TK cùng cơ sở chỉnh sửa kèm lý do và notification `CORRECTION_REQUESTED`.
   - `PUT /api/workspace/cases/{id}/corrections`: TK được giao gửi bản sửa dự thảo (`SUBMITTED`), tăng `review_revision`. TK bị chặn toàn bộ các route duyệt, ký hoặc hành động lâm sàng.
5. **Hệ thống Thông báo Bền vững (Persistent Notifications)**:
   - `GET /api/notifications`: Trả về tối đa 100 thông báo mới nhất thuộc quyền sở hữu của user hiện tại.
   - `POST /api/notifications/read`: Cập nhật trạng thái đã đọc chỉ cho các thông báo của user hiện tại, trả về số lượng thực tế đã cập nhật.
6. **Đồng bộ Patientless Study & Lượt khám (Visit)**:
   - Study chưa có bệnh nhân: khi tạo visit kèm PID, tạo và liên kết cùng một `PatientModel` cho cả study và visit trong 1 transaction nguyên tử.
   - Tạo visit không kèm PID: giữ cả study và visit ở trạng thái patientless.
   - Study đã có bệnh nhân: xác thực HMAC chặt chẽ, từ chối 422 khi mâu thuẫn; tự động kế thừa PID khi không truyền.
7. **Đặt Mặc định `generate_overlay = False` & Pruning**:
   - `InferenceEngine.predict()` và router `/api/predict` mặc định `generate_overlay=False`, trả về `overlay_base64=None`.
   - Client cần overlay phải truyền tường minh `?generate_overlay=true`.
   - Loại bỏ hoàn toàn thuộc tính trạng thái dùng chung `self.default_generate_overlay`, ngăn chặn rò rỉ trạng thái giữa các request đồng thời.

### 2. Kết Quả Kiểm Thử Thực Nghiệm (Task 8 Final Verification)
- **Pytest Suites**: 75/75 tests PASS (100% xanh)
  - `tests/test_facility_isolation_p0.py` (14 passed)
  - `tests/test_tenant_admin_hardening.py` (4 passed)
  - `tests/test_schema_migration_r10.py` (2 passed)
  - `tests/test_case_assignment.py` (5 passed)
  - `tests/test_correction_workflow.py` (4 passed)
  - `tests/test_persistent_notifications.py` (2 passed)
  - `tests/test_visit_patientless_study.py` (3 passed)
  - `tests/test_overlay_default_false.py` (2 passed)
  - `tests/test_patient_id_optional_r2.py` (5 passed)
  - `tests/test_admin_user_onboarding_r3.py` (5 passed)
  - `tests/test_api_contracts_r4.py` (5 passed)
  - `tests/test_visit_constraints_r5.py` (4 passed)
  - `tests/test_async_image_decode_r6.py` (4 passed)
  - `tests/test_cdss_boundary_30mm_r8.py` (5 passed)
  - `tests/test_payload_pruning_r9.py` (7 passed)
  - `tests/test_visits_and_multifacility.py` (4 passed)
- **Node.js Test Suites**: 29/29 tests PASS (100% xanh)
  - `tests/test_api_session.mjs` (6 passed)
  - `tests/test_frontend_intake_patient_id.mjs` (3 passed)
  - `tests/test_viewer_geometry_r7.mjs` (3 passed)
  - `tests/test_research_report_draft.mjs` (7 passed)
  - `tests/test_fe_02_report_preview.mjs` (10 passed)
- **Worktree Integrity**: Hoàn toàn bảo toàn các file dirty sẵn có trên nhánh `temp/ui-e2e-remediation-20261029`, không reset hay thất thoát file.

---

## Báo cáo Nghiệm thu Toàn diện & Khóa 14 Phát hiện Audit (Final Master Verification - 02/11/2026)

### 1. Bảng Ma trận Đóng 14 Phát hiện Audit (F01 – F14)

| Mã | Mức | Hạng mục | Bản sửa kỹ thuật | Test kiểm chứng thực nghiệm | Trạng thái |
|---|---|---|---|---|---|
| **F01** | P0 | Admin đổi mật khẩu chéo cơ sở | Scoped target user theo facility của Admin; chặn đổi chéo cơ sở trả về 403/404 | `tests/test_audit_remediation_regression.py::test_cross_facility_admin_cannot_reset_other_facility_password` | **ĐÃ ĐÓNG** |
| **F02** | P0 | Nang đơn giản 100 mm gán sai O-RADS 2 | Sửa biên 30 < d < 100 mm cho O-RADS 2; d >= 100 mm trả O-RADS 3 | `tests/test_audit_remediation_regression.py::test_cdss_100mm_boundary_and_simple_cyst_orads3` | **ĐÃ ĐÓNG** |
| **F03** | P0 | Caliper inpainter xóa nhầm vách mỏng | Khóa chế độ tự động caliper xóa (fail-closed HTTP 422 / ValueError) đến khi có clinician confirmation | `tests/test_audit_remediation_regression.py::test_caliper_removal_safety_lock` | **ĐÃ ĐÓNG** |
| **F04** | P1 | Toggle raw/enhanced race condition | Sequence guard và quản lý vòng đời đóng ImageBitmap chống ghi đè không đúng thứ tự | `tests/caliper_race_probe.cjs`, `frontend/app/viewer.js` | **ĐÃ ĐÓNG** |
| **F05** | P1 | Pipeline SRAD gọi sai keyword | Chuẩn hóa `n_iter` kèm tương thích ngược `num_iter`; Literal enum chặn typo ở API query | `tests/test_audit_remediation_regression.py::test_speckle_srad_filter_robustness` | **ĐÃ ĐÓNG** |
| **F06** | P1 | Audit trail không bất biến | Thiết lập DB triggers chặn UPDATE và DELETE trên bảng `audit_logs` (append-only) | `tests/test_audit_remediation_regression.py::test_audit_log_immutability_triggers` | **ĐÃ ĐÓNG** |
| **F07** | P1 | Audit split băm path thay vì binary | Chuyển sang `hashlib.file_digest` băm binary content; fail-closed nếu thiếu file ảnh | `tests/test_audit_remediation_regression.py::test_audit_leakage_hashes_file_bytes` | **ĐÃ ĐÓNG** |
| **F08** | P1 | Correction chỉ cho phép đúng 2 ảnh | Mở rộng hỗ trợ từ 1 đến 20 ảnh theo chuẩn schema, tương thích ca một bên và multi-frame | `tests/test_audit_remediation_regression.py::test_correction_supports_single_image_case` | **ĐÃ ĐÓNG** |
| **F09** | P1 | Demo workspace tắt rào chắn synthetic | Ép chặt `APP_SYNTHETIC_DEMO_MODE=1` trong scripts run_demo_workspace.ps1 | `tests/test_audit_remediation_regression.py::test_run_demo_workspace_enforces_synthetic_demo_mode` | **ĐÃ ĐÓNG** |
| **F10** | P1 | Baseline hồi quy đỏ (189 fail, 19 err) | Chuẩn hóa fixture tenant isolation, database hooks và model scoping; đạt 100% test pass | `tests/test_audit_remediation_regression.py::test_admin_cannot_self_deactivate_or_self_demote` | **ĐÃ ĐÓNG** |
| **F11** | P1 | Thống kê dashboard lộ toàn bộ DB | Lọc toàn bộ các count query trong `/api/stats` theo facility của người dùng đang đăng nhập | `tests/test_audit_remediation_regression.py::test_dashboard_stats_scoped_by_facility` | **ĐÃ ĐÓNG** |
| **F12** | P2 | Thiếu index tìm kiếm đa tenant | Thêm composite index `ix_studies_facility_status_created` trên bảng studies | `tests/test_audit_remediation_regression.py::test_facility_status_created_index_exists` | **ĐÃ ĐÓNG** |
| **F13** | P2 | Chưa có tổng hợp rủi ro đa tổn thương | Triển khai `evaluate_multi_lesions` theo nguyên lý worst-case O-RADS và fail-closed | `tests/test_audit_remediation_regression.py::test_cdss_multi_lesion_aggregation_worst_case` | **ĐÃ ĐÓNG** |
| **F14** | P3 | Unused imports & local variables | Rà soát và dọn dẹp các import dư thừa trên các entrypoint và routers | `scripts/deep_audit_inventory_20261101.py` | **ĐÃ ĐÓNG** |

### 2. Tổng hợp Bằng chứng Thực nghiệm Mới nhất

- **Toàn bộ Pytest Suite**: **1.532 / 1.532 tests PASSED (100% xanh)**, 0 failed, 0 errors, 2 warnings (.tmp-verify-20261101/pytest-report-100pct.xml).
- **PostgreSQL & Schema Migration Integration**: **8 / 8 tests PASSED** (`tests/test_sqlite_to_postgres_migration.py`, `tests/test_schema_migration_r10.py`).
- **Caliper Phantom & Preprocessing Enhancement**: **12 / 12 tests PASSED** (`tests/test_caliper_phantom_validation.py`, `tests/test_preprocessing_enhancement.py`).
- **Audit Remediation Regression Suite**: **27 / 27 tests PASSED** (`tests/test_audit_remediation_regression.py`, `tests/test_audit_remediation.py`).
- **Playwright E2E Thực tế (Full Backend Journey)**: **PASS** (13 assertions, upload -> inference -> review revision 1 -> region revision 2 -> reload -> export report, 0 page errors).
- **Workstation UI Responsive E2E**: **PASS** (4 viewports: 1440, 1024, 768, 390; 27 mocked writes, 0 blocked writes, 0 page errors).
- **JavaScript Syntax Check**: **55 / 55 modules PASS** (0 syntax errors).
- **Tiến trình Huấn luyện Mô hình Nền tảng (nnU-Net Fold 0)**: Đang chạy ổn định tại Epoch 11, pseudo-Dice đạt 0.7884.
- **Kỷ luật Git Worktree**: Giữ nguyên vẹn 100% dirty diff trên nhánh `temp/ui-e2e-remediation-20261029`, không reset repo, không tạo synthetic Patient ID.
