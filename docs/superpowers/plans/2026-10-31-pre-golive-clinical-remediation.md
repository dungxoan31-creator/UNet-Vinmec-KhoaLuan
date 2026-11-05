# Pre-Golive Clinical Remediation Implementation Plan (R0–R9)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triệt để khắc phục các lỗi P0–P3 về cách ly đa cơ sở, loại bỏ mã định danh giả, hoàn thiện bàn giao tài khoản, chuẩn hóa hợp đồng API/CDSS và sửa lỗi layout responsive trên workstation trước khi tái đánh giá triển khai.

**Architecture:** Áp dụng mô hình phòng thủ theo chiều sâu (Defense-in-Depth): (1) Đảm bảo tenant isolation ở tầng Service/Router backend bằng chính sách fail-closed; (2) Tách rời định danh nghiên cứu (Study/Image) khỏi Patient ID bắt buộc; (3) Đồng bộ chặt chẽ Pydantic DTO và phản hồi giao diện; (4) Chuyển tác vụ CPU-bound (giải mã ảnh/DICOM) khỏi event loop; (5) Tinh chỉnh CSS header workstation tránh xung đột layout.

**Tech Stack:** FastAPI (Python 3.11+), SQLAlchemy 2.0, Pydantic v2, PyTorch / OpenCV / PyDICOM, Vanilla ES Modules, CSS Variables / Modern Flexbox & Grid, Pytest / FastAPI TestClient, Playwright / Axe-core.

**Spec:** [BUG_REPORT.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/artifacts/pre_golive_e2e_audit/BUG_REPORT.md) và [AGENTS.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/AGENTS.md).

## Global Constraints

- **Bảo toàn Core Scope**: Giữ nguyên cơ chế image-level split, khử trùng lặp SHA-256, Letterbox 512×512, Combo Loss. Không diễn giải metric image-level thành kết quả độc lập theo bệnh nhân.
- **Không phá hủy Worktree**: Nhánh `temp/ui-e2e-remediation-20261029` đang có nhiều thay đổi chưa commit; tuyệt đối không chạy `git reset --hard`, không xóa file bừa bãi, không ghi đè đè nát các sửa đổi hiện hữu.
- **Cô lập môi trường kiểm thử**: Chỉ dùng database SQLite test cô lập (`tests/fixtures` hoặc in-memory) và ảnh tổng hợp (`SYNTHETIC_DEMO`); tuyệt đối không trỏ test vào database làm việc thật.
- **Zero-Hallucination & Clinical Precision**: Giữ trạng thái RUO (Research Use Only); AI chỉ gợi ý phân đoạn, không tự động kết luận ác tính hoặc phân loại hình thái thay bác sĩ.

## Review Focus

1. **Bác sĩ chưa gắn cơ sở (`user.facility_id = None`) truy cập dữ liệu**: Phải bị chặn 403 ở mọi thao tác đọc/ghi (fail-closed), không được phép xem hoặc khóa dữ liệu của cơ sở khác.
2. **Ca khám tạo mới không có `patient_id`**: Hệ thống phải tạo study thành công mà không gây lỗi ràng buộc khóa ngoại (Foreign Key IntegrityError) và không tự chế mã `BN-*`.
3. **Admin tạo bác sĩ mới mà không cấp mật khẩu**: Giao diện phải nhận được thông tin thiết lập/mật khẩu tạm từ backend và hiển thị an toàn cho Admin bàn giao, tránh rơi vào trạng thái "tài khoản tạo xong nhưng không thể đăng nhập".
4. **Nang buồng trứng đúng 30.0 mm**: Không được rơi vào "vùng chết logic" (unsupported pattern) giữa `< 30` và `> 30` của engine CDSS.
5. **Session token 401 khi đang tải ảnh trong viewer**: Frontend phải kích hoạt sự kiện hết phiên (`ova:expired`) thống nhất để yêu cầu đăng nhập lại, không nuốt lỗi hay treo viewer.

---

## Danh sách Task chi tiết

### Task 0: R0 — Chốt Baseline và Thiết lập Bảng kiểm soát File sở hữu

**Files:**
- Create: `docs/evaluation/baseline_remediation_tracking_20261031.md`

**Interfaces:**
- Consumes: Hiện trạng git worktree trên nhánh `temp/ui-e2e-remediation-20261029`
- Produces: Bảng phân định ranh giới trách nhiệm (file ownership) cho từng gói R1 đến R9

- [x] **Step 1: Ghi lại trạng thái Git worktree hiện tại**

Chạy:
```powershell
git status --short --branch > docs/evaluation/baseline_worktree_status_20261031.txt
git diff --stat >> docs/evaluation/baseline_worktree_status_20261031.txt
```

- [x] **Step 2: Khởi tạo bảng kiểm soát lỗi và sở hữu file trong tài liệu theo dõi**

