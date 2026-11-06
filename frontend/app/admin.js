import { renderAudit } from "./admin-audit.js";
import { renderDepartments } from "./admin-directory.js";
import { renderMetadata } from "./admin-metadata.js";
import { renderModels } from "./admin-models.js?v=20261102-loaded-models";
import { renderReports } from "./admin-reports.js";
import { renderUsers } from "./admin-users.js";
import { request } from "./api.js";
import { state } from "./state.js";

import {
  $,
  $$,
  button,
  confirmAction,
  csv,
  download,
  empty,
  errorBox,
  esc,
  field,
  loading,
  modal,
  pageHead,
  toast,
} from "./ui.js";

const sections = {
  reports: "Báo cáo quản trị",
  users: "Người dùng",
  departments: "Khoa / phòng",
  models: "Danh mục mô hình",
  audit: "Nhật ký truy cập",
  cases: "Metadata ca",
  settings: "Cấu hình",
  system: "Trạng thái / sao lưu",
};

export async function renderAdmin(root, section = "reports") {
  if (!sections[section]) section = "reports";
  root.innerHTML =
    pageHead(
      "Quản trị hệ thống",
      "Quản lý vận hành & Báo cáo điều hành; không truy cập ảnh lâm sàng.",
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
    if (section === "reports") {
      return await renderReports(target);
    } else if (section === "users") {
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
      const isGlobalAdmin = Boolean(state.user?.is_global_admin && !state.user?.facility_id);
      const facilities = isGlobalAdmin ? await request("/api/v1/facilities") : [];
      let selectedFacilityId = state.user?.facility_id || facilities[0]?.id || "";
      if (isGlobalAdmin && facilities.length === 0) {
        target.innerHTML = empty("Chưa có cơ sở hoạt động", "Tạo hoặc kích hoạt cơ sở trước khi cấu hình.");
        return;
      }

      const settingsFor = (facilityId) =>
        request(`/api/admin/settings${facilityId ? `?facility_id=${encodeURIComponent(facilityId)}` : ""}`);
      const renderSettingsForm = (config) => {
        const facilitySelector = isGlobalAdmin
          ? `<label class="field">Cơ sở áp dụng<select name="facility_id" id="settingsFacility" required>${facilities
              .map((facility) => `<option value="${esc(facility.id)}" ${facility.id === selectedFacilityId ? "selected" : ""}>${esc(facility.name)} (${esc(facility.facility_code)})</option>`)
              .join("")}</select></label>`
          : "";
        target.innerHTML = `<section class="panel"><form id="settingsForm" class="panel-body" style="max-width:600px">${facilitySelector}<p class="muted small">Chất lượng ảnh được kiểm tra bằng các quy tắc kỹ thuật cố định; cấu hình này không thay đổi ngưỡng đánh giá.</p>${field("Tên đơn vị trên phiếu", "report_header", "text", config.report_header, "required")}<label class="field">Đơn vị<select name="unit"><option value="auto" ${config.unit === "auto" ? "selected" : ""}>Theo hiệu chuẩn; thiếu spacing chỉ dùng pixel</option></select></label><button class="btn primary" type="submit">Lưu cấu hình</button></form></section>`;
        const form = $("#settingsForm");
        const selector = $("#settingsFacility", form);
        if (selector) {
          selector.onchange = async () => {
            const previousFacilityId = selectedFacilityId;
            selectedFacilityId = selector.value;
            selector.disabled = true;
            try {
              const nextConfig = await settingsFor(selectedFacilityId);
              renderSettingsForm(nextConfig);
              $("#settingsFacility")?.focus();
            } catch (error) {
              selectedFacilityId = previousFacilityId;
              selector.value = previousFacilityId;
              selector.disabled = false;
              toast(error.message, true);
            }
          };
        }
        form.onsubmit = async (event) => {
          event.preventDefault();
          const data = Object.fromEntries(new FormData(form));
          if (isGlobalAdmin) data.facility_id = selectedFacilityId;
          const submit = $("button[type=submit]", form);
          submit.disabled = true;
          try {
            const saved = await request("/api/admin/settings", { method: "PUT", body: data });
            renderSettingsForm(saved.settings);
            toast("Đã lưu cấu hình.");
          } catch (error) {
            submit.disabled = false;
            toast(error.message, true);
          }
        };
      };

      renderSettingsForm(await settingsFor(selectedFacilityId));
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
