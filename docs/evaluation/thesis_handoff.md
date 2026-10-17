# Hướng dẫn Bàn giao Bằng chứng Thực nghiệm & Bảo vệ Khóa luận Tốt nghiệp (Thesis Evidence Handoff Guide)
> **Đề tài**: Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop  
> **Chuyên ngành**: Hệ thống Thông tin Quản lý (MIS / ITBA / AI) – Trường Đại học Kinh tế Quốc dân (NEU)  
> **Đơn vị phối hợp thực nghiệm**: Bệnh viện Đa khoa Quốc tế Vinmec Times City  
> **Thời điểm chốt baseline**: 17/10/2026 – Chuẩn bị cho giai đoạn viết báo cáo và bảo vệ từ 19/10/2026  
> **Mã băm mô hình khóa (Model Checkpoint SHA-256)**: `417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d`

---

## 1. Tuyên bố Phạm vi Cốt lõi & Ranh giới Học thuật (Core Scope & Scientific Boundaries)

Để bảo đảm tính trung thực học thuật, kỷ luật kỹ thuật (Zero-Hallucination Protocol) và bảo vệ thành công trước Hội đồng chấm khóa luận, toàn bộ tài liệu khóa luận và slide bảo vệ cần bám sát các ranh giới sau:

1. **Abnormal $\neq$ Malignant (Bất thường không đồng nghĩa với Ác tính)**:
   - Mô hình học sâu U-Net thực hiện nhiệm vụ **phân đoạn hình thái âm học (Morphological Segmentation)**, xác định vị trí và diện tích vùng tổn thương nghi ngờ (nang, u nang, khối đặc) trên ảnh siêu âm 2D B-mode.
   - Mặt nạ phân đoạn **không** đưa ra kết luận chẩn đoán phân biệt u lành tính, u giáp biên hay ung thư buồng trứng. Việc chẩn đoán bản chất bệnh lý đòi hỏi phối hợp toàn diện các chỉ số lâm sàng (O-RADS US v2022, IOTA ADNEX, CA-125) và kết quả mô bệnh học (Histopathology).
2. **Pixel Recall $\neq$ Clinical Sensitivity (Độ phủ điểm ảnh không phải độ nhạy chẩn đoán)**:
   - Chỉ số Pixel Recall đo lường tỷ lệ các pixel tổn thương trong nhãn tham chiếu được mô hình nhận diện.
   - Tuyệt đối không quy đổi Pixel Recall thành độ nhạy phát hiện bệnh nhân trên lâm sàng (Patient-level Sensitivity).
3. **Retrospective Test Replay (402 ảnh) vs. Independent Holdout Test (BLOCKED)**:
   - Tập kiểm thử 402 ảnh hiện có là **Retrospective Test Replay** (tập dữ liệu đã từng được sử dụng để khảo sát trong các đợt phát triển trước đó).
   - Cổng kiểm thử độc lập (`independent_gate`) được giữ ở trạng thái **`BLOCKED`** do dữ liệu nguồn lịch sử chưa có ánh xạ định danh bệnh nhân (`patient_id`) được kiểm toán độc lập. Việc công khai trạng thái BLOCKED thể hiện sự chặt chẽ về phương pháp luận nghiên cứu khoa học.
4. **Hiện tượng Ảnh gần trùng xuyên Split (59 cặp)**:
   - Quá trình kiểm toán kỹ thuật đã phát hiện 59 cặp ảnh có độ tương quan cao giữa tập Train và Test/Val do chụp cùng một ca siêu âm ở các góc quét liền kề. Đây là giới hạn mang tính lịch sử của bộ dữ liệu mở và là động lực để đề xuất quy trình thu thập dữ liệu chuẩn hóa trong tương lai.
