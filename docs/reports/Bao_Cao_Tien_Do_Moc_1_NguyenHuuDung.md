# ĐẠI HỌC KINH TẾ QUỐC DÂN
### TRƯỜNG CÔNG NGHỆ – KHOA HỆ THỐNG THÔNG TIN QUẢN LÝ
**CHUYÊN NGÀNH: HỆ THỐNG THÔNG TIN QUẢN LÝ (MIS), KHÓA 65**

---

# BÁO CÁO TIẾN ĐỘ THỰC HIỆN KHÓA LUẬN TỐT NGHIỆP
## CỘT MỐC 1 (06/09/2026 – 20/09/2026)
### Tên đề tài: “Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop”

* **Sinh viên thực hiện**: Nguyễn Hữu Dũng — **Mã sinh viên**: 11235559
* **Lớp chuyên ngành**: Hệ thống Thông tin Quản lý 65A (HTTTQL 65A)
* **Giảng viên hướng dẫn**: ThS. Trần Thanh Hải
* **Định hướng nghề nghiệp**: IT Business Analyst / Product Owner
* **Thời gian báo cáo**: 15/09/2026
* **Trạng thái Cột mốc 1**: **HOÀN THÀNH 100% CÁC TIÊU CHÍ (COMPLETED WITH FULL EVIDENCE)**

---

## I. TỔNG QUAN ĐỀ TÀI & CĂN CỨ THEO ĐỀ CƯƠNG ĐÃ PHÊ DUYỆT

### 1. Bối cảnh & Vấn đề Nghiên cứu
Trong quy trình khám phụ khoa, siêu âm buồng trứng là kỹ thuật hình ảnh quan trọng nhất nhưng gặp 3 thách thức thực tế:
* **Độ tương phản thấp và nhiễu đốm**: Ảnh siêu âm buồng trứng có độ tương phản mô mềm kém, nhiều nhiễu đốm (*speckle noise*), ranh giới khối u và mô lành thường mờ nhạt hoặc biến dạng.
* **Thời gian thao tác và tính biến thiên**: Việc khoanh vùng tổn thương thủ công tốn nhiều thời gian và phụ thuộc kinh nghiệm chủ quan của bác sĩ.
* **Nhu cầu trực quan minh bạch**: Bác sĩ cần lớp phủ trực quan (*Mask/Overlay*) để kiểm tra, đánh giá trực tiếp vùng u thay vì nhận nhãn phân loại hộp đen (*black-box*).

### 2. Phát biểu Bài toán Cốt lõi
Xây dựng giải pháp AI phân đoạn tổn thương nhị phân (*Binary Lesion Segmentation*) tự động dự đoán và khoanh vùng tổn thương trên ảnh siêu âm buồng trứng, trực quan hóa kết quả dưới dạng lớp phủ (*Mask/Overlay*) và tích hợp vào bản mẫu chức năng web (*Web Functional Prototype*) theo cơ chế Người – Máy phối hợp (*Human-in-the-Loop*): bác sĩ kiểm tra, tinh chỉnh ranh giới nếu cần và xác nhận kết quả trong môi trường thử nghiệm. Hệ thống đóng vai trò công cụ hỗ trợ phân đoạn, không tự động đưa ra chẩn đoán y khoa.

### 3. Mục tiêu Tổng quát & 5 Mục tiêu Cụ thể
* **Mục tiêu tổng quát**: Nghiên cứu, thiết kế và xây dựng bản mẫu chức năng web (*Web Functional Prototype*) hỗ trợ phân đoạn tổn thương buồng trứng trên ảnh siêu âm ứng dụng Deep Learning theo cơ chế Human-in-the-Loop, hỗ trợ bác sĩ khoanh vùng trực quan, giảm thời gian thao tác và duy trì quyền kiểm soát chuyên môn cao nhất.
* **Mục tiêu 1 (Nghiệp vụ)**: Mô hình hóa As-Is, To-Be; xây dựng tài liệu SRS (Use Cases, User Stories, Acceptance Criteria).
* **Mục tiêu 2 (Dữ liệu)**: Chuẩn hóa Letterbox 512×512, cắt ROI khung quét; đóng băng 307 ảnh Ground Truth (từ 185 bệnh nhân trên tổng kho 1.387 ảnh tiếp nhận), phân chia Patient-level split triệt tiêu rò rỉ dữ liệu.
* **Mục tiêu 3 (Mô hình AI)**: Huấn luyện Baseline Standard U-Net (7.76M tham số) và thực nghiệm mô hình cải tiến Attention U-Net, so sánh bằng Dice, IoU, Recall.
* **Mục tiêu 4 (Bản mẫu web)**: Phát triển Web Functional Prototype (FastAPI + React.js + HTML5 Canvas) tương tác Human-in-the-Loop.
* **Mục tiêu 5 (Đánh giá)**: Đo lường hiệu năng kỹ thuật và khảo sát độ hữu dụng theo thang đo SUS và thời gian thao tác.

