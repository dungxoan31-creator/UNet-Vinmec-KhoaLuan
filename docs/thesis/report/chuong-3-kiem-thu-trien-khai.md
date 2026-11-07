## 3.7. Kiểm thử và đánh giá hệ thống

### 3.7.1. Mục tiêu và phạm vi kiểm thử

Kiểm thử phần mềm xác định các chức năng có thực hiện đúng contract và bất biến đã đặc tả hay không. Đối với hệ thống này, bất biến quan trọng gồm liên kết đúng ảnh với ca và bên, mặt nạ có đúng 512×512, không tự tạo đơn vị vật lý, prediction không bị ghi đè khi sửa, review không được gọi là ground truth chính thức và người không có quyền không thực hiện mutation. Một giao diện hiển thị được không đủ để chứng minh các bất biến đó; cần kiểm request, response và dữ liệu lưu. Vì vậy quy trình kết hợp kiểm thử Python, logic JavaScript, thao tác trình duyệt và kiểm tra luồng API thật [17]–[19].

Bằng chứng phần mềm trong báo cáo lấy từ các log kiểm thử lưu ngày 11/10/2026 của phiên bản Workspace V2. Đây là kết quả của lượt chạy đã có trong dự án, không được trình bày như một lượt chạy mới trong quá trình biên soạn tài liệu. Bộ Python ghi `180 passed, 3 warnings`; bộ frontend ghi 11 script thành công. Khi chốt mã nguồn để nộp, cần chạy lại đúng bộ lệnh trên phiên bản đóng gói. Báo cáo không lấy số ca kiểm thử kỹ thuật làm số bác sĩ tham gia khảo sát và không dùng thời gian chạy test như thời gian rà soát một ca khám.

*Bảng 3.1: Các lớp kiểm thử và bằng chứng hiện có*

| Lớp kiểm thử | Mục đích | Bằng chứng | Giới hạn |
|---|---|---|---|
| Python toàn repository | API, dữ liệu, mô hình, contract và scope guard | Log 180 passed, 3 warnings, 69,35 giây | Không bao quát mọi tải đồng thời hoặc môi trường bệnh viện |
| Syntax ES modules | Phát hiện lỗi parse các module frontend | `node --check` trong script xác minh | Không kiểm hành vi runtime chỉ bằng syntax |
| Logic thuần JavaScript | Tọa độ, letterbox, RLE, mask và transition | `workspace_v2_logic.mjs` và `frontend_review_logic.js` | Dùng dữ liệu kiểm thử có kiểm soát |
| Browser demo | Route, quyền giao diện, ký/duyệt/khóa minh họa | `workspace_v2_e2e.js` và `workspace_v2_features.js` | Không chứng minh server đã có workflow hai cấp |
| Browser API thật | Upload đủ L/R, IQA, predict, đo, undo và lưu review | `workspace_v2_live.js` và log runtime-live | Chạy trên server cô lập, không có bác sĩ thật |
| Hồi quy bất đồng bộ | Response cũ, hết phiên, draft, lease và JSON abort | Các script races/draft_conflict/lease_guards/api_abort | Lease đa thiết bị phía server chưa có |
| Khảo sát người dùng | Thời gian, khả năng sử dụng, mức sửa | Protocol và phiếu dự kiến trong phụ lục | Chưa có dữ liệu người tham gia |

Nguồn: log và mã kiểm thử trong dự án [19].

### 3.7.2. Môi trường kiểm thử và dữ liệu kiểm thử

Browser regression dùng server cô lập tại cổng 8027 thông qua `tests.serve_isolated_app`; database và uploads đặt ở thư mục artifact dành cho kiểm thử. Thiết kế này giúp những ca được tạo hoặc xóa khi chạy test không tác động cơ sở dữ liệu làm việc. Credentials kiểm thử được cấu hình theo môi trường server, không chép mật khẩu vào báo cáo hoặc hình. Demo dùng dữ liệu trong bộ nhớ và ảnh sơ đồ, còn test live tạo tệp ảnh kiểm thử để đi qua API thật. Hai kiểu dữ liệu được tách mục đích: demo kiểm trải nghiệm theo vai trò, live kiểm phần tích hợp đã được backend hỗ trợ.

