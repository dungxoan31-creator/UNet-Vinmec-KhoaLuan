# Kế hoạch Khắc phục Triệt để Các Lỗi Còn Mở (Comprehensive Remediation Closure Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục triệt để các tồn dư về kiểm soát truy cập cơ sở (tenant isolation), phân trang admin, phân công ca khám, luồng yêu cầu chỉnh sửa (corrections), lưu trữ thông báo bền vững (persistent notifications), liên kết bệnh nhân giữa study/visit, và tối ưu hóa payload tắt overlay theo mặc định.

**Architecture:** Mở rộng hệ thống RBAC fail-closed đa cơ sở đã định hình ở R1; bổ sung cột `assignee_id` vào `StudyModel` và bảng `notifications` cùng `correction_requests` trong SQLite/PostgreSQL thông qua migration lặp lại an toàn. Ràng buộc các thao tác phân công và yêu cầu sửa trong cùng transaction nguyên tử với thông báo; bảo toàn triệt để nguyên tắc không tạo patient ID giả và quy tắc nghiên cứu RUO.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, Pytest, Node.js Test Runner, SQLite / PostgreSQL.

**Spec:** Yêu cầu người dùng (Kế hoạch khắc phục triệt để các lỗi còn mở - 01/11/2026) và `AGENTS.md`.

## Global Constraints
- Bảo toàn phạm vi cốt lõi (Core Scope): Image-level split, khử trùng lặp SHA-256, Letterbox 512×512 Resize, Combo Loss ($L_{\text{Dice}} + L_{\text{BCE}}$).
- Không tạo Patient ID giả (`ANON-UPLOAD-*`, `BN-*`).
- Không thực hiện `git reset --hard` hay ghi đè các file bẩn đang có trên worktree.
- Giữ vững trạng thái RUO (Research Use Only); mọi kết quả test kỹ thuật không được diễn giải thành chứng chỉ lưu hành lâm sàng.
- Mọi thao tác nghiệp vụ đi kèm thông báo (Assignment, Correction) phải nằm trong cùng database transaction; nếu thông báo thất bại, rollback toàn bộ.

## Review Focus
1. **Rò rỉ cơ sở ở UI Event Batch & HITL Detail:** Batch chứa bất kỳ ca nào ngoài cơ sở của người dùng phải bị từ chối toàn bộ 403 (không ghi một phần).
2. **Phân trang Admin Cases:** Phải xử lý `limit` và `offset` nhất quán; khi bỏ qua cả hai, tiếp tục dùng `page` và `page_size`.
3. **Tranh chấp Phân công & Tự nhận ca:** Bác sĩ chỉ được tự nhận ca chưa có người phụ trách (`assignee_id is None`); đổi phân công khi ca đang có lease hợp lệ phải trả về 409 Conflict mà không thu hồi lease.
4. **Quyền hạn Kỹ thuật viên (TK) trong Luồng Sửa:** Kỹ thuật viên chỉ được lưu bản sửa dự thảo (`PUT /corrections`); tuyệt đối không được ký, hoàn tất review hoặc thực thi hành động lâm sàng khác.
5. **Đồng bộ Bệnh nhân giữa Study & Visit:** Tạo visit cho study chưa có patient khi request có PID phải tạo và gắn cùng một `PatientModel` cho cả hai; nếu request không có PID, giữ cả hai patientless.

---

### Task 1: Tenant Isolation & Admin Hardening (HITL, UI Events, Audit Logs, Pagination)

**Files:**
- Modify: `backend/app/routers/hitl.py`
- Modify: `backend/app/routers/admin.py`
- Test: `tests/test_tenant_admin_hardening.py`

