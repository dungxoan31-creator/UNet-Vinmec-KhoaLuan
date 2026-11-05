# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG TẠI BỆNH VIỆN & CƠ SỞ Y TẾ
## Ovarian Ultrasound AI Decision Support System (Human-in-the-Loop)

> **Tài liệu Kỹ thuật DevOps & Enterprise Deployment**\
> **Phiên bản**: 2.0 (Production Release)\
> **Tuân thủ Tiêu chuẩn Y tế**: FDA 21 CFR Part 11, ISO 27799, HIPAA Security Rule, Thông tư 46/2018/TT-BYT & 54/2017/TT-BYT (Hồ sơ Bệnh án Điện tử EMR).\
> **Mã nguồn tham chiếu**: [backend/app/main.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/backend/app/main.py), [backend/db/database.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/backend/db/database.py), [deploy/nginx/nginx.conf](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/deploy/nginx/nginx.conf), [deploy/systemd/ovarian-ai-backend.service](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/deploy/systemd/ovarian-ai-backend.service).

---

## 1. TỔNG QUAN KIẾN TRÚC TRIỂN KHAI DOANH NGHIỆP

Hệ thống được thiết kế theo mô hình phân tầng enterprise (Multi-Tier Enterprise Architecture), phân định rõ ràng ranh giới giữa tầng hiển thị lâm sàng, tầng điều phối nghiệp vụ, động cơ tính toán AI, tầng lưu trữ kiên cố và giao diện tích hợp hệ thống thông tin y tế (PACS/HIS/RIS/EMR).

```mermaid
flowchart TD
    subgraph "VLAN 10: Clinical Workstations (Phòng Khám Siêu Âm)"
        WS1["Trạm Bác sĩ Siêu âm 01<br/>(Chrome / Edge - Canvas UI)"]
        WS2["Trạm Bác sĩ Siêu âm 02<br/>(Brush/Eraser/Caliper/Review)"]
    end

    subgraph "VLAN 20: Medical Imaging Devices & PACS"
        US["Máy Siêu âm Sản Phụ khoa<br/>(GE Voluson / Samsung Hera)"]
        PACS["Hệ thống PACS / DICOMweb<br/>(Orthanc / dcm4chee)"]
    end

    subgraph "VLAN 30: Enterprise Application Tier"
        NGINX["Nginx Reverse Proxy<br/>(TLS 1.3 / HTTP/2 / Rate Limit / CSP)"]
        API1["FastAPI Backend Worker 1<br/>(Uvicorn - Port 8000)"]
        API2["FastAPI Backend Worker 2<br/>(Uvicorn - Port 8000)"]
        AI["AI Inference Engine<br/>(PyTorch CUDA / 512x512 Letterbox)"]
    end

    subgraph "VLAN 40: High-Availability Data Tier"
        PG_PRIMARY[("PostgreSQL 16 Primary<br/>(ACID / Row-Level Security / Triggers)")]
        PG_STANDBY[("PostgreSQL 16 Standby<br/>(Streaming Replication)")]
        STORAGE["Medical Storage Volume<br/>(/opt/ovarian-ai/data - Encrypted LUKS)"]
    end

    WS1 -->|"HTTPS (Port 443 / TLS 1.3)"| NGINX
    WS2 -->|"HTTPS (Port 443 / TLS 1.3)"| NGINX
    US -->|"DICOM C-STORE (Port 104)"| PACS
    PACS <-->|"DICOMweb (QIDO-RS / WADO-RS)"| API1
    NGINX -->|"HTTP (127.0.0.1:8000)"| API1
    NGINX -->|"HTTP (127.0.0.1:8000)"| API2
    API1 <-->|"IPC / Tensor Memory"| AI
    API2 <-->|"IPC / Tensor Memory"| AI
    API1 -->|"SQLAlchemy Pool (Port 5432)"| PG_PRIMARY
    API2 -->|"SQLAlchemy Pool (Port 5432)"| PG_PRIMARY
    API1 -->|"File I/O (Uploads/Reports)"| STORAGE
    API2 -->|"File I/O (Uploads/Reports)"| STORAGE
    PG_PRIMARY -.->|"WAL Streaming (Port 5432)"| PG_STANDBY
```

### 1.1. Các Tầng Chức Năng (Architecture Tiers)

