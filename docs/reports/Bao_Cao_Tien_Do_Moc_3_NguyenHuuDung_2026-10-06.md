# Báo cáo tiến độ Mốc 3

**Sinh viên:** Nguyễn Hữu Dũng — **MSV:** 11235559  
**Đề tài:** Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop  
**Thời gian:** 06/10/2026–18/10/2026  
**Cập nhật:** 06/10/2026

## 1. Tóm tắt tiến độ

Mốc 3 chưa đủ cơ sở kết luận hoàn tất. Đã có kết quả huấn luyện, Test lịch sử, prototype và phân tích lỗi; kiểm toán mới xác nhận mô hình nghiên cứu U-Net++ bằng Validation và kiểm thử prototype tách biệt. Lượt pytest mới nhất đạt 67 passed / 8 failed do dữ liệu Mốc 1 bị thiếu. Patient-level independence và nguồn phê duyệt nhãn chuyên môn chưa xác minh được; đánh giá HITL với chuyên viên chưa có kết quả thực tế.

Chủ dự án đã chốt phạm vi tiếp tục là `dataset/Vinmec/Vinmec_2d` và `dataset/Vinmec/Vinmec_3d`. Cả 1.604 cặp chính của split đã khóa nằm trong hai thư mục này: 1.438 mẫu 2d và 166 mẫu 3d. Tên thư mục `3d` không chứng minh đây là volume 3D; pipeline hiện suy diễn trên từng ảnh 2D. Không chia lại split hoặc thay nhãn để phù hợp kết luận.

Báo cáo kiểm toán đầy đủ, có inventory/hash, provenance và checklist nghiệm thu: [Kiểm toán Mốc 3](Kiem_Toan_Moc_3_2026-10-06.md). Các đoạn Test bên dưới là kết quả lịch sử riêng của Standard U-Net `417828fa…`; không phải Test metric của U-Net++.

| Hạng mục | Kết quả | Minh chứng |
|---|---|---|
| Hoàn thiện U-Net trên tập dữ liệu hợp nhất | Chọn checkpoint theo Validation; không dùng Test để huấn luyện hoặc chọn mô hình/ngưỡng | [`run_config.json`](../../checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/run_config.json) |
| Đánh giá định lượng Test | 402 ảnh; threshold 0,5; các chỉ số phân đoạn được lưu theo từng ảnh và tổng hợp | [`test_summary.json`](../../evaluation/milestone_3_2026-10-06/test_summary.json), [`test_per_image.csv`](../../evaluation/milestone_3_2026-10-06/test_per_image.csv) |
| Phân tích lỗi | Rà soát 5 ca Dice cao và 5 ca có tổng FP+FN lớn | [Báo cáo phân tích lỗi](Phan_Tich_Loi_Moc_3_2026-10-06.md), [panel ảnh](../../evaluation/milestone_3_2026-10-06/error_analysis/) |
| Kiểm thử phần mềm | Lượt mới nhất: 67 passed / 8 failed; lỗi do đường dẫn dữ liệu Mốc 1 bị thiếu. Browser Smoke Test U-Net++ PASS ở cấu hình tách biệt | [`pytest_latest.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/pytest_latest.json), [`browser_smoke_run.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/browser_smoke_run.json) |
| Đánh giá HITL với chuyên viên y tế | Chưa thực hiện; cần thu thập trực tiếp, không thay bằng kiểm thử tự động | [Biểu mẫu đánh giá HITL](Bieu_Mau_Danh_Gia_HITL_Moc_3.md) |

## 2. Dữ liệu, huấn luyện và kiểm soát đánh giá

Manifest hợp nhất ghi nhận 1.639 ảnh duy nhất trước xử lý, loại 35 ảnh gắn với fallback mask khỏi huấn luyện/đánh giá, còn 1.604 mẫu: 661 Train, 541 Validation và 402 Test. Các nhóm thư mục nguồn có nội dung trùng lặp; vì vậy thống kê theo nguồn không phải các tập con độc lập. Mỗi ảnh chỉ được tính một lần trong manifest hợp nhất.

| Thành phần | Cấu hình / kết quả |
|---|---|
| Kiến trúc | Standard U-Net, `base_filters=32` |
| Tiền xử lý | Grayscale, CLAHE, Letterbox 512×512 |
| Loss / optimizer | 0,5 BCE + 0,5 Dice; AdamW, learning rate 3×10⁻⁴ |
| Huấn luyện | 20 epochs tối đa, batch size 2, seed 42, CUDA — NVIDIA GeForce RTX 3050 Laptop GPU |
| Chọn checkpoint | Epoch 20 theo Validation Dice = 0,6724; threshold = 0,5 |
| Checkpoint đánh giá | [`baseline_unet_best.pth`](../../checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth), SHA-256 `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d` |