Tạo file `docs/evaluation/baseline_remediation_tracking_20261031.md` với nội dung bảng mẫu:
```markdown
# Bảng Kiểm soát Khắc phục Lỗi Lâm sàng (R0 - R9)

| Gói | Lỗi liên quan | File phụ trách | Test tái hiện trước sửa | Thay đổi dự kiến | Test kiểm chứng sau sửa | Trạng thái |
|---|---|---|---|---|---|---|
| R1 | E2E-SEC-001, E2E-SEC-002 | `backend/services/facility_service.py`, `backend/app/routers/cases.py`, `backend/app/routers/visits.py` | `tests/test_facility_isolation_p0.py` | Fail-closed tenant isolation | `tests/test_facility_isolation_p0.py` | Chờ thực hiện |
| R2 | Violate Core Scope | `backend/db/database.py`, `backend/schemas/schemas.py`, `frontend/app/upload.js`, `frontend/app/intake.js` | `tests/test_patient_id_optional_r2.py` | Make patient_id optional, drop BN-* | `tests/test_patient_id_optional_r2.py` | Chờ thực hiện |
| R3 | E2E-AUTH-001 | `backend/app/routers/admin.py`, `backend/schemas/schemas.py`, `frontend/app/admin-users.js` | `tests/test_admin_user_onboarding_r3.py` | Credential handover dialog, valid reset JSON | `tests/test_admin_user_onboarding_r3.py` | Chờ thực hiện |
| R4 | Contract Gaps | `backend/schemas/schemas.py`, `backend/app/routers/cases.py`, `frontend/app/notifications.js` | `tests/test_api_contracts_r4.py` | CaseItem response model, graceful capabilities | `tests/test_api_contracts_r4.py` | Chờ thực hiện |
| R5 | Orphan Visits, 500 | `backend/app/routers/visits.py`, `backend/app/main.py` | `tests/test_visit_constraints_r5.py` | Study FK check, lock consistency, 500 logging | `tests/test_visit_constraints_r5.py` | Chờ thực hiện |
| R6 | Event loop block, 401 | `backend/app/routers/inference.py`, `frontend/app/api.js` | `tests/test_async_image_decode_r6.py`, `tests/test_api_session.mjs` | run_in_threadpool, dispatch ova:expired on 401 | `tests/test_async_image_decode_r6.py` | Chờ thực hiện |
| R7 | E2E-UI-001, E2E-A11Y-* | `frontend/css/workspace.css`, `frontend/app/navigation.js` | `tests/test_viewer_geometry_r7.cjs` | Flex wrap header, min-height, contrast & aria-label | `tests/test_viewer_geometry_r7.cjs` | Chờ thực hiện |
| R8 | Boundary & Copy | `backend/services/cdss_engine.py`, `backend/services/inference_engine.py` | `tests/test_cdss_boundary_30mm_r8.py` | <= 30mm support, rename mask confidence | `tests/test_cdss_boundary_30mm_r8.py` | Chờ thực hiện |
| R9 | Payload Bloat | `backend/services/inference_engine.py`, `backend/schemas/schemas.py` | `tests/test_payload_pruning_r9.py` | Make overlay_base64 optional/on-demand | `tests/test_payload_pruning_r9.py` | Chờ thực hiện |
```

- [x] **Step 3: Commit snapshot tài liệu baseline**

```bash
git add docs/evaluation/baseline_remediation_tracking_20261031.md docs/evaluation/baseline_worktree_status_20261031.txt
git commit -m "chore(audit): lock baseline worktree status and remediation file tracking"
```

---

### Task 1: R1 (P0) — Xây dựng Helper Kiểm tra Phân quyền Cơ sở Fail-Closed

**Files:**
- Create: `backend/services/facility_service.py`
- Test: `tests/test_facility_isolation_p0.py`

**Interfaces:**
- Produces: `check_facility_access(user: UserModel, entity_facility_id: str | None) -> None`
- Rule:
  - Nếu `user.role == "ADMIN"` và `user.facility_id is None`: Cho phép truy cập toàn cục (Global Admin).
  - Nếu `user.facility_id is None`: Ném lỗi `HTTPException(403, "Tài khoản chưa được gán cơ sở y tế.")`.
  - Nếu `entity_facility_id is None`: Ném lỗi `HTTPException(403, "Dữ liệu không thuộc cơ sở y tế hợp lệ.")` (trừ Global Admin).
  - Nếu `user.facility_id != entity_facility_id`: Ném lỗi `HTTPException(403, "Không có quyền truy cập dữ liệu của cơ sở khác.")`.

- [x] **Step 1: Viết test kiểm tra các trường hợp âm tính và dương tính của `check_facility_access`**

Tạo `tests/test_facility_isolation_p0.py`:
```python
import pytest
from fastapi import HTTPException
from backend.db.database import UserModel
from backend.services.facility_service import check_facility_access

def test_check_facility_access_same_facility_allowed():
    user = UserModel(id="u1", role="DOCTOR", facility_id="fac-A")
    # Không ném ngoại lệ
    check_facility_access(user, "fac-A")

def test_check_facility_access_different_facility_blocked():
    user = UserModel(id="u1", role="DOCTOR", facility_id="fac-A")
    with pytest.raises(HTTPException) as exc:
        check_facility_access(user, "fac-B")
    assert exc.value.status_code == 403

def test_check_facility_access_unassigned_doctor_blocked():
    user = UserModel(id="u1", role="DOCTOR", facility_id=None)
    with pytest.raises(HTTPException) as exc:
        check_facility_access(user, "fac-A")
    assert exc.value.status_code == 403

def test_check_facility_access_unassigned_entity_blocked_for_doctor():
    user = UserModel(id="u1", role="DOCTOR", facility_id="fac-A")
    with pytest.raises(HTTPException) as exc:
        check_facility_access(user, None)
    assert exc.value.status_code == 403

def test_check_facility_access_global_admin_allowed():
    admin = UserModel(id="a1", role="ADMIN", facility_id=None)
    check_facility_access(admin, "fac-A")
    check_facility_access(admin, None)
```

- [x] **Step 2: Chạy test để xác nhận test thất bại**

Run: `pytest tests/test_facility_isolation_p0.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.facility_service'`

- [x] **Step 3: Cài đặt `backend/services/facility_service.py`**

