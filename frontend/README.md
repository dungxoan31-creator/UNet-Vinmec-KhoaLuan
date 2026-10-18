# Vinmec — Hỗ trợ phân đoạn siêu âm buồng trứng

SPA thuần HTML/CSS/ES modules. FastAPI phục vụ `index.html` và `/static`; không có bước build frontend và không thêm thư viện runtime.

## Mở ứng dụng

Từ thư mục repository, cấu hình `APP_JWT_SECRET`, `APP_ADMIN_PASSWORD`, `APP_DOCTOR_PASSWORD` trong môi trường. Sau đó khởi chạy qua launcher chuẩn hóa:

```powershell
# Kiểm tra điều kiện tiên quyết (CheckOnly)
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -CheckOnly

# Khởi chạy dịch vụ trên runtime độc lập
powershell -ExecutionPolicy Bypass -File scripts/run_prototype.ps1 -RuntimeDir "artifacts/prototype-runtime" -Port 8000
```

Mở `http://127.0.0.1:8000`. Màn đăng nhập hỗ trợ tài khoản bác sĩ và quản trị viên thật với mật khẩu đã cấu hình trong môi trường. Xem chi tiết tại [release_runbook.md](../docs/evaluation/release_runbook.md). Không mở `index.html` trực tiếp bằng `file://` vì app dùng module, Worker và API cùng origin.

## Tài liệu giao diện

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

Hệ thống sử dụng tài khoản xác thực, ca khảo sát và ảnh được tải lên máy chủ. Khi chưa có dữ liệu, giao diện hiển thị trạng thái trống; khi API lỗi, giao diện hiển thị lỗi và cho phép thử lại. Không có chế độ đăng nhập bỏ qua xác thực hoặc nguồn ảnh minh họa tự tạo.

Luồng hiện tại gồm đăng nhập, tạo ca hai bên, tải ảnh, IQA, phân đoạn, đo, hiệu chuẩn và lưu rà soát. Workflow hai cấp, OTP, CRUD quản trị và khóa đa thiết bị phụ thuộc khả năng API; máy chủ hiện tại chưa cung cấp đầy đủ các chức năng này.

Logo, font Inter và bảng màu được đối chiếu với website Vinmec và lưu cục bộ tại [assets/brand](assets/brand/README.md).
