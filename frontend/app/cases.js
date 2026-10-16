import { state, role, restoreDraft } from "./state.js";
import { request } from "./api.js";
import { demoDB } from "./demo.js";
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
export async function getCases() {
  if (state.demo)
    return demoDB.cases.filter((c) =>
      role() === "TK"
        ? !c.department || c.department === state.user.department
        : c.owner_id === state.user.id,
    );
  if (state.capabilities?.case_workflow !== true) {
    const raw = await request("/api/cases");
    const items = Array.isArray(raw) ? raw : (raw.items || []);
    return items.map((c) => ({
      ...c,
      study_id: c.study_id || c.id,
      study_code: c.study_code || c.id,
      patient_id: c.patient_id,
      study_date: c.study_date,
      status: c.status,
      owner_id: null,
      images: Array.isArray(c.images) ? c.images : (c.image_id ? [{ id: c.image_id, laterality: null }] : []),
    }));
  }
  const rows = [],
    scope = role() === "TK" ? "department" : "mine";
  let page = 1,
    total = Infinity;
  while (rows.length < total) {
    const data = await request(
      "/api/workspace/cases?" +
        new URLSearchParams({ scope, page, page_size: 100 }),
    );
    if (
      !Array.isArray(data.items) ||
      !Number.isInteger(data.total) ||
      data.total < 0
    )
      throw Error("Danh sách ca chưa đúng contract phân trang.");
    total = data.total;
    if (total > 10000)
      throw Error(
        "Danh sách quá lớn để tổng hợp trên thiết bị. Cần API tổng hợp dashboard và tra cứu PID.",
      );
    if (!data.items.length && rows.length < total)
      throw Error("Máy chủ trả trang rỗng trước khi hết danh sách.");
    rows.push(...data.items);
    page++;
  }
  return rows;
}
export async function getCase(id) {
  if (state.demo) {
    const c = demoDB.cases.find((c) => c.study_id === id);
    if (!c) throw Error("Không tìm thấy ca.");
    if (
      (role() === "BS" && c.owner_id !== state.user.id) ||
      (role() === "TK" &&
        c.department &&
        c.department !== state.user.department)
    )
      throw Error("Ca không thuộc phạm vi được cấp.");
    return c;
  }
  const c = await request(
    (state.capabilities.case_workflow === true
      ? "/api/workspace/cases/"
      : "/api/cases/") + encodeURIComponent(id),
  );
  for (const image of c.images) {
    image.mask = decode(
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
    image.notes = image.review?.clinical_notes || "";
    image.morphology = image.review?.lesion_type || "";
    image.history = [];
    image.redo = [];
  }
  return c;
}
let caseRequest = 0;
export async function openCase(id) {
  const identity = state.user?.id,
    mode = state.demo;
  const requestId = ++caseRequest;
  if (state.case?.study_id === id) return state.case;
  const c = await getCase(id);
  if (
    requestId !== caseRequest ||
    identity !== state.user?.id ||
    mode !== state.demo
  )
    throw new DOMException("Đã chuyển ca hoặc phiên", "AbortError");
  state.case = c;
  state.dirty = restoreDraft(c);
  state.side = "L";
  return c;
}
export function caseTable(rows, { select = false, action = "viewer" } = {}) {
  if (!rows.length)
    return empty("Không có ca phù hợp", "Thử thay đổi bộ lọc hoặc tạo ca mới.");
  return `<div class="table-wrap"><table><thead><tr>${select ? '<th><input id="selectAll" type="checkbox" aria-label="Chọn tất cả ca trên trang"></th>' : ""}<th>Mã ca / PID</th><th>Hai bên</th><th>Trạng thái</th><th>Ngày khảo sát</th><th>Phụ trách</th><th></th></tr></thead><tbody>${rows.map((c) => `<tr>${select ? `<td><input type="checkbox" class="case-select" value="${esc(c.study_id)}" aria-label="Chọn ${esc(c.study_code)}"></td>` : ""}<td><a href="#case/${encodeURIComponent(c.study_id)}"><strong>${esc(c.study_code || c.study_id)}</strong></a><small>${esc(c.patient_id)}</small></td><td><span class="badge">T ${c.images?.some((i) => i.laterality === "L") ? "✓" : "—"}</span> <span class="badge">P ${c.images?.some((i) => i.laterality === "R") ? "✓" : "—"}</span></td><td>${badge(c.status)}</td><td>${esc(c.study_date)}</td><td>${esc(c.owner_id || "Chưa có")}</td><td><a class="btn small" href="#${action}/${encodeURIComponent(c.study_id)}">${action === "approval" ? "Duyệt ca" : "Mở ca"}</a></td></tr>`).join("")}</tbody></table></div>`;
}
export async function renderCases(root) {
  return (await import("./worklist.js")).renderWorklist(root);
}
export async function renderDashboard(root) {
  const r = role();
  root.innerHTML =
    pageHead(
      "Tổng quan",
      `${{ BS: "Bác sĩ", TK: "Chuyên gia duyệt", QT: "Quản trị hệ thống" }[r]} · ${state.user.department || "Đơn vị nghiên cứu"}`,
      r === "BS"
        ? `<a class="btn primary" href="#intake">Tải ảnh mới</a>`
        : r === "TK"
          ? `<a class="btn primary" href="#approval">Duyệt ca tiếp theo</a>`
          : "",
    ) + `<div id="dashData">${loading()}</div>`;
  try {
    if (r === "QT") {
      const health = state.demo
        ? { status: "Demo" }
        : await request("/api/health");
      $("#dashData").innerHTML =
        `<div class="metrics"><div class="metric"><span>Máy chủ</span><strong>${esc(health.status || "Đã kết nối")}</strong><small>Trạng thái phản hồi hiện tại</small></div><div class="metric"><span>Quyền truy cập</span><strong>QT</strong><small>Không tải ảnh lâm sàng</small></div><div class="metric"><span>Nhật ký</span><strong>Kiểm tra</strong><small><a href="#admin/audit">Mở Audit Trail</a></small></div><div class="metric"><span>Vận hành</span><strong>Hệ thống</strong><small><a href="#admin/system">Mở kiểm tra và sao lưu</a></small></div></div><div class="grid-2"><section class="panel"><div class="panel-head"><h2>Quản trị truy cập</h2></div><div class="panel-body"><p>Kiểm tra tài khoản mới, trạng thái khóa và quyền được cấp.</p><a class="btn" href="#admin/users">Quản lý tài khoản</a></div></section><section class="panel"><div class="panel-head"><h2>Mô hình đang phục vụ</h2></div><div class="panel-body"><p>Xác minh checkpoint, phiên bản và trạng thái nạp.</p><a class="btn" href="#admin/models">Danh mục mô hình</a></div></section></div>`;
      return;
    }
    const rows = await getCases();
    const pending = rows.filter((c) =>
        ["IN_REVIEW", "AI_DONE", "REJECTED"].includes(c.status),
      ),
      waiting = rows.filter((c) => c.status === "SIGNED_PRELIM");
    $("#dashData").innerHTML = `<div class="metrics">${[
      [
        "Ca hôm nay",
        rows.filter(
          (c) => c.study_date === new Date().toISOString().slice(0, 10),
        ).length,
        "Theo ngày khảo sát",
      ],
      ["Đang rà soát", pending.length, "Cần tiếp tục xử lý"],
      ["Chờ duyệt", waiting.length, "Đã ký sơ bộ"],
      [
        "Bị từ chối",
        rows.filter((c) => c.status === "REJECTED").length,
        "Cần bổ sung rà soát",
      ],
    ]
      .map(
        (m) =>
          `<div class="metric"><span>${m[0]}</span><strong>${m[1]}</strong><small>${m[2]}</small></div>`,
      )
      .join(
        "",
      )}</div><div class="two-col"><section class="panel"><div class="panel-head"><h2>${r === "TK" ? "Hàng chờ duyệt" : "Tiếp tục công việc"}</h2><a href="#cases">Xem tất cả</a></div>${caseTable((r === "TK" ? waiting : pending).slice(0, 5), { action: r === "TK" ? "approval" : "viewer" })}</section><section class="panel"><div class="panel-head"><h2>Quy trình rà soát</h2></div><div class="panel-body"><ol class="timeline"><li><strong>Hai ảnh, hai bên</strong><small>Kiểm tra rõ nhãn Trái / Phải.</small></li><li><strong>Quan sát trước khi xác nhận</strong><small>Đối chiếu đường biên với ảnh gốc.</small></li><li><strong>Kiểm tra hiệu chuẩn</strong><small>Thiếu spacing chỉ hiển thị pixel.</small></li><li><strong>Lưu và chuyển duyệt</strong><small>Mỗi thay đổi có phiên bản và người thực hiện.</small></li></ol></div></section></div>`;
  } catch (e) {
    $("#dashData").innerHTML = errorBox(e.message);
    $("[data-action=retry]").onclick = () => renderDashboard(root);
  }
}
export async function renderCaseDetail(root, id) {
  root.innerHTML = loading();
  try {
    const c = await openCase(id);
    root.innerHTML =
      `<div class="breadcrumb"><a href="#cases">Danh sách ca</a> / ${esc(c.study_code || c.study_id)}</div>` +
      pageHead(
        c.study_code || c.study_id,
        c.patient_id,
        `<a class="btn" href="#report/${id}">Phiếu kết quả</a><a class="btn primary" href="#viewer/${id}">Mở workstation</a>`,
      ) +
      `<div class="two-col"><section class="panel"><div class="panel-head"><h2>Thông tin khảo sát</h2>${badge(c.status)}</div><div class="panel-body"><div class="grid-2"><div><p class="muted">PID ẩn danh</p><h2>${esc(c.patient_id)}</h2></div><div><p class="muted">Ngày khảo sát</p><h2>${esc(c.study_date)}</h2></div></div><p>${esc(c.clinical_indication || "Chưa ghi nhận lý do")}</p><p>Phiên bản ${c.version || "chưa có dữ liệu"}</p>${c.reason ? `<div class="banner warning">${esc(c.reason)}</div>` : ""}</div></section><section class="panel"><div class="panel-head"><h2>Dòng thời gian</h2></div><div class="panel-body"><ol class="timeline">${(c.timeline || []).map((t) => `<li><strong>${esc(t.action)}</strong><small>${esc(t.actor)} · ${esc(t.at)}</small><p>${esc(t.reason)}</p></li>`).join("") || "<li>Máy chủ chưa cung cấp lịch sử trạng thái.</li>"}</ol></div></section></div><section class="panel" style="margin-top:24px"><div class="panel-head"><h2>Lịch sử phiên bản và bản bổ sung</h2></div><div class="panel-body">${(c.versions || []).map((v) => `<p>Phiên bản ${v.version} · Bản lưu trước bổ sung · ${v.images.length} ảnh</p>`).join("") || empty("Chưa có bản bổ sung", "Phiên bản cũ được giữ khi tạo bản bổ sung sau khóa.")}</div></section>`;
  } catch (e) {
    root.innerHTML = errorBox(e.message);
    $("[data-action=retry]").onclick = () => renderCaseDetail(root, id);
  }
}
