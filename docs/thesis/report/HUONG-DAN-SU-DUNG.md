# Bộ báo cáo khóa luận theo mẫu Đinh Mạnh Hòa

## Tệp chính

- `Khoa-luan-Nguyen-Huu-Dung-theo-mau-Dinh-Manh-Hoa.docx`: nội dung và bảng chỉnh sửa trực tiếp trong Word; hình được nhúng vào tệp.
- Tệp `.pdf` cùng tên: bản xem trước bố cục đã xuất bằng Microsoft Word.
- Tệp `.md` cùng tên: nội dung nguồn, bảng Markdown và mã Mermaid.
- `figures/`: ảnh giao diện, hình thực nghiệm, sơ đồ PNG/SVG và Mermaid `.mmd` để chỉnh sửa.
- `KE-HOACH-VA-DOI-CHIEU-MAU.md`: đối chiếu chương mục với bài mẫu và hướng dẫn Khoa.
- `artifact-verification.json`: kết quả kiểm tra tệp xuất.

## Chỉnh sửa trong Word

Nội dung gồm ba chương theo kết cấu bài mẫu; phần AI, phân tích thiết kế, giao diện, kiểm thử và triển khai nằm trong các mục riêng của Chương 3. Mục lục, danh mục hình và danh mục bảng dùng trường Word. Sau khi sửa nội dung, nhấn `Ctrl+A`, `F9` và chọn cập nhật toàn bộ mục lục; kiểm tra lại trang trước khi in. Số trang nội dung bắt đầu tại Lời mở đầu, theo tài liệu hướng dẫn gốc.

Văn bản và bảng là đối tượng Word chỉnh sửa được. Hình được nhúng dưới dạng ảnh; để sửa sơ đồ, sửa tệp `.mmd` tương ứng rồi xuất ảnh và thay trong Word. Ảnh giao diện là ảnh chụp bản mẫu ở chế độ demo và được chú thích; các đường cong, metric và prediction lấy từ hồ sơ thí nghiệm đã lưu. Các thông tin chưa được xác minh hoặc chưa được thu thập được nêu rõ trong nội dung.

## Tái tạo bộ báo cáo

Tại thư mục gốc dự án, chạy lần lượt:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/build_hoa_style_thesis.py
node scripts/render_hoa_thesis_diagrams.js
.venv/Scripts/python.exe -X utf8 scripts/build_hoa_style_thesis.py --export
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/finalize_hoa_thesis.ps1 -SourcePath docs/thesis/theo-mau-dinh-manh-hoa-2026-10-13/Khoa-luan-Nguyen-Huu-Dung-theo-mau-Dinh-Manh-Hoa.docx
.venv/Scripts/python.exe -X utf8 scripts/verify_hoa_thesis_artifacts.py
```

Xuất PDF và cập nhật trường yêu cầu Microsoft Word trên Windows. Script sơ đồ sử dụng Chrome/Playwright và Mermaid; dữ liệu mô hình không được sinh lại bởi các bước xuất này. Các tài liệu gốc của Đinh Mạnh Hòa, hướng dẫn Khoa và đề cương sinh viên được giữ nguyên trong thư mục attachments.
