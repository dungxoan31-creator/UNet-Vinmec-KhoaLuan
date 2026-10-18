# Đặc tả bàn giao kiểm thử, đánh giá và prototype — 16/10/2026

Nguồn yêu cầu: yêu cầu trực tiếp của người dùng trong phiên hiện tại; không thay thế bằng checklist metric. Tài liệu này lưu các quyết định đề xuất để coding agent đọc cùng implementation plan trước khi thực hiện.

## Mục tiêu và phạm vi

Hoàn thành prototype nghiên cứu có thể khởi chạy, đăng nhập thật, tạo/mở ca, upload, suy luận, xem và sửa segmentation, xác nhận rà soát nghiên cứu, lưu bền vững, mở lại và export kết quả. Đồng thời bàn giao pipeline định lượng, phân tích lỗi, HITL instrumentation, đánh giá người dùng có thật nếu tiếp cận được và báo cáo có artifact truy vết.

Yêu cầu đánh giá: Dice, IoU, Recall, Precision; per-image/per-case/aggregate; Test độc lập theo bệnh nhân và không dùng Test tuning; top/median/worst, FP/FN/under/over/boundary; visualization ảnh gốc/GT/prediction/overlay/difference; kiểm thử toàn ứng dụng; đo inference, correction, total, số và loại thao tác; Dice/IoU trước/sau sửa nếu có reference độc lập; clinician questionnaire hoặc fallback kỹ thuật ghi rõ giới hạn; packaging, README, regression, reproducible commands.

## Ràng buộc bắt buộc

- Không triển khai code trong lượt lập kế hoạch này.
- Patient-Level Data Split; không thay mã ảnh/hash/ID tự sinh cho Patient ID nguồn.
- Letterbox 512×512; giữ pipeline và checkpoint khóa theo manifest; không thay Combo Loss của thí nghiệm huấn luyện.
- Không được dùng Test Set để tuning model.
- Không nhìn điểm Test rồi đổi threshold, hậu xử lý, cohort, metric hoặc cách tổng hợp để cải thiện điểm.
- Không tạo dữ liệu bác sĩ giả; log demo/synthetic không được tính vào clinician evaluation.
- Abnormal != Malignant; pixel Recall != sensitivity chẩn đoán ung thư; mask rỗng != bằng chứng bệnh nhân bình thường.
- Không tự bổ sung clinical sign-off, OTP, chữ ký số, backend duyệt hai cấp, model mới hoặc retraining vào critical path.
- Mỗi task có acceptance criteria; mọi metric có test; mọi kết quả evaluation lưu artifact.
- Không ghi đè lịch sử thí nghiệm, checkpoint, split hoặc dữ liệu nguồn; không phục hồi hàng loạt file đang bị người dùng xóa.
- Dùng FastAPI/SQLAlchemy/SQLite/PyTorch, frontend ES modules và pytest/Node/Playwright hiện có; không thêm runtime dependency.
- Đích bàn giao chính: Windows PowerShell, một máy và một người thao tác chủ động; ngăn ghi đè stale trong cùng phiên/nhiều tab. Chưa tuyên bố sẵn sàng triển khai bệnh viện hay đa cơ sở.
- Demo có nhãn; save/export thật phải hoạt động khi demo=false và sau restart.

## Quyết định thiết kế đề xuất

Giữ `frontend/app/` làm giao diện duy nhất của bản bàn giao. Giữ `/api/cases`, `/api/upload`, `/api/predict/{image_id}`, validation RLE và source-mask geometry. Bổ sung batch review nghiên cứu có transaction/version/idempotency; export ZIP nghiên cứu theo review_id cố định; event log HITL có session và UTC + monotonic clock; một evaluator v1 dùng đúng inference service. Giữ `/api/generate-report` trả 501; không gọi export ZIP nghiên cứu là báo cáo lâm sàng đã ký.

Evaluation v1 chạy Validation trước, khóa JSON protocol và hash bằng chứng rồi mới mở holdout mới nếu có. Tập Test 402 ảnh cũ chỉ là retrospective replay, không thể trở lại trạng thái chưa từng được xem. Independent gate phải có mapping nguồn, lịch sử huấn luyện/chọn mô hình, nhãn tham chiếu và xử lý ứng viên trùng; thiếu một điều kiện thì báo BLOCKED/UNKNOWN, không cấp chứng nhận bằng code.

## Nghiệm thu hai trạng thái độc lập

1. `prototype_ready_for_supervised_pilot`: live flow + persistence/export + telemetry + negative tests + hướng dẫn + giới hạn đều đạt. Dữ liệu dùng thử được phép, khử định danh, không dùng quyết định điều trị.
2. `evaluation_complete`: thêm Test độc lập đã xác minh, protocol khóa, kết quả và error/HITL analysis đủ, báo cáo và regression đầy đủ. Chưa có bác sĩ được ghi rõ và dùng fallback; không biến fallback thành clinician validation.

Thiếu Test độc lập thì trạng thái 2 không được COMPLETE dù trạng thái 1 đạt. Không tự cắt yêu cầu bắt buộc để đạt hạn 18/10; chỉ cắt nice-to-have và báo phần chưa hoàn thành.