1. **Presentation & Reverse Proxy Tier (Nginx)**:
   - Tiếp nhận kết nối HTTPS từ các máy tính trạm bác sĩ qua cổng 443.
   - Chịu trách nhiệm mã hóa SSL/TLS termination, nén gzip/brotli cho dữ liệu tĩnh và JSON API.
   - Thiết lập giới hạn tần suất (`limit_req_zone`), chặn tấn công vét cạn tài khoản đăng nhập và tràn bộ đệm.
   - Cung cấp giao diện Web SPA phục vụ thao tác rà soát đường viền tổn thương (Brush, Eraser, Opacity, Zoom, Pan, Caliper D1/D2) mượt mà.

2. **Application & API Tier (FastAPI / Uvicorn)**:
   - Chạy dịch vụ FastAPI thông qua cụm 4 worker Uvicorn bất đồng bộ (Asynchronous ASGI).
   - Đảm nhiệm xác thực token JWT, kiểm soát phiên làm việc độc quyền chống xung đột ghi đè (`case_leases`), quản lý quy trình Human-in-the-Loop (HITL), và tạo báo cáo chẩn đoán lâm sàng PDF/JSON.
   - Điều hướng yêu cầu ảnh trực tiếp tới động cơ AI hoặc tải về từ PACS qua chuẩn DICOMweb.

3. **AI Inference Tier (PyTorch Core)**:
   - Sử dụng GPU NVIDIA (với CUDA 12.x) hoặc CPU đa nhân dự phòng (CPU Fallback qua OpenVINO/Torchscript).
   - Tiền xử lý chuẩn hóa Letterbox 512×512 bảo toàn tỉ lệ hình học, combo loss phân đoạn ($L_{\text{Dice}} + L_{\text{BCE}}$).
   - Kiểm tra toàn vẹn trọng số mô hình: Tự động đối chiếu mã băm SHA-256 từ file cấu hình `evaluation/selected_model.json` trước khi nạp vào VRAM nhằm loại trừ nguy cơ can thiệp mã độc.

4. **Database & Storage Tier (PostgreSQL 16 Enterprise)**:
   - Lưu trữ dữ liệu quan hệ ACID: bệnh nhân ẩn danh (HMAC-SHA256 pseudonymized PID), ca khám, ảnh siêu âm, dự đoán AI, điều chỉnh của bác sĩ, và lịch sử kiểm toán bất biến `audit_logs`.
   - Vùng lưu trữ tệp (Disk Storage): Phân vùng mã hóa chuẩn quân sự (LUKS dm-crypt), phân tách thư mục `data/uploads/` và `data/reports/`.

5. **PACS / DICOMweb Integration**:
   - Tích hợp với trạm lưu trữ và truyền hình ảnh y tế bệnh viện (PACS) thông qua chuẩn DICOM WADO-RS / QIDO-RS hoặc C-STORE/C-MOVE qua cổng Orthanc/dcm4chee.
   - Khử định danh dữ liệu tại trạm biên (Edge De-identification) trước khi đưa vào mô hình AI.

---

## 2. PHÂN QUYỀN BẢO MẬT MẠNG & AN TOÀN THÔNG TIN (NETWORK SECURITY)

Nhằm đáp ứng yêu cầu khắt khe của Bộ Y tế (Thông tư 46/2018/TT-BYT) và chuẩn quốc tế ISO 27799 / HIPAA Security Rule, hệ thống phải được triển khai trong mạng cục bộ nội bộ (LAN/Intranet) cô lập, tuyệt đối không mở cổng trực tiếp ra Internet công cộng.

### 2.1. Phân Tách VLAN (VLAN Segmentation)

| VLAN ID | Phân đoạn mạng | Dải IP khuyến nghị | Chức năng & Quyền hạn |
| :--- | :--- | :--- | :--- |
| **VLAN 10** | Clinical Workstations | `10.10.10.0/24` | Các máy tính phòng khám siêu âm, phòng đọc kết quả. Chỉ được truy cập cổng 443 trên VLAN 30. |
| **VLAN 20** | Modality & PACS | `10.10.20.0/24` | Máy siêu âm (GE, Samsung, Mindray) và PACS Server. Trao đổi DICOM C-STORE / DICOMweb với VLAN 30. |
| **VLAN 30** | Application & AI | `10.10.30.0/24` | Máy chủ dịch vụ (Nginx, FastAPI, PyTorch). Tiếp nhận cổng 443 từ VLAN 10 và kết nối cổng 5432 tới VLAN 40. |
| **VLAN 40** | Database & Storage | `10.10.40.0/24` | Máy chủ cơ sở dữ liệu PostgreSQL 16 và NAS lưu trữ. Chỉ cho phép VLAN 30 truy cập cổng 5432. |
| **VLAN 99** | Management & OAM | `10.10.99.0/24` | Quản trị hạ tầng (SSH, Bastion Host, Monitoring Prometheus/Grafana). Yêu cầu xác thực 2FA. |