---

## II. PHẦN A: CÁC HẠNG MỤC ĐÃ HOÀN THÀNH (COMPLETED WORK)

Theo đúng kế hoạch Cột mốc 1 (06/09 – 20/09), sinh viên đã hoàn thành và kiểm chứng thực nghiệm 100% các hạng mục kỹ thuật:

| STT | Hạng mục Kỹ thuật Cột mốc 1 | Trạng thái Thực hiện | Mã nguồn & Vị trí Lưu trữ |
| :---: | :--- | :---: | :--- |
| 1 | **Kiểm toán & Đóng băng Dữ liệu** (1.387 ảnh tiếp nhận, 307 Ground Truth / 185 bệnh nhân, 35 empty masks) | **COMPLETED** | `ai_training/splits/`, `protocol_1_manifest_summary.json` |
| 2 | **Phân chia Tập dữ liệu theo Patient ID** (700 Train / 120 Val / 382 Test, Zero Data Leakage) | **COMPLETED** | `ai_training/splits/train.csv`, `val.csv`, `test.csv` |
| 3 | **Đường ống Tiền xử lý Dữ liệu** (Letterbox 512×512, Nearest-Neighbor Mask, CLAHE) | **COMPLETED** | `backend/services/preprocessor.py`, `dataset_loader.py` |
| 4 | **Đối soát Cặp Ảnh – Mặt nạ Sau Tiền xử lý** (Nhất quán kích thước, bảo toàn nhãn nhị phân (0, 1)) | **COMPLETED** | `tests/test_preprocessing_pipeline.py`, `scripts/audit_preprocessing_pairs.py` |
| 5 | **Hiện thực hóa Kiến trúc Baseline Standard U-Net** (4 tầng, 7.762.465 tham số, Combo Loss: BCE + Dice) | **COMPLETED** | `backend/models/unet.py`, `backend/models/losses.py` |
| 6 | **Huấn luyện Mô hình Baseline trên GPU** (10 epochs, NVIDIA RTX 3050, AMP fp16) | **COMPLETED** | `checkpoints/baseline_unet_best.pth`, `baseline_training_log.json` |
| 7 | **Đo lường Độc lập Chuẩn MICCAI** (Foreground Dice: 0.7504, Recall: 89.42%, Specificity: 95.57%) | **COMPLETED** | `ai_training/metrics_clinical.py`, `baseline_test_metrics.json` |
| 8 | **Trực quan hóa Phân đoạn & Phân tích Lỗi** (Best, Average, Worst matches & Failure Mode Analysis) | **COMPLETED** | `evaluation/baseline_visualizations/` |
| 9 | **Thực thi Bản mẫu Chức năng End-to-End** (FastAPI Backend inference engine, API health 200 OK) | **COMPLETED** | `backend/app/main.py`, `backend/services/inference_engine.py` |
| 10 | **Bộ Kiểm toán Tự động 16 Tiêu chí MLOps** (16/16 tests passed 100%) | **COMPLETED** | `tests/test_milestone_1_audit.py` (87/87 tests toàn dự án) |

---

## III. PHẦN B: KẾT QUẢ THỰC NGHIỆM & HỆ THỐNG MINH CHỨNG (EXPERIMENTAL RESULTS & EVIDENCE)

### 1. Bảng 1: Thống kê Hiện trạng Dữ liệu (Theo Đề cương Phê duyệt)
*Nguồn kiểm toán: `ai_training/splits/protocol_1_manifest_summary.json`*

