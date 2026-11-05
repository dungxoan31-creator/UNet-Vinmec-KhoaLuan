# Báo Cáo Kiểm Định Động Cơ Suy Luận Lâm Sàng CDSS & Khóa Phiên Bản Bộ Quy Tắc (Deterministic Ruleset Locking)

> **Mục tiêu**: Xác minh việc khóa cứng phiên bản bộ quy tắc (`ruleset_version: "2022.1"`), tính tất định (deterministic), tính fail-closed và độ chính xác phân tầng O-RADS US v2022 / IOTA Simple Rules / IOTA ADNEX trên ma trận 30 ca bệnh tổng hợp đại diện.
> **Mã giả định liên quan**: [A3](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/assumptions-register.md) (`RESOLVED-BY-ASSUMPTION`).
> **Ngày thực hiện**: 2026-10-30.

> **Cập nhật kiểm toán 2026-11-05 — [PARTIALLY VERIFIED]:** This historical report's rule version and table are not independent clinical validation. Current code uses `project-follicle-lt30-v3` (`0 < D < 30 mm`); exactly 30 mm is `UNSUPPORTED_PATTERN` with no category. ACR O-RADS US v2022 states follicle `≤3 cm`, so this is a project deviation, not ACR wording. Current focused software verification (`test_cdss_boundary_30mm_r8.py`, `test_cdss_fail_closed.py`, `test_frontend_clinical_copy.py`, `test_cdss_synthetic_case_matrix.py`) passed **143 tests**; this does not establish clinical validity. [Official ACR categories](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf).

---

## 1. Khóa Phiên Bản Bộ Quy Tắc (Ruleset Version Locking)
Mọi phản hồi từ `CDSSReasoningEngine.evaluate_case()` đều chứa trường định danh phiên bản bất biến:
```json
{
  "ruleset_version": "2022.1",
  "implementation_policy": {
    "version": "project-follicle-lt30-v1",
    "source_diameter_rule": "ACR O-RADS US v2022: follicle <=3 cm",
    "deviation": "Project policy excludes exactly 30 mm; unsupported is not abnormal or malignant."
  }
}
```
Khóa phiên bản đảm bảo:
- Không cho phép cập nhật âm thầm các tham số phân tầng mà không qua quy trình kiểm thử hồi quy.
- Bảo toàn tính khả kiểm (auditability) trong hồ sơ kiểm định phần mềm y tế.

---

## 2. Ma Trận Thử Nghiệm 30 Ca Tổng Hợp (Synthetic Case Matrix)

Kiểm thử được tự động hóa tại [test_cdss_synthetic_case_matrix.py](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/tests/test_cdss_synthetic_case_matrix.py).

