# Model Card: Ovarian Ultrasound Segmentation Prototype

Cập nhật theo kiểm chứng ngày 06/10/2026. Mục tiêu: phân đoạn vùng nghi ngờ để người dùng rà soát qua HITL. Không suy luận loại bệnh từ hình học mask.

## Phiên bản và phạm vi bằng chứng

| Vai trò | Mô hình / SHA | Dữ liệu / bằng chứng |
|---|---|---|
| Baseline lịch sử Mốc 1 | Standard U-Net `44b862…`; xem archive và báo cáo Mốc 1 | 307 ảnh, split 215/46/46; metric lịch sử. Các đường dẫn ảnh–mask hiện không có trong workspace. |
| Tích hợp lịch sử Mốc 2 | Standard U-Net `5e14be…` | Chọn bằng Validation 123 ảnh của lượt riêng; không phải mô hình huấn luyện trên bộ Mốc 1. Manifest lịch sử ở `evaluation/archive/`. |
| Prototype mặc định hiện tại | Standard U-Net `417828fa…` | `evaluation/selected_model.json`; Validation Dice 0,6724; Test 402 ảnh đã dùng trước đó. |
| Mô hình nghiên cứu đã khóa bằng Validation | U-Net++ / ResNet34 ImageNet `ce758032…` | `evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json`; chưa có Test metric. Có kiểm chứng riêng trên prototype. |

SHA-256 đầy đủ của model lock: `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76`.

## Model lock nghiên cứu

- SMP U-Net++, ResNet34 pretrained ImageNet; một kênh ảnh, một kênh logits.
- OpenCV grayscale, Letterbox 512×512, CLAHE clip limit 2 / grid 8×8; chia 255 rồi grayscale normalization mean 0,449 / std 0,226.
- Threshold 0,5; sigmoid và ngưỡng nhị phân, không morphology.
- Train 661, Validation 541; seed 42; batch size 2; 30 epochs, best epoch 30; Combo Loss 0,5 BCE + 0,5 Soft Dice; AdamW LR 1e-4, Cosine Annealing.
- Nạp lại `strict=True`; Validation chạy lại khớp log huấn luyện. Quyết định chọn giữa các lượt đã có là retrospective, không phải preregistered.

| Cấu hình | Validation Dice | IoU | Recall | Precision | Pixel Specificity |
|---|---:|---:|---:|---:|---:|
| Standard U-Net, cùng normalization, random initialization | 0,7383 | 0,6264 | 0,8159 | 0,7444 | 0,9739 |
| U-Net++ / ResNet34 ImageNet | 0,8170 | 0,7323 | 0,8345 | 0,8545 | 0,9851 |

Nguồn: `validation_summary.json` và `standard_comparator_validation.json` trong model lock directory. Đây là computational segmentation agreement với nhãn tham chiếu được cung cấp; nguồn phê duyệt chuyên gia của nhãn chưa được xác minh. Các độ đo không đại diện cho Diagnostic Accuracy.

Train–Validation Dice gap lần lượt 0,0688 và 0,1200. Có khác biệt khởi tạo encoder; chỉ có một seed, chưa có bằng chứng stability hoặc ưu thế trên cohort độc lập. Train metric có augmentation nên gap không đo trên hai phân bố tiền xử lý hoàn toàn giống nhau.

## Test lịch sử

`evaluation/milestone_3_2026-10-06/test_summary.json` gắn riêng với Standard U-Net `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`: Dice 0,7297; IoU 0,6186; Recall 0,7311; Precision 0,8129; Pixel Specificity 0,9836. Cả 402 reference mask có foreground; không có nhóm Empty Mask hợp lệ để báo riêng. Không chuyển metric này sang U-Net++.

Test đã dùng đánh giá baseline trước refinement: **evaluation on previously used Test set**. Mã lựa chọn và log khai báo dùng Validation; chưa có access log đủ để chứng minh mọi truy cập trong toàn bộ lịch sử. Patient-level independence chưa được xác minh.

## Dữ liệu và giới hạn

1. Phạm vi hiện tại do chủ dự án chốt: `dataset/Vinmec/Vinmec_2d` và `Vinmec_3d`. Có 1.604 cặp chính đọc được (1.438 / 166); SHA nội dung ảnh rời nhau giữa split. Hash không loại trừ các ảnh khác nhau của cùng bệnh nhân.
2. 1.881 tham chiếu bản sao nhãn lịch sử bị thiếu. Các target chính và bản sao còn tồn tại khớp nhị phân. Thiếu nguồn xác nhận Patient/Case ID và phê duyệt nhãn pixel bởi chuyên gia.
3. 35 bản ghi fallback đã loại khỏi split hợp nhất. File fallback và hồ sơ provenance ban đầu không có ở đường dẫn khai báo. Không gọi chúng là Ground Truth hoặc ca âm tính.
4. `dataset/index.csv` và báo cáo Mốc 2 bị xóa khỏi working tree trong lúc audit. Snapshot Git được giữ trong audit backup. Index hai nguồn được xuất riêng, không ghi đè việc xóa.
5. HITL hiện được kiểm chứng kỹ thuật; chưa có kết quả chuyên viên thực tế. Confirm ghi nhận thao tác, không tự tạo Ground Truth được duyệt.
6. Chỉ đo mm/thể tích khi có pixel spacing được hiệu chuẩn. Chưa có xác nhận chẩn đoán, triển khai lâm sàng hoặc SLA.

## Hiệu năng và tái lập

Benchmark U-Net++: RTX 3050 Laptop, PyTorch 2.6.0+cu124; 24 ảnh Validation, 1 warm-up/ảnh, 3 request/ảnh, tổng 72 request. Client HTTP p50 146,47 ms; p95 170,54 ms; instrumentation dùng perf_counter và đồng bộ CUDA. Phép đo nhỏ lịch sử được giữ riêng.

SHA split, checkpoint, config, thời gian chạy, command và môi trường ở model lock directory. Error analysis có 15 panel Validation và bảng FP/FN. Báo cáo kiểm toán: `docs/reports/Kiem_Toan_Moc_3_2026-10-06.md`.
