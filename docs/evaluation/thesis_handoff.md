# Bàn giao khóa luận — trạng thái kỹ thuật hiện tại

Hệ thống là prototype nghiên cứu hỗ trợ phân đoạn và rà soát HITL. Bằng chứng kỹ thuật trong repository không thay cho xác nhận lâm sàng.

## Những gì có thể kết luận

- Mô hình đang được chọn là U-Net++/ResNet34; cấu hình/checkpoint được dẫn trong [`MODEL_CARD.md`](../../MODEL_CARD.md).
- Bộ kiểm thử phải chạy bằng dữ liệu tổng hợp và database cô lập.
- Thao tác chỉnh sửa mask, kết quả lưu, revision và người rà soát cần được kiểm chứng qua API/database, không chỉ dựa vào giao diện.

## Những gì chưa thể kết luận

- Kết quả hiện tại **không đủ để khẳng định hệ thống sẵn sàng cho Supervised Pilot** hoặc sử dụng trong chăm sóc bệnh nhân.
- **Cổng đánh giá độc lập vẫn `BLOCKED`**; Patient ID nguồn và độc lập cấp bệnh nhân chưa được xác minh.
- Chưa có đánh giá người dùng lâm sàng.
- Điểm pixel-level không đồng nghĩa với độ nhạy chẩn đoán hoặc khả năng phân loại lành/ác.
- Bất kỳ số liệu nào được ghi trong tài liệu lịch sử cần đối chiếu lại nguồn artifact trước khi trích dẫn như kết quả đã xác minh.

## Hồ sơ bàn giao

- Kế hoạch và checklist QA: [`../qa-workstation-overhaul-plan.md`](../qa-workstation-overhaul-plan.md), [`../test-checklist.md`](../test-checklist.md)
- Log kiểm thử: [`../test-log.md`](../test-log.md)
- Rủi ro còn mở: [`../known-issues.md`](../known-issues.md)
- Câu hỏi cần chủ sản phẩm/chuyên gia y tế xác nhận: [`../spec-questions.md`](../spec-questions.md)
- Đánh giá QA, backlog và roadmap: [`../workstation-qa-assessment.md`](../workstation-qa-assessment.md), [`../developer-backlog.md`](../developer-backlog.md), [`../workstation-roadmap.md`](../workstation-roadmap.md)
- Prompt QA/QC theo codebase: [`../prompts/qa-workstation-codebase-prompt.md`](../prompts/qa-workstation-codebase-prompt.md)
