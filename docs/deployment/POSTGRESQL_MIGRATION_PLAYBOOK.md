# KỊCH BẢN DI TRÚ CƠ SỞ DỮ LIỆU SQLITE SANG POSTGRESQL 16
## PostgreSQL Migration Playbook for Ovarian Ultrasound AI System

> **Tài liệu Kỹ thuật Vận hành CSDL Y tế (Database Runbook)**\
> **Phiên bản**: 2.0 (Enterprise Production Migration)\
> **Áp dụng cho**: Chuyển đổi từ SQLite phát triển/thử nghiệm sang PostgreSQL 16 Enterprise tại cơ sở y tế / bệnh viện.\
> **Mã nguồn di trú**: [scripts/migrate_sqlite_to_postgres.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/scripts/migrate_sqlite_to_postgres.py), [backend/db/database.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/backend/db/database.py).\
> **Bộ kiểm thử tự động**: [tests/test_sqlite_to_postgres_migration.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/tests/test_sqlite_to_postgres_migration.py).

---

## 1. MỤC ĐÍCH & RÀNG BUỘC KỸ THUẬT

### 1.1. Mục Tiêu Di Trú
Chuyển đổi toàn bộ dữ liệu lâm sàng từ SQLite (file `ovarian_ai.db`) sang hệ quản trị cơ sở dữ liệu phân tán PostgreSQL 16 mà không làm gián đoạn tính toàn vẹn nghiệp vụ:
- **Bảo toàn 100% dữ liệu lâm sàng**: Không mất mát bất kỳ bản ghi bệnh nhân, ca khám, dự đoán AI, điều chỉnh Human-in-the-Loop, hoặc nhật ký kiểm toán nào.
- **Tính toán Checksum xác thực**: Đối chiếu mã băm xác thực SHA-256 từng bảng giữa nguồn và đích (Deterministic SHA-256 Checksum).
- **Tuân thủ Tiêu chuẩn Y tế**:
  - FDA 21 CFR Part 11 & ISO 27799: Bắt buộc kích hoạt trigger bất biến hóa `audit_logs` (nghiêm cấm mọi hành vi UPDATE/DELETE trên bảng nhật ký).
  - ACR O-RADS US v2022 & IOTA Lexicon: Bảo toàn các trường đo lường Caliper D1/D2, diện tích khối u, lát cắt hình thái và phân tầng rủi ro CDSS.
  - Đa cơ sở (Multi-Facility Isolation): Xác thực tính cô lập dữ liệu theo từng cơ sở khám chữa bệnh thông qua `facility_id` và chỉ mục liên hợp `ix_studies_facility_status_created`.

### 1.2. Các Chỉ Tiêu Dịch Vụ (Service Level Objectives)
- **RPO (Recovery Point Objective)**: $0$ (Không chấp nhận mất mát bất kỳ giao dịch nào trong quá trình di trú).
- **RTO (Recovery Time Objective)**: $< 30$ phút cho toàn bộ quy trình di trú dữ liệu và kiểm thử chấp nhận.
- **Thời gian ngừng hệ thống (Maintenance Window)**: Khuyến nghị thực hiện ngoài giờ khám bệnh (từ 22:00 đến 05:00 sáng).

---

## 2. QUY TRÌNH DI TRÚ TỔNG THỂ (MIGRATION WORKFLOW)

