# Thiết kế kiểm chứng và cải thiện độ chính xác phân đoạn siêu âm buồng trứng

Ngày: 09/10/2026. Trạng thái: chờ người dùng duyệt đặc tả trước khi sửa pipeline hoặc chạy thí nghiệm mới.

## Mục tiêu và ranh giới

Mục tiêu là tăng mức khớp của mask AI với mask tham chiếu trên ảnh siêu âm buồng trứng, đo bằng Dice theo ảnh, đồng thời theo dõi IoU, recall và precision. Đây là bài toán phân đoạn; các chỉ số này không đo độ chính xác chẩn đoán lành tính/ác tính. Người rà soát vẫn quyết định mask cuối cùng trong quy trình HITL.

Giữ Letterbox 512×512, ảnh xám + CLAHE, Combo Loss 0,5 BCE + 0,5 Soft Dice và ngưỡng suy luận được khóa theo từng checkpoint. Không dùng Test để chọn checkpoint, ngưỡng hay biến thể huấn luyện. Không sửa hoặc ghi đè split, checkpoint và kết quả Mốc 3 lịch sử.

## Bằng chứng đầu vào

- `[VERIFIED]` Split đang khóa có 661 Train, 541 Validation, 402 Test. `patient_id` trong cả Train và Validation CSV đang để trống. Nguồn: `ai_training/splits/unified_vinmec_clean_2026-10-06/` và `manifest.json`.
- `[VERIFIED]` Checkpoint U-Net++/ResNet34 SHA-256 `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76` tồn tại; Validation Dice lịch sử/replay là 0,8170 trên 541 ảnh ở ngưỡng 0,5. Model đang được khóa cho nghiên cứu, chưa có Test metric riêng. Nguồn: `evaluation/milestone_3_audit_2026-10-06/validation_lock/`.
- `[VERIFIED]` Standard U-Net đối chiếu cùng normalization có Validation Dice 0,7383; prototype mặc định dùng một Standard U-Net khác với Validation Dice 0,6724. Các số này thuộc checkpoint khác nhau và không được gộp.
- `[VERIFIED]` Workbook `docs/reports/Mau_Xin_Danh_Muc_Anh_Patient_Case_ID_2026-10-07.xlsx` chứa mã Patient/Case cho 1.639 dòng, nhưng hai cột trạng thái mask và mask rỗng đều chưa được điền. Các mã trong workbook giao bằng 0 giữa ba split sau khi nối theo ảnh; điều này chỉ chứng minh sự tách biệt của **chuỗi mã hiện có**.
- `[PARTIALLY VERIFIED]` Nguồn và quy tắc cấp mã Patient/Case chưa có chứng từ bàn giao. Hồ sơ duyệt chuyên môn của từng mask chưa có. Báo cáo đã lưu: `docs/reports/M3_Bang_Chung_Du_Lieu_2026-10-08.md` và `docs/reports/Doi_Chieu_Ho_So_Duyet_Mask_2026-10-08.md`.
- `[VERIFIED]` Kiểm toán hiện có ghi 59 cặp ảnh gần trùng xuyên split theo pHash/dHash ≤ 4, gồm 22 cặp có tương quan sau resize ≥ 0,95. Đây là ứng viên cần xem xét, không chứng minh chung bệnh nhân.

## Phương án và quyết định

1. Chỉ tối ưu ngưỡng trên Validation hiện tại: ít tốn thời gian nhưng không xử lý giới hạn danh tính và chất lượng nhãn.
2. Kiểm chứng dữ liệu trước, sau đó so sánh mô hình trên Validation với giao thức khóa: được chọn vì kết quả có thể truy vết và không biến Test cũ thành Test mới.
3. Thử thêm nhiều kiến trúc lớn: tăng chi phí GPU 4 GB và số phép thử khi nhãn, split còn bất định; để sau khi phương án 2 có kết quả.

Phương án 2 là phạm vi của đặc tả này. Việc chọn phương án không hàm ý sẽ đạt một giá trị Dice cụ thể.

## Luồng kiểm chứng dữ liệu