Một kiểm thử có giá trị phải kiểm đầu ra liên quan đến rủi ro. Chẳng hạn test lưu review kiểm bản ghi trong DB và cờ nghiên cứu, thay vì chỉ nhìn toast. Test xóa ca kiểm việc commit DB trước unlink và đường dẫn nằm trong upload root, thay vì chỉ kiểm HTTP 200. Test mask kiểm tổng run RLE bằng 262.144 pixel và quy tắc đầu vào, thay vì tạo encoder và decoder giống nhau rồi chỉ xác nhận chúng tự khớp. Test tọa độ có ảnh không vuông và padding, vì trường hợp ảnh vuông ở mức zoom mặc định khó phát hiện sai ánh xạ.

Các lỗi môi trường và warning được giữ trong hồ sơ. Hai warning Albumentations liên quan ShiftScaleRotate và một warning scheduler phát sinh ở bài kiểm AMP overflow mô phỏng. Lượt chạy ghi pass nhưng warning không bị xóa khỏi kết quả. Browser kiểm syntax và runtime của SPA; dự án không có bước bundler nên không dùng một lệnh build không tồn tại để tạo cảm giác đã kiểm. Chưa có audit screen reader toàn diện, benchmark 60 fps trên máy phòng đọc ảnh hay kiểm tải đồng thời ở quy mô vận hành; các mục này thuộc kế hoạch tiếp theo.

### 3.7.3. Báo cáo kiểm thử các chức năng cốt lõi

*Bảng 3.2: Kiểm thử tiếp nhận hai ảnh và chặn ca thiếu bên*

| Nội dung | Kết quả hoặc mô tả |
|---|---|
| Mã kịch bản | TC-INTAKE-01 |
| Tiền điều kiện | Phiên bác sĩ kiểm thử hợp lệ; chưa có ca đang xử lý |
| Dữ liệu | Tệp raster kiểm thử hợp lệ cho hai slot L/R; không dùng ảnh bệnh nhân |
| Các bước | Chọn ảnh Trái; quan sát chưa chạy; chọn ảnh Phải; chờ create/upload/IQA/predict |
| Mong đợi | Thiếu một bên không chạy; đủ cặp tạo một ca, giữ ID hai ảnh và bên tương ứng |
| Bằng chứng thực tế | Log live ghi mandatory pair upload/IQA/predict thành công |
| Nguồn kiểm thử | `tests/workspace_v2_live.js` và `runtime-live-verification.log` |
| Giới hạn | Không xác nhận DICOM nhiều frame hoặc ẩn danh chữ in cứng |

*Bảng 3.3: Kiểm thử chuyển đổi tọa độ và bảo toàn letterbox*

| Nội dung | Kết quả hoặc mô tả |
|---|---|
| Mã kịch bản | TC-VIEW-01 |
| Tiền điều kiện | Có kích thước nguồn không vuông, rect viewport, zoom và pan đã xác định |
| Các bước | Ánh xạ source → model → screen và chiều ngược; đối chiếu padding/làm tròn backend |
| Mong đợi | Điểm quay lại đúng hệ nguồn trong sai số tính toán; không bỏ padding |
| Bằng chứng thực tế | Log logic ghi source/model/screen round trips và backend letterbox rounding thành công |
| Nguồn kiểm thử | `tests/workspace_v2_logic.mjs`; `frontend/app/coordinates.js` |
| Tác động nghiệp vụ | Nét sửa mask và vùng xem phải trùng vị trí người dùng chọn |
| Giới hạn | Chưa đo thao tác bằng bút trên thiết bị phòng đọc ảnh thật |

*Bảng 3.4: Kiểm thử lưu hai review và bảo toàn phạm vi nghiên cứu*