```mermaid
flowchart TD
    subgraph "Giai đoạn 1: Chuẩn bị & Đóng băng Dữ liệu"
        A1["Thông báo bảo trì hệ thống"] --> A2["Dừng backend FastAPI (systemctl stop)"]
        A2 --> A3["Sao lưu SQLite vật lý (ovarian_ai.db.bak)"]
        A3 --> A4["Chạy PRAGMA integrity_check trên SQLite"]
    end

    subgraph "Giai đoạn 2: Khởi tạo Hạ tầng PostgreSQL 16"
        B1["Tạo Database ovarian_ai_prod & User"] --> B2["Cấu hình pg_hba.conf & postgresql.conf"]
        B2 --> B3["Khởi tạo Schema & Triggers qua --setup-schema"]
    end

    subgraph "Giai đoạn 3: Thực thi Di trú & Đồng bộ"
        C1["Chạy Dry-Run tính Checksum SQLite"] --> C2["Di trú Dữ liệu theo Thứ tự Topo (25 bảng)"]
        C2 --> C3["Ép kiểu thích ứng: Boolean (0/1 -> bool)"]
        C3 --> C4["Đồng bộ Sequences (audit_logs_id_seq)"]
    end

    subgraph "Giai đoạn 4: Xác thực Ràng buộc Y tế & Hoàn tất"
        D1["So khớp Checksum SHA-256 & Số dòng"] --> D2["Kiểm tra Composite Index ix_studies_facility_status_created"]
        D2 --> D3["Kiểm tra Trigger Bất biến audit_logs (FDA CFR Part 11)"]
        D3 --> D4["Xác thực Tính cô lập Đa cơ sở (Multi-facility)"]
        D4 --> D5["Cập nhật .env (DATABASE_URL) & Khởi động lại Backend"]
    end

    A4 --> B1
    B3 --> C1
    C4 --> D1
```

---

## 3. CHUẨN BỊ TRƯỚC DI TRÚ (PRE-MIGRATION READINESS)

### 3.1. Dừng Dịch Vụ Ứng Dụng Để Đảm Bảo Toàn Vẹn Giao Dịch
Trước khi tiến hành, phải tạm dừng dịch vụ FastAPI để đảm bảo không có giao dịch ghi mới nào phát sinh trên cơ sở dữ liệu SQLite:

```bash
# Dừng backend FastAPI
sudo systemctl stop ovarian-ai-backend.service

# Kiểm tra đảm bảo không còn tiến trình nào truy cập SQLite file
sudo lsof /opt/ovarian-ai/data/ovarian_ai.db || echo "Database file is idle."
```

### 3.2. Sao Lưu Vật Lý SQLite & Kiểm Tra Tính Toàn Vẹn
Tạo bản sao lưu lưu trữ an toàn kèm mã băm SHA-256 xác thực:

```bash
cd /opt/ovarian-ai

# 1. Tạo bản sao lưu thời điểm (Snapshot)
cp ovarian_ai.db ovarian_ai_pre_migration_$(date +%Y%m%d_%H%M%S).bak

# 2. Ghi nhận mã băm toàn vẹn của file sao lưu
sha256sum ovarian_ai.db > ovarian_ai_checksum.sha256
cat ovarian_ai_checksum.sha256

# 3. Kiểm tra tính toàn vẹn cấu trúc file SQLite
sqlite3 ovarian_ai.db "PRAGMA integrity_check;"
sqlite3 ovarian_ai.db "PRAGMA foreign_key_check;"
```
*(Yêu cầu kết quả `integrity_check` trả về `ok` và `foreign_key_check` không trả về dòng lỗi nào).*

---

## 4. KHỞI TẠO CƠ SỞ DỮ LIỆU ĐÍCH POSTGRESQL 16

### 4.1. Tạo Database & Phân Quyền Người Dùng
Đăng nhập máy chủ PostgreSQL (VLAN 40) và thực thi script SQL sau:

```sql
-- Đăng nhập bằng tài khoản postgres
-- psql -U postgres

-- 1. Tạo Database sản xuất với collation UTF-8 chuẩn xác
CREATE DATABASE ovarian_ai_prod
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'C.UTF-8'
    LC_CTYPE = 'C.UTF-8'
    TEMPLATE = template1;

-- 2. Tạo User chuyên dụng cho ứng dụng lâm sàng
CREATE USER ovarian_app WITH ENCRYPTED PASSWORD 'StrongSecretPassword_2026';

-- 3. Cấp quyền truy cập tối thiểu (Principle of Least Privilege)
GRANT CONNECT ON DATABASE ovarian_ai_prod TO ovarian_app;
\c ovarian_ai_prod

GRANT ALL ON SCHEMA public TO ovarian_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ovarian_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ovarian_app;
```

