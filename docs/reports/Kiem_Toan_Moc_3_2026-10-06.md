# Kiểm toán minh chứng và mức độ sẵn sàng Mốc 3

**Sinh viên:** Nguyễn Hữu Dũng — **MSV:** 11235559  
**Đề tài:** Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop  
**Ngày kiểm chứng:** 06/10/2026; thời gian chạy chi tiết dùng UTC trong JSON, giờ Việt Nam = UTC+7.  
**Git baseline:** `383def17be49c62f172017cb96af308438c7eaad`.  
**Phạm vi hiện tại được chủ dự án chỉ định:** `dataset/Vinmec/Vinmec_2d` và `dataset/Vinmec/Vinmec_3d`.

## 1. Executive Summary

Đã kiểm kê 3.463 artifact, kiểm tra SHA/split, khôi phục chọn lọc 8 summary/CSV lịch sử từ Git, xác minh 1.604 cặp chính và xuất index phiên bản riêng cho hai nguồn. Standard U-Net comparator và U-Net++ được nạp lại `strict=True`, đánh giá trên 541 ảnh Validation; metric khớp log huấn luyện. U-Net++ được khóa cho nghiên cứu bằng Validation; có prediction, 15 panel phân tích lỗi, benchmark 72 request và Browser Smoke Test PASS ở cấu hình tách biệt.

Chưa đủ cơ sở xác nhận hoàn tất Mốc 3: pytest toàn suite hiện **67 passed / 8 failed**; bộ ảnh–mask Mốc 1 không còn tại đường dẫn khai báo. Chưa xác minh được Patient/Case ID nguồn hoặc hồ sơ chuyên gia phê duyệt nhãn. Không tìm được cohort Test mới độc lập; Test 402 ảnh đã được đánh giá trước đó. Không có kết quả HITL bởi chuyên viên thực tế. Các giới hạn này được giữ trong kết luận, không thay bằng số liệu tạo mới.

Lượt kiểm toán không huấn luyện thêm, không chạy suy diễn/metric mới trên Test, không sửa dataset/split/trọng số. Các định danh dùng trong kiểm thử phần mềm chỉ thuộc DB kiểm thử, không được đưa vào dataset hoặc xem là Patient ID nguồn.

## 2. Evidence Inventory

Inventory đầy đủ có đường dẫn, hash, kích thước, timestamp và trạng thái Git: [`evidence_inventory.csv`](../../evaluation/milestone_3_audit_2026-10-06/evidence_inventory.csv). Eligibility chung trong inventory không tự xác nhận tính hợp lệ lâm sàng; bảng dưới xác định phạm vi của các artifact chính.

