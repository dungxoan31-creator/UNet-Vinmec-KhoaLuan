import { state } from "./state.js";
import { request, protectedImage } from "./api.js";
import { $, $$, esc, loading, errorBox } from "./ui.js";
export async function renderComparison(root, cases) {
  if (cases.length < 2) return;
  // Sort chronologically ascending: older study first (Baseline), newer study second (Follow-up)
  const sorted = [...cases].sort((a, b) =>
    (a.study_date || "").localeCompare(b.study_date || "") ||
    (a.created_at || "").localeCompare(b.created_at || "")
  );
  root.innerHTML = `<h3>So sánh hai lần khảo sát</h3><div class="filters"><label class="field">Lần trước<select id="visitA">${sorted.map((c) => `<option value="${c.study_id}">${esc(c.study_date)} · ${esc(c.study_code)}</option>`).join("")}</select></label><label class="field">Lần sau<select id="visitB">${sorted.map((c) => `<option value="${c.study_id}">${esc(c.study_date)} · ${esc(c.study_code)}</option>`).join("")}</select></label><label class="field">Bên<select id="compareSide"><option value="L">Trái</option><option value="R">Phải</option></select></label></div><div id="visitComparison">${loading()}</div>`;
  $("#visitB", root).selectedIndex = 1;
  let generation = 0;
  const urls = [];
  const draw = async () => {
    const target = $("#visitComparison", root),
      version = ++generation;
    target.innerHTML = loading();
    try {
      const ids = [$("#visitA", root).value, $("#visitB", root).value],
        side = $("#compareSide", root).value;
      if (ids[0] === ids[1]) throw Error("Chọn hai lần khảo sát khác nhau.");
      const studies = await Promise.all(
        ids.map((id) => request("/api/cases/" + encodeURIComponent(id))),
      );
      const images = studies.map((c) =>
        c.images.find((i) => i.laterality === side),
      );
      if (images.some((i) => !i))
        throw Error("Một lần khảo sát chưa có ảnh bên được chọn.");
      const assets = await Promise.all(
        images.map(async (i) => {
          const url = await protectedImage(
            "/api/images/" + i.image_id + "/source.png",
          );
          urls.push(url);
          return url;
        }),
      );
      if (!root.isConnected || version !== generation) return;
      const measurements = await Promise.all(
        images.map((i) =>
          request("/api/images/" + i.image_id + "/measurements", {
            method: "POST",
            body: {
              rle_mask: i.review?.verified_mask_rle || i.prediction?.rle_mask,
            },
          }),
        ),
      );
      if (!root.isConnected || version !== generation) return;
      const samePhysical = measurements.every((m) => m.calibrated === true);
      const value = (m, key) => m[samePhysical ? key + "_mm" : key + "_px"];
      const number = (v) => (typeof v === "number" ? v.toFixed(2) : "Chưa có");
      const delta = (key) => {
        const a = value(measurements[0], key),
          b = value(measurements[1], key);
        return typeof a === "number" && typeof b === "number"
          ? (b - a).toFixed(2)
          : "Chưa có";
      };
      target.innerHTML = `<div class="grid-2"><div class="compare-viewport"><img src="${esc(assets[0])}" alt="Ảnh lần trước"><img class="compare-top" src="${esc(assets[1])}" alt="Ảnh lần sau chồng tham chiếu" id="compareOverlay"></div><div><label class="field">Độ mờ lần sau<input id="visitOpacity" type="range" min="0" max="100" value="50"></label><table><thead><tr><th>Số đo</th><th>Trước</th><th>Sau</th><th>Thay đổi</th></tr></thead><tbody>${[
        ["max_diameter", "d₁"],
        ["ortho_diameter", "d₂"],
      ]
        .map(
          ([key, label]) =>
            `<tr><td>${label}</td><td>${number(value(measurements[0], key))}</td><td>${number(value(measurements[1], key))}</td><td>${delta(key)} ${samePhysical ? "mm" : "px"}</td></tr>`,
        )
        .join(
          "",
        )}</tbody></table><div class="banner warning small">Chồng ảnh chỉ để đối chiếu trực quan, chưa đăng ký ảnh. ${samePhysical ? "Hai ảnh có hiệu chuẩn; so sánh còn phụ thuộc mặt phẳng khảo sát." : "Chưa có hiệu chuẩn vật lý cho cả hai lần; chênh lệch pixel không thể hiện tăng/giảm kích thước thật."}</div></div></div>`;
      $("#visitOpacity", root).oninput = (e) =>
        ($("#compareOverlay", root).style.opacity =
          Number(e.target.value) / 100);
    } catch (e) {
      if (root.isConnected && version === generation) {
        target.innerHTML = errorBox(e.message);
        $("[data-action=retry]", target).onclick = draw;
      }
    }
  };
  for (const id of ["visitA", "visitB", "compareSide"])
    $("#" + id, root).onchange = draw;
  await draw();
  return () => urls.forEach(URL.revokeObjectURL);
}
