import { state } from "./state.js";
import { request } from "./api.js";

import {
  $,
  $$,
  esc,
  button,
  loading,
  errorBox,
  empty,
  csv,
  download,
  toast,
} from "./ui.js";
export async function renderAudit(target) {
  target.innerHTML = `<div class="banner info">Nhật ký chỉ đọc. Giao diện không có thao tác sửa hoặc xóa sự kiện.</div><div class="filters"><input name="q" type="search" aria-label="Tìm nhật ký" placeholder="Người dùng, hành vi, mã ca"><input name="actor" placeholder="Người thực hiện" aria-label="Người thực hiện"><select name="action" aria-label="Hành vi"><option value="">Mọi hành vi</option>${["LOGIN", "LOGIN_FAILED", "UPLOAD_IMAGE", "INFERENCE_RUN", "MASK_EDIT", "SIGN_PRELIM", "APPROVE", "REJECT", "LOCK", "UNLOCK", "EXPORT_REPORT", "ROLE_CHANGE"].map((v) => `<option>${v}</option>`).join("")}</select><label class="small">Từ <input name="from" type="date"></label><label class="small">Đến <input name="to" type="date"></label>${button("Xuất kết quả", "audit-export")}</div><section class="panel" id="auditRows">${loading()}</section>`;
  let page = 1,
    total = 0,
    rows = [],
    version = 0;
  const pageSize = 15;
  const filters = () =>
    Object.fromEntries(
      ["q", "actor", "action", "from", "to"].map((key) => [
        key,
        $(`[name=${key}]`, target).value,
      ]),
    );
  const load = async () => {
    const gen = ++version;
    const box = $("#auditRows", target);
    box.innerHTML = loading();
    try {
      {
        const data = await request(
          "/api/admin/audit-events?" +
            new URLSearchParams({ ...filters(), page, page_size: pageSize }),
        );
        if (!Array.isArray(data.items) || !Number.isInteger(data.total))
          throw Error("Nhật ký trả về không đúng contract phân trang.");
        rows = data.items;
        total = data.total;
      }
      if (!target.isConnected || gen !== version) return;
      box.innerHTML =
        (rows.length
          ? `<div class="table-wrap"><table><thead><tr><th>Thời gian</th><th>Người thực hiện</th><th>Hành vi</th><th>Đối tượng</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(r.timestamp)}</td><td>${esc(r.actor_id)}</td><td>${esc(r.action_type)}</td><td class="mono">${esc(r.entity_id)}</td></tr>`).join("")}</tbody></table></div>`
          : empty("Chưa có nhật ký phù hợp")) +
        `<div class="pagination"><span>${total} bản ghi · Trang ${page}/${Math.max(1, Math.ceil(total / pageSize))}</span><div class="actions"><button id="auditPrev" class="btn" ${page <= 1 ? "disabled" : ""}>Trước</button><button id="auditNext" class="btn" ${page * pageSize >= total ? "disabled" : ""}>Sau</button></div></div>`;
      $("#auditPrev", target).onclick = () => {
        page--;
        load();
      };
      $("#auditNext", target).onclick = () => {
        page++;
        load();
      };
    } catch (e) {
      if (target.isConnected && gen === version) {
        box.innerHTML = errorBox(e.message);
        $("[data-action=retry]", box).onclick = load;
      }
    }
  };
  let timer;
  $$("input,select", target).forEach(
    (e) =>
      (e.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          page = 1;
          load();
        }, 200);
      }),
  );
  $("[data-action=audit-export]", target).onclick = async () => {
    try {
      const data = (
        await request(
          "/api/admin/audit-events/export?" + new URLSearchParams(filters()),
        )
      ).items;
      download(
        "audit-trail.csv",
        csv([
          ["Thời gian", "Người", "Hành vi", "Đối tượng"],
          ...data.map((r) => [
            r.timestamp,
            r.actor_id,
            r.action_type,
            r.entity_id,
          ]),
        ]),
      );
    } catch (e) {
      toast(e.message, true);
    }
  };
  await load();
  return () => clearTimeout(timer);
}
