# ĐẶC TẢ API QUẢN LÝ LƯỢT KHÁM (VISIT API SPECIFICATION)
**Tiêu chuẩn định dạng**: `VIS-YYYYMMDD-XXXXXXXX` (32-bit random hex entropy, không chứa PII bệnh nhân).\
**Phạm vi**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Ra quyết định Lâm sàng (RUO).

---

## 1. Tổng quan Nghiệp vụ
Thực thể `Visit` đại diện cho một lượt khám siêu âm thực tế của bệnh nhân tại cơ sở y tế.
- Mỗi lượt khám sở hữu một mã duy nhất `visit_code` được sinh tự động tại Backend: `VIS-YYYYMMDD-XXXXXXXX`.
- Mã lượt khám **không** suy diễn hay thay thế mã định danh bệnh nhân (`patient_id` / `anonymized_pid`), không chứa thông tin định danh cá nhân (PII), và được bảo vệ chống trùng lặp tại tầng cơ sở dữ liệu (`uq_visits_visit_code`).
- Một lượt khám liên kết trực tiếp với các hình ảnh siêu âm hai bên buồng trứng, phiên bản rà soát HITL (`review_revision`), số đo Caliper ($d_1, d_2$), kết quả phân tích CDSS O-RADS/IOTA, và lịch sử kiểm toán (`AuditLog`).

---

## 2. Danh mục Endpoints

### 2.1. Tạo lượt khám mới
`POST /api/v1/visits` (hoặc alias `POST /visits`)
- **Phân quyền**: Yêu cầu tài khoản lâm sàng (`DOCTOR` / `CLINICAL`).
- **Request Body**:
```json
{
  "patient_id": "2e37b6e2-9aae-4aca-b69f-39cf60acb45f",
  "facility_id": "fac_01",
  "study_id": "optional-study-uuid",
  "status": "ACTIVE"
}
```
- **Response** (HTTP 201 Created):
```json
{
  "id": "7c5e57a5-216d-4fb5-ae79-acbdda687aa4",
  "visit_code": "VIS-20261029-A1B2C3D4",
  "facility_id": "fac_01",
  "patient_id": "2e37b6e2-9aae-4aca-b69f-39cf60acb45f",
  "status": "ACTIVE",
  "is_locked": false,
  "created_at": "2026-10-29T17:10:00Z",
  "updated_at": "2026-10-29T17:10:00Z",
  "studies": []
}
```

### 2.2. Lấy danh sách lượt khám
`GET /api/v1/visits` (hoặc alias `GET /visits`)
- **Query Parameters**:
  - `status`: Lọc theo trạng thái (`ACTIVE`, `COMPLETED`, `LOCKED`).
  - `search`: Tìm kiếm chuỗi trong `visit_code`.
  - `facility_id`: Lọc theo cơ sở y tế (nếu là quản trị viên hệ thống).
  - `page`: Số trang (mặc định 1).
  - `page_size`: Kích thước trang (mặc định 20, tối đa 100).
- **Phạm vi bảo mật**: Người dùng chỉ nhận được các lượt khám thuộc cơ sở của mình (`tenant isolation`). Quản trị viên toàn hệ thống có thể xem toàn bộ.

### 2.3. Lấy chi tiết lượt khám
`GET /api/v1/visits/{visit_code}` (hoặc alias `GET /visits/{visit_code}`)
- **Phân quyền**: Xác thực tài khoản hợp lệ, kiểm tra ranh giới cơ sở (HTTP 403 nếu cố tình truy cập lượt khám của cơ sở khác).
- **Response**: Trả về đầy đủ thông tin lượt khám, danh sách ca nghiên cứu (`studies`), số lượng ảnh, trạng thái hai bên buồng trứng.

### 2.4. Khóa lượt khám (Encounter Locking)
`POST /api/v1/visits/{visit_code}/lock`
- **Tác vụ**: Đánh dấu `is_locked = true` và `status = 'LOCKED'`.
- **Kiểm toán**: Tự động ghi nhận sự kiện `VISIT_LOCKED` vào bảng `audit_logs` với `actor_id` của bác sĩ thực hiện.
- **Ràng buộc**: Khi đã khóa, không cho phép bổ sung hoặc thay đổi kết quả rà soát của lượt khám này.
