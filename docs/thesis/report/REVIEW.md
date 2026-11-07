# Rà soát nội dung bản thảo — 13/10/2026

Phạm vi: các Markdown nguồn của báo cáo, bản ghép `Khoa-luan-Nguyen-Huu-Dung-theo-mau-Dinh-Manh-Hoa.md` và các tệp mã/JSON liên quan. Đây là rà soát tư vấn trong Phase 6, chưa kiểm bố cục Word/PDF, không phải chứng nhận khoa hoặc kiểm định lâm sàng. Không sửa bản thảo trong lượt rà soát này.

`criteria_binding_unavailable`; `calibration_status: NOT_CALIBRATED`.

## Các điểm cần sửa

### R1 — Bổ sung hồ sơ cập nhật về mã Patient/Case

**Mức: Minor Revision, tác động đến độ đầy đủ của bằng chứng.**

Vị trí: `chuong-3-mo-hinh.md`, mục 3.5.1, ngay sau đoạn về giới hạn identity của manifest; đối chiếu `chuong-1.md`, bảng 1.2 và phần hạn chế. Manifest ngày 06/10 được trình bày đúng như một hồ sơ chưa xác minh Patient/Case nguồn. Tuy nhiên báo cáo mới chưa đề cập bảng bằng chứng ngày 08/10, đã có workbook và phép đối chiếu mã/tệp/hash. Sự thiếu vắng đó có thể khiến người đọc hiểu chưa có bất kỳ mapping nào, trong khi vấn đề còn lại là xác minh ý nghĩa và tính ổn định của mã.

Nguồn kiểm tra: `docs/reports/M3_Bang_Chung_Du_Lieu_2026-10-08.md`. Nguồn này ghi workbook 1.639 dòng, 820 chuỗi mã Patient và 1.234 chuỗi mã Case khác nhau; 1.604 ảnh trong split ghép được với workbook, khớp hash ảnh. Giao từng cặp tập bằng 0 cho các chuỗi mã Patient, Case và SHA-256. Nó đồng thời ghi chưa có xác nhận bàn giao/quy tắc mã và không coi số chuỗi mã là số bệnh nhân lâm sàng đã chứng minh.

**Đề nghị thêm đoạn:**

> Hồ sơ đối chiếu bổ sung ngày 08/10/2026 ghi workbook có 1.639 dòng ảnh, 820 chuỗi mã Patient và 1.234 chuỗi mã Case khác nhau. Toàn bộ 1.604 ảnh trong split nối được với workbook theo nhóm nguồn và tên ảnh, đồng thời khớp SHA-256 ảnh. Giao chuỗi mã Patient, Case và SHA-256 giữa từng cặp Train, Validation, Test bằng 0 trên phiên bản workbook được kiểm. Đây là bằng chứng về phép đối chiếu tệp và chuỗi mã; chưa xác nhận mã giữ ổn định cho cùng người bệnh ở mọi ảnh. Vì còn thiếu hồ sơ bàn giao và quy tắc cấp mã từ nguồn, báo cáo vẫn chưa kết luận độc lập cấp bệnh nhân thực.

Thêm nguồn bảng bằng chứng/workbook vào [15] hoặc một mục tham khảo được đánh số mới. Không đổi split, metric hoặc kết luận thành patient-level verified. Bảng 1.2 có thể giữ “chưa có bảng ánh xạ xác nhận” cho quan hệ giữa 307 ảnh lịch sử và 1.604 ảnh hiện tại, nhưng nên nêu đây là quan hệ hai phiên bản dữ liệu, tránh lẫn với mapping workbook hiện có.

### R2 — Làm rõ phạm vi và bổ sung luồng ảnh ở DFD mức 0

**Mức: Minor Revision, tác động đến tính nhất quán của mô hình hóa.**

Vị trí: `chuong-3-nghiep-vu-thiet-ke.md`, dòng 289–313. CD ở dòng 275–283 có ba tác nhân Người rà soát, Quản trị và Người nghiên cứu mô hình. DFD mức 0 chỉ giữ Người rà soát; các luồng metadata/nhật ký và artifact/checkpoint từ hai tác nhân kia không xuất hiện. Vì đoạn mở đầu gọi đây là phân rã “tiến trình hệ thống”, nó chưa cân bằng đủ với CD. Ngoài ra tiến trình 3.0 Quan sát và chỉnh sửa nhận mask từ D3 nhưng chưa có luồng ảnh nền từ D2.

**Cách sửa ít nhất:** bổ sung cạnh `D2 -->|"Ảnh nguồn để đối chiếu"| P3`. Sau đó chọn một cách mô tả nhất quán:

- Nếu giữ DFD mức 0 cho toàn hệ thống: bổ sung trao đổi metadata/nhật ký của Quản trị và trao đổi artifact của Người nghiên cứu, chỉ mô tả cơ chế read/artifact thực sự tồn tại.
- Nếu chỉ vẽ vòng phân đoạn: đổi tiêu đề và câu giới thiệu thành “DFD mức 0 của phân hệ phân đoạn và rà soát”; ghi rõ đây là phạm vi phân hệ, không khẳng định phân rã đầy đủ mọi luồng của CD toàn hệ thống.

**Câu thay thế cho phương án phân hệ:**

> DFD dưới đây mô tả luồng dữ liệu của phân hệ tiếp nhận, phân đoạn và rà soát. Các trao đổi quản trị và cấp artifact của sơ đồ ngữ cảnh toàn hệ thống được mô tả riêng ở kiến trúc/API; sơ đồ này không thay thế DFD toàn bộ phân hệ quản trị. Tiến trình quan sát nhận đồng thời ảnh nguồn và mặt nạ để bảo đảm người dùng đối chiếu được gợi ý AI với dữ liệu nền.

