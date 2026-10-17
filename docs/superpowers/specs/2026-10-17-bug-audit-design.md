# Thiết kế audit và ghi nhận bug — 17/10/2026

## Mục tiêu

Audit prototype segmentation/HITL hiện tại, ghi nhận lỗi có bằng chứng tái hiện, mức độ ảnh hưởng và điều kiện retest. Không sửa product code, tuning model, tạo dữ liệu bác sĩ hoặc thay đổi phạm vi đề tài trong đợt audit. Đây là yêu cầu lập kế hoạch; audit thực tế và ticket thực tế được thực hiện sau.

## Phạm vi

Startup/model loading; preprocessing/coordinate/metrics; API/input/auth; UI Original/Mask/Overlay; edit/undo/reset; confirm/save/reopen/export; session/time/count tracking; evaluation/report/provenance. Dashboard mở rộng, LLM/VLM và chẩn đoán tự động không nằm trong audit chức năng cốt lõi; chỉ ghi nhận nếu code của chúng gây ảnh hưởng trực tiếp tới luồng lõi.

## Quyết định

1. Tái sử dụng pytest, Node/Playwright, launcher và verifier hiện có; không xây issue-tracker service hoặc dashboard mới.
2. Hồ sơ canonical của mỗi finding là một Markdown trong `docs/audit/findings/`; index CSV là bảng tra cứu được đối chiếu với hồ sơ. Bằng chứng raw đặt trong run folder mới dưới `evaluation/bug_audit/`, không sửa log/history cũ.
3. Phân loại `BUG`, `MODEL_ERROR`, `DATA_BLOCKER`, `LIMITATION`, `ENVIRONMENT`, `NEEDS_INVESTIGATION`; mã `AUD-0001` tăng dần, không đổi ID sau reclassification. BUG chỉ được CONFIRMED khi có repro thực tế hoặc chứng minh static có trace/assertion rõ; nghi vấn giữ UNCONFIRMED.
4. Mỗi finding có expected/actual, source expectation, steps, input identity/hash, version/config, severity/priority, evidence, root-cause status, owner/next action và lịch sử trạng thái. Không suy nguyên nhân từ screenshot hoặc metric thấp.
5. Audit không đồng nghĩa full PASS. Báo cáo riêng coverage, not run, blockers và finding counts; không có bug được tìm thấy không chứng minh không có bug.
6. Không đưa PHI, token, password hoặc secret env vào log chia sẻ. Evidence nhạy cảm nằm private và index dùng hash/reference khử định danh.

## Phân biệt bug và giới hạn

Patient ID chưa xác minh là DATA_BLOCKER, không phải bug thuật toán. Không có bác sĩ là điều kiện nghiên cứu chưa thực hiện. Hiển thị px khi thiếu calibration là hành vi đúng; hiển thị mm khi không có calibration hợp lệ mới là bug. Mask prediction kém so GT là MODEL_ERROR; sai tọa độ, threshold trái protocol hoặc metric tính sai là BUG.

## Nghiệm thu audit

Các miền cốt lõi có PASS/FAIL/NOT_RUN/BLOCKED và evidence; mọi BUG CONFIRMED có repro/case rõ; mọi S0/S1 được triage; index không orphan/duplicate và khớp hồ sơ; dữ liệu/checkpoint/split/production DB không bị audit thay đổi. Sửa bug là giai đoạn sau có task/test/commit riêng; VERIFIED chỉ sau retest thực tế.
