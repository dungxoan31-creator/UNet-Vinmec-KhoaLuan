import json,csv,re,hashlib,subprocess
from pathlib import Path
from collections import Counter
O=Path(__file__).parent; R=Path.cwd(); issues=[]
def source(file,needle):
 lines=(R/file).read_text(encoding='utf-8-sig').splitlines();n=next((i+1 for i,l in enumerate(lines) if needle in l),1)
 return f'[{file}:{n}](../../{file}#L{n})'
def add(id,sev,module,route,component,category,title,current,expected,steps,evidence,cause,impact,recommendation,confidence='High',status='CONFIRMED',basis='Runtime + source'):
 issues.append(dict(Issue_ID=f'AUD-{id:03}',Module=module,Screen_Route=route,Component=component,Category=category,Severity=sev,Remediation_priority='Release blocker' if sev in ('P0','P1') else 'Next usability/quality cycle',Description=title,Current_Behavior=current,Expected_Behavior=expected,Reproduction_Steps=steps,Evidence=evidence,Impact=impact,Root_Cause=cause,Recommendation=recommendation,Confidence=confidence,Status=status,Evidence_basis=basis))
add(1,'P0','Identity','POST /api/cases','Patient HMAC mapping','BA / BE / Clinical','PID cục bộ trùng giữa hai cơ sở bị hợp nhất thành một bệnh nhân',
 'Cơ sở A và B cùng gửi PID 123456789: hai ca có cùng patient_id SYN-75A6A9D7F7E34ADD8F2671D32064EC6D.','PID thuộc namespace cơ sở, trừ khi có định danh toàn mạng đã được xác minh.',
 'Chạy probe.py rồi tenant-probe.py trong sandbox mới; tạo ca A và B với cùng chuỗi PID; so sánh patient_id.',
 'probe-results.json: create left case; tenant-results.json: same source PID at unrelated facility; '+source('backend/services/patient_identity.py','digest = patient_id_digest'),
 'get_or_create_patient chỉ nhận source_patient_id; HMAC/unique key không chứa facility_id. PatientModel là bảng chung.',
 'Liên kết nhầm bệnh nhân khi các cơ sở dùng mã cục bộ giống nhau. Probe không chứng minh bác sĩ đọc được ca cơ sở khác: GET đó trả 403.',
 'Thiết kế namespace định danh và quy trình liên kết đã xác thực; đánh giá bản ghi đã hợp nhất trước khi chuyển đổi. Chưa triển khai.')
add(2,'P1','Tenant administration','#admin/settings; PUT /api/admin/settings','Global JSON settings','BE / API / BA','Quản trị viên cơ sở sửa được cấu hình toàn hệ thống',
 'Scoped admin ghi AUDIT FACILITY A GLOBAL HEADER trả 200; global admin đọc thấy đúng giá trị đó.', 'Chỉ global admin sửa cấu hình toàn mạng hoặc settings được lưu theo facility_id.',
 'Dùng tài khoản audit-scoped-admin của probe; PUT settings; GET bằng global admin.',
 'tenant-results.json; '+source('backend/app/routers/admin.py','def update_admin_settings'),
 'Router chỉ require_admin; handler không lấy actor/facility; _ADMIN_SETTINGS và admin_settings.json dùng chung.',
 'Một cơ sở thay đổi cấu hình của các cơ sở khác; cùng dạng thiết kế dùng cho danh mục khoa/phòng.', 'Phân quyền global cho cấu hình chung và tenant-scope cho cấu hình cơ sở. Chưa triển khai.')
