# BÁO CÁO TIẾN ĐỘ KHÓA LUẬN TỐT NGHIỆP — MỐC 2

**Giai đoạn:** 21/09/2026 – 05/10/2026  
**Đề tài:** Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop  
**Sinh viên:** Nguyễn Hữu Dũng — **MSV:** 11235559  
**Giảng viên hướng dẫn:** ThS. Trần Thanh Hải

Kính gửi Thầy,

Em xin báo cáo ngắn tiến độ Mốc 2. Trọng tâm giai đoạn này là khóa cấu hình U-Net tích hợp, hoàn thiện luồng Web Prototype và chức năng chuyên viên rà soát/chỉnh sửa mask. Bộ dữ liệu Mốc 1 được giữ nguyên làm tham chiếu; Mốc 2 không chia lại bộ 307 ảnh và không thực hiện đánh giá mới trên Test Mốc 1.

## 1. Công việc hoàn thành

| Nhiệm vụ | Kết quả |
| --- | --- |
| Đánh giá và lựa chọn U-Net | Chọn checkpoint Standard U-Net `5e14be…` (SHA-256 đầy đủ trong `evaluation/selected_model.json`) làm mô hình tích hợp. Checkpoint được chọn theo Validation của split huấn luyện riêng; không tinh chỉnh trên bộ 307 ảnh Mốc 1. |
| Khảo sát kiến trúc cải tiến | Chưa triển khai kiến trúc thứ hai trong Mốc 2; ưu tiên hoàn thiện và kiểm tra luồng lõi với Standard U-Net. Có thể xem xét ở Mốc 3 nếu dữ liệu và thời gian cho phép. |
| Web Prototype | Hoàn thiện luồng `Upload → Segmentation → Original/Mask/Overlay → Review/Edit → Confirm/Save`; backend FastAPI/PyTorch, giao diện HTML/Canvas. |
| Human-in-the-Loop | Có Brush, Eraser, chỉnh kích thước nét, Undo/Redo và lưu mask sau rà soát. Thao tác Confirm ghi nhận review trong prototype, không tự xác nhận mask thành Ground Truth chuyên môn. |

## 2. Dataset, pipeline và kết quả

Bộ tham chiếu Mốc 1 gồm **307 ảnh: 215 Train / 46 Validation / 46 Test** (`ai_training/splits/archive_milestone_1/`). Mốc 2 không huấn luyện lại trên bộ này; tập Test 46 ảnh tiếp tục được giữ nguyên và không dùng để chọn checkpoint hoặc ngưỡng.

Checkpoint tích hợp được huấn luyện 30 epoch trên split riêng **697 Train / 123 Validation / 382 Test**, với Standard U-Net, Combo Loss (0,5 BCE + 0,5 Dice), ảnh grayscale, CLAHE và Letterbox 512×512. Ngưỡng 0,5; checkpoint tốt nhất tại epoch 27. Kết quả theo Validation của lượt huấn luyện này: **Dice 0,8233** (`evaluation/selected_model.json`).

| Phép đo trên Test 382 ảnh của split riêng | Kết quả |
| --- | ---: |
| Dice trung bình từng ảnh | 0,8094 |
| IoU trung bình từng ảnh | 0,7160 |
| Precision trung bình từng ảnh | 0,8111 |
| Recall trung bình từng ảnh | 0,8665 |
| Specificity của pixel nền | 0,9716 |

Nguồn: `evaluation/retrain_2d_2026-10-03/test_summary.json`. Đây là **Segmentation Metrics**, không phải Diagnostic Accuracy. Các số liệu này thuộc split huấn luyện riêng, không phải kết quả của bộ Mốc 1. Báo cáo đánh giá ghi nhận danh tính bệnh nhân nguồn chưa được xác minh và Test của lượt huấn luyện này từng được truy cập trong đánh giá checkpoint trước đó; vì vậy không diễn giải là đánh giá mù hoặc độc lập cấp bệnh nhân.

Kiểm tra suy luận trên 46 ảnh Validation Mốc 1 nạp checkpoint thành công với `strict=True`, không thiếu/thừa key (`evaluation/m1_validation_sanity_check.json`). Median forward pass là **30,26 ms**; median tiền xử lý cộng forward là **46,04 ms**. Phép đo API trên Validation Mốc 1 có **5 quan sát**, median **176,69 ms**, p95 **185,76 ms** (`evaluation/milestone_2_m1_scope/api_latency_validation_2026-10-04.json`). Cỡ mẫu nhỏ nên chỉ mang tính mô tả, chưa đại diện cho tải thực tế.

## 3. Minh chứng và rủi ro

- Automated tests: **61 passed, 0 failed**. Ruff: **All checks passed**. API khởi động, trả trạng thái healthy và nạp đúng checkpoint SHA `5e14be…494e`.
- Browser smoke log ngày 04/10 ghi PASS cho kịch bản một ảnh Validation, gồm suy luận, các chế độ xem, Brush/Eraser, Undo, lưu và mở lại ca (`evaluation/milestone_2_m1_scope/browser_smoke_2026-10-04.json`). Trong lượt rà soát hiện tại chưa chạy lại browser test vì môi trường thiếu Playwright.
- Mốc 1 có 185 mã nhóm ẩn danh rời nhau trong các split; chưa có mapping xác thực tới PID bệnh viện, nên chưa thể kết luận patient-level independence. Có 35 mask rỗng dẫn xuất; không xem là nhãn âm tính lâm sàng và không dùng để tính metric y tế. File provenance được dẫn trong tài liệu cũ hiện không có tại đường dẫn đã ghi, cần khôi phục hoặc xác minh trước khi sử dụng.
- Chưa hoàn tất so sánh kiến trúc thứ hai hoặc đánh giá usability với chuyên viên y tế.

## 4. Kế hoạch tiếp theo — Mốc 3 (06/10–18/10/2026)

1. Xác minh nguồn Ground Truth và provenance mask trước khi tính metric bổ sung; giữ nguyên lịch sử sử dụng Test và không gọi lần đánh giá tiếp theo là “mù” nếu dữ liệu đã được truy cập.
2. Kiểm tra lại E2E trên browser khi có Playwright; lưu ảnh prediction/overlay và log thao tác HITL.
3. Phân tích các ca phân đoạn tốt và lỗi lớn bằng ảnh gốc, mask tham chiếu và mask dự đoán; chỉ mô tả “vùng nghi ngờ tổn thương được phân đoạn”, không tự gán nhãn bệnh học.
4. Nếu tiếp cận được chuyên viên, ghi nhận thời gian thao tác và phản hồi về tính hữu dụng của Brush/Eraser và quy trình Confirm/Save.

Kính báo cáo Thầy.

**Nguyễn Hữu Dũng**  
MSV: 11235559
