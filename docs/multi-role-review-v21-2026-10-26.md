# Review đa vai trò v2.1 — 26/10/2026

## A. Review context

- **Feature:** 9 hạng mục v2.1 được mô tả trong báo cáo người dùng: watershed; diagnostic engine; CDSS integration; Active Learning; schema; structured report; Box Prompt; classifier training; diagnosis card.
- **Objective:** xác minh hành vi và bằng chứng nghiệm thu; tìm lỗi chức năng, dữ liệu, UX, quyền, concurrency và khoảng trống yêu cầu. Đây là review, không phải nhiệm vụ triển khai thêm năng lực chẩn đoán.
- **Actors:** bác sĩ DOCTOR, quản trị ADMIN, hệ thống suy luận/CDSS, người nhận báo cáo. Chưa có bằng chứng patient portal/đặt lịch thuộc phạm vi.
- **Requirements:** AGENTS.md; báo cáo v2.1 được cung cấp; kế hoạch `docs/superpowers/plans/2026-10-26-v2.1-multibranch-diagnosis.md`; hợp đồng RUO trong MODEL_CARD.md; schema, API và các kiểm thử hiện có. Ưu tiên dữ liệu có nguồn, phân biệt unknown/negative, kiểm soát HITL, patient-level split và Letterbox.
- **Assumptions:** review working tree hiện có, không chỉ HEAD; toàn bộ ảnh đưa vào probe/browser là synthetic, DB thử nghiệm được cô lập. Không xác nhận hiệu lực lâm sàng từ test phần mềm.
- **Unknowns:** chưa có bộ user story/AC v2.1 riêng được phê duyệt; chưa chốt chuyển từ segmentation-only sang diagnosis; chưa có target SLO, mô hình classifier đã xác thực, quy tắc phát hành báo cáo và chính sách lease khi xử lý lâu.

**Lưu ý phiên bản:** working tree thay đổi trong lúc review. Reviewer chỉ tạo tài liệu/probe/log, không sửa mã ứng dụng. Active Learning đã chuyển từ JSONL sang DB; sau đó bổ sung flush review cha trước queue con. Báo cáo phân biệt lỗi lịch sử đã sửa với lỗi còn tái hiện. Không dùng kết quả pass của bản trước để chứng nhận bản sau. Manifest và log nằm trong [thư mục evidence](../artifacts/v21-review-2026-10-26/).

**Kết quả hồi quy cuối đã chạy:** 1.087 passed, **3 failed**, 2 skipped, 6 deselected, 95,42 giây. Ba failure nằm trong `test_duplicate_upload.py`: hai ca barrier/concurrency và một ca lease hết hạn trong decode. Bộ review/lease riêng đạt 25/25; JS đạt 85/85 ở snapshot đã kiểm. Kết quả gần nhất của năm browser scripts: viewer, safety, roundtrip và doctor PASS; comprehensive FAIL vì một search request `ERR_ABORTED`. Không có bằng chứng 5/5 PASS trong lượt review này. Source tiếp tục có chỉnh sửa ngoài nhiệm vụ review; các log chỉ chứng nhận snapshot đã chạy.

## B. Findings by role và cross-review

### 1. Ultrasound Specialist / Domain User

- **R02:** cùng mask nhưng Box Prompt hiển thị số đo nhỏ hơn đường đo trên ảnh gốc. Impact: bác sĩ nhìn hai kết quả không nhất quán; nếu dùng số đo nháp downstream có thể sai phân tầng. Expected: phép đổi tọa độ phải giữ đơn vị vật lý. **Confirmed Bug, High.**
- **R03:** sửa riêng chẩn đoán vẫn lưu được, nhưng không vào Active Learning. Expected theo cam kết v2.1: các sửa đổi chẩn đoán phải được ghi nhận. **Confirmed Bug, Medium.**
- **R09:** bấm lại bên đang xem xóa mô tả CDSS; gây nhập lại khi thao tác lặp nhiều ca. Expected UX: giữ nội dung khi không thay đổi ngữ cảnh. **UX Friction, Medium**, không tự nâng thành lỗi dữ liệu hồ sơ vì form đã công bố không persist.

### 2. Patient / End User

