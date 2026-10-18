import { statusLabels } from "./i18n.js";
export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1",
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6",
  check: "m4 12 5 5L20 6",
  users:
    "M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3m18 0v-3a4 4 0 0 0-3-4M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8m8-7a4 4 0 0 1 0 7",
  chart: "M4 3v18h17M8 16v-4m5 4V7m5 9V4",
  settings: "M4 7h16M4 17h16M8 4v6m8 4v6",
  bell: "M18 8a6 6 0 0 0-12 0c0 8-3 8-3 10h18c0-2-3-2-3-10m-11 13h4",
  search: "M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14m5-2 6 6",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  close: "m6 6 12 12M6 18 18 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8m0-6v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2",
  brush: "m14 3 7 7-10 10H4v-7zm-7 7 7 7",
  erase: "m14 3 7 7-11 11H5l-4-4zm-7 7 7 7m-4 4h12",
  hand: "M8 12V5a2 2 0 0 1 4 0v6-8a2 2 0 0 1 4 0v8-6a2 2 0 0 1 4 0v11c0 4-3 6-6 6h-3c-2 0-3-1-4-3l-5-7a2 2 0 0 1 3-2l3 3",
  undo: "M4 9h10a7 7 0 0 1 0 14M4 9l5-5M4 9l5 5",
  eye: "M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12m10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  lock: "M5 10h14v12H5zm3 0V6a4 4 0 0 1 8 0v4",
  help: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20m-3-14a3 3 0 0 1 6 0c0 3-3 2-3 5m0 4h.01",
  file: "M4 2h10l6 6v14H4zm10 0v6h6M8 13h8m-8 4h8",
  warning: "m12 2 11 20H1zm0 7v5m0 4h.01",
  plus: "M12 4v16M4 12h16",
  fit: "M3 9V3h6m6 0h6v6M3 15v6h6m6 0h6v-6",
  polygon: "m4 4 16 2-3 15-15-4z",
  history: "M3 12a9 9 0 1 0 3-7L2 9m0-6v6h6m4-3v6l4 2",
};
export const icon = (name, size = 20) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
export const button = (text, action = "", kind = "", ico = "") =>
  `<button type="button" class="btn ${kind}" ${action ? `data-action="${esc(action)}"` : ""}>${ico ? icon(ico) : ""}${esc(text)}</button>`;
export const badge = (status) =>
  `<span class="badge status-${esc(status)}">${esc(statusLabels[status] || status)}</span>`;
export const field = (label, name, type = "text", value = "", extra = "") =>
  `<label class="field">${esc(label)}<input name="${esc(name)}" type="${type}" value="${esc(value)}" ${extra}></label>`;
export const pageHead = (title, description = "", actions = "") =>
  `<div class="page-heading"><div><p class="eyebrow">KHÔNG GIAN LÀM VIỆC</p><h1>${esc(title)}</h1>${description ? `<p class="muted">${esc(description)}</p>` : ""}</div><div class="actions">${actions}</div></div>`;
export const empty = (
  title = "Chưa có dữ liệu",
  detail = "Dữ liệu sẽ xuất hiện tại đây khi có bản ghi phù hợp.",
  action = "",
) =>
  `<div class="empty">${icon("file", 30)}<h2>${esc(title)}</h2><p>${esc(detail)}</p>${action}</div>`;
export const loading = () =>
  `<div class="skeletons" aria-busy="true" aria-label="Đang tải"><div></div><div></div><div></div></div>`;
export function errorBox(message, retry = "retry") {
  return `<div class="banner danger" role="alert">${icon("warning")}<div><strong>Chưa tải được dữ liệu</strong><p>${esc(message)}</p>${button("Thử lại", retry)}</div></div>`;
}
export function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = "toast " + (error ? "danger" : "");
  node.role = error ? "alert" : "status";
  node.textContent = message;
  $("#toasts").append(node);
  setTimeout(() => node.remove(), 6000);
}
export function modal(title, content, onSubmit = null) {
  const d = $("#modal");
  d.innerHTML = `<form method="dialog"><div class="dialog-head"><h2>${esc(title)}</h2><button class="icon-btn" value="cancel" aria-label="Đóng">${icon("close")}</button></div><div class="dialog-body">${content}</div></form>`;
  if (onSubmit)
    d.querySelector("form").addEventListener("submit", (e) => {
      if (e.submitter?.value === "cancel") return;
      e.preventDefault();
      onSubmit(e, d);
    });
  d.showModal();
  return d;
}
export async function confirmAction(title, message) {
  return new Promise((resolve) => {
    const d = modal(
      title,
      `<p>${esc(message)}</p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" value="confirm">Xác nhận</button></div>`,
    );
    d.addEventListener("close", () => resolve(d.returnValue === "confirm"), {
      once: true,
    });
  });
}
export function download(name, content, type = "text/csv;charset=utf-8") {
  const a = document.createElement("a");
  const url = URL.createObjectURL(new Blob([content], { type }));
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function csv(rows) {
  return rows
    .map((row) =>
      row
        .map(
          (v) =>
            '"' +
            String(v ?? "")
              .replace(/^[=+@-]/, "'")
              .replaceAll('"', '""') +
            '"',
        )
        .join(","),
    )
    .join("\r\n");
}
