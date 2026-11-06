## 4. Kết quả cross-layer và user flows

| Workflow | Thực thi / kết quả | Tương tác và thời gian thực đo | Hạn chế |
|---|---|---|---|
| Login doctor | Form → auth API → dashboard | 3 thao tác Playwright, 289 ms | Không tính thời gian người đọc/gõ hoặc cold startup |
| Tạo patient tổng hợp | Modal → local store → upload; phiên khác không thấy | 6 thao tác sau khi modal mở, 644 ms | Excludes thao tác mở modal, typing thực và clinical task time |
| Tạo ca một bên | POST cases tạo PID giả danh, visit_no 6 số, trạng thái PENDING | API latency trong probe-results.json; không đo click E2E | Không exercise nút Tạo Visit/reservation replay trong audit này |
| Multi-facility identity | Hai cơ sở tạo ca với PID 123456789 | API thực thi; cùng patient_id | Không có global identity agreement nên liên kết tự động không có căn cứ |
| Cross-facility case access | B doctor GET A case | 403 trong tenant-results.json | Không chứng minh toàn bộ endpoint đều scoped |
| Upload → inference | Synthetic 640×480 → upload → prediction → lưu | API latency thật trong probe-results.json | Mask rỗng; không kiểm tra diagnostic validity/nonempty-mask pixel alignment thực tế |
| Classification | Ảnh synthetic → classify | 200/ABSTAIN | Top scores chưa hiệu chuẩn, không phải disease probabilities |
| Calibration | POST spacing=0.1 → prediction measurements/provenance → GET case | 200; calibrated=true | Không có phantom vật lý/anisotropic DICOM test trong lượt này |
| Lưu review | Nhập morphology/note/O-RADS → batch review 200 → GET/reload | 4 thao tác, 174 ms trong lần hoàn tất | Thời gian automation, không phải thời gian hoàn thành examination |
| Network failure khi save | Abort request → Lưu không thành công → draft còn trong input | Không đo tổng thời gian | Toast tiếng Anh; retry/reconnect queue chưa exercise toàn bộ |
| Reopen review | Reload cùng tab giữ note/morphology/O-RADS | Đã quan sát values đúng | Không kiểm thử mọi interruption/multitab race |
| Report/print | Saved snapshot → nút in thật → 2 trang PDF | Có PDF/text/render; không đo completion time | Hệ điều hành/printer thật, 40 ảnh, long text page-break chưa chạy |
| Đổi mật khẩu | 200 nhưng request kế tiếp hết phiên; restart hồi password bootstrap | Không đo time-and-motion | Hai lỗi độc lập, AUD-006/007 |

`summary.json`, `deep-browser-results.json` và probe artifacts lưu số đo gốc. Không cộng ba số đo nhỏ thành thời gian một ca. Không có interaction count/time cho ca song phương hoàn chỉnh; ghi NOT TESTED thay vì ước lượng.

Điểm hoạt động đúng cần bảo toàn: missing CDSS descriptors trả INSUFFICIENT_DATA; unauthenticated case trả 401; scoped cross-facility case trả 403; review save/reopen giữ nội dung đã nhập; network error không báo thành công; O-RADS chưa được AI tự chèn trong probe; classifier có abstain; calibration provenance có history; báo cáo RUO tách cảnh báo và chứa saved note thay vì note chưa lưu. Không phục hồi “Chi tiết nâng cao”.


See [full report](REPORT.md) and [complete issue register](ISSUE_REGISTER.md) for evidence, priorities and limitations.