### 2.2. Ma Trận Tường Lửa (Firewall Rules Matrix)

Thiết lập tường lửa máy chủ Linux (sử dụng `ufw` hoặc `iptables`) trên Máy chủ Ứng dụng (Application Server):

```bash
# 1. Đặt chính sách mặc định: Chặn toàn bộ kết nối vào/chuyển tiếp
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 2. Cho phép quản trị qua SSH chỉ từ mạng quản trị VLAN 99
sudo ufw allow from 10.10.99.0/24 to any port 22 proto tcp comment 'OAM SSH Management'

# 3. Cho phép trạm bác sĩ lâm sàng (VLAN 10) truy cập Web HTTPS (Port 443)
sudo ufw allow from 10.10.10.0/24 to any port 443 proto tcp comment 'Clinical Workstations HTTPS'

# 4. Cho phép chuyển hướng HTTP -> HTTPS (Port 80)
sudo ufw allow from 10.10.10.0/24 to any port 80 proto tcp comment 'HTTP Redirection'

# 5. Cho phép máy trạm PACS (VLAN 20) giao tiếp DICOMweb / DICOM C-STORE nếu cài đặt proxy DICOM
sudo ufw allow from 10.10.20.0/24 to any port 8042 proto tcp comment 'Orthanc DICOMweb API'

# 6. Kích hoạt tường lửa
sudo ufw enable
sudo ufw status verbose
```

> [!CAUTION]
> Tuyệt đối không mở cổng 8000 (FastAPI Uvicorn) và cổng 5432 (PostgreSQL) ra ngoài mạng nội bộ. Uvicorn phải được cấu hình ràng buộc strictly trên giao diện Loopback `127.0.0.1:8000`, và PostgreSQL chỉ lắng nghe IP nội bộ `10.10.40.x` hoặc `127.0.0.1`.

### 2.3. Cấu Hình Mã Hóa SSL/TLS

Hạ tầng y tế yêu cầu toàn bộ dữ liệu truyền nhận phải được mã hóa chuẩn TLS 1.2 / TLS 1.3:
- Sử dụng chứng chỉ số do Hạ tầng Khóa Công khai Nội bộ Bệnh viện (Hospital Enterprise Root CA) phát hành, hoặc chứng chỉ thương mại đã ký số.
- Vị trí lưu trữ chứng chỉ trên máy chủ Nginx:
  - File chứng chỉ: `/etc/ssl/certs/ovarian-ai.hospital.lan.crt`
  - Khóa bí mật (chỉ cấp quyền đọc cho root): `/etc/ssl/private/ovarian-ai.hospital.lan.key` (`chmod 600`)
  - Chứng chỉ CA gốc: `/etc/ssl/certs/hospital-root-ca.crt`

---

## 3. CẤU HÌNH BIẾN MÔI TRƯỜNG SẢN XUẤT (PRODUCTION ENVIRONMENT)

Tạo file cấu hình môi trường bảo mật tại `/etc/ovarian-ai/ovarian-ai.env` (phân quyền `chown root:ovarian-ai /etc/ovarian-ai/ovarian-ai.env && chmod 640 /etc/ovarian-ai/ovarian-ai.env`):

