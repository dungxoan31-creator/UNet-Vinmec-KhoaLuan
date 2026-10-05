# Model Card: Ovarian Ultrasound Segmentation Prototype

## Mô tả

- **Mục tiêu:** tạo mask nhị phân cho vùng nghi ngờ tổn thương trên ảnh siêu âm buồng trứng 2D, để người dùng rà soát và chỉnh sửa trong prototype HITL.
- **Kiến trúc:** Standard U-Net, một kênh đầu vào, một kênh đầu ra.
- **Checkpoint tích hợp hiện hành:** `checkpoints/baseline_unet_best.pth`.
- **SHA-256:** `5e14be07240966f74de91d3467edbf88a08ca07b6577081787c6abd6dede494e`.
- **Ngưỡng:** 0.5.
- **Tiền xử lý:** grayscale, CLAHE, Letterbox 512×512, chuẩn hóa cường độ theo 255; cấu hình suy luận được ghi tại `evaluation/selected_model.json`.
- **Nguồn chọn checkpoint:** Validation 123 ảnh của lượt huấn luyện riêng; không chọn lại bằng Validation Mốc 1.

## Bằng chứng định lượng và phạm vi

Checkpoint được huấn luyện bằng split riêng 697/123/382. Kết quả dưới đây là segmentation metrics của Test 382 ảnh thuộc split đó, lấy từ `evaluation/retrain_2d_2026-10-03/test_summary.json`:

| Nhóm đo | Dice | IoU | Precision | Recall | Specificity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Test set, 382 ảnh (mean per image) | 0.8094 | 0.7160 | 0.8111 | 0.8665 | — |
| Pixel nền trên toàn bộ Test | — | — | — | — | 0.9716 |

Các giá trị này đo mức trùng khớp phân đoạn pixel; không đại diện cho Diagnostic Accuracy. Test của lượt huấn luyện này đã được truy cập trong các đánh giá trước đó, do đó không được mô tả là lần đánh giá mù đầu tiên. Danh tính bệnh nhân nguồn và patient-level independence chưa được xác minh.

Checkpoint được tích hợp và sanity-check trên 46 ảnh Validation Mốc 1 với nạp `strict=True`; phép này kiểm tra nạp trọng số và đường suy luận, không tính segmentation metrics mới. Mốc 2 không huấn luyện checkpoint này trên bộ Mốc 1.

## Bộ dữ liệu Mốc 1

Bộ tham chiếu Mốc 1 gồm 307 ảnh, chia Train 215, Validation 46, Test 46. Có 185 mã nhóm ẩn danh; không có mapping đã xác thực về bệnh nhân nguồn. Vì vậy, chỉ xác nhận được tính rời nhau của mã nhóm được ghi nhận, không khẳng định patient-level split.

Trong 307 bản ghi có 35 mask rỗng dẫn xuất với provenance tại `dataset/vinmec_ovarian/empty_masks/PROVENANCE.json`. Các mask này là fallback artifacts để kiểm thử pipeline, không phải Ground Truth âm tính lâm sàng; nhãn nguồn tương ứng có pixel dương. Không dùng các mask dẫn xuất này làm nhãn cho metric y tế.

## Giới hạn sử dụng

- Prototype hỗ trợ phân đoạn và rà soát ảnh; không phân loại bệnh học, không đưa chẩn đoán và không thay quyết định của chuyên viên y tế.
- Không suy ra mm hoặc thể tích nếu thiếu pixel spacing đã hiệu chuẩn từ nguồn.
- Hiệu năng trên một split không chứng minh khả năng tổng quát hóa sang cơ sở, máy siêu âm hoặc quần thể khác.
- Kết quả của checkpoint này không được gộp với metric lịch sử Mốc 1.

## Tài liệu nguồn

- Cấu hình và SHA: `evaluation/selected_model.json`
- Test summary: `evaluation/retrain_2d_2026-10-03/test_summary.json`
- Split Mốc 1 và kiểm toán: `ai_training/splits/archive_milestone_1/`, `evaluation/milestone_2_m1_scope/data_audit_2026-10-04.json`
- Báo cáo tiến độ: `docs/reports/Bao_Cao_Tien_Do_Moc_2_NguyenHuuDung_2026-10-03.md`