| Artifact | Đường dẫn | Version/hash và trạng thái | Mục đích / liên hệ |
|---|---|---|---|
| Split hợp nhất đã khóa | `ai_training/splits/unified_vinmec_clean_2026-10-06/` | 661/541/402; hash bên dưới | Đầu vào của các checkpoint so sánh; không đổi split |
| Index hai nguồn hiện tại | [`active_two_source_index.csv`](../../evaluation/milestone_3_audit_2026-10-06/active_two_source_index.csv) | SHA `009d6307f8500bc622b6fffae10d957d1c9901b34e7710b12a0069a07db16521` | Mapping trực tiếp theo filename trong cùng thư mục annotations; liên hệ split bằng SHA nội dung |
| Provenance mask chính | [`mask_provenance.csv`](../../evaluation/milestone_3_audit_2026-10-06/verified_data/mask_provenance.csv) | 1.604 cặp đọc được | Mapping/bytes được kiểm tra; chuyên gia phê duyệt nhãn chưa xác minh |
| Fallback records | [`fallback_mask_provenance.csv`](../../evaluation/milestone_3_audit_2026-10-06/verified_data/fallback_mask_provenance.csv) | 35 records, file hiện thiếu | Bản ghi kiểm toán hiện trạng; không phải hồ sơ tạo mask ban đầu |
| Model lock nghiên cứu | [`model_lock.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json) | U-Net++ SHA `ce758032…`; Test=null | Chọn bằng Validation; liên hệ config, seed, threshold và split hashes |
| Train/Validation history | `checkpoints/unetplusplus_resnet34_2026-10-06/` và `checkpoints/standard_unet_gray_imagenet_norm_2026-10-06/` | 30 epochs, seed 42 mỗi cấu hình | Historical training results; không tạo lượt train mới trong audit |
| Validation chạy lại | [`validation_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/validation_summary.json), [`standard_comparator_validation.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/standard_comparator_validation.json) | Timestamp, command, hardware, checkpoint/split SHA | Current result; tái lập chính xác metric từng lượt |
| Test lịch sử | `evaluation/unified_vinmec_2026-10-06/test_summary.json` và `evaluation/milestone_3_2026-10-06/test_summary.json` | `509b050f…` và `417828fa…` | Hai checkpoint đã đánh giá cùng Test; không phải Test của U-Net++ |
| Prediction/overlay và lỗi | [`error_analysis_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/error_analysis_summary.json) | 541 predictions, 15 panels | U-Net++ Validation; không gán nhãn bệnh học |
| Prototype/API | `backend/app/main.py`, `frontend/`, `evaluation/selected_model.json` | Default vẫn `417828fa…`; lock U-Net++ chạy riêng | Bằng chứng kỹ thuật; không tự chứng minh clinical usefulness |
| Latency | [`api_latency_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/api_latency_summary.json) | 24 ảnh / 72 request | Engineering measurement; có protocol và sample size |
| Browser smoke | [`browser_smoke_run.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/browser_smoke_run.json), `browser_smoke.txt` | PASS, `ce758032…`, ảnh `1098.JPG` | Technical UI test; DB riêng |
| HITL form | [Biểu mẫu HITL](Bieu_Mau_Danh_Gia_HITL_Moc_3.md) | Chưa có phiếu kết quả thực tế | Protocol cho người đánh giá; mẫu trống không là evidence kết quả |
| Báo cáo Mốc 1 | `docs/reports/BaoCaoTienDoMoc1_NguyenHuuDung_11235559(1).docx` | SHA `d11f3c177e8dd2255117ab0dc66b43770b43d86bbf78e5169f163b9141ce05fb` | Historical accepted baseline; không sửa metric lịch sử |
| Báo cáo Mốc 2 chính thức tại inventory | `docs/reports/BaoCaoTienDoMoc2_NguyenHuuDung_11235559_final.docx` | SHA `7d01feb22622ae502af1190f436d3e20cb11b0c16f11d4e3e1694baec8344ffc`; sau đó bị xóa khỏi working tree | File cuối dựa trên timestamp, nội dung và reference trong project_status; snapshot chính xác ở audit backup |
| Báo cáo Mốc 3 / trạng thái | [Báo cáo Mốc 3](Bao_Cao_Tien_Do_Moc_3_NguyenHuuDung_2026-10-06.md), `docs/project_status.json` | Đã bổ sung kết quả mới và blockers | Không còn kết luận technical complete khi full suite fail |
| Test log | [`pytest_latest.json`](../../evaluation/milestone_3_audit_2026-10-06/validation_lock/pytest_latest.json), `pytest_latest.txt` | 67 passed / 8 failed / 3 warnings | Latest full suite, command và thời gian thực tế |
| Git/deletions/backups | [`inventory_summary.json`](../../evaluation/milestone_3_audit_2026-10-06/inventory_summary.json), [`committed_deletions.csv`](../../evaluation/milestone_3_audit_2026-10-06/committed_deletions.csv), [`document_backups.json`](../../evaluation/milestone_3_audit_2026-10-06/document_backups.json) | Initial clean baseline; changes trong audit được giữ riêng | Truy vết, không reset hoặc force checkout |

**Danh sách cần giữ:** tất cả checkpoint/config/history, split snapshots, nhãn và ảnh nguồn, summary/per-image CSV, prediction/overlay dùng trong báo cáo, báo cáo chính thức và log kiểm toán. Giữ cả lịch sử trước PID để thể hiện giới hạn truy vết SHA.

**Khôi phục chọn lọc:** 8 summary/per-image CSV duy nhất từ commit `af5f407…`, gồm hai file mỗi nhóm `e2e_validation_2026-10-01`, `product_validation_2026-10-01`, `full_dataset_2026-10-03/Vinmec_Split_CEUS_val`, `retrain_2d_2026-10-03/previous_validation`. SHA khớp blob Git trong [`selective_recovery.json`](../../evaluation/milestone_3_audit_2026-10-06/selective_recovery.json). Tham chiếu `comparison.json → previous_validation/summary.json` hoạt động trở lại.