| Nội dung | Kết quả hoặc mô tả |
|---|---|
| Mã kịch bản | TC-REVIEW-01 |
| Tiền điều kiện | Ca đủ hai ảnh, mỗi ảnh có prediction; phiên có quyền lưu |
| Các bước | Chỉnh mask; undo/redo; lưu rà soát; chờ xác nhận; kiểm DB |
| Mong đợi | Hai review lưu đúng ảnh; không ghi đè prediction; không ký sơ bộ giả khi endpoint thiếu |
| Bằng chứng thực tế | Log live ghi persisted two reviews, no false preliminary signoff thành công |
| Nguồn kiểm thử | `tests/workspace_v2_live.js`; `tests/test_hitl_contract.py` |
| Bất biến | `is_official_ground_truth=False`; thiếu hiệu chuẩn không tạo mm |
| Giới hạn | Endpoint review từng ảnh chưa phải transaction ký hai cấp toàn ca |

*Bảng 3.5: Kiểm thử phân quyền xóa và tính nguyên tử khi tạo ca*

| Nội dung | Kết quả hoặc mô tả |
|---|---|
| Mã kịch bản | TC-DATA-01 |
| Dữ liệu | Token DOCTOR kiểm thử; Patient/Study trong DB cô lập |
| Các bước | Gọi DELETE bằng DOCTOR; gây lỗi chèn Study khi tạo Patient mới; kiểm DB sau rollback |
| Mong đợi | DELETE trả 403; lỗi Study không để lại Patient mới mồ côi |
| Nguồn kiểm thử | `test_delete_case_requires_admin_even_with_doctor_token`; `test_failed_study_insert_rolls_back_new_patient` |
| Bằng chứng tổng | Hai bài kiểm thuộc bộ Python ghi 180 passed |
| Kiểm liên quan | Xóa chỉ unlink tệp sở hữu sau commit; không xóa ngoài upload root |
| Giới hạn | Không suy thành soft-delete hoặc audit bất biến nếu mã hiện chưa có |

*Bảng 3.6: Kiểm thử draft, lease và request cũ*

| Nội dung | Kết quả hoặc mô tả |
|---|---|
| Mã kịch bản | TC-ASYNC-01 |
| Tình huống | Response L/R đảo thứ tự; session hết hạn khi lưu; draft cũ; mất lease |
| Mong đợi | Response cũ không ghi đè ảnh mới; thu hồi UI khi hết phiên; không lưu draft cũ; chặn mutation sau mất lease |
| Bằng chứng thực tế | Log races, draft conflict và lease guards đều ghi PASS |
| Nguồn kiểm thử | `workspace_v2_races.js`; `workspace_v2_draft_conflict.js`; `workspace_v2_lease_guards.js` |
| Kiểm thêm | Hủy confirmation giữ redo; Escape hủy dialog dùng lại; JSON abort không thành thành công rỗng |
| Giới hạn | Khóa local giữa tab không bảo vệ nhiều máy; server legacy vẫn cần version/lease |

Nguồn các bảng kiểm thử: mã và log kiểm thử được lưu trong dự án [19]. Các kết quả nêu ở đây thuộc lượt chạy ngày 11/10/2026.

### 3.7.4. Kết quả hồi quy và rủi ro còn lại

Bộ frontend ghi 11 script thành công, bao gồm hai script logic và chín script dùng trình duyệt. Các nhóm kiểm tra route, cặp ảnh, ký/duyệt demo, quyền QT, sáu ảnh trong phiếu, thiết bị desktop/tablet, API live, race L/R, hết phiên, bản nháp, lease và abort request. Log server cô lập mới dùng kiểm luồng live không có ASGI exception trong phần đã ghi. Những kết quả này chứng minh các hành vi được nêu trong test tại phiên bản kiểm tra; không chứng minh mọi đường đi của ứng dụng không có lỗi.

