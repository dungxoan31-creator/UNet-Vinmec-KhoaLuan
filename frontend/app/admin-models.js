import { request } from "./api.js";

import {
  $,
  $$,
  esc,
  button,
  field,
  empty,
  modal,
  toast,
  confirmAction,
} from "./ui.js";

export async function renderModels(target) {
  const response = await request("/api/admin/models");
  const rows = response.registered_models || response.items || [];
  const reload = () => window.dispatchEvent(new CustomEvent("ova:rerender"));

  target.innerHTML =
    `<div class="banner info" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">` +
    `<div><strong>QUẢN LÝ KHO MÔ HÌNH (MODEL REGISTRY &amp; MODEL ZOO)</strong>` +
    `<p class="small muted" style="margin:2px 0 0 0;">Trạng thái nạp do máy chủ cung cấp. Chỉ mô hình đã nạp và xác minh checkpoint được dùng cho suy luận nghiên cứu (RUO); các adapter tham chiếu chưa có triển khai độc lập.</p></div>` +
    `</div>` +
    `<div class="filters" style="margin:12px 0;">${button("Đăng ký metadata mô hình", "register-model", "primary")}</div>` +
    `<section class="panel" style="display:flex; flex-direction:column; gap:8px;">${rows
      .map(
        (model) =>
          `<div class="list-row" style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border-bottom:1px solid #f1f5f9;">` +
          `<div>` +
          `<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">` +
          `<h3 style="margin:0; font-size:14.5px; font-weight:700; color:#0f172a;">${esc(model.name || model.model_id || "Mô hình")}</h3>` +
          `<span class="badge" style="background:${model.is_loaded ? '#dcfce7' : '#fee2e2'}; color:${model.is_loaded ? '#15803d' : '#b91c1c'}; font-weight:700; font-size:11px; padding:2px 8px; border-radius:4px;">` +
          `${model.is_candidate ? "Candidate metadata — không dùng suy luận" : model.is_loaded ? "Mô hình phục vụ đã nạp" : "Chưa nạp"}</span>` +
          `</div>` +
          `<p style="margin:4px 0 2px 0; color:#334155; font-size:13px;">${esc(model.architecture || "Chưa có kiến trúc")} <span class="small muted">(v${esc(model.version || "1.0.0")})</span></p>` +
          `<p class="mono" style="font-size:12px; color:#0369a1; background:#f0f9ff; padding:3px 8px; border-radius:4px; display:inline-block; border:1px solid #bae6fd; margin:4px 0 0 0;">SHA-256: ${esc(model.checksum || "Chưa được máy chủ xác minh")}</p>` +
          `${model.checkpoint ? `<p class="small muted mono" style="margin:3px 0 0 0; font-size:11px; color:#64748b;">Đường dẫn: ${esc(model.checkpoint)}</p>` : ""}` +
          `</div>` +
          (model.is_candidate
            ? `<div class="actions"><button class="btn small danger" data-remove="${esc(model.model_id)}">Gỡ metadata</button></div>`
            : "") +
          `</div>`,
      )
      .join("") || empty("Chưa có mô hình")}</section>`;

  $("[data-action=register-model]", target).onclick = () =>
    modal(
      "Đăng ký metadata mô hình",
      field("Mã mô hình", "model_id", "text", "", 'required maxlength="64"') +
        field("Tên hiển thị", "name", "text", "", 'required maxlength="100"') +
        `<label class="field">Kiến trúc<select name="architecture"><option>U-Net</option><option>U-Net++</option></select></label>` +
        field("Mã artifact tham chiếu", "artifact_id", "text", "", 'required maxlength="128"') +
        '<p class="small muted">Đăng ký chỉ lưu thông tin tham chiếu. Hệ thống chưa xác minh nội dung, hash hoặc khả năng nạp; candidate không được dùng để suy luận.</p><button class="btn primary" type="submit">Lưu metadata</button>',
      async (event, dialog) => {
        const submit = event.submitter;
        if (submit.disabled) return;
        submit.disabled = true;
        try {
          await request("/api/admin/models/register", {
            method: "POST",
            body: Object.fromEntries(new FormData(event.target)),
          });
          dialog.close();
          reload();
        } catch (error) {
          toast(error.message, true);
        } finally {
          submit.disabled = false;
        }
      },
    );

  $$('[data-remove]', target).forEach((control) => {
    control.onclick = async () => {
      const modelId = control.dataset.remove;
      if (!(await confirmAction("Gỡ metadata candidate?", modelId))) return;
      control.disabled = true;
      try {
        await request(`/api/admin/models/${encodeURIComponent(modelId)}`, {
          method: "DELETE",
        });
        reload();
      } catch (error) {
        toast(error.message, true);
        control.disabled = false;
      }
    };
  });
}
