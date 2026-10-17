# Phạm vi đề tài và thiết kế đóng mốc — 17/10/2026

Nguồn: nội dung người dùng cung cấp ngày 17/10 về hướng đề tài được thầy xác nhận. Đây là cập nhật ưu tiên cho spec/plan 16/10; không sửa lịch sử kết quả hoặc coi thông báo này là phê duyệt triển khai code mới.

## Tên đề tài và luồng cốt lõi

**Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop.**

Ảnh siêu âm → Preprocessing → Segmentation → Mask/Overlay → Doctor Review/Edit/Confirm → Đánh giá kết quả.

Sản phẩm là prototype nghiên cứu chạy được, trình diễn được, lưu và mở lại kết quả rà soát, có bằng chứng đánh giá. Confirm là xác nhận mask rà soát nghiên cứu, không mặc nhiên là chữ ký lâm sàng hay nhãn chuyên gia chính thức. Giữ Letterbox 512×512, Combo Loss đã khóa và yêu cầu chia dữ liệu theo Patient ID nguồn.

## Các mốc do người dùng cung cấp

| Thời gian | Sản phẩm cần chứng minh | Cách xử lý ngày 17/10 |
|---|---|---|
| 06/09–20/09 | Thống kê dữ liệu/GT; patient split; preprocessing image–mask; U-Net baseline; Raw→Training→Prediction→Metrics | Kiểm tra hồ sơ đã có, không tự ghi đã hoàn tất hoặc chạy lại training chỉ để khớp lịch |
| 21/09–05/10 | Tinh chỉnh trên Validation; kiến trúc so sánh nếu phù hợp; model chọn; Upload→AI→Overlay→Edit→Confirm | Tận dụng triển khai hiện có, chỉ sửa lỗi làm hỏng luồng lõi |
| 06/10–18/10 | Independent Test; quantitative/error/HITL analysis; bác sĩ nếu tiếp cận được; tổng hợp kết quả | Đóng bằng chứng và blocker; không đổi tên replay thành independent |
| Từ 19/10 | Báo cáo KLTN, rà soát model/prototype/kết quả, chuẩn bị bảo vệ | Đóng băng baseline; chỉ mở thay đổi sửa lỗi có test hoặc bổ sung bằng chứng còn thiếu |

## Phạm vi ưu tiên

Bắt buộc: segmentation, mask/overlay, review/edit/confirm, lưu/export phục vụ rà soát, kiểm thử và báo cáo có provenance. Hạ tầng auth/persistence hiện có được giữ để bảo vệ luồng này. Bác sĩ là nhánh có điều kiện; không tiếp cận được thì technical fallback có protocol và giới hạn rõ, không giả kết quả bác sĩ.

Chỉ xét sau khi lõi đạt nghiệm thu và còn thời gian: sinh mô tả/chẩn đoán, LLM/VLM, Draft Report Suggestion, Dashboard mở rộng. Không xóa chức năng đang có hoặc xây lại UI chỉ để thu hẹp phạm vi; không dùng các phần này làm bằng chứng đạt mục tiêu chính.

## Thiết kế nghiệm thu

- `prototype_ready`: chỉ true khi có log kiểm thử live hiện hành, đúng phiên bản/checkpoint, save/reopen/export và các regression bắt buộc.
- `evaluation_complete`: cần independent Test có bằng chứng theo bệnh nhân, kết quả định lượng/error/HITL đầy đủ, regression/báo cáo nhất quán; clinician study đã thực hiện **hoặc** technical fallback được nghiệm thu và công khai giới hạn.
- `clinician_validation`: trạng thái riêng, không tự chuyển true khi fallback đạt; JWT DOCTOR hoặc session tự khai clinician không đủ xác minh người tham gia.
- Thiếu patient mapping/nhãn đủ kiểm chứng thì scientific gate BLOCKED; được bàn giao prototype với giới hạn, không tuyên bố toàn bộ mốc đã hoàn thành.

## Bằng chứng hiện hành cần đối chiếu

HEAD khảo sát `25af869`; ledger `.superpowers/sdd/2026-10-16-system-evaluation-and-prototype/progress.md` ghi đã triển khai 20 task. `release_status.json` ghi prototype_ready=true/evaluation_complete=false, chỉ là trạng thái artifact cần đối chiếu. Log pytest release ghi 30 passed nhưng script chỉ chỉ định bốn file; không gọi đó là full regression. Independent audit đang BLOCKED.

HITL summary hiện ghi 32 sessions, trong đó 4 được gắn clinician; study_status lại ghi 0 bác sĩ/NOT_CONDUCTED. Đây là mâu thuẫn provenance phải phân loại, chưa đủ căn cứ kết luận có bác sĩ thật hoặc có giả mạo. Không xuất số 4 như kết quả clinician trước khi có hồ sơ người tham gia. Manual acceptance chứa checkpoint hash khác manifest chọn; report builder có timestamp/hash/technical_count mặc định và hai cách tính completion khác nhau. Plan tiếp theo phải khép các khoảng trống bằng chứng này, không xây lại 20 task.

## Lựa chọn và tự rà soát

Khuyến nghị: ổn định và đóng bằng chứng lõi. Lựa chọn thứ hai là thêm mô hình so sánh nếu đã có thí nghiệm Validation hợp lệ; không mở training mới trên critical path 17–18/10. Mở LLM/VLM/dashboard lúc này không phục vụ nghiệm thu nên để sau gate lõi.

Đã rà soát: tên đề tài và bốn mốc giữ nguyên; nhánh bác sĩ có điều kiện; independent gate không bị nới; không dùng readiness artifact thay bằng chứng chạy thực; không tự triển khai/xóa tính năng. UNKNOWN còn lại: nguồn định danh bệnh nhân, phê duyệt nhãn/quyền dữ liệu, nguồn từng session, số người thực sự thao tác, full regression hiện hành và lịch bác sĩ.
