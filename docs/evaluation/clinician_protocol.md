# Quy trình Đánh giá Người dùng & Thử nghiệm Lâm sàng Giám sát (Clinician & User Evaluation Protocol)
> **Phiên bản**: Milestone 3 v1  
> **Thời điểm ban hành**: 16/10/2026  
> **Phạm vi áp dụng**: Đánh giá prototype hỗ trợ phân vùng siêu âm buồng trứng Human-in-the-Loop (HITL)

---

## 1. Mục tiêu và Giới hạn Pháp lý / Y đức
- **Mục tiêu nghiên cứu**: Đánh giá tính khả dụng (Usability), độ hữu ích trong luồng công việc (Clinical Utility), hiệu chuẩn niềm tin (Trust Calibration) và mức độ sẵn sàng ứng dụng có giám sát (Willingness for Supervised Trial) của hệ thống prototype.
- **Quy mô mẫu**: Thử nghiệm tiện ích (Convenience Pilot) gồm 1–3 bác sĩ chẩn đoán hình ảnh / sản phụ khoa, thực hiện trên 6–10 ảnh hoặc 3–5 ca song bên (Bilateral cases).
- **Cam kết pháp lý & y đức**:
  - Dữ liệu sử dụng đã được khử toàn bộ định danh cá nhân (De-identified).
  - Không bao giờ sử dụng kết quả gợi ý của hệ thống để ra quyết định điều trị y tế thực tế trên bệnh nhân.
  - Người tham gia ký thỏa thuận đồng ý tham gia nghiên cứu (Informed Consent).

---

## 2. Hướng dẫn Chuẩn hóa cho Bác sĩ (Standardized Instructions)
Người điều phối đọc nguyên văn chỉ dẫn cố định sau cho người tham gia trước khi bắt đầu:
> *"Đối chiếu ảnh gốc và đường viền do AI gợi ý; chỉnh sửa hoặc từ chối theo nhận định chuyên môn của anh/chị; lưu kết quả rà soát nghiên cứu. Không dùng kết quả này để quyết định điều trị."*

---

## 3. Cấu trúc Phiên Đánh giá (Tổng thời lượng: 30–45 phút)
1. **5 phút — Giới thiệu & Thỏa thuận Y đức**:
   - Giải thích mục tiêu nghiên cứu và giới hạn công nghệ.
   - Nhập thông tin định danh nghiên cứu (`participant_code`, vai trò).
2. **5 phút — Hướng dẫn & Thử nghiệm Làm quen (Warm-up Case)**:
   - Thao tác thử trên 01 ca mẫu: Brush, Eraser, Undo, Redo, Reset AI.
   - *Lưu ý*: Ca làm quen này không tính vào dữ liệu phân tích định lượng.
3. **15–25 phút — Thực hiện Tác vụ Nghiên cứu Chính (Main Tasks)**:
   - Bác sĩ rà soát và chỉnh sửa 3–5 ca siêu âm (tập Validation/Pilot đã được phê duyệt, tuyệt đối không dùng tập Test độc lập).
   - Hệ thống tự động ghi nhận telemetry: thời gian suy luận, thời gian rà soát, thời gian sửa tích cực, số nét vẽ và loại thao tác.
   - Không hiển thị nhãn Ground Truth hoặc điểm số Dice cho bác sĩ trong lúc làm việc để tránh thiên lệch (Observer Bias).
4. **5–10 phút — Khảo sát Đánh giá (Questionnaire & Debriefing)**:
   - Bác sĩ điền phiếu khảo sát Likert 7 mục và 4 câu hỏi định tính mở.

---

## 4. Các Chiều Đo lường (Evaluation Dimensions)

### 4.1. Đánh giá từng ảnh (Per-image Ordinal Assessment)
- **Mức độ tiếp nhận**:
  - `accepted_raw`: Chấp nhận hoàn toàn đường viền AI, không cần chỉnh sửa.
  - `minor_correction`: Chỉnh sửa cục bộ nhẹ ở ranh giới.
  - `major_correction`: Vẽ lại phần lớn hoặc thay đổi hoàn toàn hình thái tổn thương.
  - `rejected`: Từ chối hoàn toàn (xóa trắng hoặc bỏ qua do AI nhận diện sai hoàn toàn).
- **Trạng thái hoàn thành**: Hoàn thành / Cần trợ giúp / Bỏ qua.
- **Ghi chú lỗi**: Ranh giới mờ, bóng cản âm giả u, tổn thương dạng nang hỗn hợp, cấu trúc ngoài buồng trứng nhầm lẫn.

### 4.2. Thang đo Likert Phiên làm việc (Per-session Likert Scale 1–5)
Thang điểm 1 (Hoàn toàn không đồng ý) đến 5 (Hoàn toàn đồng ý), N/A cho trường hợp không áp dụng:
1. `learnability`: Dễ học cách sử dụng hệ thống.
2. `usability_mask`: Dễ thao tác chỉnh sửa mặt nạ phân vùng (Brush/Eraser/Undo/Reset).
3. `workflow_efficiency`: Giúp tôi hoàn thành việc rà soát ảnh siêu âm hiệu quả.
4. `clinical_utility`: Có ích trong quy trình làm việc chuyên môn siêu âm.
5. `decision_confidence`: Đủ tự tin để quyết định ca nào cần can thiệp chỉnh sửa.
6. `willingness_supervised`: Sẵn sàng sử dụng hệ thống trong chế độ thử nghiệm có giám sát.
7. `trust_calibration`: Tôi nhận ra khi kết quả của mô hình AI cần được kiểm tra lại.

### 4.3. Phản hồi Định tính (Qualitative Dimensions)
- Tính năng hoặc thông tin trên giao diện hữu ích nhất.
- Thao tác hoặc bước gây khó khăn hoặc chậm nhất trong quy trình.
- Trường hợp AI dự đoán khiến bác sĩ mất tin cậy và lý do bệnh học/hình thái.
- Điều kiện cần thiết để sẵn sàng ứng dụng thử nghiệm có giám sát tại phòng khám.

---

## 5. Phương án Dự phòng Kỹ thuật (Technical Fallback Protocol)
- Trong trường hợp không sắp xếp được bác sĩ tham gia trực tiếp trước thời hạn bàn giao:
  - Ghi nhận trạng thái chính thức: `study_status = NOT_CONDUCTED`.
  - Không tự bịa đặt dữ liệu Likert hay phản hồi giả của bác sĩ.
  - Kỹ thuật viên kiểm thử độc lập (Technical Tester) thực hiện đầy đủ quy trình thao tác với nhãn vai trò minh bạch `participant_role = technical_tester`.
  - Kết quả kiểm thử kỹ thuật chứng minh tính ổn định, độ trễ và tính toàn vẹn của hệ thống, nhưng không tuyên bố là nghiệm thu lâm sàng.
