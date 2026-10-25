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
    `<div class="banner info">Mô hình đăng ký tại đây chỉ là metadata nghiên cứu. Máy chủ chưa xác minh artifact/checkpoint và không cho phép triển khai candidate để suy luận.</div>` +
    `<div class="filters">${button("Đăng ký metadata mô hình", "register-model", "primary")}</div>` +
    `<section class="panel">${rows
      .map(
        (model) =>
          `<div class="list-row"><div><h3>${esc(model.name || model.model_id || "Mô hình")}</h3>` +
          `<p>${model.is_candidate ? "Candidate metadata — không dùng suy luận" : model.is_loaded ? "Mô hình phục vụ đã nạp" : "Chưa nạp"} · ${esc(model.architecture || "Chưa có kiến trúc")}</p>` +
          `<p class="mono">SHA-256: ${esc(model.checksum || "Chưa được máy chủ xác minh")}</p></div>` +
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