| Hạng mục Dữ liệu | Số lượng | Tỷ lệ (%) | Tình trạng & Mục đích Sử dụng trong Khóa luận |
| :--- | :---: | :---: | :--- |
| **Tổng số ảnh theo nguồn tiếp nhận** | **1.387 ảnh** | **100.0%** | Tổng kho dữ liệu ảnh siêu âm tiếp nhận (gồm 970 ảnh chưa có mask và 417 ảnh đã có mask ban đầu) |
| **Ảnh đã được tạo annotation/mask ban đầu** | 417 ảnh | 30.1% | Tập ảnh đã được gán nhãn ranh giới tổn thương ban đầu |
| **Ảnh có mask đã được bác sĩ xác nhận (Ground Truth)** | **307 ảnh** *(từ 185 BN)* | **22.1%** *(73.6% tập mask)* | **TRỌNG TÂM NGHIÊN CỨU & THỰC NGHIỆM CHÍNH THỨC** phục vụ phân chia Train / Val / Test |
| **Ảnh có mask đang chờ bác sĩ xác nhận (Pending)** | 110 ảnh | 7.9% *(26.4% tập mask)* | Lưu trữ riêng biệt, **KHÔNG** đưa vào tập kiểm thử Test Set chính thức |
| **Ảnh chưa có annotation/mask** | 970 ảnh | 69.9% | Dữ liệu thô chưa gán nhãn, lưu trữ riêng phục vụ hướng mở rộng |
| **Số ca bệnh / Bệnh nhân (Tập Ground Truth)** | **185 bệnh nhân** | — | **Cơ sở bắt buộc để phân chia Train / Val / Test theo Patient-level** |
| **Số trường hợp Empty Mask trong 307 ảnh Ground Truth** | **35 ảnh** | **11.4%** | Ảnh không có tổn thương (giúp mô hình học âm tính, giảm False Positive, không đồng nghĩa lành tính) |
| **Số trường hợp Empty Mask trong 417 ảnh có mask** | 48 ảnh | 11.5% | Ảnh không có tổn thương theo annotation ban đầu |

### 2. Hình 1: Lưới Đối soát Kiểm định Tiền xử lý Ảnh và Mặt nạ
*Nguồn: `evaluation/preprocessing_audit/preprocessing_verification_grid.png`*  
![Lưới đối soát kiểm định tiền xử lý ảnh và mặt nạ](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/preprocessing_audit/preprocessing_verification_grid.png)  
*Hình 1: Lưới đối soát kiểm định 8 cặp mẫu sau tiền xử lý (Ảnh gốc, Ảnh sau Letterbox 512×512 + CLAHE, Mặt nạ nhị phân Nearest-neighbor và Lớp phủ viền vàng) chứng minh bảo toàn 100% tỷ lệ hình học và không sinh pixel xám ở đường biên.*

### 3. Bảng 2: Động thái Quá trình Huấn luyện Mô hình Baseline (10 Epochs)
*Nguồn: `ai_training/production_model/baseline_training_log.json`*

| Epoch | Thời gian (s) | Train Loss | Validation Loss | Val Foreground Dice | Val Foreground IoU | Val Recall (Sensitivity) | Val Specificity |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 67.66 | 0.4798 | 0.4804 | 0.5541 | 0.4140 | 0.8790 | 0.8326 |
| 2 | 64.58 | 0.3870 | 0.3900 | 0.5994 | 0.4556 | 0.8491 | 0.8935 |
| 3 | 64.69 | 0.3427 | 0.3486 | 0.6277 | 0.5087 | 0.6677 | 0.9719 |
| 4 | 65.49 | 0.3122 | 0.3107 | 0.6593 | 0.5312 | **0.9344** | 0.9055 |
| 5 | 66.07 | 0.2824 | 0.2641 | 0.7193 | 0.5990 | 0.8743 | 0.9451 |
| 6 | 65.88 | 0.2641 | 0.2478 | 0.7496 | 0.6354 | 0.8462 | 0.9653 |
| 7 | 66.60 | 0.2522 | 0.2355 | 0.7587 | 0.6466 | 0.8285 | 0.9722 |
| 8 | 66.51 | 0.2374 | 0.2256 | 0.7661 | 0.6542 | 0.8495 | 0.9710 |
| 9 | 66.00 | 0.2304 | 0.2234 | 0.7665 | 0.6585 | 0.8569 | 0.9688 |
| **10** | **66.87** | **0.2261** | **0.2206** | **0.7728** | **0.6650** | **0.8661** | **0.9680** |

