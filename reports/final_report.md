# Báo cáo huấn luyện hợp nhất Vinmec — 06/10/2026

**Trạng thái: TRAINING COMPLETED; TEST EVALUATED ONCE**

## Dataset và mapping

Sáu thư mục có tổng cộng **4.997 file ảnh vật lý**. Khử trùng lặp bằng SHA-256 còn **1.639 ảnh nội dung duy nhất**; các nguồn là các bản sao/tập con chồng lặp, không phải sáu tập độc lập. 35 ảnh được liên kết với mask fallback rỗng Mốc 1 đã bị loại khỏi index huấn luyện vì bất đồng với nhãn nguồn. Còn **1.604 ảnh** với một target nhị phân đã xác thực cho mỗi ảnh. Trong các bản sao còn lại, không phát hiện sai khác mask sau khi nhị phân hóa.

| Nguồn | File ảnh vật lý |
|---|---:|
| `Vinmec` | 1.639 |
| `Vinmec_2D` | 1.202 |
| `Vinmec_CEUS` | 170 |
| `vinmec_m1_307` | 307 |
| `vinmec_ovarian` | 1.372 |
| `vinmec_splits` | 307 |

Index giữ provenance của cả sáu nguồn tại `dataset/index.csv`; split dành cho dataloader ở `ai_training/splits/unified_vinmec_clean_2026-10-06/`.

## Split và giới hạn định danh

| Train | Validation | Test | Tổng |
|---:|---:|---:|---:|
| 661 | 541 | 402 | 1.604 |

Split giải quyết chứng cứ mâu thuẫn theo thứ tự `Test > Validation > Train`; do đó một ảnh từng có bằng chứng Test không được đưa vào Train. Không có SHA ảnh giao nhau giữa ba split. Dataset nguồn không có Patient/Case ID đã xác thực, nên chỉ xác nhận được độc lập ở mức ảnh/hash; chưa chứng minh độc lập ở mức bệnh nhân.

Số record theo provenance trong từng split (các hàng nguồn chồng lặp, không cộng thành tổng):

| Nguồn provenance | Train | Validation | Test |
|---|---:|---:|---:|
| `Vinmec` | 661 | 541 | 402 |
| `Vinmec_2D` | 445 | 329 | 397 |
| `Vinmec_CEUS` | 54 | 107 | 5 |
| `vinmec_m1_307` | 81 | 87 | 104 |
| `vinmec_ovarian` | 499 | 436 | 402 |
| `vinmec_splits` | 81 | 87 | 104 |

## Huấn luyện

- Framework/mô hình: PyTorch Standard U-Net, base filters 32.
- Tiền xử lý: grayscale, Letterbox 512×512, CLAHE; augmentation chỉ áp dụng đồng bộ trên Train.
- Loss: 0,5 BCE + 0,5 Soft Dice; optimizer AdamW, learning rate 0,001, weight decay 1e-4.
- Scheduler: CosineAnnealingLR; tối đa 12 epoch, patience 8; seed 42; batch size 2.
- Thiết bị: NVIDIA GeForce RTX 3050 Laptop GPU, CUDA; thời gian 763,95 giây.
- Best checkpoint: epoch 10, Validation Dice **0,6366**. Test không tham gia huấn luyện hoặc chọn checkpoint.

## Đánh giá Test

Checkpoint tốt nhất được nạp với `strict=True`, ngưỡng 0,5; Test 402 ảnh được chạy một lần sau khi khóa checkpoint.

| Metric phân đoạn điểm ảnh | Test |
|---|---:|
| Foreground Dice | 0,7016 ± 0,2128 |
| Foreground IoU | 0,5772 ± 0,2280 |
| Recall/Sensitivity | 0,7596 |
| Precision | 0,7382 |
| Specificity toàn pixel | 0,9715 |
| Test loss | 0,2523 |

402/402 target trong split này có foreground; không có Empty Mask case (`empty_mask_specificity` không áp dụng). Specificity là tỷ lệ pixel nền được nhận diện đúng. Các metric trên đo chất lượng phân đoạn pixel, **không phải Diagnostic Accuracy** và không xác nhận chẩn đoán lâm sàng. Các vùng mask chỉ là vùng được phân đoạn theo nhãn dữ liệu.

Metric theo source membership có trong `evaluation/unified_vinmec_2026-10-06/test_metrics_by_source.csv`; các membership chồng lặp do ảnh trùng giữa nguồn nên không phải các nhóm độc lập.

## Artifacts và xác minh

- Best/last checkpoint và cấu hình: `checkpoints/unified_vinmec_2026-10-06/`.
- Training history: `checkpoints/unified_vinmec_2026-10-06/vinmec_unet_best_history.json`.
- Test summary, per-image metrics, top ca tốt/lỗi, và 402 prediction masks: `evaluation/unified_vinmec_2026-10-06/`.
- Test summary liên kết checkpoint SHA-256 `509b050f633f765b03419d1615397557889c9c647dd24d500446fa3495d8198b`.
- Unit tests: **68 passed** (4 dependency/runtime warnings); Ruff trên các file thay đổi: **pass**.

## Hạn chế còn lại

Không có Patient/Case ID nguồn; kết quả không chứng minh patient-level independence. 35 ảnh fallback đã loại khỏi nghiên cứu huấn luyện này và vẫn cần xác minh nguồn gốc nếu muốn sử dụng trong nghiên cứu khác. Test chỉ là đánh giá segmentation trên split ảnh đã tạo theo quy tắc nêu trên; chưa có đánh giá bác sĩ hoặc hiệu lực chẩn đoán.