Một log server cũ từng ghi `StaleDataError` khi test xóa ca trong lúc review còn xử lý. Test cleanup được sửa để chờ xác nhận hai review và kiểm DB trước khi xóa. Kết quả runtime mới và log cũ không được trộn thành một trạng thái chung. Tuy vậy race review/delete giữa người dùng thật vẫn là rủi ro backend cần xử lý bằng boundary transaction, kiểm trạng thái hoặc lease/version và lỗi xung đột dễ hiểu. Việc làm test chờ đúng thứ tự tránh một cleanup sai; nó không tự giải quyết mọi concurrency trong sản phẩm.

Các endpoint mở rộng như OTP, phân quyền theo khoa, transition hai cấp, lease server, DICOM inspect nhiều frame, IQA override và heatmap chưa được kiểm với backend thật vì chưa có implementation tương ứng. UI báo thiếu khả năng hoặc lỗi retry. Tình trạng này phải được xem là phần tích hợp còn lại trong nghiệm thu, không hạ xuống một lỗi mỹ thuật. Những thao tác đã hiện thực trong demo có thể dùng trình diễn yêu cầu, nhưng điều kiện cho dữ liệu thật luôn phải xác nhận ở server.

### 3.7.5. Thiết kế đánh giá tính hữu dụng và thời gian thao tác

Đề cương đặt câu hỏi HITL có hỗ trợ giảm thời gian khoanh vùng và tăng tính thuận tiện hay không. Để trả lời, cần so sánh cùng nhiệm vụ trên những ca có mức khó tương đương giữa vẽ thủ công và rà soát gợi ý AI. Thời gian đo nên bắt đầu khi ảnh cần phân đoạn đã sẵn sàng cho người sử dụng, kết thúc khi mask cuối được lưu thành công. Thời gian upload hoặc chờ mô hình có thể ghi riêng và cộng vào một chỉ số end-to-end nếu protocol quy định. Không lấy độ trễ inference để thay cho tổng thời gian thao tác của bác sĩ.

Một protocol khả thi là chọn tập ca được phép dùng, chuẩn hóa hướng dẫn nhiệm vụ, tổ chức phiên làm quen trước, rồi dùng thứ tự tác vụ đối cân bằng để giảm ảnh hưởng học thuộc ca. Người tham gia là vai trò mục tiêu có hồ sơ đồng ý tham gia; cần ghi kinh nghiệm đọc ảnh theo nhóm, không ghi dữ liệu định danh vào bản công bố. Mỗi tác vụ thu thời gian, số thao tác sửa, action cuối, sự cố UI và nhận xét. Các mask sau sửa vẫn giữ nguồn reviewer và trạng thái nghiên cứu, không tự chuyển thành dữ liệu Test mới.

SUS có thể dùng như thang đo cảm nhận khả năng sử dụng theo kế hoạch đề cương. Ngưỡng 75/100 trong kế hoạch chỉ là kỳ vọng tham chiếu, không phải kết quả đạt được. Khi triển khai thang đo, cần sử dụng phiên bản câu hỏi và cách tính đã được xác minh, giữ các câu theo đúng chiều điểm; phụ lục của báo cáo này trước hết cung cấp phiếu tác vụ và câu hỏi phản hồi, không bịa một bộ phiếu đã được bác sĩ điền. Hiện chưa có số người tham gia, phân phối thời gian, điểm SUS hay kiểm định thống kê. Kết luận hiệu quả thực tiễn do đó vẫn để mở.

### 3.7.6. Bàn luận về mức hoàn thành

Phần thuật toán đã có model, cấu hình, lịch sử và phép đo trên bộ ảnh hiện hữu. Phần hệ thống đã có contract và kiểm thử cho các thao tác cốt lõi, đồng thời có bộ giao diện mở rộng giúp mô hình hóa nhiều vai trò. Phần người dùng chưa có khảo sát đủ hồ sơ. Tách ba mức này giúp đánh giá sản phẩm đúng với chứng cứ: có thể khẳng định prototype cho phép xem, sửa và lưu mask, nhưng chưa khẳng định giảm bao nhiêu phần trăm thời gian bác sĩ hay đạt mức an toàn vận hành bệnh viện. Báo cáo đầy đủ không cần mọi ô đều là một kết quả tích cực; cần mọi kết quả có nguồn và mọi thiếu hụt có điều kiện xử lý.