add(3,'P1','Backup','POST /api/admin/backups/create','Full database archive','BE / API / Security','API sao lưu toàn database không giới hạn global admin',
 'Code cho mọi ADMIN gọi BackupService.create_backup(include_images=False), dịch vụ sao chép toàn SQLite bằng backup API.', 'Sao lưu toàn mạng chỉ dành cho global operator; quyền cơ sở chỉ xuất metadata được phép.',
 'Đọc router require_admin, trigger_backup và BackupService.create_backup; không bấm tạo backup trong audit.',
 source('backend/app/routers/admin.py','def trigger_backup')+'; '+source('backend/services/backup_service.py','src_conn.backup'),
 'Handler không kiểm tra is_global_admin/facility; sao chép database nguyên khối.',
 'Quản trị cơ sở có thể kích hoạt tạo bản sao dữ liệu toàn mạng. Không khẳng định có endpoint tải archive hoặc đã trích xuất dữ liệu.',
 'Giới hạn quyền, vị trí lưu, retention và kiểm thử restore theo engine. Chưa triển khai.',basis='Confirmed static authorization path; archive execution BLOCKED')
add(4,'P1','Patient registration','#intake','Create/edit patient','FE / BA / Data','Thông báo đã tạo hồ sơ nhưng dữ liệu hồ sơ chỉ nằm ở trình duyệt',
 'Tạo Audit Synthetic Alpha báo thành công; context trình duyệt mới cùng tài khoản không thấy PID; không có request tạo patient.','Phân biệt rõ hồ sơ cục bộ và hồ sơ dùng chung; nếu phục vụ vận hành nhiều máy cần persistence phía server.',
 'Tạo patient trong intake; đăng nhập cùng user ở context mới; tìm PID đã tạo.',
 'browser-results.json: patient browser storage / same user fresh browser patient visibility; patient-created-upload.png; '+source('frontend/app/intake.js','patientsStore.add'),
 'createDemoPatientStore lưu localStorage theo user id, không có API CRUD demographic.',
 'Bác sĩ đổi máy hoặc nhân viên khác không tìm thấy hồ sơ; xóa dữ liệu trình duyệt làm mất danh bạ.', 'Làm rõ phạm vi lưu và xây hợp đồng persistence phù hợp nếu triển khai. Chưa triển khai.')
add(5,'P1','Intake defaults','#intake','Default patient list','FE / BA / Clinical','Bốn tên và PID mẫu hiện ra khi synthetic_demo_mode=false',
 'Sandbox sạch ngoài synthetic mode vẫn có Nguyễn Minh Anh/100000001 và ba hồ sơ khác, chọn được như hồ sơ thường.', 'Không tạo hồ sơ mẫu trong chế độ ngoài demo; mẫu phải gắn nhãn tổng hợp và bị giới hạn rõ.',
 'Mở intake với localStorage sạch và synthetic_demo_mode=false.',
 'intake-seeds.png; browser-results.json; '+source('frontend/app/intake.js','const patientsStore = createDemoPatientStore'),
 'Seeds hardcoded dùng bất kể mode; chỉ additions 300 hồ sơ được ràng buộc synthetic mode.',
 'Có thể chọn hồ sơ giả và tạo ca dưới PID mẫu trong thao tác hàng ngày.', 'Giới hạn seed vào sandbox tổng hợp; không tự tạo patient mẫu ngoài demo. Chưa triển khai.')
add(6,'P1','Account','#profile','Change password','FE / API','Đổi mật khẩu thành công làm phiên hiện tại hết hạn ở request tiếp theo',
 'POST change-password trả 200; chuyển cases dẫn đến #expired.', 'Phiên hiện tại nhận token mới khi đổi mật khẩu; các phiên cũ bị thu hồi theo chính sách.',
 'Đăng nhập doctor; đổi password qua profile; chuyển Danh sách ca.',
 'deep-browser-results.json: password change response + responses 401; after-password-change.png; '+source('frontend/app/personal.js','await request("/api/auth/change-password"'),
 'Backend tăng token_version và trả TokenResponse; personal.js không nhận/áp dụng access_token trả về.',
 'Bác sĩ bị gián đoạn không giải thích sau thông báo đổi mật khẩu thành công.', 'Đồng bộ session bằng token trả về và kiểm thử luồng tiếp tục công việc. Chưa triển khai.')
