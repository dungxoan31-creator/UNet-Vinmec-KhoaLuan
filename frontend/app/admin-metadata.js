import { state } from "./state.js";
import { request } from "./api.js";

import { $, esc, badge, loading, errorBox, empty, button } from "./ui.js";
export async function renderMetadata(target) {
  target.innerHTML =
    '<div class="banner info">Quản trị chỉ xem metadata vận hành. Không tải thumbnail, ảnh hoặc mask.</div><div class="filters"><input id="metadataQuery" aria-label="Tìm mã ca" placeholder="Tìm mã ca khảo sát"></div><section class="panel" id="metadataRows"></section>';
  let page = 1,
    timer;
  const size = 20;
  async function load() {
    const panel = $("#metadataRows", target);
    panel.innerHTML = loading();
    try {
      const q = $("#metadataQuery", target).value;
      const result = await request(
        "/api/admin/cases?" + new URLSearchParams({ q, page, page_size: size }),
      );
      if (!Array.isArray(result.items) || !Number.isFinite(result.total))
        throw Error("Metadata chưa đúng contract phân trang.");
      panel.innerHTML = result.items.length
        ? `<div class="table-wrap"><table><thead><tr><th>Mã ca</th><th>Trạng thái</th><th>Khoa</th><th>Thời gian tạo</th><th>Phiên bản</th></tr></thead><tbody>${result.items.map((c) => `<tr><td class="mono">${esc(c.study_code || c.study_id)}</td><td>${badge(c.status)}</td><td>${esc(c.department || "Chưa được cung cấp")}</td><td>${esc(c.created_at || c.study_date)}</td><td>${esc(c.version || "Chưa được cung cấp")}</td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${result.total} ca · trang ${page}</span><div class="actions">${button("Trước", "meta-prev")}${button("Sau", "meta-next")}</div></div>`
        : empty("Không có metadata phù hợp");
      const prev = $("[data-action=meta-prev]", target),
        next = $("[data-action=meta-next]", target);
      if (prev) {
        prev.disabled = page === 1;
        prev.onclick = () => {
          page--;
          load();
        };
        next.disabled = page * size >= result.total;
        next.onclick = () => {
          page++;
          load();
        };
      }
    } catch (e) {
      if (panel.isConnected) {
        panel.innerHTML = errorBox(e.message);
        $("[data-action=retry]", panel).onclick = load;
      }
    }
  }
  $("#metadataQuery", target).oninput = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      page = 1;
      load();
    }, 250);
  };
  await load();
  return () => clearTimeout(timer);
}