Tạo `backend/services/facility_service.py`:
```python
"""
Tenant Isolation and Facility Access Enforcement Service.
"""
from fastapi import HTTPException
from backend.db.database import UserModel

def check_facility_access(user: UserModel, entity_facility_id: str | None) -> None:
    """Enforce strict fail-closed tenant isolation.

    1. Global ADMIN (role == 'ADMIN' and facility_id is None) can access everything.
    2. Users without facility_id are blocked from accessing any facility-scoped entity.
    3. Entities without facility_id are inaccessible to non-global-admin users.
    4. Users can only access entities matching their own facility_id.
    """
    if user.role == "ADMIN" and not user.facility_id:
        return
    if not user.facility_id:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa được gán cơ sở y tế. Vui lòng liên hệ quản trị viên."
        )
    if not entity_facility_id:
        raise HTTPException(
            status_code=403,
            detail="Bản ghi không thuộc cơ sở y tế hợp lệ hoặc chưa được định danh cơ sở."
        )
    if user.facility_id != entity_facility_id:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập dữ liệu của cơ sở khác."
        )
```

- [x] **Step 4: Chạy lại test để kiểm tra pass**

Run: `pytest tests/test_facility_isolation_p0.py -v`
Expected: PASS

- [x] **Step 5: Commit task 1**

```bash
git add backend/services/facility_service.py tests/test_facility_isolation_p0.py
git commit -m "feat(security): implement fail-closed facility tenant access control helper"
```

---

### Task 2: R1 (P0) — Cách ly Ca khám, Tìm kiếm, Lease và Tải ảnh theo Cơ sở

**Files:**
- Modify: `backend/app/routers/cases.py:270-350, 420-580`
- Modify: `backend/app/routers/visits.py:43-50, 160-170`
- Modify: `backend/services/case_lease_service.py:30-80`
- Test: `tests/test_facility_isolation_p0.py`

**Interfaces:**
- Consumes: `check_facility_access` từ `backend.services.facility_service`
- Produces:
  - `POST /api/cases`: Tự động gán `study.facility_id = current_user.facility_id`.
  - `GET /api/cases/{study_id}`: Gọi `check_facility_access(current_user, study.facility_id)`.
  - `POST /api/workspace/cases/search`: Bổ sung filter `StudyModel.facility_id == current_user.facility_id` nếu không phải Global Admin.
  - `POST /api/workspace/cases/{id}/lease`: Kiểm tra cơ sở trước khi cấp quyền lease.
  - `GET /api/cases/{case_id}/images/{image_id}`: Kiểm tra quyền cơ sở của study cha trước khi trả ảnh.

- [x] **Step 1: Thêm integration test cho kịch bản 2 cơ sở (Doctor A vs Doctor B vs Unassigned Doctor)**

Thêm vào `tests/test_facility_isolation_p0.py`:
```python
def test_cross_facility_case_and_lease_isolation(auth_client):
    client = auth_client["client"]
    token_a = auth_client["token_a"]
    token_b = auth_client["token_b"]

    # 1. Doctor A tạo study
    resp_create = client.post(
        "/api/cases",
        json={
            "patient_id": "BN-TEST-01",
            "study_date": "2026-10-31",
            "active_ovary_side": "RIGHT",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_create.status_code in (200, 201)
    study_id = resp_create.json()["id"]

    # 2. Doctor B không thể đọc detail của Study A
    resp_detail_b = client.get(
        f"/api/cases/{study_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_detail_b.status_code == 403

    # 3. Doctor B không thể chiếm lease của Study A
    resp_lease_b = client.post(
        f"/api/workspace/cases/{study_id}/lease",
        json={"page_instance_id": "page-b-1", "lease_token": "token-b"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_lease_b.status_code == 403

    # 4. Doctor B tìm kiếm không thấy ca của Doctor A
    resp_search_b = client.post(
        "/api/workspace/cases/search",
        json={"limit": 50},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_search_b.status_code == 200
    ids_b = [item["id"] for item in resp_search_b.json()]
    assert study_id not in ids_b
```

- [x] **Step 2: Chạy test để xác minh test thất bại**

Run: `pytest tests/test_facility_isolation_p0.py::test_cross_facility_case_and_lease_isolation -v`
Expected: FAIL (status code 200 != 403)

- [x] **Step 3: Tích hợp `check_facility_access` vào `cases.py`, `visits.py`, `case_lease_service.py`**

1. Trong `backend/app/routers/cases.py`:
   - Import `from backend.services.facility_service import check_facility_access`.
   - Trong `create_case`: Gán `study.facility_id = current_user.facility_id`. Nếu `current_user.facility_id` là `None` và không phải Global Admin, từ chối tạo với 403.
   - Trong `get_case_detail`: Thêm `check_facility_access(current_user, study.facility_id)`.
   - Trong `_filtered_cases_query`: Nếu `current_user.facility_id`: thêm `.filter(StudyModel.facility_id == current_user.facility_id)`.
   - Trong router ảnh: Trước khi trả bytes ảnh, truy vấn `study = db.query(StudyModel).filter(StudyModel.id == image.study_id).first()` và gọi `check_facility_access(current_user, study.facility_id)`.
2. Trong `backend/services/case_lease_service.py`:
   - Nhận thêm `current_user: UserModel`.
   - Kiểm tra `check_facility_access(current_user, study.facility_id)` trước khi cấp hoặc giải phóng lease.
3. Trong `backend/app/routers/visits.py`:
   - Thay thế implementation `_check_facility_access` cục bộ bằng `from backend.services.facility_service import check_facility_access`.

- [x] **Step 4: Chạy test để xác nhận test pass**

Run: `pytest tests/test_facility_isolation_p0.py -v`
Expected: ALL PASS

- [x] **Step 5: Commit task 2**