**Trùng/obsolete:** 461/469 artifact bị xóa ở commit gần nhất có bản sao byte giống hệt còn tồn tại. Không xóa thêm hoặc phục hồi hàng loạt. DOCX `Bao_Cao_Tien_Do_Moc_2_NguyenHuuDung_Final.docx` là bản khác, cũ hơn bản `11235559_final`; đã lưu snapshot, không đánh đồng nội dung.

## 3. Dataset & Provenance

| Nguồn hiện tại | Ảnh vật lý có binary target | Train | Validation | Test | Loại khỏi manifest |
|---|---:|---:|---:|---:|---:|
| Vinmec_2d | 1.469 | 607 | 434 | 397 | 31 |
| Vinmec_3d | 170 | 54 | 107 | 5 | 4 |
| Tổng | **1.639** | **661** | **541** | **402** | **35** |

Hai nguồn có 1.639 mapping image → annotation binary hợp lệ về file, shape và tính duy nhất; 1.604 mẫu thuộc split đã khóa. Một binary annotation file đóng vai trò label và mask, không phải ba nhãn độc lập. Quy tắc là `<image_stem>_binary` trong annotations cùng nguồn; không ghép theo thứ tự thư mục. Tên `Vinmec_3d` không đủ căn cứ xác nhận dữ liệu volume: hiện là các file ảnh được xử lý 2D.

**Patient-level independence chưa được xác minh.** Index hiện tại chỉ có image/file ID (nhóm C). Các mã `ANON-VINMEC-PID-*` lịch sử thuộc nhóm B; chưa có tài liệu chứng minh tương ứng bệnh nhân nguồn. Không tìm thấy mapping nhóm A được đơn vị cung cấp. Không tạo Patient ID mới.

Đã xác minh 0 giao nhau của SHA nội dung ảnh giữa Train/Validation/Test. SHA ảnh khác nhau vẫn có thể thuộc cùng bệnh nhân; do đó không khẳng định patient-level split hoặc loại bỏ mọi data leakage. Tính độc lập bệnh nhân chỉ được kết luận sau khi nhận mapping nguồn, đối chiếu overlap và phê duyệt chính sách split.

35 bản ghi fallback chia 25 Train / 5 Validation / 5 Test theo lịch sử. Tại audit, cả 35 ảnh/mask ở đường dẫn Mốc 1 khai báo đều thiếu và hồ sơ `empty_masks/PROVENANCE.json` không còn. Script tạo lịch sử cho biết cơ chế zero-mask dùng kiểm thử pipeline; log lịch sử ghi nguồn tương ứng có foreground. **Không thể xác minh bit-to-bit nguồn tạo của từng fallback bằng hồ sơ ban đầu hiện có.** Bảng provenance mới ghi nhận sự thiếu này, không thay thế hồ sơ ban đầu và không tạo thêm mask.

Mọi ảnh bị loại khỏi manifest giữ trạng thái excluded trong index hai nguồn. Không tính metric bằng fallback và không gọi các bản ghi đó là ca âm tính. Clinical ground truth approval chưa xác minh được: còn thiếu hồ sơ nguồn nhãn, người phê duyệt và tiêu chí annotation. Số liệu chạy lại được diễn giải là computational segmentation agreement trên nhãn cung cấp có mapping cơ học kiểm chứng.

Index lịch sử có 1.881 tham chiếu bản sao nhãn không còn tồn tại, ảnh hưởng 1.337 mẫu; 2.941 bản sao target còn tồn tại khớp nhị phân với target chính. Không nhầm thiếu file với khác pixel. Phạm vi hai nguồn mới dùng target chính còn tồn tại và xuất index riêng; không sửa provenance lịch sử hoặc split gốc.

## 4. Model Selection

Tiêu chí được ghi trước khi chạy lại Validation: chọn mean per-image Validation Dice cao nhất ở threshold cố định 0,5; đối chiếu IoU/Recall/Precision, train–validation gap, nạp trọng số và prototype. Đây là lựa chọn retrospective giữa các lượt đã hoàn thành, không phải preregistration trước các lượt huấn luyện. Không dùng kết quả Test để xếp hạng.