## 3.8. Cài đặt, đào tạo và triển khai bản mẫu

### 3.8.1. Môi trường phần mềm và lựa chọn hạ tầng

Hệ thống được chạy theo kiến trúc client–server trên môi trường local của dự án. Trình duyệt tải HTML/CSS/ES modules từ FastAPI; backend tiếp nhận REST request, thao tác SQLAlchemy/SQLite và gọi dịch vụ PyTorch. Frontend không có bước build React hoặc bundler. Vì dùng module, Worker và API cùng origin, không mở trực tiếp `index.html` bằng đường dẫn tệp. Cách triển khai tối thiểu là chạy Uvicorn ở địa chỉ localhost và mở URL server. Cấu hình này phù hợp kiểm tra và trình diễn học thuật, không được gọi là đã triển khai nội bộ bệnh viện [17], [18].

Run config của hai mô hình đối sánh ghi GPU NVIDIA GeForce RTX 3050 Laptop GPU, batch size 2, ngân sách 30 epoch. Đây là môi trường đã chạy thí nghiệm, không phải cấu hình tối thiểu đã đo để khuyến nghị mua máy. Một máy trạm chỉ hiển thị giao diện không cần GPU suy luận nếu API chạy ở máy khác. Ngược lại, máy chủ có model cần đủ bộ nhớ cho trọng số, tensor đầu vào và request đồng thời. Các cấu hình CPU fallback, nhiều worker và đồng thời cần đo riêng; nhân số worker mà không tính bộ nhớ model có thể nạp nhiều bản trọng số gây thiếu tài nguyên.

*Bảng 3.7: Môi trường và trạng thái xác minh*

| Thành phần | Cấu hình hoặc cách dùng | Trạng thái |
|---|---|---|
| Backend | Python, FastAPI, Uvicorn theo môi trường `.venv` của dự án | Có mã và log API thật |
| AI | PyTorch; Standard U-Net và U-Net++/ResNet34 | Có run config và checkpoint |
| Thí nghiệm huấn luyện | RTX 3050 Laptop GPU, batch 2, 30 epoch | Ghi trong cấu hình chạy |
| Database | SQLite qua SQLAlchemy | Prototype local, chưa kiểm tải bệnh viện |
| Frontend | HTML5/CSS3/JavaScript ES modules, Canvas 2D, Worker | Không có bước bundler |
| Browser regression | Playwright-core và Chrome trên Windows | Có log kiểm thử lưu |
| Xuất phiếu | Print CSS và hộp thoại trình duyệt | Không phải dịch vụ PDF lâm sàng server |
| Word khóa luận | Times New Roman 13, A4, ảnh nhúng và trường mục lục | Kiểm tra trong hồ sơ biên soạn |

Nguồn: run config, README frontend, mã backend và log [16]–[19].

### 3.8.2. Các bước cài đặt và khởi động

Người triển khai chuẩn bị repository, môi trường Python và dependencies theo hồ sơ cài đặt của dự án, sau đó chọn đúng model artifact. Không đổi tên một checkpoint bất kỳ thành tên model mong muốn; kiến trúc nạp và trạng thái tensor phải tương thích. SHA-256 checkpoint được lưu để đối chiếu. Cấu hình dữ liệu, upload root và database phải tách khỏi thư mục dùng chạy kiểm thử. Khi sao chép dự án sang máy mới, cần kiểm đường dẫn tương đối và quyền ghi, vì một absolute path còn trỏ máy phát triển có thể làm mất khả năng mở lại ảnh.