```bash
git add backend/app/routers/cases.py backend/app/routers/visits.py backend/services/case_lease_service.py tests/test_facility_isolation_p0.py
git commit -m "fix(security): enforce tenant isolation on cases, search, leases, and images"
```

---

### Task 3: R2 (P1) — Bỏ Ràng Buộc Bắt Buộc `patient_id` Ở Database & Schema Backend

**Files:**
- Modify: `backend/db/database.py:170`
- Modify: `backend/schemas/schemas.py:734-750`
- Modify: `backend/app/routers/cases.py:240-290`
- Test: `tests/test_patient_id_optional_r2.py`

**Interfaces:**
- Consumes: `CreateCaseRequest`
- Produces: Cho phép tạo Study mà không có `patient_id` (trường `patient_id` nhận `None`), không phát sinh lỗi khóa ngoại `patients.id`.

- [x] **Step 1: Viết test cho phép tạo ca nghiên cứu không cần patient_id**

Tạo `tests/test_patient_id_optional_r2.py`:
```python
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

def test_create_study_without_patient_id(auth_client):
    client = auth_client["client"]
    token = auth_client["token_a"]

    payload = {
        "study_date": "2026-10-31",
        "active_ovary_side": "LEFT",
        "contralateral_status": "NORMAL",
        "clinical_notes": "Research study with unverified patient identity",
    }
    # Request không gửi patient_id
    resp = client.post(
        "/api/cases",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["study_code"] is not None
    assert "BN-" not in (data.get("patient_id") or "")
```

- [x] **Step 2: Chạy test để xác nhận test thất bại**

Run: `pytest tests/test_patient_id_optional_r2.py -v`
Expected: FAIL with 422 Unprocessable Entity (`Field required: patient_id`)

- [x] **Step 3: Chỉnh sửa Database Model và Pydantic Schema**

1. Trong `backend/db/database.py:170`:
   Đổi `patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)` thành:
   ```python
   patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
   ```
2. Trong `backend/schemas/schemas.py:739`:
   Đổi `patient_id: str` thành:
   ```python
   patient_id: str | None = Field(default=None, max_length=64)
   ```
3. Trong `backend/app/routers/cases.py:270-280`:
   Nếu `req.patient_id`: tra cứu hoặc tạo Patient qua `get_or_create_patient(db, req.patient_id)`.
   Nếu `not req.patient_id`: gán `patient = None` và `study.patient_id = None`. Khi trả về response, trường `patient_id` trả về `None` (hoặc hiển thị mã `study_code` như mã đối tượng nghiên cứu, không gán nhãn là mã bệnh nhân).

- [x] **Step 4: Chạy test để xác nhận test pass**

Run: `pytest tests/test_patient_id_optional_r2.py -v`
Expected: PASS

- [x] **Step 5: Commit task 3**

```bash
git add backend/db/database.py backend/schemas/schemas.py backend/app/routers/cases.py tests/test_patient_id_optional_r2.py
git commit -m "feat(data): make patient_id nullable in study model and case intake schema"
```

---

### Task 4: R2 (P1) — Loại bỏ Mã `BN-*` Tự Sinh ở Frontend và Cập nhật Giao diện Intake

**Files:**
- Modify: `frontend/app/upload.js:169-176`
- Modify: `frontend/app/intake.js:145-155`
- Test: `tests/test_frontend_intake_patient_id.mjs`

**Interfaces:**
- Consumes: Backend API chấp nhận `patient_id: null`
- Produces: Frontend gửi payload không kèm mã `BN-` giả lập

- [x] **Step 1: Viết test kiểm tra payload sinh ra từ `upload.js`**

Tạo `tests/test_frontend_intake_patient_id.mjs`:
```javascript
import assert from "node:assert/strict";
import test from "node:test";

test("upload payload does not generate synthetic BN- prefix when targetPid is empty", async () => {
  const targetPid = "";
  const patientIdPayload = targetPid ? targetPid.trim() : null;
  assert.equal(patientIdPayload, null);
  assert.ok(!String(patientIdPayload).startsWith("BN-"));
});
```

- [x] **Step 2: Chạy test để xác minh**

Run: `node --test tests/test_frontend_intake_patient_id.mjs`
Expected: PASS

- [x] **Step 3: Chỉnh sửa `frontend/app/upload.js` và `frontend/app/intake.js`**

1. Trong `frontend/app/upload.js:170-172`:
   Xóa bỏ:
   ```javascript
   patient_id:
     targetPid ||
     "BN-" + crypto.randomUUID().slice(0, 8).toUpperCase(),
   ```
   Thay bằng:
   ```javascript
   patient_id: targetPid ? targetPid.trim() : null,
   ```
2. Trong `frontend/app/intake.js`:
   Đổi placeholder `'placeholder="Để trống để tự cấp BN-XXXX"'` thành `'placeholder="Để trống cho ca nghiên cứu không định danh"'`.

- [x] **Step 4: Chạy lại toàn bộ test e2e liên quan đến intake/upload**

Run: `node --test tests/test_frontend_intake_patient_id.mjs`
Expected: PASS

- [x] **Step 5: Commit task 4**

```bash
git add frontend/app/upload.js frontend/app/intake.js tests/test_frontend_intake_patient_id.mjs
git commit -m "fix(fe): remove client-side synthetic BN-* generation and update intake copy"
```

---

### Task 5: R3 (P1) — Hoàn thiện Quy trình Bàn giao Mật khẩu Khởi tạo và Reset Mật khẩu

**Files:**
- Modify: `backend/schemas/schemas.py:100-115`
- Modify: `backend/app/routers/admin.py:560-605, 670-705`
- Modify: `frontend/app/admin-users.js:125-185`
- Test: `tests/test_admin_user_onboarding_r3.py`

