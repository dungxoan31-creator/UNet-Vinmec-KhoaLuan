# TRƯỜNG ĐẠI HỌC KINH TẾ QUỐC DÂN
## TRƯỜNG CÔNG NGHỆ VÀ KINH TẾ SỐ

# BÁO CÁO TIẾN ĐỘ THỰC HIỆN KHÓA LUẬN TỐT NGHIỆP
## CỘT MỐC 1: DỮ LIỆU, TIỀN XỬ LÝ VÀ MÔ HÌNH PHÂN ĐOẠN CƠ SỞ
*Thời gian thực hiện: Từ ngày 06/09/2026 đến ngày 20/09/2026*

* **Tên đề tài:** Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop.
* **Sinh viên thực hiện:** Nguyễn Hữu Dũng (Mã sinh viên: 11235559).
* **Lớp chuyên ngành:** Hệ thống Thông tin Quản lý 65A (HTTTQL 65A).
* **Giảng viên hướng dẫn:** ThS. Trần Thanh Hải.
* **Ngày lập báo cáo:** 17/09/2026.

---

Kính gửi: ThS. Trần Thanh Hải,

Theo đề cương nghiên cứu đã được Thầy thông qua với phạm vi trọng tâm:
> **Ảnh siêu âm -> Tiền xử lý -> Phân đoạn tổn thương -> Lớp phủ mặt nạ -> Bác sĩ đánh giá và chỉnh sửa -> Đánh giá kết quả**

Em xin gửi Thầy báo cáo chi tiết về kết quả thực hiện Cột mốc 1 trong giai đoạn từ ngày 06/09/2026 đến ngày 20/09/2026. Nội dung báo cáo bao gồm việc hoàn thành rà soát tập dữ liệu lâm sàng thu nhận tại Bệnh viện Đa khoa Quốc tế Vinmec Times City, thiết lập chuỗi tiền xử lý ảnh y tế, xây dựng bộ nạp dữ liệu và kịch bản kiểm thử tự động, huấn luyện mô hình Standard U-Net cơ sở trên phần cứng thực tế và đánh giá định lượng độc lập trên tập kiểm thử 46 ca.

---

### I. CÁC HẠNG MỤC CÔNG VIỆC ĐÃ HOÀN THÀNH

Trong Cột mốc 1, toàn bộ sáu nhiệm vụ kỹ thuật đã được triển khai tuần tự theo kế hoạch và hoàn tất việc kiểm tra thực nghiệm trên hệ thống:

#### Bảng 1. Danh mục các nhiệm vụ kỹ thuật đã hoàn thành trong Cột mốc 1

