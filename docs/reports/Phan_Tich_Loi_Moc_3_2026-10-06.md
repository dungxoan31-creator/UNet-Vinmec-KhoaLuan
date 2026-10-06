# Phân tích lỗi Mốc 3 — 06/10/2026

Phân tích dưới đây dùng các kết quả trong [`test_summary.json`](../../evaluation/milestone_3_2026-10-06/test_summary.json). Checkpoint được đánh giá có SHA-256 `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`, threshold 0,5. Mỗi panel hiển thị ảnh đầu vào, mask tham chiếu, dự đoán và vùng sai khác. FP/FN là số pixel, không phải số ca lâm sàng.

## Ca có Dice cao nhất

| Ảnh | Dice | Recall | Precision | FP | FN | Panel |
|---|---:|---:|---:|---:|---:|---|
| `159.JPG` | 0,9754 | 0,9844 | 0,9666 | 749 | 343 | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/best_01_dice_0.975.png) |
| `614.JPG` | 0,9748 | 0,9763 | 0,9733 | 677 | 597 | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/best_02_dice_0.975.png) |
| `177.JPG` | 0,9743 | 0,9619 | 0,9870 | 722 | 2.179 | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/best_03_dice_0.974.png) |
| `1367.JPG` | 0,9737 | 0,9723 | 0,9751 | 952 | 1.063 | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/best_04_dice_0.974.png) |
| `1200.JPG` | 0,9730 | 0,9952 | 0,9519 | 950 | 91 | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/best_05_dice_0.973.png) |

Trong các ca này, phần lớn foreground dự đoán chồng lấp tốt với mask tham chiếu. Sai khác còn lại chủ yếu là các dải pixel rìa và một số vùng nhỏ bị thêm hoặc bỏ. Đây là nhận xét hình học về mặt nạ; không suy ra loại tổn thương hay ý nghĩa chẩn đoán.

## Ca có tổng FP + FN lớn

| Ảnh | Dice | Recall | Precision | FP | FN | Nhận xét từ pixel | Panel |
|---|---:|---:|---:|---:|---:|---|---|
| `904.JPG` | 0,0241 | 0,0122 | 1,0000 | 0 | 96.595 | Bỏ sót phần lớn vùng foreground tham chiếu; dự đoán chỉ chiếm phần rất nhỏ | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/fp_fn_errors_01_dice_0.024.png) |
| `326.JPG` | 0,0464 | 0,0290 | 0,1158 | 16.027 | 70.250 | Bỏ sót nhiều pixel, đồng thời có vùng dương tính dự đoán ngoài mask tham chiếu | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/fp_fn_errors_02_dice_0.046.png) |
| `998.JPG` | 0,0059 | 0,0031 | 0,0661 | 3.108 | 71.076 | Gần như bỏ sót vùng foreground tham chiếu; còn một số vùng dự đoán rời rạc | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/fp_fn_errors_03_dice_0.006.png) |
| `560.JPG` | 0,3294 | 0,2041 | 0,8533 | 2.735 | 62.024 | Precision tương đối cao nhưng độ bao phủ thấp; phần lớn FN | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/fp_fn_errors_04_dice_0.329.png) |
| `1460.JPG` | 0,2639 | 0,2088 | 0,3585 | 18.909 | 40.045 | Có cả vùng bỏ sót đáng kể và pixel dự đoán ngoài mask tham chiếu | [Xem](../../evaluation/milestone_3_2026-10-06/error_analysis/fp_fn_errors_05_dice_0.264.png) |

Các trường hợp này gợi ý ưu tiên rà soát lỗi under-segmentation và sai khác vị trí/kích thước mask. Chỉ từ ảnh, mask và dự đoán hiện có chưa thể xác định nguyên nhân là chất lượng ảnh, quy ước gán nhãn, tiền xử lý hay đặc tính dữ liệu. Cần chuyên viên rà soát các vùng nghi ngờ và xác nhận chất lượng nhãn trước khi đưa ra diễn giải sâu hơn.

## Liên kết dữ liệu từng ca

Đường dẫn ảnh, mask tham chiếu và mask dự đoán cho toàn bộ 402 mẫu có trong [`test_per_image.csv`](../../evaluation/milestone_3_2026-10-06/test_per_image.csv). Ví dụ các ca trong bảng trên nằm dưới `dataset/Vinmec/Vinmec_2d/images/` và `dataset/Vinmec/Vinmec_2d/annotations/`; prediction tương ứng được lưu trong `evaluation/milestone_3_2026-10-06/predictions/` theo SHA-256 ảnh.