| Cấu hình | Best epoch | Train Dice | Validation Dice | IoU | Recall | Precision | Specificity | Gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Standard U-Net, matched normalization | 28 | 0,8071 | 0,7383 | 0,6264 | 0,8159 | 0,7444 | 0,9739 | 0,0688 |
| U-Net++ / ResNet34 ImageNet | 30 | 0,9371 | **0,8170** | **0,7323** | 0,8345 | **0,8545** | **0,9851** | 0,1200 |

Cả hai được kiểm chứng lại trên đủ 541 ảnh Validation, metric và loss khớp log tới số liệu lưu. Cùng split, grayscale normalization, augmentation đồng bộ, Combo Loss, AdamW, LR 1e-4, batch size 2, seed 42, 30 epochs và threshold 0,5. Khởi tạo khác nhau: Standard ngẫu nhiên; U-Net++ pretrained ImageNet. Vì vậy so sánh cấu hình, không phải ablation thuần kiến trúc. Train metric có augmentation; không coi gap là chứng minh chắc chắn quá khớp. U-Net++ best epoch ở cuối ngân sách 30 epochs; chưa biết hiệu quả của các ngân sách khác.

Chọn và khóa U-Net++ cho bước nghiên cứu tiếp theo: checkpoint SHA `ce7580329fd8cab47cf7418e5a5ebd212bf70847983c57f352dc77a98e591e76`; threshold 0,5; grayscale → Letterbox 512×512 → CLAHE → /255 → mean 0,449/std 0,226; sigmoid threshold, không morphology. Seed 42; không chạy seed bổ sung trong audit, nên stability giữa seed chưa xác minh.

Model lock được kiểm chứng trong prototype riêng. Manifest mặc định vẫn chọn Standard `417828fa…`, cần ghi rõ khi chạy app mặc định hoặc bằng `MODEL_SELECTION_MANIFEST`. Không gán Test metric cũ cho U-Net++.

**SHA split/manifest đã kiểm tra:**

| File | SHA-256 |
|---|---|
| train.csv | `a8a8c4067aa911613f79ecd26f01707fce1101df36176bfe4b3228b869ea32f4` |
| val.csv | `d0296b00651bace33bca4a2c1c7f8c260eb6817e3bc624b77acc252b3f907f7b` |
| test.csv | `fbc1f55df5f09c784b2f2ce30705b2202b74d02ec83bdf3d2a5ced5c17f4af6f` |
| manifest.json | `272a3a51079b2da053529e086c27d08bb45ba1484bc6f502a863314358be32d6` |

## 5. Test Evaluation

Lịch sử có ít nhất hai lần đánh giá cùng Test 402: baseline `509b050f…` tại commit `b1fa06d…`, và refined Standard `417828fa…` trong artifact Mốc 3. Selection code chỉ đọc Validation metric; trainer/comparison configs khai báo không iterate Test để optimization/threshold/model selection. Chưa có access log toàn lịch sử để chứng minh không tồn tại mọi hình thức ảnh hưởng ngoài script. Việc biết Test result trước các thử nghiệm sau là một giới hạn cần nêu.

| Checkpoint / phạm vi | Dice | IoU | Recall | Precision | Pixel Specificity |
|---|---:|---:|---:|---:|---:|
| Standard `417828fa…`; **evaluation on previously used Test set** | 0,7297 | 0,6186 | 0,7311 | 0,8129 | 0,9836 |
| U-Net++ `ce758032…` | Chưa đánh giá | Chưa đánh giá | Chưa đánh giá | Chưa đánh giá | Chưa đánh giá |

Các kết quả Test lịch sử được giữ nguyên. Không gọi là blind/first-time/untouched Test; không dùng chọn model mới. Cả 402 reference mask có foreground; không có Empty Mask subgroup để báo empty-mask accuracy. Specificity là phân loại pixel nền, không phải độ chính xác chẩn đoán ca âm tính.

**Chưa xác minh được cohort mới độc lập.** Cần cohort chưa dùng, mapping Patient/Case nguồn, nhãn chuyên gia, kiểm tra overlap với dữ liệu cũ, hash manifest và access log. Chỉ đánh giá sau model lock; không quay lại chọn/tune bằng kết quả đó. Nếu không có cohort mới, báo cáo đúng giới hạn Test đã sử dụng, không tạo cohort từ PID tự gán.

## 6. Error Analysis

