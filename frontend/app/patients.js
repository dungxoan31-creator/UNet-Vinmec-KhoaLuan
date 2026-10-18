import { getCases } from "./cases.js";
import { renderComparison } from "./patient-compare.js";
import { $, $$, esc, pageHead, loading, errorBox, empty } from "./ui.js";
export async function renderPatients(root, pid) {
  root.innerHTML =
    pageHead(
      pid ? "Lịch sử khảo sát" : "Tra cứu bệnh nhân",
      "Chỉ hiển thị PID ẩn danh, không thu thập danh tính thật.",
    ) +
    '<input id="pidSearch" type="search" placeholder="Tìm PID" aria-label="Tìm PID" style="margin-bottom:20px"><div id="patientData">' +
    loading() +
    "</div>";
  const cleanups = [];
  let timer;

  const load = async () => {
    if (!root.isConnected) return;
    const q = ($("#pidSearch", root)?.value || "").trim();
    cleanups.splice(0).forEach((fn) => fn?.());
    try {
      const searchTerm = q || pid || "";
      const cases = await getCases(searchTerm ? { search: searchTerm } : {});
      if (!root.isConnected) return;

      const rows = cases.filter(
        (c) =>
          (!pid || c.patient_id.toLowerCase() === pid.toLowerCase()) &&
          (!q || c.patient_id.toLowerCase().includes(q.toLowerCase())),
      );
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
                `<section class="panel" style="margin-bottom:20px"><div class="panel-head"><h2>${esc(p)}</h2><span class="badge">${items.length} lần khảo sát</span></div><div class="panel-body"><ol class="timeline">${items.map((c) => `<li><strong><a href="#case/${c.study_id}">${esc(c.study_code)}</a></strong><small>${esc(c.study_date)}</small></li>`).join("")}</ol>${items.length >= 2 ? `<details data-comparison="${index}"><summary>So sánh hai lần khảo sát</summary><div class="comparison-content" style="margin-top:20px"></div></details>` : '<p class="muted">Cần ít nhất hai lần khảo sát để so sánh.</p>'}</div></section>`,
            )
            .join("")
        : empty("Chưa có PID phù hợp", "Thử lại với mã PID khác.");
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
      if (root.isConnected) {
        $("#patientData", root).innerHTML = errorBox(e.message);
        $("[data-action=retry]", root).onclick = () => load();
      }
    }
  };

  $("#pidSearch", root).oninput = () => {
    clearTimeout(timer);
    timer = setTimeout(load, 250);
  };
  await load();

  return () => {
    clearTimeout(timer);
    cleanups.splice(0).forEach((fn) => fn?.());
  };
}