| STT | Nhiệm vụ kỹ thuật | Nội dung triển khai | Tệp mã nguồn và dữ liệu liên quan | Kết quả |
| :---: | :--- | :--- | :--- | :---: |
| 1 | Khảo sát và đóng băng dữ liệu Ground Truth | Rà soát kho 1.387 ảnh thô từ BVĐKQT Vinmec Times City; chốt danh mục 307 ảnh Ground Truth từ 185 bệnh nhân; xác định 35 ca mask rỗng (11,4%) phục vụ kiểm chứng âm tính. | `dataset/vinmec_ovarian/vinmec_dataset_manifest.json`<br>`dataset/vinmec_ovarian/metadata/kltn_ground_truth_307.csv` | Đã đóng băng |
| 2 | Phân chia dữ liệu theo cấp bệnh nhân (Patient-Level Split) | Cài đặt thuật toán phân tầng theo mã bệnh nhân; kiểm định loại trừ 100% việc trùng lặp bệnh nhân giữa ba tập; tỷ lệ phân chia Train (215 ảnh), Val (46 ảnh) và Test (46 ảnh). | `scripts/prepare_splits.py`<br>`ai_training/splits/train.csv`<br>`ai_training/splits/val.csv`<br>`ai_training/splits/test.csv` | Không rò rỉ dữ liệu |
| 3 | Xây dựng pipeline tiền xử lý chuẩn y tế (Medical Preprocessor) | Cắt vùng quạt quét siêu âm (ROI Fan-beam); kỹ thuật Letterbox kích thước 512x512 giữ nguyên tỷ lệ hình thái; bảo toàn nhãn nhị phân {0, 1} bằng phép nội suy lân cận gần nhất; lập trình hàm khôi phục tọa độ gốc `inverse_letterbox_mask`. | `backend/services/preprocessor.py`<br>`tests/test_milestone_1_audit.py` | Đạt kiểm thử |
| 4 | Xây dựng PyTorch DataLoader và bộ kiểm thử tự động | Xây dựng lớp nạp dữ liệu kèm tăng cường hình ảnh an toàn trên tập huấn luyện; cài đặt các hàm đo lường chỉ số lâm sàng; xây dựng bộ kiểm thử 16 tiêu chí tự động. | `ai_training/dataset_loader.py`<br>`ai_training/metrics_clinical.py`<br>`tests/test_milestone_1_audit.py` | 16/16 bài kiểm thử đạt (7,31s) |
| 5 | Huấn luyện mô hình Standard U-Net cơ sở | Huấn luyện kiến trúc U-Net 7,76 triệu tham số trên GPU NVIDIA RTX 3050; sử dụng Combo Loss kết hợp BCE và Soft Dice; áp dụng bộ tối ưu AdamW cùng lịch học Cosine Annealing; lưu checkpoint tại epoch 12. | `backend/models/unet.py`<br>`ai_training/train_baseline_unet.py`<br>`checkpoints/baseline_unet_best.pth` | Validation Dice: 0,5830 |
| 6 | Đánh giá định lượng trên tập kiểm thử độc lập | Đánh giá độc lập trên 46 ảnh của tập kiểm thử; tính toán các chỉ số Dice, IoU, Recall, Precision, Specificity; kết xuất đồ thị huấn luyện và năm bảng ảnh trực quan đối chứng. | `evaluation/evaluate_baseline_testset.py`<br>`evaluation/baseline_test_metrics.json`<br>`evaluation/baseline_visualizations/` | Foreground Dice: 0,5719<br>IoU: 0,4405 |

*Nguồn: Tổng hợp từ kế hoạch thực hiện đề cương khóa luận tốt nghiệp.*

---

### II. DỮ LIỆU NGHIÊN CỨU VÀ QUY TRÌNH TIỀN XỬ LÝ CHUẨN Y KHOA

Trong bài toán chẩn đoán hình ảnh y tế, việc phân chia dữ liệu ngẫu nhiên theo từng ảnh chụp rất dễ dẫn đến hiện tượng rò rỉ dữ liệu (data leakage) khi ảnh của cùng một bệnh nhân xuất hiện ở cả tập huấn luyện và tập kiểm thử. Hiện tượng này làm cho mô hình ghi nhớ đặc điểm mô học cục bộ của bệnh nhân thay vì học các đặc trưng bệnh lý phổ quát, dẫn đến việc đánh giá độ chính xác bị thổi phồng so với thực tế lâm sàng.

Để giải quyết triệt để rủi ro trên, thuật toán phân chia trong đề tài được thiết lập theo cấp bệnh nhân (Patient-Level Split). Toàn bộ 307 ảnh Ground Truth từ 185 bệnh nhân được phân chia thành ba tập dữ liệu độc lập hoàn toàn với tỷ lệ 70% huấn luyện, 15% thẩm định và 15% kiểm thử.

#### Bảng 2. Cơ cấu phân chia tập dữ liệu nghiên cứu theo cấp bệnh nhân

| Tập dữ liệu | Số lượng ảnh | Tỷ lệ ảnh (%) | Số bệnh nhân độc lập | Số ca mask rỗng | Mục đích sử dụng |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Tập huấn luyện (Train set) | 215 | 70,03% | 130 | 25 | Cập nhật trọng số của mô hình U-Net |
| Tập thẩm định (Val set) | 46 | 14,98% | 27 | 5 | Tinh chỉnh siêu tham số và lưu checkpoint |
| Tập kiểm thử (Test set) | 46 | 14,98% | 28 | 5 | Đánh giá độc lập năng lực mô hình |
| **Tổng cộng (Ground Truth)** | **307** | **100,0%** | **185** | **35 (11,4%)** | **Tập dữ liệu được niêm phong nghiên cứu** |

*Nguồn: Trích xuất từ tệp de_cuong_split_manifest.json và vinmec_dataset_manifest.json.*

