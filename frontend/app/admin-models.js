import { state } from "./state.js";
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
  target.innerHTML = `<div class="banner info">SHA-256 và trạng thái checkpoint lấy từ máy chủ. Đăng ký metadata không đồng nghĩa mô hình đã được kiểm chứng.</div><div class="filters">${button("Đăng ký checkpoint", "register-model", "primary")}</div><section class="panel">${rows.map((m) => `<div class="list-row"><div><h3>${esc(m.name || m.model_name || m.model_id)}</h3><p>${m.is_loaded ? "Đã nạp" : "Chưa nạp"} · ${esc(m.architecture || "Chưa có kiến trúc")}</p><p class="mono">SHA-256: ${esc(m.checksum || "Chưa được máy chủ xác minh")}</p></div><div class="actions"><button class="btn small" data-deploy="${esc(m.model_id)}" ${m.is_loaded ? "disabled" : ""}>${"Triển khai"}</button><button class="btn small danger" data-remove="${esc(m.model_id)}" ${m.is_loaded ? "disabled" : ""}>Gỡ đăng ký</button></div></div>`).join("") || empty("Chưa có checkpoint")}</section>`;
  $("[data-action=register-model]", target).onclick = () =>
    modal(
      "Đăng ký checkpoint",
      field("Mã mô hình", "model_id", "text", "", 'required maxlength="64"') +
        field("Tên hiển thị", "name", "text", "", 'required maxlength="100"') +
        `<label class="field">Kiến trúc<select name="architecture"><option>U-Net</option><option>U-Net++</option></select></label>` +
        field(
          "Mã artifact trên máy chủ",
          "artifact_id",
          "text",
          "",
          'required maxlength="128"',
        ) +
        '<p class="small muted">Không nhập đường dẫn tùy ý hoặc SHA giả. Máy chủ phải xác minh artifact, hash và khả năng nạp trước khi triển khai.</p><button class="btn primary" type="submit">Đăng ký</button>',
      async (e, d) => {
        const b = e.submitter;
        if (b.disabled) return;
        b.disabled = true;
        try {
          const body = Object.fromEntries(new FormData(e.target));
          {
            await request("/api/admin/models/register", {
              method: "POST",
              body,
            });
          }
          d.close();
          reload();
        } catch (err) {
          toast(err.message, true);
        } finally {
          b.disabled = false;
        }
      },
    );
  for (const action of ["deploy", "remove"])
    $$("[data-" + action + "]", target).forEach(
      (b) =>
        (b.onclick = async () => {
          const id = b.dataset[action];
          if (
            !(await confirmAction(
              action === "deploy"
                ? "Triển khai mô hình?"
                : "Gỡ đăng ký mô hình?",
              "Không thay đổi provenance của các dự đoán đã lưu.",
            ))
          )
            return;
          b.disabled = true;
          try {
            {
              await request(
                "/api/admin/models/" +
                  encodeURIComponent(id) +
                  (action === "deploy" ? "/deploy" : ""),
                { method: action === "deploy" ? "POST" : "DELETE" },
              );
            }
            reload();
          } catch (e) {
            toast(e.message, true);
            b.disabled = false;
          }
        }),
    );
}
