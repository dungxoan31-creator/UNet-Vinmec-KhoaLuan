# Báo cáo Đánh giá Định lượng và Thực nghiệm Mô hình Phân đoạn Buồng trứng

> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop
> **Thời điểm tạo**: 2026-10-19T12:44:33.183037+00:00
> **Trạng thái nguyên mẫu (Prototype Ready)**: NOT READY
> **Trạng thái đánh giá khoa học (Evaluation Complete)**: PARTIAL / BLOCKED

---

## 1. Thông tin Mô hình và Cấu hình Suy luận

- **Kiến trúc mạng**: Standard U-Net (Baseline v1)
- **Checkpoint SHA-256**: `None`
- **Kích thước đầu vào**: 512×512 (Letterbox bảo toàn tỷ lệ khung hình gốc)
- **Ngưỡng nhị phân hóa**: $\ge 0.5$ (không áp dụng hình thái học morphology post-processing)
- **Không gian dự đoán**: Native Resolution (hồi phục kích thước ảnh gốc qua inverse letterbox)

---

## 2. Kết quả Đánh giá Phân đoạn Định lượng

*Chưa có lượt chạy đánh giá nào được nạp.*

---

## 3. Phân tích Lỗi Định tính (Error Analysis)

> **Trạng thái minh chứng ngày 2026-10-22:** Thư mục `legacy_test_v1` không tồn tại, gồm cả summary và các panel được dẫn bên dưới. Checksum manifest ghi summary là `NOT_FOUND`. Các mô tả về nhóm lỗi và panel chưa được xác minh độc lập; cần khôi phục artifact gốc trước khi trích dẫn như kết quả đã kiểm chứng.

Tài liệu milestone trước đây mô tả phân tích theo 8 nhóm hình thái và trường hợp biên, gồm xếp hạng Best / Median / Worst, nhóm False Negative, False Positive và Boundary Ambiguity. Tuy nhiên, thư mục run cùng các panel, CSV và HTML được dẫn hiện không tồn tại. Vì vậy các mô tả đó là ghi chú lịch sử chưa được xác minh độc lập, không phải phát hiện lâm sàng đã kiểm chứng.

Chỉ khôi phục các kết luận này sau khi có thể đối chiếu artifact gốc theo từng ảnh và checksum. Không dùng các mô tả cũ để suy ra mức độ ác tính hoặc hiệu năng lâm sàng.

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
