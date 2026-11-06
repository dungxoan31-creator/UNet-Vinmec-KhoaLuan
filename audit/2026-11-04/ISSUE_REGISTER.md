# Complete issue register

This register preserves the findings as confirmed on 04/11/2026. `CONFIRMED` describes the baseline observation, not the current remediation state and not a claim that clinical harm occurred. Severity, remediation priority and evidence confidence are independent. Current dispositions and follow-up evidence are appended in the 05/11/2026 section below.

## AUD-001 — P0 — PID cục bộ trùng giữa hai cơ sở bị hợp nhất thành một bệnh nhân

| Field | Finding |
|---|---|
| Module | Identity |
| Screen Route | POST /api/cases |
| Component | Patient HMAC mapping |
| Category | BA / BE / Clinical |
| Severity | P0 |
| Remediation priority | Release blocker |
| Current Behavior | Cơ sở A và B cùng gửi PID 123456789: hai ca có cùng patient_id SYN-75A6A9D7F7E34ADD8F2671D32064EC6D. |
| Expected Behavior | PID thuộc namespace cơ sở, trừ khi có định danh toàn mạng đã được xác minh. |
| Reproduction Steps | Chạy probe.py rồi tenant-probe.py trong sandbox mới; tạo ca A và B với cùng chuỗi PID; so sánh patient_id. |
| Evidence | probe-results.json: create left case; tenant-results.json: same source PID at unrelated facility; [backend/services/patient_identity.py:28](../../backend/services/patient_identity.py#L28) |
| Impact | Liên kết nhầm bệnh nhân khi các cơ sở dùng mã cục bộ giống nhau. Probe không chứng minh bác sĩ đọc được ca cơ sở khác: GET đó trả 403. |
| Root Cause | get_or_create_patient chỉ nhận source_patient_id; HMAC/unique key không chứa facility_id. PatientModel là bảng chung. |
| Recommendation | Thiết kế namespace định danh và quy trình liên kết đã xác thực; đánh giá bản ghi đã hợp nhất trước khi chuyển đổi. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-002 — P1 — Quản trị viên cơ sở sửa được cấu hình toàn hệ thống

| Field | Finding |
|---|---|
| Module | Tenant administration |
| Screen Route | #admin/settings; PUT /api/admin/settings |
| Component | Global JSON settings |
| Category | BE / API / BA |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Scoped admin ghi AUDIT FACILITY A GLOBAL HEADER trả 200; global admin đọc thấy đúng giá trị đó. |
| Expected Behavior | Chỉ global admin sửa cấu hình toàn mạng hoặc settings được lưu theo facility_id. |
| Reproduction Steps | Dùng tài khoản audit-scoped-admin của probe; PUT settings; GET bằng global admin. |
| Evidence | tenant-results.json; [backend/app/routers/admin.py:1394](../../backend/app/routers/admin.py#L1394) |
| Impact | Một cơ sở thay đổi cấu hình của các cơ sở khác; cùng dạng thiết kế dùng cho danh mục khoa/phòng. |
| Root Cause | Router chỉ require_admin; handler không lấy actor/facility; _ADMIN_SETTINGS và admin_settings.json dùng chung. |
| Recommendation | Phân quyền global cho cấu hình chung và tenant-scope cho cấu hình cơ sở. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-003 — P1 — API sao lưu toàn database không giới hạn global admin

| Field | Finding |
|---|---|
| Module | Backup |
| Screen Route | POST /api/admin/backups/create |
| Component | Full database archive |
| Category | BE / API / Security |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Code cho mọi ADMIN gọi BackupService.create_backup(include_images=False), dịch vụ sao chép toàn SQLite bằng backup API. |
| Expected Behavior | Sao lưu toàn mạng chỉ dành cho global operator; quyền cơ sở chỉ xuất metadata được phép. |
| Reproduction Steps | Đọc router require_admin, trigger_backup và BackupService.create_backup; không bấm tạo backup trong audit. |
| Evidence | [backend/app/routers/admin.py:643](../../backend/app/routers/admin.py#L643); [backend/services/backup_service.py:78](../../backend/services/backup_service.py#L78) |
| Impact | Quản trị cơ sở có thể kích hoạt tạo bản sao dữ liệu toàn mạng. Không khẳng định có endpoint tải archive hoặc đã trích xuất dữ liệu. |
| Root Cause | Handler không kiểm tra is_global_admin/facility; sao chép database nguyên khối. |
| Recommendation | Giới hạn quyền, vị trí lưu, retention và kiểm thử restore theo engine. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Confirmed static authorization path; archive execution BLOCKED |

## AUD-004 — P1 — Thông báo đã tạo hồ sơ nhưng dữ liệu hồ sơ chỉ nằm ở trình duyệt

| Field | Finding |
|---|---|
| Module | Patient registration |
| Screen Route | #intake |
| Component | Create/edit patient |
| Category | FE / BA / Data |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Tạo Audit Synthetic Alpha báo thành công; context trình duyệt mới cùng tài khoản không thấy PID; không có request tạo patient. |
| Expected Behavior | Phân biệt rõ hồ sơ cục bộ và hồ sơ dùng chung; nếu phục vụ vận hành nhiều máy cần persistence phía server. |
| Reproduction Steps | Tạo patient trong intake; đăng nhập cùng user ở context mới; tìm PID đã tạo. |
| Evidence | browser-results.json: patient browser storage / same user fresh browser patient visibility; patient-created-upload.png; [frontend/app/intake.js:152](../../frontend/app/intake.js#L152) |
| Impact | Bác sĩ đổi máy hoặc nhân viên khác không tìm thấy hồ sơ; xóa dữ liệu trình duyệt làm mất danh bạ. |
| Root Cause | createDemoPatientStore lưu localStorage theo user id, không có API CRUD demographic. |
| Recommendation | Làm rõ phạm vi lưu và xây hợp đồng persistence phù hợp nếu triển khai. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-005 — P1 — Bốn tên và PID mẫu hiện ra khi synthetic_demo_mode=false

| Field | Finding |
|---|---|
| Module | Intake defaults |
| Screen Route | #intake |
| Component | Default patient list |
| Category | FE / BA / Clinical |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Sandbox sạch ngoài synthetic mode vẫn có Nguyễn Minh Anh/100000001 và ba hồ sơ khác, chọn được như hồ sơ thường. |
| Expected Behavior | Không tạo hồ sơ mẫu trong chế độ ngoài demo; mẫu phải gắn nhãn tổng hợp và bị giới hạn rõ. |
| Reproduction Steps | Mở intake với localStorage sạch và synthetic_demo_mode=false. |
| Evidence | intake-seeds.png; browser-results.json; [frontend/app/intake.js:22](../../frontend/app/intake.js#L22) |
| Impact | Có thể chọn hồ sơ giả và tạo ca dưới PID mẫu trong thao tác hàng ngày. |
| Root Cause | Seeds hardcoded dùng bất kể mode; chỉ additions 300 hồ sơ được ràng buộc synthetic mode. |
| Recommendation | Giới hạn seed vào sandbox tổng hợp; không tự tạo patient mẫu ngoài demo. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-006 — P1 — Đổi mật khẩu thành công làm phiên hiện tại hết hạn ở request tiếp theo

| Field | Finding |
|---|---|
| Module | Account |
| Screen Route | #profile |
| Component | Change password |
| Category | FE / API |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | POST change-password trả 200; chuyển cases dẫn đến #expired. |
| Expected Behavior | Phiên hiện tại nhận token mới khi đổi mật khẩu; các phiên cũ bị thu hồi theo chính sách. |
| Reproduction Steps | Đăng nhập doctor; đổi password qua profile; chuyển Danh sách ca. |
| Evidence | deep-browser-results.json: password change response + responses 401; after-password-change.png; [frontend/app/personal.js:65](../../frontend/app/personal.js#L65) |
| Impact | Bác sĩ bị gián đoạn không giải thích sau thông báo đổi mật khẩu thành công. |
| Root Cause | Backend tăng token_version và trả TokenResponse; personal.js không nhận/áp dụng access_token trả về. |
| Recommendation | Đồng bộ session bằng token trả về và kiểm thử luồng tiếp tục công việc. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-007 — P1 — Khởi động lại ghi đè mật khẩu bootstrap đã đổi trong UI

| Field | Finding |
|---|---|
| Module | Bootstrap |
| Screen Route | Application startup |
| Component | init_db bootstrap credentials |
| Category | BE / Security |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Sau đổi mật khẩu, restart cùng DB và env bootstrap cũ: password mới không đăng nhập được; password env cũ đăng nhập được. |
| Expected Behavior | Bootstrap không ghi đè mật khẩu user đã được thiết lập, trừ thao tác reset có chủ đích/audit. |
| Reproduction Steps | Đổi mật khẩu doctor; restart server với APP_DOCTOR_PASSWORD cũ; thử hai password. |
| Evidence | deep-browser-results.json / after-password-change.png; final-browser.cjs retry history documented in REPORT.md; [backend/db/database.py:900](../../backend/db/database.py#L900) |
| Impact | Mật khẩu do người dùng đổi bị hoàn nguyên khi deploy/restart; độ bền thay đổi bảo mật không đúng kỳ vọng. |
| Root Cause | init_db gán lại hash cho mọi user bootstrap đang tồn tại mỗi khi env password có giá trị. |
| Recommendation | Bootstrap chỉ tạo mới; reset mật khẩu phải tường minh và có audit. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Source + isolated restart observation; failed first rerun is harness evidence |

## AUD-008 — P1 — Hai phiên danh bạ có thể ghi đè mất cập nhật của nhau

| Field | Finding |
|---|---|
| Module | Patient store |
| Screen Route | #intake |
| Component | Concurrent cached store |
| Category | FE / Data |
| Severity | P1 |
| Remediation priority | Release blocker |
| Current Behavior | Hai store dùng cùng storage: store A thêm Alpha; store B đã đọc cache thêm Beta; storage cuối mất Alpha. |
| Expected Behavior | Thêm/sửa không làm mất cập nhật hợp lệ từ phiên khác. |
| Reproduction Steps | node audit/2026-11-04/store-probe.mjs; xem firstUpdateLost=true. |
| Evidence | store-probe-results.json; [frontend/app/intake-session.js:82](../../frontend/app/intake-session.js#L82) |
| Impact | Mất hoặc hoàn nguyên hồ sơ khi cùng tài khoản dùng nhiều tab. |
| Root Cause | Cache Map luôn được ưu tiên; không refresh storage/merge/version hoặc lắng nghe storage event trước save. |
| Recommendation | Dùng nguồn dữ liệu có version/concurrency và cơ chế đồng bộ. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Executable production store function + source |

## AUD-009 — P2 — Danh sách đã xóa hết tự khôi phục seed khi mở lại

| Field | Finding |
|---|---|
| Module | Patient store |
| Screen Route | #intake |
| Component | Empty list hydration |
| Category | FE / Data |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | save(key,[]) rồi tạo store mới/read(key) trả seed thay vì []. |
| Expected Behavior | Danh sách rỗng hợp lệ phải giữ nguyên. |
| Reproduction Steps | Chạy store-probe.mjs; xem emptyStoreAfterReopen. |
| Evidence | store-probe-results.json; [frontend/app/intake-session.js:85](../../frontend/app/intake-session.js#L85) |
| Impact | Hồ sơ đã gỡ lại xuất hiện, khiến người dùng không tin thao tác xóa. |
| Root Cause | Điều kiện rows.length loại bỏ mảng rỗng và gọi save(key,seeds). |
| Recommendation | Phân biệt missing/invalid storage với empty list hợp lệ. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Executable production store function + source |

## AUD-010 — P2 — Dữ liệu định danh lưu dài hạn trên thiết bị, không được xóa khi đăng xuất

| Field | Finding |
|---|---|
| Module | Privacy |
| Screen Route | #intake; logout |
| Component | Local demographic retention |
| Category | FE / Security / BA |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Danh bạ localStorage chứa name, phone, birth_year, hometown và national_id nếu nhập; logout chỉ gỡ token/expiry trong sessionStorage. |
| Expected Behavior | Quy định rõ mục đích, thời hạn, bảo vệ và cơ chế xóa dữ liệu định danh trên thiết bị dùng chung. |
| Reproduction Steps | Tạo patient tổng hợp; xem storage JSON; đọc logout cleanup. |
| Evidence | browser-results.json: patient browser storage; [frontend/app/intake-session.js:74](../../frontend/app/intake-session.js#L74); [frontend/app/auth.js:45](../../frontend/app/auth.js#L45) |
| Impact | Tăng rủi ro dữ liệu lưu lại trên máy phòng khám. Không thực hiện khai thác XSS hoặc đọc dữ liệu thật. |
| Root Cause | Persistent browser store nằm ngoài backend authorization/retention; user id trong key không phải kiểm soát truy cập ở mức OS. |
| Recommendation | Chọn chính sách tối thiểu hóa dữ liệu và quản lý lưu cục bộ phù hợp. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime storage + static logout; privacy impact is risk assessment |

## AUD-011 — P2 — Bắt buộc nhập thông tin không được truyền vào luồng khảo sát

| Field | Finding |
|---|---|
| Module | Registration |
| Screen Route | #intake patient modal |
| Component | Required demographic fields |
| Category | BA / PO / UX |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Phone, hometown, gender và birth year là required; request tạo ca chỉ truyền PID/date/reason/sides, không truyền tuổi đã tính. |
| Expected Behavior | Chỉ bắt buộc dữ liệu có mục đích nghiệp vụ; giá trị đã xác thực cần có đường sử dụng/persistence rõ. |
| Reproduction Steps | Mở Tạo bệnh nhân, kiểm tra required; đối chiếu create patient với run()/startBilateral payload. |
| Evidence | patient-create.png; field-inventory.json; [frontend/app/intake.js:106](../../frontend/app/intake.js#L106); [frontend/app/upload.js:186](../../frontend/app/upload.js#L186) |
| Impact | Nhập thêm nhiều trường nhưng bước nhận định vẫn thiếu dữ liệu tuổi; lợi ích vận hành chưa được chứng minh. |
| Root Cause | Form danh bạ local tách khỏi hợp đồng case và patient context; tuổi không đi vào API tạo ca. |
| Recommendation | Xác lập purpose từng field; tái sử dụng tuổi đã xác minh hoặc bỏ bắt buộc trường không phục vụ luồng. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Rendered required attributes + source; business necessity judgment |

## AUD-012 — P2 — Cùng nhãn PID nhưng intake và hồ sơ server hiển thị hai mã khác nhau

| Field | Finding |
|---|---|
| Module | Identity display |
| Screen Route | #intake → #case/:id → #report/:id |
| Component | PID labels |
| Category | UX / BA |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Intake hiển thị PID 9 chữ số; case/report hiển thị SYN-...; tên patient đã chọn không đi cùng bản ghi server. |
| Expected Behavior | Phân biệt PID nguồn và mã nghiên cứu, hỗ trợ xác minh liên kết mà không lộ định danh không cần thiết. |
| Reproduction Steps | Chọn/create patient; tạo case; mở case và report; so sánh mã. |
| Evidence | patient-created-upload.png; case-detail.png; report-reviewed.png; probe-results.json. |
| Impact | Người dùng khó đối chiếu ca với hồ sơ đã chọn và tưởng mã bị thay đổi. |
| Root Cause | Server sinh pseudonym, UI gọi cả nguồn lẫn pseudonym bằng PID; label không thể hiện sự chuyển đổi. |
| Recommendation | Dùng thuật ngữ nhất quán, chỉ dẫn liên kết theo quyền. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-013 — P2 — Thanh Phân tích ảnh AI che nội dung chọn ảnh trên màn thấp

| Field | Finding |
|---|---|
| Module | Intake layout |
| Screen Route | #intake upload |
| Component | Sticky action bar |
| Category | UX / FE |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Ở 1366×768, action bar nằm giữa vùng dropzone; ở 1440×900 che vùng control bên dưới. |
| Expected Behavior | Thanh hành động có vùng riêng, không phủ thao tác đang cần ở bước upload. |
| Reproduction Steps | Chọn patient, chưa upload; xem ở 1366×768 và 1440×900. |
| Evidence | upload-1366.png; upload-1440.png; [frontend/css/workspace.css:2763](../../frontend/css/workspace.css#L2763) |
| Impact | Giảm diện tích xem và thêm cuộn tìm control trong bước đầu khảo sát. |
| Root Cause | Sticky bottom:40px ở cuối nội dung dài có thể dịch ngược lên phủ sibling khi viewport thấp. |
| Recommendation | Dành không gian layout cho action bar và kiểm tra overlap ở viewport thấp. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Screenshot + CSS; no claim that scrolling cannot recover controls |

## AUD-014 — P2 — Trường Ngày giờ khảo sát bị bó hẹp, không đọc được giá trị

| Field | Finding |
|---|---|
| Module | Intake responsive |
| Screen Route | #intake upload at 390px |
| Component | datetime-local |
| Category | UX / FE |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Ở 390px, hai field PID/date vẫn cùng hàng; datetime chỉ hiện một phần ngắn cạnh nút Hiện tại. |
| Expected Behavior | Đọc/kiểm tra được toàn bộ ngày giờ trước tạo ca. |
| Reproduction Steps | Mở upload ở 390×844. |
| Evidence | upload-390.png; browser-results.json controls boxes; [frontend/app/intake.js:253](../../frontend/app/intake.js#L253) |
| Impact | Khó phát hiện sai ngày/giờ khi xác nhận metadata. |
| Root Cause | Grid hai cột và flex datetime/button không đủ chiều rộng nội dung. |
| Recommendation | Cho metadata xuống hàng ở chiều rộng nhỏ, giữ input date đủ rộng. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-015 — P2 — Tên bệnh nhân xuống dòng gần từng ký tự trên mobile

| Field | Finding |
|---|---|
| Module | Intake responsive |
| Screen Route | #intake at 390px |
| Component | Patient table name column |
| Category | UX / FE |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Danh sách 390px ép cột tên hẹp thành chuỗi dọc trong khi các nút thao tác chiếm ngang. |
| Expected Behavior | Tên patient vẫn đọc được, bảng cuộn ngang có chủ đích hoặc dùng cấu trúc phù hợp. |
| Reproduction Steps | Mở intake với danh sách seed tại 390×844. |
| Evidence | intake-390.png; [frontend/app/intake.js:58](../../frontend/app/intake.js#L58) |
| Impact | Khó chọn đúng hồ sơ khi duyệt nhanh. |
| Root Cause | Bảng nhiều cột/action không có ràng buộc chiều rộng tối thiểu đủ cho cột tên trong layout mobile. |
| Recommendation | Bảo vệ chiều rộng cột định danh hoặc đổi presentation theo breakpoint. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Screenshot; specific CSS contributor requires further isolation |

## AUD-016 — P2 — Phiếu bỏ mất tình trạng bên đối diện đã ghi nhận

| Field | Finding |
|---|---|
| Module | Report |
| Screen Route | #report/:id |
| Component | Missing ovary status |
| Category | Clinical / BA / FE |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Ca LEFT có contralateral_status=NOT_VISUALIZED; report chỉ ghi Chưa có ảnh khảo sát bên này. |
| Expected Behavior | Phân biệt không thấy, đã cắt bỏ và chưa tải ảnh; dùng đúng dữ liệu đã lưu. |
| Reproduction Steps | Tạo ca chỉ trái với NOT_VISUALIZED; review rồi xem/in report. |
| Evidence | probe-results.json: create left case; actual-print-text.json; [frontend/app/report-preview.js:381](../../frontend/app/report-preview.js#L381) |
| Impact | Người đọc downstream không biết bên đối diện đã khảo sát không thấy hay bị bỏ sót. |
| Root Cause | Report renderer nhận danh sách images theo bên, không đưa contralateral_status vào overview. |
| Recommendation | Hiển thị trạng thái thiếu bên từ snapshot đã lưu, theo ngữ nghĩa rõ ràng. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-017 — P2 — Tên đơn vị trên phiếu được lưu nhưng không được renderer sử dụng

| Field | Finding |
|---|---|
| Module | Admin/report integration |
| Screen Route | #admin/settings → #report/:id |
| Component | report_header |
| Category | FE / BE / API |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | PUT report_header thành công; source chỉ đọc field ở admin settings; report vẫn có tiêu đề cố định KẾT QUẢ KHẢO SÁT. |
| Expected Behavior | Field mang tên trên phiếu phải được áp dụng nhất quán hoặc nêu rõ chưa tích hợp. |
| Reproduction Steps | Đổi report_header trong tenant probe; mở actual-print.pdf; tìm header tùy chỉnh. |
| Evidence | tenant-results.json; actual-print-text.json; [frontend/app/admin.js:68](../../frontend/app/admin.js#L68); [frontend/app/report-preview.js:469](../../frontend/app/report-preview.js#L469) |
| Impact | Người quản trị tin đã cấu hình đơn vị nhưng phiếu không phản ánh thay đổi. |
| Root Cause | Settings persistence không nối vào report rendering contract. |
| Recommendation | Nối contract theo facility/tenant đã xác minh, hoặc bỏ field sai kỳ vọng. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-018 — P2 — Trang đầu ưu tiên provenance kỹ thuật, ghi chú bác sĩ ở trang sau

| Field | Finding |
|---|---|
| Module | Report composition |
| Screen Route | #report/:id / print |
| Component | First-page hierarchy |
| Category | UX / Clinical |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Một ảnh tạo hai trang: trang 1 có Model, SHA-256, UUID/revision và đoạn giải thích; O-RADS, mô tả, nhận định ở trang 2. |
| Expected Behavior | Trang tổng hợp hỗ trợ đọc nhanh kết quả do bác sĩ ghi nhận; provenance vẫn truy xuất được. |
| Reproduction Steps | Mở actual-print.pdf trang 1 và 2. |
| Evidence | actual-print.pdf; actual-print-text.json; report-reviewed.png. |
| Impact | Người xem phải chuyển trang để thấy phần quan trọng; tăng giấy và tải nhận thức. Đây là đánh giá UX, không phải lỗi số liệu. |
| Root Cause | renderReportDocument chia overview/technical info vào trang đầu, nội dung từng ảnh vào evidence page. |
| Recommendation | Ưu tiên nội dung bác sĩ trên phần tổng hợp, giữ cảnh báo RUO bắt buộc và provenance ở vị trí phù hợp. Chưa triển khai. |
| Confidence | Medium |
| Status | CONFIRMED |
| Evidence basis | Actual printed artifact + explicit UX judgment |

## AUD-019 — P2 — Không có quan sát nhưng dashboard hiển thị 0%, 0 điểm, 0s

| Field | Finding |
|---|---|
| Module | Operational analytics |
| Screen Route | #admin/reports |
| Component | Missing metric defaults |
| Category | BA / QC / FE |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Khi chưa có prediction/review, cards hiện consensus 0%, IQA 0, thời gian 0s. |
| Expected Behavior | Không có dữ liệu khác với kết quả đo bằng 0; hiển thị N/A và mẫu số. |
| Reproduction Steps | Mở admin reports trên DB tổng hợp chỉ có ca chưa phân tích. |
| Evidence | admin-reports.png; [backend/app/routers/admin.py:315](../../backend/app/routers/admin.py#L315); [backend/app/routers/admin.py:345](../../backend/app/routers/admin.py#L345) |
| Impact | Người quản lý có thể hiểu nhầm chất lượng AI bằng 0 hoặc rà soát tức thời. |
| Root Cause | Aggregate None và denominator zero được thay bằng 0.0; FE render như giá trị đo. |
| Recommendation | Giữ null/no-observation và hiển thị số mẫu/định nghĩa metric. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-020 — P2 — Mốc O-RADS không nhất quán giữa viewer, rule engine và analytics

| Field | Finding |
|---|---|
| Module | Clinical terminology |
| Screen Route | #viewer; #admin/reports |
| Component | O-RADS labels |
| Category | Clinical / UX / Content |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Viewer label nang noãn <30 mm nhưng phần reference/rule dùng ≤30 mm; admin dùng 1–9% và 10–49% trong khi viewer dùng 1–<10% và 10–<50%. |
| Expected Behavior | Thuật ngữ và khoảng liên tục nhất quán theo nguồn ACR được phê duyệt; không suy ra sinh lý chỉ từ kích thước. |
| Reproduction Steps | So sánh option O-RADS 1/3/4 với labels admin và PHYSIOLOGIC_FOLLICLE_POLICY. |
| Evidence | [frontend/app/viewer.js:42](../../frontend/app/viewer.js#L42); [frontend/app/admin-reports.js:15](../../frontend/app/admin-reports.js#L15); clinical-sources.md. |
| Impact | Gây mâu thuẫn tại đúng ngưỡng 30 mm và khi diễn giải nguy cơ giữa các màn hình. |
| Root Cause | Label sao chép riêng ở các module và không dùng một bộ thuật ngữ chuẩn. |
| Recommendation | Dùng bộ lexicon thống nhất, được chuyên gia xác nhận, bao gồm điều kiện áp dụng. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Rendered text + code + verified primary ACR source |

## AUD-021 — P2 — Hàng biểu đồ có click drilldown nhưng không có bàn phím/semantic control

| Field | Finding |
|---|---|
| Module | Accessibility |
| Screen Route | #admin/reports |
| Component | Chart drilldown rows |
| Category | FE / A11y |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | chart-drilldown-row là div cursor:pointer/data-orads; handler onclick; không có tabindex/role/key handler cho hàng đó. |
| Expected Behavior | Mọi drilldown tương tác phải truy cập và kích hoạt được bằng bàn phím. |
| Reproduction Steps | Đọc markup/hook chart-drilldown-row, thử Tab tới hàng category; runtime keyboard activation chưa chạy. |
| Evidence | [frontend/app/admin-reports.js:409](../../frontend/app/admin-reports.js#L409); admin-reports.png. |
| Impact | Người dùng bàn phím không dùng được bộ lọc từ biểu đồ theo cách tương đương. |
| Root Cause | Dùng div click thay vì button/link với tương tác keyboard native. |
| Recommendation | Dùng control semantic và focus rõ. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Confirmed markup/handler inspection; runtime keyboard drilldown NOT TESTED |

## AUD-022 — P3 — Ca chỉ có ảnh trái vẫn báo lưu hai bên thành công

| Field | Finding |
|---|---|
| Module | Save feedback |
| Screen Route | #viewer/:id |
| Component | Success toast |
| Category | UX / Content |
| Severity | P3 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Ca LEFT/NOT_VISUALIZED có một image; toast Đã lưu rà soát của hai bên thành công. |
| Expected Behavior | Thông báo đúng số ảnh/bên đã lưu, không xác nhận phần không có ảnh. |
| Reproduction Steps | Lưu review một ảnh trái. |
| Evidence | viewer-after-save.png; [frontend/app/review.js:259](../../frontend/app/review.js#L259) |
| Impact | Có thể hiểu nhầm bên phải đã được rà soát; report vẫn chỉ có một ảnh. |
| Root Cause | Success toast hardcoded hai bên cho mọi case. |
| Recommendation | Sinh thông báo từ phạm vi đã lưu. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-023 — P3 — Lỗi mạng lộ chuỗi Failed to fetch tiếng Anh

| Field | Finding |
|---|---|
| Module | Network errors |
| Screen Route | #viewer/:id; #admin/system |
| Component | Error toast/text |
| Category | UX / Content |
| Severity | P3 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Giả lập connectionreset khi save: draft/status xử lý đúng, toast hiện Failed to fetch. |
| Expected Behavior | Thông báo ngắn gọn tiếng Việt và hành động phục hồi cụ thể. |
| Reproduction Steps | Abort /api/reviews/batch trong Playwright rồi lưu note. |
| Evidence | viewer-network-save-failure.png; [frontend/app/api.js:34](../../frontend/app/api.js#L34) |
| Impact | Người dùng không hiểu nguyên nhân; không có bằng chứng false-success, vì save status báo lỗi đúng. |
| Root Cause | Fetch TypeError không chuẩn hóa, được truyền vào toast(e.message). |
| Recommendation | Chuẩn hóa network error theo ngữ cảnh và giữ draft. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## AUD-024 — P2 — Loss của checkpoint đang phục vụ khác core scope Dice+BCE

| Field | Finding |
|---|---|
| Module | Training protocol |
| Screen Route | evaluation/selected_model.json |
| Component | Selected model loss specification |
| Category | AI / Governance |
| Severity | P2 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | Selected manifest khai báo AdvancedHybridLoss(0.5 FocalTversky + 0.3 SoftDice + 0.2 BCE); training baseline khác dùng 0.5 BCE +0.5 Dice. |
| Expected Behavior | Phương pháp checkpoint phục vụ phải khớp phạm vi đã duyệt hoặc có quyết định thay đổi và tài liệu truy vết. |
| Reproduction Steps | Đọc selected_model.json loss_function và core scope AGENTS.md. |
| Evidence | [evaluation/selected_model.json:11](../../evaluation/selected_model.json#L11); [ai_training/train_unetplusplus_resnet34.py:172](../../ai_training/train_unetplusplus_resnet34.py#L172) |
| Impact | Sai lệch phương pháp khóa luận/provenance; không phải bằng chứng model kém chính xác hay lỗi inference. |
| Root Cause | Lựa chọn checkpoint boosted không đồng bộ mô tả phương pháp core scope. Chưa tái huấn luyện hoặc đối chứng loss. |
| Recommendation | Đối soát phê duyệt phương pháp, experiment lineage và mô tả mô hình phục vụ. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Manifest/source discrepancy; checkpoint training history only partially verified |

## AUD-025 — P3 — PID giả danh bị tách ba dòng ở phần định danh phiếu

| Field | Finding |
|---|---|
| Module | Report typography |
| Screen Route | #report/:id / print |
| Component | Patient ID block |
| Category | UX / Content |
| Severity | P3 |
| Remediation priority | Next usability/quality cycle |
| Current Behavior | SYN- và chuỗi hash dài xuống nhiều dòng, chữ cuối tách riêng trong bản in trang 1. |
| Expected Behavior | Mã định danh đọc/đối chiếu được, có trình bày phù hợp chuỗi dài. |
| Reproduction Steps | Mở actual-print.pdf trang 1. |
| Evidence | actual-print-text.json; actual-print-page-1.png; report-reviewed.png. |
| Impact | Giảm khả năng đối chiếu nhanh mã hồ sơ; mức ảnh hưởng thấp vì mã vẫn đầy đủ. |
| Root Cause | Khối PID dùng cột hẹp trong hàng ba cột; wrap chuỗi không phù hợp. |
| Recommendation | Điều chỉnh bố cục định danh không cắt vụn chuỗi. Chưa triển khai. |
| Confidence | High |
| Status | CONFIRMED |
| Evidence basis | Runtime + source |

## Remediation disposition — 05/11/2026

The original finding rows above remain unchanged as baseline evidence. `CONFIRMED` describes the 04/11 observation; the current disposition is below. The `Remediation_Status` columns in `issues.csv` are the 04/11 snapshot; this follow-up table supersedes AUD-013, AUD-018 and AUD-024 as of 05/11/2026.

| ID | Current disposition | Evidence | Remaining limit |
|---|---|---|---|
| AUD-001 | VERIFIED | `tests/test_patient_identity.py`; `tests/test_facility_isolation_p0.py` | Legacy multi-facility identity records stop startup for manual reconciliation. |
| AUD-002 | VERIFIED | `tests/test_tenant_admin_hardening.py` | Role/facility contract tests; no production tenant data used. |
| AUD-003 | VERIFIED | `tests/test_backup_service_sandbox.py`; `tests/test_tenant_admin_hardening.py` | Restore checked only for synthetic archive in `tmp_path`; product has no restore endpoint. |
| AUD-004 | VERIFIED | `tests/test_patient_directory_api.py`; `tests/test_patient_crud_e2e.mjs` | Synthetic facility records and disposable SQLite only. |
| AUD-005 | VERIFIED | `tests/test_patient_store_crud.mjs`; `tests/test_patient_crud_e2e.mjs` | Non-demo state tested in isolated browser. |
| AUD-006 | VERIFIED | `tests/password_change_session_e2e.js` | Isolated auth/session flow. |
| AUD-007 | VERIFIED | `tests/test_database_startup_safety.py` | Temporary SQLite restart test. |
| AUD-008 | VERIFIED | `tests/test_case_creation_concurrency.py`; `tests/test_patient_directory_api.py` | Synthetic concurrent writers only. |
| AUD-009 | VERIFIED | `tests/test_patient_store_crud.mjs` | Empty directory remains empty in tested browser state. |
| AUD-010 | VERIFIED | `tests/test_intake_session.mjs`; `tests/test_patient_crud_e2e.mjs` | Browser storage test; unrelated user preferences remain. |
| AUD-011 | VERIFIED | `tests/test_patient_directory_api.py`; `tests/test_patient_id_optional_r2.py` | No clinical validation of entered age. |
| AUD-012 | VERIFIED | `tests/test_frontend_intake_patient_id.mjs`; report tests | Labels/contract tested; no cross-facility source ID linkage. |
| AUD-013 | VERIFIED | `artifacts/qa-next-steps-2026-11-05-r2/safety-results.json`; `intake-1366.png` | CTA natural bounds y=585.8–629.8 at 1366×768, scrollTop=0; no horizontal overflow. At 768×768 it still needs scrolling. |
| AUD-014 | VERIFIED | `artifacts/qa-clinical-fixed/mobile-intake-2026-11-05/results.json`; `upload-390x844.png` | One Chromium viewport; browser/device matrix not tested. |
| AUD-015 | VERIFIED | `artifacts/qa-clinical-fixed/mobile-intake-2026-11-05/results.json`; `patient-list-390x844.png` | Synthetic directory row at 390×844. |
| AUD-016 | VERIFIED | `tests/test_fe_02_report_preview.mjs`; `tests/test_v21_report_generator.py` | Synthetic report contract. |
| AUD-017 | VERIFIED | `tests/test_fe_02_report_preview.mjs`; facility settings tests | Tenant-specific synthetic header only. |
| AUD-018 | VERIFIED | `artifacts/qa-next-steps-2026-11-05-r2/report-followup.pdf`; extracted PDF text; report E2E | Both laterality-specific doctor notes are on page 1; image evidence pages 2–3; provenance page 4. Synthetic-only artifact. |
| AUD-019 | VERIFIED | `tests/test_admin_reports.py`; `tests/test_admin_analytics_ui.mjs` | UI/API test coverage; no operational analytics dataset. |
| AUD-020 | PARTIAL | `tests/test_cdss_boundary_30mm_r8.py`; `tests/test_frontend_clinical_copy.py`; [official ACR v2022 table](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf) | Project `<30 mm` policy is internally consistent; ACR describes follicle `≤3 cm`; requires independent clinical decision. |
| AUD-021 | VERIFIED | `tests/admin_reports_keyboard_e2e.js`; `tests/test_admin_analytics_ui.mjs` | Isolated keyboard/browser checks. |
| AUD-022 | VERIFIED | `tests/test_review_save.mjs` | Save acknowledgement only; no live clinical save. |
| AUD-023 | VERIFIED | `tests/test_api_session.mjs`; `tests/test_review_save.mjs` | Synthetic transport failure. |
| AUD-024 | VERIFIED — research provenance only | `tests/test_model_selection.py`; `clinical_roundtrip_e2e.js`; `doctor_workflow_e2e.js` | ComboLoss checkpoint hash verified and loaded in isolated synthetic E2E. Candidate-only; independent validation and clinical readiness remain blocked. |
| AUD-025 | VERIFIED | `tests/test_fe_02_report_preview.mjs` | Current PDF fixture uses a short synthetic pseudonym; long-hash print behavior is covered by frontend contract tests. |

### Supplementary findings from remediation verification

These three items were not part of the 25-issue baseline. They were reproduced and fixed in the current working tree.

| ID | Severity | Finding | Disposition / evidence |
|---|---|---|---|
| RM-001 | P2 | Model-readiness check masked v1 input-size and case-lease validation errors. | VERIFIED; readiness gate follows source/suitability checks. `tests/test_v1_segment_limits.py`, `tests/test_case_leases.py`, `tests/test_model_registry_fail_closed.py`. |
| RM-002 | P2 | Migration order omitted `patient_directory` before dependent tables. | VERIFIED in synthetic migration contract; `tests/test_sqlite_to_postgres_migration.py`. Native PostgreSQL remains BLOCKED. |
| RM-003 | P2 | Mobile directory stylesheet targeted stale four-column markup and mislabeled name/year/actions. | VERIFIED; `artifacts/qa-clinical-fixed/mobile-intake-probe.cjs`, `mobile-intake-2026-11-05/results.json`, 390×844 screenshots. |

See [REMEDIATION_REPORT.md](REMEDIATION_REPORT.md) for the executive disposition, test results, coverage matrix, clinical limitations and remaining actions.