add(7,'P1','Bootstrap','Application startup','init_db bootstrap credentials','BE / Security','Khởi động lại ghi đè mật khẩu bootstrap đã đổi trong UI',
 'Sau đổi mật khẩu, restart cùng DB và env bootstrap cũ: password mới không đăng nhập được; password env cũ đăng nhập được.', 'Bootstrap không ghi đè mật khẩu user đã được thiết lập, trừ thao tác reset có chủ đích/audit.',
 'Đổi mật khẩu doctor; restart server với APP_DOCTOR_PASSWORD cũ; thử hai password.',
 'deep-browser-results.json / after-password-change.png; final-browser.cjs retry history documented in REPORT.md; '+source('backend/db/database.py','user.password_hash = hash_password(os.environ[password_key])'),
 'init_db gán lại hash cho mọi user bootstrap đang tồn tại mỗi khi env password có giá trị.',
 'Mật khẩu do người dùng đổi bị hoàn nguyên khi deploy/restart; độ bền thay đổi bảo mật không đúng kỳ vọng.', 'Bootstrap chỉ tạo mới; reset mật khẩu phải tường minh và có audit. Chưa triển khai.',basis='Source + isolated restart observation; failed first rerun is harness evidence')
add(8,'P1','Patient store','#intake','Concurrent cached store','FE / Data','Hai phiên danh bạ có thể ghi đè mất cập nhật của nhau',
 'Hai store dùng cùng storage: store A thêm Alpha; store B đã đọc cache thêm Beta; storage cuối mất Alpha.', 'Thêm/sửa không làm mất cập nhật hợp lệ từ phiên khác.',
 'node audit/2026-11-04/store-probe.mjs; xem firstUpdateLost=true.',
 'store-probe-results.json; '+source('frontend/app/intake-session.js','if (memory.has(key))'),
 'Cache Map luôn được ưu tiên; không refresh storage/merge/version hoặc lắng nghe storage event trước save.',
 'Mất hoặc hoàn nguyên hồ sơ khi cùng tài khoản dùng nhiều tab.', 'Dùng nguồn dữ liệu có version/concurrency và cơ chế đồng bộ. Chưa triển khai.',basis='Executable production store function + source')
add(9,'P2','Patient store','#intake','Empty list hydration','FE / Data','Danh sách đã xóa hết tự khôi phục seed khi mở lại',
 'save(key,[]) rồi tạo store mới/read(key) trả seed thay vì [].', 'Danh sách rỗng hợp lệ phải giữ nguyên.',
 'Chạy store-probe.mjs; xem emptyStoreAfterReopen.',
 'store-probe-results.json; '+source('frontend/app/intake-session.js','Array.isArray(rows) && rows.length'),
 'Điều kiện rows.length loại bỏ mảng rỗng và gọi save(key,seeds).',
 'Hồ sơ đã gỡ lại xuất hiện, khiến người dùng không tin thao tác xóa.', 'Phân biệt missing/invalid storage với empty list hợp lệ. Chưa triển khai.',basis='Executable production store function + source')
add(10,'P2','Privacy','#intake; logout','Local demographic retention','FE / Security / BA','Dữ liệu định danh lưu dài hạn trên thiết bị, không được xóa khi đăng xuất',
 'Danh bạ localStorage chứa name, phone, birth_year, hometown và national_id nếu nhập; logout chỉ gỡ token/expiry trong sessionStorage.', 'Quy định rõ mục đích, thời hạn, bảo vệ và cơ chế xóa dữ liệu định danh trên thiết bị dùng chung.',
 'Tạo patient tổng hợp; xem storage JSON; đọc logout cleanup.',
 'browser-results.json: patient browser storage; '+source('frontend/app/intake-session.js','storage().setItem')+'; '+source('frontend/app/auth.js','export async function logout'),
 'Persistent browser store nằm ngoài backend authorization/retention; user id trong key không phải kiểm soát truy cập ở mức OS.',
 'Tăng rủi ro dữ liệu lưu lại trên máy phòng khám. Không thực hiện khai thác XSS hoặc đọc dữ liệu thật.', 'Chọn chính sách tối thiểu hóa dữ liệu và quản lý lưu cục bộ phù hợp. Chưa triển khai.',basis='Runtime storage + static logout; privacy impact is risk assessment')