Kiểm toán mã nguồn xác nhận tập giao bệnh nhân giữa ba tập là rỗng: $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$. Tỷ lệ ca mask rỗng (11,4%) được phân bổ đồng đều ở cả ba tập nhằm kiểm chứng khả năng phát hiện âm tính và tránh báo động giả trên các ca không có tổn thương.

#### Quy trình tiền xử lý ảnh năm bước

Ảnh siêu âm buồng trứng thường đi kèm nhiều yếu tố gây nhiễu như vùng quét hình quạt, thông tin văn bản hành chính của máy, thước đo độ sâu và dải tương phản không đồng đều. Chuỗi tiền xử lý trong hệ thống được thiết kế thành năm bước nối tiếp:

1. Đọc ảnh thang độ xám và trích xuất mặt nạ tổn thương dạng nhị phân;
2. Tự động xác định và cắt vùng quạt quét sóng âm (ROI Fan-beam) để loại bỏ toàn bộ khung viền đen và thông số văn bản xung quanh;
3. Áp dụng kỹ thuật Letterbox đưa ảnh về kích thước chuẩn 512x512 pixel, bổ sung đệm viền đen đối xứng nhằm giữ nguyên tỷ lệ khung hình tự nhiên của khối u. Phép nội suy song tuyến tính (Bilinear) được áp dụng cho ảnh và phép nội suy lân cận gần nhất (Nearest-Neighbor) được áp dụng cho mặt nạ nhằm bảo toàn nhãn nhị phân {0, 1};
4. Áp dụng thuật toán cân bằng tương phản thích ứng cục bộ (CLAHE) với ngưỡng giới hạn clip_limit = 2.0 để tăng cường độ tương phản giữa ranh giới u nang và mô đệm buồng trứng;
5. Cài đặt hàm khôi phục kích thước ngược (`inverse_letterbox_mask`) nhằm ánh xạ chính xác kết quả phân đoạn 512x512 pixel trở lại hệ tọa độ không gian ban đầu của ảnh siêu âm.

![Quy trình tiền xử lý ảnh siêu âm buồng trứng năm bước](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/preprocessing_pipeline_demonstration.png)
*Hình 1. Quy trình tiền xử lý ảnh siêu âm buồng trứng năm bước từ ảnh thô đến khôi phục tọa độ gốc.*

---

### III. THÔNG SỐ HUẤN LUYỆN VÀ NHẬT KÝ HỘI TỤ MÔ HÌNH

Mô hình phân đoạn cơ sở được xây dựng dựa trên kiến trúc Standard U-Net nguyên bản (Ronneberger và cộng sự, 2015). Mạng gồm 4 tầng mã hóa (Encoder) trích xuất đặc trưng với số kênh tăng dần (32 -> 64 -> 128 -> 256), 1 tầng nghẽn cổ chai (Bottleneck, 512 kênh) và 4 tầng giải mã (Decoder) khôi phục độ phân giải không gian thông qua các đường truyền tắt (skip connections).

#### Bảng 3. Thông số kỹ thuật của mô hình Standard U-Net cơ sở

| Tham số kỹ thuật | Giá trị thiết lập | Ghi chú kỹ thuật và phần cứng |
| :--- | :--- | :--- |
| Kiến trúc mô hình | Standard U-Net (Ronneberger et al., 2015) | 4 tầng Encoder, 1 Bottleneck, 4 tầng Decoder, liên kết tắt |
| Tổng số tham số | 7.762.465 tham số (~7,76 triệu) | Base filters: 32 -> 64 -> 128 -> 256 -> 512 |
| Kích thước đầu vào | `(B, 1, 512, 512)` kiểu float32 | Định dạng chuẩn hóa qua quy trình Letterbox |
| Hàm mất mát (Loss) | Combo Loss ($0,5 \times L_{\text{BCE}} + 0,5 \times L_{\text{Dice}}$) | Cân bằng giữa tối ưu phân loại pixel và độ trùng lặp hình học |
| Bộ tối ưu hóa | AdamW (lr = 1e-3, weight_decay = 1e-4) | Tối ưu hóa có điều chuẩn L2 ổn định |
| Lịch điều chỉnh tốc độ học | Cosine Annealing ($T_{\max} = 12$, $\eta_{\min} = 10^{-6}$) | Giảm dần tốc độ học theo chu kỳ cosine |
| Kỹ thuật tính toán | Automatic Mixed Precision (AMP FP16) | Giảm chiếm dụng bộ nhớ, tăng tốc tính toán trên GPU RTX 3050 |
| Kích thước lô (Batch size) | `batch_size = 4` | Mức tiêu hao bộ nhớ ~1,4 GB VRAM, tránh tràn RAM hệ thống |

