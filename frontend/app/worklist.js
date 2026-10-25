import { state, role } from "./state.js";
import { request, protectedImage } from "./api.js";
import { getCases } from "./cases.js";

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
  csv,
  download,
  modal,
} from "./ui.js";
import { statusLabels } from "./i18n.js";

export async function renderWorklist(root) {
  const r = role(),
    identity = state.user.id;
  const active = () => root.isConnected && identity === state.user?.id;
  const scopes =
    r === "BS"
      ? [["mine", "Của tôi"]]
      : [
          ["mine", "Của tôi"],
          ["department", "Khoa"],
          ["all", "Tất cả trong quyền"],
        ];
  let scope = r === "BS" ? "mine" : "department",
    page = 1,
    total = 0,
    rows = [],
    viewMode = "table",
    sort = "created_at",
    direction = "desc",
    serial = 0,
    controller = null;
  const selected = new Set(),
    known = new Map(),
    thumbnailUrls = new Map(),
    urls = [];
  root.innerHTML =
    pageHead(
      "Danh sách ca",
      "Theo dõi khảo sát hai bên, tiếp tục rà soát và chuyển duyệt.",
      r === "BS" ? '<a class="btn primary" href="#intake">Tải ảnh mới</a>' : "",
    ) +
    `<div class="tabs" role="tablist" aria-label="Phạm vi ca">${scopes.map(([key, label]) => `<button role="tab" data-scope="${key}" aria-selected="${key === scope}" class="${key === scope ? "active" : ""}">${label}</button>`).join("")}</div>
        <div class="filters"><input id="caseSearch" type="search" placeholder="Mã ca, PID giả danh hoặc PID nguồn đầy đủ" aria-label="Tìm ca"><select id="caseStatus" aria-label="Trạng thái"><option value="">Mọi trạng thái</option>${Object.entries(
          statusLabels,
        )
          .map(([key, label]) => `<option value="${key}">${label}</option>`)
          .join(
            "",
          )}</select><input id="caseDate" type="date" aria-label="Ngày khảo sát"><input id="caseOwner" placeholder="Người phụ trách" aria-label="Lọc người phụ trách">${button("Lưu bộ lọc", "save-filter")}${button("Làm mới", "refresh-cases")}</div>
        <div class="actions bulk-actions"><span id="selectionCount" class="muted small">Chưa chọn ca</span>${button("Xuất đã chọn", "export-selected")}${r === "TK" ? button("Gán người phụ trách", "assign-selected") : ""}<label class="small"><input id="autoRefresh" type="checkbox" checked> Tự làm mới mỗi phút</label></div>
        <div class="worklist-view-switch" role="group" aria-label="Cách hiển thị danh sách ca"><button class="btn small" id="caseTableView" type="button" aria-pressed="true">Dạng bảng</button><button class="btn small" id="caseGridView" type="button" aria-pressed="false">Dạng lưới</button></div>
        <div class="panel" id="caseResults">${loading()}</div>`;
  const target = $("#caseResults", root);
  if (state.capabilities?.case_workflow !== true)
    $("#caseOwner", root)?.remove();
  const filters = () => ({
    q: $("#caseSearch", root).value.trim(),
    status: $("#caseStatus", root).value,
    date: $("#caseDate", root).value,
    owner: $("#caseOwner", root)?.value.trim() || "",
  });
  const selectionCount = () => {
    $("#selectionCount", root).textContent = selected.size
      ? `Đã chọn ${selected.size} ca`
      : "Chưa chọn ca";
  };
  const thumbnail = (c, side) => {
    const i = c.images?.find((v) => v.laterality === side);
    return `<span class="case-thumb"><span>${side === "L" ? "T" : "P"}</span>${i ? `<img data-thumb="${esc(i.image_id)}"  alt="Ảnh ${side === "L" ? "trái" : "phải"} của ${esc(c.study_code)}" loading="lazy">` : '<span aria-label="Chưa có ảnh">—</span>'}</span>`;
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
    `<div class="table-wrap"><table><thead><tr><th><input id="selectAll" type="checkbox" aria-label="Chọn tất cả ca trên trang"></th>${[
      ["study_code", "Mã ca / PID"],
      ["images", "Trái / Phải"],
      ["status", "Trạng thái"],
      ["study_date", "Ngày khảo sát"],
      ["owner_id", "Người phụ trách"],
    ]
      .map(
        ([key, label]) =>
          `<th>${key === "images" ? label : `<button class="sort-button" data-sort="${key}">${label}${sort === key ? (direction === "asc" ? " ↑" : " ↓") : ""}</button>`}</th>`,
      )
      .join("")}<th></th></tr></thead><tbody>${rows
      .map(
        (c) =>
          `<tr><td><input class="case-select" type="checkbox" value="${esc(c.study_id)}" aria-label="Chọn ${esc(c.study_code)}" ${selected.has(c.study_id) ? "checked" : ""}></td><td><a href="#case/${encodeURIComponent(c.study_id)}"><strong>${esc(c.study_code || c.study_id)}</strong></a><small>${esc(c.patient_id)}</small></td><td><div class="case-thumbs">${thumbnail(c, "L")}${thumbnail(c, "R")}</div></td><td>${badge(c.status)}</td><td>${esc(c.study_date || "—")}</td><td>${esc(c.owner_name || c.owner_id || "Chưa phân công")}</td><td><a class="btn small" href="#${r === "TK" && c.status === "SIGNED_PRELIM" ? "approval" : "viewer"}/${encodeURIComponent(c.study_id)}">Mở ca</a></td></tr>`,
      )
      .join("")}</tbody></table></div>`;
  const renderGrid = () =>
    `<div class="worklist-grid" role="list">${rows
      .map((c) => {
        const openRoute =
          r === "TK" && c.status === "SIGNED_PRELIM" ? "approval" : "viewer";
        return `<article class="worklist-grid-card" data-worklist-card="${esc(c.study_id)}" role="listitem"><div class="worklist-grid-card-head"><input class="case-select" type="checkbox" value="${esc(c.study_id)}" aria-label="Chọn ${esc(c.study_code)}" ${selected.has(c.study_id) ? "checked" : ""}>${badge(c.status)}</div><a class="worklist-grid-open" href="#${openRoute}/${encodeURIComponent(c.study_id)}" aria-label="Mở ca ${esc(c.study_code || c.study_id)}"><div class="case-thumbs worklist-grid-thumbs">${thumbnail(c, "L")}${thumbnail(c, "R")}</div><strong>${esc(c.study_code || c.study_id)}</strong><small>${esc(c.patient_id)}</small></a><dl class="worklist-grid-meta"><div><dt>Ngày khảo sát</dt><dd>${esc(c.study_date || "—")}</dd></div><div><dt>Người phụ trách</dt><dd>${esc(c.owner_name || c.owner_id || "Chưa phân công")}</dd></div></dl></article>`;
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
    $$(".case-select", root).forEach(
      (input) =>
        (input.onchange = () => {
          input.checked
            ? selected.add(input.value)
            : selected.delete(input.value);
          selectionCount();
        }),
    );
    $("#selectAll", root)?.addEventListener("change", (e) => {
      $$(".case-select", root).forEach((input) => {
        input.checked = e.target.checked;
        input.checked
          ? selected.add(input.value)
          : selected.delete(input.value);
      });
      selectionCount();
    });
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
      $$("[data-thumb]", root).forEach(async (img) => {
        try {
          const url = await loadThumbnail(img.dataset.thumb);
          if (active() && img.isConnected) img.src = url;
        } catch {
          if (img.isConnected) {
            img.removeAttribute("src");
            img.alt = "Chưa tải được ảnh xem trước";
          }
        }
      });
    }
    selectionCount();
  };
  $("#caseTableView", root).onclick = () => {
    if (viewMode === "table") return;
    viewMode = "table";
    syncViewButtons();
    draw();
  };
  $("#caseGridView", root).onclick = () => {
    if (viewMode === "grid") return;
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
      if (state.capabilities?.case_workflow !== true) {
        const adapted = await getCases(
          { search: f.q, status: f.status, date: f.date },
          { signal: controller.signal },
        );
        total = adapted.length;
        const pageSize = 10;
        const start = (page - 1) * pageSize;
        rows = adapted.slice(start, start + pageSize);
      } else {
        const query = new URLSearchParams({
          ...f,
          scope,
          page: String(page),
          page_size: "10",
          sort,
          direction,
        });
        const data = await request("/api/workspace/cases?" + query, {
          signal: controller.signal,
        });
        if (Array.isArray(data)) {
          total = data.length;
          const pageSize = 10;
          const start = (page - 1) * pageSize;
          rows = data.slice(start, start + pageSize);
        } else if (Array.isArray(data?.items)) {
          rows = data.items;
          total = Number.isInteger(data.total) ? data.total : data.items.length;
        } else {
          throw Error("Danh sách ca trả về không đúng hợp đồng phân trang.");
        }
      }
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
    ...(state.capabilities?.case_workflow === true ? ["caseOwner"] : []),
  ])
    $("#" + id, root).oninput = () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => {
        page = 1;
        load();
      }, 200);
    };
  $$("[data-scope]", root).forEach(
    (btn) =>
      (btn.onclick = () => {
        scope = btn.dataset.scope;
        page = 1;
        selected.clear();
        $$("[data-scope]", root).forEach((b) => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-selected", String(b === btn));
        });
        load();
      }),
  );
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
        ["owner", "caseOwner"],
      ]) {
        const input = $("#" + id, root);
        if (input) input.value = f[key] || "";
      }
  } catch {}
  $("[data-action=export-selected]", root).onclick = async () => {
    if (!selected.size) return toast("Chọn ít nhất một ca.", true);
    try {
      const data = (
        await request("/api/workspace/cases/export", {
          method: "POST",
          body: { ids: [...selected] },
        })
      ).items;
      download(
        "danh-sach-ca.csv",
        csv([
          ["Mã ca", "PID", "Trạng thái"],
          ...data.map((c) => [
            c.study_code,
            c.patient_id,
            statusLabels[c.status] || c.status,
          ]),
        ]),
      );
    } catch (e) {
      toast(e.message, true);
    }
  };
  $("[data-action=assign-selected]", root)?.addEventListener("click", () => {
    if (!selected.size) return toast("Chọn ít nhất một ca.", true);
    modal(
      "Gán người phụ trách",
      `<label class="field">Mã tài khoản phụ trách<input name="owner" required></label><p>${selected.size} ca đã chọn. Thao tác không ký duyệt thay người rà soát.</p><button class="btn primary" type="submit">Gán người phụ trách</button>`,
      async (e, d) => {
        try {
          const owner = new FormData(e.target).get("owner");
          {
            await request("/api/workspace/cases/assign", {
              method: "POST",
              body: { ids: [...selected], owner_id: owner },
            });
          }
          d.close();
          await load();
        } catch (err) {
          toast(err.message, true);
        }
      },
    );
  });
  await load();
  const timer = setInterval(() => {
    if (
      active() &&
      $("#autoRefresh", root).checked &&
      document.visibilityState === "visible" &&
      !state.dirty &&
      !selected.size
    )
      load();
  }, 60000);
  return () => {
    controller?.abort();
    clearTimeout(filterTimer);
    clearInterval(timer);
    urls.forEach(URL.revokeObjectURL);
  };
}