- [x] **Step 1: Viết test kiểm tra fail-closed cho HITL session, UI-events batch, Audit logs và Admin cases pagination**
  - Tạo file `tests/test_tenant_admin_hardening.py` chứa:
    - `test_hitl_session_detail_tenant_forbidden`: Bác sĩ/Admin cơ sở B gọi `GET /api/hitl/sessions/{session_id}` của ca thuộc cơ sở A nhận 403.
    - `test_ui_events_batch_cross_facility_rejected_entirely`: Gửi batch gồm 2 sự kiện (1 thuộc ca cơ sở A, 1 thuộc ca cơ sở B), bác sĩ cơ sở A gửi request -> toàn bộ batch bị từ chối 403, không có bản ghi nào được ghi vào `ui_events`.
    - `test_admin_audit_logs_facility_filtering`: Facility admin cơ sở A chỉ thấy các log truy ngược được về study/image/review/visit của cơ sở A; log của cơ sở B hoặc log hệ thống không xác định được cơ sở không xuất hiện. Global admin thấy toàn bộ.
    - `test_admin_cases_offset_limit_consistency`: Kiểm tra gọi `/api/admin/cases?offset=5&limit=10` trả về đúng 10 bản ghi từ vị trí thứ 5; gọi không có limit/offset dùng `page/page_size`.

- [x] **Step 2: Chạy test để xác nhận test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_tenant_admin_hardening.py`
  - Ghi nhận lỗi fail do logic kiểm tra cơ sở và phân trang chưa cập nhật.

- [x] **Step 3: Cập nhật `backend/app/routers/hitl.py` và `backend/app/routers/admin.py`**
  - Trong `backend/app/routers/hitl.py`:
    - `get_hitl_session`: Thêm `study = sess.study` và gọi `check_facility_access(current_user, study.facility_id)`.
    - `ingest_ui_events`: Truy vấn tất cả `StudyModel` theo `case_ids`; nếu bất kỳ `study` nào không vượt qua `check_facility_access(current_user, study.facility_id)` -> raise `HTTPException(403)`.
  - Trong `backend/app/routers/admin.py`:
    - `get_admin_cases`: Cập nhật signature `offset: int | None = Query(None, ge=0)`. Nếu `limit is not None` hoặc `offset is not None`:
      `effective_limit = limit if limit is not None else page_size`
      `effective_offset = offset if offset is not None else 0`
      Ngược lại dùng `(page - 1) * page_size` và `page_size`.
    - `get_audit_logs`: Khi `current_user.facility_id` tồn tại (facility admin): Lọc audit logs có `entity_id` liên kết với study, image, review, hoặc visit thuộc `current_user.facility_id`. Log không xác định được cơ sở chỉ hiển thị cho global admin.

- [x] **Step 4: Chạy lại test để kiểm tra pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_tenant_admin_hardening.py`
  - Đảm bảo tất cả test cases đều PASS.

---

### Task 2: Schema & Migration cho Assignee, Correction Request & Notification

**Files:**
- Modify: `backend/db/database.py`
- Modify: `backend/schemas/schemas.py`
- Test: `tests/test_schema_migration_r10.py`

- [x] **Step 1: Viết test kiểm tra migration lặp lại an toàn và schemas mới**
  - Tạo `tests/test_schema_migration_r10.py` kiểm tra:
    - Bảng `studies` có cột `assignee_id` nullable (mặc định NULL cho bản ghi cũ).
    - Bảng `correction_requests` có đầy đủ các trường: `id`, `study_id`, `version`, `reason`, `doctor_id`, `technician_id`, `status`, `created_at`, `updated_at`.
    - Bảng `notifications` có các trường: `id`, `recipient_id`, `facility_id`, `study_id`, `event_type`, `title`, `message`, `is_read`, `read_at`, `created_at`, `dedup_key`.
    - DTO Pydantic xác thực đúng định dạng payload của assignment, correction và notification.