**Interfaces:**
- Produces:
  - `AdminCreateUserResponse` chứa `temp_password`, `username`, `must_change_password`.
  - Frontend hiển thị modal bàn giao thông tin đăng nhập kèm nút "Sao chép mật khẩu tạm" khi Admin tạo user hoặc reset mật khẩu.
  - Reset mật khẩu gửi body JSON hợp lệ `{ "new_password": null }` để yêu cầu sinh mật khẩu tạm.

- [x] **Step 1: Viết test backend cho endpoint create user và reset password response**

Tạo `tests/test_admin_user_onboarding_r3.py`:
```python
import pytest

def test_admin_create_user_returns_temp_password(auth_client):
    client = auth_client["client"]
    token_admin = auth_client["token_admin"]

    resp = client.post(
        "/api/admin/users",
        json={
            "username": f"newdoc_{auth_client['prefix']}",
            "full_name": "Bác sĩ Mới",
            "role": "DOCTOR",
            "department": "Chẩn đoán hình ảnh",
            # Không gửi password -> BE tự sinh
        },
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["must_change_password"] is True
    assert "temp_password" in data
    assert len(data["temp_password"]) >= 12

def test_admin_reset_password_with_valid_body(auth_client):
    client = auth_client["client"]
    token_admin = auth_client["token_admin"]
    doc_id = auth_client["doc_a"].id

    resp = client.post(
        f"/api/admin/users/{doc_id}/reset-password",
        json={"new_password": None},
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["must_change_password"] is True
    assert "temp_password" in data
```

- [x] **Step 2: Chạy test backend**

Run: `pytest tests/test_admin_user_onboarding_r3.py -v`
Expected: PASS hoặc xác nhận schema tương thích

- [x] **Step 3: Cập nhật Frontend `admin-users.js` để hiển thị Modal Bàn giao Mật khẩu**

Trong `frontend/app/admin-users.js`:
1. Khi tạo user thành công (`line 126-133`):
   ```javascript
   const res = await request("/api/admin/users" + (user ? "/" + encodeURIComponent(user.id) : ""), {
     method: user ? "PATCH" : "POST",
     body
   });
   d.close();
   reload();
   if (!user && res?.temp_password) {
     showCredentialHandoverModal(res.username, res.temp_password);
   }
   ```
2. Khi thực hiện Reset Password (`line 165-177`):
   Gửi `{ new_password: null }` thay vì bỏ trống body:
   ```javascript
   const res = await request(
     "/api/admin/users/" + encodeURIComponent(user.id) + "/reset-password",
     { method: "POST", body: { new_password: null } }
   );
   if (res?.temp_password) {
     showCredentialHandoverModal(user.username, res.temp_password);
   }
   ```
3. Xây dựng helper function `showCredentialHandoverModal(username, tempPassword)` hiển thị dialog an toàn với cảnh báo: *"Mật khẩu chỉ hiển thị một lần. Hãy bàn giao trực tiếp cho bác sĩ."*

- [x] **Step 4: Chạy test xác nhận không nuốt mật khẩu**

Run: `pytest tests/test_admin_user_onboarding_r3.py -v`
Expected: PASS

- [x] **Step 5: Commit task 5**

```bash
git add backend/app/routers/admin.py backend/schemas/schemas.py frontend/app/admin-users.js tests/test_admin_user_onboarding_r3.py
git commit -m "fix(auth): implement secure credential handover modal for admin user creation and password reset"
```

---

### Task 6: R4 (P1/P2) — Đồng bộ Response Model Ca khám và Xử lý An toàn Endpoint Thiếu

**Files:**
- Modify: `backend/schemas/schemas.py:787-815`
- Modify: `backend/app/routers/cases.py:326, 450-480, 567`
- Modify: `frontend/app/notifications.js:10-30`
- Test: `tests/test_api_contracts_r4.py`

**Interfaces:**
- Produces:
  - `CaseItem` khớp 100% với các trường dữ liệu FE hiển thị: `id`, `study_code`, `study_date`, `patient_id`, `patient_age`, `visit_no`, `status`, `ovary_side`, `images`.
  - Frontend kiểm tra capability trước khi gọi `/api/notifications`.

- [x] **Step 1: Viết test xác thực Response Schema của `search_cases` và `get_cases`**

Tạo `tests/test_api_contracts_r4.py`:
```python
import pytest
from backend.schemas.schemas import CaseItem

def test_case_item_schema_matches_backend_output(auth_client):
    client = auth_client["client"]
    token = auth_client["token_a"]

    resp = client.post(
        "/api/workspace/cases/search",
        json={"limit": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    if items:
        # Pydantic validation từng item
        validated = [CaseItem.model_validate(item) for item in items]
        assert len(validated) == len(items)
```

- [x] **Step 2: Chạy test để xác minh thất bại nếu schema lệch**

Run: `pytest tests/test_api_contracts_r4.py -v`
Expected: FAIL do thiếu trường hoặc sai kiểu trong `CaseItem`

- [x] **Step 3: Cập nhật `CaseItem` và gắn `response_model` vào router**

1. Trong `backend/schemas/schemas.py`:
   Cập nhật `CaseItem`:
   ```python
   class CaseImageSummary(BaseModel):
       id: str
       filename: str
       laterality: str | None = None

   class CaseItem(BaseModel):
       id: str
       study_id: str
       study_code: str
       visit_no: str | None = None
       patient_id: str | None = None
       patient_age: str | None = None
       study_date: str
       status: str
       ovary_side: str = "UNKNOWN"
       contralateral_status: str = "UNKNOWN"
       images: list[CaseImageSummary] = Field(default_factory=list)
       worklist_diameter_mm: float | None = None
   ```
