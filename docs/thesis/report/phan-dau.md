# XÂY DỰNG HỆ THỐNG HỖ TRỢ PHÂN ĐOẠN TỔN THƯƠNG TRÊN ẢNH SIÊU ÂM BUỒNG TRỨNG ỨNG DỤNG DEEP LEARNING THEO MÔ HÌNH HUMAN-IN-THE-LOOP

# MỤC LỤC

# LỜI CAM ĐOAN

Tôi trình bày khóa luận này trên cơ sở đề cương nghiên cứu, mã nguồn và các hồ sơ thực nghiệm được lưu trong dự án. Các nội dung tham khảo về mô hình, phương pháp và công cụ được chỉ nguồn. Bài khóa luận của Đinh Mạnh Hòa được dùng làm mẫu kết cấu và cách trình bày; nội dung nghiệp vụ cho thuê xe không được chuyển thành nội dung chuyên môn của đề tài phân đoạn siêu âm.

Các số liệu trong báo cáo được phân biệt theo nguồn: số liệu dự kiến trong đề cương, thống kê từ manifest, kết quả trong run config và báo cáo đánh giá, cùng log kiểm thử phần mềm. Tôi không sử dụng dữ liệu minh họa giao diện để thay thế dữ liệu thực nghiệm mô hình và không gọi các phản hồi chưa có người tham gia là kết quả khảo sát bác sĩ. Những hạn chế về nguồn ảnh, mã bệnh nhân, trạng thái phê duyệt nhãn và phép đánh giá được công bố cùng kết quả.

Bản thảo này được biên soạn với sự hỗ trợ của công cụ AI trong tổ chức nội dung, diễn giải mã nguồn và dựng hình. Trách nhiệm đối chiếu hồ sơ, rà soát học thuật và chốt bản nộp thuộc sinh viên thực hiện. Báo cáo mô tả bản mẫu nghiên cứu, không xác nhận thiết bị y tế được cấp phép, không thay thế chẩn đoán chuyên môn và không tạo kết luận lành hoặc ác tính từ mask nhị phân.

Nguyễn Hữu Dũng

# LỜI CẢM ƠN

Tôi xin cảm ơn các thầy cô Khoa Hệ thống Thông tin Quản lý, Trường Công nghệ, Đại học Kinh tế Quốc dân đã cung cấp nền tảng về phân tích nghiệp vụ, hệ thống thông tin, cơ sở dữ liệu và phát triển phần mềm. Những kiến thức đó giúp tôi tiếp cận đề tài như một bài toán có tác nhân, dữ liệu, quy trình và trách nhiệm, đồng thời nghiên cứu thành phần học sâu phục vụ khoanh vùng trên ảnh.

Tôi xin cảm ơn ThS. Trần Thanh Hải, giảng viên hướng dẫn được ghi trong đề cương, về định hướng nghiên cứu và việc kết nối yêu cầu học thuật với sản phẩm bản mẫu. Tôi cũng xin cảm ơn các cá nhân đã hỗ trợ cung cấp tài liệu, trao đổi kỹ thuật và phản hồi trong quá trình phát triển dự án. Những phần thông tin về cơ sở thực tập VinSmart Future và bối cảnh dự kiến khảo sát Vinmec được trình bày đúng giới hạn hồ sơ hiện có.

Đề tài còn những câu hỏi cần tiếp tục kiểm chứng về provenance dữ liệu, tính độc lập bệnh nhân và hiệu quả sử dụng với người chuyên môn. Tôi mong nhận được góp ý để hoàn thiện cách đặc tả, thiết kế và đánh giá ở các giai đoạn tiếp theo. Các lời cảm ơn không được dùng để suy rằng một đơn vị đã phê duyệt triển khai hoặc xác nhận toàn bộ số liệu của nghiên cứu.

# DANH MỤC TỪ VIẾT TẮT

| Từ viết tắt | Cụm từ đầy đủ | Nghĩa dùng trong báo cáo |
|---|---|---|
| AC | Acceptance Criteria | Tiêu chí nghiệm thu |
| AI | Artificial Intelligence | Trí tuệ nhân tạo |
| API | Application Programming Interface | Giao diện lập trình ứng dụng |
| BA | Business Analyst | Chuyên viên phân tích nghiệp vụ |
| BCE | Binary Cross-Entropy | Hàm mất mát phân loại nhị phân theo pixel |
| BFD | Business Function Diagram | Sơ đồ phân rã chức năng |
| BS | Bác sĩ | Vai trò người rà soát trong thiết kế |
| CD | Context Diagram | Sơ đồ ngữ cảnh |
| CNN | Convolutional Neural Network | Mạng nơ-ron tích chập |
| DFD | Data Flow Diagram | Sơ đồ luồng dữ liệu |
| DICOM | Digital Imaging and Communications in Medicine | Chuẩn dữ liệu và truyền thông ảnh y tế |
| ERD | Entity Relationship Diagram | Sơ đồ quan hệ thực thể |
| FN / FP | False Negative / False Positive | Pixel bị bỏ sót / khoanh thừa so với mask tham chiếu |
| FR / NFR | Functional / Non-functional Requirement | Yêu cầu chức năng / phi chức năng |
| GT | Ground Truth | Nhãn tham chiếu; trạng thái chuyên gia xác nhận phải có hồ sơ |
| HITL | Human-in-the-Loop | Quy trình có người kiểm tra và hiệu chỉnh |
| IoU | Intersection over Union | Tỷ lệ giao trên hợp hai vùng |
| IQA | Image Quality Assessment | Đánh giá chất lượng ảnh ở cấp kỹ thuật |
| MIS | Management Information Systems | Hệ thống Thông tin Quản lý |
| ORM | Object-Relational Mapping | Ánh xạ đối tượng–quan hệ |
| PID | Patient Identifier | Mã giả danh bệnh nhân |
| QT | Quản trị | Vai trò vận hành kỹ thuật trong thiết kế |
| RBAC | Role-Based Access Control | Phân quyền theo vai trò |
| RLE | Run-Length Encoding | Mã hóa độ dài chuỗi pixel |
| ROI | Region of Interest | Vùng quan tâm |
| SDLC | Software Development Life Cycle | Vòng đời phát triển phần mềm |
| SPA | Single-Page Application | Ứng dụng web một trang |
| SRS | Software Requirements Specification | Đặc tả yêu cầu phần mềm |
| TK | Trưởng khoa | Vai trò duyệt trong thiết kế mở rộng |
| TP / TN | True Positive / True Negative | Pixel đúng tiền cảnh / đúng nền |
| UI / UX | User Interface / User Experience | Giao diện / trải nghiệm người dùng |