### R3 — Sửa đường dẫn nguồn và bổ sung đường dẫn hồ sơ đánh giá

**Mức: Minor Revision, tác động đến khả năng truy vết.**

Vị trí: `tai-lieu-tham-khao.md`, mục [17]. Đường `backend/app/schemas` không tồn tại; tệp thật là `backend/schemas/schemas.py`.

**Thay cụm đường dẫn trong [17]:** `backend/models/unet.py`, `backend/services/preprocessor.py`, `backend/services/inference_engine.py`, `backend/services/source_measurements.py`, `backend/app/routers/`, `backend/schemas/schemas.py` và `backend/db/database.py`.

Trong [16], nên bổ sung `evaluation/milestone_3_audit_2026-10-06/validation_lock/` vì các ví dụ lỗi Validation và benchmark 24 ảnh/72 request được truy đến `error_analysis_summary.json` và `api_latency_summary.json` trong thư mục đó. Benchmark 1 ảnh/5 request trong `api_latency_validation_unetplusplus_candidate.json` là lượt khác, không phải nguồn của các mốc HTTP 146,47/170,54 ms.

## Các phép đối chiếu đã thực hiện

| Nội dung | Kết quả kiểm tra |
|---|---|
| Kết cấu | Bản ghép có đúng ba tiêu đề chương chính |
| Caption sau ghép | Không trùng cặp loại–số; các file nguồn Ch3 có số tạm trùng nhưng assembler đã xử lý trong bản ghép |
| Standard U-Net | Một kênh vào/ra, base_filters=32, ConvBlock hai Conv–BN–ReLU, logits ở đầu ra; khớp mã |
| Loss đối sánh | Hai trainer dùng 0,5 BCEWithLogits + 0,5 SoftDice; không nhầm lớp Dice–Focal–BCE khác |
| Validation | Standard 0,738296 Dice/0,626416 IoU; U-Net++ 0,817036/0,732287; khớp run config |
| Test lịch sử | SHA-256 417828fa…; 402 ảnh; Dice 0,729749 ± 0,230365 và IoU 0,618615 ± 0,247552; khớp summary |
| Thí nghiệm candidate | Chưa biến Validation thành Test hoặc tuyên bố candidate đã triển khai bệnh viện |
| Benchmark 72 request | HTTP p50 146,46675 ms, p95 170,53577 ms; forward p50 56,58790 ms; khớp hồ sơ validation_lock |
| Ảnh gần trùng | 59 ứng viên/22 cặp tương quan ≥0,95 có hồ sơ expanded; không phải kết luận cùng bệnh nhân |
| Giao diện | SPA thuần ES modules; React chỉ được nhắc như phương án đề cương |
| Quyền | BS/TK/QT demo được tách khỏi DOCTOR/ADMIN server; chưa tuyên bố ownership/duyệt hai cấp đã cưỡng chế |
| Đơn vị và đo | Thiếu spacing giữ px; bộ đo nguồn và preview được phân biệt; không suy d₃/thể tích từ mặt cắt |
| Review | ORM `is_official_ground_truth=False`; response `is_ground_truth=False`; tên trong bảng API phù hợp hai lớp khác nhau |
| Kiểm thử phần mềm | Kết quả lưu ngày 11/10 được phân biệt với lượt kiểm tra biên soạn; không biến test thành khảo sát bác sĩ |

## Đánh giá theo năm tiêu chí

Nguồn tiêu chí: rubric chung Phase 6 của academic-research-suite; đánh giá giới hạn trong bản mẫu nghiên cứu và tài liệu hiện có.

| Tiêu chí | Đánh giá | Căn cứ / điều kiện | Ảnh hưởng quyết định |
|---|---|---|---|
| Đóng góp | MEETS | Chương 1 và kết luận giới hạn đóng góp ở tích hợp quy trình, AI, dữ liệu và tương tác; không claim kiến trúc mới | Không phát hiện sửa trọng yếu |
| Chặt chẽ phương pháp | MEETS | Mục 3.5 công bố khác biệt pretrained, split image-level, Test lịch sử và quy ước metric | R1 bổ sung hồ sơ, không đổi kết luận |
| Đủ bằng chứng | PARTLY_MEETS | Metric có tệp đối chiếu; hồ sơ mã nguồn cập nhật và đường dẫn tham khảo cần R1/R3 | Cần sửa trước chốt bản |
| Nhất quán lập luận | PARTLY_MEETS | Ranh giới demo/live và lâm sàng được giữ; CD/DFD cần R2 | Sửa cục bộ sơ đồ/phạm vi |
| Chất lượng diễn đạt | MEETS | Có diễn giải mục tiêu, giới hạn và các lớp chứng cứ; chưa đánh giá layout Word/PDF | Không thay thế kiểm tra trình bày |

## Kết luận rà soát

**Minor Revision.** Cần sửa R1–R3 trước chốt bản xuất. Không phát hiện sai lệch trọng yếu về kiến trúc mô hình, số metric, scope nghiên cứu hoặc phân biệt demo/backend trong các phần đã đối chiếu. Không chạy lại training, pytest, browser test hoặc đánh giá lâm sàng trong lượt review tài liệu này; các nhận định kiểm thử dựa trên mã và log hiện hữu. Việc kiểm hình render, trang, mục lục, font và lề thuộc bước xác minh artifact của người biên soạn.