1. Đối chiếu ảnh trong split với workbook qua nguồn `2d/3d` và tên file, kiểm SHA-256 ảnh, phát hiện thiếu/nhân đôi mã và giao mã giữa split. Báo cáo chỉ xuất số lượng và mã mẫu băm; không xuất mã bệnh nhân vào artifact công khai.
2. Giữ trạng thái `patient_identity_unverified` cho đến khi đơn vị dữ liệu xác nhận một mã Patient ổn định cho mọi ảnh của cùng người, quy tắc Case ID, nguồn xuất và ngày bàn giao. Nếu chưa xác nhận, mọi phân tích trên split hiện tại chỉ mang nhãn `image_level_exploratory`.
3. Kiểm hồ sơ mask theo `scripts/audit_mask_approval_evidence.py` khi có ledger nguồn. `FILES_MATCH` chỉ xác nhận byte/hash; không tự đổi thành `clinical_approval_verified`.
4. Xem xét các cặp gần trùng và ca Dice thấp với người có chuyên môn. Ghi nhận nhãn sai/không chắc chắn bằng quyết định có nguồn; không tự sửa mask tham chiếu dựa trên prediction.

## Giao thức thí nghiệm so sánh

- Baseline khóa: U-Net++/ResNet34 SHA trên, threshold 0,5; Standard U-Net đối chiếu được giữ như mốc lịch sử, không dùng checkpoint mặc định 0,6724 để thay thế mốc 0,7383.
- Thử lần lượt một biến trên cùng Train/Validation: (a) ngưỡng dự đoán trên Validation; (b) thời lượng huấn luyện nếu đường cong vẫn cải thiện ở epoch 30; (c) augmentation sau khi rà ca lỗi. Mỗi lượt tạo thư mục mới, ghi seed, phiên bản code, hash split, checkpoint, tiền xử lý, biến được thay và thời gian chạy. Không ghi đè checkpoint khóa.
- Dùng mean per-image Dice làm tiêu chí chính, kèm IoU/recall/precision, số ca Dice < 0,5, kết quả theo nhóm nguồn `2d/3d` và kích thước vùng tham chiếu. Chỉ so sánh cặp ảnh giống nhau và cùng độ phân giải đánh giá. Đối với bệnh nhân đã xác minh, khoảng tin cậy được bootstrap theo bệnh nhân; trước đó chỉ báo phân bố theo ảnh, không gọi là CI độc lập theo bệnh nhân.
- Chọn một ứng viên bằng Validation sau khi đã định trước số phép thử. Không chọn bằng Test 402 ảnh đã được xem trước; Test này chỉ dùng để báo kết quả lịch sử có nhãn. Cần một cohort bệnh nhân mới, chưa được dùng cho lựa chọn, để ước lượng cuối cùng.
- Mô hình chỉ được đề nghị chuyển vào prototype khi có cải thiện trên đánh giá đáng tin cậy, kiểm tra đúng checkpoint/normalization/threshold ở API, và quy trình HITL vẫn buộc người dùng rà soát. Không tự động thay manifest mặc định trong pha nghiên cứu.

## Lỗi và giới hạn cần xử lý

- Thiếu hoặc mâu thuẫn mã Patient/Case: dừng tuyên bố patient-level; không sinh mã giả để hợp thức hóa split.
- Thiếu hoặc không khớp hash ảnh/mask: loại khỏi lượt thí nghiệm mới và báo danh sách mẫu; không sửa dữ liệu gốc.
- Mask rỗng không rõ ý nghĩa: không coi là ca âm tính lâm sàng.
- Hết VRAM hoặc huấn luyện gián đoạn: giữ log và checkpoint hiện có; không tự đổi batch/kiến trúc rồi trộn kết quả vào cùng lượt.
- Nhiều lần thử trên Validation có nguy cơ overfit vào Validation; khóa số thử, lưu mọi kết quả và xác nhận trên cohort mới.

## Tiêu chí nghiệm thu của pha này

1. Có báo cáo kiểm toán nguồn và mức xác minh của mã/nhãn, không lộ mã Patient trong output.
2. Có giao thức so sánh và lệnh tái lập được khóa trước thí nghiệm; các artifact mới nằm trong thư mục riêng.
3. Có kết quả Validation so cặp và kiểm thử suy luận API nếu chạy thí nghiệm; chỉ phát biểu cải thiện khi lệnh đã chạy, log và hash được kiểm tra.
4. Báo rõ phần chưa thể xác minh và đầu vào cần từ đơn vị dữ liệu. Không công bố độ chính xác chẩn đoán từ Dice phân đoạn.
