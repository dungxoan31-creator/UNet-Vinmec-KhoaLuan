# AUD-NNNN — [Mô tả ngắn gọn trigger và hậu quả phát hiện]

- **Type**: BUG | MODEL_ERROR | DATA_BLOCKER | LIMITATION | ENVIRONMENT | NEEDS_INVESTIGATION
- **Severity**: S0 Critical | S1 High | S2 Medium | S3 Low
- **Priority**: P0 | P1 | P2 | P3
- **Status**: NEW | TRIAGED | CONFIRMED | IN_PROGRESS | FIXED_PENDING_VERIFICATION | VERIFIED | CLOSED | BLOCKED | DEFERRED

## 1. Siêu dữ liệu & Phiên bản (Metadata & Provenance)
- **Run ID**: `YYYYMMDDTHHMMSSZ-<short-head>`
- **UTC Timestamp**: `YYYY-MM-DDTHH:MM:SSZ`
- **Git HEAD**: `<full-commit-sha>`
- **Source Manifest**: `evaluation/bug_audit/<run-id>/source_hashes.csv`
- **Component**: `<path/to/source_file.py:Lxx-Lyy>`
- **Config / Checkpoint Hash**: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`

## 2. Mô tả Hành vi (Behavior Specification)
- **Expected Behavior**: [Mô tả hành vi kỳ vọng theo spec/protocol/requirements]
- **Actual Behavior**: [Mô tả chính xác hành vi thực tế quan sát được]
- **Source of Expectation**: [Tài liệu spec, protocol JSON, hoặc file test quy định]

## 3. Đầu vào & Điều kiện Tiên quyết (Inputs & Preconditions)
- **Input Identifier / Hash / Shape**: [Mã ẩn danh, SHA-256, shape; tuyệt đối không chứa PHI]
- **Preconditions**: [Trạng thái server, DB, phiên đăng nhập, cấu hình runtime trước khi kích hoạt]

## 4. Các Bước Tái hiện (Reproduction Steps)
1. Bước 1: Khởi động môi trường / chuẩn bị dữ liệu...
2. Bước 2: Gửi request hoặc thao tác UI...
3. Bước 3: Quan sát phản hồi hoặc trạng thái...

## 5. Lệnh & Bằng chứng Thực nghiệm (Commands & Evidence)
- **Redacted Command / API Request**:
  ```bash
  # Lệnh thực thi đã bỏ token, credentials, passwords
  ```
- **Evidence Paths**:
  - Raw Log: `evaluation/bug_audit/<run_id>/...`
  - Stacktrace / Line / Assertion:
  - Screenshots / Mask Diff:

## 6. Tần suất & Tác động (Frequency & Impact)
- **Observed Frequency**: X / Y lượt thử nghiệm (hoặc `static_proof`)
- **Impact Analysis**: [Ảnh hưởng đến tính toàn vẹn dữ liệu, trải nghiệm người dùng, hoặc tính sẵn sàng]
- **Workaround**: [Biện pháp khắc phục tạm thời nếu có]

## 7. Nguyên nhân Gốc (Root Cause Analysis)
- **Root Cause Status**: UNKNOWN | HYPOTHESIS | CONFIRMED
- **Detailed Trace / Explanation**: [Trace ngược đến dòng code hoặc nhánh logic gây lỗi]

## 8. Hướng Xử lý & Kiểm thử Hồi quy (Remediation & Regression)
- **Owner**: UNASSIGNED | [Tên/vai trò người phụ trách]
- **Next Action**: [Đề xuất phạm vi sửa chữa cụ thể]
- **Regression Test**: `<tests/test_file.py::test_name>` hoặc `NOT_YET_WRITTEN`
- **Fix Commit**: [Commit hash sau khi sửa]
- **Retest Run / Result**: [Run ID kiểm thử lại và kết quả]

## 9. Lịch sử Trạng thái (Status History)
| UTC Timestamp | Old Status | New Status | Operator | Evidence / Note |
|---|---|---|---|---|
| YYYY-MM-DDTHH:MM:SSZ | — | NEW | Auditor | Khởi tạo hồ sơ phát hiện |
