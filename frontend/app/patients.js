import { getCasesPage } from "./cases.js";
import { renderComparison } from "./patient-compare.js";
import { $, $$, esc, pageHead, loading, errorBox, empty } from "./ui.js";
export async function renderPatients(root, pid) {
  root.innerHTML =
    pageHead(
      pid ? "Lịch sử khảo sát" : "Tra cứu bệnh nhân",
      "Chỉ hiển thị PID giả danh. Bảng hồ sơ dùng dấu HMAC để tra cứu PID nguồn. DICOM chưa được khử định danh đầy đủ: máy chủ lọc metadata văn bản, ngày giờ và thay UID nguồn; pixel không được làm sạch hay rà soát. Cờ BurnedInAnnotation từ máy siêu âm không xác nhận ảnh sạch; không tải ảnh có chữ định danh.",
    ) +
    '<input id="pidSearch" type="search" placeholder="PID nguồn đầy đủ hoặc PID giả danh" aria-label="Tìm PID" style="margin-bottom:20px"><div id="patientData">' +
    loading() +
    "</div>";
  const cleanups = [];
  const pageSize = 50;
  let timer, page = 1, serial = 0, controller;

  const load = async () => {
    if (!root.isConnected) return;
    const requestId = ++serial;
    controller?.abort();
    controller = new AbortController();
    const q = ($("#pidSearch", root)?.value || "").trim();
    cleanups.splice(0).forEach((fn) => fn?.());
    try {
      const search = q || "";
      const { items: rows, total } = await getCasesPage(
        pid && !search
          ? { patient_id: pid }
          : search
            ? { search }
            : {},
        {
          signal: controller.signal,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      );
      if (!root.isConnected || requestId !== serial) return;
      const grouped = rows.reduce(
        (map, c) =>
          map.set(c.patient_id, [...(map.get(c.patient_id) || []), c]),
        new Map(),
      );
      const entries = [...grouped.entries()];
      $("#patientData", root).innerHTML = rows.length
        ? entries
            .map(
              ([p, items], index) =>
                `<section class="panel" style="margin-bottom:20px"><div class="panel-head"><h2>${esc(p)}</h2><span class="badge">${items.length} lượt trên trang</span></div><div class="panel-body"><ol class="timeline">${items.map((c) => `<li><strong><a href="#case/${c.study_id}">${esc(c.study_code)}</a></strong><small>${esc(c.study_date)}</small></li>`).join("")}</ol>${items.length >= 2 ? `<details data-comparison="${index}"><summary>So sánh hai lần khảo sát</summary><div class="comparison-content" style="margin-top:20px"></div></details>` : '<p class="muted">Cần ít nhất hai lần khảo sát để so sánh.</p>'}</div></section>`,
            )
            .join("")
        : empty("Chưa có PID phù hợp", "Thử lại với mã PID khác.");
      if (total > pageSize) {
        $("#patientData", root).insertAdjacentHTML(
          "beforeend",
          `<div class="pagination"><span>${total} lượt khảo sát · Trang ${page}/${Math.ceil(total / pageSize)}</span><div class="actions"><button class="btn" id="patientPrev" ${page <= 1 ? "disabled" : ""}>Trước</button><button class="btn" id="patientNext" ${page * pageSize >= total ? "disabled" : ""}>Sau</button></div></div>`,
        );
        $("#patientPrev", root).onclick = () => {
          page--;
          load();
        };
        $("#patientNext", root).onclick = () => {
          page++;
          load();
        };
      }
      $$("[data-comparison]", root).forEach((detail) =>
        detail.addEventListener("toggle", async () => {
          if (!detail.open || detail.dataset.loaded) return;
          detail.dataset.loaded = "true";
          const cleanup = await renderComparison(
            detail.querySelector(".comparison-content"),
            entries[Number(detail.dataset.comparison)][1],
          );
          if (cleanup) cleanups.push(cleanup);
        }),
      );
    } catch (e) {
      if (e.name === "AbortError" || requestId !== serial) return;
      if (root.isConnected) {
        $("#patientData", root).innerHTML = errorBox(e.message);
        $("[data-action=retry]", root).onclick = () => load();
      }
    }
  };

  $("#pidSearch", root).oninput = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      page = 1;
      load();
    }, 250);
  };
  await load();

  return () => {
    clearTimeout(timer);
    controller?.abort();
    cleanups.splice(0).forEach((fn) => fn?.());
  };
}
