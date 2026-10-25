import { state } from "./state.js";
import { getCases, openCase, caseTable } from "./cases.js";
import { request } from "./api.js";

import { startCorrection } from "./corrections.js";
import { nextCase } from "./workflow.js";
import { approvalImages } from "./approval-images.js";
import {
  $,
  esc,
  pageHead,
  button,
  badge,
  loading,
  errorBox,
  modal,
  toast,
} from "./ui.js";

export async function renderApproval(root, id) {
  root.innerHTML =
    pageHead(
      id ? "Duyệt chính thức" : "Hàng chờ duyệt",
      "Kiểm tra hai bên. Người duyệt khác người ký sơ bộ.",
    ) + `<div id="approvalData">${loading()}</div>`;
  try {
    if (!id) {
      const rows = (await getCases()).filter(
        (c) => c.status === "SIGNED_PRELIM",
      );
      state.queue = rows.map((c) => c.study_id);
      $("#approvalData", root).innerHTML =
        `<section class="panel">${caseTable(rows, { action: "approval" })}</section>`;
      return;
    }
    const c = await openCase(id),
      target = $("#approvalData", root);
    target.innerHTML = `<div class="breadcrumb"><a href="#approval">Hàng chờ</a> / ${esc(c.study_code || c.study_id)}</div><section class="panel"><div class="panel-head"><h2>${esc(c.study_code || c.study_id)} · ${esc(c.patient_id)}</h2>${badge(c.status)}</div><div class="panel-body"><div class="grid-2">${c.images.map((i) => `<section><h3>Buồng trứng ${i.laterality === "L" ? "trái" : "phải"}</h3>${i.source ? `<img src="${esc(i.source)}" alt="Ảnh bên ${i.laterality}" style="width:100%;max-height:280px;object-fit:contain;background:#20262c">` : "<p>Ảnh sẽ tải trong workstation.</p>"}<p>${esc(i.notes || i.review?.clinical_notes || "Chưa có ghi chú")}</p><a class="btn" href="#viewer/${c.study_id}">Đối chiếu mask bác sĩ / AI</a></section>`).join("")}</div><div class="banner info">Người ký sơ bộ: ${esc(c.signed_by || "Máy chủ chưa cung cấp")} · Phiên bản ${c.version || "chưa có"}</div>${c.reason ? `<div class="banner warning">${esc(c.reason)}</div>` : ""}<div class="actions">${button("Duyệt chính thức", "approve", "primary")}${button("Từ chối, yêu cầu sửa", "reject", "danger")}${button("Sửa trong phiên bản mới", "correct")}${button("Khóa ca", "lock")}${button("Tạo bản bổ sung", "addendum")}${button("Ca tiếp theo", "approval-next")}</div><p id="approvalError" class="form-error" role="alert"></p></div></section>`;
    const own = c.signed_by === state.user.id;
    for (const name of ["approve", "reject", "correct", "lock", "addendum"])
      $(`[data-action=${name}]`, root).disabled = true;
    const previews = await Promise.all(
      c.images.map(async (image) => ({
        image,
        html: await approvalImages(image),
      })),
    );
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
    for (const name of ["approve", "reject"])
      $(`[data-action=${name}]`, root).disabled =
        own || c.status !== "SIGNED_PRELIM";
    $("[data-action=correct]", root).disabled =
      own || !["SIGNED_PRELIM", "IN_REVIEW", "REJECTED"].includes(c.status);
    $("[data-action=lock]", root).disabled = c.status !== "APPROVED";
    $("[data-action=addendum]", root).disabled = c.status !== "LOCKED";
    let pending = false;
    async function execute(action, reason = "") {
      if (pending) return;
      pending = true;
      try {
        {
          Object.assign(
            c,
            await request(
              "/api/workspace/cases/" +
                encodeURIComponent(c.study_id) +
                "/transitions",
              { method: "POST", body: { action, reason, version: c.version } },
            ),
          );
        }
        toast("Đã ghi nhận thao tác" + ".");
        await renderApproval(root, id);
      } catch (e) {
        if (root.isConnected) $("#approvalError", root).textContent = e.message;
      } finally {
        pending = false;
      }
    }
    $("[data-action=approve]", root).onclick = () => execute("APPROVE");
    $("[data-action=lock]", root).onclick = () => execute("LOCK");
    $("[data-action=approval-next]", root).onclick = () => nextCase();
    for (const [name, action] of [
      ["reject", "REJECT"],
      ["addendum", "ADDENDUM"],
      ["correct", "CORRECTION"],
    ])
      $(`[data-action=${name}]`, root).onclick = () =>
        modal(
          {
            reject: "Lý do từ chối",
            addendum: "Lý do bản bổ sung",
            correct: "Sửa trên phiên bản mới",
          }[name],
          `<label class="field">Lý do<textarea name="reason" required minlength="5" maxlength="500"></textarea></label>${name === "correct" ? '<p class="muted small">Giữ phiên bản trước. Sau khi chuyên gia sửa, ca trở lại bác sĩ phụ trách để rà soát và ký lại.</p>' : ""}<button class="btn primary" type="submit">Xác nhận</button>`,
          async (e, d) => {
            const reason = new FormData(e.target).get("reason").trim();
            if (reason.length < 5) return;
            const submit = e.submitter;
            submit.disabled = true;
            try {
              if (action === "CORRECTION") await startCorrection(c, reason);
              else await execute(action, reason);
              d.close();
            } catch (err) {
              toast(err.message, true);
            } finally {
              submit.disabled = false;
            }
          },
        );
  } catch (e) {
    const target = $("#approvalData", root);
    if (target) {
      target.innerHTML = errorBox(e.message);
      $("[data-action=retry]", target).onclick = () => renderApproval(root, id);
    }
  }
}
