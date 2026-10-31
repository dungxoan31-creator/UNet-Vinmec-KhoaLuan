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

const activeRoles = ["BS", "QT"];

export function showCredentialHandover(username, tempPassword) {
  const content = `
    <div class="credential-handover">
      <p class="muted">Vui lòng sao chép và bàn giao thông tin đăng nhập này cho người dùng. Mật khẩu khởi tạo chỉ hiển thị <strong>một lần duy nhất</strong>.</p>
      <div style="background:var(--color-surface-elevated, #1a2234);padding:1rem;border-radius:6px;margin:1rem 0;border:1px solid var(--color-border,#2e3b52);">
        <p style="margin:0 0 0.5rem 0;"><strong>Tên đăng nhập:</strong> <code style="user-select:all;color:var(--color-primary,#38bdf8);">${esc(username)}</code></p>
        <p style="margin:0;"><strong>Mật khẩu khởi tạo:</strong> <code id="tempPasswordCode" style="user-select:all;font-size:1.15em;font-weight:bold;color:var(--color-accent,#f59e0b);">${esc(tempPassword)}</code></p>
      </div>
      <p class="small text-warning" style="color:var(--color-warning,#f59e0b);margin-bottom:1rem;">Người dùng bắt buộc phải đổi mật khẩu ngay trong lần đăng nhập đầu tiên.</p>
      <div class="actions">
        <button type="button" class="btn" id="copyCredentialBtn">Sao chép thông tin</button>
        <button type="button" class="btn primary" value="cancel">Đã bàn giao & Đóng</button>
      </div>
    </div>
  `;
  const d = modal("Bàn giao thông tin đăng nhập", content);
  const copyBtn = d.querySelector("#copyCredentialBtn");
  if (copyBtn) {
    copyBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText(`Tài khoản: ${username}\nMật khẩu: ${tempPassword}`);
        toast("Đã sao chép tài khoản và mật khẩu vào clipboard.");
      } catch {
        toast("Không thể tự động sao chép. Vui lòng bôi đen để copy.", true);
      }
    };
  }
  return d;
}

export async function renderUsers(target) {
  const response = await request("/api/auth/users");
  const rows = Array.isArray(response) ? response : response.items;
  const reload = () => window.dispatchEvent(new CustomEvent("ova:rerender"));
  let query = "";
  function draw() {
    target.innerHTML = `<div class="filters"><input id="userSearch" type="search" value="${esc(query)}" placeholder="Tìm tài khoản" aria-label="Tìm tài khoản">${button("Thêm người dùng", "add-user", "primary")}</div><section class="panel"><p class="admin-users-scroll-hint" id="adminUsersScrollHint">Cuộn ngang để xem trạng thái và thao tác.</p><div class="table-wrap admin-users-table" role="region" aria-label="Danh sách người dùng" aria-describedby="adminUsersScrollHint" tabindex="0"><table><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Khoa</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${rows
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
    const selectedRole =
      ({ DOCTOR: "BS", BS: "BS", ADMIN: "QT", QT: "QT" })[user?.role] ?? "";
    const roleOptions = `${user && !selectedRole ? `<option value="" selected>Vai trò hiện tại (${esc(user.role || "chưa xác định")}); giữ nguyên</option>` : ""}${activeRoles
      .map(
        (r) =>
          `<option value="${r}" ${r === selectedRole ? "selected" : ""}>${r}</option>`,
      )
      .join("")}`;
    const dialog = modal(
      user ? "Cập nhật người dùng" : "Thêm người dùng",
      field(
        "Tên đăng nhập",
        "username",
        "text",
        user?.username || "",
        'required maxlength="50"',
      ) +
        field(
          "Tên hiển thị",
          "full_name",
          "text",
          user?.full_name || "",
          'required maxlength="100"',
        ) +
        `<label class="field">Vai trò<select name="role">${roleOptions}</select></label>` +
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
          if (body.role === "") delete body.role;
          if (!body.username || !body.full_name || !body.department)
            throw Error("Nhập đủ thông tin người dùng.");
          if (user?.id === state.user.id && body.role !== "QT")
            throw Error("Không tự hạ quyền tài khoản đang quản trị.");
          const res = await request(
            "/api/admin/users" +
              (user ? "/" + encodeURIComponent(user.id) : ""),
            { method: user ? "PATCH" : "POST", body },
          );
          d.close();
          if (res?.temp_password) {
            showCredentialHandover(res.username || body.username, res.temp_password);
          }
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
      const res = await request(
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
            : action === "reset"
              ? { body: { new_password: null } }
              : {}),
        },
      );
      if (action === "reset" && res?.temp_password) {
        showCredentialHandover(user.username, res.temp_password);
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
