import { state } from "./state.js";
import { getCasesPage, openCase, caseTable } from "./cases.js";
import { approvalImages } from "./approval-images.js";
import { formatLaterality } from "./laterality-hint.js";
import { $, esc, pageHead, badge, loading, errorBox } from "./ui.js";

export async function renderApproval(root, id, page = 1) {
  root.innerHTML =
    pageHead(
      id ? "Đối chiếu bản rà soát" : "Hàng chờ rà soát",
      "Chỉ xem và đối chiếu hồ sơ. Trang này không phê duyệt lâm sàng.",
    ) + `<div id="approvalData">${loading()}</div>`;
  try {
    if (!id) {
      const pageSize = 50;
      const { items: rows, total } = await getCasesPage(
        { status: "SIGNED_PRELIM" },
        { limit: pageSize, offset: (page - 1) * pageSize },
      );
      state.queue = rows.map((c) => c.study_id);
      $("#approvalData", root).innerHTML =
        `<section class="panel">${caseTable(rows, { action: "approval" })}</section><div class="pagination"><span>${total} ca · Trang ${page}/${Math.max(1, Math.ceil(total / pageSize))}</span><div class="actions"><button class="btn" id="approvalPrev" ${page <= 1 ? "disabled" : ""}>Trước</button><button class="btn" id="approvalNext" ${page * pageSize >= total ? "disabled" : ""}>Sau</button></div></div>`;
      $("#approvalPrev", root).onclick = () =>
        renderApproval(root, undefined, page - 1);
      $("#approvalNext", root).onclick = () =>
        renderApproval(root, undefined, page + 1);
      return;
    }
    const c = await openCase(id),
      target = $("#approvalData", root);
    target.innerHTML = `<div class="breadcrumb"><a href="#approval">Hàng chờ rà soát</a> / ${esc(c.study_code || c.study_id)}</div><section class="panel"><div class="panel-head"><h2>${esc(c.study_code || c.study_id)} · ${esc(c.patient_id)}</h2><div class="small">Trạng thái bản rà soát: ${badge(c.status)}</div></div><div class="panel-body"><p class="banner warning ruo-approval-notice" role="note">Bản rà soát này chỉ để đối chiếu nội bộ. Chức năng ký duyệt, chuyển trạng thái và phát hành kết quả lâm sàng chưa được triển khai.</p><div class="grid-2">${c.images.map((i) => `<section><h3>Buồng trứng ${formatLaterality(i.laterality)}</h3>${i.source ? `<img src="${esc(i.source)}" alt="Ảnh bên ${formatLaterality(i.laterality)}" style="width:100%;max-height:280px;object-fit:contain;background:#20262c">` : "<p>Ảnh sẽ tải trong workstation.</p>"}<p>${esc(i.notes || i.review?.clinical_notes || "Chưa có ghi chú")}</p><a class="btn" href="#viewer/${encodeURIComponent(c.study_id)}">Mở ca trong Workstation</a></section>`).join("")}</div>${c.signed_by ? `<div class="banner info">Người ghi nhận bản trước: ${esc(c.signed_by)} · Phiên bản ${esc(c.version || "chưa có")}</div>` : ""}${c.reason ? `<div class="banner warning">${esc(c.reason)}</div>` : ""}</div></section>`;
    const previews = [];
    for (const image of c.images) {
      previews.push({ image, html: await approvalImages(image) });
    }
    if (!target.isConnected) return;
    const sections = target.querySelectorAll(".grid-2 > section");
    previews.forEach(({ image, html }, index) => {
      const original = sections[index]?.querySelector("img");
      if (original) {
        const strip = document.createElement("div");
        strip.className = "approval-images";
        strip.innerHTML = html;
        original.replaceWith(strip);
      } else if (sections[index]) {
        const strip = document.createElement("div");
        strip.className = "approval-images";
        strip.innerHTML = html;
        sections[index].querySelector("h3").after(strip);
      }
      image.approval_seen = true;
    });
    await Promise.all(
      [...target.querySelectorAll(".approval-images img")].map((i) =>
        i.decode(),
      ),
    );
    if (!target.isConnected) return;
  } catch (e) {
    const target = $("#approvalData", root);
    if (target) {
      target.innerHTML = errorBox(e.message);
      $("[data-action=retry]", target).onclick = () => renderApproval(root, id);
    }
  }
}
