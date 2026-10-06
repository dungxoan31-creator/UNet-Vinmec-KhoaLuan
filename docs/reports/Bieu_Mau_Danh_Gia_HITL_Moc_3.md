# Biểu mẫu đánh giá luồng Human-in-the-Loop — Mốc 3

Biểu mẫu này dành cho người đánh giá chuyên môn thực tế. Không điền thay người tham gia. Không ghi thông tin định danh bệnh nhân; sử dụng mã ca nghiên cứu đã được phê duyệt.

## Thông tin phiên đánh giá

- Mã người đánh giá (ẩn danh): ____________________
- Vai trò/chuyên môn: ____________________
- Ngày đánh giá: ____________________
- Mã phiên: ____________________
- Thiết bị / trình duyệt: ____________________
- Đã giải thích mục đích và được người tham gia đồng ý: Có / Không
- Mã phiên bản prototype: ____________________
- SHA-256 checkpoint: ____________________
- CSV/manifest và SHA-256 của tập ca được phép dùng: ____________________
- Tổng số ca được thực hiện / chưa hoàn tất: ____________________

Với mỗi ca, ghi rõ **Accept nguyên trạng / Chỉnh sửa rồi Accept / Reject**, lý do, thời điểm bắt đầu–kết thúc, số thao tác Brush/Eraser/Undo/Redo và có cần trợ giúp hay không. Ghi riêng thời gian xem kết quả và thời gian chỉnh sửa. Chỉ tổng hợp sau khi có phiếu thực tế; mẫu trống không phải kết quả đánh giá.

## Kịch bản thao tác

Với mỗi ca đã được phê duyệt để thử nghiệm, ghi thời gian từ lúc bắt đầu tác vụ đến khi lưu/xác nhận. Không dùng kết quả prototype làm chẩn đoán.

| # | Tác vụ | Hoàn tất (Có/Không) | Thời gian (giây) | Brush/Eraser thao tác | Cần trợ giúp (Có/Không) | Ghi chú |
|---:|---|---|---:|---:|---|---|
| 1 | Tải ảnh và mở kết quả phân đoạn | | | | | |
| 2 | Chuyển đổi Original / Mask / Overlay | | | | | |
| 3 | Dùng Brush để chỉnh vùng thiếu theo nhận định người đánh giá | | | | | |
| 4 | Dùng Eraser để loại vùng không phù hợp theo nhận định người đánh giá | | | | | |
| 5 | Dùng Undo/Redo hoặc Reset khi cần | | | | | |
| 6 | Review, lưu và mở lại phiên đã lưu | | | | | |

## Đánh giá sau phiên

Chấm từ **1 (rất khó/không đồng ý)** đến **5 (rất dễ/đồng ý)**.

| Câu hỏi | Điểm 1–5 | Ghi chú |
|---|---:|---|
| Thao tác điều hướng và xem lớp phủ dễ hiểu | | |
| Brush/Eraser có thể kiểm soát được | | |
| Phản hồi giao diện đủ rõ khi thao tác/lưu | | |
| Quy trình Review và Confirm phù hợp với cách làm việc dự kiến | | |
| Prototype hữu ích như công cụ hỗ trợ rà soát phân đoạn | | |

- Số lần chỉnh sửa mask: __________
- Vấn đề gây chậm hoặc nhầm lẫn: __________________________________________
- Điểm cần cải thiện ưu tiên: ______________________________________________
- Nhận xét tự do: _________________________________________________________

## Ghi chú phân tích

Thời gian và điểm Likert là đánh giá trải nghiệm prototype trong phiên thử nghiệm, không phải chỉ số hiệu năng chẩn đoán. Việc người đánh giá chỉnh sửa/lưu mask không tự biến mask đó thành ground truth được phê duyệt. Mọi ground truth dùng cho nghiên cứu cần quy trình chuyên môn và nguồn gốc riêng.

**Người đánh giá xác nhận nội dung ghi nhận:** ____________________  
**Ngày:** ____________________