5. **Human-in-the-Loop & Khảo sát Người dùng (NOT_CONDUCTED)**:
   - Tương tác với bác sĩ lâm sàng thực tế được ghi nhận trung thực là **`NOT_CONDUCTED`** (0 bác sĩ tham gia nghiên cứu người dùng chính thức).
   - Hệ thống chứng minh tính khả dụng thông qua Quy trình Nghiệm thu Kỹ thuật Thủ công (Manual Technical Acceptance B1–B8) và bộ kiểm thử tự động Live E2E (Playwright).
   - Thao tác "Confirm" trong hệ thống là lưu trữ kết quả rà soát nghiên cứu nguyên khối (Atomic Research Review), không cấu thành chữ ký số y tế pháp lý.

---

## 2. Bảng Tổng hợp Số liệu Thực nghiệm Đã Xác minh (Verified Empirical Evidence)

Mọi bảng biểu và kết quả trích dẫn trong Khóa luận tốt nghiệp bắt buộc phải đối chiếu khớp với các artifact sau:

### 2.1. Đánh giá Mô hình Phân đoạn U-Net (Protocol v1 - 16/10/2026)
*Nguồn trích xuất: `evaluation/milestone_3_final/legacy_test_v1/summary.json` và `evaluation/milestone_3_final/validation_v1/summary.json`.*

| Tập dữ liệu | Quy mô | Vai trò đánh giá | Dice Mean (Median) | IoU Mean (Median) | Recall | Precision | Specificity | HD95 (px) |
|---|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Validation Cohort** | 541 | Tinh chỉnh & chọn ngưỡng | 0,6717 (0,7588) | 0,5542 (0,6113) | 0,6979 | 0,7527 | 0,9726 | 102,43 |
| **Retrospective Test** | 402 | Tái lập lịch sử đóng băng | 0,7289 (0,8045) | 0,6176 (0,6729) | 0,7304 | 0,8140 | 0,9771 | 90,19 |
| **Independent Holdout**| 0 | Kiểm thử độc lập cấp bệnh nhân | — | — | — | — | — | — *(BLOCKED)* |

### 2.2. Nghiên cứu So sánh Kiến trúc (Model Comparator trên Validation N=541)
*Nguồn trích xuất: `evaluation/milestone_3_audit_2026-10-06/validation_lock/model_lock.json`.*

| Kiến trúc Mô hình | Khởi tạo Trọng số | Validation Dice | Validation IoU | Validation Recall | Validation Precision |
|---|---|:---:|:---:|:---:|:---:|
| **Standard U-Net (Baseline)** | Khởi tạo ngẫu nhiên (Random Init) | 0,7383 | 0,6264 | 0,8159 | 0,7444 |
| **U-Net++ (ResNet34 Backbone)**| Tiền huấn luyện ImageNet (Pretrained) | **0,8170** | **0,7323** | **0,8345** | **0,8545** |

*(Lưu ý: U-Net++ là kết quả thực nghiệm so sánh phương pháp trên tập Validation; mô hình tích hợp mặc định phục vụ nguyên mẫu prototype hiện tại là Standard U-Net đã được chuẩn hóa Letterbox).*

### 2.3. Bằng chứng Đo lường Tương tác HITL (Human-in-the-Loop Telemetry)
*Nguồn trích xuất: `evaluation/milestone_3_final/hitl/analysis_v2/summary.json` và `docs/evaluation/hitl_session_provenance.csv`.*

| Chỉ số Đo lường | Giá trị Thực nghiệm | Ghi chú & Diễn giải |
|---|:---:|---|
| **Tổng số phiên ghi nhận (Sessions)** | 32 phiên | 28 phiên kỹ thuật hợp lệ, 4 phiên tự khai báo bác sĩ được cách ly kiểm toán (Quarantined) |
| **Số người tham gia thực tế (Unique Participants)**| 8 người | 6 kỹ thuật viên xác thực, 1 fixture tự động, 1 tài khoản chưa xác minh danh tính y tế |
| **Bác sĩ lâm sàng xác thực (Verified Clinicians)** | 0 người | Ghi nhận trung thực `NOT_CONDUCTED`, không suy diễn từ chuỗi phân quyền JWT |
| **Thời gian can thiệp trung bình (Interaction Time)**| 17,45 giây | Thời gian bác sĩ dùng cọ/tẩy tinh chỉnh đường viền mặt nạ |
| **Độ trễ suy luận AI (Inference Latency)** | ~95 ms (GPU) / ~135 ms (Pipeline) | Đo lường đơn điệu (Monotonic Time), đáp ứng thời gian thực phòng khám |