add(11,'P2','Registration','#intake patient modal','Required demographic fields','BA / PO / UX','Bắt buộc nhập thông tin không được truyền vào luồng khảo sát',
 'Phone, hometown, gender và birth year là required; request tạo ca chỉ truyền PID/date/reason/sides, không truyền tuổi đã tính.', 'Chỉ bắt buộc dữ liệu có mục đích nghiệp vụ; giá trị đã xác thực cần có đường sử dụng/persistence rõ.',
 'Mở Tạo bệnh nhân, kiểm tra required; đối chiếu create patient với run()/startBilateral payload.',
 'patient-create.png; field-inventory.json; '+source('frontend/app/intake.js','field("Số điện thoại"')+'; '+source('frontend/app/upload.js','patient_id: targetPid'),
 'Form danh bạ local tách khỏi hợp đồng case và patient context; tuổi không đi vào API tạo ca.',
 'Nhập thêm nhiều trường nhưng bước nhận định vẫn thiếu dữ liệu tuổi; lợi ích vận hành chưa được chứng minh.', 'Xác lập purpose từng field; tái sử dụng tuổi đã xác minh hoặc bỏ bắt buộc trường không phục vụ luồng. Chưa triển khai.',basis='Rendered required attributes + source; business necessity judgment')
add(12,'P2','Identity display','#intake → #case/:id → #report/:id','PID labels','UX / BA','Cùng nhãn PID nhưng intake và hồ sơ server hiển thị hai mã khác nhau',
 'Intake hiển thị PID 9 chữ số; case/report hiển thị SYN-...; tên patient đã chọn không đi cùng bản ghi server.', 'Phân biệt PID nguồn và mã nghiên cứu, hỗ trợ xác minh liên kết mà không lộ định danh không cần thiết.',
 'Chọn/create patient; tạo case; mở case và report; so sánh mã.',
 'patient-created-upload.png; case-detail.png; report-reviewed.png; probe-results.json.',
 'Server sinh pseudonym, UI gọi cả nguồn lẫn pseudonym bằng PID; label không thể hiện sự chuyển đổi.',
 'Người dùng khó đối chiếu ca với hồ sơ đã chọn và tưởng mã bị thay đổi.', 'Dùng thuật ngữ nhất quán, chỉ dẫn liên kết theo quyền. Chưa triển khai.')
add(13,'P2','Intake layout','#intake upload','Sticky action bar','UX / FE','Thanh Phân tích ảnh AI che nội dung chọn ảnh trên màn thấp',
 'Ở 1366×768, action bar nằm giữa vùng dropzone; ở 1440×900 che vùng control bên dưới.', 'Thanh hành động có vùng riêng, không phủ thao tác đang cần ở bước upload.',
 'Chọn patient, chưa upload; xem ở 1366×768 và 1440×900.',
 'upload-1366.png; upload-1440.png; '+source('frontend/css/workspace.css','.intake-action-bar {'),
 'Sticky bottom:40px ở cuối nội dung dài có thể dịch ngược lên phủ sibling khi viewport thấp.',
 'Giảm diện tích xem và thêm cuộn tìm control trong bước đầu khảo sát.', 'Dành không gian layout cho action bar và kiểm tra overlap ở viewport thấp. Chưa triển khai.',basis='Screenshot + CSS; no claim that scrolling cannot recover controls')
add(14,'P2','Intake responsive','#intake upload at 390px','datetime-local','UX / FE','Trường Ngày giờ khảo sát bị bó hẹp, không đọc được giá trị',
 'Ở 390px, hai field PID/date vẫn cùng hàng; datetime chỉ hiện một phần ngắn cạnh nút Hiện tại.', 'Đọc/kiểm tra được toàn bộ ngày giờ trước tạo ca.',
 'Mở upload ở 390×844.',
 'upload-390.png; browser-results.json controls boxes; '+source('frontend/app/intake.js','intake-metadata'),
 'Grid hai cột và flex datetime/button không đủ chiều rộng nội dung.',
 'Khó phát hiện sai ngày/giờ khi xác nhận metadata.', 'Cho metadata xuống hàng ở chiều rộng nhỏ, giữ input date đủ rộng. Chưa triển khai.')