- [x] **Step 2: Chạy test để xác nhận test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_schema_migration_r10.py`

- [x] **Step 3: Cài đặt Database Models và Migration trong `backend/db/database.py` và `backend/schemas/schemas.py`**
  - Cập nhật `StudyModel` thêm:
    `assignee_id = Column(String(36), ForeignKey("users.id"), nullable=True)`
    `assignee = relationship("UserModel", foreign_keys=[assignee_id])`
  - Định nghĩa `CorrectionRequestModel`:
    `id = Column(String(36), primary_key=True)`
    `study_id = Column(String(36), ForeignKey("studies.id"), nullable=False)`
    `review_revision = Column(Integer, nullable=False)`
    `reason = Column(Text, nullable=False)`
    `doctor_id = Column(String(36), ForeignKey("users.id"), nullable=False)`
    `technician_id = Column(String(36), ForeignKey("users.id"), nullable=False)`
    `status = Column(String(32), default="PENDING", nullable=False)`
    `draft_payload = Column(JSON, nullable=True)`
    `created_at = Column(DateTime, default=lambda: datetime.now(UTC))`
    `updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))`
  - Định nghĩa `NotificationModel`:
    `id = Column(String(36), primary_key=True)`
    `recipient_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)`
    `facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)`
    `study_id = Column(String(36), ForeignKey("studies.id"), nullable=True)`
    `event_type = Column(String(50), nullable=False)` (CheckConstraint: `CASE_ASSIGNED`, `CORRECTION_REQUESTED`)
    `title = Column(String(255), nullable=False)`
    `message = Column(Text, nullable=False)`
    `is_read = Column(Boolean, default=False, nullable=False)`
    `read_at = Column(DateTime, nullable=True)`
    `created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)`
    `dedup_key = Column(String(128), unique=True, nullable=True, index=True)`
  - Bổ sung hàm migration trong `_migrate_sqlite_schema` để thêm cột/tạo bảng an toàn lặp lại (idempotent).
  - Khai báo DTOs trong `backend/schemas/schemas.py`:
    `CaseAssignRequest`, `CaseClaimResponse`, `CorrectionCreateRequest`, `CorrectionSaveRequest`, `NotificationResponseItem`, `NotificationListResponse`.

- [x] **Step 4: Chạy lại test để kiểm tra pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_schema_migration_r10.py`

---

### Task 3: Phân công Ca khám (Assignment) & Tự nhận Ca (Self-Claim)

**Files:**
- Modify: `backend/app/routers/cases.py`
- Test: `tests/test_case_assignment.py`

- [x] **Step 1: Viết test cho phân công và tự nhận ca**
  - Tạo `tests/test_case_assignment.py` kiểm tra:
    - Admin cơ sở giao/đổi bác sĩ trong cùng cơ sở -> 200 OK, `study.assignee_id` được cập nhật, có notification `CASE_ASSIGNED` gửi tới bác sĩ được giao.
    - Admin cơ sở giao bác sĩ ngoài cơ sở -> 403 Forbidden.
    - Global admin giao bác sĩ thuộc cơ sở của study -> 200 OK.
    - Admin đổi assignee khi ca đang có active lease -> 409 Conflict (lease không bị thu hồi).
    - Bác sĩ tự nhận ca chưa có assignee (`POST /api/cases/{study_id}/claim`) -> 200 OK, `study.assignee_id = doctor.id`, KHÔNG gửi notification cho chính mình.
    - Hai bác sĩ đồng thời nhận ca chưa có assignee -> 1 thành công (200), 1 bị từ chối 409.
    - Bác sĩ claim ca đã có assignee -> 409 Conflict.