Các biến môi trường xác thực gồm `APP_JWT_SECRET`, `APP_ADMIN_PASSWORD` và `APP_DOCTOR_PASSWORD` theo cấu hình hiện có. Bí mật thật được thiết lập ngoài báo cáo và ngoài screenshot. Tài khoản theo role hiện tại là cơ chế prototype, chưa thay thế tài khoản cá nhân có password hash và quản lý đầy đủ. Không thể ghi danh tính chuyên môn có giá trị chỉ từ username mặc định. Nếu mở cho người dùng thật, tài khoản cá nhân, khóa/rate limit và quản lý phiên phải được triển khai phía server trước.

Lệnh khởi động local theo README frontend là `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`. Sau khi máy chủ sẵn sàng, truy cập `http://127.0.0.1:8000`. Kiểm `/api/health`, trạng thái model, khả năng truy cập static và cấu hình API trước khi tiếp nhận tệp. Chế độ demo được chọn rõ trên màn đăng nhập; nó không tạo hoặc xóa bản ghi server. Đăng nhập thật sử dụng cấu hình đúng môi trường và chỉ dùng dữ liệu đã được phép nghiên cứu.

Để kiểm tra regression, chạy `.venv\Scripts\python.exe -m pytest -q --tb=short` và script `scripts/verify_workspace_v2.ps1`. Browser test cần server cô lập ở 8027 theo hướng dẫn; không chạy cleanup đối với ca làm việc. Kết quả được lưu với ngày, phiên bản và phạm vi môi trường. Đối với hồ sơ mô hình, dùng manifest và run config đi kèm, không thay đường dẫn tập Test hoặc threshold sau khi đã lấy metric rồi giữ nguyên tiêu đề bảng cũ.

### 3.8.3. Khởi tạo dữ liệu, kiểm tra schema và sao lưu

`init_db()` tạo schema và có logic bổ sung cột tương thích SQLite cũ. Cột laterality và file_hash giúp quản lý cặp ảnh và chống trùng trong Study. Unique index đảm bảo application check không phải lớp duy nhất chống upload trùng. Những bản ghi legacy thiếu hash hoặc side cần được nhận diện trong kế hoạch chuyển đổi; không tự suy một bên từ tên tệp rồi coi là dữ liệu đã xác nhận. Quá trình migration có thể thay đổi DB, nên thao tác trên bản sao để kiểm before/after và lưu lại bản gốc trước lần cập nhật schema.

Sao lưu có ít nhất hai thành phần: database chứa metadata và tệp ảnh/mask liên quan. Chỉ có DB mà raw_path trỏ tệp không tồn tại sẽ không đủ mở lại ca. Một archive cần có manifest đường dẫn, thời điểm, phạm vi, kiểm hash và hướng dẫn phục hồi. Thử restore trên môi trường cô lập là bằng chứng quan trọng hơn việc thấy một file backup đã được tạo. Hiện chưa có hồ sơ kiểm restore đầy đủ trong báo cáo; do đó khả năng phục hồi vận hành chưa được chứng nhận. Dữ liệu backup cần kiểm quyền truy cập như dữ liệu chính.

Đối với model, backup trọng số phải đi cùng kiến trúc, phiên bản tiền xử lý, ngưỡng và hồ sơ đánh giá. Khi thay model đang nạp, prediction cũ không được cập nhật nguồn bằng checksum mới. Nếu rollback, hệ thống phải nhận diện phiên bản nào tạo prediction nào để không trộn hai loại kết quả trong một chỉ số. Registry trong demo mô hình hóa yêu cầu này, còn chính sách triển khai model thật cần kiểm API và transaction cấu hình. Tính tái lập ở cấp báo cáo dựa vào artifact, không dựa vào tên marketing của model.

### 3.8.4. Đào tạo sử dụng và kịch bản trình diễn