```ini
# ==============================================================================
# OVARIAN ULTRASOUND AI - PRODUCTION ENVIRONMENT CONFIGURATION
# Location: /etc/ovarian-ai/ovarian-ai.env
# ==============================================================================

# 1. Cơ chế môi trường & Định danh hệ thống
APP_ENVIRONMENT=PRODUCTION
APP_FACILITY_NAME=Vinmec Times City (Bệnh viện ĐKQT)
APP_FACILITY_CODE=FAC-VINMEC-TC

# 2. Cơ sở Dữ liệu Sản xuất (PostgreSQL 16 Connection Pool)
# Định dạng: postgresql+psycopg://<user>:<password>@<host>:<port>/<dbname>
DATABASE_URL=postgresql+psycopg://ovarian_app:StrongSecretPassword_2026@10.10.40.15:5432/ovarian_ai_prod

# 3. Tắt Chế độ Giả lập / Demo (BẮT BUỘC trong môi trường lâm sàng thực tế)
APP_SYNTHETIC_DEMO_MODE=0

# 4. Bảo mật Token & Xác thực Bác sĩ
# Chuỗi khóa bí mật JWT ngẫu nhiên tối thiểu 64 ký tự hex (tạo bằng: openssl rand -hex 32)
APP_JWT_SECRET=f4a9b83c2e1d0f5e7a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f
SECRET_KEY=f4a9b83c2e1d0f5e7a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f
ACCESS_TOKEN_EXPIRE_MINUTES=480

# 5. Khử định danh Bệnh nhân Lâm sàng (Pseudonymization Key HMAC-SHA256)
# Đường dẫn chứa khóa bí mật băm mã bệnh nhân (FDA/HIPAA Privacy Rule)
PATIENT_PID_SECRET_FILE=/etc/ovarian-ai/patient_pid_hmac.key
PATIENT_PID_HMAC_KEY_ID=KEY-PROD-2026-V1

# 6. Giới hạn Nguồn Gốc Tên Miền (CORS Origins)
# Chỉ cho phép domain/IP nội bộ của bệnh viện, TUYỆT ĐỐI KHÔNG DÙNG "*"
APP_CORS_ORIGINS=https://ovarian-ai.hospital.lan,https://10.10.30.12

# 7. Thư mục Lưu trữ Dữ liệu Cục bộ
APP_DATA_DIR=/opt/ovarian-ai/data
APP_LOG_DIR=/var/log/ovarian-ai

# 8. Cấu hình AI Model Registry & Checkpoint Verification
MODEL_SELECTION_MANIFEST=/opt/ovarian-ai/evaluation/selected_model.json
CUDA_VISIBLE_DEVICES=0
TORCH_NUM_THREADS=4

# 9. Tài khoản Quản trị Khởi tạo Ban đầu (Bootstrap Credentials)
# Sau khi tạo xong, đổi mật khẩu ngay qua giao diện quản trị
APP_ADMIN_PASSWORD=InitialComplexAdminPassword2026!
APP_ADMIN_FULL_NAME=Quản trị viên Hệ thống Y tế
APP_DOCTOR_PASSWORD=InitialDoctorClinicalPass2026!
APP_DOCTOR_FULL_NAME=BS.CKII Trưởng khoa CĐHA
```

> [!IMPORTANT]
> Biến `APP_SYNTHETIC_DEMO_MODE=0` là tham số sinh tử: Khi đặt bằng 0, hệ thống chuyển sang chế độ chấp nhận ảnh siêu âm thật từ máy lâm sàng, vô hiệu hóa việc hạn chế địa chỉ Loopback, và áp dụng đầy đủ ràng buộc khóa ngoại ACID cùng cơ chế bất biến kiểm toán.

---

## 4. QUY TRÌNH CÀI ĐẶT HẠ TẦNG TỪNG BƯỚC (STEP-BY-STEP DEPLOYMENT)

### Bước 1: Chuẩn Bị Máy Chủ Linux (Ubuntu 22.04 LTS / 24.04 LTS)

```bash
# Cập nhật gói hệ thống
sudo apt-get update && sudo apt-get upgrade -y

# Cài đặt các gói phụ thuộc cần thiết
sudo apt-get install -y python3.12 python3.12-venv python3-pip \
    nginx postgresql-client libpq-dev git curl jq ufw
```

### Bước 2: Thiết Lập Thư Mục Ứng Dụng & Phân Quyền Người Dùng

