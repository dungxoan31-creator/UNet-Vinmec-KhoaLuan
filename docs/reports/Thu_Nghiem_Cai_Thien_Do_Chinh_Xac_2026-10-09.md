# Thử nghiệm cải thiện phân đoạn trên Validation — 09/10/2026

## Kết luận

`[VERIFIED]` U-Net++/ResNet34 nghiên cứu tái hiện Dice **0,817036** trên 541 ảnh Validation, khớp mốc khóa 0,8170359435 (sai khác < 1e-6). Trong 18 cấu hình ngưỡng/TTA đã thử, kết quả Dice cao nhất là **0,818512** với lật ngang khi suy luận và ngưỡng 0,40: tăng **0,001476** tuyệt đối. Mức tăng này thấp hơn ngưỡng quyết định **0,005** đã định trước. Giữ cấu hình U-Net++ nghiên cứu ở ngưỡng 0,5 và giữ Standard U-Net đang là mặc định của prototype; không chuyển ứng viên TTA vào mặc định.

Đây là mức khớp **phân đoạn** với mask tham chiếu được cung cấp, không phải độ chính xác chẩn đoán hoặc hiệu quả lâm sàng. Phân tích chỉ dùng Validation và không thực hiện suy luận trên Test trong lượt này.

## Dữ liệu và phép thử

- `[VERIFIED]` Split khóa: 661 Train / 541 Validation / 402 Test; `image_sha256` không giao giữa split. [Kiểm toán mới](../../evaluation/accuracy_2026-10-09/data_audit/dataset_audit.json) đọc và kiểm hash được cả **1.604/1.604** cặp ảnh–mask chuẩn, 0 lỗi chuẩn, 0 mask tham chiếu rỗng, 35 ảnh fallback lịch sử vẫn ngoài split.
- `[VERIFIED]` Có **2.047 tham chiếu đường dẫn tới bản sao nhãn nguồn cũ** chưa giải được tới tệp hiện có, thuộc 1.337 mẫu; đây là thiếu đường dẫn bản sao để truy vết, không phải 2.047 cặp chuẩn bị thiếu. [Danh sách đường dẫn thiếu](../../evaluation/accuracy_2026-10-09/data_audit/missing_source_paths.csv).
- `[VERIFIED]` Chạy U-Net++ khóa với preprocessing ảnh xám, Letterbox 512×512, CLAHE, chuẩn hóa mean 0,449/std 0,226 và AMP như Validation replay. Thử 9 ngưỡng từ 0,30 đến 0,70, bước 0,05, cho dự đoán gốc và trung bình xác suất sau flip TTA. Không thay mask hay checkpoint.
- Checkpoint SHA-256: `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76`; Validation CSV SHA-256: `d0296b00651bace33bca4a2c1c7f8c260eb6817e3bc624b77acc252b3f907f7b`; code khi chạy: `40d552f367d5ac6b3bea7333f1928556ecbd7a98`. [Toàn bộ 18 cấu hình](../../evaluation/accuracy_2026-10-09/candidates/summary.json) · [điểm từng ảnh](../../evaluation/accuracy_2026-10-09/candidates/per_image.csv).

| Cấu hình | Dice | IoU | Recall | Precision theo quy ước mới | Ảnh Dice < 0,5 |
|---|---:|---:|---:|---:|---:|
| Gốc, ngưỡng 0,50 | 0,817036 | 0,732287 | 0,834509 | 0,845230 | 45 |
| Gốc, ngưỡng 0,30 | 0,818221 | 0,733106 | 0,847886 | 0,834118 | 42 |
| Flip TTA, ngưỡng 0,40 | **0,818512** | 0,733784 | 0,853340 | 0,833479 | 50 |

Flip TTA/ngưỡng 0,40 cải thiện Dice ở 302 ảnh, giảm ở 233 ảnh, không đổi ở 6 ảnh. Nhóm thư mục nguồn `2d` (434 ảnh) tăng từ 0,820912 lên 0,823944; nhóm `3d` (107 ảnh) giảm từ 0,801313 xuống 0,796477. Tên thư mục `3d` không chứng minh ảnh là volume 3D. Theo tứ phân vị diện tích mask tham chiếu ở ảnh letterbox từ [Validation replay](../../evaluation/milestone_3_audit_2026-10-06/validation_replay_2026-10-07/validation_per_image.csv), Dice của nhóm nhỏ nhất (449–10.689 pixel; 135 ảnh) giảm nhẹ từ 0,712047 xuống 0,711799; nhóm lớn nhất (44.447–145.568 pixel; 136 ảnh) tăng từ 0,880152 lên 0,886478. Các nhóm này là phân tích mô tả sau phép chọn ứng viên, không phải bằng chứng tổng quát hóa độc lập.

### Quy ước Precision

Log huấn luyện/replay lịch sử ghi Precision 0,854472 tại ngưỡng 0,5; phép tính mới ghi 0,845230. Nguyên nhân đã truy được: **5 ảnh có mask tham chiếu dương nhưng mô hình dự đoán mask rỗng**. `ai_training.train_unetplusplus_resnet34.batch_metrics` cho Precision = 1 khi không có pixel dự đoán; `ai_training.metrics_clinical.compute_sample_clinical_metrics` cho Precision = 0 với ca có tổn thương bị bỏ sót hoàn toàn. Chênh lệch đúng 5/541 ≈ 0,009242. Dice, IoU và Recall của cấu hình gốc khớp log cũ. Không sửa log lịch sử; mọi Precision trong bảng trên dùng cùng quy ước mới.

## Giới hạn và bước tiếp theo

- `[PARTIALLY VERIFIED]` Workbook có mã Patient/Case tách biệt giữa split theo chuỗi mã, nhưng chưa có xác nhận từ đơn vị dữ liệu rằng mã ổn định cho cùng người bệnh/ca. Không gọi kết quả này là đánh giá độc lập cấp bệnh nhân.
- `[PARTIALLY VERIFIED]` Trạng thái chuyên gia duyệt từng mask chưa có hồ sơ gắn phiên bản. Không gọi mask tham chiếu là ground truth lâm sàng đã duyệt.
- Test 402 ảnh đã được dùng trước lượt này; giữ nguyên và không dùng để chọn cấu hình. Muốn ước lượng cuối cùng cần cohort bệnh nhân mới, chưa từng dùng để chọn mô hình/ngưỡng.
- Với mức tăng chỉ 0,001476 và kết quả không đồng đều theo nhóm nguồn, ưu tiên xác nhận Patient/Case ID, kiểm duyệt nhãn và ca lỗi trước khi tăng ngân sách huấn luyện hoặc chuyển mô hình vào prototype. Nếu nguồn được xác nhận, chạy lại đánh giá theo bệnh nhân và thử thêm seed/augmentation theo giao thức khóa.