- [x] **Step 2: Chạy test để xác nhận test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_case_assignment.py`

- [x] **Step 3: Triển khai router phân công và claim trong `backend/app/routers/cases.py`**
  - `POST /api/cases/{study_id}/assign` và `POST /api/workspace/cases/{study_id}/assign`:
    - Kiểm tra role admin (global admin hoặc facility admin).
    - Kiểm tra lease đang hoạt động (`has_active_lease`): nếu có, raise 409 mà không xóa lease.
    - Xác thực bác sĩ đích: phải có role `DOCTOR` và thuộc cơ sở của ca khám.
    - Cập nhật `study.assignee_id = target_user.id`.
    - Tạo `NotificationModel(recipient_id=target_user.id, facility_id=study.facility_id, study_id=study.id, event_type="CASE_ASSIGNED", ...)` trong cùng transaction.
  - `POST /api/cases/{study_id}/claim` và `POST /api/workspace/cases/{study_id}/claim`:
    - Yêu cầu `require_clinical` và `check_facility_access(current_user, study.facility_id)`.
    - Thực hiện update nguyên tử:
      `rows = db.query(StudyModel).filter(StudyModel.id == study_id, StudyModel.assignee_id.is_(None)).update({StudyModel.assignee_id: current_user.id})`.
    - Nếu `rows == 0`: nếu `study.assignee_id == current_user.id` trả 200, ngược lại raise 409 ("Ca khám đã có người phụ trách.").
    - Không tạo notification khi tự nhận.

- [x] **Step 4: Chạy test để xác nhận pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_case_assignment.py`

---

### Task 4: Luồng Yêu cầu Sửa (Correction Workflow) cho Kỹ thuật viên (TK)

**Files:**
- Create: `backend/app/routers/corrections.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_correction_workflow.py`

- [x] **Step 1: Viết test cho luồng yêu cầu chỉnh sửa**
  - Tạo `tests/test_correction_workflow.py` kiểm tra:
    - Bác sĩ phụ trách gọi `POST /api/workspace/cases/{study_id}/corrections` chọn TK cùng cơ sở -> 200 OK, tạo record correction và notification `CORRECTION_REQUESTED` cho TK.
    - Bác sĩ chọn TK khác cơ sở hoặc user không phải TK -> 403 / 422.
    - TK được chỉ định gọi `PUT /api/workspace/cases/{study_id}/corrections` lưu bản sửa -> 200 OK, lưu draft masks và ghi chú.
    - Người không phải TK được giao gọi PUT corrections -> 403 Forbidden.
    - TK cố tình gọi sign, approve hoặc export report -> 403 Forbidden.
    - Bác sĩ mở ca, rà soát lại và hoàn tất review ca sau khi TK sửa -> 200 OK.
    - Nếu tạo notification lỗi -> toàn bộ transaction tạo correction rollback.

- [x] **Step 2: Chạy test để xác nhận test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_correction_workflow.py`

- [x] **Step 3: Cài đặt router `corrections.py` và mount vào `main.py`**
  - Xây dựng `POST /api/workspace/cases/{study_id}/corrections` (và alias `/api/cases/{study_id}/corrections`):
    - Kiểm tra quyền bác sĩ và cơ sở.
    - Kiểm tra `technician_id`: phải thuộc cùng `facility_id` và có role `TECHNICIAN` (hoặc `TK`).
    - Tạo `CorrectionRequestModel` và `NotificationModel(event_type="CORRECTION_REQUESTED")` trong cùng transaction.
  - Xây dựng `PUT /api/workspace/cases/{study_id}/corrections` (và alias `/api/cases/{study_id}/corrections`):
    - Kiểm tra `current_user.id == correction.technician_id`.
    - Lưu `draft_payload` (danh sách mask RLE, morphology, notes của từng ảnh).
    - Cập nhật trạng thái `CorrectionRequestModel` thành `SUBMITTED`.
    - Tăng `study.review_revision` an toàn.
  - Chặn triệt để TK không được gọi các route hoàn tất lâm sàng (`require_clinical` phân định bác sĩ rà soát chính thức).

- [x] **Step 4: Chạy test xác nhận pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_correction_workflow.py`

---

### Task 5: Hệ thống Thông báo Lưu Bền vững (Persistent Notifications)

**Files:**
- Modify: `backend/app/main.py`
- Test: `tests/test_persistent_notifications.py`

