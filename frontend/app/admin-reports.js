import { request } from "./api.js";
import { $, $$, esc, errorBox, loading } from "./ui.js";

export function formatAdminMetric(value, unit = "") {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value}${unit}`
    : "Chưa có số liệu";
}

export function analyticsShare(count, total) {
  if (!Number.isFinite(count) || !Number.isFinite(total) || total <= 0) return null;
  return Math.round((count / total) * 100);
}

export function renderExecutiveMetrics(summary) {
  const completionRate = summary.total_cases > 0
    ? Math.round((summary.completed_cases / summary.total_cases) * 100)
    : null;
  return `
    <div class="metrics">
      <div class="metric">
        <span>Tổng ca khám</span>
        <strong>${summary.total_cases}</strong>
        <small>${summary.completed_cases} hoàn thành (${formatAdminMetric(completionRate, "%")})</small>
      </div>
      <div class="metric">
        <span>Đồng thuận AI toàn viện</span>
        <strong style="color:var(--vm-primary-blue, #0284c7);">${formatAdminMetric(summary.overall_consensus_rate_pct, "%")}</strong>
        <small>Bác sĩ chấp thuận nguyên bản · ${summary.total_reviews} lượt rà soát</small>
      </div>
      <div class="metric">
        <span>Chất lượng ảnh (IQA)</span>
        <strong style="color:#10b981;">${formatAdminMetric(summary.avg_iqa_score)}</strong>
        <small>Đạt chuẩn: ${formatAdminMetric(summary.iqa_pass_rate_pct, "%")} · ${summary.iqa_scored_count ?? 0} ảnh có điểm IQA</small>
      </div>
      <div class="metric">
        <span>Thời gian rà soát TB</span>
        <strong>${formatAdminMetric(summary.avg_review_seconds, "s")}</strong>
        <small>${summary.review_duration_count ?? 0} lượt có thời lượng ghi nhận</small>
      </div>
    </div>
  `;
}

export function renderChartDrilldownButton({ type, value, label, count, percentage, color, selected }) {
  const dataAttribute = type === "ORADS" ? "data-orads" : "data-lesion";
  const context = type === "ORADS" ? `${value} (${label})` : value;
  const percentageLabel = percentage === null ? "tỷ lệ chưa có số liệu" : `${percentage}%`;
  return `
    <button type="button" class="chart-drilldown-row" ${dataAttribute}="${esc(value)}"
      aria-pressed="${selected ? "true" : "false"}"
      aria-label="Lọc danh sách ca theo ${esc(context)}, ${count} ca, ${percentageLabel}"
      title="Bấm để lọc ca ${esc(value)}"
      style="cursor:pointer; display:block; width:100%; text-align:left; color:inherit; font:inherit; padding:6px 8px; border-radius:6px; border:1px solid ${selected ? (type === "ORADS" ? "#0284c7" : "#8b5cf6") : "transparent"}; background:${selected ? (type === "ORADS" ? "#f0f9ff" : "#faf5ff") : "transparent"}; transition:all 0.15s ease;">
      <span style="display:flex; justify-content:space-between; margin-bottom:3px; font-size:12.5px;">
        <span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">
          <span aria-hidden="true" style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${color};"></span>
          ${esc(value)} ${label ? `<small class="muted" style="font-weight:400;">(${esc(label)})</small>` : ""}
        </span>
        <span style="font-weight:700;">${count} ca (${percentageLabel})</span>
      </span>
      <span aria-hidden="true" style="display:block; background:#e2e8f0; height:7px; border-radius:4px; overflow:hidden;">
        <span style="display:block; width:${percentage ?? 0}%; background:${color}; height:100%;"></span>
      </span>
    </button>
  `;
}

export async function renderReports(target) {
  target.innerHTML = loading();

  try {
    // 1. Initial metadata fetch for doctors list
    const initialDoctors = await request("/api/admin/doctor-stats");

    // Palette & Labels
    const oradsBadges = {
      "O-RADS 1": { color: "#10b981", label: "Sinh lý / Bình thường" },
      "O-RADS 2": { color: "#0284c7", label: "Lành tính cao (<1%)" },
      "O-RADS 3": { color: "#f59e0b", label: "Nguy cơ thấp (1–<10%)" },
      "O-RADS 4": { color: "#ea580c", label: "Nguy cơ trung bình (10–<50%)" },
      "O-RADS 5": { color: "#ef4444", label: "Nguy cơ cao (≥50%)" },
      "Chưa ghi nhận": { color: "#64748b", label: "Chờ rà soát" },
    };

    const lesionColors = {
      "U quái (Dermoid cyst)": "#8b5cf6",
      "Nang lạc nội mạc tử cung (Chocolate cyst)": "#d946ef",
      "U nang tuyến thanh dịch": "#0284c7",
      "U nang tuyến nhầy": "#06b6d4",
      "Nang đơn giản": "#10b981",
      "U tế bào vỏ (Thecoma)": "#f59e0b",
      "Ung thư biểu mô thanh dịch độ cao": "#ef4444",
      "Buồng trứng bình thường": "#10b981",
      "Khác / Chưa ghi nhận": "#64748b",
    };

    const actionMeta = {
      ACCEPTED_RAW: { label: "Chấp thuận AI thô (Không sửa)", color: "#10b981" },
      MODIFIED: { label: "Bác sĩ tinh chỉnh Mask / Caliper", color: "#f59e0b" },
      REJECTED_ALL: { label: "Bác sĩ từ chối kết quả AI", color: "#ef4444" },
    };

    const iqaMeta = {
      "Xuất sắc (≥ 0.8)": { color: "#10b981", desc: "Độ sắc nét & tương phản tối ưu" },
      "Đạt chuẩn (0.5 - 0.8)": { color: "#0284c7", desc: "Đủ tiêu chuẩn chẩn đoán" },
      "Cần chú ý (< 0.5)": { color: "#ef4444", desc: "Nhiễu âm / vôi hóa / che khuất" },
    };

    const demoMeta = {
      "Tiền mãn kinh (Pre-menopausal)": { color: "#0284c7" },
      "Sau mãn kinh (Post-menopausal)": { color: "#d946ef" },
      "Chưa ghi nhận": { color: "#94a3b8" },
    };

    // State
    const state = {
      days: "",
      status: "",
      doctor_id: "",
      chartFilter: { type: null, value: null, label: null },
    };

    // Build Base Layout
    target.innerHTML = `
      <!-- TOP BANNER -->
      <div class="banner info" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:14px;">
        <div>
          <strong style="font-size:15px; letter-spacing:0.02em;">BÁO CÁO QUẢN TRỊ & THỐNG KÊ LÂM SÀNG (MIS EXECUTIVE BI DASHBOARD)</strong>
          <p class="small muted" style="margin:2px 0 0 0;" id="lastUpdateText">Đang tải số liệu mới nhất từ máy chủ...</p>
        </div>
        <div class="actions" style="display:flex; align-items:center; gap:8px;">
          <a class="btn small" href="/api/admin/reports/doctor-productivity/export-csv" download="doctor_productivity.csv">Xuất CSV Năng suất</a>
          <button class="btn small primary" type="button" data-action="print-report">In báo cáo / Lưu PDF</button>
          <button class="btn small quiet" type="button" data-action="refresh-reports">Làm mới</button>
        </div>
      </div>

      <!-- MULTI-DIMENSIONAL FILTER TOOLBAR -->
      <section class="panel" style="margin-bottom:16px; background:#f8fafc; border:1px solid #cbd5e1;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap; flex:1;">
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="font-size:12px; font-weight:700; color:#334155; text-transform:uppercase;">Bộ lọc quản trị:</span>
            </div>

            <!-- 1. Time Horizon Filter -->
            <label style="display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:600; color:#475569;">
              <span>🕒 Thời gian:</span>
              <select id="filterDays" class="input-select" style="padding:5px 8px; border-radius:5px; border:1px solid #cbd5e1; font-size:12.5px; background:#ffffff;">
                <option value="">Toàn bộ thời gian</option>
                <option value="1">Hôm nay (24 giờ)</option>
                <option value="7">7 ngày gần nhất</option>
                <option value="30">30 ngày gần nhất</option>
                <option value="90">Quý này (90 ngày)</option>
              </select>
            </label>

            <!-- 2. Status Filter -->
            <label style="display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:600; color:#475569;">
              <span>🩺 Trạng thái ca:</span>
              <select id="filterStatus" class="input-select" style="padding:5px 8px; border-radius:5px; border:1px solid #cbd5e1; font-size:12.5px; background:#ffffff;">
                <option value="">Tất cả trạng thái</option>
                <option value="REVIEWED">Đã hoàn tất / Ký duyệt</option>
                <option value="PENDING">Chờ xử lý / Chưa ký</option>
              </select>
            </label>

            <!-- 3. Doctor Filter -->
            <label style="display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:600; color:#475569;">
              <span>👨‍⚕️ Bác sĩ:</span>
              <select id="filterDoctor" class="input-select" style="padding:5px 8px; border-radius:5px; border:1px solid #cbd5e1; font-size:12.5px; background:#ffffff; max-width:200px;">
                <option value="">Tất cả bác sĩ</option>
                ${initialDoctors.map(d => `<option value="${esc(d.doctor_id)}">${esc(d.doctor_name)} (${d.signed_count} ca)</option>`).join("")}
              </select>
            </label>
          </div>

          <div style="display:flex; align-items:center; gap:8px;">
            <button class="btn small quiet" id="resetFiltersBtn" type="button" style="font-size:12px;">✕ Đặt lại bộ lọc</button>
          </div>
        </div>
      </section>

      <!-- 1. TOP EXECUTIVE KPI METRICS CONTAINER -->
      <div id="metricsContainer">
        ${loading()}
      </div>

      <!-- 2. 6 KPI BI CHARTS GRID -->
      <div id="chartsContainer" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap:16px; margin-top:16px;">
        ${loading()}
      </div>

      <!-- 3. DRILL-DOWN DATA GRID (MASTER-DETAIL INTERACTIVE SECTION) -->
      <section class="panel" id="drilldownSection" style="margin-top:20px;">
        <div class="panel-head" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <div>
            <h2 id="drilldownTitle" style="display:inline-flex; align-items:center; gap:8px; margin:0;">
              Danh sách Ca khám chi tiết
            </h2>
            <small class="muted" id="drilldownSubtitle" style="display:block; margin-top:2px;">
              Dữ liệu tra cứu chi tiết; nhấp vào các thanh biểu đồ ở trên để lọc tức thì.
            </small>
          </div>
          <div class="actions" style="display:flex; align-items:center; gap:8px;">
            <button class="btn small quiet" id="clearChartFilterBtn" type="button" style="display:none;">✕ Xóa lọc biểu đồ</button>
            <a class="btn small" id="exportFilteredCsvBtn" href="/api/admin/reports/cases/export-csv" download="filtered_cases.csv">Xuất CSV danh sách</a>
          </div>
        </div>
        <div class="table-responsive-box" id="drilldownTableContainer">
          ${loading()}
        </div>
      </section>

      <!-- 4. DOCTOR PRODUCTIVITY & CONSENSUS TABLE -->
      <section class="panel" style="margin-top:20px;">
        <div class="panel-head" style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h2 style="margin:0;">Báo cáo Năng suất Bác sĩ & Tỷ lệ Đồng thuận AI</h2>
            <small class="muted">Theo dõi khối lượng ký duyệt và mức độ chỉnh sửa mask/caliper của từng bác sĩ.</small>
          </div>
          <span class="badge" style="background:#e0f2fe; color:#0369a1; padding:4px 8px; border-radius:4px; font-weight:600; font-size:12px;" id="doctorCountBadge">
            ${initialDoctors.length} Bác sĩ
          </span>
        </div>
        <div class="table-responsive-box" id="doctorsTableContainer">
          ${renderDoctorTable(initialDoctors)}
        </div>
      </section>

      <!-- 5. ULTRASOUND EQUIPMENT QUALITY CONTROL SUMMARY -->
      <section class="panel" style="margin-top:20px;">
        <div class="panel-head">
          <h2 style="margin:0;">Kiểm soát Chất lượng Ảnh & Thiết bị Siêu âm</h2>
          <small class="muted">Đánh giá độ sắc nét, tương phản và tính toàn vẹn hiệu chuẩn đo đạc theo tiêu chuẩn y tế.</small>
        </div>
        <div class="panel-body" id="equipmentQcContainer">
          <!-- Populated dynamically -->
        </div>
      </section>
    `;

    // Helper: Render Doctor Productivity Table HTML
    function renderDoctorTable(docs) {
      if (!docs || !docs.length) {
        return `<div style="text-align:center; padding:24px;" class="muted">Chưa có dữ liệu bác sĩ nào.</div>`;
      }
      return `
        <table class="medical-data-table" style="width:100%; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:2px solid var(--vm-border, #e2e8f0); text-align:left;">
              <th style="padding:10px 12px;">Bác sĩ</th>
              <th style="padding:10px 12px;">Khoa / Đơn vị</th>
              <th style="padding:10px 12px; text-align:center;">Số ca đã ký</th>
              <th style="padding:10px 12px; text-align:center;">Chấp thuận thô</th>
              <th style="padding:10px 12px; text-align:center;">Chỉnh sửa</th>
              <th style="padding:10px 12px; text-align:center;">Từ chối</th>
              <th style="padding:10px 12px;">Tỷ lệ đồng thuận AI</th>
              <th style="padding:10px 12px; text-align:right;">Thời gian TB</th>
              <th style="padding:10px 12px; text-align:right;">Hoạt động cuối</th>
            </tr>
          </thead>
          <tbody>
            ${docs.map(d => `
              <tr style="border-bottom:1px solid var(--vm-border, #f1f5f9);">
                <td style="padding:10px 12px; font-weight:600;">
                  <div>${esc(d.doctor_name)}</div>
                  <small class="muted mono">${esc(d.doctor_id)}</small>
                </td>
                <td style="padding:10px 12px;">${esc(d.department)}</td>
                <td style="padding:10px 12px; text-align:center; font-weight:700;">${d.signed_count}</td>
                <td style="padding:10px 12px; text-align:center; color:#10b981;">${d.raw_accepted_count}</td>
                <td style="padding:10px 12px; text-align:center; color:#f59e0b;">${d.modified_count}</td>
                <td style="padding:10px 12px; text-align:center; color:#ef4444;">${d.rejected_count}</td>
                <td style="padding:10px 12px;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <div style="flex:1; background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden;">
                      <div style="width:${Math.min(100, d.consensus_rate_pct ?? 0)}%; background:#0284c7; height:100%;"></div>
                    </div>
                    <span style="font-weight:600; font-size:12px; min-width:40px;">${formatAdminMetric(d.consensus_rate_pct, "%")}</span>
                  </div>
                  <small class="muted">${d.signed_count} lượt rà soát</small>
                </td>
                <td style="padding:10px 12px; text-align:right;">${formatAdminMetric(d.avg_review_seconds, "s")}<small class="muted">${d.review_duration_count ?? 0} lượt</small></td>
                <td style="padding:10px 12px; text-align:right; font-size:12px;" class="muted">${esc(d.last_active)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    // Function: Load Drill-down Cases Table
    const loadDrilldownCases = async () => {
      const container = $("#drilldownTableContainer", target);
      const title = $("#drilldownTitle", target);
      const subtitle = $("#drilldownSubtitle", target);
      const clearBtn = $("#clearChartFilterBtn", target);
      const exportBtn = $("#exportFilteredCsvBtn", target);

      container.innerHTML = loading();

      const params = new URLSearchParams();
      if (state.days) params.set("days", state.days);
      if (state.status) params.set("status", state.status);
      if (state.doctor_id) params.set("doctor_id", state.doctor_id);

      if (state.chartFilter.type === "ORADS" && state.chartFilter.value) {
        params.set("orads", state.chartFilter.value);
      } else if (state.chartFilter.type === "LESION" && state.chartFilter.value) {
        params.set("lesion_type", state.chartFilter.value);
      }

      const qs = params.toString() ? `?${params.toString()}` : "";
      exportBtn.href = `/api/admin/reports/cases/export-csv${qs}`;

      // Title & Subtitle updates
      let criteria = [];
      if (state.days) criteria.push(`${state.days} ngày qua`);
      if (state.status) criteria.push(state.status === "REVIEWED" ? "Đã ký duyệt" : "Chờ xử lý");
      if (state.doctor_id) criteria.push(`BS: ${state.doctor_id}`);
      if (state.chartFilter.label) criteria.push(state.chartFilter.label);

      if (state.chartFilter.label) {
        title.innerHTML = `Danh sách Ca khám chi tiết · <span style="color:#0284c7; font-weight:700;">${esc(state.chartFilter.label)}</span>`;
        clearBtn.style.display = "inline-flex";
      } else {
        title.textContent = "Danh sách Ca khám chi tiết (Tất cả ca theo bộ lọc)";
        clearBtn.style.display = "none";
      }

      subtitle.textContent = criteria.length
        ? `Đang áp dụng bộ lọc: ${criteria.join(" · ")}. Nhấp vào các dòng để xem hoặc bấm Xuất CSV.`
        : "Hiển thị toàn bộ ca khám trong cơ sở dữ liệu. Nhấp chuột vào biểu đồ để lọc tức thì.";

      try {
        const cases = await request(`/api/admin/reports/cases${qs}`);
        if (!cases || !cases.length) {
          container.innerHTML = `<div style="text-align:center; padding:36px;" class="muted">Không có ca khám nào khớp với các tiêu chí lọc hiện tại.</div>`;
          return;
        }

        container.innerHTML = `
          <table class="medical-data-table" style="width:100%; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid var(--vm-border, #e2e8f0); text-align:left;">
                <th style="padding:10px 12px;">Mã ca</th>
                <th style="padding:10px 12px;">Đợt khám</th>
                <th style="padding:10px 12px;">Bác sĩ phụ trách</th>
                <th style="padding:10px 12px;">Phân tầng O-RADS</th>
                <th style="padding:10px 12px;">Mặt bệnh / Loại tổn thương</th>
                <th style="padding:10px 12px; text-align:right;">Kích thước (D1×D2)</th>
                <th style="padding:10px 12px; text-align:center;">Ngày khám</th>
                <th style="padding:10px 12px; text-align:center;">Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              ${cases.map(c => {
                const badge = oradsBadges[c.orads] || { color: "#64748b", label: "Khác" };
                const lesionColor = lesionColors[c.lesion_type] || "#475569";
                return `
                  <tr style="border-bottom:1px solid var(--vm-border, #f1f5f9);">
                    <td style="padding:10px 12px; font-weight:600;" class="mono">${esc(c.study_code)}</td>
                    <td style="padding:10px 12px;">${esc(c.visit_no || "—")}</td>
                    <td style="padding:10px 12px; font-weight:500;">${esc(c.doctor_name)}</td>
                    <td style="padding:10px 12px;">
                      <span style="display:inline-flex; align-items:center; gap:6px; font-weight:600; font-size:12px;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${badge.color};"></span>
                        ${esc(c.orads)}
                      </span>
                    </td>
                    <td style="padding:10px 12px;">
                      <span style="display:inline-flex; align-items:center; gap:6px; font-weight:600; font-size:12px;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${lesionColor};"></span>
                        ${esc(c.lesion_type)}
                      </span>
                    </td>
                    <td style="padding:10px 12px; text-align:right; font-weight:600;" class="mono">${esc(c.measurements_summary)}</td>
                    <td style="padding:10px 12px; text-align:center; font-size:12px;" class="muted">${esc(c.study_date)}</td>
                    <td style="padding:10px 12px; text-align:center;">
                      <span class="badge" style="background:#f1f5f9; color:#334155; font-size:11px;">${esc(c.status)}</span>
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        `;
      } catch (err) {
        container.innerHTML = errorBox("Lỗi nạp danh sách ca: " + err.message);
      }
    };

    // Function: Refresh Dashboard with current filters
    const refreshDashboard = async () => {
      const metricsContainer = $("#metricsContainer", target);
      const chartsContainer = $("#chartsContainer", target);
      const qcContainer = $("#equipmentQcContainer", target);
      const lastUpdateText = $("#lastUpdateText", target);

      metricsContainer.innerHTML = loading();
      chartsContainer.innerHTML = loading();

      const params = new URLSearchParams();
      if (state.days) params.set("days", state.days);
      if (state.status) params.set("status", state.status);
      if (state.doctor_id) params.set("doctor_id", state.doctor_id);

      const qs = params.toString() ? `?${params.toString()}` : "";

      try {
        const summary = await request(`/api/admin/analytics/summary${qs}`);
        lastUpdateText.textContent = `Cập nhật lúc: ${esc(summary.generated_at)} · Toàn bộ chỉ số phản ánh lát cắt dữ liệu đang chọn.`;

        // 1. RENDER 4 TOP EXECUTIVE METRICS
        metricsContainer.innerHTML = renderExecutiveMetrics(summary);

        // 2. RENDER 6 BI CHARTS
        const totalOradsCount = Object.values(summary.orads_distribution || {}).reduce((a, b) => a + b, 0);
        const totalLesionCount = Object.values(summary.lesion_distribution || {}).reduce((a, b) => a + b, 0);
        const totalActionCount = Object.values(summary.action_distribution || {}).reduce((a, b) => a + b, 0);
        const totalIqaCount = Object.values(summary.iqa_tiers || {}).reduce((a, b) => a + b, 0);
        const totalDemoCount = Object.values(summary.demographics || {}).reduce((a, b) => a + b, 0);

        chartsContainer.innerHTML = `
          <!-- CHART 1: ORADS RISK STRATIFICATION (INTERACTIVE) -->
          <section class="panel">
            <div class="panel-head" style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <h3 style="margin:0; font-size:14px; font-weight:700;">1. Phân tầng Nguy cơ O-RADS</h3>
                <small class="muted">Nhấp vào từng thanh để lọc danh sách ca bệnh tương ứng.</small>
              </div>
              <span class="badge" style="background:#e0f2fe; color:#0369a1; font-size:11px;">Interactive</span>
            </div>
            <div class="panel-body">
              <div style="display:flex; flex-direction:column; gap:8px;">
                ${Object.entries(summary.orads_distribution || {}).map(([key, count]) => {
                  const badge = oradsBadges[key] || { color: "#64748b", label: "Khác" };
                  const pct = analyticsShare(count, totalOradsCount);
                  const isSelected = state.chartFilter.type === "ORADS" && state.chartFilter.value === key;
                  return renderChartDrilldownButton({
                    type: "ORADS", value: key, label: badge.label, count,
                    percentage: pct, color: badge.color, selected: isSelected,
                  });
                }).join("")}
              </div>
            </div>
          </section>

          <!-- CHART 2: LESION HISTOPATHOLOGY (INTERACTIVE) -->
          <section class="panel">
            <div class="panel-head" style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <h3 style="margin:0; font-size:14px; font-weight:700;">2. Cơ cấu Mặt bệnh & Loại tổn thương</h3>
                <small class="muted">Thống kê dịch tễ u buồng trứng; nhấp để xem danh sách ca.</small>
              </div>
              <span class="badge" style="background:#e0f2fe; color:#0369a1; font-size:11px;">Interactive</span>
            </div>
            <div class="panel-body">
              <div style="display:flex; flex-direction:column; gap:8px;">
                ${Object.entries(summary.lesion_distribution || {}).map(([key, count]) => {
                  const color = lesionColors[key] || "#64748b";
                  const pct = analyticsShare(count, totalLesionCount);
                  const isSelected = state.chartFilter.type === "LESION" && state.chartFilter.value === key;
                  return renderChartDrilldownButton({
                    type: "LESION", value: key, label: "", count,
                    percentage: pct, color, selected: isSelected,
                  });
                }).join("")}
              </div>
            </div>
          </section>

          <!-- CHART 3: WORKLOAD & COMPLETION TIMELINE TREND -->
          <section class="panel">
            <div class="panel-head">
              <h3 style="margin:0; font-size:14px; font-weight:700;">3. Xu hướng Tiếp nhận & Hoàn tất Ca</h3>
              <small class="muted">Tải công việc hàng ngày trong chu kỳ lọc (Tổng tiếp nhận vs Hoàn tất).</small>
            </div>
            <div class="panel-body">
              ${summary.timeline_trend && summary.timeline_trend.length ? `
                <div style="display:flex; flex-direction:column; gap:8px;">
                  ${summary.timeline_trend.map(item => {
                    const maxVal = Math.max(...summary.timeline_trend.map(t => t.total), 1);
                    const totalPct = Math.round((item.total / maxVal) * 100);
                    const compPct = Math.round((item.completed / maxVal) * 100);
                    return `
                      <div style="padding:4px 0;">
                        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
                          <span style="font-weight:600; color:#334155;">Ngày ${esc(item.date)}</span>
                          <span class="muted" style="font-size:11.5px;">
                            <strong style="color:#0284c7;">${item.total} tiếp nhận</strong> · <strong style="color:#10b981;">${item.completed} hoàn tất</strong>
                          </span>
                        </div>
                        <div style="background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden; position:relative;">
                          <div style="width:${totalPct}%; background:#cbd5e1; height:100%; position:absolute; left:0; top:0;"></div>
                          <div style="width:${compPct}%; background:#10b981; height:100%; position:absolute; left:0; top:0;"></div>
                        </div>
                      </div>
                    `;
                  }).join("")}
                  <div style="display:flex; justify-content:flex-end; gap:12px; margin-top:6px; font-size:11px;" class="muted">
                    <span style="display:inline-flex; align-items:center; gap:4px;"><span style="width:8px; height:8px; background:#cbd5e1; border-radius:2px;"></span> Tiếp nhận</span>
                    <span style="display:inline-flex; align-items:center; gap:4px;"><span style="width:8px; height:8px; background:#10b981; border-radius:2px;"></span> Đã hoàn tất</span>
                  </div>
                </div>
              ` : `<div style="text-align:center; padding:24px;" class="muted">Không có dữ liệu chu kỳ.</div>`}
            </div>
          </section>

          <!-- CHART 4: HITL HUMAN-IN-THE-LOOP ACTION DISTRIBUTION -->
          <section class="panel">
            <div class="panel-head">
              <h3 style="margin:0; font-size:14px; font-weight:700;">4. Quyết định Thẩm định AI (HITL Actions)</h3>
              <small class="muted">Đo lường mức độ phụ thuộc và can thiệp của bác sĩ đối với gợi ý AI.</small>
            </div>
            <div class="panel-body">
              <div style="display:flex; flex-direction:column; gap:10px;">
                ${Object.entries(summary.action_distribution || {}).map(([key, count]) => {
                  const meta = actionMeta[key] || { label: key, color: "#64748b" };
                  const pct = analyticsShare(count, totalActionCount);
                  const pctLabel = pct === null ? "—" : `${pct}%`;
                  return `
                    <div>
                      <div style="display:flex; justify-content:space-between; margin-bottom:3px; font-size:12.5px;">
                        <span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">
                          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${meta.color};"></span>
                          ${esc(meta.label)}
                        </span>
                        <span style="font-weight:700;">${count} lượt (${pctLabel})</span>
                      </div>
                      <div style="background:#e2e8f0; height:7px; border-radius:4px; overflow:hidden;">
                        <div style="width:${pct ?? 0}%; background:${meta.color}; height:100%;"></div>
                      </div>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          </section>

          <!-- CHART 5: ULTRASOUND IMAGE QUALITY TIERS (IQA) -->
          <section class="panel">
            <div class="panel-head">
              <h3 style="margin:0; font-size:14px; font-weight:700;">5. Phân cấp Chất lượng Ảnh Siêu âm (IQA)</h3>
              <small class="muted">Tự động chấm điểm độ sắc nét, tương phản trên từng khung hình DICOM/PNG.</small>
            </div>
            <div class="panel-body">
              <div style="display:flex; flex-direction:column; gap:10px;">
                ${Object.entries(summary.iqa_tiers || {}).map(([key, count]) => {
                  const meta = iqaMeta[key] || { color: "#64748b", desc: "" };
                  const pct = analyticsShare(count, totalIqaCount);
                  const pctLabel = pct === null ? "—" : `${pct}%`;
                  return `
                    <div>
                      <div style="display:flex; justify-content:space-between; margin-bottom:3px; font-size:12.5px;">
                        <span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">
                          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${meta.color};"></span>
                          ${esc(key)} <small class="muted" style="font-weight:400;">(${esc(meta.desc)})</small>
                        </span>
                        <span style="font-weight:700;">${count} ảnh (${pctLabel})</span>
                      </div>
                      <div style="background:#e2e8f0; height:7px; border-radius:4px; overflow:hidden;">
                        <div style="width:${pct ?? 0}%; background:${meta.color}; height:100%;"></div>
                      </div>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          </section>

          <!-- CHART 6: PATIENT DEMOGRAPHICS (MENOPAUSAL STATUS) -->
          <section class="panel">
            <div class="panel-head">
              <h3 style="margin:0; font-size:14px; font-weight:700;">6. Cơ cấu Bệnh nhân & Mãn kinh</h3>
              <small class="muted">Chỉ số sinh lý quyết định ngưỡng phân loại O-RADS 2 / O-RADS 3.</small>
            </div>
            <div class="panel-body">
              <div style="display:flex; flex-direction:column; gap:10px;">
                ${Object.entries(summary.demographics || {}).map(([key, count]) => {
                  const meta = demoMeta[key] || { color: "#64748b" };
                  const pct = analyticsShare(count, totalDemoCount);
                  const pctLabel = pct === null ? "—" : `${pct}%`;
                  return `
                    <div>
                      <div style="display:flex; justify-content:space-between; margin-bottom:3px; font-size:12.5px;">
                        <span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">
                          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${meta.color};"></span>
                          ${esc(key)}
                        </span>
                        <span style="font-weight:700;">${count} BN (${pctLabel})</span>
                      </div>
                      <div style="background:#e2e8f0; height:7px; border-radius:4px; overflow:hidden;">
                        <div style="width:${pct ?? 0}%; background:${meta.color}; height:100%;"></div>
                      </div>
                    </div>
                  `;
                }).join("")}
              </div>
            </div>
          </section>
        `;

        // Bind interactive clicks for Chart 1 (ORADS)
        $$(".chart-drilldown-row[data-orads]", chartsContainer).forEach((row) => {
          row.onclick = () => {
            const val = row.getAttribute("data-orads");
            if (state.chartFilter.type === "ORADS" && state.chartFilter.value === val) {
              // Toggle off
              state.chartFilter = { type: null, value: null, label: null };
            } else {
              state.chartFilter = { type: "ORADS", value: val, label: `Phân tầng ${val}` };
            }
            refreshDashboard();
            loadDrilldownCases();
            $("#drilldownSection", target)?.scrollIntoView({ behavior: "smooth", block: "start" });
          };
        });

        // Bind interactive clicks for Chart 2 (Lesion)
        $$(".chart-drilldown-row[data-lesion]", chartsContainer).forEach((row) => {
          row.onclick = () => {
            const val = row.getAttribute("data-lesion");
            if (state.chartFilter.type === "LESION" && state.chartFilter.value === val) {
              // Toggle off
              state.chartFilter = { type: null, value: null, label: null };
            } else {
              state.chartFilter = { type: "LESION", value: val, label: `Mặt bệnh: ${val}` };
            }
            refreshDashboard();
            loadDrilldownCases();
            $("#drilldownSection", target)?.scrollIntoView({ behavior: "smooth", block: "start" });
          };
        });

        // 3. EQUIPMENT QC SUMMARY
        qcContainer.innerHTML = `
          <div class="grid-2">
            <div style="display:flex; flex-direction:column; gap:10px;">
              <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:6px;">
                <span class="muted">Tổng số ảnh nạp vào hệ thống</span>
                <strong>${summary.total_images} ảnh</strong>
              </div>
              <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:6px;">
                <span class="muted">Tổng lượt suy luận mô hình AI</span>
                <strong>${summary.total_predictions} lượt</strong>
              </div>
            </div>
            <div style="display:flex; flex-direction:column; gap:10px;">
              <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:6px;">
                <span class="muted">Điểm sắc nét IQA trung bình</span>
                <strong style="color:#10b981;">${summary.avg_iqa_score} / 1.00</strong>
              </div>
              <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding-bottom:6px;">
                <span class="muted">Tỷ lệ ảnh đạt tiêu chuẩn chẩn đoán</span>
                <strong style="color:#0284c7;">${summary.iqa_pass_rate_pct}%</strong>
              </div>
            </div>
          </div>
        `;

      } catch (err) {
        metricsContainer.innerHTML = errorBox("Không thể tải chỉ số KPI: " + err.message);
        chartsContainer.innerHTML = "";
      }
    };

    // Initial Dashboard Render
    await refreshDashboard();
    await loadDrilldownCases();

    // Event Listeners for Filters
    $("#filterDays", target).onchange = (e) => {
      state.days = e.target.value;
      refreshDashboard();
      loadDrilldownCases();
    };

    $("#filterStatus", target).onchange = (e) => {
      state.status = e.target.value;
      refreshDashboard();
      loadDrilldownCases();
    };

    $("#filterDoctor", target).onchange = (e) => {
      state.doctor_id = e.target.value;
      refreshDashboard();
      loadDrilldownCases();
    };

    // Reset all filters button
    $("#resetFiltersBtn", target).onclick = () => {
      state.days = "";
      state.status = "";
      state.doctor_id = "";
      state.chartFilter = { type: null, value: null, label: null };
      $("#filterDays", target).value = "";
      $("#filterStatus", target).value = "";
      $("#filterDoctor", target).value = "";
      refreshDashboard();
      loadDrilldownCases();
    };

    // Clear only chart filter button
    $("#clearChartFilterBtn", target).onclick = () => {
      state.chartFilter = { type: null, value: null, label: null };
      refreshDashboard();
      loadDrilldownCases();
    };

    // Actions
    $("[data-action=refresh-reports]", target).onclick = () => {
      refreshDashboard();
      loadDrilldownCases();
    };
    $("[data-action=print-report]", target).onclick = () => window.print();

  } catch (err) {
    target.innerHTML = errorBox("Không thể khởi tạo màn hình báo cáo quản trị: " + err.message);
  }
}
