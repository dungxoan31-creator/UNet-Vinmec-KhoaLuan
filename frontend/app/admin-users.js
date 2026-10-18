import { state } from "./state.js";
import { request } from "./api.js";

import {
  $,
  $$,
  esc,
  button,
  field,
  empty,
  modal,
  toast,
  confirmAction,
} from "./ui.js";

export async function renderUsers(target) {
  const response = await request("/api/auth/users");
  const rows = Array.isArray(response) ? response : response.items;
  const reload = () => window.dispatchEvent(new CustomEvent("ova:rerender"));
  let query = "";
  function draw() {
    target.innerHTML = `<div class="filters"><input id="userSearch" type="search" value="${esc(query)}" placeholder="Tìm tài khoản" aria-label="Tìm tài khoản">${button("Thêm người dùng", "add-user", "primary")}</div><section class="panel"><div class="table-wrap"><table><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Khoa</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${rows
      .filter((u) =>
        (u.username + " " + u.full_name)
          .toLowerCase()
          .includes(query.toLowerCase()),
      )
      .map(
        (u) =>
          `<tr><td><strong>${esc(u.full_name || u.username)}</strong><small>${esc(u.username)}</small></td><td>${esc(u.role)}</td><td>${esc(u.department || "Chưa phân khoa")}</td><td>${u.is_active ? "Đang hoạt động" : "Đã khóa"}</td><td><div class="actions"><button class="btn small" data-edit="${esc(u.id)}">Sửa quyền</button><button class="btn small" data-lock="${esc(u.id)}">${u.is_active ? "Khóa" : "Mở khóa"}</button><button class="btn small" data-reset="${esc(u.id)}">Đặt lại mật khẩu</button>${u.id !== state.user.id ? `<button class="btn small danger" data-delete="${esc(u.id)}">Xóa</button>` : ""}</div></td></tr>`,
      )
      .join(
        "",
      )}</tbody></table></div>${rows.length ? "" : empty("Chưa có tài khoản")}</section>`;
    $("#userSearch", target).oninput = (e) => {
      query = e.target.value;
      const start = e.target.selectionStart;
      draw();
      const input = $("#userSearch", target);
      input.focus();
      input.setSelectionRange(start, start);
    };
    $("[data-action=add-user]", target).onclick = () => edit();
    $$("[data-edit]", target).forEach(
      (b) =>
        (b.onclick = () =>
          edit(rows.find((u) => String(u.id) === b.dataset.edit))),
    );
    $$("[data-lock]", target).forEach(
      (b) =>
        (b.onclick = () =>
          change(
            b,
            rows.find((u) => String(u.id) === b.dataset.lock),
            "lock",
          )),
    );
    $$("[data-reset]", target).forEach(
      (b) =>
        (b.onclick = () =>
          change(
            b,
            rows.find((u) => String(u.id) === b.dataset.reset),
            "reset",
          )),
    );
    $$("[data-delete]", target).forEach(
      (b) =>
        (b.onclick = () =>
          change(
            b,
            rows.find((u) => String(u.id) === b.dataset.delete),
            "delete",
          )),
    );
  }
  function edit(user) {
    const dialog = modal(
      user ? "Cập nhật người dùng" : "Thêm người dùng",
      field(
        "Tên đăng nhập",
        "username",
        "text",
        user?.username || "",
        'required maxlength="64"',
      ) +
        field(
          "Tên hiển thị",
          "full_name",
          "text",
          user?.full_name || "",
          'required maxlength="100"',
        ) +
        `<label class="field">Vai trò<select name="role">${["BS", "TK", "QT"].map((r) => `<option ${r === user?.role ? "selected" : ""}>${r}</option>`).join("")}</select></label>` +
        field(
          "Khoa",
          "department",
          "text",
          user?.department || "",
          'required maxlength="100"',
        ) +
        '<p class="muted small">Máy chủ gửi quy trình thiết lập mật khẩu riêng; không hiển thị mật khẩu tại đây.</p><button class="btn primary" type="submit">Lưu</button>',
      async (e, d) => {
        const submit = e.submitter;
        if (submit.disabled) return;
        submit.disabled = true;
        try {
          const body = Object.fromEntries(new FormData(e.target));
          for (const key of Object.keys(body)) body[key] = body[key].trim();
          if (!body.username || !body.full_name || !body.department)
            throw Error("Nhập đủ thông tin người dùng.");
          if (user?.id === state.user.id && body.role !== "QT")
            throw Error("Không tự hạ quyền tài khoản đang quản trị.");
          {
            await request(
              "/api/admin/users" +
                (user ? "/" + encodeURIComponent(user.id) : ""),
              { method: user ? "PATCH" : "POST", body },
            );
          }
          d.close();
          reload();
        } catch (err) {
          toast(err.message, true);
        } finally {
          submit.disabled = false;
        }
      },
    );
    return dialog;
  }
  async function change(buttonNode, user, action) {
    if (user.id === state.user.id && action !== "reset")
      return toast("Không khóa hoặc xóa tài khoản đang sử dụng.", true);
    if (
      !(await confirmAction(
        {
          lock: "Thay đổi trạng thái tài khoản?",
          reset: "Đặt lại mật khẩu?",
          delete: "Xóa người dùng?",
        }[action],
        action === "delete"
          ? "Máy chủ phải bảo toàn tác giả và lịch sử thao tác. Tài khoản có tham chiếu có thể bị từ chối xóa."
          : user.username,
      ))
    )
      return;
    buttonNode.disabled = true;
    try {
      {
        await request(
          "/api/admin/users/" +
            encodeURIComponent(user.id) +
            (action === "reset" ? "/reset-password" : ""),
          {
            method:
              action === "delete"
                ? "DELETE"
                : action === "reset"
                  ? "POST"
                  : "PATCH",
            ...(action === "lock"
              ? { body: { is_active: !user.is_active } }
              : {}),
          },
        );
      }
      toast(
        action === "reset"
          ? "Đã ghi nhận yêu cầu đặt lại mật khẩu."
          : "Đã cập nhật tài khoản.",
      );
      reload();
    } catch (e) {
      toast(e.message, true);
      buttonNode.disabled = false;
    }
  }
  draw();
}
