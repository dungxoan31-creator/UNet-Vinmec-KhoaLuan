# KẾT LUẬN

## Kết quả đạt được

Đề tài xây dựng một cách tiếp cận liên kết ba thành phần: quy trình nghiệp vụ có người kiểm soát, mô hình phân đoạn pixel và bản mẫu web tương tác. Phần tổng quan xác định phạm vi hỗ trợ khoanh vùng trên ảnh siêu âm hai chiều, không kết luận bệnh học từ mask. Phần lý thuyết lựa chọn U-Net làm mô hình cơ sở, U-Net++/ResNet34 làm cấu hình đối chứng, cùng các phương pháp phân tích MIS và quản trị dữ liệu. Phần triển khai chuyển yêu cầu đó thành sơ đồ chức năng, luồng dữ liệu, cơ sở dữ liệu, API và giao diện có thể rà soát từng ảnh.

Về mô hình, hai cấu hình đối sánh có run config và lịch sử 30 epoch, dùng cùng 661 ảnh Train và 541 ảnh Validation, loss kết hợp BCE–Dice, threshold 0,5. Validation Dice của Standard U-Net comparator là 0,738296, của U-Net++ là 0,817036; Validation IoU lần lượt 0,626416 và 0,732287. Các con số phản ánh hai cấu hình tổng thể, trong đó encoder U-Net++ pretrained còn Standard khởi tạo ngẫu nhiên. Không quy toàn bộ chênh lệch cho một thành phần skip connection. Kết quả Test Standard thuộc hồ sơ lịch sử của checkpoint khác; U-Net++ chưa có Test trong hồ sơ đối sánh. Do vậy khóa luận chưa kết luận mô hình cải tiến vượt trội trên một cohort lâm sàng mới [16].

Về phần mềm, bản mẫu có luồng đăng nhập, tiếp nhận đủ hai ảnh, IQA, suy luận, hiển thị mask/overlay, chỉnh sửa, đo và lưu review nghiên cứu. Prediction và Review được giữ độc lập để có thể truy vết. Giao diện mở rộng thể hiện Worklist, duyệt, lịch sử, phiếu, PID, đánh giá mô hình và quản trị theo vai trò. Bộ kiểm thử lưu ngày 11/10/2026 ghi 180 bài Python pass cùng 11 script frontend thành công. Những kết quả này hỗ trợ nhận định về chức năng tại phiên bản kiểm tra; chúng không chứng minh mọi endpoint mở rộng đã được backend hiện thực [17]–[19].

Về phương pháp của ngành Hệ thống Thông tin Quản lý, đóng góp là tổ chức trách nhiệm và bằng chứng quanh một đầu ra AI. Quy trình không chỉ hỏi model tạo gì mà còn xác định ai rà soát, sửa ở đâu, lưu phiên bản nào và xuất thông tin với đơn vị gì. Việc đối chiếu số liệu đề cương với manifest cho thấy quản trị nguồn gốc là một phần của bài toán kỹ thuật. Một chỉ số Dice chỉ có ý nghĩa khi gắn với nhãn, split, checkpoint và điều kiện phép đo. Một nút xác nhận chỉ có ý nghĩa khi dữ liệu cần thiết đã lưu theo contract phù hợp.

## Hạn chế của đề tài

Hạn chế dữ liệu là chưa có hồ sơ đủ để xác nhận mã bệnh nhân nguồn, toàn bộ phê duyệt mask và quyền công bố ảnh. Số 307 ảnh/185 bệnh nhân trong đề cương không được dùng làm kết quả đã xác nhận của manifest chạy mô hình. Split thực nghiệm gồm 1.604 ảnh bảo đảm không trùng SHA-256 xuyên tập, chưa bảo đảm độc lập bệnh nhân thật. Những cặp ảnh gần trùng còn cần rà lại. Tên thư mục hoặc số lượng trùng một dataset công khai không tự chứng minh nguồn. Vì vậy kết quả là mức khớp với mask tham chiếu hiện hữu, không phải chứng nhận hiệu năng lâm sàng của dữ liệu bệnh viện riêng [12], [15], [16].

Hạn chế thực nghiệm gồm một seed chính, khác biệt khởi tạo encoder, chưa có ablation tách từng quyết định tiền xử lý/loss và chưa có Test mới cho U-Net++. Test Standard đã được dùng trong các lượt trước nên không được coi là một phép kiểm định mù mới. Metric trung bình chưa thay thế phân tích các ca thất bại hoặc sự khác biệt giữa nguồn ảnh. Đo hình học hai trục trên lát cắt không cho phép suy thể tích hay áp dụng đầy đủ một hệ thống phân tầng nguy cơ. Thiếu spacing phải giữ px; mask rỗng chỉ phản ánh kết quả phân đoạn theo quy ước nhãn.

