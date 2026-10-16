# Ova Workspace 2.0

SPA thuần HTML/CSS/ES modules. FastAPI phục vụ `index.html` và `/static`; không có bước build frontend và không thêm thư viện runtime.

## Mở ứng dụng

Từ thư mục repository, cấu hình `APP_JWT_SECRET`, `APP_ADMIN_PASSWORD`, `APP_DOCTOR_PASSWORD` trong môi trường. Sau đó khởi chạy qua launcher chuẩn hóa:

```powershell
# Kiểm tra điều kiện tiên quyết (CheckOnly)
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -CheckOnly

# Khởi chạy dịch vụ prototype trên runtime độc lập
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -RuntimeDir "artifacts/prototype-runtime" -Port 8000
```

Mở `http://127.0.0.1:8000`. Màn đăng nhập hỗ trợ tài khoản bác sĩ và quản trị viên thật với mật khẩu đã cấu hình trong môi trường. Xem chi tiết tại [release_runbook.md](../docs/evaluation/release_runbook.md). Không mở `index.html` trực tiếp bằng `file://` vì app dùng module, Worker và API cùng origin.

## Tài liệu / mockup

- [Sitemap, luồng, RBAC, design system, API và checklist](../docs/reports/Workspace_V2_Design_and_API.md).
- [Gallery ảnh chụp desktop và tablet](../artifacts/workspace-v2/gallery.html).
- [Tokens](css/workspace-tokens.css), [styles](css/workspace.css), [modules](app/).
- `legacy-workspace.html` giữ bản FE cũ để đối chiếu, không phải route của app mới.

## Kiểm thử

Server thử nghiệm: `python -m tests.serve_isolated_app` tại 8027, dùng DB/uploads cô lập. Các browser test cần `playwright-core`, Chrome trên Windows và credentials test được cấu hình cho server này. Không dùng tài khoản hoặc DB thật để chạy test.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_workspace_v2.ps1
.venv\Scripts\python.exe -m pytest -q --tb=short
```

Có thể dùng `-SkipBrowser` để chỉ kiểm tra syntax và logic thuần. Log kết quả nằm trong `artifacts/workspace-v2/`.

## Giới hạn tích hợp

Luồng thật đã nối login, tạo ca hai bên, upload/IQA/AI, đo, hiệu chuẩn và lưu review nghiên cứu. Các màn workflow hai cấp, OTP, CRUD quản trị và lease đa thiết bị dùng contract mới trong tài liệu; backend hiện tại chưa cung cấp. UI báo lỗi nếu API thiếu. Không coi demo là bằng chứng bảo mật server, ẩn danh tự động hoặc kết quả thực nghiệm AI.
