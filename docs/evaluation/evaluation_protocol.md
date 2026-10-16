# Quy trình Đánh giá Định lượng Milestone 3 v1 (Frozen Protocol)

> **Mã văn bản**: `EVAL-PROTOCOL-2026-10-16-V1`  
> **Phiên bản**: 1.0 (Khóa cố định trước các lượt đánh giá mới)  
> **Trạng thái**: Đã phê duyệt kỹ thuật — Áp dụng tất định

---

## 1. Mục tiêu và Nguyên tắc Cốt lõi

1. **Chống rò rỉ dữ liệu (No Data Leakage)**: Tách biệt nghiêm ngặt ở cấp độ bệnh nhân (Patient-Level Split). Tuyệt đối không dùng dữ liệu Test để tinh chỉnh mô hình, chọn ngưỡng hoặc điều chỉnh siêu tham số.
2. **Kỷ luật trung thực y tế (Clinical Grounding)**: Không giả lập thông tin bệnh nhân, nhãn chuyên gia hay tự động chuyển đổi mã định danh ẩn danh thành ca lâm sàng khi chưa có hồ sơ xác minh nguồn.
3. **Tính nhất quán giữa Serving và Evaluation**: Động cơ suy luận dùng chung kiến trúc Standard U-Net, tham số tiền xử lý Letterbox 512×512, CLAHE clip 2 / grid 8, ngưỡng nhị phân $\ge 0.5$, và tính điểm trên không gian tọa độ gốc (Native Image Space).

---

## 2. Thông số Protocol đã khóa (`milestone3_v1.json`)

| Tham số | Giá trị khóa | Ghi chú kỹ thuật |
|---|---|---|
| **Mô hình phục vụ** | Standard U-Net (PyTorch) | Khóa strict state_dict |
| **Đường dẫn Checkpoint** | `checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/baseline_unet_best.pth` | SHA256: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d` |
| **Tiền xử lý** | Grayscale $\to$ Letterbox 512×512 $\to$ CLAHE (clip 2.0, grid 8×8) $\to$ Scale /255 | Tương đương giữa API và Offline |
| **Toán tử suy luận** | $\sigma(z) \ge 0.5$ | Không lọc hình thái học, không bỏ connected components |
| **Không gian tọa độ** | Native Image Resolution | Inverse letterbox nội suy Nearest-Neighbor |
| **Chỉ số đánh giá** | Dice, IoU, Recall, Precision, Specificity, HD95 (px) | Tính theo chuẩn `evaluation/segmentation_metrics.py` |
| **Cơ chế tái lập** | Seed cố định: 42, 2.000 lần Bootstrap theo bệnh nhân | Xác định thống kê |

---

## 3. Phân loại Cohort và Cổng Dữ liệu (Data Independence Gate)

1. **`validation_dry_run` (Tập Thẩm định - 541 mẫu)**:
   - Dùng để chạy thử nghiệm pipeline, kiểm toán kỹ thuật và kiểm tra tính tương đương của kết quả suy luận.
   - Trạng thái: Sẵn sàng thực thi.
2. **`retrospective_test_replay` (Tập Test lịch sử - 402 mẫu)**:
   - Dùng để tái lập và đánh giá hồi cứu đối với bộ Test 402 ảnh đã xem trước đây trong quá trình phát triển.
   - Nhãn minh bạch: Báo cáo rõ là hồi cứu (`prior_test_access: true`), không tuyên bố là thử nghiệm độc lập.
3. **`independent_test` (Tập Kiểm thử Độc lập Cấp độ Bệnh nhân)**:
   - Bắt buộc phải có: `patient_id` nguồn, bằng chứng định danh bệnh nhân (`identity_evidence`), hồ sơ nhãn chuyên gia (`label_evidence`), và chứng chỉ lịch sử mô hình (`development_history_evidence`).
   - Cổng tự động kiểm tra: Nếu thiếu bằng chứng hoặc phát hiện trùng lặp bệnh nhân với tập huấn luyện/thẩm định, trạng thái trả về là `BLOCKED`, tiến trình đánh giá lập tức dừng trước khi nạp model.

---

## 4. Lệnh Thực thi và Kiểm toán

Kiểm toán dữ liệu và tiền kiểm trước khi chạy:
```powershell
.venv\Scripts\python.exe -m evaluation.protocol --root . --protocol evaluation/protocols/milestone3_v1.json --manifest evaluation/manifests/validation_v1.csv --run-kind validation_dry_run --output evaluation/milestone_3_final/data_audit/validation_audit
```