*Nguồn: Cấu hình mã nguồn tại backend/models/unet.py và ai_training/train_baseline_unet.py.*

Mô hình được huấn luyện trong 12 epoch trên máy tính xách tay cá nhân trang bị GPU NVIDIA GeForce RTX 3050 Laptop. Quá trình hội tụ diễn ra ổn định, hàm mất mát giảm dần qua các chu kỳ và hệ số Dice trên tập thẩm định liên tục được cải thiện, đạt giá trị cao nhất 0,5830 tại epoch 12.

#### Bảng 4. Nhật ký huấn luyện mô hình qua 12 epoch

| Epoch | Train Loss | Train Dice | Val Loss | Val Dice | Tốc độ học (LR) | Ghi nhận Checkpoint |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Epoch 01 | 0.6072 | 0.3306 | 1.4062 | 0.3562 | 0.000983 | Lưu checkpoint (Best Val Dice) |
| Epoch 02 | 0.5150 | 0.4184 | 0.5107 | 0.4321 | 0.000933 | Lưu checkpoint (Best Val Dice) |
| Epoch 03 | 0.4738 | 0.4588 | 0.5841 | 0.4309 | 0.000854 | - |
| Epoch 04 | 0.4313 | 0.5083 | 0.6683 | 0.4427 | 0.000750 | Lưu checkpoint (Best Val Dice) |
| Epoch 05 | 0.3986 | 0.5365 | 0.5040 | 0.5239 | 0.000630 | Lưu checkpoint (Best Val Dice) |
| Epoch 06 | 0.3845 | 0.5467 | 0.4341 | 0.5053 | 0.000501 | - |
| Epoch 07 | 0.3611 | 0.5789 | 0.4158 | 0.5188 | 0.000371 | - |
| Epoch 08 | 0.3468 | 0.5902 | 0.3815 | 0.5615 | 0.000251 | Lưu checkpoint (Best Val Dice) |
| Epoch 09 | 0.3356 | 0.6068 | 0.4039 | 0.5556 | 0.000147 | - |
| Epoch 10 | 0.3291 | 0.6183 | 0.4910 | 0.5046 | 0.000068 | - |
| Epoch 11 | 0.3153 | 0.6385 | 0.3728 | 0.5751 | 0.000018 | Lưu checkpoint (Best Val Dice) |
| Epoch 12 | 0.3204 | 0.6259 | 0.3762 | 0.5830 | 0.000001 | Lưu checkpoint tối ưu (0,5830) |

*Nguồn: Trích xuất từ nhật ký huấn luyện tại checkpoints/baseline_training_history.json.*

![Đồ thị hội tụ hàm mất mát và hệ số Dice qua 12 epoch](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/training_convergence_curves.png)
*Hình 2. Đồ thị hội tụ hàm mất mát Combo Loss và hệ số Dice trên tập huấn luyện và thẩm định qua 12 epoch.*

---

### IV. KẾT QUẢ ĐÁNH GIÁ ĐỊNH LƯỢNG VÀ PHÂN TÍCH HÌNH ẢNH THỰC NGHIỆM

Mô hình Standard U-Net tốt nhất (lưu tại epoch 12) được đánh giá độc lập trên toàn bộ 46 ca của tập kiểm thử. Quá trình đánh giá áp dụng các chỉ số đo lường hình học và lâm sàng chuyên dụng:

#### Bảng 5. Kết quả đánh giá định lượng trên tập kiểm thử độc lập (46 ca)