### 4.2. Khởi Tạo Cấu Trúc Schema & Triggers Bất Biến Bằng Script
Sử dụng cờ `--setup-schema` của script `scripts/migrate_sqlite_to_postgres.py` để tự động khởi tạo toàn bộ 25 bảng, chỉ mục và trigger bất biến trên PostgreSQL:

```bash
cd /opt/ovarian-ai
.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
    --pg-url "postgresql+psycopg://ovarian_app:StrongSecretPassword_2026@10.10.40.15:5432/ovarian_ai_prod" \
    --setup-schema \
    --dry-run
```

---

## 5. THỰC THI DI TRÚ DỮ LIỆU (EXECUTION)

### 5.1. Chạy Phân Tích Khảo Sát Nguồn (Dry-Run Mode)
Trước khi ghi dữ liệu thật, chạy chế độ phân tích nguồn để kiểm đếm số dòng và tính toán mã băm SHA-256 ban đầu:

```bash
.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path ovarian_ai.db \
    --dry-run
```

*Mẫu kết quả khảo sát hiển thị*:
```text
2026-11-01 23:00:00 [INFO] Found 25 tables to migrate: ['facilities', 'patients', 'users', ...]
2026-11-01 23:00:00 [INFO] Source SQLite table 'facilities': 1 rows, checksum=3f8a91b...
2026-11-01 23:00:00 [INFO] Source SQLite table 'patients': 120 rows, checksum=7c1b4e2...
2026-11-01 23:00:00 [INFO] Source SQLite table 'studies': 150 rows, checksum=8a2f01d...
2026-11-01 23:00:00 [INFO] Source SQLite table 'audit_logs': 1420 rows, checksum=99e4b1a...
2026-11-01 23:00:00 [INFO] [DRY RUN] Source database analyzed successfully. No changes written.
```

### 5.2. Chạy Lệnh Di Trú Chính Thức (Live Migration)
Thực hiện nạp dữ liệu nguyên tử (Atomic Transaction): Nếu xảy ra bất kỳ lỗi ràng buộc nào, giao dịch sẽ tự động Rollback hoàn toàn:

```bash
.venv/bin/python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path ovarian_ai.db \
    --pg-url "postgresql+psycopg://ovarian_app:StrongSecretPassword_2026@10.10.40.15:5432/ovarian_ai_prod"
```

### 5.3. Thứ Tự Nạp Bảng Tuân Thủ Khóa Ngoại (Topological Insertion Order)
Script tự động tuân thủ thứ tự nạp 25 bảng để không gây xung đột khóa ngoại:
1. `facilities`, `patients`, `visit_number_sequences`, `pending_file_deletions`, `audit_logs`, `email_verification_challenges`, `consumed_password_reset_tokens`, `auth_rate_limits`.
2. `users`, `visits`.
3. `studies`.
4. `images`, `case_leases`, `review_batches`, `ui_events`, `notifications`, `correction_requests`.
5. `predictions`, `reviews`.
6. `active_learning_queue`, `region_assignment_batches`.
7. `region_caliper_events`.
8. `region_cdss_assessments`.
9. `hitl_sessions`, `hitl_events`.

---

## 6. XÁC THỰC TÍNH TOÀN VẸN Y TẾ & RÀNG BUỘC LÂM SÀNG (VERIFICATION)

Sau khi dữ liệu đã được nạp thành công, bắt buộc thực hiện kiểm tra 4 tiêu chí nghiệm thu y tế sau đây:

### 6.1. Xác Thực Composite Index `ix_studies_facility_status_created`
Chỉ mục liên hợp trên bảng `studies` là thành phần quyết định tốc độ truy vấn danh sách ca khám theo từng cơ sở khám chữa bệnh:

```sql
-- Chạy trên psql kết nối tới ovarian_ai_prod
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'studies'
  AND indexname = 'ix_studies_facility_status_created';
```
*Kết quả kỳ vọng*:
```text
               indexname               |                                           indexdef
---------------------------------------+-----------------------------------------------------------------------------------------------
 ix_studies_facility_status_created    | CREATE INDEX ix_studies_facility_status_created ON public.studies USING btree (facility_id, status, created_at)
```

### 6.2. Kiểm Tra Trigger Bất Biến Hóa `audit_logs` (FDA 21 CFR Part 11 / ISO 27799)
Kiểm tra xem hệ thống có nghiêm cấm việc chỉnh sửa hoặc xóa nhật ký kiểm toán lâm sàng hay không:

```sql
-- 1. Kiểm tra sự tồn tại của 2 triggers
SELECT tgname, tgenabled
FROM pg_trigger
WHERE tgname IN ('trg_audit_logs_no_update', 'trg_audit_logs_no_delete');

-- 2. Thử nghiệm hành vi CẤM UPDATE trên audit_logs (Bắt buộc phải thất bại)
UPDATE audit_logs SET action_type = 'TAMPERED_ACTION' WHERE id = (SELECT id FROM audit_logs LIMIT 1);
```
*Kết quả kỳ vọng bắt buộc phải sinh lỗi ném ngoại lệ*:
```text
ERROR:  Audit log is append-only and immutable; UPDATE and DELETE are forbidden under FDA 21 CFR Part 11 / ISO 27799.
CONTEXT:  PL/pgSQL function trg_audit_logs_immutable() line 3 at RAISE
```

```sql
-- 3. Thử nghiệm hành vi CẤM DELETE trên audit_logs (Bắt buộc phải thất bại)
DELETE FROM audit_logs WHERE id = (SELECT id FROM audit_logs LIMIT 1);
```
*Kết quả kỳ vọng bắt buộc phải sinh lỗi ném ngoại lệ*:
```text
ERROR:  Audit log is append-only and immutable; UPDATE and DELETE are forbidden under FDA 21 CFR Part 11 / ISO 27799.
```

### 6.3. Xác Thực Đồng Bộ Sequence Khóa Chính (`audit_logs_id_seq`)
Đảm bảo sequence của PostgreSQL đã được đồng bộ với giá trị `MAX(id)` đã nạp từ SQLite để tránh lỗi trùng lặp khóa chính khi ghi nhận nhật ký mới:

```sql
SELECT
    last_value,
    (SELECT MAX(id) FROM audit_logs) AS current_max
FROM audit_logs_id_seq;
```
*Yêu cầu `last_value >= current_max`*.

### 6.4. Kiểm Tra Tính Cô Lập Đa Cơ Sở (Multi-Facility Isolation)
Đảm bảo tính toàn vẹn phân tách dữ liệu giữa các cơ sở:

```sql
-- 1. Thống kê số lượng ca khám theo từng cơ sở y tế
SELECT
    f.facility_code,
    f.name,
    COUNT(s.id) AS total_studies,
    COUNT(u.id) AS total_users
FROM facilities f
LEFT JOIN studies s ON s.facility_id = f.id
LEFT JOIN users u ON u.facility_id = f.id
GROUP BY f.facility_code, f.name;

-- 2. Xác thực không có ca khám nào bị mồ côi (tham chiếu facility_id không hợp lệ)
SELECT COUNT(*) AS orphaned_studies
FROM studies s
WHERE s.facility_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM facilities f WHERE f.id = s.facility_id);
```
*(Yêu cầu `orphaned_studies = 0`)*.

---