### 2.1 Bảng Tổng Hợp Kết Quả 30 Ca
| Mã Ca | Mô tả lâm sàng | Nhóm quy tắc | Kết quả kỳ vọng | Kết quả thực tế | Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CASE-01** | Nang noãn $20\text{ mm}$, tiền mãn kinh, bác sĩ xác nhận | Follicle O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | **PASS** |
| **CASE-02** | Nang nhỏ $12\text{ mm}$, tiền mãn kinh, bác sĩ xác nhận | Follicle O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | **PASS** |
| **CASE-03** | Nang vượt trội $28.5\text{ mm}$, tiền mãn kinh ($<30\text{ mm}$) | Follicle O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | `RULE_MATCHED` / O-RADS 1 | **PASS** |
| **CASE-04** | Gắn nhãn nang sinh lý ở phụ nữ sau mãn kinh | Follicle Policy | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-05** | Nang sinh lý vượt ngưỡng kích thước ($35\text{ mm} \ge 30\text{ mm}$) | Follicle Policy | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-06** | Thiếu thông tin tình trạng mãn kinh | Safety Gate | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | **PASS** |
| **CASE-07** | Nang đơn thùy, trống âm, thành nhẵn $35\text{ mm}$ | Simple Cyst O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | **PASS** |
| **CASE-08** | Nang đơn thùy, trống âm, thành nhẵn $60\text{ mm}$ | Simple Cyst O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | **PASS** |
| **CASE-09** | Nang đơn thùy, trống âm, thành nhẵn $95\text{ mm}$ | Simple Cyst O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | **PASS** |
| **CASE-10** | Nang đơn giản $<30\text{ mm}$ không có nhãn nang noãn | Policy Boundary | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-11** | Nang đơn giản $>100\text{ mm}$ ($110\text{ mm}$) | Scope Boundary | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-12** | U bì điển hình $45\text{ mm}$ có bóng cản âm ($<10\text{ cm}$) | Dermoid O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | **PASS** |
| **CASE-13** | U bì điển hình $75\text{ mm}$ có dải/chấm tăng âm | Dermoid O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | `RULE_MATCHED` / O-RADS 2 | **PASS** |
| **CASE-14** | U bì điển hình lớn $120\text{ mm}$ ($\ge 10\text{ cm}$) | Dermoid O-RADS 3 | `RULE_MATCHED` / O-RADS 3 | `RULE_MATCHED` / O-RADS 3 | **PASS** |
| **CASE-15** | Mâu thuẫn: Khai u bì có cản âm nhưng `acoustic_shadowing=False` | Contradiction Gate | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-16** | Khai u bì nhưng có thành phần đặc (`has_solid_component=True`) | Contradiction Gate | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |
| **CASE-17** | IOTA Simple Rules: Thuần tiêu chí lành tính B1 (đơn thùy) + B5 | IOTA Benign | IOTA `BENIGN` / O-RADS 2 | IOTA `BENIGN` / O-RADS 2 | **PASS** |
| **CASE-18** | IOTA Simple Rules: Thuần B3 (bóng cản âm) | IOTA Benign | IOTA `BENIGN` | IOTA `BENIGN` | **PASS** |
| **CASE-19** | IOTA Simple Rules: Thuần B4 (đa thùy nhẵn $<100\text{ mm}$) | IOTA Benign | IOTA `BENIGN` | IOTA `BENIGN` | **PASS** |
| **CASE-20** | IOTA Simple Rules: Thuần M1 (u đặc không đều) | IOTA Malignant | IOTA `MALIGNANT` / Block | IOTA `MALIGNANT` / Block | **PASS** |
| **CASE-21** | IOTA Simple Rules: Thuần M2 (cổ trướng) | IOTA Malignant | IOTA `MALIGNANT` / Block | IOTA `MALIGNANT` / Block | **PASS** |
| **CASE-22** | IOTA Simple Rules: Thuần M3 ($\ge 4$ chồi nhú) | IOTA Malignant | IOTA `MALIGNANT` / Block | IOTA `MALIGNANT` / Block | **PASS** |
| **CASE-23** | IOTA Simple Rules: Đồng thời có B1 và M2 | IOTA Inconclusive | IOTA `INCONCLUSIVE` | IOTA `INCONCLUSIVE` | **PASS** |
| **CASE-24** | IOTA Simple Rules: Cả 10 tiêu chí B & M đều âm tính | IOTA Inconclusive | IOTA `INCONCLUSIVE` | IOTA `INCONCLUSIVE` | **PASS** |
| **CASE-25** | IOTA Simple Rules ngoài phạm vi (không chỉ định phẫu thuật) | Eligibility Gate | `OUT_OF_SCOPE` | `OUT_OF_SCOPE` | **PASS** |
| **CASE-26** | Mô hình ADNEX có CA-125 ($60$t, trung tâm ung bướu, $70\text{ mm}$, u đặc $20\text{ mm}$) | IOTA ADNEX | `EVALUATED_RUO` ($\sum P = 1.0$) | `EVALUATED_RUO` ($\sum P = 1.0$) | **PASS** |
| **CASE-27** | Mô hình ADNEX không CA-125 ($28$t, tuyến cơ sở, $40\text{ mm}$, đơn thùy) | IOTA ADNEX | `EVALUATED_RUO` ($\sum P = 1.0$) | `EVALUATED_RUO` ($\sum P = 1.0$) | **PASS** |
| **CASE-28** | Cổng an toàn: Nguồn đánh giá do AI tự suy luận (`ai_inferred`) | Safety Boundary | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | **PASS** |
| **CASE-29** | Cổng an toàn: Cuộc siêu âm chưa hoàn thành (`exam_complete=False`) | Safety Boundary | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | **PASS** |
| **CASE-30** | Cổng an toàn: Chứa trường mô tả lạ ngoài đặc tả | Safety Boundary | `UNSUPPORTED_PATTERN` | `UNSUPPORTED_PATTERN` | **PASS** |

### 2.2 Boundary cases added to the current software suite
The following exact-boundary assertions are covered by the current code-level tests, not by clinical evidence:

| Scenario | Current result | Interpretation |
| :--- | :--- | :--- |
| Clinician-confirmed follicle at exactly 30.0 mm | `UNSUPPORTED_PATTERN`, no O-RADS category | Local `<30 mm` boundary; not equivalent to ACR `≤3 cm`; unsupported does not mean abnormal or malignant. |
| Simple cyst at exactly 30.0 mm | `UNSUPPORTED_PATTERN`, no O-RADS category | Outside the implemented simple-cyst rule (`>30 mm`); no automatic diagnosis. |
| Corpus luteum input | Not covered by a dedicated runtime rule | Do not infer an O-RADS 1 result from this fixture until supported and clinically reviewed. |

---

## 3. Các Cơ Chế Bảo Vệ Lâm Sàng Đặc Thù (Clinical Guardrails)

1. **Fail-Closed by Design**:
   - Khi thiếu bất kỳ trường thông tin nào bắt buộc hoặc dữ liệu không nhất quán, hệ thống lập tức từ chối phân tầng (trả về `INSUFFICIENT_DATA` hoặc `UNSUPPORTED_PATTERN`) kèm danh sách trường thiếu cụ thể.
   - Tuyệt đối không tự suy diễn đặc điểm mô học từ mặt nạ phân đoạn 2D.
2. **Khóa Nguy Cơ Ác Tính (M-Feature Safety Lockout)**:
   - Khi bác sĩ đánh dấu bất kỳ đặc điểm ác tính nào theo tiêu chuẩn IOTA (M1-M5), hệ thống lập tức khóa không cho đối chiếu về các nhãn nguy cơ thấp (O-RADS 1 hoặc O-RADS 2), buộc bác sĩ phải trực tiếp rà soát chuyên sâu.
3. **Tuân Thủ Ranh Giới Nghiên Cứu (RUO Boundary)**:
   - Nhãn kết quả ADNEX và O-RADS luôn đi kèm cờ `requires_clinician_confirmation: true` và `evidence_status: "UNVALIDATED_RESEARCH_PROTOTYPE"`.
