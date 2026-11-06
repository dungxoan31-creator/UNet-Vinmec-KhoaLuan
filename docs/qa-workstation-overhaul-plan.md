# Kế hoạch QA và sửa lỗi workstation HITL

Ngày bắt đầu: **2026-10-25**
Nhánh làm việc hiện tại: `main`

## Mục tiêu

Đánh giá workstation nghiên cứu siêu âm buồng trứng theo quy trình thật của bác sĩ bận rộn; xử lý lỗi có thể tái hiện; giữ rõ giới hạn RUO, bảo vệ nguồn dữ liệu và không đưa ra chẩn đoán tự động thiếu căn cứ.

## Ràng buộc không được vi phạm

- Không sửa `dataset/`, ảnh/mask nguồn, split đã đóng băng, checkpoint/trọng số hoặc kiến trúc mô hình.
- Không huấn luyện lại mô hình.
- Kiểm thử tự động chỉ dùng ảnh/DICOM tổng hợp hoặc ảnh tổng hợp tạo riêng trong `tmp_path`; không đọc ảnh bệnh nhân từ `dataset/` hay `ai_training/`.
- Chạy browser E2E trên server và SQLite database cô lập; không dùng `ovarian_ai.db`.
- Giữ nguyên image-level split đã khử trùng lặp SHA-256, Letterbox 512×512, Dice+BCE và rà soát HITL; không yêu cầu patient ID cho huấn luyện và không diễn giải split ảnh thành độc lập theo bệnh nhân.
- Không đưa PID nguồn vào log, URL hoặc bản ghi có thể khôi phục nếu chưa có quyết định Product/Data Owner về mã hóa, quyền truy cập và vòng đời dữ liệu.
- Không tuyên bố hiệu lực lâm sàng, readiness pilot hoặc tuân thủ pháp lý khi chưa có bằng chứng độc lập.

## Kế hoạch thực hiện và checkpoint

1. **Đóng băng baseline:** xác nhận nhánh sạch, ghi log cú pháp, test JS, pytest và Ruff; phân loại từng lỗi baseline.
2. **Kiểm tra ranh giới dữ liệu:** thay mọi nguồn ảnh test từ split/dataset bằng fixture tổng hợp; rà soát mã browser/API trước khi chạy tiếp test.
3. **Sửa blocker có nguyên nhân xác định:** làm test hermetic, sửa fixture DICOM, bổ sung model card và hồ sơ đánh giá tối thiểu, không sửa test bằng skip/xfail.
4. **Chạy unit/API regression:** chạy focused tests trên dữ liệu tổng hợp, sau đó chạy toàn bộ suite khi audit nguồn ảnh đạt.
5. **Kiểm tra UI và quy trình:** kiểm tra năm route (`dashboard`, `intake`, `viewer`, `report`, `admin`) tại 1440×900, 768×1024 và 390×844; kiểm tra bàn phím, validation, lưu và lỗi mạng.
6. **Chạy E2E hai vòng:** dùng Playwright, port 8027, database cô lập riêng; giữ log, screenshot và mọi lỗi console/pageerror/HTTP 500.
7. **Đóng bug và bàn giao:** cập nhật bug log, known issues, spec questions, test checklist, test log và roadmap. Chỉ đóng mục có bằng chứng test tái hiện sau sửa.

## Tiêu chí dừng

- Bất kỳ đường test nào có thể đọc ảnh nguồn bệnh nhân hoặc ghi vào dữ liệu/mô hình bị bảo vệ.
- Có lỗi P0/P1 chưa được khoanh vùng hoặc test an toàn chưa thể xác minh.
- Còn failure trong unit/integration, hoặc một trong hai vòng E2E có console/page error hay HTTP 500.
- Hành vi phụ thuộc quyết định Product/Clinical/Data Owner chưa được xác định; phần liên quan phải được đánh dấu rõ và không được tự suy diễn.

## Tài liệu thực thi

- [Prompt QA/QC đã điều chỉnh theo codebase](prompts/qa-workstation-codebase-prompt.md)
- [Checklist kiểm thử](test-checklist.md)
- [Nhật ký bug](bug-log.md)
- [Nhật ký kiểm thử](test-log.md)
- [Known issues](known-issues.md)
- [Câu hỏi đặc tả cần xác nhận](spec-questions.md)
- [Đánh giá QA/QC và wireframe](workstation-qa-assessment.md)
- [Backlog giao Developer](developer-backlog.md)
- [Roadmap cải tiến](workstation-roadmap.md)
- [Bàn giao khóa luận](evaluation/thesis_handoff.md)