# DANH MỤC BẢNG BIỂU

# DANH MỤC HÌNH VẼ

# LỜI MỞ ĐẦU

Trong một hệ thống hỗ trợ đọc ảnh, giá trị của AI không chỉ nằm ở việc tạo một đầu ra tự động mà còn ở khả năng người sử dụng nhìn thấy, kiểm tra và kiểm soát đầu ra đó. Đối với ảnh siêu âm buồng trứng, một mask phân đoạn có thể biểu diễn vị trí và hình dạng vùng được chú giải. Tuy nhiên mask nhị phân không mô tả đầy đủ hình thái chuyên môn, không cung cấp thông tin mô bệnh học và không tự quyết định tính lành hay ác. Đề tài vì thế lựa chọn bài toán hỗ trợ khoanh vùng, kết hợp mô hình học sâu và giao diện hiệu chỉnh, giữ quyết định rà soát ở con người.

Khó khăn kỹ thuật của bài toán xuất phát từ chất lượng ảnh không đồng nhất, biên vùng quan tâm mờ, kết cấu và nhiễu ảnh, cùng yêu cầu chuẩn hóa hình học giữa ảnh nguồn và đầu vào mô hình. Khó khăn của hệ thống thông tin nằm ở cách tổ chức cặp ảnh–mask, trạng thái ca, các bản prediction và review, quyền thao tác và khả năng truy vết. Nếu chỉ lưu mask cuối mà không lưu prediction gốc, khó xác định phần máy đề xuất và phần người đã sửa. Nếu giao diện hiển thị mm khi chưa có spacing, thông tin đo bị diễn giải sai dù mask được vẽ đúng. Những vấn đề này cho thấy thuật toán và quản trị quy trình cần được thiết kế cùng nhau [12], [17], [18].

Mục tiêu của khóa luận là xây dựng một bản mẫu web hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng bằng Deep Learning theo mô hình Human-in-the-Loop. Các nhiệm vụ bao gồm phân tích quy trình tham chiếu, xây dựng SRS, mô hình hóa chức năng và luồng dữ liệu, nghiên cứu U-Net/U-Net++, triển khai tiền xử lý 512×512, thiết kế cơ sở dữ liệu và API, xây dựng giao diện Canvas, cùng kiểm thử và đánh giá theo chứng cứ. Cặp ảnh Trái/Phải được tiếp nhận rõ ràng ở quy trình phần mềm; mỗi ảnh vẫn là một đầu vào suy luận hai chiều độc lập.

Đối tượng nghiên cứu ở cấp thuật toán là quan hệ giữa ảnh và nhãn pixel nhị phân. Ở cấp hệ thống là quá trình từ tiếp nhận ảnh đến gợi ý AI, thao tác hiệu chỉnh và lưu review. Phạm vi là môi trường nghiên cứu local cùng những artifact hiện hữu trong repository. VinSmart Future là cơ sở thực tập và Vinmec Times City là bối cảnh dự kiến khảo sát trong đề cương; bản thảo không khẳng định hệ thống đã tích hợp PACS/RIS hay đi vào vận hành bệnh viện. Các quy trình As-Is được dùng như mô hình tham chiếu cần được xác nhận bằng khảo sát thực địa.

Phương pháp nghiên cứu gồm phân tích tài liệu, đọc mã nguồn, đối chiếu dữ liệu và cấu hình, mô hình hóa hệ thống, phát triển prototype và kiểm thử. Các khái niệm kiến trúc được tham chiếu bài báo gốc; thông tin implementation lấy từ mã và run config. Kết quả định lượng được truy đến tập ảnh, checkpoint và cách tổng hợp metric. Khi thiếu nguồn xác nhận số bệnh nhân hoặc duyệt nhãn, kết luận được giới hạn ở mức phù hợp với file tham chiếu. Khi chưa có khảo sát bác sĩ, mục tiêu giảm thời gian được giữ là câu hỏi cần kiểm định.

Theo kết cấu bài mẫu Đinh Mạnh Hòa và hướng dẫn Khoa [13], [14], báo cáo tổ chức thành ba chương chính. Chương 1 trình bày cơ sở thực tập, bối cảnh áp dụng và đề tài nghiên cứu. Chương 2 trình bày cơ sở lý thuyết, phương pháp và công cụ cần thiết. Chương 3 triển khai giải pháp từ mô tả bài toán, yêu cầu, sơ đồ, dữ liệu đến mô hình AI, giao diện, kiểm thử và cài đặt. Các nhóm nội dung của đề cương năm chương được giữ trong các mục tương ứng, không lược bỏ nghiên cứu mô hình hay đánh giá hệ thống. Kết luận tổng hợp kết quả, hạn chế và hướng phát triển; phụ lục cung cấp nguồn tái lập và công cụ khảo sát dự kiến.
