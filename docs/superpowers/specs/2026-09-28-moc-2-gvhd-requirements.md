# Yêu cầu Mốc 2 từ phản hồi của GVHD

Nguồn: nội dung hai email của ThS. Trần Thanh Hải do sinh viên cung cấp trong cuộc trao đổi ngày 28/09/2026. Tài liệu này ghi lại yêu cầu để lập kế hoạch; chưa xác minh email độc lập.

## Phạm vi và lịch

- Đề tài: “Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop.”
- Luồng cốt lõi: ảnh siêu âm → preprocessing → segmentation → mask/overlay → bác sĩ review/edit/confirm → đánh giá kết quả.
- Mốc 2, 21/09–05/10: đánh giá và tinh chỉnh U-Net; thử kiến trúc cải tiến nếu phù hợp; chọn mô hình cho prototype; xây Web Prototype với Upload → Segmentation → Original/Mask/Overlay → Review/Edit → Confirm.
- Mốc 3, 06/10–18/10: sau khi khóa mô hình cuối, đánh giá định lượng trên Test Set độc lập, phân tích ca tốt/xấu và kiểm thử HITL; đánh giá với bác sĩ nếu tiếp cận được.
- Từ 19/10: hoàn thiện báo cáo khóa luận và chuẩn bị bảo vệ. LLM/VLM, sinh chẩn đoán, báo cáo gợi ý và dashboard mở rộng chỉ xem xét khi phạm vi cốt lõi đã hoàn thành tốt.

## Kỷ luật dữ liệu và diễn giải

- Từ Mốc 2, đóng băng Test Set. Tuning, lựa chọn mô hình, threshold, loss và hyperparameter chỉ dựa trên Train/Validation. Chỉ dùng lại Test sau khi đã chốt mô hình cuối, ở Mốc 3.
- Diễn đạt split là “loại bỏ việc trùng bệnh nhân giữa các tập và giảm nguy cơ data leakage”; không viết “loại bỏ 100% nguy cơ data leakage”.
- Báo cáo riêng nhóm có lesion và Empty Mask. Không gộp một Dice/IoU trung bình khi cách xử lý Empty Mask có thể làm sai lệch kết quả.
- Dice, IoU, Recall, Precision, Specificity là chỉ số phân đoạn; không diễn giải thành độ chính xác chẩn đoán.
- Chỉ nhận định loại tổn thương khi có metadata hoặc xác nhận bác sĩ.

## Bàn giao

- Sau mỗi mốc, gửi báo cáo tiến độ ngắn gồm việc đã hoàn thành, minh chứng, rủi ro và bước xử lý tiếp theo.
- Ưu tiên source code, kết quả training, segmentation metrics, ảnh prediction/overlay và prototype chạy được.
- Gửi lại link GitHub Mốc 1 cho GVHD và cập nhật source/code, kết quả các mốc sau lên repository để theo dõi. Việc gửi email thực tế do sinh viên thực hiện hoặc cần chỉ thị gửi rõ ràng.
