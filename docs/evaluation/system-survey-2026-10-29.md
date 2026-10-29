# Khảo sát kỹ thuật ban đầu — 2026-10-29

Trạng thái: khảo sát một phần; không phải phê duyệt triển khai. Các giả định A1–A10 được ghi trong `assumptions-register.md`.

## Thành phần và luồng

- Frontend là HTML/CSS và JavaScript ES modules; FastAPI phục vụ tài nguyên tĩnh và các router API. Authentication, phân quyền và các router được đăng ký trong `backend/app/main.py`.
- `backend/db/database.py` chứa SQLAlchemy ORM, engine SQLite và các migration SQLite riêng tại startup. `DATABASE_URL` hiện bị từ chối chủ động; các thao tác raw SQLite và PRAGMA cần được chuyển đổi và kiểm chứng trước khi hỗ trợ PostgreSQL.
- `PatientModel` liên kết `StudyModel`; study liên kết ảnh và review. Các bảng region assignment, caliper event, CDSS assessment và review batch đã tồn tại; cần kiểm tra từng đường ghi và scope trước khi thêm thực thể Visit.
- `visit_no` sáu ký tự của study và sequence hiện hữu không chứng minh có thực thể Visit, mã không dự đoán được hoặc cách ly cơ sở. Không coi chúng là patient ID hay tự động gộp dữ liệu lịch sử.
- Kiểm kê bằng `rg --files backend frontend tests` cho thấy 312 đường dẫn; đây không phải số lượng tính năng đã được kiểm chứng.

## Phụ thuộc và thứ tự

1. PostgreSQL: kiểm kê toàn bộ SQL theo dialect, xác định baseline migration và kiểm tra dữ liệu trước khi bật dialect mới. Docker CLI hiện có nhưng Engine không kết nối; chưa có bằng chứng PostgreSQL thật (A1).
2. Visit và cơ sở: xác định ownership, tương thích API, khóa và migration lịch sử trước khi nối UI; không suy luận quan hệ từ tên file (A7, A9, A10).
3. Frontend: đối chiếu dữ liệu và trạng thái với API, giữ disclosure RUO; kiểm tra tại viewport yêu cầu và trên dữ liệu tổng hợp (A8).
4. Provenance, độc lập dữ liệu, phantom và CDSS: lưu log, hash và giới hạn tương ứng; không suy ra hiệu lực lâm sàng (A2–A6).

## Bằng chứng hiện tại và tồn đọng

`artifacts/audit_remediation_2026_10_28/status.md` ghi lịch sử kiểm thử và các hạn chế. Chúng là bằng chứng tại thời điểm chạy, không thay thế chạy lại trên trạng thái hiện tại. Bộ workstation hiện thất bại vì assertion cấm macro không xác thực nhưng UI có năm macro. Cần điều tra sự khác biệt preset frontend/backend và cơ chế xác nhận trước khi quyết định hành vi; không hạ tiêu chí test.

Các luồng và dependency chưa được khảo sát toàn diện. Chưa có baseline Alembic, kiểm thử PostgreSQL thật, thiết kế/kiểm thử cách ly đa cơ sở, visit API, hoặc kiểm thử tích hợp đầy đủ theo yêu cầu. Chưa có bằng chứng độc lập mức bệnh nhân, xác thực lâm sàng hoặc phê duyệt site.
