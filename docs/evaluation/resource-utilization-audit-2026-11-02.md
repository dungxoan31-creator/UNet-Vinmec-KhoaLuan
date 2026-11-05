# Kiểm kê tài nguyên, tích hợp và xác minh — 02–03/11/2026

## Kết luận và phạm vi

Đã triển khai các sửa đổi trực tiếp cho đường suy luận, phân loại, đo đạc, đóng
gói runtime và giao diện. Không tự động kích hoạt các adapter mô hình chỉ có tên
hoặc prototype. Không có bằng chứng để công bố hệ thống sẵn sàng sử dụng lâm sàng.

Worktree đã có nhiều thay đổi trước khi bắt đầu. Báo cáo này chỉ nhận các thay đổi
và kết quả được mô tả dưới đây; không nhận toàn bộ dirty diff là sản phẩm của lượt
audit này. Không reset, xóa checkpoint, thay model segmentation đã chọn hay triển
khai lên môi trường thật.

**Trạng thái full regression:** 1.583/1.583 Python đạt ở lượt đầy đủ cuối. Các
kiểm tra package/driver và thay đổi cơ học cuối được chạy bổ sung riêng; chi tiết
phạm vi ở bảng minh chứng. E2E roundtrip và E2E tích hợp đạt, không có page errors.

- [VERIFIED — local] Inventory tự động: 250 file nguồn/cấu hình, 120 khai báo
  route, 41 file checkpoint. Số dòng và SHA-256 từng file nằm trong artifact.
- 34 dependency trực tiếp được khai báo sau khi bổ sung manifest cho driver
  PostgreSQL vốn đã cài trên máy. Có dependency phục vụ CLI, plugin hoặc nghiên
  cứu; không có direct import không đồng nghĩa với không được sử dụng.
- Graph import/asset xác định các đường nối tĩnh; không chứng minh mọi nhánh có
  thể chạy. Router prefix, import động và điều kiện runtime cần kiểm tra riêng.
- Phạm vi inventory là backend, frontend, pipeline nghiên cứu/evaluation, script
  và cấu hình deploy. Không nhận là đã đọc thủ công mọi dòng trong kho external,
  tài liệu lịch sử, dữ liệu nhị phân hoặc toàn bộ dependency bên thứ ba.

Inventory tái tạo bằng `python scripts/audit_resource_utilization.py`:
[resource_inventory.json](../../artifacts/resource_audit/resource_inventory.json).
Các cờ `runtime_verified: false` trong inventory được giữ nguyên có chủ ý; bảng
subsystem dưới đây mới ghi nhận phần đã xác minh thực nghiệm.

## Phân loại tài nguyên và quyết định

Mã nhóm: **1** đang dùng và có kiểm thử; **2** dùng chưa hết; **3** ngoài workflow
chính; **4** chưa hoàn chỉnh/ngắt kết nối; **5** trùng/lỗi thời; **6** có tiềm năng
nhưng cần đánh giá. Nhóm 1 không có nghĩa mọi nhánh đã được kiểm thử hoặc đã được
chấp thuận lâm sàng.