| Chỉ số đo lường | Kết quả thực nghiệm | Ý nghĩa chuyên môn và đánh giá y tế |
| :--- | :---: | :--- |
| Foreground Dice (DSC) | 0,5719 ± 0,2482 | Mức độ trùng lặp không gian giữa vùng u dự đoán và Ground Truth do chuyên gia xác nhận. |
| Intersection over Union (IoU) | 0,4405 ± 0,2341 | Chỉ số Jaccard đo độ khít ranh giới vùng tổn thương buồng trứng. |
| Recall (Độ nhạy) | 0,6362 (63,6%) | Tỷ lệ diện tích u thực tế được mô hình phát hiện, phản ánh khả năng hạn chế bỏ sót tổn thương. |
| Precision (Độ chuẩn xác) | 0,5864 (58,6%) | Tỷ lệ diện tích dự đoán thực sự là tổn thương, phản ánh mức độ lan ra mô lành lân cận. |
| Specificity trên toàn bộ ảnh | 0,8977 (89,8%) | Khả năng nhận diện chính xác các vùng mô lành xung quanh trên toàn khung hình. |
| Specificity trên ca mask rỗng | 0,8235 (82,4%) | Khả năng nhận biết chính xác các ca không có u, hạn chế báo động giả. |

*Nguồn: Kết xuất từ kịch bản evaluation/evaluate_baseline_testset.py và tệp evaluation/baseline_test_metrics.json.*

#### Phân tích trực quan các trường hợp phân đoạn thực tế

Quan sát kết quả đối chứng trực quan trên 46 ca kiểm thử cho thấy sự phân hóa rõ nét giữa các nhóm hình thái bệnh lý:

1. **Nhóm phân đoạn có độ chính xác cao (Dice > 0,75):** Gồm các ca u nang bì hoặc nang đơn thùy có ranh giới âm học rõ ràng, cấu trúc cản âm phân biệt tốt với mô buồng trứng lành xung quanh. Mô hình Standard U-Net bám sát đường viền Ground Truth của bác sĩ.

![Các trường hợp phân đoạn đạt độ chính xác cao](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/best_matches.png)
*Hình 3. Các trường hợp phân đoạn đạt độ chính xác cao (Dice > 0,75).*

2. **Nhóm phân đoạn có độ chính xác trung bình (Dice từ 0,60 đến 0,70):** Mô hình định vị chính xác vị trí tâm và hình thái chung của khối u, tuy nhiên ranh giới phân đoạn ngoài rìa hơi lan nhẹ sang các cấu trúc lân cận có mức độ phản hồi âm thấp.

![Các trường hợp phân đoạn đạt độ chính xác trung bình](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/average_matches.png)
*Hình 4. Các trường hợp phân đoạn đạt độ chính xác trung bình (Dice từ 0,60 đến 0,70).*

3. **Nhóm ca bệnh khó và thách thức phân đoạn:** Gồm các ca tổn thương buồng trứng bị che khuất bởi vệt bóng cản âm (acoustic shadowing) xuất phát từ thành phần tóc, bã đậu hoặc nốt vôi hóa của u bì, hoặc các ca u có cấu trúc đa vách phức tạp. Hiện tượng mất tín hiệu âm học phía sau khiến mặt nạ dự đoán của mô hình bị đứt quãng hoặc phân đoạn thiếu.

![Các trường hợp phân đoạn sai lệch](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/worst_matches.png)
*Hình 5. Các trường hợp phân đoạn sai lệch do bóng cản âm hoặc cấu trúc u phức tạp.*

---

### V. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG TOÀN DIỆN (AUTOMATED AUDIT SUITE)

Để bảo đảm tính toàn vẹn kỹ thuật, chống lỗi ngầm và xác nhận độ tin cậy của toàn bộ pipeline từ tiền xử lý đến mô hình, một bộ kiểm thử tự động gồm 16 kịch bản đã được xây dựng bằng thư viện PyTest (tại `tests/test_milestone_1_audit.py`):

#### Bảng 6. Danh mục 16 tiêu chí kiểm thử tự động toàn diện của hệ thống