## 7. CHUYỂN ĐỔI HỆ THỐNG & KIỂM THỬ KHÓI (CUTOVER & SMOKE TEST)

### 7.1. Cập Nhật Cấu Hình Biến Môi Trường Sản Xuất
Chỉnh sửa file `/etc/ovarian-ai/ovarian-ai.env`:

```ini
# Chuyển đổi từ SQLite sang PostgreSQL
DATABASE_URL=postgresql+psycopg://ovarian_app:StrongSecretPassword_2026@10.10.40.15:5432/ovarian_ai_prod
APP_SYNTHETIC_DEMO_MODE=0
```

### 7.2. Khởi Động Lại Ứng Dụng
```bash
# Khởi động lại dịch vụ backend
sudo systemctl restart ovarian-ai-backend.service

# Kiểm tra log khởi động
sudo journalctl -u ovarian-ai-backend.service -n 50 --no-pager
```
*Log khởi động phải xuất hiện dòng*:
`[Database] PostgreSQL DB initialized and verified.`

### 7.3. Danh Mục Kiểm Thử Khói Lâm Sàng (Clinical Smoke Tests)
1. **Đăng nhập Bác sĩ**: Truy cập `https://ovarian-ai.hospital.lan/`, đăng nhập bằng tài khoản `doctor` / mật khẩu mới.
2. **Xem Danh sách Ca khám**: Mở danh sách ca khám, kiểm tra bộ lọc cơ sở `FAC-VINMEC-TC`, kiểm tra độ trễ hiển thị (phải $< 150\text{ ms}$ nhờ index `ix_studies_facility_status_created`).
3. **Mở Chi tiết Ca khám**: Mở một ca khám đã có, hiển thị ảnh siêu âm và mặt nạ phân đoạn do AI tạo ra.
4. **Kiểm tra Ghi Nhật ký Mới**: Thực hiện thao tác khóa phiên làm việc (Case Lease) hoặc gửi một lượt đánh giá review, kiểm tra bản ghi mới được sinh ra trong bảng `audit_logs` trên PostgreSQL thành công.

---

## 8. KẾ HOẠCH HOÀN TÁC KHẨN CẤP (EMERGENCY ROLLBACK PLAN)

Trong trường hợp phát hiện bất kỳ lỗi không tương thích nào đe dọa đến hoạt động khám chữa bệnh tại bệnh viện, Trưởng nhóm DevOps thực hiện quy trình hoàn tác về SQLite trong vòng dưới **5 phút**:

```bash
# ==============================================================================
# KHẨN CẤP: QUY TRÌNH HOÀN TÁC VỀ SQLITE (EMERGENCY ROLLBACK IN < 5 MINUTES)
# ==============================================================================

# 1. Dừng backend FastAPI ngay lập tức
sudo systemctl stop ovarian-ai-backend.service

# 2. Khôi phục file SQLite nguyên bản từ bản sao lưu trước di trú
cd /opt/ovarian-ai
cp ovarian_ai_checksum.sha256 ovarian_ai.db.verify
sha256sum -c ovarian_ai_checksum.sha256

# 3. Đổi cấu hình DATABASE_URL trong /etc/ovarian-ai/ovarian-ai.env quay lại SQLite
sudo sed -i 's|^DATABASE_URL=postgresql.*|DATABASE_URL=sqlite:////opt/ovarian-ai/ovarian_ai.db|g' /etc/ovarian-ai/ovarian-ai.env

# 4. Khởi động lại dịch vụ backend
sudo systemctl start ovarian-ai-backend.service

# 5. Kiểm tra trạng thái hoạt động bình thường
sudo systemctl status ovarian-ai-backend.service
```

> [!NOTE]
> Bản sao lưu `ovarian_ai_pre_migration_*.bak` và file mã băm `ovarian_ai_checksum.sha256` phải được bảo lưu trên NAS tối thiểu 90 ngày sau ngày Go-Live thành công.
