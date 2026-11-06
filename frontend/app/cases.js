import { state, role, restoreDraft } from "./state.js";
import { request } from "./api.js";

import { decode } from "./coordinates.js";
import {
  $,
  $$,
  esc,
  button,
  badge,
  pageHead,
  empty,
  loading,
  errorBox,
  toast,
  csv,
  download,
  field,
} from "./ui.js";
import { statusLabels } from "./i18n.js";
import { patientRecordLabel, researchIdentifierLabel } from "./patient-labels.js";
import { startCorrection } from "./corrections.js";
function normalizeCase(c) {
  return {
    ...c,
    study_id: c.study_id || c.id,
    study_code: c.study_code || c.id,
    images: Array.isArray(c.images)
      ? c.images.map((image) => ({
          ...image,
          image_id: image.image_id || image.id,
        }))
      : c.image_id
        ? [{ id: c.image_id, image_id: c.image_id, laterality: null }]
        : [],
  };
}

export async function getCasesPage(
  params = {},
  { signal, limit = 10, offset = 0, sort = "created_at", direction = "desc" } = {},
) {
  const raw = await request("/api/workspace/cases/search", {
    method: "POST",
    body: {
      search: params.search || params.q || null,
      patient_id: params.patient_id || null,
      status: params.status && params.status !== "ALL" ? params.status : null,
      statuses: params.statuses || null,
      date: params.date || null,
      limit,
      offset,
      sort,
      direction,
    },
    signal,
  });
  if (
    !Array.isArray(raw?.items) ||
    !Number.isInteger(raw.total) ||
    raw.total < 0 ||
    raw.items.length > limit
  )
    throw Error("Danh sách ca trả về không đúng hợp đồng phân trang.");
  return { items: raw.items.map(normalizeCase), total: raw.total };
}
export async function getCase(id) {
  const c = await request(
    (state.capabilities.case_workflow === true
      ? "/api/workspace/cases/"
      : "/api/cases/") + encodeURIComponent(id),
  );
  const correctionDrafts = new Map(
    (c.correction_draft?.images || []).map((row) => [row.image_id, row]),
  );
  for (const image of c.images) {
    const correctionDraft = correctionDrafts.get(image.image_id);
    image.mask = decode(
      correctionDraft?.verified_mask_rle ||
        image.review?.verified_mask_rle ||
        image.prediction?.rle_mask || {
          shape: [512, 512],
          first_val: 0,
          counts: [262144],
        },
    );
    image.aiMask = decode(
      image.prediction?.rle_mask || {
        shape: [512, 512],
        first_val: 0,
        counts: [262144],
      },
    );
    image.notes = correctionDraft?.notes ?? image.review?.clinical_notes ?? "";
    image.morphology = correctionDraft?.morphology ?? image.review?.lesion_type ?? "";
    image.morphologyDesc = image.review?.morphology_description || image.review?.hitl_feedback?.morphologyDesc || "";
    image.orads = image.review?.orads || image.review?.orads_score || image.review?.hitl_feedback?.orads || "";
    image.history = [];
    image.redo = [];
  }
  return c;
}
let caseRequest = 0;
export async function openCase(id) {
  const identity = state.user?.id;
  const requestId = ++caseRequest;
  const c = await getCase(id);
  if (requestId !== caseRequest || identity !== state.user?.id)
    throw new DOMException("Đã chuyển ca hoặc phiên", "AbortError");
  state.case = c;
  state.dirty = restoreDraft(c);
  state.side = "L";
  return c;
}
export function caseTable(rows, { select = false, action = "viewer" } = {}) {
  if (!rows.length)
    return empty("Không có ca phù hợp", "Thử thay đổi bộ lọc hoặc tạo ca mới.");
  return `<div class="table-wrap"><table><thead><tr>${select ? '<th><input id="selectAll" type="checkbox" aria-label="Chọn tất cả ca trên trang"></th>' : ""}<th>Mã ca</th><th>Hai bên</th><th>Trạng thái</th><th>Ngày khảo sát</th><th></th></tr></thead><tbody>${rows.map((c) => `<tr>${select ? `<td><input type="checkbox" class="case-select" value="${esc(c.study_id)}" aria-label="Chọn ${esc(c.study_code)}"></td>` : ""}<td><a href="#case/${encodeURIComponent(c.study_id)}"><strong>${esc(c.study_code || c.study_id)}</strong></a><small>${esc(patientRecordLabel(c))}</small></td><td><span class="badge">T ${c.images?.some((i) => i.laterality === "L") ? "✓" : "—"}</span> <span class="badge">P ${c.images?.some((i) => i.laterality === "R") ? "✓" : "—"}</span></td><td>${badge(c.status)}</td><td>${esc(c.study_date)}</td><td><a class="btn small" href="#${action}/${encodeURIComponent(c.study_id)}">${action === "approval" ? "Đối chiếu rà soát" : "Mở ca"}</a></td></tr>`).join("")}</tbody></table></div>`;
}
export async function renderCases(root) {
  return (await import("./worklist.js")).renderWorklist(root);
}
export async function renderDashboard(root) {
  const r = role();
  root.innerHTML =
    pageHead(
      "Tổng quan",
      `${{ BS: "Bác sĩ", TK: "Chuyên gia rà soát", QT: "Quản trị hệ thống" }[r]} · ${state.user.department || "Đơn vị công tác"}`,
      r === "BS"
        ? `<a class="btn primary" href="#intake">Tải ảnh mới</a>`
        : r === "TK"
          ? `<a class="btn primary" href="#approval">Mở hàng chờ rà soát</a>`
          : `<a class="btn primary" href="#admin/reports">Báo cáo Quản trị</a>`,
    ) + `<div id="dashData">${loading()}</div>`;
  try {
    if (r === "QT") {
      const [health, summary] = await Promise.all([
        request("/api/health").catch(() => ({ status: "Đã kết nối" })),
        request("/api/admin/analytics/summary").catch(() => null),
      ]);
      const s = summary || {
        total_cases: 0,
        completed_cases: 0,
        overall_consensus_rate_pct: 0,
        avg_iqa_score: 0,
        iqa_pass_rate_pct: 0,
      };
      $("#dashData").innerHTML =
        `<div class="metrics"><div class="metric"><span>Tổng ca khám</span><strong>${s.total_cases}</strong><small>${s.completed_cases} hoàn thành</small></div><div class="metric"><span>Đồng thuận AI</span><strong style="color:#0284c7;">${s.overall_consensus_rate_pct}%</strong><small>Chấp thuận nguyên bản</small></div><div class="metric"><span>Chất lượng IQA</span><strong style="color:#10b981;">${s.avg_iqa_score}</strong><small>Đạt chuẩn: ${s.iqa_pass_rate_pct}%</small></div><div class="metric"><span>Máy chủ</span><strong>${esc(health.status || "Hoạt động")}</strong><small><a href="#admin/system">Kiểm tra / sao lưu</a></small></div></div><div class="grid-2"><section class="panel"><div class="panel-head"><h2>Trung tâm Báo cáo Quản trị (MIS BI)</h2></div><div class="panel-body"><p>Xem chi tiết 4 phân hệ báo cáo: Năng suất Bác sĩ, Phân tầng O-RADS, Kiểm chuẩn IQA và Thời gian quy trình.</p><div class="actions" style="margin-top:12px;"><a class="btn primary" href="#admin/reports">Mở Báo cáo Quản trị</a></div></div></section><section class="panel"><div class="panel-head"><h2>Quản trị Vận hành & Phân quyền</h2></div><div class="panel-body"><p>Quản lý tài khoản bác sĩ, cấu hình khoa phòng, danh mục mô hình U-Net và nhật ký Audit Trail.</p><div class="actions" style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;"><a class="btn" href="#admin/users">Người dùng</a><a class="btn" href="#admin/models">Mô hình AI</a><a class="btn" href="#admin/audit">Audit Trail</a></div></div></section></div>`;
      return;
    }
    const localToday = (() => {
      const d = new Date();
      return [
        d.getFullYear(),
        String(d.getMonth() + 1).padStart(2, "0"),
        String(d.getDate()).padStart(2, "0"),
      ].join("-");
    })();
    const queue = r === "TK" ? "reviewer" : "doctor";
    const summary = await request(
      "/api/workspace/dashboard/summary?" +
        new URLSearchParams({ date: localToday, queue }),
    );
    const { counts, items } = summary;
    const pending = queue === "doctor" ? items : [];
    const waiting = queue === "reviewer" ? items : [];
    $("#dashData").innerHTML = `<div class="metrics">${[
      [
        "Ca hôm nay",
        counts.today,
        "Theo ngày khảo sát",
      ],
      ["Đang rà soát", counts.pending, "Cần tiếp tục xử lý"],
      ["Chờ đối chiếu", counts.waiting, "Danh sách ca chờ xem xét"],
    ]
      .map(
        (m) =>
          `<div class="metric"><span>${m[0]}</span><strong>${m[1]}</strong><small>${m[2]}</small></div>`,
      )
      .join(
        "",
      )}</div><div class="two-col"><section class="panel"><div class="panel-head"><h2>${r === "TK" ? "Hàng chờ rà soát" : "Tiếp tục công việc"}</h2><a href="#cases">Xem tất cả</a></div>${caseTable((r === "TK" ? waiting : pending).slice(0, 5), { action: r === "TK" ? "approval" : "viewer" })}</section><section class="panel"><div class="panel-head"><h2>Quy trình rà soát</h2></div><div class="panel-body"><ol class="timeline"><li><strong>Hai ảnh, hai bên</strong><small>Kiểm tra rõ nhãn Trái / Phải.</small></li><li><strong>Quan sát trước khi xác nhận</strong><small>Đối chiếu đường biên với ảnh gốc.</small></li><li><strong>Kiểm tra hiệu chuẩn</strong><small>Thiếu spacing chỉ hiển thị pixel.</small></li><li><strong>Lưu kết quả đánh giá</strong><small>Lưu vết thao tác và xác nhận của bác sĩ.</small></li></ol></div></section></div>`;
  } catch (e) {
    $("#dashData").innerHTML = errorBox(e.message);
    $("[data-action=retry]").onclick = () => renderDashboard(root);
  }
}
export async function renderCaseDetail(root, id) {
  root.innerHTML = loading();
  try {
    const c = await openCase(id);
    let correctionTechnicians = [];
    if (role() === "BS" && !c.correction_status) {
      correctionTechnicians = await request(
        `/api/workspace/cases/${encodeURIComponent(c.study_id)}/correction-technicians`,
      );
    }
    const correctionSection = role() !== "BS"
      ? ""
      : c.correction_status === "PENDING"
        ? `<section class="panel" style="margin-top:24px"><div class="panel-body"><strong>Đang chờ TK hiệu chỉnh</strong><p>${esc(c.correction_reason || "")}</p></div></section>`
        : c.correction_status === "SUBMITTED"
          ? `<section class="panel" style="margin-top:24px"><div class="panel-body"><strong>Bản hiệu chỉnh đã gửi, cần bác sĩ rà soát lại</strong><p>${esc(c.correction_reason || "")}</p><a class="btn primary" href="#viewer/${encodeURIComponent(c.study_id)}">Mở workstation để rà soát</a></div></section>`
          : `<section class="panel" id="correctionPanel" style="margin-top:24px"><div class="panel-head"><h2>Yêu cầu TK hiệu chỉnh</h2></div><div class="panel-body"><label class="field"><span>TK được giao</span><select id="correctionTechnician" required><option value="">Chọn TK</option>${correctionTechnicians.map((user) => `<option value="${esc(user.id)}">${esc(user.name)}</option>`).join("")}</select></label><label class="field"><span>Lý do hiệu chỉnh</span><textarea id="correctionReason" maxlength="1000" required></textarea></label><button class="btn primary" id="createCorrection" type="button" ${correctionTechnicians.length ? "" : "disabled"}>Gửi yêu cầu</button>${correctionTechnicians.length ? "" : '<p class="muted">Không có TK đang hoạt động trong cùng cơ sở.</p>'}</div></section>`;
    const patientSummary = c.patient_name
      ? `Hồ sơ tại cơ sở: ${c.patient_name} · ${researchIdentifierLabel(c.patient_id)}`
      : researchIdentifierLabel(c.patient_id);
    root.innerHTML =
      `<div class="breadcrumb"><a href="#cases">Danh sách ca</a> / ${esc(c.study_code || c.study_id)}</div>` +
      pageHead(
        c.study_code || c.study_id,
        `${patientSummary} · Visit No ${c.visit_no || "Chưa cấp"}`,
        `<a class="btn" href="#report/${id}">Phiếu kết quả</a><a class="btn primary" href="#viewer/${id}">Mở workstation</a>`,
      ) +
      `<div class="two-col"><section class="panel"><div class="panel-head"><h2>Thông tin khảo sát</h2>${badge(c.status)}</div><div class="panel-body"><div class="grid-2"><div><p class="muted">Hồ sơ tại cơ sở</p><h2>${esc(c.patient_name || "Không gắn hồ sơ")}</h2></div><div><p class="muted">Mã nghiên cứu (giả danh)</p><h2>${esc(c.patient_id || "Chưa cấp")}</h2></div><div><p class="muted">Ngày khảo sát</p><h2>${esc(c.study_date)}</h2></div><div><p class="muted">Tuổi đã ghi nhận</p><h2>${esc(c.patient_age || "Chưa ghi nhận")}</h2></div></div><p>${esc(c.clinical_indication || "Chưa ghi nhận lý do")}</p><p>Phiên bản ${c.review_revision ?? 0}</p>${c.reason ? `<div class="banner warning">${esc(c.reason)}</div>` : ""}</div></section><section class="panel"><div class="panel-head"><h2>Dòng thời gian</h2></div><div class="panel-body"><ol class="timeline">${(c.timeline || []).map((t) => `<li><strong>${esc(t.action)}</strong><small>${esc(t.actor)} · ${esc(t.at)}</small><p>${esc(t.reason)}</p></li>`).join("") || "<li>Máy chủ chưa cung cấp lịch sử trạng thái.</li>"}</ol></div></section></div>${correctionSection}<section class="panel" style="margin-top:24px"><div class="panel-head"><h2>Lịch sử phiên bản và bản bổ sung</h2></div><div class="panel-body">${(c.versions || []).map((v) => `<p>Phiên bản ${v.version} · Bản lưu trước bổ sung · ${v.images.length} ảnh</p>`).join("") || empty("Chưa có bản bổ sung", "Phiên bản cũ được giữ khi tạo bản bổ sung sau khóa.")}</div></section>`;
    const createCorrectionButton = $("#createCorrection", root);
    if (createCorrectionButton) {
      createCorrectionButton.onclick = async () => {
        createCorrectionButton.disabled = true;
        try {
          await startCorrection(
            c,
            $("#correctionTechnician", root).value,
            $("#correctionReason", root).value,
          );
        } catch (error) {
          toast(error.message, true);
          createCorrectionButton.disabled = false;
        }
      };
    }
  } catch (e) {
    root.innerHTML = errorBox(e.message);
    $("[data-action=retry]").onclick = () => renderCaseDetail(root, id);
  }
}