- Quan tâm chính là thông tin xuất ra và khả năng hiểu báo cáo. **R04** tự tạo “85%” không có trong findings có thể khiến người đọc tưởng đã có xác suất được đo; helper chưa được nối với báo cáo đang dùng nên không khẳng định bệnh nhân đã nhận kết quả sai.
- Không xếp thiếu đặt lịch, check-in, notification hay patient login thành bug: chưa có yêu cầu/actor tương ứng. Cần PO xác định nếu muốn mở rộng phạm vi.
- Mã máy trong panel CDSS (**R10**) làm người dùng không chuyên khó hiểu, nhưng panel hiện dành cho nhân viên nghiên cứu; không coi đây là lỗi patient portal.

### 3. QA/QC

- Boundary probes xác nhận **R05** bỏ sót nang gần biên và **R07** nhận xác suất NaN/âm/lớn hơn 1 mà không abstain.
- **R06:** thiếu phép đo bị chuyển thành 0/NOT_SUGGESTED, và `complete=True` dù CDSS báo thiếu trường. Expected: không biến thiếu dữ liệu thành đánh giá hoàn tất.
- Bằng chứng pass hiện có không bao phủ các ca này. Tests của helper không chứng minh đường API → DB → reopen → report đã sử dụng helper.

### 4. Senior Automation / Technical Tester

- Tái hiện API thật: review, idempotency, diagnosis-only feedback, Box Prompt, role transition; dữ liệu tổng hợp và DB riêng.
- **R01 lịch sử:** queue JSONL ghi trước commit; sau khi chuyển DB xuất hiện lỗi FK làm lưu MODIFIED trả 409. Bản bổ sung flush cha đã được kiểm tra lại thành công.
- **R08:** abort request CDSS khi chuyển bên để lại nút ghi “Đang đối chiếu…”.
- **R11:** `numbers_match()` chỉ so tập số, không kiểm tra số thuộc trường/đơn vị/bên nào.
- Second pass kiểm tra role DOCTOR→ADMIN: cả case và Box Prompt đều trả 403. Không xác nhận lỗ hổng chỉ vì handler dùng `get_current_user`; router còn có `require_clinical`.

### 5. BA / PO — phản biện và quyết định

**QA:** “API luôn trả `ai_diagnosis=None`, vậy diagnosis card bị lỗi.”

**BA:** MODEL_CARD và tests hiện hành cố ý chặn chẩn đoán từ checkpoint chỉ phân đoạn. Không bật chẩn đoán để làm khớp một báo cáo hoàn thành. Chốt **R12 — Requirement Gap**: phạm vi release và AC mâu thuẫn, cần quyết định sản phẩm.

**Technical:** “POST review trả 409, có thể là conflict hợp lệ.”

**Domain:** “Một bác sĩ, lease đúng, revision đúng vẫn không lưu được mask sửa.”

**QA:** log SQL xác nhận `FOREIGN KEY constraint failed` tại INSERT queue. **BA:** **R01 Confirmed Bug, High** khi tái hiện; sau thay đổi flush và retest, chuyển **Resolved in observed workspace**, giữ bằng chứng trước/sau.

**Technical:** “Số đo 9,9 mm có thể là spacing trên lưới 512?”

**QA:** request không gửi override; endpoint dùng `ImageModel.pixel_spacing_mm=0.1` của ảnh gốc 1024², còn pipeline chuẩn inverse Letterbox cho 19,9 mm. **BA:** **R02 Confirmed Bug, High**; không phải khác quy tắc làm tròn.

**QA:** “Test expiry mong 423 nhưng upload trả 200; mọi trường hợp đó là bug?”

**BA:** chưa có quyết định lease được kiểm tra lúc nhận tác vụ hay phải còn hạn lúc commit. Transaction hiện giữ quyền ghi trong lúc decode. Chốt **R14 — Need Clarification**, không suy diễn đã có hai bác sĩ ghi đè nhau.

**QA:** “Comprehensive E2E đỏ nghĩa là giao diện hỏng.”

**Technical:** lỗi cuối là `ERR_ABORTED` của search; navigation chủ động abort request cũ. **BA:** **R13 Technical Risk của evidence/test oracle**, chưa đủ chứng cứ gọi lỗi sản phẩm. Giữ nguyên kết quả FAIL, không miễn trừ tất cả lỗi mạng để làm xanh.

## C. Consolidated findings