Việc chia dữ liệu bảo đảm không có cùng SHA-256 nội dung ảnh giữa Train, Validation và Test. Không có Patient ID/Case ID nguồn được xác thực, nên đây là bảo đảm độc lập ở mức ảnh, không phải patient-level split. 35 mask fallback không được xem là ground truth hợp lệ và các mẫu liên quan bị loại khỏi tập dùng để huấn luyện/đánh giá.

Test được giữ ngoài quá trình tối ưu, chọn checkpoint và chọn threshold của lượt huấn luyện này. Tuy nhiên, cùng split Test đã từng được dùng đánh giá checkpoint baseline trước lượt refinement. Vì vậy kết quả dưới đây là đánh giá trên split giữ lại cho checkpoint hiện tại, không được mô tả là lần mở Test đầu tiên của toàn bộ nghiên cứu. Kết quả Test không được dùng để tinh chỉnh tiếp mô hình.

## 3. Kết quả Test

| Tập đánh giá | Số ảnh | Dice (mean ± SD) | IoU (mean ± SD) | Recall | Precision | Pixel Specificity |
|---|---:|---:|---:|---:|---:|---:|
| Test | 402 | 0,7297 ± 0,2304 | 0,6186 ± 0,2476 | 0,7311 | 0,8129 | 0,9836 |

Cả 402 mask tham chiếu trong manifest đánh giá đều có vùng foreground; không có mẫu mask rỗng để ước lượng riêng empty-mask specificity. Specificity được báo cáo là độ đặc hiệu ở mức pixel trên toàn bộ ảnh. Dice, IoU, Recall, Precision và Specificity là **Segmentation Metrics**, đo mức độ trùng khớp pixel với mask tham chiếu; chúng không phải và không đại diện cho Diagnostic Accuracy hay kết luận lâm sàng. Vùng dự đoán được gọi là “vùng được mô hình phân đoạn”; báo cáo không gán tên bệnh học.

Các số liệu theo thư mục nguồn được lưu trong [`test_metrics_by_source.csv`](../../evaluation/milestone_3_2026-10-06/test_metrics_by_source.csv). Do các thư mục có ảnh trùng nội dung, các hàng theo nguồn có thể chồng lấp và không được diễn giải như kết quả trên các cohort độc lập.

### Ứng viên U-Net++ — so sánh trên Validation

Sau khi hoàn tất lượt Standard U-Net, đã huấn luyện thêm ứng viên U-Net++ với encoder ResNet34 pretrained. Trên cùng 541 ảnh Validation, Dice đạt **0,8170**, so với **0,6724** của Standard U-Net (chênh lệch tuyệt đối +0,1446). Ứng viên đạt IoU **0,7323**, Recall **0,8345**, Precision **0,8545**, Specificity pixel **0,9851** ở threshold 0,5. Cấu hình dùng grayscale CLAHE, Letterbox 512×512 và chuẩn hóa grayscale theo ImageNet mean/std.

Train Dice tại epoch được chọn là **0,9371**, cao hơn Validation Dice 0,8170 (khoảng cách 0,1200); đây là dấu hiệu cần lưu ý về khả năng quá khớp trên tập dữ liệu nhỏ. Kết quả Validation tốt hơn là bằng chứng để tiếp tục xem xét ứng viên, chưa đủ để khẳng định mô hình tổng quát hóa tốt hơn trên cohort độc lập.

Để đối chiếu công bằng hơn, Standard U-Net được huấn luyện lại với cùng grayscale ImageNet mean/std và cùng các thiết lập còn lại. Trên cùng Validation, Standard U-Net đạt Dice **0,7383** tại epoch 28; U-Net++ đạt **0,8170**, chênh **+0,0787** Dice tuyệt đối. Vẫn còn khác biệt về khởi tạo: Standard U-Net bắt đầu ngẫu nhiên, U-Net++ dùng encoder ResNet34 pretrained ImageNet. Do đó đây là so sánh cấu hình mô hình, chưa phải ablation thuần kiến trúc.

Đây là kết quả chọn mô hình trên Validation, chưa phải kết quả Test; Test không được truy cập trong các lượt huấn luyện và tích hợp candidate này. Checkpoint ứng viên [`unetplusplus_resnet34_best.pth`](../../checkpoints/unetplusplus_resnet34_2026-10-06/unetplusplus_resnet34_best.pth) đạt SHA-256 `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76`; nạp lại bằng `strict=True` không có missing/unexpected keys. Candidate đã được nạp qua manifest riêng để kiểm thử Web Prototype, trong khi manifest mặc định và checkpoint gắn với Test metrics vẫn giữ nguyên `417828fa…`. Bằng chứng tại [`browser_smoke_2026-10-06_unetplusplus_candidate.json`](../../evaluation/milestone_3_2026-10-06/browser_smoke_2026-10-06_unetplusplus_candidate.json) và [`api_latency_validation_unetplusplus_candidate.json`](../../evaluation/milestone_3_2026-10-06/api_latency_validation_unetplusplus_candidate.json). So sánh đầy đủ tại [`model_comparison_validation.json`](../../evaluation/milestone_3_2026-10-06/model_comparison_validation.json) và cấu hình/lịch sử huấn luyện trong thư mục checkpoint.

