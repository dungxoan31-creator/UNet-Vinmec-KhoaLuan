import { state, role } from "./state.js";
import { request, protectedImage } from "./api.js";
import { getCasesPage } from "./cases.js";

import {
  $,
  $$,
  esc,
  button,
  badge,
  pageHead,
  empty,
  loading,
  errorBox,
  toast,
} from "./ui.js";
import { statusLabels } from "./i18n.js";

export async function renderWorklist(root) {
  const r = role(),
    identity = state.user.id,
    responsiveView = window.matchMedia("(max-width: 620px)");
  const active = () => root.isConnected && identity === state.user?.id;
  let page = 1,
    total = 0,
    rows = [],
    viewMode = responsiveView.matches ? "grid" : "table",
    viewModeChosen = false,
    sort = "created_at",
    direction = "desc",
    serial = 0,
    controller = null;
  const known = new Map(),
    thumbnailUrls = new Map(),
    urls = [];
  root.innerHTML =
    pageHead(
      "Danh sách ca",
      "Theo dõi hồ sơ RUO hai bên và tiếp tục rà soát đã lưu.",
      r === "BS" ? '<a class="btn primary" href="#intake">Tải ảnh mới</a>' : "",
    ) +
    `<p class="muted">Danh sách hồ sơ nghiên cứu RUO trong phạm vi tài khoản.</p>
        <div class="filters"><input id="caseSearch" type="search" placeholder="Mã ca, PID giả danh hoặc PID nguồn đầy đủ" aria-label="Tìm ca"><select id="caseStatus" aria-label="Trạng thái"><option value="">Mọi trạng thái</option>${Object.entries(
          statusLabels,
        )
          .map(([key, label]) => `<option value="${key}">${label}</option>`)
          .join(
            "",
          )}</select><input id="caseDate" type="date" aria-label="Ngày khảo sát">${button("Lưu bộ lọc", "save-filter")}${button("Làm mới", "refresh-cases")}</div>
        <div class="actions bulk-actions"><span class="muted small" data-export-status="disabled">Xuất dữ liệu đang bị khóa trên máy chủ RUO.</span><label class="small"><input id="autoRefresh" type="checkbox" checked> Tự làm mới mỗi phút</label></div>
        <div class="worklist-view-switch" role="group" aria-label="Cách hiển thị danh sách ca"><button class="btn small" id="caseTableView" type="button" aria-pressed="true">Dạng bảng</button><button class="btn small" id="caseGridView" type="button" aria-pressed="false">Dạng lưới</button></div>
        <div class="panel" id="caseResults">${loading()}</div>`;
  const target = $("#caseResults", root);
  const filters = () => ({
    q: $("#caseSearch", root).value.trim(),
    status: $("#caseStatus", root).value,
    date: $("#caseDate", root).value,
  });
  const thumbnail = (c, side) => {
    const i = c.images?.find((v) => v.laterality === side);
    const alt = `Ảnh ${side === "L" ? "trái" : "phải"} của ${c.study_code || c.study_id}`;
    return `<span class="case-thumb"><span>${side === "L" ? "T" : "P"}</span>${i ? `<span class="case-thumb-placeholder" data-thumb="${esc(i.image_id)}" data-thumb-alt="${esc(alt)}" aria-hidden="true"></span>` : '<span aria-label="Chưa có ảnh">—</span>'}</span>`;
  };
  const loadThumbnail = (imageId) => {
    let pending = thumbnailUrls.get(imageId);
    if (!pending) {
      pending = protectedImage(
        "/api/images/" + encodeURIComponent(imageId) + "/source.png",
      )
        .then((url) => {
          urls.push(url);
          return url;
        })
        .catch((error) => {
          thumbnailUrls.delete(imageId);
          throw error;
        });
      thumbnailUrls.set(imageId, pending);
    }
    return pending;
  };
  const renderTable = () =>
    `<div class="table-wrap"><table><thead><tr>${[
      ["study_code", "Mã ca / PID"],
      ["images", "Trái / Phải"],
      ["status", "Trạng thái"],
      ["study_date", "Ngày khảo sát"],
    ]
      .map(
        ([key, label]) =>
          `<th>${key === "images" ? label : `<button class="sort-button" data-sort="${key}">${label}${sort === key ? (direction === "asc" ? " ↑" : " ↓") : ""}</button>`}</th>`,
      )
      .join("")}<th></th></tr></thead><tbody>${rows
      .map(
        (c) =>
          `<tr><td><a href="#case/${encodeURIComponent(c.study_id)}"><strong>${esc(c.study_code || c.study_id)}</strong></a><small>PID ${esc(c.patient_id)}</small><small>Visit No ${esc(c.visit_no || "Chưa cấp")}</small></td><td><div class="case-thumbs">${thumbnail(c, "L")}${thumbnail(c, "R")}</div></td><td>${badge(c.status)}</td><td>${esc(c.study_date || "—")}</td><td><a class="btn small" href="#${r === "TK" && c.status === "SIGNED_PRELIM" ? "approval" : "viewer"}/${encodeURIComponent(c.study_id)}">Mở ca</a></td></tr>`,
      )
      .join("")}</tbody></table></div>`;
  const renderGrid = () =>
    `<div class="worklist-grid" role="list">${rows
      .map((c) => {
        const openRoute =
          r === "TK" && c.status === "SIGNED_PRELIM" ? "approval" : "viewer";
        return `<article class="worklist-grid-card" data-worklist-card="${esc(c.study_id)}" role="listitem"><div class="worklist-grid-card-head">${badge(c.status)}</div><a class="worklist-grid-open" href="#${openRoute}/${encodeURIComponent(c.study_id)}" aria-label="Mở ca ${esc(c.study_code || c.study_id)}"><div class="case-thumbs worklist-grid-thumbs">${thumbnail(c, "L")}${thumbnail(c, "R")}</div><strong>${esc(c.study_code || c.study_id)}</strong><small>PID ${esc(c.patient_id)}</small><small>Visit No ${esc(c.visit_no || "Chưa cấp")}</small></a><dl class="worklist-grid-meta"><div><dt>Ngày khảo sát</dt><dd>${esc(c.study_date || "—")}</dd></div></dl></article>`;
      })
      .join("")}</div>`;
  const syncViewButtons = () => {
    $("#caseTableView", root).setAttribute(
      "aria-pressed",
      String(viewMode === "table"),
    );
    $("#caseGridView", root).setAttribute(
      "aria-pressed",
      String(viewMode === "grid"),
    );
  };
  const draw = () => {
    target.innerHTML =
      (rows.length
        ? viewMode === "grid"
          ? renderGrid()
          : renderTable()
        : empty(
            "Không có ca phù hợp",
            "Thử bỏ bớt bộ lọc hoặc tải ảnh cho ca mới.",
          )) +
      `<div class="pagination"><span>${total} ca · Trang ${page}/${Math.max(1, Math.ceil(total / 10))}</span><div class="actions"><button class="btn" id="pagePrev" ${page <= 1 ? "disabled" : ""}>Trước</button><button class="btn" id="pageNext" ${page * 10 >= total ? "disabled" : ""}>Sau</button></div></div>`;
    $("#pagePrev", root).onclick = () => {
      page--;
      load();
    };
    $("#pageNext", root).onclick = () => {
      page++;
      load();
    };
    $$("[data-sort]", root).forEach(
      (btn) =>
        (btn.onclick = () => {
          direction =
            sort === btn.dataset.sort && direction === "asc" ? "desc" : "asc";
          sort = btn.dataset.sort;
          page = 1;
          load();
        }),
    );
    {
      $$("[data-thumb]", root).forEach(async (placeholder) => {
        try {
          const url = await loadThumbnail(placeholder.dataset.thumb);
          if (active() && placeholder.isConnected) {
            const image = document.createElement("img");
            image.dataset.thumb = placeholder.dataset.thumb;
            image.alt = placeholder.dataset.thumbAlt;
            image.loading = "lazy";
            image.src = url;
            placeholder.replaceWith(image);
          }
        } catch {
          if (placeholder.isConnected) {
            placeholder.classList.add("is-error");
            placeholder.textContent = "×";
            placeholder.removeAttribute("data-thumb");
            placeholder.removeAttribute("data-thumb-alt");
            placeholder.removeAttribute("aria-hidden");
            placeholder.setAttribute("role", "img");
            placeholder.setAttribute("aria-label", "Chưa tải được ảnh xem trước");
          }
        }
      });
    }
  };
  const updateResponsiveView = () => {
    if (viewModeChosen) return;
    const nextView = responsiveView.matches ? "grid" : "table";
    if (viewMode === nextView) return;
    viewMode = nextView;
    syncViewButtons();
    draw();
  };
  responsiveView.addEventListener("change", updateResponsiveView);
  syncViewButtons();
  $("#caseTableView", root).onclick = () => {
    if (viewMode === "table") return;
    viewModeChosen = true;
    viewMode = "table";
    syncViewButtons();
    draw();
  };
  $("#caseGridView", root).onclick = () => {
    if (viewMode === "grid") return;
    viewModeChosen = true;
    viewMode = "grid";
    syncViewButtons();
    draw();
  };
  const load = async () => {
    const version = ++serial;
    controller?.abort();
    controller = new AbortController();
    target.innerHTML = loading();
    try {
      const f = filters();
      const result = await getCasesPage(
        { search: f.q, status: f.status, date: f.date },
        {
          signal: controller.signal,
          limit: 10,
          offset: (page - 1) * 10,
          sort,
          direction,
        },
      );
      rows = result.items;
      total = result.total;
      if (!active() || version !== serial) return;
      for (const c of rows) known.set(c.study_id, c);
      state.queue = rows.map((c) => c.study_id);
      draw();
    } catch (e) {
      if (e.name === "AbortError" || !active() || version !== serial) return;
      target.innerHTML = errorBox(e.message);
      $("[data-action=retry]", target).onclick = load;
    }
  };
  let filterTimer;
  for (const id of [
    "caseSearch",
    "caseStatus",
    "caseDate",
  ])
    $("#" + id, root).oninput = () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => {
        page = 1;
        load();
      }, 200);
    };
  $("[data-action=refresh-cases]", root).onclick = load;
  $("[data-action=save-filter]", root).onclick = () => {
    const savedFilters = filters();
    delete savedFilters.q;
    try {
      localStorage.setItem("ova.filter." + identity, JSON.stringify(savedFilters));
    } catch {
      return toast("Không thể lưu bộ lọc trên thiết bị.", true);
    }
    toast("Đã lưu bộ lọc; nội dung tìm kiếm không được lưu.");
  };
  try {
    const filterKey = "ova.filter." + identity;
    let f = JSON.parse(localStorage.getItem(filterKey));
    if (
      f &&
      typeof f === "object" &&
      Object.prototype.hasOwnProperty.call(f, "q")
    ) {
      try {
        localStorage.removeItem(filterKey);
        toast("Đã xóa bộ lọc cũ có nội dung tìm kiếm.");
      } catch {
        toast("Không thể xóa truy vấn tìm kiếm cũ khỏi bộ nhớ trình duyệt.", true);
      }
      f = null;
    }
    if (f)
      for (const [key, id] of [
        ["q", "caseSearch"],
        ["status", "caseStatus"],
        ["date", "caseDate"],
      ]) {
        const input = $("#" + id, root);
        if (input) input.value = f[key] || "";
      }
  } catch {}
  await load();
  const timer = setInterval(() => {
    if (
      active() &&
      $("#autoRefresh", root).checked &&
      document.visibilityState === "visible" &&
      !state.dirty
    )
      load();
  }, 60000);
  return () => {
    controller?.abort();
    clearTimeout(filterTimer);
    clearInterval(timer);
    responsiveView.removeEventListener("change", updateResponsiveView);
    urls.forEach(URL.revokeObjectURL);
  };
}