| ID | Type | Severity | Finding | Expected behavior | Impact | Source | Status |
|---|---|---|---|---|---|---|---|
| R01 | Confirmed Bug | High | Queue rollback/idempotency lỗi ở bản đầu; bản chuyển DB có lỗi FK chặn lưu | Review và queue cùng transaction, replay phân biệt nội dung | Lưu review bị chặn hoặc feedback không hợp lệ | review_service; API probes | Resolved trong bản đã retest; xem lịch sử |
| R02 | Confirmed Bug | High | Box Prompt bỏ hệ số Letterbox khi tính mm/cm² | Đo trên ảnh gốc hoặc đổi spacing đúng scale | Số đo sai ở API tương tác | inference.py:966,987 | Open, API thật tái hiện |
| R03 | Confirmed Bug | Medium | Sửa riêng chẩn đoán không tạo queue | Ghi nhận sửa chẩn đoán theo cam kết v2.1 | Mất feedback học chủ động; hồ sơ vẫn lưu | review.js:76; review_service.py:330 | Open, API thật tái hiện |
| R04 | Confirmed Bug | Medium | Structured report tự thêm xác suất PCOS 85% | Không có xác suất nguồn thì không in phần trăm | Con số không có nguồn trong báo cáo nháp | report_generator.py:395 | Open, helper chưa nối production |
| R05 | Confirmed Bug | Medium | Watershed bỏ nang gần biên khi ảnh có nang khác | Không làm mất component hợp lệ chỉ vì thêm component xa | Đếm thiếu trước bước phân tích hình thái | morphology_extractor.py:38 | Open, synthetic helper probe |
| R06 | Confirmed Bug | Medium | Thiếu phép đo/morphology thành kết quả âm tính hoặc complete | Giữ trạng thái unavailable/incomplete | Dễ tạo sự yên tâm sai khi tích hợp | inference_engine.py:881; diagnostic_engine.py:98,148 | Open, helper probe |
| R07 | Confirmed Bug | Medium | NaN, nhãn lạ, xác suất ngoài miền vẫn `abstain=False` | Reject hoặc abstain với đầu vào không hợp lệ | Dữ liệu không hợp lệ thành nhãn BENIGN | diagnostic_engine.py:54 | Open, helper probe; API hiện chưa gọi |
| R08 | Confirmed Bug | Low | Nút CDSS còn “Đang đối chiếu…” sau abort | Trở lại nhãn idle khi request đã hủy | Chờ/bấm lặp không cần thiết | cdss-panel.js:228,249,310 | Open, Node DOM/network probe |
| R09 | UX Friction | Medium | Bấm lại L khi đang ở L xóa form CDSS | Không reset khi ngữ cảnh không đổi | Nhập lại mô tả, tăng thao tác | viewer.js:1000 | Open, Chrome thật tái hiện |
| R10 | UX Friction | Low | Missing fields/status dùng mã máy | Gắn nhãn người dùng có thể đối chiếu với form | Khó biết trường cần bổ sung | cdss-panel.js:169,179,185 | Open, source review |
| R11 | Technical Risk | Medium | Guard số không bảo toàn ngữ nghĩa | Nếu dùng làm cổng chống sai số, cần kiểm tra trường/đơn vị/bên | Hoán đổi số vẫn qua guard | report_generator.py:323 | Open, helper probe |
| R12 | Requirement Gap | High | Tuyên bố hoàn tất v2.1 khác phạm vi thực của code | Baseline, AC, năng lực model và release claim thống nhất | Nghiệm thu/triển khai nhầm năng lực | MODEL_CARD; training CLI; router/UI | Open, cần PO/Clinical Owner |
| R13 | Technical Risk | Medium | Test oracle/evidence có điểm dễ báo sai | Phân biệt hủy hợp lệ, lỗi mạng và lỗi fixture | Kết luận pass/fail không phản ánh đúng hệ thống | comprehensive E2E; upload race tests | Open, cần điều tra test theo từng failure |
| R14 | Need Clarification | Medium | Lease hết hạn trong xử lý upload | Chốt thời điểm hiệu lực quyền và hành vi recovery | Chưa xác định đúng acceptance của slow upload | inference.py:134; test_duplicate_upload.py:467 | Open; test hiện kỳ vọng 423, actual 200 |

### Chi tiết tái hiện và chuỗi ảnh hưởng