---

## 3. Khung Cấu trúc Khóa luận Tốt nghiệp Đề xuất (Thesis Structure Proposal)

Bản thảo Khóa luận Tốt nghiệp ngành Hệ thống Thông tin Quản lý nên được tổ chức thành 5 chương chặt chẽ:

- **Chương 1: Tổng quan Đề tài & Cơ sở Lý luận về CDSS trong Y tế Thông minh**:
  - Bài toán chẩn đoán hình ảnh siêu âm buồng trứng và các rào cản chủ quan.
  - Tổng quan về Hệ thống Hỗ trợ Ra quyết định Y tế (CDSS) và triết lý Human-in-the-Loop (HITL) trong chuyển đổi số y tế.
  - Phân định rõ phạm vi đề tài: Hệ thống hỗ trợ phân đoạn hình thái, không chẩn đoán tự động thay bác sĩ.
- **Chương 2: Phân tích Nghiệp vụ & Thiết kế Hệ thống HITL (ITBA / MIS Focus)**:
  - Phân tích quy trình nghiệp vụ As-Is (truyền thống) và To-Be (có AI hỗ trợ).
  - Đặc tả yêu cầu người dùng (User Requirements) và yêu cầu phi chức năng (bảo mật, cách ly PHI, toàn vẹn dữ liệu).
  - Thiết kế kiến trúc hệ thống đa tầng (FastAPI, SQLite, PyTorch, Canvas Workstation).
- **Chương 3: Phương pháp Xây dựng Mô hình Học sâu Phân đoạn Ảnh Siêu âm**:
  - Thu thập, chuẩn hóa và kiểm toán dữ liệu ảnh siêu âm Vinmec.
  - Quy trình tiền xử lý: Grayscale, CLAHE tăng cường tương phản, Letterbox $512 \times 512$ bảo toàn tỷ lệ.
  - Kiến trúc mạng Standard U-Net, hàm mất mát Combo Loss ($L_{\text{Dice}} + L_{\text{BCE}}$) và quy chuẩn suy luận.
- **Chương 4: Hiện thực hóa Nguyên mẫu & Kết quả Thực nghiệm Kỹ thuật**:
  - Giao diện máy trạm lâm sàng (Clinical Workstation 2.0): Bút vẽ (Brush), Tẩy (Eraser), Đo Caliper $d_1, d_2$.
  - Kết quả thực nghiệm định lượng trên tập Validation (541 ảnh) và Retrospective Test (402 ảnh).
  - Phân tích lỗi định tính trên 8 nhóm hình thái âm học (nang đơn thùy, u quái, khối đặc, bóng cản âm...).
  - Kết quả kiểm định tương tác HITL và nghiệm thu kỹ thuật thủ công (B1–B8).
- **Chương 5: Đánh giá Rủi ro, Giới hạn Nghiên cứu & Hướng Phát triển**:
  - Phân tích thấu đáo hiện tượng Data Leakage và lý do giữ cổng Independent Holdout ở trạng thái BLOCKED.
  - Giới hạn của việc chưa thể tổ chức thử nghiệm lâm sàng trên diện rộng với bác sĩ thực tế.
  - Lộ trình phát triển To-Be: Tích hợp chuẩn O-RADS / IOTA ADNEX và thử nghiệm đa trung tâm.

---

## 4. Kịch bản Trả lời Câu hỏi Phản biện trước Hội đồng (Defense Q&A Strategy)

Dưới đây là 5 tình huống phản biện trọng tâm từ Hội đồng chuyên môn và định hướng trả lời chuẩn mực ITBA/AI:

### Câu 1: "Tại sao chỉ số Dice trên tập Test lại cao hơn tập Validation (0.7289 so với 0.6717)?"
> **Trả lời**:  
> "Kính thưa Hội đồng, hiện tượng này xuất phát từ hai nguyên nhân kỹ thuật đã được nhóm kiểm toán làm rõ:  
> 1. Về mặt phân phối hình thái: Tập Test Replay (402 ảnh) có tỷ lệ diện tích tổn thương trung bình trên diện tích ảnh lớn hơn so với tập Validation (541 ảnh). Trong độ đo Dice Coefficient, các tổn thương có kích thước lớn hơn có xu hướng đạt điểm số cao hơn do giảm độ nhạy với sai số ở đường biên (boundary penalty).  
> 2. Về tính chất dữ liệu: Tập 402 ảnh này là tập Test lịch sử (Retrospective Test) từng được khảo sát trong các đợt thử nghiệm trước đó. Chính vì phát hiện độ lệch này, nhóm nghiên cứu đã thiết lập Cổng kiểm thử độc lập (Independent Holdout Gate) và quyết định **chưa công nhận** kết quả này là kiểm thử độc lập khách quan hoàn toàn khi chưa có bộ dữ liệu mới được phân tách triệt để cấp bệnh nhân."

### Câu 2: "Có hiện tượng rò rỉ dữ liệu (Data Leakage) giữa tập Huấn luyện và Kiểm thử không?"
> **Trả lời**:  
> "Dạ có. Báo cáo kiểm toán kỹ thuật của nhóm đã chủ động phát hiện 59 cặp ảnh có độ tương đồng cao (tương quan $\ge 0.95$) giữa tập Train và Test do dữ liệu nguồn bệnh viện trước đây chưa gắn nhãn mã bệnh nhân (Patient ID), dẫn đến các ảnh chụp cùng một bệnh nhân ở các lát cắt liên tiếp bị chia vào hai tập khác nhau.  
> Thay vì che giấu hoặc báo cáo kết quả đẹp một cách giả tạo, nhóm đã thực hiện đúng kỷ luật nghiên cứu khoa học: Công bố minh bạch 59 cặp ảnh này trong báo cáo hạn chế, ghi nhận cổng Independent Gate ở trạng thái `BLOCKED`, và đề xuất đây là bài học quan trọng nhất trong việc quản trị dữ liệu y tế trước khi huấn luyện AI."

### Câu 3: "Vai trò và đóng góp của sinh viên ngành Hệ thống Thông tin Quản lý (MIS) trong đề tài này là gì, hay đây là đề tài thuần về Khoa học Máy tính?"
> **Trả lời**:  
> "Kính thưa Thầy/Cô, đóng góp trọng tâm của đề tài mang tính chất bản chất của ngành MIS:  
> 1. **Phân tích Nghiệp vụ Y tế (Healthcare ITBA)**: Nghiên cứu không dừng lại ở việc tinh chỉnh thuật toán hộp đen, mà giải quyết bài toán tích hợp hệ thống vào quy trình khám chữa bệnh thực tế (Clinical Workflow Integration).  
> 2. **Thiết kế Mô hình Tương tác Human-in-the-Loop (HITL)**: Xây dựng cơ chế tương tác đa tầng, nơi bác sĩ giữ quyền kiểm soát tối cao, sử dụng công cụ Canvas trực quan để hiệu chỉnh kết quả AI, biến AI từ mối đe dọa thay thế thành công cụ trợ lực tin cậy.  
> 3. **Quản trị Rủi ro & Toàn vẹn Dữ liệu (IT Governance & Audit Trails)**: Thiết kế kiến trúc kiểm toán (Audit Logs), theo dõi thời gian thao tác đơn điệu, khóa phiên bản CSDL chống xung đột (Optimistic Locking) và bảo đảm tuân thủ quyền riêng tư dữ liệu y tế (loại bỏ định danh PHI)."

