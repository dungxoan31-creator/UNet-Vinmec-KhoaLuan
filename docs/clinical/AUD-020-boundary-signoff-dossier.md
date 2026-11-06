# AUD-020 — Hồ sơ đề nghị phê duyệt ngưỡng nang noãn 30 mm

**Trạng thái:** DRAFT — chờ bác sĩ chuyên khoa/giảng viên hướng dẫn phê duyệt.
**Phạm vi:** Quy tắc giới hạn kích thước trong CDSS nghiên cứu. Hồ sơ này không xác nhận hệ thống phù hợp chăm sóc người bệnh.

## Quyết định cần xin

Đề nghị người có thẩm quyền xác nhận có áp dụng mô tả nang noãn sinh lý tiền mãn kinh của ACR O-RADS US v2022 tại ngưỡng bao gồm 30,0 mm hay tiếp tục giữ policy nội bộ `<30 mm`. Đây là quyết định về biên kích thước, không phải phê duyệt tự động phân loại tổn thương hoặc phát hành báo cáo lâm sàng.

## Căn cứ đã đối chiếu

- **[VERIFIED] ACR O-RADS US v2022:** Bảng Assessment Categories mô tả nang sinh lý là nang noãn `≤3 cm` hoặc hoàng thể thường `≤3 cm`; hàng này thuộc O-RADS 1/ovary bình thường và ghi quản lý tiền mãn kinh “None”. [Nguồn PDF chính thức, phát hành tháng 11/2022](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/US-v2022/O-RADS--US-v2022-Assessment-Categories.pdf).
- **[VERIFIED] ACR O-RADS US v2022 Lexicon:** Định nghĩa nang noãn ở nhóm tiền mãn kinh là nang đơn giản, một thùy, trống âm, thành nhẵn, kích thước `≤3 cm`. [Nguồn PDF chính thức, bản sửa tháng 01/2023](https://cs.acr.org/-/media/ACR/Files/RADS/O-RADS/O-RADS-US-v2022-Lexicon-Terms-Table-2023.pdf).
- **[VERIFIED] IOTA Simple Rules:** Dùng năm đặc điểm siêu âm lành tính và năm đặc điểm ác tính để đánh giá khối phần phụ; một số ca không kết luận được theo quy tắc. Đây là bộ đặc điểm hình thái, không được dùng trong hồ sơ này như nguồn thay thế ngưỡng nang noãn của ACR. [Bài xác nhận tiến cứu của nhóm IOTA, BMJ 2010](https://www.bmj.com/content/341/bmj.c6839).
- **[VERIFIED] IOTA/ISUOG consensus:** Tài liệu đồng thuận chuẩn hóa thuật ngữ, định nghĩa và phép đo mô tả khối phần phụ. Hồ sơ này không suy diễn rằng đồng thuận IOTA/ISUOG đặt ra ngưỡng 30 mm. [Trang tài liệu chính thức ISUOG](https://www.isuog.org/resource/updated-consensus-opinion-on-the-terms-definitions-and-measurements-to-describe-the-sonographic-features-of-adnexal-tumors.html).

**Hiệu chỉnh nội dung kế hoạch:** Không dùng giả định “30 mm sinh lý = O-RADS 2” hoặc “không sinh lý = O-RADS 3 theo dõi 3–6 tháng”. Bảng ACR đặt nang noãn sinh lý `≤3 cm` trong O-RADS 1. Các tổn thương khác phải được phân tầng theo mô tả hình thái và ngữ cảnh áp dụng; riêng kích thước không đủ để gán O-RADS 3 hay lịch theo dõi.

## Hành vi hiện tại trong mã nguồn

`backend/services/cdss_engine.py` ghi policy `project-follicle-lt30-v3`, chỉ nhận `0 < diameter < 30 mm`. Fixture bác sĩ xác nhận nang noãn ở 29,9 mm trả `RULE_MATCHED`/O-RADS 1; đúng 30,0 mm trả `UNSUPPORTED_PATTERN` và chưa có category. Theo thông điệp trong engine, ngoài policy không đồng nghĩa bất thường hoặc ác tính.

Đối chiếu này không thay đổi logic hiện hành. Cờ `ENABLE_O_RADS_V2022_INCLUSIVE_30MM` chưa được khai báo hoặc nối vào runtime; đề xuất chỉ để tham khảo trong lần triển khai sau khi có hồ sơ phê duyệt đầy đủ, không phải một cấu hình đang hoạt động.

## Bảng quyết định kỹ thuật

| Kích thước fixture | Policy hiện hành | Mô tả ACR có thể áp dụng | Điều kiện để xem xét thay đổi |
|---:|---|---|---|
| 29,9 mm | Nang noãn được bác sĩ xác nhận: O-RADS 1 | Tiền mãn kinh, nang noãn `≤3 cm` | Tiếp tục giữ các điều kiện lâm sàng/hình thái hiện có |
| 30,0 mm | Chưa phân tầng theo policy nội bộ | Nằm đúng trong mô tả nang noãn tiền mãn kinh `≤3 cm` | Chỉ xem xét nới policy sau khi ký duyệt; không suy ra từ số đo AI |
| 30,1 mm | Chưa phân tầng như nang noãn theo fixture hiện tại | Vượt mô tả nang noãn sinh lý; cần mô tả tổn thương phù hợp | Đánh giá theo hình thái; không tự gán O-RADS 2/3 từ ngưỡng này |

Các dòng trên là **fixture tổng hợp**, không phải ca bệnh. Có thể tạo CSV đối chiếu bằng:

```powershell
.\.venv\Scripts\python.exe scripts\generate_boundary_comparison_report.py --output artifacts\aud020-boundary-comparison.csv
```

Script không đọc dữ liệu người bệnh và từ chối ghi đè file đích.

## Điều kiện an toàn trước khi sửa mã nguồn

1. Xác nhận văn bản ACR áp dụng cho ngữ cảnh dự án và đối tượng tiền mãn kinh.
2. Bác sĩ/giảng viên xác nhận cách diễn giải đúng 30,0 mm, cách đo và yêu cầu làm tròn.
3. Xác nhận không phân loại chỉ dựa vào số đo; các điều kiện bác sĩ xác nhận, siêu âm 2D đầy đủ, hình thái, tình trạng tiền mãn kinh và các đặc điểm bắt buộc tiếp tục có hiệu lực.
4. Ghi người phê duyệt, vai trò/chuyên môn, cơ sở/phạm vi, phiên bản policy, ngày hiệu lực và tài liệu tham chiếu.
5. Kiểm thử ranh giới 29,9 / 30,0 / 30,1 mm và trường hợp thiếu/sai ngữ cảnh; rà lại report, viewer, export, API và lịch sử lưu.

Cho đến khi các điều kiện này được đáp ứng, giữ nguyên `<30 mm`, không bật cờ chuyển đổi và không diễn giải `UNSUPPORTED_PATTERN` thành bệnh lý.

## Biểu mẫu ký duyệt — chưa ký

| Trường | Nội dung cần điền bởi người phê duyệt |
|---|---|
| Quyết định | ☐ Chấp thuận có điều kiện ngưỡng `≤30 mm`  ☐ Tiếp tục `<30 mm`  ☐ Yêu cầu sửa hồ sơ |
| Họ tên bác sĩ chuyên khoa | ______________________________________________ |
| Chuyên khoa/chức danh và căn cứ thẩm quyền | ______________________________________________ |
| Cơ sở/phạm vi áp dụng | ______________________________________________ |
| Họ tên giảng viên hướng dẫn (nếu áp dụng) | ______________________________________________ |
| Phiên bản policy và ngày hiệu lực | ______________________________________________ |
| Tài liệu đối chiếu/biên bản | ______________________________________________ |
| Chữ ký và ngày ký | ______________________________________________ |

**Tình trạng hiện tại:** chưa có chữ ký hoặc biên bản chuyên môn đính kèm; ngưỡng trong code vẫn là `<30 mm`; AUD-020 chưa được nâng thành VERIFIED.