```bash
# Tạo người dùng hệ thống chuyên biệt không có quyền đăng nhập shell
sudo useradd -r -s /bin/false -d /opt/ovarian-ai ovarian-ai

# Tạo cây thư mục dự án
sudo mkdir -p /opt/ovarian-ai /etc/ovarian-ai /var/log/ovarian-ai
sudo mkdir -p /opt/ovarian-ai/data/uploads /opt/ovarian-ai/data/reports

# Clone mã nguồn dự án vào /opt/ovarian-ai
sudo git clone https://github.com/vinmec/ovarian-ultrasound-ai.git /opt/ovarian-ai

# Thiết lập môi trường ảo Python 3.12
cd /opt/ovarian-ai
sudo python3.12 -m venv .venv
sudo /opt/ovarian-ai/.venv/bin/pip install --upgrade pip setuptools wheel
sudo /opt/ovarian-ai/.venv/bin/pip install -r requirements.txt
sudo /opt/ovarian-ai/.venv/bin/pip install psycopg[binary]

# Sinh khóa bí mật mã hóa bệnh nhân
sudo openssl rand -hex 32 | sudo tee /etc/ovarian-ai/patient_pid_hmac.key > /dev/null
sudo chmod 600 /etc/ovarian-ai/patient_pid_hmac.key

# Phân quyền tệp tin an toàn
sudo chown -R ovarian-ai:ovarian-ai /opt/ovarian-ai /var/log/ovarian-ai
sudo chown -R root:ovarian-ai /etc/ovarian-ai
sudo chmod 750 /opt/ovarian-ai/data
```

### Bước 3: Cấu Hình Dịch Vụ Systemd

```bash
# Sao chép file cấu hình dịch vụ systemd
sudo cp /opt/ovarian-ai/deploy/systemd/ovarian-ai-backend.service /etc/systemd/system/

# Tải lại cấu hình systemd daemon
sudo systemctl daemon-reload

# Kích hoạt dịch vụ tự khởi động cùng hệ điều hành
sudo systemctl enable ovarian-ai-backend.service

# Khởi chạy dịch vụ
sudo systemctl start ovarian-ai-backend.service

# Kiểm tra trạng thái hoạt động
sudo systemctl status ovarian-ai-backend.service
```

### Bước 4: Cấu Hình & Khởi Động Nginx

```bash
# Sao chép cấu hình Nginx tối ưu cho y tế
sudo cp /opt/ovarian-ai/deploy/nginx/nginx.conf /etc/nginx/nginx.conf

# Kiểm tra cú pháp cấu hình Nginx
sudo nginx -t

# Khởi động lại Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 5. KẾT NỐI HỆ THỐNG PACS & TRẠM SIÊU ÂM (PACS / DICOM INTEGRATION)

Hệ thống hỗ trợ 2 phương thức tiếp nhận ảnh y tế từ phòng máy siêu âm:

```mermaid
sequenceDiagram
    autonumber
    participant US as "Máy Siêu Âm<br/>(GE / Samsung)"
    participant PACS as "Máy chủ PACS<br/>(Orthanc / dcm4chee)"
    participant App as "FastAPI Gateway<br/>(Ovarian AI Backend)"
    participant AI as "PyTorch Inference<br/>(CUDA 512x512)"
    participant Doc as "Trạm Bác Sĩ<br/>(Canvas Workstation)"

    US->>PACS: DICOM C-STORE (Dung lượng 5-30MB)
    PACS->>App: Webhook / C-MOVE Notify (StudyInstanceUID)
    App->>PACS: WADO-RS Retrieve Frame (DICOM / JPEG Lossless)
    App->>App: De-identification (Pseudonymize PID, HMAC-SHA256)
    App->>AI: Chuyển đổi mảng Tensor (Letterbox Resize 512x512)
    AI-->>App: Kết quả Phân đoạn (RLE Mask, Caliper D1/D2, Conf score)
    App->>Doc: WebSocket Push: Ca khám mới đã phân tích AI
    Doc->>App: Bác sĩ rà soát, tinh chỉnh Brush/Eraser & Xác nhận
    App->>PACS: Gửi báo cáo kết quả (DICOM SR / Encapsulated PDF)