| Tài nguyên | Nhóm | Bằng chứng/quyết định |
|---|---|---|
| `model_service.py`, `inference_engine.py`, manifest segmentation | 1 | Checkpoint chính được kiểm tra hash; API và E2E chạy thật. Giữ Letterbox 512×512 và cấu hình đã chọn. |
| Hai classifier ResNet34 và hai lần gọi trong một prediction | 2, 5 → 1 | Hợp nhất vào `ResearchImageClassifier`; facade tương thích cho CLI/mask. API phân loại ảnh nguồn đúng một lần. |
| Schema nhãn MMOTU trong thư mục training | 4 → 1 | Chuyển quyền sở hữu sang `backend/core/mmotu_labels.py`; training re-export cùng tuple, giữ nguyên thứ tự 8 lớp. |
| Lee/SRAD và các tiện ích enhancement trong `scripts/` | 2, 4 → 1/2 | Đưa implementation dùng chung vào backend; script giữ CLI/re-export. Package runtime không còn cần thư mục scripts để lọc ảnh. |
| Caliper inpainting | 6 | Không kích hoạt trong serving. Chưa có đối chứng đủ để chứng minh không xóa cấu trúc ảnh cần đọc. |
| `preprocessor.py`, IQA, DICOM decode/metadata/calibration | 1, 2 | Giữ kiểm tra ảnh và calibration có provenance; không thay defaults tiền xử lý để tìm metric tốt hơn. |
| `source_measurements.py`, inverse letterbox, caliper engine | 1, 2 | Tái sử dụng cho CLI; `/classify` phục hồi mask viewer về tọa độ nguồn trước khi tính hình học. |
| Morphology extractor/watershed | 1, 6 | Có kiểm thử kỹ thuật; không diễn giải số vùng/nang hoặc hình học mask thành chẩn đoán. |
| Entropy/uncertainty overlay | 1, 2 | Luồng viewer có kiểm thử; đây là entropy pixel chưa hiệu chuẩn, không phải OOD detector hay xác suất bệnh đã kiểm định. |
| Canvas, mask tools, worker, undo/redo, revision-bound drafts | 1 | Viewer E2E kiểm tra thao tác và hình học; sửa mất trạng thái bản nháp và bảo vệ kết quả khi request đến muộn. |
| Nhập ca nghiên cứu không PID | 4 → 1 | Backend đã có khả năng lưu ca không patient; nối lại schema và đường UI riêng. API/SQLite giữ `patient_id: null`, không tạo PID thay thế. |
| Metadata proposal/autofill | 1, 2 | Giữ thông tin nguồn và quyền xác nhận; không tự ghi đè bối cảnh hoặc lựa chọn lâm sàng. |
| Lease, idempotency, reviews, region assignment/calipers | 1 | E2E dài chạy qua browser/API/SQLite, retry và reopen; cập nhật fixture để kiểm tra đúng hợp đồng mới. |
| CDSS/ADNEX và giao diện vùng | 1, 6 | Kết nối đã có, synthetic E2E đạt. Không thay quy tắc y khoa; không nhận kiểm thử synthetic là adjudication chuyên gia. |
| PDF lâm sàng, interactive prompt, research export bị khóa | 4 | Giữ khóa 501 khi thiếu workflow/chứng cứ cần thiết. Bản in RUO frontend là luồng riêng đã kiểm tra. |
| S4M, UltraSAM, DS2Net, SovaSeg, TinyUSFM, CSA-SegNet, MedSAM, MedNeXt adapters | 4, 6 | Chưa có native implementation/trọng số được nạp qua các adapter này. Bỏ metadata “đã nạp” chỉ dựa trên file tồn tại; chặn chọn chúng để chạy lại mô hình chính dưới tên khác. |
| Model-zoo benchmark và báo cáo so sánh cũ | 5 | Source chứa accuracy literal và toy networks. Thay generator bằng benchmark latency model thật; đánh dấu artifact/báo cáo cũ không phải bằng chứng accuracy. |
| `patients.js`, `worklist.js`, `patient-compare.js` | 3, 5 | Không có đường import từ navigation hiện tại trong graph; các luồng hiện hành nằm ở intake/cases/viewer. Giữ file để bảo toàn worktree, không tạo thêm màn hình trùng. |
| Training, losses, split/evaluation scripts | 3, 6 | Phục vụ nghiên cứu offline. Giữ baseline Combo Loss Dice+BCE; không huấn luyện lại hoặc tự quảng bá checkpoint khác. |
| nnU-Net/foundation-model prototypes, kho external | 3, 4, 6 | Giữ cô lập. Cần native weights, protocol đánh giá và xác minh quyền sử dụng trước khi tích hợp serving. |
| 41 checkpoint, nhiều trial/last/best | 6 | Inventory tên/kích thước không chứng minh tương thích. Chỉ hash checkpoint đang thực sự được sử dụng được kiểm tra trong đường chạy. |
| Email, notifications, corrections, admin, backup | 1, 2, 4 | Có source connections và regression tương ứng; SMTP ngoài máy, restore backup thật và toàn bộ tổ hợp môi trường chưa được xác minh trong lượt này. |
| PostgreSQL Compose/migration | 2, 4 | Bổ sung khai báo/pin `psycopg` và binary đã có trên máy; kiểm tra load dialect không mở kết nối. Chưa kiểm thử database PostgreSQL sống. |
| Docker, nginx/systemd, hai bản nginx config | 3, 4, 5 | Rà soát đóng gói; runtime-only subprocess đạt. Compose dùng nginx root; không tự thay cấu hình vận hành bằng bản deploy chưa chạy. Docker daemon hiện không khả dụng. |
| Script vá một lần và tài liệu nghiệm thu lịch sử | 3, 5 | Không đưa vào luồng sản phẩm. Giữ để truy vết; các tuyên bố model/metric không có bằng chứng được gắn correction. |