**R01 — lịch sử và counter-check.** Ở bản JSONL, ép commit thất bại: HTTP 500, 0 review, revision 0 nhưng queue có 1 dòng; retry thành công tạo dòng thứ hai. Hash cũ bỏ overrides nên thay locules 2→3 với cùng request ID trả response cũ. Khi source đổi sang bảng queue, single-user save với lease/revision đúng trả 409; SQL lỗi FK khi queue tham chiếu review chưa flush. Sau bổ sung `db.flush([review_record])`: save override HTTP 200/revision 1/queue 1; sửa mask HTTP 200/revision 2; thay overrides cùng request ID HTTP 409. Bộ review/lease retest 25/25 PASS. Không coi 409 trước sửa là conflict hợp lệ vì probe chỉ có một actor. Không xóa hay chỉnh dữ liệu JSONL cũ trong nhiệm vụ review.

**R02 — High, counter-check đầy đủ.** Tạo ảnh tổng hợp 1024×1024, nền 200, vòng tròn tối bán kính 100 tại tâm, calibration gốc 0.1 mm/pixel. Có case, image và lease hợp lệ; POST `/api/v1/inference/interactive-prompt` với box `[170,170,342,342]`, không gửi spacing override. HTTP 200; endpoint trả 9.9 mm và 0.773 cm². Chạy `measure_source_mask` của pipeline hiện có trên chính mask trả về: 19.9 mm và 3.114 cm². Endpoint bỏ transform trả từ `preprocess_for_inference` và nhân source spacing trực tiếp trên lưới 512. Chuỗi ảnh hưởng: resize → sai đơn vị vật lý → API/UI đối chiếu sai → rủi ro báo cáo nếu sau này nối vào report. Chưa chứng minh báo cáo A4 hiện tại dùng các số sai này. Sửa cần theo contract source-coordinate hiện có; không sửa bằng hệ số cố định 2 cho mọi ảnh.

**R03.** Giữ nguyên mask; đổi `lesion_type` thành `mucinous_cystadenoma`; gửi theo payload UI hiện tại (`ACCEPTED_RAW`, không overrides), request ID mới và revision mới. HTTP 200, queue tăng 0. UI tính action theo mask; queue chỉ xét MODIFIED/nonempty overrides. Diagnosis saved → feedback không đến tập review ưu tiên → training tương lai bỏ sót bất đồng. Expected không có nghĩa mọi ACCEPTED_RAW đều phải vào queue; cần so sánh thay đổi chẩn đoán có nguồn trước/sau hoặc gửi override tường minh.

**R04.** Gọi `build_structured_findings_report` với `ai_diagnosis={abstain:False, pcos_suggestion:{suggested:True}}`, không có `prob`. Output chứa `85%`, do default 0.85. Không phải một xác suất được hiệu chuẩn. Hàm report mới chưa được gọi từ route báo cáo đang dùng; severity phản ánh phạm vi helper hiện tại. Không cần thêm một xác suất giả khác để sửa.

**R05.** Mask 64²: hình tròn tâm (2,20), bán kính 2 có diện tích đạt min_area → count 1. Thêm hình tròn cách xa tại (32,32), bán kính 6 → connected components 2 nhưng count vẫn 1. `peak_local_max` bỏ peak gần biên; fallback chỉ chạy khi không có peak nào toàn ảnh. Chuỗi: component mất marker → watershed không gán nhãn → count thiếu. Không phải hai nang chạm nhau hay component dưới ngưỡng.

**R06.** `synthesize_multibranch_findings('synthetic-review','left')` không cung cấp nang/thể tích vẫn trả PCOS `NOT_SUGGESTED`, count 0. Cung cấp riêng diameter 40 và probabilities, không ảnh/features: `orads_suggested.complete=True`, missing `[]`, trong khi `cdss_raw.status=INSUFFICIENT_DATA`. Empty mask còn sinh `ANECHOIC` confidence .90 và các negative descriptor .99. Đây là biến thiếu quan sát thành giá trị khẳng định trong helper; không nói rằng bệnh nhân thực đã bị phân loại sai.

**R07.** `fuse_and_evaluate({'simple_cyst':float('nan')},{})` trả `abstain=False`, BENIGN. Nhãn không thuộc tập lớp với xác suất 1.0 cũng qua; probabilities 1.5 và -0.5 sinh nguy cơ âm. Expected reject/abstain; quyết định cụ thể reject hay abstain là lựa chọn contract. Counter-check: có thể caller hứa đầu vào hợp lệ, nhưng schema hiện chưa khóa miền dữ liệu này; đặc biệt NaN từ pipeline không được biến thành kết quả tin cậy. Scope là helper chưa production-integrated.