Đã lưu 541 prediction masks và bảng metric từng ảnh Validation; 15 panel tương ứng 5 Dice cao nhất, 5 FP lớn nhất, 5 FN lớn nhất. Các hạng mục có thể chồng nhau ở mẫu khác; đây là tiêu chí tự động, không phải hội đồng xác nhận lỗi lâm sàng. Bảng lưu image ID, raw image/reference/prediction/panel paths, SHA checkpoint, threshold và confusion counts ở độ phân giải 512×512.

| Nhóm / ảnh | Dice | FP pixels | FN pixels | Nhận xét theo reference |
|---|---:|---:|---:|---|
| Dice cao — `1225.JPG` | 0,9894 | 654 | 73 | Hai vùng phần lớn chồng khớp; sai lệch nhỏ tại biên |
| FP lớn — `958.JPG` | 0,0118 | 62.993 | 3.822 | Vùng dự đoán lớn, vị trí phần lớn không chồng với vùng reference |
| FP lớn — `376.JPG` | 0,0000 | 40.158 | 29.972 | Prediction và reference không có pixel giao tại ngưỡng hiện tại |
| FN lớn — `48.JPG` | 0,6983 | 4.947 | 51.973 | Prediction bao phủ một phần reference, thiếu vùng rộng ở biên/phần ngoài |
| FN lớn — `378.JPG` | 0,2360 | 0 | 48.245 | Thiên về under-segmentation, thiếu coverage lớn |

Đã xem panel đại diện tốt/FP/FN. Mô tả dựa trên chồng khớp mask, không gán tên bệnh học, không coi reference chưa có xác nhận chuyên môn là chẩn đoán đúng tuyệt đối. Panel gồm ảnh đã tiền xử lý, reference overlay xanh, prediction đỏ và composite; raw image được giữ qua đường dẫn trong bảng.

## 7. HITL

Browser smoke thực tế đạt PASS trên ảnh Validation `1098.JPG`, checkpoint lock `ce758032…`. Kịch bản: upload, inference/error retry, Original/Mask/Overlay, Brush/Eraser, pan, opacity, undo/reset, review/error retry, save/reopen. DB kiểm thử riêng; không có console error ngoài lỗi được chủ động tạo để kiểm tra retry.

**Đánh giá chuyên viên: chưa thực hiện hoặc chưa xác minh được; không tìm thấy phiếu kết quả thực tế.** Không báo số case/acceptance/time của bác sĩ. Đã bổ sung protocol ghi reviewer/session/model/split SHA, accept nguyên trạng/chỉnh rồi accept/reject, thời gian tác vụ, số thao tác và feedback. Checklist/phiếu trống không phải kết quả. Confirm không tự biến mask thành expert-approved Ground Truth.

Thầy đặt đánh giá bác sĩ dưới điều kiện “nếu tiếp cận được”; khi chưa tiếp cận, báo rõ limitation. Không biến technical UI test thành clinical usability evaluation.

## 8. Latency

Môi trường: Windows 11; Python 3.12.10; RTX 3050 Laptop; torch 2.6.0+cu124 / CUDA 12.4; FastAPI 0.141.1, httpx 0.28.1, SMP 0.5.0. Protocol: 24 dòng Validation phân bố đều theo thứ tự CSV cố định, 1 warm-up/ảnh, 3 request/ảnh, sequential localhost HTTP, DB kiểm thử riêng. **72 request / 24 ảnh thành công**, không loại lỗi âm thầm.

| Thành phần | n | p50 ms | p95 ms |
|---|---:|---:|---:|
| Preprocessing | 72 | 20,53 | 25,13 |
| Transfer + normalization | 72 | 0,74 | 1,00 |
| Model forward | 72 | 56,59 | 64,50 |
| Engine postprocessing | 72 | 31,09 | 39,43 |
| API overhead | 72 | 32,65 | 40,35 |
| Server field: preprocessing + engine | 72 | 109,00 | 122,00 |
| Client HTTP total | 72 | **146,47** | **170,54** |

Instrumentation chỉ ở process benchmark: perf_counter, CUDA synchronize trước/sau; postprocessing = engine total trừ transfer/normalization và forward; API overhead là thời gian handler còn lại, gồm các việc ngoài preprocessing/engine. Median các thành phần không cộng thành median total. Server field bỏ qua decoding, DB commit và response serialization; client total bao gồm toàn request. Các wrapper làm tăng overhead đồng bộ CUDA, nên không so sánh trực tiếp với benchmark nhỏ trước đó.