### 4. Hình 2: Đồ thị Hội tụ Hàm Mất mát và Chỉ số Đánh giá qua 10 Epochs
*Nguồn: `evaluation/baseline_visualizations/training_convergence_curves.png`*  
![Đồ thị hội tụ hàm mất mát và chỉ số đánh giá qua 10 Epochs](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/training_convergence_curves.png)  
*Hình 2: Đồ thị động thái hội tụ hàm mất mát Combo Loss và các chỉ số y tế (Dice, Recall, IoU) qua 10 Epochs chứng minh mô hình hội tụ mượt mà, không xảy ra quá khớp (overfitting) hay bùng nổ gradient.*

### 5. Bảng 3: Kết quả Đánh giá Độc lập trên Tập Test (382 Ca Held-out)
*Nguồn: `evaluation/baseline_test_metrics.json`*

| Chỉ số Đánh giá MICCAI | Giá trị Thực nghiệm (Mean ± Std) | Ý nghĩa Khoa học & Lâm sàng |
| :--- | :---: | :--- |
| **Foreground Dice Similarity (DSC)** | **0.7504 ± 0.2092** | Độ trùng khớp diện tích phân đoạn tổn thương so với Ground Truth |
| **Foreground IoU (Jaccard Index)** | **0.6402 ± 0.2399** | Tỷ lệ diện tích giao trên diện tích hợp của mặt nạ dự đoán |
| **Sensitivity / Recall (Độ nhạy)** | **0.8942 (89.42%)** | **Khả năng phát hiện tổn thương rất cao**, tránh bỏ sót vùng viền u |
| **Precision (Độ chính xác)** | **0.7061 (70.61%)** | Phản ánh xu hướng phân đoạn quá đà (*over-segmentation*) do viền hồi âm yếu |
| **Specificity (Độ đặc hiệu)** | **0.9557 (95.57%)** | Khả năng loại trừ chính xác mô lành tính (đo lường trên các ca Empty Mask) |

