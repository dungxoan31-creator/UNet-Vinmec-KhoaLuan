# Đánh giá bổ sung trên ảnh Vinmec chưa dùng để huấn luyện

## Nguồn và phạm vi

- [VERIFIED] Nguồn: Vinmec 2D, bản biên tập gồm 1.469 cặp ảnh–mask. MD5 archive: `74936e6e2f466c158fb0573956a54522`.
- [VERIFIED] Bộ huấn luyện của lượt này gồm 820 ảnh `Vinmec 2D/train`, 382 ảnh `Vinmec 2D/test` và 170 ảnh `Vinmec CEUS`; checkpoint SHA-256: `06238d8d87d35e70d510314a3019a8ee2b325dc56662bf0fb57c4726ca6a9bdb`.
- [VERIFIED] Sau khi so SHA-256 của pixel xám đã giải mã, 1.202/1.469 ảnh 2D tổng thể trùng ảnh đã train; 267 ảnh còn lại chưa xuất hiện nguyên dạng trong train. Mask của cả 1.202 ảnh trùng khớp sau nhị phân hóa.
- [PARTIALLY VERIFIED] Không có Patient ID đáng tin cậy để loại trừ cùng bệnh nhân, ảnh gần trùng hoặc cùng phiên siêu âm. Đây là đánh giá **mức ảnh trong cùng nguồn Vinmec**, không phải kiểm định ngoài trung tâm.

## Cách đo

Standard U-Net với checkpoint `full_unet_final.pth`; ảnh xám → letterbox 512×512 → CLAHE → chuẩn hóa [0,1] → ngưỡng xác suất 0,5 → trả mask về kích thước gốc. So với mask nhị phân trên ảnh gốc. Không tinh chỉnh checkpoint hoặc ngưỡng bằng 267 ảnh này.

## Kết quả trên 267 ảnh có mask không rỗng

| Chỉ số phân đoạn | Giá trị |
| --- | ---: |
| Dice trung bình ± độ lệch chuẩn | 0,5254 ± 0,2711 |
| Dice trung vị (Q1–Q3) | 0,5685 (0,3113–0,7608) |
| IoU trung bình ± độ lệch chuẩn | 0,4025 ± 0,2546 |
| Recall trung bình | 0,7144 |
| Precision trung bình | 0,4914 |
| Ảnh có Dice < 0,5 | 116/267 |
| Ảnh có Dice = 0 | 5/267 |
| Specificity trên mask rỗng | Không có dữ liệu |

Theo phân vị diện tích mask gốc, Dice trung bình lần lượt là 0,3452 / 0,4125 / 0,6221 / 0,7233 từ nhóm nhỏ nhất đến lớn nhất. Đây là phân tích theo số pixel của ảnh có kích thước khác nhau, không phải kích thước tổn thương theo mm. Precision thấp hơn recall và số pixel dương tính giả lớn hơn dương tính đúng cho thấy xu hướng khoanh dư trong tập này; năm ảnh Dice bằng 0 cần xem lại trực quan.

## Diễn giải và bước tiếp theo

Kết quả chưa đủ để khẳng định hiệu năng lâm sàng. Tập đánh giá cùng nguồn với train, chưa kiểm được trùng bệnh nhân và không có ca mask rỗng để đo dương tính giả trên nhóm không có vùng đích. Nên thu thập một tập ảnh–mask từ cơ sở khác, có Patient ID hoặc mã ca kiểm soát trùng lặp, và có cả ca mask rỗng; khóa checkpoint/ngưỡng trước khi đánh giá. Theo [bài báo OvAi Focus](https://www.medrxiv.org/content/10.64898/2026.07.24.26358148v1.full), dữ liệu đa trung tâm của họ hiện không công khai.

Dữ liệu chi tiết: `external_vinmec_per_image.csv`; tổng hợp máy đọc được: `external_vinmec_summary.json`. Dữ liệu được chuẩn hóa và quản lý nội bộ theo tiêu chuẩn dữ liệu nghiên cứu Vinmec.
