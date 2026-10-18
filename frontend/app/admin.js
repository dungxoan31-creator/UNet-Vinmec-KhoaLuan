import { renderUsers } from "./admin-users.js";
import { renderDepartments } from "./admin-directory.js";
import { renderModels } from "./admin-models.js";
import { renderAudit } from "./admin-audit.js";
import { renderMetadata } from "./admin-metadata.js";
import { state } from "./state.js";
import { request } from "./api.js";

import {
  $,
  $$,
  esc,
  pageHead,
  button,
  field,
  loading,
  errorBox,
  empty,
  modal,
  toast,
  csv,
  download,
  confirmAction,
} from "./ui.js";
const sections = {
  users: "Người dùng",
  departments: "Khoa / phòng",
  models: "Danh mục mô hình",
  audit: "Nhật ký truy cập",
  cases: "Metadata ca",
  settings: "Cấu hình",
  system: "Trạng thái / sao lưu",
};
export async function renderAdmin(root, section = "users") {
  if (!sections[section]) section = "users";
  root.innerHTML =
    pageHead(
      "Quản trị hệ thống",
      "Quản lý vận hành; không truy cập ảnh lâm sàng.",
    ) +
    `<nav class="tabs">${Object.entries(sections)
      .map(
        ([key, title]) =>
          `<a href="#admin/${key}" class="${key === section ? "active" : ""}">${title}</a>`,
      )
      .join("")}</nav><div id="adminData">${loading()}</div>`;
  const target = $("#adminData");
  const reload = () => renderAdmin(root, section);
  try {
    if (section === "users") {
      return await renderUsers(target);
    } else if (section === "departments") {
      return await renderDepartments(target);
    } else if (section === "models") {
      return await renderModels(target);
    } else if (section === "audit") {
      return await renderAudit(target);
    } else if (section === "cases") {
      return await renderMetadata(target);
    } else if (section === "settings") {
      const config = await request("/api/admin/settings");
      target.innerHTML = `<section class="panel"><form id="settingsForm" class="panel-body" style="max-width:600px">${field("Ngưỡng IQA (0–1)", "iqa_threshold", "number", config.iqa_threshold, 'required min="0" max="1" step="0.01"')}${field("Tên đơn vị trên phiếu", "report_header", "text", config.report_header, "required")}<label class="field">Đơn vị<select name="unit"><option value="auto">Theo hiệu chuẩn; thiếu spacing chỉ dùng pixel</option></select></label><button class="btn primary" type="submit">Lưu cấu hình</button></form></section>`;
      $("#settingsForm").onsubmit = async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        try {
          {
            await request("/api/admin/settings", { method: "PUT", body: data });
          }
          toast("Đã lưu cấu hình" + ".");
        } catch (e) {
          toast(e.message, true);
        }
      };
    } else {
      const data = await request("/api/health");
      target.innerHTML = `<div class="grid-2"><section class="panel"><div class="panel-head"><h2>Sức khỏe dịch vụ</h2></div><div class="panel-body"><p>${esc(data.status || "Đã phản hồi")}</p>${button("Kiểm tra lại", "refresh-health")}</div></section><section class="panel"><div class="panel-head"><h2>Sao lưu dữ liệu</h2></div><div class="panel-body"><p>Quản trị chỉ tạo bản sao lưu metadata trong giao diện này.</p>${button("Tạo bản sao lưu", "backup")}</div></section></div><section class="panel" style="margin-top:24px"><div class="panel-head"><h2>Lịch sử sao lưu</h2></div><div id="backupList" class="panel-body"></div></section>`;
      $("[data-action=refresh-health]").onclick = reload;
      const showBackups = async () => {
        try {
          const backups = await request("/api/admin/backups/list");
          $("#backupList").textContent = JSON.stringify(backups, null, 2);
        } catch (e) {
          $("#backupList").textContent = e.message;
        }
      };
      await showBackups();
      $("[data-action=backup]").onclick = async () => {
        try {
          {
            await request("/api/admin/backups/create?include_images=false", {
              method: "POST",
            });
          }
          toast("Đã yêu cầu sao lưu metadata.");
          showBackups();
        } catch (e) {
          toast(e.message, true);
        }
      };
    }
  } catch (e) {
    target.innerHTML = errorBox(e.message);
    $("[data-action=retry]").onclick = reload;
  }
}