Hạn chế triển khai gồm backend hiện có hai vai trò DOCTOR/ADMIN, chưa có đầy đủ ownership theo khoa, tài khoản TK, OTP, lease server, workflow duyệt hai cấp, addendum bất biến hay pipeline ẩn danh/OCR vận hành. Các màn frontend tương ứng đã mô hình hóa được trong demo, nhưng demo không được dùng như bằng chứng server bảo vệ dữ liệu thật. Chưa có benchmark 60 fps trên máy bác sĩ, khảo sát screen reader đầy đủ hay hồ sơ restore dữ liệu vận hành. Mục tiêu thao tác nhanh và hiệu quả HITL chưa có số liệu người tham gia để kết luận [18], [19].

## Hướng phát triển

Ưu tiên tiếp theo là hoàn thiện hồ sơ dữ liệu: xác nhận nguồn, điều kiện sử dụng, danh mục ảnh và mapping bệnh nhân ổn định; rà các ảnh gần trùng; xác định trạng thái nhãn theo người tạo/người duyệt/phiên bản. Sau đó tạo một cohort đánh giá mới theo bệnh nhân, khóa checkpoint và threshold trước khi mở Test. Các lượt thí nghiệm tiếp theo nên giữ chính sách encoder có thể so sánh, chạy nhiều seed và phân tích thêm biên, vùng nhỏ, ca rỗng và ngoài miền. Những bước này tạo nền tảng cho kết luận mạnh hơn, thay vì chỉ tăng số kiến trúc trong bảng.

Phần hệ thống cần tích hợp API workspace có transaction cho hai ảnh, kiểm version/lease ở biên mutation, quyền theo người/khoa, lịch sử trạng thái và provenance prediction được lưu bền. Tài khoản cá nhân, quản lý phiên và audit server cần được xây dựng trước khi sử dụng dữ liệu thật. Ẩn danh cần xử lý cả metadata và chữ in cứng, giữ lại thông tin cần cho phép đo nhưng không tự xác nhận thành công bằng một flag frontend. Phiếu vẫn phải ghi phạm vi nghiên cứu cho tới khi có quy trình được đơn vị có thẩm quyền phê duyệt.

Đánh giá người dùng cần protocol, ca được phép sử dụng, người tham gia đúng vai trò và chỉ số thời gian/mức sửa được định nghĩa trước. Thử nghiệm pilot giúp sửa lỗi thao tác, sau đó mới tiến hành đo chính thức. Phản hồi mask của bác sĩ nếu dùng huấn luyện lại cần quy trình duyệt và phiên bản hóa, tránh làm thay đổi Test đã khóa. Hiệu quả của HITL được xác định từ công việc thực tế, không từ một giao diện đẹp hay độ trễ suy luận thấp.

Kết luận chung của khóa luận là đã hình thành một prototype nghiên cứu có đường đi rõ từ yêu cầu đến mô hình và vòng rà soát, cùng các artifact hỗ trợ kiểm tra lại. Báo cáo giữ những kết quả có nguồn, mô tả đầy đủ giao diện và kiến trúc, đồng thời chỉ ra chính xác điều kiện chưa hoàn tất. Đây là cơ sở để tiếp tục kiểm định và hoàn thiện sản phẩm trong một nghiên cứu có sự phối hợp của nguồn dữ liệu và người dùng chuyên môn.

# PHỤ LỤC

## Phụ lục A. Danh mục hồ sơ để tái lập

| Hồ sơ | Đường dẫn trong repository | Mục đích |
|---|---|---|
| Đề cương | `docs/Email/attachments/MSV_11235559_NguyenHuuDung_DeCuongSoBo.docx` | Mục tiêu và kế hoạch gốc |
| Manifest | `ai_training/splits/unified_vinmec_clean_2026-10-06/manifest.json` | Số ảnh và giới hạn identity |
| Bằng chứng mapping | `docs/reports/M3_Bang_Chung_Du_Lieu_2026-10-08.md` | Đối chiếu chuỗi mã, tệp và giao tập |
| Workbook nguồn | `docs/reports/Mau_Xin_Danh_Muc_Anh_Patient_Case_ID_2026-10-07.xlsx` | Phiên bản 1.639 dòng; chưa xác minh tính ổn định mã |
| Comparator Standard | `checkpoints/standard_unet_gray_imagenet_norm_2026-10-06/run_config.json` | Cấu hình và Validation |
| Candidate U-Net++ | `checkpoints/unetplusplus_resnet34_2026-10-06/run_config.json` | Cấu hình và Validation |
| Test lịch sử | `evaluation/milestone_3_2026-10-06/test_summary.json` | Phạm vi Test Standard |
| Theo ảnh Test | `evaluation/milestone_3_2026-10-06/test_per_image.csv` | Phân phối và phân tích lỗi |
| Mã mô hình | `backend/models/unet.py` | Kiến trúc baseline |
| Tiền xử lý | `backend/services/preprocessor.py` | Letterbox và ánh xạ |
| Suy luận | `backend/services/inference_engine.py` | Checkpoint, threshold và đầu ra |
| Database | `backend/db/database.py` | ORM và ràng buộc |
| Frontend | `frontend/app/`, `frontend/css/` | Giao diện, state, viewer và quyền UI |
| Thiết kế/API | `docs/reports/Workspace_V2_Design_and_API.md` | Contract hiện có và cần bổ sung |
| Bằng chứng phần mềm | `artifacts/workspace-v2/*verification.log` | Log ngày 11/10/2026 |
| Ảnh giao diện | `artifacts/workspace-v2/*.png` | Ảnh chụp demo desktop/tablet |

