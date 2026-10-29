# Sổ giả định học thuật

Các giả định dưới đây không phải bằng chứng xác thực lâm sàng. Trạng thái biểu thị mức độ hoàn thành có thể chứng minh, không phải chấp thuận sử dụng cho chăm sóc bệnh nhân.

| Mã | Giả định và lý do | Phạm vi; rủi ro nếu sai | Thay thế bằng dữ liệu thực tế | Trạng thái |
|---|---|---|---|---|
| A1 | PostgreSQL 16 đại diện kỹ thuật cho môi trường giả định, để thiết kế kiểm thử. | Chỉ môi trường phát triển; khác cấu hình site có thể làm sai kết quả. | Kiểm thử PostgreSQL thật với cấu hình site. | BLOCKED |
| A2 | Phantom tổng hợp và ngưỡng MAE ≤1 mm hoặc 2%, ICC ≥0,90 là mục tiêu học thuật định trước. | Chỉ kiểm thử kỹ thuật, không đại diện người vận hành hay thiết bị; ngưỡng có thể không phù hợp. | Phantom hiệu chuẩn và ngưỡng được chuyên gia phê duyệt trước. | BLOCKED |
| A3 | Ca tổng hợp và quy tắc tham chiếu dùng để kiểm tra triển khai CDSS. | Không ước lượng độ chính xác chẩn đoán; ca hoặc mapping có thể thiếu. | Bộ tham chiếu và adjudication chuyên gia độc lập. | BLOCKED |
| A4 | Phân tách và khử trùng lặp mức ảnh là phạm vi hiện chứng minh được. | Không chứng minh độc lập bệnh nhân; nhiều ảnh cùng bệnh nhân có thể giao nhau. | Nhóm bệnh nhân ẩn danh đáng tin cậy từ data custodian. | RESOLVED-BY-ASSUMPTION |
| A5 | Vai trò và protocol được mô tả để chuẩn bị nghiên cứu. | Không cấp quyền nghiên cứu hay chăm sóc; trách nhiệm thực tế có thể khác. | Phê duyệt PI, ethics, cơ sở và các bên liên quan. | BLOCKED |
| A6 | Giữ checkpoint và mô tả provenance hiện có, không đổi nhãn loss. | Thiếu split lịch sử khiến tái lập không chắc chắn. | Hồ sơ huấn luyện gốc hoặc huấn luyện lại được cho phép và ghi log. | BLOCKED |
| A7 | Visit code chỉ xác định lượt khám, không xác định bệnh nhân. | Mô hình visit mới chưa được triển khai; giả định nhóm lịch sử sai có thể gộp nhầm. | Mapping được data custodian xác nhận và migration có kiểm thử. | BLOCKED |
| A8 | Người dùng chính là bác sĩ/kỹ thuật viên siêu âm, theo yêu cầu sản phẩm. | Chỉ dùng định hướng UX; nhu cầu thực tế có thể khác. | Quan sát và đánh giá người dùng được chấp thuận. | RESOLVED-BY-ASSUMPTION |
| A9 | Hai cơ sở và dữ liệu tổng hợp đủ cho kiểm thử kỹ thuật cách ly ban đầu. | Không chứng minh bảo mật vận hành; chưa triển khai mô hình scope hoàn chỉnh. | Kiểm thử site, threat model và đánh giá bảo mật độc lập. | BLOCKED |
| A10 | Luồng nghiệp vụ đề xuất dùng cho khóa luận. | Chưa được cơ sở y tế xác nhận; thao tác thực tế có thể khác. | Xác nhận quy trình, vai trò và ngoại lệ với cơ sở. | BLOCKED |