## Các thay đổi đã triển khai

### Phân loại và độ tin cậy AI

- Bộ nạp classifier dùng một snapshot kiểm tra SHA-256, `weights_only=True`,
  strict state dict, khóa có thời hạn và CPU dùng chung. Không còn tạo model mới
  với trọng số ngẫu nhiên rồi trả nhãn khi checkpoint thiếu/hỏng.
- Loại bỏ classifier chạy trên ảnh segmentation đã CLAHE/letterbox. Lần gọi duy
  nhất ở API dùng ảnh nguồn BGR và pipeline CLAHE/Letterbox 256/ImageNet khớp
  dataset training. Không crop ROI chưa được đối chứng, không dùng mask để tạo
  phân tầng nguy cơ.
- `ABSTAIN` không trả suggested label để áp dụng; `UNAVAILABLE` không sinh
  phân bố giả. Facade không biến tên lớp ảnh thành kết luận ác/lành tính.
- `server_pipeline_ms` bao gồm decode/classification; thêm `classification_ms`
  để phép đo không bỏ mất nhánh phân loại.
- Adapter chưa nạp không còn công bố threshold/checksum của model fallback.
  Model chưa triển khai trả 503, model key không tồn tại trả 422.

### Hình học, CLI và đóng gói

- Mask `/classify` phải là RLE viewer 512×512, được inverse-letterbox về nguồn.
  Reject mask rỗng về cấu trúc, sai shape, spacing không hữu hạn/không hợp lệ và
  field lạ; kiểm tra quyền cơ sở trước khi đọc ảnh.
- Phân biệt đường kính tương đương diện tích với kích thước lớn nhất của hộp
  xoay; không mặc định tỷ lệ 0,1 mm/pixel.
- CLI dùng decoder raster/DICOM chung, mask nguồn cùng kích thước, letterbox
  bảo toàn tỷ lệ, measurement service hiện có và checkpoint segmentation đã nạp.
- Package-only subprocess xác minh app import, schema nhãn và lọc Lee khi không
  có thư mục training/scripts. Không phải bằng chứng native Docker build.
- Thêm ignore cho hai tên file secret runtime; không đọc hoặc đưa giá trị secret
  vào artifact. Thêm pin driver PostgreSQL để dependency của Compose có thể được
  tái tạo từ requirements, không chỉ tình cờ có trên máy phát triển.

### Giảm thao tác và làm rõ giao diện

- Luồng ca không định danh bỏ yêu cầu tạo hồ sơ với 6 trường bắt buộc trước khi
  tải ảnh nghiên cứu. Vẫn giữ xác nhận bên, chất lượng ảnh và rà soát của bác sĩ.
- Viewer bỏ dropdown 9 tên model gây hiểu nhầm và nút lọc trùng; giữ một lựa chọn
  lọc ảnh đối chiếu, ghi rõ chỉ ảnh hưởng hiển thị. Không tự đưa Lee vào prediction.
- Thêm gợi ý AI bằng một thao tác trên nút sẵn có: append ghi chú có nhãn
  “RUO, chưa xác nhận”, giữ mô tả đã nhập, không lặp dòng và lưu draft qua cùng
  event handler nhập liệu. Không tự xác nhận ghi chú/O-RADS.
- Khóa chạy lại AI khi có draft đang sửa hoặc review đã lưu; kiểm tra lease,
  quyền sửa và busy state; gửi idempotency key, giải phóng bitmap.
