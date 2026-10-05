# Thử nghiệm cải thiện U-Net trên ảnh Vinmec 2D

## Thiết lập

- [VERIFIED] Checkpoint gốc `checkpoints/full_unet_final.pth` học trên 1.372 cặp ảnh–mask trong `dataset/`: 1.202 ảnh 2D và 170 ảnh CEUS.
- [VERIFIED] Checkpoint thử nghiệm `checkpoints/finetune_2d/finetune_2d_final.pth` khởi tạo từ checkpoint gốc, sau đó học thêm 3 epoch trên cả 1.202 ảnh 2D; AdamW, learning rate `1e-4`, batch 2, loss `0.5 BCE + 0.5 Soft Dice`, letterbox 512×512 và CLAHE theo pipeline hiện có. Checkpoint gốc được giữ nguyên.
- [VERIFIED] So sánh trên cùng 267 ảnh–mask Vinmec không trùng pixel xám giải mã với 1.372 ảnh train, cùng tiền xử lý và ngưỡng 0,5. Đây là dữ liệu **cùng nguồn**, đã được dùng để phân tích lỗi và chọn hướng tinh chỉnh.

## Kết quả trên 267 ảnh

| Chỉ số | Checkpoint gốc | Tinh chỉnh 2D | Thay đổi |
| --- | ---: | ---: | ---: |
| Dice trung bình | 0,5254 | 0,5479 | +0,0225 |
| IoU trung bình | 0,4025 | 0,4233 | +0,0208 |
| Precision trung bình | 0,4914 | 0,5241 | +0,0327 |
| Recall trung bình | 0,7144 | 0,7108 | −0,0036 |
| Dice ở 66 mask nhỏ nhất theo diện tích pixel | 0,3410 | 0,3627 | +0,0217 |

Dice tăng ở 173 ảnh, giảm ở 90 ảnh và bằng nhau ở 4 ảnh. Số pixel dương tính giả giảm từ 4.650.867 xuống 3.926.929; pixel âm tính giả tăng từ 1.203.038 lên 1.235.448. Thử ngưỡng 0,7 trên checkpoint gốc làm Dice giảm nhẹ xuống 0,5241 và recall giảm còn 0,6305, nên checkpoint tinh chỉnh dùng ngưỡng 0,5.

## Giới hạn sử dụng

- [PARTIALLY VERIFIED] Không có Patient ID để loại trừ trùng bệnh nhân; 267 ảnh này không phải kiểm định độc lập theo bệnh nhân hoặc trung tâm. Vì đã xem kết quả tập này để chọn cách cải thiện, mức tăng Dice là **kết quả phát triển mang tính thăm dò**, không phải ước lượng hiệu năng lâm sàng cuối cùng.
- [VERIFIED] Toàn bộ 267 mask đều có vùng đích, nên không đo được tỷ lệ dương tính giả ở ca mask rỗng.
- [VERIFIED] Năm ảnh có Dice thấp nhất của checkpoint mới gồm `129.JPG`, `1384.JPG`, `258.JPG`, `509.JPG` và `621.JPG`; vẫn cần rà soát HITL.
- Cần khóa checkpoint và ngưỡng trước khi đánh giá trên dữ liệu từ cơ sở khác, có mã bệnh nhân và cả ca mask rỗng.

Checkpoint SHA-256: `5d02327dbe65a84e435a41321f1349a0e4301a956a15b3cced1177799d2859f6`.

Nguồn ảnh được đánh giá: Tập dữ liệu nghiên cứu Vinmec.
