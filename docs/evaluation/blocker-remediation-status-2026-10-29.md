# Trạng thái remediation — 2026-10-29

Đây là snapshot bắt đầu công việc, không phải báo cáo hoàn thành. Chi tiết lịch sử và log trước đó ở `artifacts/audit_remediation_2026_10_28/status.md`; giả định A1–A10 ở `assumptions-register.md`.

| Hạng mục | Trạng thái | Bằng chứng và giới hạn |
|---|---|---|
| Khảo sát | BLOCKED | Đã lập `system-survey-2026-10-29.md`; còn phải truy nguyên toàn bộ đường dữ liệu. |
| PostgreSQL/migration | BLOCKED | Runtime từ chối `DATABASE_URL`; Docker Engine không kết nối. Kiểm thử an toàn cấu hình hiện tại 10 passed, xem `artifacts/audit_remediation_2026_10_28/evidence/database-baseline-2026-10-29-current.log`; không chứng minh PostgreSQL (A1). |
| Visit và đa cơ sở | BLOCKED | Chưa có Visit/facility scope hoàn chỉnh và test cách ly (A7, A9, A10). |
| UI | BLOCKED | Chưa rà soát đủ các màn hình và viewport; test workstation hiện thất bại tại assertion macro. |
| Provenance | BLOCKED | Audit split lịch sử không tái lập được; xem `artifacts/audit_remediation_2026_10_28/evidence/model-split-provenance-audit-2026-10-29.md` (A6). |
| Độc lập bệnh nhân | BLOCKED | Không có dữ liệu nhóm đáng tin cậy; image-level không chứng minh patient-level (A4). |
| Caliper và CDSS | BLOCKED | Có kiểm thử kỹ thuật trước đây; chưa có bộ phantom và tham chiếu chuyên gia theo yêu cầu (A2, A3). |
| Protocol/phê duyệt | BLOCKED | Tài liệu chuẩn bị không thay thế phê duyệt ethics/site (A5). |
| Tích hợp/regression | BLOCKED | Chưa chạy đầy đủ theo workflow mới; không có cơ sở tuyên bố PASS. |