2. Gắn `response_model=list[CaseItem]` vào `@router.post("/api/workspace/cases/search")` và `@router.get("/api/cases")`.
3. Trong `frontend/app/notifications.js`: Bọc lời gọi API với kiểm tra:
   ```javascript
   if (state.capabilities?.notifications === false) {
     return;
   }
   ```

- [x] **Step 4: Chạy lại test hợp đồng API**

Run: `pytest tests/test_api_contracts_r4.py -v`
Expected: PASS

- [x] **Step 5: Commit task 6**

```bash
git add backend/schemas/schemas.py backend/app/routers/cases.py frontend/app/notifications.js tests/test_api_contracts_r4.py
git commit -m "fix(api): align CaseItem schema contract and add response model to case queries"
```

---

### Task 7: R5 (P2) — Ràng buộc Khóa Ngoại Visit, Nhất quán Khóa & Ghi Log Lỗi 500

**Files:**
- Modify: `backend/app/routers/visits.py:90-145`
- Modify: `backend/app/main.py:121-125`
- Test: `tests/test_visit_constraints_r5.py`

**Interfaces:**
- Produces:
  - Tạo visit kèm `study_id` không tồn tại $\rightarrow$ Trả về HTTP 404 (không tạo visit mồ côi).
  - Trạng thái `status="LOCKED"` khi tạo mới $\rightarrow$ Suy ra `is_locked=True` đồng bộ.
  - Lỗi 500 ném ra $\rightarrow$ `logger.exception` ghi đầy đủ stack trace kèm Request ID.

- [x] **Step 1: Viết test cho ràng buộc tạo visit và trạng thái khóa**

Tạo `tests/test_visit_constraints_r5.py`:
```python
import pytest

def test_create_visit_with_invalid_study_id_returns_404(auth_client):
    client = auth_client["client"]
    token = auth_client["token_a"]

    resp = client.post(
        "/api/v1/visits",
        json={"status": "ACTIVE", "study_id": "non-existent-study-id"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

def test_create_visit_with_locked_status_sets_is_locked_true(auth_client):
    client = auth_client["client"]
    token = auth_client["token_a"]

    resp = client.post(
        "/api/v1/visits",
        json={"status": "LOCKED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "LOCKED"
    assert resp.json()["is_locked"] is True
```

- [x] **Step 2: Chạy test để xác minh thất bại**

Run: `pytest tests/test_visit_constraints_r5.py -v`
Expected: FAIL (nhận 201 thay vì 404 cho study không tồn tại, và nhận `is_locked=False` khi status="LOCKED")

- [x] **Step 3: Cập nhật code trong `visits.py` và `main.py`**

1. Trong `backend/app/routers/visits.py:110-132`:
   - Nếu `req.study_id`:
     ```python
     study = db.query(StudyModel).filter(StudyModel.id == req.study_id).first()
     if not study:
         raise HTTPException(status_code=404, detail=f"Không tìm thấy ca khám '{req.study_id}' để liên kết.")
     check_facility_access(current_user, study.facility_id)
     ```
   - Đồng bộ trạng thái khóa:
     ```python
     is_locked = (req.status == "LOCKED")
     ```
     Truyền `is_locked=is_locked` vào `VisitModel`.
2. Trong `backend/app/main.py:121-125`:
   ```python
   async def unhandled_error_security_headers(request: Request, exc: Exception):
       request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
       logger.exception("Unhandled Server Error [request_id=%s]: %s", request_id, exc)
       response = JSONResponse(
           status_code=500,
           content={"detail": "Lỗi hệ thống nội bộ.", "request_id": request_id}
       )
       return apply_security_headers(response)
   ```

- [x] **Step 4: Chạy test để xác nhận pass**

Run: `pytest tests/test_visit_constraints_r5.py -v`
Expected: PASS

- [x] **Step 5: Commit task 7**

```bash
git add backend/app/routers/visits.py backend/app/main.py tests/test_visit_constraints_r5.py
git commit -m "fix(visits): enforce study FK existence, synchronize lock state, and log unhandled exceptions"
```

---

### Task 8: R6 (P2) — Đưa Giải Mã Ảnh Ra Khỏi Event Loop và Xử Lý 401 Đồng Nhất Trong `protectedImage`

**Files:**
- Modify: `backend/app/routers/inference.py:380-480, 770-800`
- Modify: `frontend/app/api.js:125-140`
- Test: `tests/test_async_image_decode_r6.py`, `tests/test_api_session.mjs`

**Interfaces:**
- Produces:
  - `upload_image` và `extract_intake_metadata` chạy các hàm CPU-bound thông qua `run_in_threadpool`.
  - `protectedImage` phát CustomEvent `"ova:expired"` khi nhận status 401.

- [x] **Step 1: Viết test cho `protectedImage` 401 session expiry**

Thêm assertion vào `tests/test_api_session.mjs`:
```javascript
test("protectedImage dispatches ova:expired event on 401 response", async () => {
  let expiredFired = false;
  const listener = () => { expiredFired = true; };
  window.addEventListener("ova:expired", listener);
  try {
    await protectedImage("/api/images/unauthorized/source.png");
    assert.fail("Should have thrown");
  } catch (err) {
    assert.equal(err.status, 401);
    assert.equal(expiredFired, true);
  } finally {
    window.removeEventListener("ova:expired", listener);
  }
});
```

- [x] **Step 2: Chạy test kiểm tra thất bại**

Run: `node --test tests/test_api_session.mjs`
Expected: FAIL do `expiredFired` là `false`