add(15,'P2','Intake responsive','#intake at 390px','Patient table name column','UX / FE','Tên bệnh nhân xuống dòng gần từng ký tự trên mobile',
 'Danh sách 390px ép cột tên hẹp thành chuỗi dọc trong khi các nút thao tác chiếm ngang.', 'Tên patient vẫn đọc được, bảng cuộn ngang có chủ đích hoặc dùng cấu trúc phù hợp.',
 'Mở intake với danh sách seed tại 390×844.',
 'intake-390.png; '+source('frontend/app/intake.js','intake-patient-list'),
 'Bảng nhiều cột/action không có ràng buộc chiều rộng tối thiểu đủ cho cột tên trong layout mobile.',
 'Khó chọn đúng hồ sơ khi duyệt nhanh.', 'Bảo vệ chiều rộng cột định danh hoặc đổi presentation theo breakpoint. Chưa triển khai.',basis='Screenshot; specific CSS contributor requires further isolation')
add(16,'P2','Report','#report/:id','Missing ovary status','Clinical / BA / FE','Phiếu bỏ mất tình trạng bên đối diện đã ghi nhận',
 'Ca LEFT có contralateral_status=NOT_VISUALIZED; report chỉ ghi Chưa có ảnh khảo sát bên này.', 'Phân biệt không thấy, đã cắt bỏ và chưa tải ảnh; dùng đúng dữ liệu đã lưu.',
 'Tạo ca chỉ trái với NOT_VISUALIZED; review rồi xem/in report.',
 'probe-results.json: create left case; actual-print-text.json; '+source('frontend/app/report-preview.js','function reportSideOverview'),
 'Report renderer nhận danh sách images theo bên, không đưa contralateral_status vào overview.',
 'Người đọc downstream không biết bên đối diện đã khảo sát không thấy hay bị bỏ sót.', 'Hiển thị trạng thái thiếu bên từ snapshot đã lưu, theo ngữ nghĩa rõ ràng. Chưa triển khai.')
add(17,'P2','Admin/report integration','#admin/settings → #report/:id','report_header','FE / BE / API','Tên đơn vị trên phiếu được lưu nhưng không được renderer sử dụng',
 'PUT report_header thành công; source chỉ đọc field ở admin settings; report vẫn có tiêu đề cố định KẾT QUẢ KHẢO SÁT.', 'Field mang tên trên phiếu phải được áp dụng nhất quán hoặc nêu rõ chưa tích hợp.',
 'Đổi report_header trong tenant probe; mở actual-print.pdf; tìm header tùy chỉnh.',
 'tenant-results.json; actual-print-text.json; '+source('frontend/app/admin.js','Tên đơn vị trên phiếu')+'; '+source('frontend/app/report-preview.js','KẾT QUẢ KHẢO SÁT'),
 'Settings persistence không nối vào report rendering contract.',
 'Người quản trị tin đã cấu hình đơn vị nhưng phiếu không phản ánh thay đổi.', 'Nối contract theo facility/tenant đã xác minh, hoặc bỏ field sai kỳ vọng. Chưa triển khai.')
add(18,'P2','Report composition','#report/:id / print','First-page hierarchy','UX / Clinical','Trang đầu ưu tiên provenance kỹ thuật, ghi chú bác sĩ ở trang sau',
 'Một ảnh tạo hai trang: trang 1 có Model, SHA-256, UUID/revision và đoạn giải thích; O-RADS, mô tả, nhận định ở trang 2.', 'Trang tổng hợp hỗ trợ đọc nhanh kết quả do bác sĩ ghi nhận; provenance vẫn truy xuất được.',
 'Mở actual-print.pdf trang 1 và 2.',
 'actual-print.pdf; actual-print-text.json; report-reviewed.png.',
 'renderReportDocument chia overview/technical info vào trang đầu, nội dung từng ảnh vào evidence page.',
 'Người xem phải chuyển trang để thấy phần quan trọng; tăng giấy và tải nhận thức. Đây là đánh giá UX, không phải lỗi số liệu.', 'Ưu tiên nội dung bác sĩ trên phần tổng hợp, giữ cảnh báo RUO bắt buộc và provenance ở vị trí phù hợp. Chưa triển khai.',confidence='Medium',basis='Actual printed artifact + explicit UX judgment')