Đào tạo bản mẫu bắt đầu bằng phân biệt demo và live, PID giả danh và định danh thật, mask AI và mask rà soát. Người sử dụng được hướng dẫn tải cặp Trái/Phải, đọc trạng thái IQA, mở ảnh gốc, kiểm đường biên và chọn công cụ sửa. Một tác vụ thực hành nên yêu cầu người dùng sửa có chủ đích một vùng nhỏ rồi undo/reset để biết dữ liệu nào thay đổi. Sau đó giới thiệu hiệu chuẩn, đơn vị px/mm, tóm tắt hai bên và sự khác nhau giữa lưu review nghiên cứu với ký duyệt quy trình dự kiến.

Kịch bản BS gồm tiếp nhận hai ảnh, quan sát đủ hai bên, sửa khi cần, nhập notes và lưu. Kịch bản TK trong demo gồm mở hàng chờ, đối chiếu mask, Reject với lý do, sửa tạo phiên bản, duyệt và khóa. Kịch bản QT gồm xem metadata, người dùng, model, audit và cấu hình, không mở ảnh. Người hướng dẫn phải nói rõ màn nào đang dùng endpoint thật và màn nào mô hình hóa luồng chưa tích hợp. Không dùng một ca demo có đầy đủ badge để trình diễn như hồ sơ bệnh viện đã được duyệt.

Phần thực hành ngoại lệ gồm mất mạng, thử lại, thiếu một ảnh, AI lỗi, mask rỗng, hết phiên và draft cũ. Người dùng cần biết lưu nháp cục bộ không có nghĩa đã lưu server. Khi lỗi, không tải lại trang ngay nếu có thể giữ dữ liệu hợp lệ và thử đúng bước. Đối với ca chưa hiệu chuẩn, kết quả thực hành phải giữ px. Thông tin phản hồi đào tạo được ghi vào phiếu tác vụ, không tự tổng hợp thành một điểm SUS nếu chưa dùng thang đo đã kiểm chứng.

### 3.8.5. Giám sát, xử lý sự cố và kế hoạch mở rộng

Một lỗi vận hành cần được phân loại theo chặng: upload, IQA, suy luận, đo, review hay render. Thời gian từng chặng và mã tài nguyên giúp truy vết; log không ghi mật khẩu/token hoặc metadata định danh. Nếu upload thất bại nhưng Study đã có, retry dùng ID đang giữ; nếu suy luận lỗi, không tạo prediction giả để cho bước review đi tiếp. Nếu server đã lưu nhưng response bị mất, contract idempotency hoặc truy vấn trạng thái là cách giảm duplicate operation. Những yêu cầu đó phải được áp dụng vào API khi mở rộng, không vá bằng cách disable nút ở frontend.

Lộ trình mở rộng được sắp theo các phụ thuộc thực tế. Trước hết khóa provenance dữ liệu và nhãn, xác minh quyền dùng và mã bệnh nhân. Tiếp theo tạo cohort mới, chạy đối sánh mô hình có kiểm soát và khảo sát HITL với người dùng mục tiêu. Phần backend sau đó bổ sung ownership/khoa, tài khoản cá nhân, transition/version/lease, transaction hai ảnh và lịch sử bất biến. Cuối cùng mới xem xét tích hợp PACS/RIS, chuẩn DICOM vận hành và báo cáo được phê duyệt bởi cơ sở. Các module CDSS thử nghiệm không được mở thành kết luận chẩn đoán chỉ vì pipeline phân đoạn đã chạy.

### 3.8.6. Tiểu kết chương

Chương 3 chuyển bài toán đã xác định thành quy trình, yêu cầu, dữ liệu, thuật toán và giao diện có thể quan sát. Phần mô hình cung cấp bằng chứng định lượng theo checkpoint và split; phần phần mềm cung cấp các luồng upload, hiển thị, hiệu chỉnh và lưu review cùng kiểm thử. Bộ giao diện nhiều vai trò giúp làm rõ hướng mở rộng nghiệp vụ nhưng không che phần server còn thiếu. Kết quả có ý nghĩa của chương là một prototype nghiên cứu có khả năng truy vết, với mức hoàn thành và giới hạn được chỉ ra đến từng nhóm chức năng.