## 4. Kiểm thử hệ thống và Human-in-the-Loop

Sau khi cập nhật manifest lựa chọn, backend đã nạp checkpoint SHA-256 `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d` thành công thành Standard U-Net trên CUDA. Smoke Test đạt **PASS** trên Chrome, dùng ảnh Validation `217_41.JPG`; kịch bản bao gồm upload, inference retry, Original/Mask/Overlay, responsive layout, Brush/Eraser, pan, opacity, undo/reset, review retry, lưu mask và mở lại ca. Không có lỗi console bất ngờ. Bản smoke test trước đó của checkpoint `5e14be…` được giữ riêng tại [`browser_smoke_2026-10-06_checkpoint_5e14be.json`](../../evaluation/milestone_3_2026-10-06/browser_smoke_2026-10-06_checkpoint_5e14be.json).

API inference end-to-end được đo trên Validation bằng 5 yêu cầu sau một lượt warm-up, cùng một ảnh (`OTU_CEUS_113`): median **78,23 ms**, p95 **81,40 ms**. Đây là phép đo cục bộ với cỡ mẫu nhỏ, dùng để xác nhận vận hành và không đại diện cho phân bố độ trễ trên mọi ảnh/thiết bị. Chi tiết tại [`api_latency_validation_417828fa.json`](../../evaluation/milestone_3_2026-10-06/api_latency_validation_417828fa.json).

Test metrics, checkpoint tích hợp và Browser Smoke Test hiện cùng gắn với SHA `417828fa…`. Manifest Mốc 2 của `5e14be…` được lưu nguyên trạng tại [`selected_model_milestone_2_2026-10-05.json`](../../evaluation/archive/selected_model_milestone_2_2026-10-05.json).

Candidate U-Net++ được chạy ở cấu hình tách biệt bằng biến môi trường `MODEL_SELECTION_MANIFEST`; manifest chính thức không bị thay đổi. Browser Smoke Test đạt **PASS** với checkpoint SHA `ce758032…` trên ảnh Validation `1098.JPG`, gồm upload, inference, Original/Mask/Overlay, Brush/Eraser, undo, lưu và mở lại ca; không có lỗi console ngoài dự kiến. Đo độ trễ sau 1 warm-up và 5 request trên cùng ảnh cho API median **78 ms**, p95 **86,4 ms**; client end-to-end median **101,4 ms**, p95 **109,8 ms**. Đây là phép đo mô tả trên một ảnh và năm lần lặp, không đại diện cho phân bố hiệu năng trên nhiều ảnh hoặc thiết bị.

Kiểm thử tự động xác nhận hành vi phần mềm theo kịch bản đã định; chưa đo mức độ chấp nhận, thời gian thao tác hoặc tính hữu dụng với bác sĩ. Biểu mẫu thu thập phản hồi đã chuẩn bị tại [Biểu mẫu đánh giá HITL](Bieu_Mau_Danh_Gia_HITL_Moc_3.md). Kết quả cần được điền bởi người đánh giá thực tế.

## 5. Vấn đề còn lại và kế hoạch tiếp theo

| Vấn đề / giới hạn | Hướng xử lý |
|---|---|
| Chưa có Patient/Case ID nguồn đã xác thực | Ghi rõ kết quả ở mức độc lập ảnh; chỉ tuyên bố patient-level split khi có mapping được đơn vị dữ liệu xác nhận |
| Có 35 ảnh liên quan fallback mask bị loại | Giữ provenance; chỉ đưa lại vào đánh giá khi có nhãn pixel-level hợp lệ được xác nhận |
| Chưa có đánh giá HITL bởi chuyên viên y tế | Mời người đánh giá phù hợp, ghi thời gian thao tác, số lần chỉnh sửa, mức độ hữu dụng và nhận xét bằng biểu mẫu; không suy diễn kết quả khi chưa thu thập |
| Test split đã từng được dùng với baseline | Báo cáo đầy đủ lịch sử sử dụng; không tiếp tục dùng Test để chọn mô hình/ngưỡng; nếu cần đánh giá xác nhận mới, thiết lập cohort độc lập với nhãn được xác thực |