Đây là engineering benchmark trên một thiết bị, không concurrency/network stress test hoặc clinical SLA. Phép đo cũ một ảnh × 5 request giữ nguyên như historical reference, không chọn số thấp hơn để kết luận mọi request dưới 100 ms.

## 9. Documentation Consistency

| Discrepancy | Xử lý |
|---|---|
| README/MODEL_CARD ghi active `5e14be…`, config chọn `417828fa…` | Đã phân biệt lịch sử M2, default hiện tại và research lock U-Net++ |
| project_status ghi M2 20 passed, log lịch sử ghi 61 | Đã ghi 61 là historical theo log 04/10; command gốc không lưu trong log nên không suy diễn |
| Report M3 ghi 74; status ghi 75, không có raw timestamped log tương ứng trong inventory | Giữ claim cũ trong backup/status history, không trình bày như kết quả hiện tại |
| Lượt mới hiện 67 passed / 8 failed | Đã đồng bộ report/status/README với `pytest_latest.json`; command `.venv/Scripts/python.exe -m pytest -q`, PYTHONPATH=root |
| Provenance cũ và 307 cặp được mô tả như đang hiện diện | Đã ghi file/path hiện thiếu; `307/307` là kiểm toán lịch sử, không phải current verification |
| Candidate chưa khóa vs lock mới | Ghi rõ thời điểm: model lock mới thay trạng thái ứng viên cho mục đích nghiên cứu; default chưa chuyển |
| `comparison.json` trỏ summary bị xóa | Khôi phục đúng blob summary lịch sử, không sửa metric |
| Dataset index/báo cáo M2 bị xóa trong lúc audit | Lưu exact HEAD snapshots; chủ dự án yêu cầu tiếp tục với hai nguồn, xuất index riêng; không ghi đè việc xóa |

Giữ các segmentation metrics lịch sử Mốc 1 nguyên trạng, không gán sang checkpoint khác. Nhãn specificity của mask dẫn xuất Mốc 1 cần gọi trung tính; không coi đó là ca âm tính lâm sàng. Bản M2 reviewed được lưu riêng trong audit package; không backdate kết quả M3 vào M2.

## 10. Files Changed

| File/nhóm | Thay đổi và lý do | Ảnh hưởng reproducibility |
|---|---|---|
| `scripts/audit_milestone3_evidence.py` | Inventory, provenance, hash và selective recovery | Chỉ đọc dataset; recovery đúng Git blob |
| `scripts/verify_milestone3_validation.py` | Model lock, replay Validation, error analysis, isolated benchmark/smoke, test provenance | Không sửa training/inference implementation hoặc trọng số |
| `scripts/index_two_vinmec_sources.py` | Index versioned hai nguồn theo yêu cầu mới | Không thay split/data; giữ excluded records |
| `scripts/finalize_milestone3_audit.py` | Backup tài liệu và cập nhật trạng thái có nguồn | Giữ lịch sử trước sửa và snapshot Git |
| `evaluation/milestone_3_audit_2026-10-06/` | CSV/JSON/log, prediction/panel và backup có phiên bản | Bổ sung evidence mới; không overwrite metric gốc |
| 8 file summary/per-image lịch sử | Khôi phục chọn lọc | SHA bằng blob trước cleanup |
| README, MODEL_CARD, TECH_STACK | Đồng bộ phạm vi và checkpoint/benchmark | Thay tài liệu, có backup |
| project_status, report M3, HITL form | Current vs historical tests, blockers, protocol | Giữ backup; không tạo user result |
| Plan và báo cáo audit này | Ghi quy trình, decision và limitations | Bổ sung tài liệu kiểm toán |

Các deletion của `dataset/index.csv` và ba file Mốc 2 được quan sát xuất hiện trong lúc audit, không do các script ở trên thực hiện. Không reset/force checkout/xóa hàng loạt. Git diff và hash kiểm tra cuối được lưu trong audit package. Không commit/push trong đợt này.

## 11. Remaining Risks / Limitations