- Request lọc ảnh đến muộn không được vẽ lên ảnh vừa chọn khác. Đổi ảnh hoặc chạy
  lại AI reset trạng thái bộ lọc tương ứng. E2E giữ chậm response để kiểm tra race.
- Cảnh báo draft chưa lưu giữ hiển thị sau reload/relogin; không phụ thuộc toast
  ngắn hạn. Các nội dung RUO và dữ liệu tổng hợp trên bản in được giữ.

## Kết quả đo được và giới hạn

### So sánh xử lý màu trên validation mức ảnh

[PARTIALLY VERIFIED — dataset provenance] Đã đọc trực tiếp 1.000 ảnh train và 469
ảnh validation theo các label file cục bộ; kiểm tra SHA-256 không trùng giữa hai
partition và validation không lặp nội dung. Chưa xác minh độc lập nguồn nhãn bằng
chuyên gia, quyền tái phân phối hay tính độc lập theo bệnh nhân.

So sánh dùng cùng checkpoint classifier. Nhánh cũ được tái tạo bằng cách diễn giải
BGR như RGB, tương ứng phép biến đổi màu trước đây; không phải phép so sánh toàn
bộ hệ thống trước/sau. Tập validation đã dùng để chọn checkpoint từ trước.

| Chỉ số | Xử lý màu cũ được tái tạo | Khớp training |
|---|---:|---:|
| Accuracy top-1 trên 469 ảnh | 0,678038 | 0,684435 |
| Macro-F1 trên toàn bộ ảnh | 0,599501 | 0,604389 |
| Có đề xuất / tổng số | 413/469 | 410/469 |
| Accuracy trong nhóm có đề xuất | 0,711864 | 0,721951 |
| Từ chối đề xuất | 56 | 59 |

10 ảnh đổi nhãn top-1; số dự đoán đúng tăng ròng 3 ảnh, tương đương khoảng 0,64
điểm phần trăm accuracy. Chưa kiểm định ý nghĩa thống kê. Không suy rộng thành độ
chính xác lâm sàng, xác suất mắc bệnh hoặc kết quả độc lập theo bệnh nhân.

[classifier_preprocessing_validation.json](../../artifacts/resource_audit/classifier_preprocessing_validation.json)
chứa confusion matrices, split audit, checkpoint hash và giới hạn phép so sánh.
Tái tạo bằng `python scripts/evaluate_classifier_preprocessing.py`.

### Chi phí thực thi và thao tác

- Số lần classifier forward mỗi request prediction giảm từ 2 xuống 1, được
  kiểm tra bằng spy trên pixel nguồn qua API thật. Không công bố tổng latency
  giảm 50% vì đường cũ dùng thiết bị và bước xử lý khác.
- Benchmark checkpoint segmentation thật: median **170,12 ms**, p95 **176,57 ms**,
  5 lần đo sau 1 warmup trên CUDA, đầu vào zero 1×1×512×512. Bao gồm TTA được chọn
  và chuyển kết quả về CPU. Không phải latency toàn API hay benchmark accuracy.
- Viewer giảm 2 điều khiển trùng/gây hiểu nhầm. Ghi chú AI cần 1 thao tác có chủ
  ý thay cho nhập lại nhãn; chưa có nghiên cứu đo thời gian thao tác trên người.

[segmentation_latency.json](../../artifacts/resource_audit/segmentation_latency.json)
được tạo bằng `python scripts/evaluate_model_zoo_benchmark.py --iterations 5`.

