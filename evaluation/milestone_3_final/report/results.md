# Báo cáo Đánh giá Định lượng và Thực nghiệm Mô hình Phân đoạn Buồng trứng

> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop
> **Thời điểm tạo**: 2026-10-17T03:41:19.929611+00:00
> **Trạng thái nguyên mẫu (Prototype Ready)**: PASS
> **Trạng thái đánh giá khoa học (Evaluation Complete)**: PARTIAL / BLOCKED

---

## 1. Thông tin Mô hình và Cấu hình Suy luận

- **Kiến trúc mạng**: Standard U-Net (Baseline v1)
- **Checkpoint SHA-256**: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`
- **Kích thước đầu vào**: 512×512 (Letterbox bảo toàn tỷ lệ khung hình gốc)
- **Ngưỡng nhị phân hóa**: $\ge 0.5$ (không áp dụng hình thái học morphology post-processing)
- **Không gian dự đoán**: Native Resolution (hồi phục kích thước ảnh gốc qua inverse letterbox)

---

## 2. Kết quả Đánh giá Phân đoạn Định lượng

| Tập dữ liệu / Vai trò | Số mẫu | Dice Mean (Median) | IoU Mean (Median) | Độ nhạy Recall | Độ chính xác Precision | Độ đặc hiệu Specificity | HD95 (px) |
|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Retrospective Test Replay (Historical Data)** | 402 | 0.7289 (0.8045) | 0.6176 (0.6729) | 0.7304 | 0.8140 | 0.9771 | 90.19 |
| **Validation Cohort** | 541 | 0.6717 (0.7588) | 0.5542 (0.6113) | 0.6979 | 0.7527 | 0.9726 | 102.43 |

> [!NOTE]
> Các metric rỗng/null do không có foreground hoặc chưa chạy độc lập được bảo toàn nguyên trạng, không bao giờ gán cưỡng bức bằng 0.0.

---

## 3. Phân tích Lỗi Định tính (Error Analysis)

Phân tích lỗi được thực hiện theo 8 nhóm hình thái và trường hợp biên (Milestone 3 Protocol):
- **Best / Median / Worst cases**: Xếp hạng theo chỉ số Dice đối chiếu trực quan 5 cột (Original, GT, Prediction, Overlay, Difference).
- **Bỏ sót tổn thương (False Negative Dominant)**: Mô hình bỏ sót các tổn thương nhỏ phân tán hoặc u có bờ ranh giới cản âm mờ nhạt.
- **Lan vùng giả dương (False Positive Dominant)**: Nhầm lẫn vùng bóng cản âm của ruột, bàng quang hoặc nang noãn buồng trứng sinh lý thành u nang.
- **Lỗi ranh giới (Boundary Ambiguity)**: Lớp mask nhị phân có độ biến động cao ở vùng ranh giới tiếp giáp nhu mô lành.
- **Truy vết minh chứng**: Toàn bộ panel đối chiếu được lưu trữ tại `evaluation/milestone_3_final/legacy_test_v1/error_analysis/`.

---

## 4. Đo lường Quy trình Tương tác Human-in-the-Loop (HITL)

- **Tổng số phiên ghi nhận**: 32 phiên
- **Phiên thử nghiệm kỹ thuật (Technical Sessions)**: 24 phiên
- **Phiên bác sĩ (Clinician Sessions)**: 0 phiên
- **Tổng số tác vụ chỉnh sửa (Total Tasks)**: 15 tác vụ
- **Thời gian phản hồi rà soát trung vị (Median Review Time)**: Chưa có / Không xác định ms
- **Độ cải thiện Dice trước và sau chỉnh sửa (Δ Dice)**: Chưa có / Không xác định (chưa tính nếu thiếu nhãn độc lập)

> [!IMPORTANT]
> Dữ liệu HITL phân định rạch ròi giữa thao tác của kỹ sư kiểm thử (Technical) và bác sĩ lâm sàng (Clinician). Không tự động nội suy điểm cải thiện chất lượng khi chưa có nhãn tham chiếu độc lập.

---

## 5. Khảo sát Người dùng và Tính Khả dụng Lâm sàng

- **Trạng thái nghiên cứu người dùng**: `NOT_CONDUCTED`
- **Số lượng bác sĩ tham gia (Clinicians)**: 0 bác sĩ
- **Số lượng kỹ thuật viên / kiểm thử viên**: 1 người
- **Có đánh giá lâm sàng độc lập**: CHƯA (NOT_CONDUCTED)
- **Biên bản nghiệm thu kỹ thuật (Technical Acceptance)**: PASS (Quy trình nạp, sửa, hoàn tác, lưu atomic và xuất ZIP hoạt động ổn định).

> [!WARNING]
> Nghiên cứu không ngụy tạo kết quả khảo sát Likert của bác sĩ. Mọi đánh giá tính khả dụng hiện tại dựa trên quy trình nghiệm thu kỹ thuật nội bộ (Technical Acceptance Protocol) và ghi nhận trạng thái trung thực `NOT_CONDUCTED` cho khảo sát lâm sàng.

---

## 6. Giới hạn Hệ thống và Khuyến cáo Lâm sàng

1. **Bất thường $\neq$ Ác tính (Abnormal $\neq$ Malignant)**: Vùng phân đoạn chỉ mang tính chất định vị tổn thương hình thái, không phải chẩn đoán bản chất mô bệnh học u lành/u ác.
2. **Pixel Recall $\neq$ Độ nhạy chẩn đoán lâm sàng**: Chỉ số Recall trên pixel phản ánh độ bao phủ không gian của mask, không đo lường độ nhạy phát hiện bệnh nhân ung thư.
3. **Tập kiểm thử độc lập bị chặn (Independent Test Gate: BLOCKED)**: Do chưa có hồ sơ bệnh nhân gốc và chứng từ khử định danh độc lập, tập 402 ảnh chỉ được coi là Retrospective Test Replay.
4. **Nguyên mẫu nghiên cứu hỗ trợ quan sát (Observation-Only Prototype)**: Hệ thống chưa được phê duyệt cho chẩn đoán y tế hoặc chỉ định phẫu thuật/điều trị thực tế.

---

## 7. Kết luận và Đề xuất Hướng Phát triển

- **Hoàn thành nguyên mẫu nghiên cứu (Prototype Readiness: PASS)**: Hệ thống đáp ứng toàn bộ các yêu cầu tương tác Human-in-the-Loop, lưu trữ atomic, export ZIP có mã băm toàn vẹn SHA-256, chạy bền vững qua restart.
- **Khuyến nghị tiếp theo**: Thu thập tập dữ liệu kiểm thử độc lập có đầy đủ Patient ID và đồng thuận chuyên gia đa trung tâm để mở khóa cổng đánh giá khoa học toàn diện (`evaluation_complete`).