**R08.** Submit CDSS với Promise network chưa hoàn tất → đổi context → `resetForSide()`/abort → status NOT_EVALUATED, button enabled nhưng text “Đang đối chiếu…”. Đối chiếu nhãn idle từ markup là “Đối chiếu quy tắc RUO”. Bằng chứng Node với DOM/network giả; không gọi đây là browser measurement.

**R09.** Login bác sĩ trên server cô lập, tạo ca hai ảnh tổng hợp, chạy inference, mở Mở rộng & RUO, nhập số thùy 3 ở L. Click lại nút L: giá trị thành rỗng; không đổi bệnh nhân hay bên. Chrome không phát sinh pageError. Không áp dụng finding cho L→R vì reset khi đổi bên có mục đích an toàn. Ảnh chụp còn cho thấy message tạm “Không có quyền đối chiếu hoặc phiên đánh giá đã kết thúc”; chưa mở finding quyền riêng từ dòng chữ đó.

**R10.** `renderResponse` ghép trực tiếp status/missing_fields vào textContent. Không phải XSS; vấn đề là liên hệ `max_diameter_mm` với nhãn “Đường kính lớn nhất...” và hiểu `INSUFFICIENT_DATA`. Đề xuất dictionary nhãn, giữ mã kỹ thuật trong chi tiết nếu cần.

**R11.** `numbers_match('Diameter 2 mm; O-RADS 25','Diameter 25 mm; O-RADS 2')` trả True. Hàm đúng với docstring hẹp “không có số mới”; chưa đủ để bảo đảm số liệu không bị gán nhầm trường. Vì yêu cầu kiểm tra ngữ nghĩa chưa rõ và helper chưa nối route, xếp Technical Risk. Việc bỏ toàn bộ số cũng có thể qua quan hệ tập con; cần chốt có cho phép rút gọn hay không.

**R12 — High, counter-check.** CLI `python ai_training/train_classifier_8class.py --epochs 1` exit 1: “Classifier training is not implemented; refusing to report a successful training run.” Chưa có dataset loader/split/train loop/save classifier checkpoint trong file này. `synthesize_multibranch_findings`, watershed helper và structured report chưa được nối thành đường production v2.1; API trả diagnosis/unified findings None; UI cố ý hiển thị giới hạn phân đoạn. Classifier 2-kênh không tự được registry segmentation nạp chỉ vì chép file vào `weights`. Mapper CDSS cũng dùng source/modality khác contract clinician/ultrasound_2d và đọc `orads_category` thay vì `orads_stratification.category`. `verified_features` được plan nhắc nhưng chưa có schema. Guard hiện hành là đúng với MODEL_CARD; vì vậy cần sửa baseline/acceptance và thiết kế integration có xác nhận bác sĩ, không coi bỏ guard là cách sửa bug. Test synthetic forward chứng minh shape, không chứng minh training hay tính đúng lâm sàng.

**R13.** Comprehensive chạy hết các bước layout/auth/report/admin rồi fail vì một POST search bị `net::ERR_ABORTED`: lần đầu `/api/cases/search`, lần cuối `/api/workspace/cases/search`; router chủ động abort khi navigation. Cần trace thời điểm request/cancel để xác nhận cancellation nào hợp lệ, không lọc bỏ mọi requestfailed. Hai upload race tests đặt Barrier ở decode, trong khi lease update đã chiếm SQLite write transaction trước decode: một request chờ peer tại barrier, peer chờ DB lock; `BrokenBarrierError` không tự chứng minh dữ liệu upload bị race. Test rollback từng dùng count toàn bảng trên DB suite chung: chạy riêng pass, chạy cùng các test có review trước đó fail; kiểm tra isolation/filtered counts trước khi kết luận rollback mất dữ liệu. Failure rollback không còn ở lần full suite cuối.

**R14.** Test hiện có thay clock lease thành năm 2099 ngay sau decode; mong 423/no insert nhưng nhận 200. Code validate/renew trước decode, không tái kiểm tra trước commit. Chưa có bằng chứng takeover xảy ra đồng thời vì transaction còn giữ khóa ghi. PO/IT cần quyết định request được nhận khi lease hợp lệ có được hoàn tất sau expiry không; sau đó mới chốt test/HTTP status/retry policy.

## D. BA decision

### Confirmed bugs còn mở