- [x] **Step 1: Viết test cho endpoint thông báo lưu bền vững**
  - Tạo `tests/test_persistent_notifications.py` kiểm tra:
    - User A chỉ nhận được thông báo gửi cho User A (`GET /api/notifications`).
    - Danh sách trả về tối đa 100 mục mới nhất, định dạng khớp hợp đồng frontend (`id`, `title`, `message`, `caseId`, `is_read`, `created_at`).
    - User A đánh dấu đã đọc (`POST /api/notifications/read` với `ids`) -> chỉ cập nhật các thông báo của User A và trả về số lượng thực tế đã cập nhật.
    - User B gửi request đánh dấu đã đọc chứa ID thông báo của User A -> không cập nhật thông báo của User A (`updated: 0`).
    - Trùng `dedup_key` khi retry gửi thông báo không sinh bản ghi trùng lặp.

- [x] **Step 2: Chạy test để xác minh test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_persistent_notifications.py`

- [x] **Step 3: Cập nhật endpoints thông báo trong `backend/app/main.py`**
  - `GET /api/notifications`:
    - Query `NotificationModel` lọc theo `recipient_id == current_user.id`.
    - Sắp xếp `desc(NotificationModel.created_at)`, `limit(100)`.
    - Trả về danh sách JSON chuẩn hóa cho frontend.
  - `POST /api/notifications/read`:
    - Nhận `payload: NotificationReadRequest`.
    - Update nguyên tử:
      `rows_updated = db.query(NotificationModel).filter(NotificationModel.id.in_(payload.ids), NotificationModel.recipient_id == current_user.id, NotificationModel.is_read.is_(False)).update({NotificationModel.is_read: True, NotificationModel.read_at: datetime.now(UTC)}, synchronize_session=False)`.
    - Commit và trả về `{"status": "SUCCESS", "updated": rows_updated}`.

- [x] **Step 4: Chạy test xác nhận pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_persistent_notifications.py`

---

### Task 6: Đồng bộ Patientless Study và Tạo Lượt khám (Visit)

**Files:**
- Modify: `backend/app/routers/visits.py`
- Test: `tests/test_visit_patientless_study.py`

- [x] **Step 1: Viết test cho kịch bản ca khám patientless liên kết visit**
  - Tạo `tests/test_visit_patientless_study.py` kiểm tra:
    - Ca khám chưa có bệnh nhân (`study.patient_id is None`) khi tạo visit kèm PID: dùng `get_or_create_patient`, liên kết cùng `PatientModel` cho cả study và visit trong 1 transaction -> cả hai đều có patient ID hợp lệ.
    - Ca khám chưa có bệnh nhân khi tạo visit không kèm PID: giữ cả study và visit ở trạng thái patientless (`patient_id = None`).
    - Ca khám đã có bệnh nhân: truyền PID đúng HMAC -> 201 OK; truyền PID mâu thuẫn -> 422 Unprocessable Entity; không truyền PID -> tự động kế thừa PID của study.
    - Kiểm tra rollback nếu có lỗi xảy ra giữa chừng: không để lại visit mồ côi hay study bị thay đổi một phần.

- [x] **Step 2: Chạy test để xác minh test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_visit_patientless_study.py`

- [x] **Step 3: Cập nhật hàm `create_visit` trong `backend/app/routers/visits.py`**
  - Xử lý nhánh liên kết study:
    - Nếu `study.patient_id is None`:
      - Nếu `req.patient_id`:
        - Gọi `patient = get_or_create_patient(db, req.patient_id)`.
        - Gán `study.patient_id = patient.id` và `study.patient = patient`.
        - Gán `visit.patient_id = patient.id` và `visit.patient = patient`.
      - Nếu không có `req.patient_id`:
        - `visit.patient_id = None`.
    - Nếu `study.patient_id is not None`:
      - Giữ nguyên logic HMAC validation chặt chẽ: từ chối 422 nếu mâu thuẫn.
      - Kế thừa patient của study nếu `req.patient_id` là None.

- [x] **Step 4: Chạy test xác nhận pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_visit_patientless_study.py`

---

### Task 7: Đặt Mặc Định `generate_overlay = False` & Payload Pruning

**Files:**
- Modify: `backend/services/inference_engine.py`
- Modify: `backend/app/routers/inference.py`
- Modify: `tests/test_payload_pruning_r9.py`
- Modify: `tests/test_vinmec_api_smoke.py`
- Test: `tests/test_overlay_default_false.py`