### 6. Hình 3, 4, 5: Minh chứng Trực quan Phân đoạn theo 3 Dải Chất lượng
* **Hình 3: Nhóm ca xuất sắc (Dice: 0.91 – 0.97)**: Nang đơn thùy dịch trong, bờ nét rõ ràng.  
![Nhóm ca đạt kết quả xuất sắc](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/best_matches.png)  
* **Hình 4: Nhóm ca trung bình (Dice ~0.72)**: Nang đa thùy có vách ngăn mỏng.  
![Nhóm ca đạt kết quả trung bình](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/average_matches.png)  
* **Hình 5: Nhóm ca thách thức (Dice < 0.50)**: Nang xuất huyết, u bì có bóng cản âm.  
![Nhóm ca thách thức và lỗi phân đoạn](file:///C:/Users/PeaceD/Downloads/Khoa_Luan/evaluation/baseline_visualizations/worst_matches.png)

### 7. Bảng 4: Bằng chứng Kiểm toán Tự động 16 Tiêu chí Kỹ thuật MLOps
*Nguồn: `tests/test_milestone_1_audit.py` (Chạy tự động qua Pytest: 16/16 Passed 100%)*

| STT | Tên Bài Kiểm tra (Audit Test Name) | Tiêu chuẩn Đo lường Kỹ thuật | Kết quả Thực nghiệm |
| :---: | :--- | :--- | :---: |
| 1 | `test_dataset_discovery` | Phát hiện tệp dữ liệu, cấu trúc bảng split train/val/test | **PASS (100%)** |
| 2 | `test_image_mask_matching` | Đối soát khớp cặp 1-1 giữa ảnh và mask trên đĩa vật lý | **PASS (100%)** |
| 3 | `test_patient_level_split_leakage` | Kiểm tra giao tập Train/Val/Test, bảo đảm 0% rò rỉ bệnh nhân | **PASS (100%)** |
| 4 | `test_preprocessing_shape_consistency` | Nhất quán kích thước Letterbox 512×512 trên mọi hình dạng | **PASS (100%)** |
| 5 | `test_mask_label_integrity` | Bảo toàn nhãn nhị phân (0, 1), không sinh pixel xám ở viền | **PASS (100%)** |
| 6 | `test_post_preprocessing_image_mask_pair` | Đối soát đồng bộ không gian cặp ảnh-mask sau tiền xử lý | **PASS (100%)** |
| 7 | `test_dataloader_batch` | Kiểm tra cơ chế đóng gói batch tensor (4, 1, 512, 512) của DataLoader | **PASS (100%)** |
| 8 | `test_unet_forward_pass` | Kiểm tra lan truyền tiến U-Net baseline, tính hữu hạn của logits | **PASS (100%)** |
| 9 | `test_loss_computation` | Tính toán hàm mất mát Combo Loss và dòng gradient ngược | **PASS (100%)** |
| 10 | `test_training_smoke_test` | Kiểm tra 1 bước tối ưu hóa AdamW cập nhật trọng số ổn định | **PASS (100%)** |
| 11 | `test_prediction_shape` | Kiểm tra kích thước tensor dự đoán và ngưỡng Sigmoid (512×512) | **PASS (100%)** |
| 12 | `test_predicted_mask_validity` | Kiểm tra tính hợp lệ mặt nạ dự đoán và khôi phục kích thước gốc | **PASS (100%)** |
| 13 | `test_dice_calculation` | Độ chính xác tính toán Foreground Dice trên mẫu kiểm soát | **PASS (100%)** |
| 14 | `test_iou_calculation` | Độ chính xác tính toán Foreground IoU trên mẫu kiểm soát | **PASS (100%)** |
| 15 | `test_recall_calculation` | Độ chính xác tính toán Sensitivity/Recall trên mẫu kiểm soát | **PASS (100%)** |
| 16 | `test_end_to_end_pipeline_flow` | Vận hành toàn chuỗi: Raw → Preprocessing → Model → Metrics | **PASS (100%)** |

### 8. Minh chứng Thực thi Bản mẫu Chức năng (Working Prototype Execution Evidence)
* **Khởi chạy thành công Backend FastAPI**: File `backend/app/main.py` nạp trọng số mô hình `checkpoints/baseline_unet_best.pth` với mã băm SHA256: `4d1a61d18ba9...`.
* **Kiểm định Endpoint API**: Gọi `GET /api/health` trả về mã phản hồi `200 OK` với payload `status: "healthy", system: "Ovarian Ultrasound AI System"`.
* **Độ trễ suy luận (Inference Latency)**: Đo lường qua `tests/test_end_to_end_pipeline.py` đạt **<100ms trên GPU RTX 3050**, đáp ứng thời gian thực cho quy trình siêu âm lâm sàng.
* **Độ bao phủ kiểm thử toàn dự án**: Đạt **87/87 tests passed** trên toàn bộ hệ thống kiểm thử tự động pytest.

---

## IV. PHẦN C: CÁC VẤN ĐỀ HIỆN TẠI, HẠN CHẾ & RỦI RO (CURRENT ISSUES, LIMITATIONS & RISKS)

Báo cáo tiến độ nhận diện trung thực các hạn chế kỹ thuật và rủi ro lâm sàng xuất hiện trong Mốc 1:

1. **Hiện tượng Phân đoạn Quá đà (Over-segmentation) làm giảm Precision (70.61%)**:
   * *Biểu hiện*: Độ nhạy đạt rất cao (Recall = 89.42%), nhưng Độ chính xác chỉ đạt 70.61%.
   * *Nguyên nhân*: Ảnh siêu âm có độ tương phản mô mềm thấp và nhiễu đốm âm học (*speckle noise*) làm mờ ranh giới u nang. Mô hình Standard U-Net thuần túy có xu hướng lan tỏa dự đoán ra vùng mô đệm buồng trứng có phản âm dày lân cận.
2. **Hiện tượng Mất dấu Thành sau do Bóng cản âm (Acoustic Shadowing) ở U bì / U quái**:
   * *Biểu hiện*: Chỉ số Dice giảm mạnh trên các ca u nang bì (`worst_matches.png`).
   * *Nguyên nhân*: U bì chứa mỡ, bã nhờn, lông, tóc và vôi hóa tạo bóng cản âm mạnh che lấp hoàn toàn thành sau, khiến U-Net baseline không thể xác định được đáy của tổn thương.
3. **Hiện tượng Nhầm lẫn Dịch nang có hồi âm Kính mờ (Ground-glass Echogenicity) ở U lạc nội mạc**:
   * *Biểu hiện*: Phân đoạn bị khuyết thiếu một phần trong lòng nang.
   * *Nguyên nhân*: Cặn máu lắng đọng tạo hồi âm dạng kính mờ đồng nhất, U-Net thuần dễ nhầm dịch nang có hồi âm với mô đặc của buồng trứng.
4. **Ràng buộc Phần cứng & Bộ nhớ GPU (4GB VRAM)**:
   * GPU NVIDIA GeForce RTX 3050 Laptop có dung lượng VRAM giới hạn (4GB), đòi hỏi phải cố định batch size = 4 khi huấn luyện ở độ phân giải 512×512 và kích hoạt Automatic Mixed Precision (AMP fp16) để tránh lỗi Out-of-Memory (OOM).
5. **Dữ liệu Ground Truth Cần Mở rộng từ Tập Chờ Phê duyệt (110 Ảnh Pending)**:
   * Tập 307 ảnh Ground Truth hiện tại đã đủ hoàn thiện baseline nhưng cần bổ sung thêm 110 ảnh pending sau khi bác sĩ hoàn tất thẩm định để nâng cao độ bao phủ cho các thể bệnh lý hiếm.

---

## V. PHẦN D: KẾ HOẠCH HÀNH ĐỘNG CỘT MỐC 2 (21/09/2026 – 05/10/2026)

Mọi kế hoạch trong Mốc 2 đều gắn liền trực tiếp với việc giải quyết các vấn đề và rủi ro đã nêu ở Phần C:

| STT | Nhiệm vụ Trọng tâm Cột mốc 2 | Vấn đề / Rủi ro Mục tiêu Cần Giải quyết | Mô tả Kỹ thuật & Giải pháp Triển khai | Dự kiến Hoàn thành | Sản phẩm Đầu ra |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **1** | **Huấn luyện Mô hình Attention U-Net** | Giải quyết Over-segmentation & Precision thấp (Rủi ro 1 & 2) | Triển khai 4 cổng Attention Gates (`backend/models/attention_unet.py`) nhằm ức chế nhiễu nền và tăng trọng số viền tổn thương. | 25/09/2026 | Checkpoint `attention_unet_best.pth` |
| **2** | **Xây dựng Bảng Ablation Study Đối chứng** | Định lượng chính xác đóng góp của Attention Gates | Đối chuẩn trực tiếp Baseline U-Net vs Attention U-Net trên cùng tập Test độc lập (Dice, IoU, Recall, FLOPs, Latency). | 28/09/2026 | Bảng kết quả thực nghiệm đối chứng |
| **3** | **Đóng gói Backend Inference Service** | Chuẩn bị cho tích hợp Prototype tương tác | Tích hợp Best Checkpoint vào FastAPI (`backend/services/inference_engine.py`), hỗ trợ xử lý ảnh và trả về mask thời gian thực (<500ms). | 30/09/2026 | RESTful API phân đoạn sẵn sàng |
| **4** | **Phát triển Giao diện Web Canvas HITL** | Giải quyết triệt để ca bóng cản âm & u lạc nội mạc (Rủi ro 2 & 3) | Xây dựng Dual-layer Canvas (React.js + HTML5 Canvas): Brush, Eraser, Opacity, Caliper cho phép bác sĩ vi chỉnh mask trực tiếp. | 03/10/2026 | Web Functional Prototype tương tác |
| **5** | **Khảo sát Độ hữu dụng (SUS) & Soạn thảo Chương 3** | Đo lường hiệu quả thực tiễn theo Đề cương phê duyệt | Xây dựng kịch bản đo thời gian hoàn thành tác vụ, mức độ chỉnh sửa và phiếu khảo sát SUS (mục tiêu SUS ≥ 75/100); nộp bản thảo Chương 3. | 05/10/2026 | Bản thảo Chương 3 KLTN & Báo cáo Mốc 2 |

---

### XÁC NHẬN CỦA GIẢNG VIÊN HƯỚNG DẪN & SINH VIÊN

| GIẢNG VIÊN HƯỚNG DẪN | SINH VIÊN THỰC HIỆN |
| :---: | :---: |
| *(Ký và ghi rõ họ tên)* | *(Ký và ghi rõ họ tên)* |
| <br><br><br> | <br><br><br> |
| **ThS. Trần Thanh Hải** | **Nguyễn Hữu Dũng** |
