## 5. UI/UX friction và nội dung

1. **Intake/patient modal:** năm field editable bắt buộc cộng gender selection và optional ID trong danh bạ không nối server. CTA nằm dưới mép modal ở 1440×900, phải cuộn; chưa kết luận không thể submit vì Playwright auto-scroll đã thực hiện được. Nhãn không nói rõ local-only, trong khi toast khẳng định đã tạo hồ sơ. AUD-004/011.
2. **Upload:** banner định danh lặp PID trong field read-only, có thêm “Tạo Visit” trước nút phân tích, privacy disclosure, hai dropzone và stepper. Thanh sticky che vùng cần thao tác ở màn thấp; mobile date bị co. Không đề nghị bỏ disclosure an toàn. Có thể gom thông tin định danh và giải thích chính xác khi nào phải tạo Visit; chưa đo lợi ích số click của phương án thay thế. AUD-012/013/014.
3. **Patient list mobile:** tên gần như xếp dọc từng ký tự, action buttons chiếm không gian. Đây là lỗi readability cụ thể, không phải kết luận từ code. AUD-015.
4. **Viewer:** canvas dark lớn, phân biệt Trái/Phải và nội dung bác sĩ/AI có ý nghĩa; chỉ số và toolbar compact. Panel bên phải dài hơn viewport, notes/save cần cuộn ở một số state. Thông báo lưu hai bên sai đối với ca một bên; network toast tiếng Anh. AUD-022/023. Không có claim tất cả icon/tooltips đều được kích hoạt.
5. **Report:** PID vỡ dòng; trang đầu dành nhiều chỗ cho model/hash/UUID và giải thích, nhận định ở trang 2. Mất lý do không có ảnh bên phải. AUD-016/018/025. Giữ RUO và confirmation status; đề xuất giảm technical noise chỉ áp dụng thông tin không cần cho quyết định tức thời.
6. **Admin analytics:** heading dài/mixed English, nhiều card/legend; lỗi quan trọng hơn thẩm mỹ là null biến thành 0 và ranges lâm sàng khác viewer. Chart rows không native keyboard controls. AUD-019/020/021. Không lấy “Failed to fetch” ở admin-system làm lỗi server: audit cố ý chặn backup list vì constructor có thể tạo thư mục backup ngoài sandbox.

### Phân loại text đã xác minh

| Nhóm | Ví dụ cụ thể | Finding |
|---|---|---|
| Misleading information | Đã tạo hồ sơ bệnh nhân khi chỉ localStorage | AUD-004 |
| Missing context | PID nguồn và SYN cùng gọi PID | AUD-012 |
| Clinically inconsistent communication | <30 mm so với ≤30 mm, 1–9% so với 1–<10% | AUD-020 |
| Unnecessary technical detail / placement | Checkpoint SHA-256 ở trang đầu phiếu | AUD-018 |
| Incorrect confirmation scope | Đã lưu rà soát của hai bên với case chỉ trái | AUD-022 |
| Unclear wording / untranslated error | Failed to fetch | AUD-023 |
| Duplicated information | PID trong banner và field; repeated report explanations | UX opportunity, chưa tính lỗi riêng |

Không kết luận toàn bộ string catalog đã được review thủ công từng biến thể. DOM text/controls của các captures được lưu; hidden states, locale English đầy đủ, tooltips chỉ hiện hover và mọi validation message vẫn PARTIALLY TESTED.


See [full report](REPORT.md) and [complete issue register](ISSUE_REGISTER.md) for evidence, priorities and limitations.