add(19,'P2','Operational analytics','#admin/reports','Missing metric defaults','BA / QC / FE','Không có quan sát nhưng dashboard hiển thị 0%, 0 điểm, 0s',
 'Khi chưa có prediction/review, cards hiện consensus 0%, IQA 0, thời gian 0s.', 'Không có dữ liệu khác với kết quả đo bằng 0; hiển thị N/A và mẫu số.',
 'Mở admin reports trên DB tổng hợp chỉ có ca chưa phân tích.',
 'admin-reports.png; '+source('backend/app/routers/admin.py','avg_iqa_score =')+'; '+source('backend/app/routers/admin.py','avg_review_seconds ='),
 'Aggregate None và denominator zero được thay bằng 0.0; FE render như giá trị đo.',
 'Người quản lý có thể hiểu nhầm chất lượng AI bằng 0 hoặc rà soát tức thời.', 'Giữ null/no-observation và hiển thị số mẫu/định nghĩa metric. Chưa triển khai.')
add(20,'P2','Clinical terminology','#viewer; #admin/reports','O-RADS labels','Clinical / UX / Content','Mốc O-RADS không nhất quán giữa viewer, rule engine và analytics',
 'Viewer label nang noãn <30 mm nhưng phần reference/rule dùng ≤30 mm; admin dùng 1–9% và 10–49% trong khi viewer dùng 1–<10% và 10–<50%.',
 'Thuật ngữ và khoảng liên tục nhất quán theo nguồn ACR được phê duyệt; không suy ra sinh lý chỉ từ kích thước.',
 'So sánh option O-RADS 1/3/4 với labels admin và PHYSIOLOGIC_FOLLICLE_POLICY.',
 source('frontend/app/viewer.js','nang noãn < 30 mm')+'; '+source('frontend/app/admin-reports.js','Nguy cơ thấp (1-9%)')+'; clinical-sources.md.',
 'Label sao chép riêng ở các module và không dùng một bộ thuật ngữ chuẩn.',
 'Gây mâu thuẫn tại đúng ngưỡng 30 mm và khi diễn giải nguy cơ giữa các màn hình.', 'Dùng bộ lexicon thống nhất, được chuyên gia xác nhận, bao gồm điều kiện áp dụng. Chưa triển khai.',basis='Rendered text + code + verified primary ACR source')
add(21,'P2','Accessibility','#admin/reports','Chart drilldown rows','FE / A11y','Hàng biểu đồ có click drilldown nhưng không có bàn phím/semantic control',
 'chart-drilldown-row là div cursor:pointer/data-orads; handler onclick; không có tabindex/role/key handler cho hàng đó.', 'Mọi drilldown tương tác phải truy cập và kích hoạt được bằng bàn phím.',
 'Đọc markup/hook chart-drilldown-row, thử Tab tới hàng category; runtime keyboard activation chưa chạy.',
 source('frontend/app/admin-reports.js','<div class="chart-drilldown-row"')+'; admin-reports.png.',
 'Dùng div click thay vì button/link với tương tác keyboard native.',
 'Người dùng bàn phím không dùng được bộ lọc từ biểu đồ theo cách tương đương.', 'Dùng control semantic và focus rõ. Chưa triển khai.',basis='Confirmed markup/handler inspection; runtime keyboard drilldown NOT TESTED')
add(22,'P3','Save feedback','#viewer/:id','Success toast','UX / Content','Ca chỉ có ảnh trái vẫn báo lưu hai bên thành công',
 'Ca LEFT/NOT_VISUALIZED có một image; toast Đã lưu rà soát của hai bên thành công.', 'Thông báo đúng số ảnh/bên đã lưu, không xác nhận phần không có ảnh.',
 'Lưu review một ảnh trái.',
 'viewer-after-save.png; '+source('frontend/app/review.js','Đã lưu rà soát của hai bên thành công'),
 'Success toast hardcoded hai bên cho mọi case.',
 'Có thể hiểu nhầm bên phải đã được rà soát; report vẫn chỉ có một ảnh.', 'Sinh thông báo từ phạm vi đã lưu. Chưa triển khai.')