- [x] **Step 1: Viết test kiểm tra mặc định không sinh overlay**
  - Tạo `tests/test_overlay_default_false.py` kiểm tra:
    - Gọi `InferenceEngine.predict(..., generate_overlay=False)` -> `overlay_base64 is None`.
    - Gọi `InferenceEngine.predict` mặc định (không truyền flag) -> `overlay_base64 is None`.
    - Gọi `POST /api/predict/{image_id}` không truyền param -> `overlay_base64 is None`.
    - Gọi `POST /api/predict/{image_id}?generate_overlay=true` -> `overlay_base64` trả về chuỗi Data URL Base64 hợp lệ.
    - Không tồn tại trạng thái dùng chung `self.default_generate_overlay` gây rò rỉ giữa các request đồng thời.

- [x] **Step 2: Chạy test để xác minh test thất bại**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_overlay_default_false.py`

- [x] **Step 3: Cập nhật code trong `inference_engine.py`, `inference.py` và các test liên quan**
  - Trong `backend/services/inference_engine.py`:
    - Đổi tham số `generate_overlay: bool = False` trong hàm `predict()`.
    - Loại bỏ việc đọc/ghi thuộc tính `getattr(self, "default_generate_overlay", True)`.
    - Chỉ sinh overlay khi tham số `generate_overlay` được truyền `True`.
  - Trong `backend/app/routers/inference.py`:
    - Đổi mặc định `generate_overlay: bool = False` ở `run_ai_prediction`.
  - Cập nhật `tests/test_payload_pruning_r9.py`:
    - Sửa test case dòng 245: xác nhận mặc định `overlay_base64 is None`, và khi gọi kèm `?generate_overlay=true` thì `overlay_base64 is not None`.
  - Cập nhật `tests/test_vinmec_api_smoke.py`:
    - Truyền rõ ràng `?generate_overlay=true` ở request cần kiểm tra overlay.

- [x] **Step 4: Chạy test xác nhận pass**
  - Chạy: `.venv\Scripts\python.exe -m pytest tests/test_overlay_default_false.py tests/test_payload_pruning_r9.py tests/test_vinmec_api_smoke.py`

---

### Task 8: Chạy Toàn Bộ Regression Suite & Kiểm Chứng Cuối Cùng

**Files:**
- Toàn bộ test suite liên quan.

- [x] **Step 1: Chạy toàn bộ Pytest test suites**
  - Chạy lệnh:
    ```bash
    .venv\Scripts\python.exe -m pytest tests/test_facility_isolation_p0.py tests/test_tenant_admin_hardening.py tests/test_schema_migration_r10.py tests/test_case_assignment.py tests/test_correction_workflow.py tests/test_persistent_notifications.py tests/test_visit_patientless_study.py tests/test_overlay_default_false.py tests/test_patient_id_optional_r2.py tests/test_admin_user_onboarding_r3.py tests/test_api_contracts_r4.py tests/test_visit_constraints_r5.py tests/test_async_image_decode_r6.py tests/test_cdss_boundary_30mm_r8.py tests/test_payload_pruning_r9.py tests/test_visits_and_multifacility.py -v
    ```
  - Xác nhận 100% tests PASS (75 passed).

- [x] **Step 2: Chạy toàn bộ Node.js / UI test suites**
  - Chạy lệnh:
    ```bash
    node --test tests/test_api_session.mjs tests/test_frontend_intake_patient_id.mjs tests/test_viewer_geometry_r7.mjs tests/test_research_report_draft.mjs tests/test_fe_02_report_preview.mjs
    ```
  - Xác nhận 100% tests PASS (29 passed).

- [x] **Step 3: Rà soát Git Worktree Status**
  - Chạy: `git status --short --branch`
  - Đảm bảo không mất bất kỳ file dirty nào có sẵn trước đợt thực hiện; các file mới tạo hoặc sửa đúng phân quyền sở hữu.
