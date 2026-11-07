# Kế hoạch biên soạn báo cáo theo mẫu Đinh Mạnh Hòa

## Cấu hình bản thảo

Đề tài: **Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop**. Sinh viên: Nguyễn Hữu Dũng, 11235559, HTTTQL 65A. Giảng viên hướng dẫn: ThS. Trần Thanh Hải, theo bảng thông tin trong đề cương được cung cấp. Ngôn ngữ: tiếng Việt; trích dẫn số nhất quán; đầu ra Word có thể chỉnh sửa, PDF xem trước và Markdown nguồn.

Chọn kết cấu ba chương để bám bài mẫu và hướng dẫn Khoa. Năm nhóm nội dung của đề cương vẫn được giữ, chuyển phần nghiệp vụ, AI, thiết kế và đánh giá vào các mục tương ứng của Chương 3. Đây là lựa chọn biên soạn theo yêu cầu hiện tại, không phải thay đổi đề tài hay cắt nội dung đề cương.

## Đối chiếu cấu trúc

| Bài mẫu Đinh Mạnh Hòa | Bản báo cáo của Nguyễn Hữu Dũng | Bằng chứng cần dùng |
|---|---|---|
| Bìa chính, bìa phụ, mục lục, danh mục | Giữ thứ tự; bổ sung lời cam đoan và cảm ơn | Đề cương sinh viên và hướng dẫn Khoa |
| Chương 1: Cơ sở thực tập, đơn vị áp dụng, đề tài | VinSmart Future; bối cảnh khảo sát Vinmec; mục tiêu, phạm vi, phương pháp | Đề cương; không tự tạo cơ cấu tổ chức hoặc biên bản khảo sát |
| Chương 2: Khái niệm, phương pháp và công cụ | MIS/HITL; siêu âm; CNN, U-Net/U-Net++; công cụ thực tế | Bài báo gốc, tài liệu chính thức, mã nguồn |
| 3.1 Mô tả bài toán và yêu cầu | As-Is tham chiếu, FR/NFR, Use Case, User Story/AC | Đề cương, schema và luồng ứng dụng |
| 3.2 Mô hình hóa | BFD, CD, DFD, trạng thái, hoạt động, tuần tự | Logic tiếp nhận hai ảnh và phân đoạn/rà soát |
| 3.4 Thiết kế logic | Thực thể, ERD, lược đồ và từ điển dữ liệu | Bảy ORM model hiện có |
| 3.5 Thiết kế giải thuật | Pipeline, huấn luyện, suy luận, đo hình học, đánh giá sai số | Run config, lịch sử huấn luyện, báo cáo theo ảnh |
| 3.6 Thiết kế giao diện | Toàn bộ nhóm màn nghiệp vụ, desktop/tablet, phiếu | Ảnh chụp ứng dụng, ghi rõ chế độ demo |
| 3.7 Kiểm thử | API, thuật toán, frontend, luồng thật và giới hạn khảo sát người dùng | Log kiểm thử lưu ngày 11/10/2026 |
| 3.8 Cài đặt, đào tạo, triển khai | Môi trường local, cấu hình, quy trình vận hành nghiên cứu | README, script kiểm thử và mô hình đang dùng |
| Kết luận, tài liệu tham khảo, phụ lục | Kết quả đạt được, hạn chế, hướng phát triển; nguồn và công cụ tái lập | Chỉ kết luận theo bằng chứng |

## Chuẩn trình bày lấy từ tài liệu gốc

A4; Times New Roman 13; giãn dòng 1,3; lề trên/dưới/phải 2,5 cm; lề trái 3,5 cm. Số trang ở giữa phía trên; phần nội dung đánh số Ả Rập bắt đầu tại Lời mở đầu. Bảng có tên phía trên, hình có tên phía dưới, đánh số theo chương. Mục lục và danh mục có trường Word cập nhật được. Giữ văn bản, bảng, tiêu đề chỉnh sửa được; sơ đồ có nguồn Mermaid và hình xuất riêng.

## Trình tự và checkpoint

1. Trích xuất và đọc toàn bộ ba tài liệu nguồn; đếm hình, bảng và dung lượng mẫu theo cùng phương pháp.
2. Đối chiếu đề cương với mã, manifest, checkpoint và log; chốt phạm vi chứng cứ, không dùng số dự kiến như kết quả.
3. Viết lại ba chương theo mạch mẫu; kiểm tra độ phủ SRS, mô hình, cơ sở dữ liệu, giao diện và kiểm thử.
4. Vẽ sơ đồ, đồ thị từ dữ liệu thực nghiệm; chèn ảnh chụp giao diện có chú thích demo và nguồn.
5. Ghép Word, tạo bìa/danh mục/caption, cập nhật mục lục bằng Word và xuất PDF.
6. Kiểm tra số chương, dung lượng, nguồn, hình được nhúng, định dạng; quan sát các trang bìa, mục lục, bảng, sơ đồ, màn hình và kết luận.

## Quy tắc sử dụng bằng chứng

Tập 307 ảnh/185 bệnh nhân là thông tin đề cương, chưa có hồ sơ nguồn hiện trạng đủ để xác nhận. Manifest chạy thực nghiệm có 1.604 ảnh, chia 661/541/402 và chỉ bảo đảm tách nội dung ảnh; không được gọi là đã hoàn thành patient-level split. Validation U-Net++ không đồng nghĩa Test lâm sàng. Demo giao diện BS/TK/QT không đồng nghĩa backend đã thực thi workflow hai cấp. Số đo vật lý chỉ hiển thị khi có spacing hợp lệ. Review vẫn mang cờ `is_official_ground_truth=False`. Không sao chép nội dung nghiệp vụ thuê xe, không tự tạo kết quả SUS hay thời gian bác sĩ.
