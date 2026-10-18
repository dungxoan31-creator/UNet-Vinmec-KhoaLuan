import { state, preferences } from "./state.js";
import { request } from "./api.js";
import { $, esc, field, pageHead, button, modal, toast } from "./ui.js";
import { startTour } from "./onboarding.js";
export const shortcuts = [
  ["1 / 2 / 3", "Ảnh gốc / mask / lớp phủ"],
  ["Space (giữ)", "Xem tạm ảnh gốc"],
  ["C", "Đổi chế độ đối chiếu"],
  ["K", "Đường viền / lớp phủ"],
  ["F", "Toàn màn hình"],
  ["B / E / L", "Cọ / tẩy / đa giác (nhấp đúp để hoàn tất)"],
  ["X", "Đổi cọ và tẩy"],
  ["[ / ] hoặc Alt + cuộn", "Đổi cỡ cọ"],
  ["H / chuột giữa", "Di chuyển ảnh"],
  ["← / →", "Chuyển bên trái / phải"],
  ["S", "Làm trơn mask"],
  ["R / Shift + R", "Khôi phục AI / xóa mask (có xác nhận)"],
  ["Ctrl + Z / Ctrl + Y", "Hoàn tác / làm lại"],
  ["Ctrl + Enter", "Ký sơ bộ khi đã xem hai bên"],
  ["N / P", "Ca kế tiếp / trước trong hàng chờ"],
  ["Ctrl + K", "Tìm nhanh"],
  ["?", "Bảng phím tắt"],
];
export function renderPersonal(root, route) {
  if (route === "profile") {
    root.innerHTML =
      pageHead(
        "Hồ sơ cá nhân",
        "Thông tin tài khoản được đơn vị quản trị cấp.",
      ) +
      `<section class="panel"><div class="panel-body" style="max-width:560px">${field("Tên hiển thị", "full_name", "text", state.user.full_name, "readonly")}${field("Tài khoản", "username", "text", state.user.username, "readonly")}${field("Khoa", "department", "text", state.user.department, "readonly")}${button("Đổi mật khẩu", "change-password")}</div></section>`;
    $("[data-action=change-password]").onclick = () =>
      modal(
        "Đổi mật khẩu",
        field(
          "Mật khẩu hiện tại",
          "current_password",
          "password",
          "",
          'required autocomplete="current-password"',
        ) +
          field(
            "Mật khẩu mới",
            "new_password",
            "password",
            "",
            'required minlength="10" autocomplete="new-password"',
          ) +
          field(
            "Nhập lại mật khẩu mới",
            "confirmation",
            "password",
            "",
            'required autocomplete="new-password"',
          ) +
          '<button type="submit" class="btn primary">Đổi mật khẩu</button>',
        async (e, d) => {
          const data = Object.fromEntries(new FormData(e.target));
          data.old_password = data.current_password;
          if (data.new_password !== data.confirmation)
            return toast("Mật khẩu xác nhận không trùng.", true);
          try {
            await request("/api/auth/change-password", {
              method: "POST",
              body: data,
            });
            d.close();
            toast("Đã đổi mật khẩu.");
          } catch (err) {
            toast(err.message, true);
          }
        },
      );
  } else if (route === "preferences") {
    root.innerHTML =
      pageHead("Tùy chọn", "Lưu riêng trên thiết bị này.") +
      `<section class="panel"><form id="preferencesForm" class="panel-body" style="max-width:560px"><label class="field">Giao diện<select name="theme"><option value="system">Theo màn hình: quản lý sáng, workstation tối</option><option value="light">Sáng</option><option value="dark">Tối</option></select></label><label class="field">Ngôn ngữ<select name="language"><option value="vi">Tiếng Việt</option><option value="en">English – điều hướng</option></select></label><label class="field">Bố cục viewer<select name="layout"><option value="single">Một ảnh</option><option value="side">Song song với ảnh gốc</option></select></label><button class="btn primary" type="submit">Lưu tùy chọn</button></form></section>`;
    for (const key of ["theme", "language", "layout"])
      $(`[name=${key}]`).value = state.preferences[key];
    $("#preferencesForm").onsubmit = (e) => {
      e.preventDefault();
      preferences(Object.fromEntries(new FormData(e.target)));
      window.dispatchEvent(new Event("ova:rerender"));
      toast("Đã lưu tùy chọn.");
    };
  } else {
    root.innerHTML =
      pageHead(
        "Trợ giúp và phím tắt",
        "Hướng dẫn sử dụng hệ thống.",
        button("Hướng dẫn nhanh", "start-tour") +
          button("Gửi góp ý", "feedback"),
      ) +
      `<div class="two-col"><section class="panel"><div class="panel-head"><h2>Bắt đầu một khảo sát</h2></div><div class="panel-body"><div class="help-step"><h3>1. Chuẩn bị ảnh</h3><p>Sử dụng ảnh đã ẩn danh. Chọn riêng ảnh trái và phải, mỗi ảnh không quá 20 MB.</p></div><div class="help-step"><h3>2. Rà soát cả hai bên</h3><p>Dùng đường viền để quan sát; giữ Space để xem ảnh gốc. Chuyển bên bằng phím mũi tên.</p></div><div class="help-step"><h3>3. Kiểm tra thước đo</h3><p>Khi thiếu hiệu chuẩn, số đo chỉ có pixel. Không suy ra mm từ kích thước ảnh.</p></div><div class="help-step"><h3>4. Lưu và chuyển duyệt</h3><p>Ctrl+Enter mở bản tóm tắt. Chuyên gia duyệt độc lập trước khi khóa ca.</p></div><p class="muted small">Hỗ trợ phân đoạn siêu âm buồng trứng</p></div></section><section class="panel"><div class="panel-head"><h2>Phím tắt workstation</h2></div><div class="table-wrap"><table class="shortcut-table"><tbody>${shortcuts.map(([k, v]) => `<tr><td><kbd>${esc(k)}</kbd></td><td>${v}</td></tr>`).join("")}</tbody></table></div></section></div>`;
    $("[data-action=start-tour]").onclick = startTour;
    $("[data-action=feedback]").onclick = () =>
      modal(
        "Báo lỗi / góp ý",
        field("Tiêu đề", "title", "text", "", "required") +
          '<label class="field">Mô tả<textarea name="message" required></textarea></label><p class="small muted">Không gửi thông tin định danh bệnh nhân.</p><button class="btn primary" type="submit">Gửi góp ý</button>',
        async (e, d) => {
          try {
            {
              await request("/api/feedback", {
                method: "POST",
                body: Object.fromEntries(new FormData(e.target)),
              });
            }
            d.close();
          } catch (err) {
            toast(err.message, true);
          }
        },
      );
  }
}