| Vấn đề | Artifact còn thiếu / cách kiểm chứng | Cách báo cáo hợp lệ hiện tại |
|---|---|---|
| Patient-level independence | Mapping nguồn image → Patient/Case, xác nhận đơn vị; kiểm tra group overlap | “Patient-level independence chưa được xác minh”; chỉ xác nhận SHA ảnh rời nhau |
| Clinical label approval | Hồ sơ annotation, reviewer và quy tắc phê duyệt từng nhãn | Agreement trên supplied reference labels, chưa chứng minh clinical ground truth |
| Test đã sử dụng | Cohort mới có PID/labels, lịch sử truy cập và overlap audit | Evaluation on previously used Test set; không blind/untouched claims |
| 35 fallback / M1 paths thiếu | Bản gốc/backup có provenance; không tạo file zero thay thế | Historical fallback records, excluded; chưa tái lập M1 hiện tại |
| Full suite fail | Dữ liệu M1 xác thực hoặc quyết định version hóa test theo phạm vi mới, vẫn giữ lịch sử kiểm thử | 67 passed / 8 failed; không skip hoặc đổi assertion để tuyên bố xanh |
| Stability / overfitting | Replicate seeds/config đối chứng trên Train/Val | Một seed; train–Val gap 0,1200; pretrained initialization confound |
| HITL chuyên môn | Người tham gia phù hợp và phiếu/log thật | Technical UI PASS; clinical evaluation chưa thực hiện |
| Latency | Thêm devices/concurrency/network nếu cần | Benchmark cục bộ có instrumentation; không SLA |
| Nhóm Empty Mask | Ca thật có nhãn rỗng được chuyên môn xác nhận | Chưa có nhóm hợp lệ; không thay bằng fallback |
| Confidence/quality gate | Calibration và đánh giá threshold của quality gate | Sigmoid/entropy là tín hiệu kỹ thuật, không xác suất chẩn đoán đã hiệu chuẩn |
| PACS/DICOM | Metadata nguồn, pixel spacing và E2E integration thực tế | Không kết luận PACS-ready hay đo kích thước chính xác khi thiếu calibration |
| Giới hạn SHA 03/10 | CSV huấn luyện gốc matching original_split_sha | Giữ kết luận audit đã chấp nhận; không gọi archive_pre_pid là training-time byte-identical snapshot |

## 12. Mốc 3 Readiness

| Điều kiện | Trạng thái | Căn cứ |
|---|---|---|
| Checkpoint chọn bằng Validation và có SHA/config/threshold | READY | Model lock và replay hai mô hình |
| Split/hash, dữ liệu hai nguồn và exclusion rõ ràng | READY | 1.639 mappings; 1.604 retained; 35 excluded; hash kiểm tra |
| Patient identity và clinical mask approval | PARTIALLY READY | Limitation ghi rõ; bằng chứng nguồn chưa có |
| Test scope / không gán metric sai model | READY | Historical Test riêng Standard; U-Net++ Test=null |
| Đánh giá xác nhận trên cohort độc lập | NOT READY | Chưa có cohort đủ provenance/PID |
| Error Analysis có artifact truy vết | READY | 541 predictions và 15 Validation panels |
| HITL kỹ thuật | READY | Browser smoke PASS, isolated DB |
| HITL chuyên môn | PARTIALLY READY | Protocol có; chưa có kết quả người thật; theo điều kiện tiếp cận chuyên viên |
| Latency engineering có protocol/sample size | READY | 24 ảnh / 72 request, component timings |
| Full test suite xanh / tái lập dữ liệu M1 | NOT READY | 8 lỗi do file/path thiếu |
| Tài liệu/index chính thức sau thay đổi phạm vi | PARTIALLY READY | Index mới có; M2 hiện chỉ còn snapshot/reviewed version; deletion được giữ |
| Không có dữ liệu, PID, GT hoặc metric tạo giả | READY | Không tạo clinical evidence thay thế; source/split/weight checks được lưu |

**Project is not fully ready for Milestone 3.** Blocker kỹ thuật trực tiếp là 8 kiểm thử thất bại và đường dẫn dữ liệu Mốc 1 không còn; cần chốt lưu trữ/index/report chính thức sau thay đổi phạm vi. Kết luận patient-level/clinical validation cần thêm mapping và hồ sơ nhãn chuyên gia. Đánh giá xác nhận mới cần cohort chưa dùng; HITL chuyên môn phải có kết quả thực tế hoặc được trình bày là chưa tiếp cận được theo yêu cầu của Thầy.