| STT | Tên hàm kiểm thử | Mục tiêu kiểm định kỹ thuật và nghiệp vụ | Kết quả |
| :---: | :--- | :--- | :---: |
| 1 | `test_dataset_discovery` | Xác nhận sự tồn tại và định dạng các tệp CSV phân chia dữ liệu | Đạt (Pass) |
| 2 | `test_image_mask_matching` | Kiểm tra việc khớp cặp 100% giữa tệp ảnh gốc và tệp mặt nạ tổn thương | Đạt (Pass) |
| 3 | `test_patient_level_split_leakage` | Kiểm tra độc lập tuyệt đối giữa các tập dữ liệu, không có bệnh nhân trùng lặp | Đạt (Pass) |
| 4 | `test_preprocessing_shape_consistency` | Xác nhận kích thước đầu ra cố định 512x512 sau phép biến đổi Letterbox | Đạt (Pass) |
| 5 | `test_mask_label_integrity` | Kiểm tra việc bảo toàn tập nhãn nhị phân {0, 1} của mặt nạ qua phép nội suy | Đạt (Pass) |
| 6 | `test_post_preprocessing_image_mask_pair` | Kiểm tra kiểu dữ liệu float32 và khoảng giá trị chuẩn hóa [0, 1] | Đạt (Pass) |
| 7 | `test_dataloader_batch` | Kiểm tra cấu trúc tensor đầu ra theo lô của PyTorch DataLoader | Đạt (Pass) |
| 8 | `test_unet_forward_pass` | Kiểm tra lan truyền tiến qua mô hình U-Net, không xuất hiện giá trị NaN | Đạt (Pass) |
| 9 | `test_loss_computation` | Kiểm tra việc tính toán hàm mất mát Combo Loss và đồ thị đạo hàm | Đạt (Pass) |
| 10 | `test_training_smoke_test` | Kiểm tra một bước cập nhật trọng số hoàn chỉnh của thuật toán tối ưu hóa | Đạt (Pass) |
| 11 | `test_prediction_shape` | Kiểm tra kích thước tensor dự đoán và ngưỡng phân lớp nhị phân 0,5 | Đạt (Pass) |
| 12 | `test_predicted_mask_validity` | Kiểm tra tính đúng đắn của hàm ánh xạ ngược về kích thước ban đầu | Đạt (Pass) |
| 13 | `test_dice_calculation` | Kiểm tra tính toán chỉ số Dice trên dữ liệu kiểm soát giả lập | Đạt (Pass) |
| 14 | `test_iou_calculation` | Kiểm tra tính toán chỉ số IoU trên dữ liệu kiểm soát giả lập | Đạt (Pass) |
| 15 | `test_recall_calculation` | Kiểm tra tính toán độ nhạy Recall trên dữ liệu kiểm soát giả lập | Đạt (Pass) |
| 16 | `test_end_to_end_pipeline_flow` | Kiểm tra tích hợp toàn bộ chuỗi xử lý từ ảnh thô đến chỉ số đánh giá | Đạt (Pass) |

*Nguồn: Thực thi lệnh pytest tests/test_milestone_1_audit.py (Kết quả: 16 passed in 7.31s).*

---

### VI. NHẬN ĐỊNH KỸ THUẬT VÀ CÁC HẠN CHẾ CẦN GIẢI QUYẾT

Dựa trên các kết quả thực nghiệm đạt được ở Cột mốc 1, một số vấn đề kỹ thuật và thực tế nghiệp vụ được rút ra như sau:

1. **Hiện tượng dự đoán lan rộng tại vùng biên mờ (Over-segmentation):** Chỉ số Precision (58,6%) thấp hơn Recall (63,6%) cho thấy mô hình Standard U-Net có xu hướng phân đoạn thừa tại các ranh giới mô có độ phản hồi âm thấp tương tự dịch u. Do kiến trúc U-Net cơ sở sử dụng các phép tích chập cục bộ thuần túy mà chưa có cơ chế chọn lọc đặc trưng không gian, thông tin nhiễu từ các tầng mã hóa ban đầu truyền thẳng sang các tầng giải mã qua đường liên kết tắt.
2. **Suy giảm tín hiệu do bóng cản âm (Acoustic Shadowing):** Đối với các khối u bì buồng trứng chứa nhiều thành phần cản âm như nốt vôi hóa hoặc tóc, chùm sóng siêu âm bị triệt tiêu tạo thành dải bóng sẫm màu phía sau. Mô hình hiện tại gặp khó khăn trong việc suy luận hình học liên tục của khối u qua các dải bóng cản này.
3. **Tính tất yếu của cơ chế tương tác Human-in-the-Loop:** Kết quả định lượng trên tập kiểm thử khẳng định rằng mô hình học sâu đóng vai trò hỗ trợ gợi ý ban đầu chứ không thể thay thế việc xác nhận của bác sĩ chẩn đoán hình ảnh. Do đó, việc xây dựng công cụ tương tác trực quan (cho phép bác sĩ xem lớp phủ, dùng chổi vẽ hoặc tẩy xóa để tinh chỉnh mặt nạ trực tiếp trên trình duyệt) là mắt xích bắt buộc để bảo đảm độ chính xác và an toàn trước khi kết quả được lưu trữ hoặc đưa vào bệnh án.