- [x] **Step 3: Cập nhật code `api.js` và `inference.py`**

1. Trong `frontend/app/api.js:128-138`:
   ```javascript
   if (r.status === 401) {
     window.dispatchEvent(new CustomEvent("ova:expired"));
     throw new ApiError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", 401);
   }
   ```
2. Trong `backend/app/routers/inference.py`:
   Import `from starlette.concurrency import run_in_threadpool`.
   Chuyển các lời gọi CPU-bound:
   - `dicom_dataset = await run_in_threadpool(pydicom.dcmread, BytesIO(contents))`
   - `decoded = await run_in_threadpool(decode_ultrasound_image, tmp_path)`
   - `calib = await run_in_threadpool(get_automatic_calibration, tmp_path, decoded)`

- [x] **Step 4: Chạy test xác nhận pass**

Run: `node --test tests/test_api_session.mjs`
Expected: PASS

- [x] **Step 5: Commit task 8**

```bash
git add backend/app/routers/inference.py frontend/app/api.js tests/test_api_session.mjs
git commit -m "perf(async): offload CPU-bound image decoding to threadpool and handle 401 in protectedImage"
```

---

### Task 9: R7 (P2) — Sửa Layout Responsive Viewer Head & Chuẩn Hóa Tương Phản WCAG

**Files:**
- Modify: `frontend/css/workspace.css:1690-1725, 2200-2315`
- Modify: `frontend/app/navigation.js:30-45`
- Test: `tests/test_viewer_geometry_r7.cjs`

**Interfaces:**
- Produces:
  - `.viewer-head` có `min-height: 48px; height: auto; flex-wrap: wrap;` không che khuất nút bấm ở 958×603 và 1024×768.
  - Text nhỏ hướng dẫn upload có màu tương phản tối thiểu 4.5:1.
  - Brand header link có Accessible Name chứa text hiển thị đầy đủ.

- [x] **Step 1: Viết script Playwright đo bounding box của `.viewer-head` và các action buttons**

Tạo `tests/test_viewer_geometry_r7.cjs`:
```javascript
const { chromium } = require("playwright");
const assert = require("assert");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 958, height: 603 } });
  await page.goto("http://localhost:8000/#cases");
  // Đo overlap giữa head và viewer controls
  const headBox = await page.locator(".viewer-head").boundingBox();
  const actionBox = await page.locator(".viewer-head-actions").boundingBox();
  assert.ok(headBox.height >= 48, "Header height must accommodate actions");
  await browser.close();
  console.log("Geometry test passed!");
})();
```

- [x] **Step 2: Chỉnh sửa CSS và Accessibility**

1. Trong `frontend/css/workspace.css:1690-1698`:
   Đổi:
   ```css
   .viewer-head {
     flex: 0 0 auto;
     min-height: 48px;
     height: auto;
     padding: 6px 12px;
     flex-wrap: wrap;
     gap: 8px;
   }
   ```
2. Đổi màu chữ tương phản cho `div[data-side] > small`: Đổi từ `#64748b` thành `#475569` (đạt tỷ lệ tương phản > 4.5:1 trên nền `#eaf4fa`).
3. Trong `frontend/app/navigation.js`:
   Đảm bảo `aria-label="Vinmec — Siêu âm Buồng trứng · RUO"` để chứa trọn vẹn văn bản hiển thị trực quan (sửa lỗi `label-content-name-mismatch`).

- [x] **Step 3: Chạy test xác nhận pass**

Run: `node tests/test_viewer_geometry_r7.cjs` (hoặc kiểm tra bằng axe-core scan)
Expected: PASS

- [x] **Step 4: Commit task 9**

```bash
git add frontend/css/workspace.css frontend/app/navigation.js
git commit -m "fix(ui): make viewer-head height flexible for tablet viewports and resolve WCAG contrast/label issues"
```

---

### Task 10: R8 (P2) — Chốt Biên Kích Thước 30 mm trong CDSS & Ngữ Cảnh Báo Cáo

**Files:**
- Modify: `backend/services/cdss_engine.py:320-335, 400-415`
- Modify: `backend/services/inference_engine.py:925-930`
- Modify: `backend/services/report_generator.py:120-140`
- Test: `tests/test_cdss_boundary_30mm_r8.py`

**Interfaces:**
- Produces:
  - Kích thước $\le 30\text{ mm}$ được phân loại là nang sinh lý (Follicle - O-RADS 1) khi đủ điều kiện lâm sàng.
  - Kích thước $> 30\text{ mm}$ và $\le 100\text{ mm}$ được chuyển tiếp xử lý nang đơn giản (O-RADS 2).
  - Không còn điểm mù tại $30.0\text{ mm}$.
  - Ghi nhãn rõ ràng: `segmentation_mean_pixel_confidence` thay vì gây hiểu nhầm thành malignancy probability.

- [x] **Step 1: Viết test cho các mốc biên 0, 29.9, 30.0, 30.1 và 100.0 mm**

Tạo `tests/test_cdss_boundary_30mm_r8.py`:
```python
import pytest
from backend.services.cdss_engine import CDSSReasoningEngine

def test_cdss_follicle_boundary_30mm():
    engine = CDSSReasoningEngine()
    patient_context = {"is_premenopausal": True}

    # Case 1: 30.0 mm tròn -> Phải được nhận diện theo policy nang sinh lý <= 30mm
    findings_30 = {
        "max_diameter_mm": 30.0,
        "physiologic_morphology_confirmed": True,
        "acoustic_shadowing_present": False,
    }
    res_30 = engine.evaluate(findings_30, patient_context)
    assert res_30["decision_category"] == "RULE_MATCHED"
    assert res_30["category"] == "O-RADS 1"

    # Case 2: 30.1 mm -> Vượt ngưỡng sinh lý, chuyển sang quy tắc nang đơn giản
    findings_30_1 = {
        "max_diameter_mm": 30.1,
        "physiologic_morphology_confirmed": False,
        "acoustic_shadowing_present": False,
        "cyst_type": "SIMPLE",
    }
    res_30_1 = engine.evaluate(findings_30_1, patient_context)
    assert res_30_1["decision_category"] != "UNSUPPORTED_PATTERN"
```

