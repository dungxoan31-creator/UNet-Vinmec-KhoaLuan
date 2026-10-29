# Hợp đồng đề xuất: định danh vùng trong một ảnh nghiên cứu

Trạng thái: đã có API liệt kê component, lưu xác nhận vùng hình học và đề xuất đối chiếu chỉ đọc; chưa có UI xác nhận hoặc liên kết CDSS. Không dùng kết quả dưới đây như danh tính lâm sàng.

## Ranh giới

- Một ảnh có thể chứa nhiều vùng mask; một tổn thương có thể xuất hiện trên nhiều ảnh. Không suy ra quan hệ xuyên ảnh từ vị trí hay hình dạng.
- `lesion_id` hiện do OpenCV sắp theo diện tích và chỉ có giá trị trong một kết quả đo. Nó không ổn định khi diện tích đổi và không được lưu như khóa lâm sàng.
- Đồng nhất phân tích connected-component theo liên thông 8 hướng, cùng OpenCV. Một pixel chạm góc có thể gộp hai vùng, do đó kết quả hình học chỉ là gợi ý cần người đọc kiểm tra.
- Không tự suy luận phân loại mô, số nang noãn, nguy cơ hoặc O-RADS từ component. Review cũ cấp ảnh giữ nguyên; không backfill tự động sang tổn thương lớn nhất.

## Đối chiếu đề xuất

`propose_component_links(previous_masks, current_mask)` chỉ so các mask thuộc cùng một ảnh và cùng hệ tọa độ. Đầu vào phải do lớp dịch vụ kiểm tra study/image/revision trước khi gọi; hàm thuần không xác minh quyền. Mask trước phải rời nhau, không rỗng và cùng kích thước. Mỗi component của mask hiện tại được cấp **index tạm**.

- Một component giao với đúng một vùng cũ và vùng cũ chỉ giao với component đó: gợi ý một-một; vẫn cần bác sĩ xác nhận, kể cả chỉ giao một pixel.
- Vùng cũ giao nhiều component: tách; tất cả nhánh là mơ hồ.
- Component giao nhiều vùng cũ: gộp; không chọn vùng có diện tích lớn nhất.
- Vùng cũ không giao component nào: báo thiếu; component mới không giao vùng cũ: báo mới. Không tự khẳng định tổn thương biến mất hoặc liên kết bằng vị trí.
- Chặn đầu vào sai shape/không nhị phân/vùng cũ chồng nhau/vượt giới hạn. Không bỏ im lặng các vùng nhỏ.

## Bước triển khai tiếp theo

1. API chỉ đọc theo ca/ảnh/review trả component index tạm, seed, bounding box, pixel count và SHA-256 của mask; reject tham chiếu sai và mask lỗi. API đề xuất liên kết chỉ so snapshot cùng ảnh với review mới nhất, không tự lưu ID. Snapshot thiếu phiên bản, geometry hoặc hash không khớp bị từ chối; không backfill lịch sử.
2. API xác nhận riêng có lease, revision, idempotency, server cấp UUID, lưu phiên bản thuật toán và geometry tham chiếu tới mask review bất biến. ID cũ không được liên kết phải được bác sĩ chỉ rõ trong `retired_region_ids`; đây là kết thúc liên kết hình học, không khẳng định tổn thương đã biến mất. Snapshot cũ thiếu bằng chứng phiên bản không được tự phục hồi hoặc chuyển ID. Chưa có giao diện khôi phục, caliper riêng theo vùng hoặc gắn giao dịch này vào review.
3. Phân biệt chưa liên kết, đã xác nhận, đã thay thế/ngừng theo dõi. Với tách/gộp, yêu cầu bác sĩ chỉ rõ quan hệ; không chuyển mô tả và kết quả CDSS âm thầm.
4. Schema/migration additive, test FK/cascade/xóa ca/rollback, dữ liệu cũ không thay đổi. Test hai bác sĩ, stale revision, mất ACK sau commit, sửa lại mask, thay thứ tự và crossing.
5. Viewer phải liệt kê tất cả vùng, kể cả dưới ngưỡng, và hỗ trợ hai bộ caliper độc lập. Chưa đánh giá một vùng thì trạng thái tổng hợp phải giữ chưa đầy đủ. Report và CDSS dùng snapshot cùng revision.

Để tránh ngộ nhận: các API mới chưa được nối vào UI, caliper hoặc CDSS; T07 chưa hoàn tất và ứng dụng chưa hỗ trợ đầy đủ nhiều tổn thương. ID vùng chỉ mô tả quan hệ hình học được xác nhận, không xác thực bản chất tổn thương.