---

### VII. KẾ HOẠCH TRIỂN KHAI CỘT MỐC 2 (21/09/2026 - 05/10/2026)

Trong giai đoạn tiếp theo của đề tài, các công việc sẽ tập trung vào việc thử nghiệm mô hình Attention U-Net nhằm khắc phục hiện tượng phân đoạn thừa, đồng thời lập trình giao diện Web Prototype Human-in-the-Loop hoàn chỉnh:

#### Bảng 7. Kế hoạch công việc chi tiết trong Cột mốc 2

| Thời gian | Nhiệm vụ trọng tâm | Nội dung kỹ thuật cụ thể | Sản phẩm bàn giao dự kiến |
| :---: | :--- | :--- | :--- |
| 21/09 - 25/09 | Thử nghiệm kiến trúc Attention U-Net | Tích hợp các cổng chú ý (Attention Gates) vào các đường liên kết tắt nhằm hạn chế nhiễu nền từ encoder, tập trung vào vùng tổn thương mục tiêu để nâng cao chỉ số Precision và Dice. | Mã nguồn `backend/models/attention_unet.py`<br>Checkpoint `checkpoints/best_attention_unet.pth`<br>Bảng thực nghiệm so sánh Ablation Study |
| 26/09 - 28/09 | Đánh giá so sánh và phân tích lỗi | Đánh giá đối chứng Standard U-Net và Attention U-Net trên cùng tập kiểm thử 46 ca; phân tích lỗi chi tiết trên các nhóm ca bóng cản âm và ca u vách ngăn; lựa chọn mô hình chính thức. | Báo cáo đối chứng định lượng (`model_comparison.csv`)<br>Bộ hình ảnh phân tích lỗi chuyên sâu |
| 29/09 - 30/09 | Xây dựng dịch vụ suy luận (Inference API) | Phát triển RESTful API bằng FastAPI; tối ưu hóa pipeline tiền xử lý ảnh và nạp mô hình; bảo đảm thời gian đáp ứng dưới 500 mili-giây mỗi ảnh trên phần cứng GPU cá nhân. | Mã nguồn `backend/api/segmentation.py`<br>Điểm cuối `/api/v1/segmentation/predict` hoạt động ổn định |
| 01/10 - 03/10 | Xây dựng giao diện Web Prototype HITL | Lập trình giao diện người dùng bằng React.js và HTML5 Canvas; cung cấp tính năng tải ảnh, hiển thị lớp phủ mặt nạ gợi ý, công cụ chổi vẽ (Brush) và tẩy xóa (Eraser) để bác sĩ chỉnh sửa và xác nhận kết quả. | Giao diện Web Prototype tương tác trực tiếp trên trình duyệt |
| 04/10 - 05/10 | Tổng hợp kết quả và soạn thảo báo cáo | Tổng hợp dữ liệu thực nghiệm đưa vào bản thảo Chương 3 khóa luận tốt nghiệp; hoàn thiện Báo cáo tiến độ Cột mốc 2 nộp Thầy. | Bản thảo Chương 3 KLTN<br>Báo cáo tiến độ Cột mốc 2 |

*Lưu ý về phạm vi triển khai:* Bám sát chỉ đạo chuyên môn của Thầy, các hướng nghiên cứu mở rộng như tích hợp mô hình ngôn ngữ lớn (LLM/VLM), tự động sinh văn bản mô tả bệnh án hoặc phát triển bảng điều khiển quản trị nâng cao sẽ chỉ được xem xét nếu phần phân đoạn và giao diện tương tác Human-in-the-Loop cốt lõi đã hoàn thành tốt và còn đủ thời gian.

---

Em xin kính báo cáo Thầy tình hình thực hiện Cột mốc 1 của khóa luận. Em rất mong tiếp tục nhận được những lời khuyên và chỉ dẫn chuyên môn của Thầy để thực hiện tốt các nội dung nghiên cứu trong Cột mốc 2.

Em xin chân thành cảm ơn Thầy.

<br>

**Sinh viên thực hiện**  
*Nguyễn Hữu Dũng*  
(Mã sinh viên: 11235559, Lớp: HTTTQL 65A)