add(23,'P3','Network errors','#viewer/:id; #admin/system','Error toast/text','UX / Content','Lỗi mạng lộ chuỗi Failed to fetch tiếng Anh',
 'Giả lập connectionreset khi save: draft/status xử lý đúng, toast hiện Failed to fetch.', 'Thông báo ngắn gọn tiếng Việt và hành động phục hồi cụ thể.',
 'Abort /api/reviews/batch trong Playwright rồi lưu note.',
 'viewer-network-save-failure.png; '+source('frontend/app/api.js','throw error;'),
 'Fetch TypeError không chuẩn hóa, được truyền vào toast(e.message).',
 'Người dùng không hiểu nguyên nhân; không có bằng chứng false-success, vì save status báo lỗi đúng.', 'Chuẩn hóa network error theo ngữ cảnh và giữ draft. Chưa triển khai.')
add(24,'P2','Training protocol','evaluation/selected_model.json','Selected model loss specification','AI / Governance','Loss của checkpoint đang phục vụ khác core scope Dice+BCE',
 'Selected manifest khai báo AdvancedHybridLoss(0.5 FocalTversky + 0.3 SoftDice + 0.2 BCE); training baseline khác dùng 0.5 BCE +0.5 Dice.', 'Phương pháp checkpoint phục vụ phải khớp phạm vi đã duyệt hoặc có quyết định thay đổi và tài liệu truy vết.',
 'Đọc selected_model.json loss_function và core scope AGENTS.md.',
 source('evaluation/selected_model.json','loss_function')+'; '+source('ai_training/train_unetplusplus_resnet34.py','criterion = ComboLoss'),
 'Lựa chọn checkpoint boosted không đồng bộ mô tả phương pháp core scope. Chưa tái huấn luyện hoặc đối chứng loss.',
 'Sai lệch phương pháp khóa luận/provenance; không phải bằng chứng model kém chính xác hay lỗi inference.', 'Đối soát phê duyệt phương pháp, experiment lineage và mô tả mô hình phục vụ. Chưa triển khai.',basis='Manifest/source discrepancy; checkpoint training history only partially verified')
add(25,'P3','Report typography','#report/:id / print','Patient ID block','UX / Content','PID giả danh bị tách ba dòng ở phần định danh phiếu',
 'SYN- và chuỗi hash dài xuống nhiều dòng, chữ cuối tách riêng trong bản in trang 1.', 'Mã định danh đọc/đối chiếu được, có trình bày phù hợp chuỗi dài.',
 'Mở actual-print.pdf trang 1.',
 'actual-print-text.json; actual-print-page-1.png; report-reviewed.png.',
 'Khối PID dùng cột hẹp trong hàng ba cột; wrap chuỗi không phù hợp.',
 'Giảm khả năng đối chiếu nhanh mã hồ sơ; mức ảnh hưởng thấp vì mã vẫn đầy đủ.', 'Điều chỉnh bố cục định danh không cắt vụn chuỗi. Chưa triển khai.')

(O/'issues.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2),encoding='utf-8')
with (O/'issues.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(issues[0]));w.writeheader();w.writerows(issues)
register=['# Complete issue register','', 'All recommendations below remain unimplemented. CONFIRMED denotes the specific observed/static behavior, not a claim that clinical harm occurred. Severity, remediation priority and evidence confidence are independent.','']
for i in issues:
 register+=['## '+i['Issue_ID']+' — '+i['Severity']+' — '+i['Description'],'','| Field | Finding |','|---|---|']
 register += ['| '+k.replace('_',' ')+' | '+str(v).replace('|','\\|').replace('\n','<br>')+' |' for k,v in i.items() if k not in ('Issue_ID','Description')]
 register+=['']
(O/'ISSUE_REGISTER.md').write_text('\n'.join(register),encoding='utf-8')
print('issues',len(issues),dict(Counter(i['Severity'] for i in issues)))