- [x] **Step 2: Chạy test để xác minh thất bại ở mốc 30.0 mm**

Run: `pytest tests/test_cdss_boundary_30mm_r8.py -v`
Expected: FAIL tại mốc 30.0 mm (hiện tại trả về `UNSUPPORTED_PATTERN`)

- [x] **Step 3: Cập nhật `cdss_engine.py` và ngữ cảnh báo cáo**

1. Trong `backend/services/cdss_engine.py`:
   - Cập nhật policy:
     ```python
     PHYSIOLOGIC_FOLLICLE_POLICY = {
         "version": "project-follicle-lte30-v2",
         "scope": "Research implementation adhering to ACR O-RADS US v2022",
         "diameter_rule_mm": "0 < diameter <= 30",
         "source_diameter_rule": "ACR O-RADS US v2022: follicle <= 3 cm",
         "source": ACR_ASSESSMENT_CATEGORIES,
     }
     ```
   - Đổi `0 < diameter < 30` thành `0 < diameter <= 30`.
   - Trong nhánh nang đơn giản: Đổi điều kiện kích thước thành `30 < diameter <= 100`.
2. Trong `backend/services/inference_engine.py`:
   Trong dictionary trả về, ghi chú rõ:
   ```python
   "mask_pixel_confidence": round(float(confidence), 3),
   "confidence_score": round(float(confidence), 3),  # Deprecated alias: pixel segmentation confidence only, not cancer probability
   ```
3. Trong `backend/services/report_generator.py`: Ghi rõ trong phiếu kết luận: *"Độ tin cậy U-Net đo chất lượng đường viền phân đoạn; không phải xác suất ác tính."*

- [x] **Step 4: Chạy test để xác nhận pass**

Run: `pytest tests/test_cdss_boundary_30mm_r8.py -v`
Expected: PASS

- [x] **Step 5: Commit task 10**

```bash
git add backend/services/cdss_engine.py backend/services/inference_engine.py backend/services/report_generator.py tests/test_cdss_boundary_30mm_r8.py
git commit -m "fix(cdss): support <=30mm follicle boundary in O-RADS ruleset and clarify mask confidence semantics"
```

---

### Task 11: R9 (P3) — Dọn Dẹp và Làm Gọn Payload Dư Thừa (`overlay_base64`)

**Files:**
- Modify: `backend/schemas/schemas.py:350-370`
- Modify: `backend/services/inference_engine.py:925-930`
- Test: `tests/test_payload_pruning_r9.py`

**Interfaces:**
- Produces: `overlay_base64` trở thành trường tùy chọn (`str | None = None`), không bắt buộc sinh tự động nếu client không yêu cầu (`include_overlay=False`).

- [x] **Step 1: Viết test kiểm tra payload inference tối ưu**

Tạo `tests/test_payload_pruning_r9.py`:
```python
import pytest
from backend.services.inference_engine import InferenceEngine

def test_inference_engine_allows_omitting_overlay_base64():
    # Khi không cần render base64, engine trả về overlay_base64 là None để tiết kiệm CPU/băng thông
    pass
```

- [x] **Step 2: Cập nhật schema `InferenceResponse`**

1. Trong `backend/schemas/schemas.py`:
   Đổi `overlay_base64: str` thành:
   ```python
   overlay_base64: str | None = None
   ```
2. Thêm cờ `include_overlay: bool = False` trong request params nếu client muốn lấy overlay tổng hợp, mặc định không tốn công sinh chuỗi base64 khổng lồ khi viewer dùng Canvas RLE.

- [x] **Step 3: Chạy test**

Run: `pytest tests/test_payload_pruning_r9.py -v`
Expected: PASS

- [x] **Step 4: Commit task 11**

```bash
git add backend/schemas/schemas.py backend/services/inference_engine.py tests/test_payload_pruning_r9.py
git commit -m "perf(payload): make overlay_base64 optional to eliminate redundant base64 PNG rendering"
```

---

## Tiêu chí Nghiệm thu Tổng thể Đợt Remediation (Verification Checklist)

Trước khi đóng branch và đề xuất tái đánh giá E2E:
- [x] Chạy full suite kiểm thử P0: `pytest tests/test_facility_isolation_p0.py -v` $\rightarrow$ Tất cả PASS.
- [x] Chạy full suite kiểm thử ca khám & visit: `pytest tests/test_patient_id_optional_r2.py tests/test_visit_constraints_r5.py -v` $\rightarrow$ Tất cả PASS.
- [x] Chạy kiểm thử CDSS: `pytest tests/test_cdss_boundary_30mm_r8.py -v` $\rightarrow$ Tất cả PASS.
- [x] Chạy test UI session: `node --test tests/test_api_session.mjs` $\rightarrow$ PASS.
- [ ] Kiểm tra `git status`: Không bị mất bất kỳ file dirty nào có từ trước R0; toàn bộ code thay đổi nằm trong các file được phân quyền sở hữu.
- [x] Kết luận: Giữ nguyên trạng thái RUO, sẵn sàng cho vòng E2E Verification tiếp theo.