### Câu 4: "Hệ thống đã được bác sĩ lâm sàng đánh giá và sử dụng thực tế chưa?"
> **Trả lời**:  
> "Kính thưa Hội đồng, nhóm xin báo cáo trung thực: Trong phạm vi thời gian và điều kiện bảo mật của đợt thực tập tốt nghiệp, nhóm **chưa tiến hành được khảo sát tương tác chính thức với các bác sĩ lâm sàng tại bệnh viện** (ghi nhận trạng thái `NOT_CONDUCTED`).  
> Tuy nhiên, để đảm bảo hệ thống hoàn toàn sẵn sàng cho giai đoạn thử nghiệm có giám sát (Supervised Pilot) ngay khi được bệnh viện cấp phép, nhóm đã thực hiện quy trình Nghiệm thu Kỹ thuật Thủ công độc lập (Manual Technical Acceptance) gồm 8 bước từ B1 đến B8 và bộ kiểm thử tự động Live E2E, xác nhận 100% các tính năng tiếp nhận ca, suy luận AI, vẽ cọ/tẩy, khóa phiên bản và xuất file ZIP đều vận hành ổn định không phát sinh lỗi."

### Câu 5: "Mặt nạ phân đoạn có phân biệt được khối u nang lành tính hay ung thư buồng trứng không?"
> **Trả lời**:  
> "Dạ hoàn toàn không. Mô hình U-Net của hệ thống chỉ thực hiện phân đoạn ranh giới hình thái âm học của vùng tổn thương (nghi ngờ có khối u). Nhóm nghiên cứu quán triệt nguyên tắc y khoa quốc tế: **Bất thường không đồng nghĩa với Ác tính (Abnormal != Malignant)**.  
> Việc xác định nguy cơ ác tính trên lâm sàng bắt buộc phải áp dụng quy tắc IOTA Simple Rules, mô hình toán học IOTA ADNEX hoặc thang phân loại ACR O-RADS US v2022, kết hợp các triệu chứng lâm sàng và xét nghiệm cận lâm sàng. Hệ thống của nhóm đóng vai trò cung cấp diện tích và kích thước đo đạc chuẩn xác ($d_1, d_2$) để làm đầu vào cho các tính toán lâm sàng đó của bác sĩ."

---

## 5. Danh mục Tệp Artifact & Bằng chứng Đi kèm (Handoff Artifacts Directory)

Toàn bộ minh chứng thực nghiệm đã được đóng gói và kiểm toán toàn vẹn mã băm:

| Tên Artifact | Đường dẫn Tệp | Vai trò Minh chứng |
|---|---|---|
| **Bảng tổng hợp mốc** | [milestone_scope_matrix.csv](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/milestone_scope_matrix.csv) | Đối chiếu 16 yêu cầu nghiệp vụ xuyên suốt 4 mốc dự án |
| **Báo cáo kết quả Mốc 3** | [results.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/milestone_3_final/report/results.md) | Báo cáo định lượng và định tính tổng hợp |
| **Tuyên bố giới hạn** | [limitations.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/milestone_3_final/report/limitations.md) | Công khai 7 ranh giới khoa học và hạn chế dữ liệu |
| **Trạng thái phát hành** | [release_status.json](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/milestone_3_final/report/release_status.json) | Kết quả nghiệm thu tự động (`prototype_ready: true`, `evaluation_complete: false`) |
| **Provenance người dùng** | [hitl_session_provenance.csv](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/hitl_session_provenance.csv) | Phân định 8 người tham gia và cách ly 4 session tự khai báo |
| **Sổ tay vận hành** | [release_runbook.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/release_runbook.md) | Hướng dẫn triển khai, cài đặt và sao lưu dữ liệu |
| **Biên bản nghiệm thu** | [2026-10-18-core-acceptance.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/docs/evaluation/2026-10-18-core-acceptance.md) | Bằng chứng chạy thực tế 8 bước thao tác nguyên mẫu |
| **Kịch bản Demo** | [demo_script.md](file:///C:/Users/Dung/Documents/UNet-Vinmec-KhoaLuan/evaluation/milestone_3_final/report/demo_script.md) | Kịch bản trình diễn trực tiếp 5–7 phút trước Hội đồng |