R02, R03, R04, R05, R06, R07, R08. Ưu tiên R02 vì đường API có sẵn; tiếp đến R03 và các gate dữ liệu trước khi tích hợp nhánh chẩn đoán.

### Confirmed bugs đã được sửa trong working tree quan sát

R01: transaction queue, request hash và FK insert ordering; đã retest API và 25 tests review/lease. Giữ log lịch sử, không quy công sửa mã cho nhiệm vụ review này.

### Potential / Need clarification

R14: thời điểm hết hiệu lực lease. Không nâng các test barrier/ERR_ABORTED thành lỗi concurrency/sản phẩm khi chưa có chứng cứ đúng mức. Patient-facing workflow cần xác định scope trước khi đưa vào backlog.

### UX / process friction

R09 và R10; R08 là lỗi trạng thái đã xác nhận, không chỉ sở thích giao diện.

### Enhancements

Không đề xuất thêm tính năng trước khi xử lý lỗi và chốt R12. Hỗ trợ point prompt/MedSAM thật chỉ trở thành requirement sau khi thống nhất contract; endpoint hiện là ROI + Gaussian/Otsu, không có bằng chứng inference MedSAM.

### Technical risks

R11, R13; hiệu năng SLO/concurrency thực và clinical validation vẫn là unknown đã có trong hồ sơ dự án, không báo lại thành bug mới. Queue JSONL cũ cần được chủ dữ liệu đánh giá trước khi dùng cho training; review này không sửa/xóa nó.

### Open questions

1. Release tiếp theo nghiệm thu segmentation RUO hay 8-class diagnosis có model được xác thực? Ai duyệt AC và clinical descriptors?
2. Với sửa diagnosis/O-RADS nhưng giữ mask, cần lưu diff/provenance nào và định nghĩa feedback đủ điều kiện training ra sao?
3. Box/point prompt là thuật toán ảnh nghiên cứu hay inference MedSAM? API cần công bố provenance tương ứng thế nào?
4. Lease được kiểm tra lúc bắt đầu hay trước commit; pending request được phục hồi thế nào?
5. Patient portal, phát hành/ký báo cáo, SLO và thiết bị cảm ứng có trong release này không?

## E. Coverage check

- **Requirements reviewed: 9/9 hạng mục được cung cấp**, ở mức source/call graph và kiểm thử liên quan; không đồng nghĩa 9/9 đã triển khai hoàn chỉnh.
- **Acceptance criteria reviewed: N/A** — phần INPUT để trống AC; không có denominator AC v2.1 đã phê duyệt. Checklist plan và tests được đối chiếu nhưng không gọi chúng là bộ AC đầy đủ.
- **Happy path:** login, intake, upload, inference segmentation, review, reopen, A4; API override/mask save đã kiểm lại sau source change.
- **Negative/boundaries:** thiếu ảnh, sai box, mask rỗng/biên, probability NaN/âm/>1, thiếu calibration/features; upload corrupt/empty/oversize và schema guards trong tests hiện có.
- **State transitions:** PENDING→ANALYZED→REVIEWED; readonly/finalized guards, lease acquire/expire/release, role change, CDSS pending→abort, cùng bên/đổi bên. Chưa nghiệm thu lifecycle ký/phát hành kết quả bệnh viện.
- **Data lifecycle:** create/save/edit/review/reopen/report và delete/rollback tests; Active Learning commit/retry/diff. Chưa kiểm training consumer/migration từ JSONL vì pipeline classifier chưa có.
- **Error/recovery:** simulated commit failure; failed save giữ draft; stale revision; request abort/route change; expired role/access; synthetic fault injection. Không đo mạng bệnh viện hay khôi phục backup thật.
- **Permissions:** role-level UI/API; lease ownership; DOCTOR→ADMIN bị 403 ở case và Box Prompt. Không thực hiện pentest toàn diện hay xác minh một scope tenant chưa được định nghĩa.
- **Concurrency:** idempotency, concurrent reviews, lease guards, concurrent upload tests. Một số upload tests fail/barrier nên chưa chứng nhận upload concurrency.
- **Integration:** segmentation→DB→reopen→A4 có bằng chứng; v2.1 classifier/diagnostic/report path chưa end-to-end; không kiểm tích hợp lịch hẹn/PACS/notification không thuộc scope.
- **UI/UX:** Chrome thật, synthetic images, viewport 390/768/1024/1366/1440 qua các script liên quan; xem screenshot desktop/mobile và same-side reset. Chưa test screen reader, touch/stylus vật lý, Safari/Firefox hay usability với bác sĩ/bệnh nhân thật.
- **Second-pass bug hunt:** hoàn tất; phát hiện bổ sung same-side reset, invalid probabilities/missing data, numeric semantic guard; role bypass nghi ngờ bị loại sau kiểm tra router dependency/API 403. Các phát hiện trùng được gộp.

