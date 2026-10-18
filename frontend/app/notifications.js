import { state, role } from "./state.js";
import { request } from "./api.js";
import {
  $,
  $$,
  esc,
  pageHead,
  loading,
  errorBox,
  empty,
  button,
  toast,
} from "./ui.js";
export async function renderNotifications(root) {
  root.innerHTML =
    pageHead(
      "Thông báo",
      "Các thay đổi liên quan đến công việc của bạn.",
      button("Đánh dấu tất cả đã đọc", "read-all"),
    ) +
    `<div class="tabs"><button class="active" data-filter="all">Tất cả</button><button data-filter="unread">Chưa đọc</button></div><section class="panel" id="notificationsData">${loading()}</section>`;
  const target = $("#notificationsData", root);
  let filter = "all";
  try {
    const response = await request("/api/notifications");
    const rows = Array.isArray(response) ? response : response.items;
    if (!Array.isArray(rows))
      throw Error("Thông báo trả về không đúng hợp đồng.");
    if (!root.isConnected) return;
    for (const n of rows) {
      n.read = n.read ?? n.is_read ?? false;
      n.caseId = n.caseId ?? n.study_id;
    }
    const mark = async (ids) => {
      {
        await request("/api/notifications/read", {
          method: "POST",
          body: { ids },
        });
      }
      rows
        .filter((n) => ids.includes(n.id))
        .forEach((n) => {
          n.read = true;
          n.is_read = true;
        });
    };
    const draw = () => {
      const visible = rows.filter((n) => filter === "all" || !n.read);
      target.innerHTML = visible.length
        ? visible
            .map(
              (n) =>
                `<div class="list-row"><div><strong>${esc(n.title)}</strong><p class="muted">${esc(n.message)}</p><small class="muted">${esc(n.created_at || "")}</small></div><div class="actions">${n.caseId && role() !== "QT" ? `<a class="btn small" href="#case/${encodeURIComponent(n.caseId)}">Mở ca</a>` : ""}<button class="btn small" data-read="${esc(n.id)}" ${n.read ? "disabled" : ""}>${n.read ? "Đã đọc" : "Đánh dấu đã đọc"}</button></div></div>`,
            )
            .join("")
        : empty(
            "Không có thông báo mới",
            "Thông báo về ca bị từ chối và ca chờ duyệt sẽ xuất hiện ở đây.",
          );
      $$("[data-read]", root).forEach(
        (b) =>
          (b.onclick = async () => {
            try {
              await mark([b.dataset.read]);
              draw();
            } catch (e) {
              toast(e.message, true);
            }
          }),
      );
    };
    $$("[data-filter]", root).forEach(
      (b) =>
        (b.onclick = () => {
          filter = b.dataset.filter;
          $$("[data-filter]", root).forEach((v) =>
            v.classList.toggle("active", v === b),
          );
          draw();
        }),
    );
    $("[data-action=read-all]", root).onclick = async () => {
      try {
        await mark(rows.map((n) => n.id));
        draw();
      } catch (e) {
        toast(e.message, true);
      }
    };
    draw();
  } catch (e) {
    if (root.isConnected) {
      target.innerHTML = errorBox(e.message);
      $("[data-action=retry]", target).onclick = () =>
        renderNotifications(root);
    }
  }
}
