# Kiểm tra thủ công các phần tử axe từng đánh dấu incomplete

Ảnh là fixture tổng hợp. Axe ban đầu không tính được nền do các nhãn phủ trên canvas và dùng nền trong suốt. Các tỷ lệ trước dưới đây là khoảng tính toán khi giả định điểm ảnh bên dưới biến thiên từ đen đến trắng; không phải số đo cho mọi ảnh. Công thức WCAG dùng sRGB và alpha blending.

| Phần tử | Màu chữ | Nền trước | Tỷ lệ ước lượng trước | Xử lý và tỷ lệ sau |
|---|---|---|---|---|
| `#sideLabel` | `#38bdf8` | `rgba(15,23,42,0.8)` trên ảnh | 4,45:1–8,69:1 | Nền đặc `#0f172a`, 8,33:1 |
| Nhãn d₁ | `#a3b3c2` | `rgba(15,23,42,0.88)` trên ảnh | 5,90:1–8,54:1 | Nền đặc `#0f172a`, 8,32:1 |
| Nhãn d₂ | `#a3b3c2` | `rgba(15,23,42,0.88)` trên ảnh | 5,90:1–8,54:1 | Nền đặc `#0f172a`, 8,32:1 |
| Nhãn Diện tích | `#a3b3c2` | `rgba(15,23,42,0.88)` trên ảnh | 5,90:1–8,54:1 | Nền đặc `#0f172a`, 8,32:1 |
| `#d1` | `#38bdf8` | `rgba(15,23,42,0.88)` trên ảnh | 5,91:1–8,55:1 | Nền đặc `#0f172a`, 8,33:1 |
| `#d2` | `#38bdf8` | `rgba(15,23,42,0.88)` trên ảnh | 5,91:1–8,55:1 | Nền đặc `#0f172a`, 8,33:1 |
| `#area` | `#38bdf8` | `rgba(15,23,42,0.88)` trên ảnh | 5,91:1–8,55:1 | Nền đặc `#0f172a`, 8,33:1 |

Đề xuất: giữ nền đặc khi nhãn phủ ảnh và xác minh lại nếu đổi màu hoặc thêm trạng thái. Tỷ lệ không đánh giá độ nhìn thấy đường caliper trên toàn bộ hình ảnh lâm sàng.