## Minh chứng kiểm thử

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Baseline toàn bộ Python | 1.522 đạt, 52 lỗi; lưu trước gói sửa chính. Một số module được import muộn khi worktree đang được sửa, nên không dùng lượt này làm snapshot hiệu năng. |
| Bộ tích hợp mở rộng | 128/128 đạt trước bước tách runtime package; package và full regression được chạy lại sau bước này. |
| Nhóm đóng gói, fixture DICOM/upload, preprocessing | 109/109 đạt. |
| Full Python cuối | **1.583 đạt, 0 lỗi**, 2 warning, 318,41 giây. Các fixture được sửa để đi tới assertion nghiệp vụ thay vì bị từ chối sớm bởi PID/IQA; không nới các ràng buộc này. |
| Package/driver cuối và kiểm tra sau cleanup cơ học | **21/21** và **30/30** đạt. Có một test driver được thêm sau khi full suite đã collection; không gộp các lần chạy thành một số coverage. |
| Node unit tests | 162/162 đạt ở lượt gần nhất; không phải E2E. |
| JavaScript syntax | 59 module đạt `node --check`; không phải static type analysis hoặc bundler build. |
| `resource_integration_e2e.js` | API thật với ảnh tổng hợp: ca không PID, upload, inference, rerun, giữ bản nháp; response lọc bị trì hoãn để kiểm tra đổi ảnh. Nhãn PREDICTED fixture chỉ dùng cho kiểm tra thao tác ghi chú. |
| `clinical_roundtrip_e2e.js` | Luồng thành công dùng backend/SQLite thật; lỗi mạng được fault-inject. Review, vùng, caliper, CDSS/ADNEX, reopen, bản in 3 trang và quyền in theo capability được kiểm tra. |
| `workstation_viewer_e2e.js` | 4 chiều rộng 1440/1024/768/390; 0 page errors, 28 clinical writes được mock, không thay cho bằng chứng persistence thật. |
| Computer Use | Quan sát cửa sổ Chrome kiểm thử và accessibility tree; chụp ảnh native. Một thao tác sau khi harness đã đóng Chrome không thực hiện được; không tính là kiểm thử thành công. |
| Design detector | `[]` cho các file UI đã sửa; không phải chứng nhận WCAG hoặc usability audit đầy đủ. |
| Docker | CLI có, daemon Linux không chạy; chưa có native image build/run. Package-boundary test là kiểm tra thay thế có giới hạn. |
| PostgreSQL | Import driver và tạo dialect không mở kết nối; chưa chứng minh CRUD/migration trên server thật. |

Logs: [full Python](../../artifacts/resource_audit_final_pytest.log),
[tích hợp](../../artifacts/resource_audit_integration_final.log),
[package](../../artifacts/resource_audit_package_final.log),
[E2E mới](../../artifacts/resource_audit_integration_e2e.log),
[roundtrip](../../artifacts/resource_audit_roundtrip.log),
[viewer](../../artifacts/resource_audit_workstation.log),
[Node](../../artifacts/resource_audit_node_final.log).

Ảnh: [desktop](../../artifacts/resource_audit/viewer-desktop.png),
[mobile](../../artifacts/resource_audit/viewer-mobile.png),
[Computer Use](../../artifacts/resource_audit/computer-use-viewer.png).

## Những phần chưa được giải quyết bằng bằng chứng hiện có

1. Independent test có label/provenance phù hợp; đánh giá bên ngoài, domain shift,
   calibration/OOD và đánh giá chuyên gia. Không tự thêm ensemble/model mới từ
   các con số model-zoo không có đối chứng.
2. Trọng số và native integration của các foundation-model adapters; kiểm định
   caliper inpainting, phép đo trên ảnh thực và các trường hợp sát ranh giới.
3. Native Docker runtime và PostgreSQL sống, SMTP thật, backup/restore vận hành.
4. Manifest segmentation hiện ghi AdvancedHybridLoss cho candidate đang chọn,
   trong khi baseline Combo Loss Dice+BCE vẫn được giữ trong code. Audit này
   không thay lịch sử huấn luyện hoặc tự retrain/promote để giải quyết khác biệt
   protocol đó; cần đối chiếu lại trước khi dùng kết quả cho khóa luận.
5. PDF lâm sàng, chữ ký/xác thực chuyên môn và xuất dữ liệu nghiên cứu vẫn giữ
   khóa thích hợp. Không coi bản in RUO là báo cáo lâm sàng đã duyệt.
6. Kiểm thử một số nhánh không đồng nghĩa phủ toàn bộ source, toàn bộ màn hình
   hay mọi tổ hợp cấu hình; các legacy modules và prototype chưa xác minh vẫn
   được đánh dấu trong inventory thay vì công bố “đã tích hợp tất cả”.
