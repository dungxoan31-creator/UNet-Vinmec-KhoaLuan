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
export async function renderDepartments(target) {
  const response = await request("/api/admin/departments"),
    rows = Array.isArray(response) ? response : response.items;
  const draw = () => {
    target.innerHTML =
      button("Thêm khoa / phòng", "add-dept", "primary") +
      `<section class="panel" style="margin-top:20px">${rows.map((d) => `<div class="list-row"><div><strong>${esc(d.name)}</strong><p class="muted">Mã ${esc(d.id)} · ${d.members ?? "—"} thành viên</p></div><div class="actions"><button class="btn small" data-edit-dept="${esc(d.id)}">Chỉnh sửa</button><button class="btn small danger" data-delete-dept="${esc(d.id)}">Xóa khoa</button></div></div>`).join("") || empty()}</section>`;
    const edit = (d) =>
      modal(
        d ? "Chỉnh sửa khoa" : "Thêm khoa / phòng",
        field(
          "Mã khoa",
          "id",
          "text",
          d?.id || "",
          d ? "readonly" : "required",
        ) +
          field("Tên khoa", "name", "text", d?.name || "", "required") +
          '<button class="btn primary" type="submit">Lưu</button>',
        async (e, dialog) => {
          try {
            const body = Object.fromEntries(new FormData(e.target));
            {
              await request(
                "/api/admin/departments" +
                  (d ? "/" + encodeURIComponent(d.id) : ""),
                { method: d ? "PATCH" : "POST", body },
              );
            }
            dialog.close();
            {
              window.dispatchEvent(new CustomEvent("ova:rerender"));
            }
          } catch (e) {
            toast(e.message, true);
          }
        },
      );
    $("[data-action=add-dept]", target).onclick = () => edit(null);
    $$("[data-edit-dept]", target).forEach(
      (b) =>
        (b.onclick = () => edit(rows.find((d) => d.id === b.dataset.editDept))),
    );
    $$("[data-delete-dept]", target).forEach(
      (b) =>
        (b.onclick = async () => {
          const d = rows.find((d) => d.id === b.dataset.deleteDept);
          if (!(await confirmAction("Xóa khoa / phòng?", d.name))) return;
          try {
            {
              await request(
                "/api/admin/departments/" + encodeURIComponent(d.id),
                { method: "DELETE" },
              );
            }
            {
              window.dispatchEvent(new CustomEvent("ova:rerender"));
            }
          } catch (e) {
            toast(e.message, true);
          }
        }),
    );
  };
  draw();
}