## Evidence index

Các probe ghi lại **hành vi lỗi hiện có**, nên exit 0 của probe không có nghĩa sản phẩm đã sửa lỗi.

| Evidence | Ý nghĩa |
|---|---|
| [current-api-results.json](../artifacts/v21-review-2026-10-26/current-api-results.json) | Bản cuối API thật: save, feedback queue, hash, geometry, role guard và report helper |
| [before-fk-fix-api-results.json](../artifacts/v21-review-2026-10-26/before-fk-fix-api-results.json) | Lỗi FK trước thay đổi flush |
| [technical-results.json](../artifacts/v21-review-2026-10-26/technical-results.json) | Kết quả lịch sử JSONL trước khi source thay đổi; không dùng như trạng thái hiện tại |
| [current-api-probes.py](../artifacts/v21-review-2026-10-26/current-api-probes.py) | Script tái hiện cô lập, không sửa ứng dụng |
| [clinical-probe-current.log](../artifacts/v21-review-2026-10-26/clinical-probe-current.log) | 7 boundary/helper scenarios |
| [clinical-probe.py](../artifacts/v21-review-2026-10-26/clinical-probe.py) | Script synthetic cho helper |
| [ux-cdss-cancel-probe.log](../artifacts/v21-review-2026-10-26/ux-cdss-cancel-probe.log) | Nút loading sau abort; Node, không phải browser |
| [ux-same-side-results.json](../artifacts/v21-review-2026-10-26/ux-same-side-results.json) | Chrome thật: 3→rỗng khi L→L |
| [same-side-reset.png](../artifacts/v21-review-2026-10-26/same-side-reset.png) | Screenshot synthetic |
| [training-cli.log](../artifacts/v21-review-2026-10-26/training-cli.log) | Training entry point exit 1 vì chưa triển khai |
| [targeted-v21.log](../artifacts/v21-review-2026-10-26/targeted-v21.log) | 29 tests v2.1 PASS trên snapshot đã chạy |
| [node-tests.log](../artifacts/v21-review-2026-10-26/node-tests.log) | 85 JS tests PASS |
| [final-review-tests.log](../artifacts/v21-review-2026-10-26/final-review-tests.log) | 25/25 review/lease PASS sau fix được quan sát |
| [pytest.log](../artifacts/v21-review-2026-10-26/pytest.log) | Snapshot đầu: 1087 pass, 2 skip, 6 deselect; 83.69 s |
| [pytest-current.log](../artifacts/v21-review-2026-10-26/pytest-current.log) | Snapshot giữa thay đổi: 1082 pass, 7 fail, 2 skip, 6 deselect; 95.11 s |
| [pytest-final.log](../artifacts/v21-review-2026-10-26/pytest-final.log) | 1087 pass, 3 fail, 2 skip, 6 deselect; 95.42 s; cả ba failure thuộc upload tests |
| [final-browser/browser-results.json](../artifacts/v21-review-2026-10-26/final-browser/browser-results.json) | Doctor pass; comprehensive fail vì request search abort ở lần cuối |
| [current-browser/clinical_roundtrip_e2e.js.log](../artifacts/v21-review-2026-10-26/current-browser/clinical_roundtrip_e2e.js.log) | Real model/DB/reopen/report, PDF 2 trang A4, 0 pageError |
| [workstation_viewer_e2e.js.log](../artifacts/v21-review-2026-10-26/workstation_viewer_e2e.js.log) | Viewer pass, có mocked clinical writes; không phải toàn bộ backend thật |
| [clinical_safety_e2e.js.log](../artifacts/v21-review-2026-10-26/clinical_safety_e2e.js.log) | 13 safety checks pass, synthetic fault injection |

Không có cơ sở kết luận “không còn bug”, “phần mềm hoàn tất 100%”, hoặc “chỉ cần thêm classifier weights là có thể chẩn đoán”. Các số pass là bằng chứng kiểm thử kỹ thuật theo snapshot và phạm vi ghi ở trên.
