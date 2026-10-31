# Bảng Kiểm soát Khắc phục Lỗi Lâm sàng (R0 - R9)

> **Mục tiêu**: Giữ nguyên toàn bộ các thay đổi chưa commit trên nhánh `temp/ui-e2e-remediation-20261029`, phân định rõ quyền sở hữu file của từng gói task, và xác minh thực nghiệm trước khi công bố.

| Gói | Lỗi liên quan | File phụ trách | Test tái hiện trước sửa | Thay đổi dự kiến | Test kiểm chứng sau sửa | Trạng thái |
|---|---|---|---|---|---|---|
| R0 | Baseline tracking | `docs/evaluation/baseline_remediation_tracking_20261031.md`, `docs/evaluation/baseline_worktree_status_20261031.txt` | N/A | Khóa baseline và lập bảng theo dõi | N/A | Hoàn thành |
| R1 | E2E-SEC-001, E2E-SEC-002 | `backend/services/facility_service.py`, `backend/app/routers/cases.py`, `backend/app/routers/visits.py`, `backend/services/case_lease_service.py` | `tests/test_facility_isolation_p0.py` | Fail-closed tenant isolation | `tests/test_facility_isolation_p0.py` | Đang triển khai |
| R2 | Violate Core Scope | `backend/db/database.py`, `backend/schemas/schemas.py`, `frontend/app/upload.js`, `frontend/app/intake.js` | `tests/test_patient_id_optional_r2.py` | Make patient_id optional, drop BN-* | `tests/test_patient_id_optional_r2.py` | Chờ thực hiện |
| R3 | E2E-AUTH-001 | `backend/app/routers/admin.py`, `backend/schemas/schemas.py`, `frontend/app/admin-users.js` | `tests/test_admin_user_onboarding_r3.py` | Credential handover dialog, valid reset JSON | `tests/test_admin_user_onboarding_r3.py` | Chờ thực hiện |
| R4 | Contract Gaps | `backend/schemas/schemas.py`, `backend/app/routers/cases.py`, `frontend/app/notifications.js` | `tests/test_api_contracts_r4.py` | CaseItem response model, graceful capabilities | `tests/test_api_contracts_r4.py` | Chờ thực hiện |
| R5 | Orphan Visits, 500 | `backend/app/routers/visits.py`, `backend/app/main.py` | `tests/test_visit_constraints_r5.py` | Study FK check, lock consistency, 500 logging | `tests/test_visit_constraints_r5.py` | Chờ thực hiện |
| R6 | Event loop block, 401 | `backend/app/routers/inference.py`, `frontend/app/api.js` | `tests/test_async_image_decode_r6.py`, `tests/test_api_session.mjs` | run_in_threadpool, dispatch ova:expired on 401 | `tests/test_async_image_decode_r6.py` | Chờ thực hiện |
| R7 | E2E-UI-001, E2E-A11Y-* | `frontend/css/workspace.css`, `frontend/app/navigation.js` | `tests/test_viewer_geometry_r7.cjs` | Flex wrap header, min-height, contrast & aria-label | `tests/test_viewer_geometry_r7.cjs` | Chờ thực hiện |
| R8 | Boundary & Copy | `backend/services/cdss_engine.py`, `backend/services/inference_engine.py` | `tests/test_cdss_boundary_30mm_r8.py` | <= 30mm support, rename mask confidence | `tests/test_cdss_boundary_30mm_r8.py` | Chờ thực hiện |
| R9 | Payload Bloat | `backend/services/inference_engine.py`, `backend/schemas/schemas.py` | `tests/test_payload_pruning_r9.py` | Make overlay_base64 optional/on-demand | `tests/test_payload_pruning_r9.py` | Chờ thực hiện |