```

1. **Phương thức 1: Tải trực tiếp qua DICOMweb (Khuyến nghị cho Bệnh viện hiện đại)**:
   - Backend sử dụng module kết nối chuẩn RESTful WADO-RS / QIDO-RS tới PACS.
   - Khi bác sĩ mở một ca khám, hệ thống truy xuất các khung hình 2D đơn (Single-frame) hoặc chuỗi thể tích (Cine Multi-frame) trực tiếp vào bộ nhớ đệm an toàn.

2. **Phương thức 2: Tải lên tệp ảnh/DICOM thủ công từ máy trạm lâm sàng**:
   - Bác sĩ xuất ảnh trực tiếp từ máy siêu âm ra định dạng `.dcm`, `.png` độ phân giải cao hoặc `.jpg` lossless.
   - Tải lên qua cổng giao tiếp bảo mật `/api/cases/upload`, giới hạn kích thước tối đa 100MB qua Nginx.

---

## 6. QUY TRÌNH SAO LƯU & PHỤC HỒI THẢM HỌA (DISASTER RECOVERY)

Nhằm đảm bảo tính sẵn sàng cao và an toàn hồ sơ bệnh án theo tiêu chuẩn ISO 27799:
- **Chỉ tiêu RPO (Recovery Point Objective)**: $< 15$ phút (mất mát dữ liệu tối đa không quá 15 phút nhờ cơ chế PostgreSQL WAL Archiving).
- **Chỉ tiêu RTO (Recovery Time Objective)**: $< 1$ giờ (thời gian khôi phục toàn bộ dịch vụ khi gặp sự cố phần cứng).

### Kịch Bản Sao Lưu Tự Động Định Kỳ (Cronjob)

Tạo file kịch bản sao lưu tại `/opt/ovarian-ai/scripts/backup_production.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/mnt/nas_backup/ovarian_ai"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATABASE_NAME="ovarian_ai_prod"
DB_USER="ovarian_app"

mkdir -p "${BACKUP_DIR}/db" "${BACKUP_DIR}/storage"

# 1. Sao lưu Cơ sở dữ liệu PostgreSQL (Format custom có nén, bảo toàn triggers/indexes)
pg_dump -U "${DB_USER}" -h 10.10.40.15 -Fc "${DATABASE_NAME}" > "${BACKUP_DIR}/db/${DATABASE_NAME}_${TIMESTAMP}.dump"

# 2. Đồng bộ gia số thư mục tệp tin ảnh và báo cáo
rsync -avz --delete /opt/ovarian-ai/data/ "${BACKUP_DIR}/storage/data_mirror/"

# 3. Dọn dẹp bản sao lưu cũ hơn 30 ngày (Tuân thủ chính sách lưu trữ y tế)
find "${BACKUP_DIR}/db" -type f -name "*.dump" -mtime +30 -delete

echo "[$(date)] Backup completed successfully: ${DATABASE_NAME}_${TIMESTAMP}.dump"
```

Cấu hình Crontab chạy tự động mỗi ngày lúc 01:00 sáng:
```cron
0 1 * * * /opt/ovarian-ai/scripts/backup_production.sh >> /var/log/ovarian-ai/backup.log 2>&1
```

---

## 7. DANH MỤC KIỂM TRA NGHIỆM THU TRIỂN KHAI (GO-LIVE CHECKLIST)

- [ ] **Bảo mật mạng**: Tường lửa chỉ mở cổng 443; cổng 8000 và 5432 bị cô lập hoàn toàn khỏi VLAN trạm khám.
- [ ] **Mã hóa TLS**: Chứng chỉ SSL/TLS hợp lệ, không xuất hiện cảnh báo trình duyệt, giao thức TLS 1.0/1.1 đã bị vô hiệu hóa.
- [ ] **Cơ sở dữ liệu**: PostgreSQL 16 đã nạp đầy đủ 25 bảng quan hệ; trigger bất biến `audit_logs` hoạt động chuẩn xác; composite index `ix_studies_facility_status_created` đã được đánh chỉ mục.
- [ ] **Biến môi trường**: `APP_SYNTHETIC_DEMO_MODE=0` đã được xác lập; `APP_CORS_ORIGINS` chỉ chứa FQDN bệnh viện; khóa HMAC bệnh nhân đã được sinh ngẫu nhiên.
- [ ] **Giám sát & Dịch vụ**: Dịch vụ `ovarian-ai-backend.service` chuyển trạng thái `active (running)`; Nginx ghi log định dạng `clinical_combined`.
- [ ] **Kiểm thử Luồng Lâm sàng**: Thực hiện tải lên ảnh siêu âm mẫu, chạy phân đoạn AI, rà soát trên Canvas, đo đạc kích thước Caliper D1/D2, và xuất báo cáo kết quả thành công.