## Phụ lục B. Phiếu ghi nhận tác vụ dự kiến

Phiếu này là công cụ chuẩn bị đánh giá người dùng, chưa có dữ liệu người tham gia. Mã người tham gia là mã nghiên cứu, không dùng tên thật trong bản công bố. Thời điểm bắt đầu/kết thúc phải đo theo protocol; nếu chưa đo, ghi “Chưa thu thập” thay cho số 0. Một tác vụ có lỗi kỹ thuật được ghi riêng, không loại bỏ âm thầm để làm thời gian trung bình đẹp hơn.

| Trường ghi nhận | Quy tắc nhập | Trạng thái hiện tại |
|---|---|---|
| Mã người tham gia | Mã nghiên cứu do protocol cấp | Chưa thu thập |
| Vai trò/nhóm kinh nghiệm | Nhóm phù hợp protocol, không định danh | Chưa thu thập |
| Mã ca và phiên bản | Liên kết đúng bộ ảnh được phép dùng | Chưa thu thập |
| Điều kiện tác vụ | Thủ công hoặc AI + HITL; thứ tự đối cân bằng | Chưa thu thập |
| Thời gian chuẩn bị | Tách upload/chờ AI nếu protocol yêu cầu | Chưa thu thập |
| Thời gian rà soát | Từ ảnh sẵn sàng đến lưu mask thành công | Chưa thu thập |
| Action cuối mỗi bên | Giữ AI / Sửa / Mask rỗng / Từ chối | Chưa thu thập |
| Mức sửa | Quy tắc định lượng/định tính đặt trước | Chưa thu thập |
| Lỗi và gián đoạn | Mạng, AI, viewer, đơn vị, lưu hoặc quyền | Chưa thu thập |
| Nhận xét | Vấn đề quan sát được, không nhập PHI | Chưa thu thập |

## Phụ lục C. Câu hỏi phỏng vấn sau tác vụ

Người tham gia được hỏi liệu có phân biệt rõ ảnh nguồn, mask AI và mask sau sửa không; trường hợp nào cần tắt overlay; các công cụ có đủ để sửa biên không; có nhận ra đơn vị px khi chưa hiệu chuẩn không; có biết tác vụ đã lưu server hay chỉ còn nháp không; có hiểu lý do bị từ chối và phiên bản ca đang sửa không. Với mỗi câu trả lời, người quan sát yêu cầu mô tả một thao tác hoặc một ca cụ thể để tránh nhận xét chung như “dễ dùng”.

Một câu hỏi bổ sung là trong điều kiện AI sai, người dùng có dễ bỏ mặt nạ và bắt đầu vẽ lại hay không. Câu hỏi khác kiểm việc cảnh báo ảnh kém có nói rõ lựa chọn tiếp theo không, và liệu ký tóm tắt hai bên có giúp phát hiện thiếu ảnh hoặc nhầm bên không. Những phản hồi này phục vụ cải tiến giao diện, không được chuyển tự động thành kết luận lâm sàng. Nếu áp dụng SUS, bổ sung thang đo đã xác minh và cách chấm đúng trước khi thu thập.

## Phụ lục D. Quy trình chốt gói nộp

Gói nộp gồm bản Word, bản PDF đối chiếu, Markdown nguồn, ảnh đã nhúng, mã sơ đồ và tài liệu nguồn. Đối với mã hệ thống, chốt phiên bản, chạy test lại trên môi trường cô lập và lưu log. Đối với mô hình, giữ checkpoint, run config, manifest và metric theo cùng phiên bản. Không đưa token, mật khẩu, raw metadata định danh hoặc tệp chưa rõ quyền chia sẻ vào gói công bố. Những thông tin chưa xác minh vẫn giữ nhãn trạng thái, không bỏ khỏi bản nộp chỉ để trông như mọi mục tiêu đều hoàn thành.

Mục lục và danh mục được tạo bằng trường Word, có thể cập nhật khi chỉnh sửa. Nếu di chuyển hoặc thay hình, cần cập nhật trường và xuất lại PDF để kiểm bố cục. Nguồn Mermaid cho phép sửa sơ đồ riêng mà không làm biến đổi mã chạy ứng dụng. Hình chụp demo trong báo cáo cần giữ nhãn demo khi tái sử dụng cho slide, vì việc cắt bỏ nhãn có thể làm người xem nhầm đó là hồ sơ thực nghiệm.