**Kết luận:** Project is not fully ready for Milestone 3. Cần xử lý 8 lỗi kiểm thử liên quan dữ liệu Mốc 1 bị thiếu, thống nhất lưu trữ/index và báo cáo sau thay đổi phạm vi. Patient/Case ID, phê duyệt nhãn chuyên gia và cohort độc lập là các bằng chứng còn thiếu. Nếu chưa tiếp cận được chuyên viên, báo cáo HITL chuyên môn là chưa thực hiện theo điều kiện trong kế hoạch của Thầy; không thay bằng kết quả kiểm thử trình duyệt.

## Cập nhật kiểm chứng trong đợt audit ngày 06/10/2026

U-Net++ được khóa cho nghiên cứu bằng tiêu chí Validation Dice, threshold 0,5, seed 42; model lock ở [`model_lock.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json). Quyết định chọn giữa các lượt đã có là retrospective; chưa có stability giữa nhiều seed. Cả U-Net++ và Standard U-Net comparator được nạp `strict=True`, chạy lại trên đủ 541 ảnh Validation; toàn bộ metric khớp số liệu lịch sử của từng lượt. Nguồn nhãn ở mức file/mapping đã kiểm tra; chưa có tài liệu chuyên gia xác nhận nhãn để diễn giải hiệu quả lâm sàng.

Phân tích U-Net++ có 15 panel Validation: 5 Dice cao nhất, 5 FP lớn nhất và 5 FN lớn nhất; bảng ghi ảnh, reference mask, prediction, overlay, threshold và SHA. Minh chứng tại [`error_analysis_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/error_analysis_summary.json). Các nhận xét chỉ mô tả vùng dự đoán thiếu/thừa.

Benchmark mới dùng 24 ảnh Validation × 3 request sau một warm-up mỗi ảnh, 72 request thành công trên RTX 3050 Laptop. Client HTTP p50 **146,47 ms**, p95 **170,54 ms**; server preprocessing + engine p50 **109 ms**, p95 **122 ms**. Có instrumentation và đồng bộ CUDA nên không so sánh trực tiếp với phép đo nhỏ lịch sử; không tuyên bố SLA. Các thành phần đo, môi trường và command ở [`api_latency_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/api_latency_summary.json).

Browser smoke mới chạy ảnh Validation `1098.JPG`, SHA `ce758032…`, đạt PASS trong DB kiểm thử riêng. Đây là technical UI test, không có người tham gia chuyên môn. Toàn bộ Test result cũ vẫn gắn riêng với Standard U-Net. Các mô tả candidate chưa khóa ở phần lịch sử bên dưới được thay thế bởi model lock mới; manifest mặc định vẫn giữ Standard U-Net.

## Bổ sung lịch sử: so sánh cấu hình Standard U-Net và U-Net++ trên Validation

Để giảm khác biệt về tiền xử lý giữa hai ứng viên, Standard U-Net được huấn luyện lại trên cùng 661 ảnh Train và 541 ảnh Validation với grayscale ImageNet normalization (mean=0,449; std=0,226), cùng augmentation, Combo Loss, AdamW, learning rate 1×10⁻⁴, batch size 2, seed 42, tối đa 30 epochs, patience 6 và threshold 0,5 như lượt U-Net++. Tập Test không được mở hoặc sử dụng.

| Ứng viên | Epoch tốt nhất | Dice | IoU | Recall | Precision | Specificity |
|---|---:|---:|---:|---:|---:|---:|
| Standard U-Net, normalization đã khớp | 28 | 0,7383 | 0,6264 | 0,8159 | 0,7444 | 0,9739 |
| U-Net++ + ResNet34 ImageNet encoder | 30 | **0,8170** | **0,7323** | 0,8345 | **0,8545** | **0,9851** |

Trong hai cấu hình đã chạy, U-Net++ cao hơn Standard U-Net 0,0787 Dice tuyệt đối trên Validation. Checkpoint Standard U-Net được nạp lại bằng `strict=True`; các metric tính lại trên Validation khớp với lịch sử huấn luyện. Hồ sơ phép so sánh và SHA checkpoint được lưu tại [`model_comparison_validation.json`](../../evaluation/milestone_3_2026-10-06/model_comparison_validation.json), còn cấu hình và lịch sử huấn luyện nằm cạnh từng checkpoint.

Đây là so sánh giữa hai cấu hình mô hình, chưa phải ablation thuần kiến trúc: Standard U-Net khởi tạo ngẫu nhiên, trong khi U-Net++ dùng encoder ResNet34 pretrained trên ImageNet. Khoảng cách Train–Validation Dice lần lượt là 0,0688 và 0,1200; vì vậy kết quả tốt hơn của U-Net++ là căn cứ để chọn ứng viên cho kiểm thử tích hợp trên Validation, chưa chứng minh khả năng tổng quát hóa trên cohort độc lập. Ứng viên U-Net++ chưa thay thế checkpoint hiện hành, và chưa được dùng để tạo hoặc điều chỉnh kết quả Test.
