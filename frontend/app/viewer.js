import { acquireLease } from "./leases.js";
import { organizeAssessment } from "./assessment-layout.js";
import { classificationText, classificationNote } from "./image-classification.js";
import { logout } from "./auth.js";
import { saveCorrection } from "./corrections.js";
import { state, role, setBusy, saveDraft, saveMaskDraft, restoreMaskDrafts, keepServerVersion } from "./state.js";
import { openCase } from "./cases.js";
import { patientRecordLabel } from "./patient-labels.js";
import { protectedImage, request } from "./api.js";
import { letterbox, screenToModel, encode, decode } from "./coordinates.js";
import { cleanMask, components } from "./mask-tools.js";
import {
  $,
  $$,
  esc,
  button,
  icon,
  badge,
  loading,
  errorBox,
  toast,
  confirmAction,
  modal,
  field,
  download,
} from "./ui.js";
import { openSignoff, saveResearchReview } from "./review.js";
import { tracker, trackUIEvent } from "./hitl-tracker.js";
import { imageSourceBitmap } from "./image-source.js";
import { adnexPanelMarkup, bindAdnexPanel } from "./adnex.js";
import { bindCdssPanel, cdssPanelMarkup } from "./cdss-panel.js";
import { applyCalibrationAck, manualCaliperLength as measuredCaliperLength, unavailableMeasurements } from "./measurement-fallback.js";
import { LatestMeasurementQueue } from "./latest-measurement-queue.js";
import { bindResearchCandidate, researchCandidateMarkup } from "./research-candidate.js";
import { bindRegionReview } from "./region-review.js";
import { loadUncertaintyMap } from "./uncertainty-map.js";
import { bindLocalDictation } from "./voice-dictation.js";
import { getReportShortcutHash, getOradsShortcutValue, isAutoZoomShortcut, isUndoShortcut } from "./viewer-shortcuts.js";
import { expandDraftPhrase } from "./draft-phrases.js";
import { reviewWarnings, consistencyKey } from "./review-content.js";
let active = null;
const ORADS1_OPTION_LABEL =
  "O-RADS 1 - Không có tổn thương hoặc nang sinh lý do bác sĩ xác định (nang noãn < 30 mm; hoàng thể thường ≤ 30 mm)";
const ORADS0_OPTION_LABEL =
  "O-RADS 0 - Đánh giá chưa đầy đủ do yếu tố kỹ thuật (chưa phân tầng nguy cơ)";
export function currentViewer() {
  return active;
}
export async function renderViewer(root, id, { readonly = false } = {}) {
  root.innerHTML = loading();
  let disposed = false,
    cleanup = () => {};
  try {
    const c = await openCase(id);
    if (!root.isConnected) return;
    if (restoreMaskDrafts(c).length) {
      toast("Đã phục hồi bản nháp chưa lưu gần nhất");
    }
    if (state.unattributedMaskDraft) {
      toast("Phát hiện bản nháp mask cũ không ghi nhận người tạo; hệ thống không khôi phục để tránh dùng nhầm. Dữ liệu cũ vẫn được giữ trên thiết bị.", true);
    }
    const correction = role() === "TK" && c.correction_status === "PENDING" && c.correction_by === state.user.id;
    const recordUiEvent = (...args) => { if (!correction) trackUIEvent(...args); };
    readonly =
      readonly ||
      (!correction && role() !== "BS") ||
      ["LOCKED", "SIGNED_PRELIM", "APPROVED"].includes(c.status) ||
      (c.correction_by && !correction);
    readonly = readonly || state.draftConflict?.caseId === c.study_id;
    let lease = null;
    if (!readonly) {
      lease = await acquireLease(c.study_id, (message) => {
        readonly = true;
        if (state.editing?.caseId === c.study_id) state.editing.allowed = false;
        toast(message, true);
        window.dispatchEvent(new CustomEvent("ova:lease-lost"));
      });
      readonly = !lease.editable;
    }
    if (!root.isConnected) {
      lease?.release();
      return;
    }
    state.editing = {
      caseId: c.study_id,
      allowed: !readonly,
      leaseToken: lease?.leaseToken?.() ?? null,
      pageInstanceId: lease?.pageInstanceId ?? null,
    };
    if (lease?.editable && !correction) {
      const telemetryLeaseHeaders = {
        "X-Case-Lease-Token": lease.leaseToken(),
        "X-Case-Page-Instance-Id": lease.pageInstanceId,
      };
      tracker
        .flushPendingEvents(c.study_id, telemetryLeaseHeaders, state.user?.id)
        .then(({ replayedEventCount, skippedSessionCount }) => {
          if (state.pendingReviewTelemetryAck?.studyId === c.study_id)
            state.pendingReviewTelemetryAck = null;
          if (replayedEventCount > 0)
            toast("Đã khôi phục và đồng bộ nhật ký HITL của phiên trước.");
          if (skippedSessionCount > 0)
            console.warn("Pending HITL events belong to another signed-in user.");
        })
        .catch((error) => {
          if (error?.name === "AbortError") return;
          console.warn("Pending HITL telemetry replay failed:", error);
          toast("Nhật ký HITL của phiên trước chưa đồng bộ; thử lại khi mở lại ca.", true);
        });
    }
    const workflowEnabled = state.capabilities?.case_workflow === true;
    const workflowStage =
      workflowEnabled
        ? "<li>Ký sơ bộ hai bên</li>"
        : "<li>Lưu kết quả rà soát</li>";
    const signLabel = workflowEnabled ? "Ký sơ bộ" : "Ký sơ bộ (chưa khả dụng)";
    const toolButtonMarkup = (tools) =>
      tools
        .map(
          ([action, glyph, label]) =>
            '<button type="button" class="icon-btn" data-tool="' +
            action +
            '" title="' +
            esc(label) +
            '" aria-label="' +
            esc(label) +
            '">' +
            icon(glyph) +
            "</button>",
        )
        .join("");
    const primaryTools = [
      ["brush", "brush", "Cọ vẽ (B)"],
      ["erase", "erase", "Tẩy (E)"],
      ["auto-zoom", "fit", "Auto-Zoom tổn thương (A)"],
      ["caliper-d1", "ruler", "Caliper D1 (C)"],
      ["caliper-d2", "ruler", "Caliper D2"],
      ["pan", "hand", "Di chuyển (H)"],
      ["fit", "fit", "Vừa khung (0)"],
    ];
    const historyTools = [
      ["undo", "undo", "Hoàn tác"],
      ["redo", "history", "Làm lại"],
      ["reset", "history", "Về mask AI (R)"],
    ];
    const advancedTools = [
      ["polygon", "polygon", "Đa giác (L · G hoàn tất)"],
      ["fill", "plus", "Lấp lỗ"],
      ["smooth", "settings", "Làm trơn (S)"],
      ["small", "grid", "Xóa mảnh nhỏ"],
      ["clear", "close", "Xóa toàn bộ mask"],
      ["fullscreen", "fit", "Toàn màn hình (F)"],
    ];
    root.innerHTML = `<div class="viewer-head">
      <div class="viewer-id">
        <a class="icon-btn" href="#cases" aria-label="Về danh sách">${ icon("list")}</a>
        <div class="viewer-case-meta">
          <strong class="case-code">${ esc(c.study_code || c.study_id)}</strong>
          <span class="muted small case-pid">${esc(patientRecordLabel(c))}</span>
        </div>
        ${ badge(c.status)}
      </div>
      <div class="side-switch" role="group" aria-label="Buồng trứng đang xem">
        ${ button("Trái (T)", "side-L", "small primary")}
        ${ button("Phải (P)", "side-R", "small")}
        <label class="visually-hidden" for="viewerImageSelect">Ảnh hoặc mặt cắt đang xem</label>
        <span class="viewer-image-select-wrap">
          <span id="viewerImageSelectCurrent" class="viewer-image-select-current" aria-hidden="true"></span>
          <select id="viewerImageSelect" aria-label="Ảnh hoặc mặt cắt đang xem"></select>
        </span>
      </div>
      <div class="viewer-head-actions actions">
        ${ button("Lưu rồi in", "quick-print", "small primary viewer-quick-print-action", "print")}
        ${ button("Xem phiếu", "report", "small quiet viewer-report-action")}
        ${ button("?", "shortcuts-help", "small quiet viewer-help-action")}
        <div class="viewer-save-action">
          ${ button("Lưu kết quả đánh giá", "save-review", "quiet")}
          <kbd>Ctrl+S</kbd>
        </div>
        <details class="viewer-more-actions">
          <summary class="icon-btn" aria-label="Thao tác khác" title="Thao tác khác">${ icon("menu")}</summary>
          <div class="viewer-more-menu">
            ${ button("Tải kết quả tham khảo", "export-research", "small")}
            ${ button(signLabel, "sign", "small")}
            ${ correction ? button("Lưu phiên bản sửa", "save-correction", "small") : ""}
            ${ button("Đăng xuất", "logout", "small")}
          </div>
        </details>
        ${ button("Lâm sàng", "panel-toggle", "small viewer-panel-toggle", "users")}
      </div>
    </div>
    <div class="viewer-grid">
      <section class="viewer-center">
        <div class="viewport-wrap">
          <div class="canvas-pane" id="pane">
            <p id="viewerImageSummary" class="visually-hidden" role="status" aria-live="polite"></p>
            <div id="brushCursorV2" class="brush-cursor" hidden></div>
            <canvas id="viewport" tabindex="0" aria-describedby="viewerImageSummary" aria-label="Khung ảnh phân đoạn, phím B vẽ, E tẩy, H di chuyển"></canvas>
          </div>
          <div class="canvas-pane" id="secondPane" hidden>
            <canvas id="secondViewport" aria-describedby="viewerImageSummary" aria-label="Ảnh gốc đối chiếu"></canvas>
            <span class="canvas-label">Đối chiếu ảnh gốc</span>
          </div>
          <aside class="toolrail" aria-label="Công cụ chỉnh mask">
            <div class="tool-group" role="group" aria-label="Công cụ chính">${ toolButtonMarkup(primaryTools)}</div>
            <div class="tool-group" role="group" aria-label="Lịch sử chỉnh sửa">${ toolButtonMarkup(historyTools)}</div>
            <details class="tool-more">
              <summary class="icon-btn" aria-label="Công cụ nâng cao" title="Công cụ nâng cao">${ icon("settings")}</summary>
              <div class="tool-more-menu">${ toolButtonMarkup(advancedTools)}</div>
            </details>
          </aside>
          <div class="viewer-hud" aria-label="Thông tin ảnh và số đo">
            <span class="canvas-label" id="sideLabel">Buồng trứng trái · giữ Space xem ảnh gốc</span>
            <div class="measure-strip">
              <div class="measure-values pixel" id="measureValues">
                <div><small>d₁</small><strong id="d1">—</strong></div>
                <div><small>d₂</small><strong id="d2">—</strong></div>
                <div><small>Diện tích</small><strong id="area">—</strong></div>
              </div>
              <div class="calibration-controls">
                <span class="badge" id="calibrationBadge" style="display:none"></span>
                ${ button("Hiệu chuẩn thước", "calibrate", "small")}
              </div>
            </div>
          </div>
        </div>
        <div class="viewer-controls">
          <div class="layer-controls" role="group" aria-label="Chế độ xem ảnh">
            ${ ["Gốc", "Mask", "Lớp phủ"].map((label, index) => button(label, "layer-" + index, "small")).join("")}
            <button type="button" class="btn small" data-action="overlay-visibility" aria-label="Hiện/ẩn lớp phủ AI" aria-pressed="false" title="Hiện hoặc ẩn lớp phủ AI">Lớp phủ AI</button>
            <button type="button" class="btn small" data-action="rerun-ai-model" id="btnRerunAI" title="Chạy suy luận lại bằng mô hình và thiết lập tiền xử lý đã chọn">Chạy lại AI</button>
          </div>
          <details class="view-more">
            <summary class="btn small">Đối chiếu</summary>
            <div class="view-more-menu">
              ${ button("Đường viền", "contour", "small")}
              ${ button("Đối chiếu gốc", "compare", "small")}
              ${ button("Hai bên", "bilateral", "small")}
              ${ button("Mask AI", "ai-compare", "small")}
            </div>
          </details>
          <details class="viewer-adjustments" id="viewerAdjustments">
            <summary class="btn small">Điều chỉnh</summary>
            <div class="viewer-adjustments-popover" id="viewerAdjustmentsPopover">
              <label class="range-row">Cọ <input type="range" id="brushSize" min="2" max="64" value="16" aria-label="Cỡ cọ"><output id="brushOutput">16</output></label>
              <label class="range-row">Độ mờ<input id="opacity" type="range" min="0" max="100" value="35" aria-label="Độ mờ lớp phủ"></label>
              <label class="range-row">Sáng<input type="range" id="brightness" min="50" max="180" value="100"></label>
              <label class="range-row">Tương phản<input type="range" id="contrast" min="50" max="180" value="100"></label>
              <label class="range-row toggle-row" style="display:flex;align-items:center;gap:6px;cursor:pointer;">
                <input type="checkbox" id="caliperDenoiseToggle">
                <span>Lọc đốm để đối chiếu (chỉ hiển thị)</span>
              </label>
              ${ button("Mặc định", "image-reset", "small")}
              <span class="muted small" id="draftStatus">Bản nháp trên thiết bị</span>
            </div>
          </details>
        </div>
      </section>
      <aside class="viewer-panel" aria-label="Thông tin lâm sàng">
        <h3>Thông tin lâm sàng</h3>
        <section class="viewer-tabpanel" id="clinicalPanel" aria-label="Thông tin lâm sàng">
          <div class="clinical-panel-notices">
            <div id="localReviewDraftNotice" class="banner warning small local-review-draft-notice" ${state.dirty && !state.draftConflict ? "" : "hidden"} role="status" aria-live="polite">
              Bản nháp trên thiết bị chưa được lưu lên máy chủ.
            </div>
            <div id="leaseLostNotice" class="banner warning small lease-lost-notice" ${lease && !lease.editable ? "" : "hidden"} role="alert" aria-live="assertive">
              <span>${lease && !lease.editable ? esc(lease.label) : "Mất kết nối hoặc quyền chỉnh sửa đã hết hạn."} Bản nháp được lưu trên thiết bị nếu trình duyệt cho phép. Tải lại sẽ thử cấp lease; bản nháp chỉ khôi phục tự động khi revision chưa đổi.</span>
              ${button("Tải lại ca và thử tiếp", "lease-reload", "small")}
            </div>
            ${ lease && lease.label ? '<div class="banner info small">' + esc(lease.label) + "</div>" : ""}
            ${ c.reason ? '<div class="banner warning small">Yêu cầu sửa: ' + esc(c.reason) + "</div>" : ""}
            ${ state.draftConflict ? '<div class="banner warning small">Bản nháp dựa trên phiên bản cũ. Đang hiển thị bản máy chủ.' + button("Tải bản nháp cũ", "download-conflict", "small") + button("Giữ bản máy chủ", "keep-server", "small") + "</div>" : ""}
          </div>
          <div id="viewerWarnings"></div>
          <p id="assessmentSaveStatus" class="small" role="status" aria-label="Trạng thái đánh giá" aria-live="polite">Chưa lưu</p>
          <h3>Phân loại hình thái &amp; nguy cơ</h3>
          <label class="field">Hình thái tổn thương
            <select id="iotaMorphology">
              <option value="">-- Chọn hình thái --</option>
              <option value="Nang đơn thùy dịch trong">Nang đơn thùy dịch trong (Unilocular Anechoic)</option>
              <option value="Nang nhiều thùy">Nang nhiều thùy (Multilocular)</option>
              <option value="Nang đơn thùy có phần đặc">Nang đơn thùy có phần đặc (Unilocular-Solid)</option>
              <option value="Nang nhiều thùy có phần đặc">Nang nhiều thùy có phần đặc (Multilocular-Solid)</option>
              <option value="Khối u đặc">Khối u đặc (Solid Tumor)</option>
            </select>
          </label>
          <label class="field">Phân tầng ACR O-RADS do bác sĩ chọn
            <select id="oradsScore" aria-describedby="oradsHelp">
              <option value="">Chưa đánh giá</option>
              <option value="O-RADS 1">O-RADS 1 - Bình thường / Nang sinh lý (&lt;30 mm)</option>
              <option value="O-RADS 2">O-RADS 2 - Lành tính (&lt;1% nguy cơ)</option>
              <option value="O-RADS 3">O-RADS 3 - Nguy cơ thấp (1% - &lt;10%)</option>
              <option value="O-RADS 4">O-RADS 4 - Nguy cơ trung bình (10% - &lt;50%)</option>
              <option value="O-RADS 5">O-RADS 5 - Nguy cơ cao (≥50%)</option>
            </select>
          </label>
          <p id="oradsHelp" class="muted small">Lựa chọn này do bác sĩ nhập; hệ thống không tự suy luận O-RADS. Để trống khi chưa đủ thông tin.</p>
          <details id="follicleReference"><summary>Điều kiện áp dụng</summary><p class="muted small">Đối chiếu nang noãn &lt;30 mm cần bác sĩ xác nhận hình thái và tình trạng tiền mãn kinh; mốc đúng 30 mm chưa được policy dự án tự phân tầng. Thiếu dữ liệu thì chưa phân tầng.</p></details>
          <div class="chips clinical-morphology-chips">${ ["Dạng nang", "Dạng đặc", "Hỗn hợp", "Bóng cản âm"].map((label) => '<button type="button" class="chip" data-chip="' + esc(label) + '">' + esc(label) + "</button>").join("")}<span id="customChipsWrap"></span><button type="button" class="chip chip-add" data-action="add-chip" title="Thêm đặc điểm mới">+ Thêm</button></div>
          <label class="field">Mô tả hình thái
            <input id="morphology" maxlength="100" placeholder="Chi tiết âm vang, vách ngăn...">
          </label>
          <label class="field">Nhận định của bác sĩ
            <textarea id="notes" rows="2" placeholder="Kết luận hoặc lưu ý theo dõi..."></textarea>
          </label>
          <div id="reviewContentWarning" class="banner warning small" hidden>
            <p id="reviewContentWarningText" role="alert"></p>
            <label id="reviewContentAckLabel"><input type="checkbox" id="reviewContentAck"> Tôi đã kiểm tra nhận định và bối cảnh của ghi chú/O-RADS.</label>
          </div>
          <div class="field small" id="localDictation">
            <button class="btn small" type="button" id="dictationRecord" aria-label="Nhập bằng giọng nói" title="Nhập bằng giọng nói"></button>
            <p id="dictationStatus" class="small muted" role="status" aria-live="polite" hidden></p>
            <p id="dictationPreview" class="small" aria-live="polite" hidden></p>
            <div class="actions">
              <button class="btn small" type="button" id="dictationInsert" disabled hidden>Chèn nội dung</button>
              <button class="btn small" type="button" id="dictationDiscard" disabled hidden>Xóa bản chép</button>
            </div>
          </div>
          <div class="clinical-actions">
            ${ button("Không có vùng tổn thương cần phân đoạn", "no-lesion", "small")}
            ${ button("Xóa phân đoạn và vẽ lại", "manual", "small")}
          </div>
          <p id="segmentationState" class="small" role="status"></p>
          <p id="segmentationDependencyWarning" class="banner warning small" role="status" hidden>Có thay đổi chưa lưu. Lưu hoặc khôi phục để tiếp tục đo và đánh giá.</p>
          <p class="muted small clinical-mask-note">Mask rỗng ghi nhận vùng phân đoạn rỗng; bác sĩ tiếp tục rà soát trên ảnh gốc.</p>
          <div id="adnexMount"></div>
          <div id="researchCandidateMount"></div>
          <div id="regionReviewMount"></div>
          <p id="regionCaliperStatus" class="muted small" role="status" aria-live="polite">Caliper theo vùng chỉ lưu sau khi chọn snapshot vùng đã xác nhận.</p>
          <button id="regionCaliperRetry" class="btn small" type="button" hidden>Thử lưu lại caliper chưa xác nhận</button>
          <details>
            <summary class="small">Nguồn mô hình</summary>
              <p id="modelHash" class="mono"></p>
          </details>
            <details open>
              <summary>Kết quả phân tích AI</summary>
              <p id="imageClassification" role="status" style="white-space:pre-wrap;overflow-wrap:anywhere"></p>
              <button id="btnApplyAiDiagnosis" class="btn small outline" type="button" style="margin-top:8px" hidden>Thêm gợi ý AI vào ghi chú</button>
            </details>
          <details>
            <summary class="small">Lịch sử chỉnh sửa</summary>
            <ol id="historyList" class="small"></ol>
          </details>
          <h3>Trạng thái rà soát</h3>
          <ol class="timeline"><li>AI đề xuất phân đoạn</li><li>Bác sĩ đã hiệu chỉnh</li>${ workflowStage}</ol>
        </section>
      </aside>
    </div>`;
    organizeAssessment(root);
    const orads1Option = $("#oradsScore").querySelector('option[value="O-RADS 1"]');
    if (orads1Option) orads1Option.textContent = ORADS1_OPTION_LABEL;
    const orads0Option = new Option(ORADS0_OPTION_LABEL, "O-RADS 0");
    $("#oradsScore").add(orads0Option, 1);
    const oradsSelect = $("#oradsScore");
    const syncContentWarning = () => {
      const warnings = reviewWarnings(image);
      $("#reviewContentWarning").hidden = warnings.length === 0;
      $("#reviewContentWarningText").textContent = warnings.join(" ");
      $("#reviewContentAckLabel").hidden = warnings.some(text => text.includes("chỗ trống"));
      $("#reviewContentAck").checked = image?.consistencyAcknowledgement === consistencyKey(image);
      $("#reviewContentAck").disabled = readonly || state.busy;
    };
    $("#reviewContentAck").onchange = event => {
      if (!image || readonly || state.busy) return syncContentWarning();
      image.consistencyAcknowledgement = event.target.checked ? consistencyKey(image) : null;
      recordUiEvent(c.study_id, "field_edit", { field: "review_consistency_ack", source: "manual" });
    };
    if (role() === "BS") {
      $("#adnexMount").insertAdjacentHTML(
        "beforeend",
        adnexPanelMarkup(
          readonly || !state.editing?.allowed || !state.editing?.leaseToken,
        ),
      );
      $("#adnexMount").insertAdjacentHTML(
        "beforeend",
        cdssPanelMarkup(
          readonly || !state.editing?.allowed || !state.editing?.leaseToken,
        ),
      );
      $("#researchCandidateMount").innerHTML = researchCandidateMarkup();
    }
    if (state.draftConflict) {
      $("[data-action=download-conflict]").onclick = () =>
        download(
          "ban-nhap-xung-dot.json",
          JSON.stringify(state.draftConflict.draft, null, 2),
          "application/json",
        );
      $("[data-action=keep-server]").onclick = () => {
        keepServerVersion();
        window.dispatchEvent(new CustomEvent("ova:rerender"));
      };
    }
    const canvas = $("#viewport"),
      ctx = canvas.getContext("2d"),
      second = $("#secondViewport"),
      secondCtx = second.getContext("2d");
    const canReviewFullCase = () =>
      c.images.length > 0 &&
      c.images.every((item) => item.seen) &&
      (c.ovary_side !== "BOTH" || ["L", "R"].every((side) => c.images.some((item) => item.laterality === side)));
    let view = { x: 0, y: 0, scale: 1 },
      tool = "brush",
      brush = 16,
      layer = 2,
      layerBeforeOverlay = 0,
      contour = true,
      peek = false,
      comparison = false,
      compareKind = "original",
      brightness = 100,
      contrast = 100,
      opacity = 0.35,
      caliperDenoise = false,
      draw = false,
      pan = false,
      activePointerId = null,
      fitAfterPointer = false,
      last = null,
      polygon = [],
      pendingCaliper = null,
      caliperPreviewPoint = null,
      serial = 0,
      timer = null,
      frame = 0;
    let uncertainty = null,
      showUncertainty = false;
    const dictation = bindLocalDictation({
      compact: true,
      browser: window,
      input: $("#notes"),
      recordButton: $("#dictationRecord"),
      status: $("#dictationStatus"),
      preview: $("#dictationPreview"),
      insertButton: $("#dictationInsert"),
      discardButton: $("#dictationDiscard"),
    });
    $("#dictationRecord").disabled = readonly;
    const presetLabel = document.createElement("label");
    presetLabel.className = "range-row";
    presetLabel.innerHTML =
      'Hiển thị <select id="displayPreset" aria-label="Thiết lập sáng và tương phản"><option value="normal">Mặc định</option><option value="dim">Ít chói</option><option value="contrast">Tăng tương phản</option></select>';
    $("#viewerAdjustmentsPopover").prepend(presetLabel);
    const uncertaintyLabel = document.createElement("label");
    uncertaintyLabel.className = "field small";
    uncertaintyLabel.hidden = true;
    uncertaintyLabel.innerHTML =
      '<span><input id="uncertaintyToggle" type="checkbox" disabled> Xem độ bất định của AI</span><small id="uncertaintyInfo" hidden>Độ bất định của mô hình không phải xác suất ác tính.</small>';
    $("#viewerInternalData").append(uncertaintyLabel);
    const abort = new AbortController(),
      events = { signal: abort.signal };
    const popovers = $$(
      "details.viewer-more-actions, details.tool-more, details.view-more, details.viewer-adjustments",
      root,
    );
    root.addEventListener(
      "click",
      (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        for (const popover of popovers) {
          if (
            popover.open &&
            (!popover.contains(target) || target.closest("button"))
          )
            popover.open = false;
        }
      },
      events,
    );
    const worker = new Worker("/static/app/measure-worker.js", {
      type: "module",
    });
    const measurementQueue = new LatestMeasurementQueue();
    const source = document.createElement("canvas");
    source.width = source.height = 512;
    const sourceCtx = source.getContext("2d");
    const maskCanvas = document.createElement("canvas");
    maskCanvas.width = maskCanvas.height = 512;
    const maskCtx = maskCanvas.getContext("2d");
    const regionHighlightCanvas = document.createElement("canvas");
    regionHighlightCanvas.width = regionHighlightCanvas.height = 512;
    const regionHighlightCtx = regionHighlightCanvas.getContext("2d");
    let regionGroupsByIndex = new Map(),
      highlightedRegionIndex = null,
      activeRegionContext = null,
      pendingRegionCaliperRequest = null;
    const outline = document.createElement("canvas");
    outline.width = outline.height = 512;
    const outlineCtx = outline.getContext("2d");
    const maskPixels = maskCtx.createImageData(512, 512),
      edgePixels = outlineCtx.createImageData(512, 512);
    const compareCanvas = document.createElement("canvas");
    compareCanvas.width = compareCanvas.height = 512;
    let image = null,
      box = null,
      selecting = true,
      comparisonSerial = 0,
      selectionSerial = 0,
      selectionActive = false;
    const syncDraftNotice = () => {
      const notice = $("#localReviewDraftNotice");
      if (notice) notice.hidden = !state.dirty || Boolean(state.draftConflict);
      const status = $('#assessmentSaveStatus');
      if (status && status.dataset.saving !== 'true') {
        if (status.dataset.error === 'true') status.textContent = 'Lưu không thành công';
        else if (state.dirty) status.textContent = 'Chưa lưu';
        else if (image?.review?.review_id) status.textContent = 'Đã lưu';
        else if (status.dataset.error !== 'true') status.textContent = 'Chưa lưu';
      }
      const segmentation = $('#segmentationState');
      if (!state.dirty) $('#segmentationDependencyWarning').hidden = true;
      if (segmentation) segmentation.textContent = image?.mask?.some(Boolean)
        ? 'Vùng tổn thương: có phân đoạn'
        : 'Chưa có vùng phân đoạn';
    };
    const syncClinicalInputs = () => {
      syncDraftNotice();
      const editable = canEditCanvas();
      const blocked = !editable || state.busy || selecting || !image || disposed;
      const filterToggle = $("#caliperDenoiseToggle");
      if (filterToggle) filterToggle.disabled = state.busy || selecting || !image || disposed;
      const rerun = $("#btnRerunAI");
      if (rerun) {
        rerun.disabled = blocked || correction || state.dirty || Boolean(image?.review);
        rerun.title = state.dirty || image?.review
          ? "Giữ nguyên mask đã rà soát hoặc bản nháp đang chỉnh sửa."
          : "Phân tích lại bằng checkpoint đã xác minh, với tiền xử lý mặc định.";
      }
      const applyAi = $("#btnApplyAiDiagnosis");
      if (applyAi) applyAi.disabled = blocked || correction;
      for (const id of ["notes", "morphology", "iotaMorphology", "oradsScore", "reviewContentAck"])
        if ($("#" + id)) $("#" + id).disabled = blocked || (correction && ["iotaMorphology", "oradsScore", "reviewContentAck"].includes(id));
      $("[data-action=quick-print]").disabled = blocked || correction;
      $("[data-action=save-review]").disabled = blocked || !c.images.every(i => i.seen);
      $("[data-action=save-review]").title = !canReviewFullCase()
        ? (c.ovary_side === 'BOTH' ? 'Vui lòng hoàn tất đánh giá hai bên trước khi tiếp tục.' : 'Vui lòng xem đủ ảnh trước khi lưu.') : '';
      $("#dictationRecord").disabled = blocked;
      $("#dictationInsert").disabled = blocked || $("#dictationPreview").hidden;
      $("[data-action=calibrate]").disabled = blocked || correction || !state.editing?.leaseToken;
      $("[data-action=sign]").disabled = blocked || !workflowEnabled || !canReviewFullCase();
      if ($("[data-action=save-correction]")) $("[data-action=save-correction]").disabled = blocked;
      $("[data-action=manual]").hidden = !editable;
      $("[data-action=no-lesion]").hidden = !editable;
      $("[data-action=manual]").disabled = blocked;
      $("[data-action=no-lesion]").disabled = blocked;
      $$('[data-chip]').forEach((button) => { button.disabled = blocked; });
    };
    const canEditCanvas = () =>
      !disposed &&
      !readonly &&
      state.editing?.caseId === c.study_id &&
      state.editing.allowed &&
      !["LOCKED", "SIGNED_PRELIM", "APPROVED"].includes(c.status);
    function renderClassification() {
      const result = image?.prediction?.ai_diagnosis;
      $("#imageClassification").textContent = result ? classificationText(result) : 'Chưa có kết quả phân tích AI';
      $("#classificationProvenance").textContent = result?.provenance
        ? `Phân loại ảnh: ${result.provenance.model || 'Chưa ghi nhận'} · SHA-256: ${result.provenance.checkpoint_sha256 || 'Chưa ghi nhận'}` : '';
      const apply = $("#btnApplyAiDiagnosis");
      apply.hidden = classificationNote(result) === null;
      apply.onclick = () => {
        if (!canEditCanvas() || state.busy || selecting || correction) return;
        const notes = $("#notes");
        const next = classificationNote(image?.prediction?.ai_diagnosis, notes.value);
        if (next === null || next === notes.value) return;
        notes.value = next;
        notes.dispatchEvent(new Event("input", { bubbles: true }));
        toast("Đã thêm gợi ý AI chưa xác nhận vào ghi chú.");
      };
    }
    const syncToolButtons = () => {
      $$('[data-tool]').forEach((button) => {
        const viewOnlyTool = ['fit', 'pan', 'fullscreen'].includes(button.dataset.tool);
        button.disabled = !image || selecting || state.busy || (!canEditCanvas() && !viewOnlyTool);
      });
    };
    const syncImageSelectionControls = () => {
      $$('[data-action^=side-]').forEach((button) => {
        button.disabled = selecting || state.busy;
      });
      const imageSelect = $('#viewerImageSelect');
      if (imageSelect) imageSelect.disabled = selecting || state.busy || readonly;
    };
    syncClinicalInputs();
    syncToolButtons();
    syncImageSelectionControls();
    root.addEventListener("ova:review-lock-changed", () => {
      syncClinicalInputs();
      syncToolButtons();
    }, events);
    window.addEventListener("ova:busy-changed", () => {
      syncClinicalInputs();
      syncToolButtons();
      syncImageSelectionControls();
    }, events);
    window.addEventListener("ova:review-draft-state-changed", syncDraftNotice, events);
    const canEvaluateAdnex = () =>
      role() === "BS" &&
      !disposed &&
      !state.busy &&
      canEditCanvas() &&
      !selecting &&
      !!image &&
      !!state.editing.leaseToken;
    const adnexUI = bindAdnexPanel(root, {
      getContext: () => ({ side: state.side, imageId: image?.image_id ?? null }),
      canEvaluate: canEvaluateAdnex,
      routeSignal: abort.signal,
    });
    const canEvaluateCdss = () => canEvaluateAdnex();
    const cdssUI = bindCdssPanel(root, {
      getContext: () => ({
        studyId: c.study_id ?? null,
        imageId: image?.image_id ?? null,
        side: state.side ?? null,
        leaseToken: state.editing?.leaseToken ?? null,
        pageInstanceId: state.editing?.pageInstanceId ?? null,
      }),
      canEvaluate: canEvaluateCdss,
      signal: abort.signal,
      requireSavedRegion: true,
      onCalipers: (snapshot) => {
        if (!activeRegionContext || snapshot.region_id !== activeRegionContext.regionId ||
            snapshot.assignment_request_id !== activeRegionContext.assignmentRequestId || !image ||
            image.image_id !== activeRegionContext.imageId) return;
        image.regionCalipers = snapshot.measurements || {};
        const describe = (label) => {
          const item = image.regionCalipers[label];
          if (!item) return `${label}: chưa đo`;
          return item.diameter_mm == null
            ? `${label}: ${Number(item.diameter_px).toFixed(1)} px · mm chưa khả dụng`
            : `${label}: ${Number(item.diameter_mm).toFixed(1)} mm (${Number(item.diameter_px).toFixed(1)} px)`;
        };
        $("#regionCaliperStatus").textContent = `${describe("D1")} · ${describe("D2")}`;
        schedule();
      },
    });
    const schedule = () => {
      if (!frame)
        frame = requestAnimationFrame(() => {
          frame = 0;
          render();
        });
    };
    const overlayVisibilityButton = $(`[data-action="overlay-visibility"]`);
    const syncOverlayVisibility = () => {
      const visible = layer === 2 && !peek;
      overlayVisibilityButton.setAttribute("aria-pressed", String(visible));
      overlayVisibilityButton.classList.toggle("primary", visible);
    };
    const setLayer = (nextLayer) => {
      if (nextLayer !== layer) {
        if (layer === 2) layerBeforeOverlay = nextLayer;
        else if (nextLayer === 2) layerBeforeOverlay = layer;
      }
      layer = nextLayer;
      syncOverlayVisibility();
      schedule();
    };
    const toggleOverlayVisibility = () =>
      setLayer(layer === 2 ? layerBeforeOverlay : 2);
    const render = () => {
      syncOverlayVisibility();
      if (disposed || !image) return;
      for (const [target, context, isSecond] of [
        [canvas, ctx, false],
        [second, secondCtx, true],
      ]) {
        const r = target.getBoundingClientRect(),
          dpr = window.devicePixelRatio || 1;
        if (
          target.width !== Math.round(r.width * dpr) ||
          target.height !== Math.round(r.height * dpr)
        ) {
          target.width = Math.round(r.width * dpr);
          target.height = Math.round(r.height * dpr);
        }
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        context.fillStyle = "#20262c";
        context.fillRect(0, 0, r.width, r.height);
        context.translate(view.x, view.y);
        context.scale(view.scale, view.scale);
        context.imageSmoothingEnabled = true;
        if (layer !== 1 || peek || isSecond) {
          let filterStr = `brightness(${brightness}%) contrast(${contrast}%)`;
          context.filter = filterStr;
          context.drawImage(
            isSecond && compareKind !== "original" ? compareCanvas : source,
            0,
            0,
          );
          context.filter = "none";
        }
        if (!peek && !isSecond && layer !== 0) {
          context.globalAlpha = contour ? 1 : opacity;
          context.imageSmoothingEnabled = false;
          context.drawImage(contour ? outline : maskCanvas, 0, 0);
          context.globalAlpha = 1;
        }
        if (!peek && !isSecond && highlightedRegionIndex != null &&
            regionGroupsByIndex.has(highlightedRegionIndex)) {
          context.save();
          context.globalAlpha = 0.72;
          context.imageSmoothingEnabled = false;
          context.drawImage(regionHighlightCanvas, 0, 0);
          context.restore();
        }
        if (
          !peek &&
          !isSecond &&
          layer === 2 &&
          showUncertainty &&
          uncertainty
        ) {
          context.globalAlpha = 0.35;
          context.drawImage(uncertainty, 0, 0, 512, 512);
          context.globalAlpha = 1;
        }
        const measurements = image?.measurements;
        const measuredLesion =
          measurements?.lesions?.[0] || measurements?.filtered_components?.[0];
        if (
          !peek &&
          !isSecond &&
          layer === 2 &&
          measurements?.coordinate_space === "decoded-source-image" &&
          measuredLesion
        ) {
          context.save();
          context.lineCap = "round";
          context.lineJoin = "round";
          context.font = `${12 / view.scale}px system-ui, sans-serif`;
          context.textAlign = "left";
          context.textBaseline = "bottom";
          for (const [label, points] of [
            ["d₁", measuredLesion.viewer_caliper_dmax_points],
            ["d₂", measuredLesion.viewer_caliper_dorth_points],
          ]) {
            if (
              !Array.isArray(points) ||
              points.length !== 2 ||
              points.some(
                (point) =>
                  !Array.isArray(point) ||
                  point.length < 2 ||
                  !Number.isFinite(point[0]) ||
                  !Number.isFinite(point[1]),
              )
            )
              continue;
            context.beginPath();
            context.moveTo(points[0][0], points[0][1]);
            context.lineTo(points[1][0], points[1][1]);
            context.strokeStyle = "#101820";
            context.lineWidth = 4 / view.scale;
            context.stroke();
            context.strokeStyle = "#ffd166";
            context.lineWidth = 2 / view.scale;
            context.stroke();
            for (const [x, y] of points) {
              context.beginPath();
              context.arc(x, y, 3 / view.scale, 0, Math.PI * 2);
              context.fillStyle = "#101820";
              context.fill();
              context.beginPath();
              context.arc(x, y, 1.8 / view.scale, 0, Math.PI * 2);
              context.fillStyle = "#ffd166";
              context.fill();
            }
            const midX = (points[0][0] + points[1][0]) / 2;
            const midY = (points[0][1] + points[1][1]) / 2;
            context.lineWidth = 3 / view.scale;
            context.strokeStyle = "#101820";
            context.strokeText(label, midX + 4 / view.scale, midY - 4 / view.scale);
            context.fillStyle = "#ffd166";
            context.fillText(label, midX + 4 / view.scale, midY - 4 / view.scale);
          }
          context.restore();
        }
        if (!peek && !isSecond && image?.manualCalipers?.length) {
          context.save();
          context.lineCap = "round";
          context.lineJoin = "round";
          context.font = `${12 / view.scale}px system-ui, sans-serif`;
          context.textAlign = "left";
          context.textBaseline = "bottom";
          const width = image.dimensions?.[0] || image.width || 512;
          const height = image.dimensions?.[1] || image.height || 512;
          for (const caliper of image.manualCalipers) {
            if (!Array.isArray(caliper?.points) || caliper.points.length !== 2 ||
                caliper.points.some(point => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))) continue;
            const points = caliper.points.map(([x, y]) => [
              box.left + x * box.width / width,
              box.top + y * box.height / height,
            ]);
            context.beginPath();
            context.moveTo(points[0][0], points[0][1]);
            context.lineTo(points[1][0], points[1][1]);
            context.strokeStyle = "#101820";
            context.lineWidth = 4 / view.scale;
            context.stroke();
            context.strokeStyle = "#ffbf47";
            context.lineWidth = 2 / view.scale;
            context.stroke();
            for (const [x, y] of points) {
              context.beginPath();
              context.arc(x, y, 3 / view.scale, 0, Math.PI * 2);
              context.fillStyle = "#101820";
              context.fill();
              context.beginPath();
              context.arc(x, y, 1.8 / view.scale, 0, Math.PI * 2);
              context.fillStyle = "#ffbf47";
              context.fill();
            }
            const midX = (points[0][0] + points[1][0]) / 2;
            const midY = (points[0][1] + points[1][1]) / 2;
            context.lineWidth = 3 / view.scale;
            context.strokeStyle = "#101820";
            context.strokeText(`BS · ${caliper.label}`, midX + 4 / view.scale, midY - 4 / view.scale);
            context.fillStyle = "#ffbf47";
            context.fillText(`BS · ${caliper.label}`, midX + 4 / view.scale, midY - 4 / view.scale);
          }
          context.restore();
        }
        if (!peek && !isSecond && activeRegionContext && image?.regionCalipers) {
          context.save();
          context.lineCap = "round";
          context.lineJoin = "round";
          context.font = `${12 / view.scale}px system-ui, sans-serif`;
          context.textAlign = "left";
          context.textBaseline = "bottom";
          const width = image.dimensions?.[0] || image.width || 512;
          const height = image.dimensions?.[1] || image.height || 512;
          for (const label of ["D1", "D2"]) {
            const caliper = image.regionCalipers[label];
            if (!Array.isArray(caliper?.points) || caliper.points.length !== 2 ||
                caliper.points.some(point => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))) continue;
            const points = caliper.points.map(([x, y]) => [
              box.left + x * box.width / width,
              box.top + y * box.height / height,
            ]);
            context.beginPath();
            context.moveTo(points[0][0], points[0][1]);
            context.lineTo(points[1][0], points[1][1]);
            context.strokeStyle = "#071b26";
            context.lineWidth = 4 / view.scale;
            context.stroke();
            context.strokeStyle = label === "D1" ? "#62e9e0" : "#ff9f68";
            context.lineWidth = 2 / view.scale;
            context.stroke();
            for (const [x, y] of points) {
              context.beginPath();
              context.arc(x, y, 3 / view.scale, 0, Math.PI * 2);
              context.fillStyle = "#071b26";
              context.fill();
              context.beginPath();
              context.arc(x, y, 1.8 / view.scale, 0, Math.PI * 2);
              context.fillStyle = label === "D1" ? "#62e9e0" : "#ff9f68";
              context.fill();
            }
            const midX = (points[0][0] + points[1][0]) / 2;
            const midY = (points[0][1] + points[1][1]) / 2;
            const displayed = caliper.diameter_mm == null
              ? `${label} ${Number(caliper.diameter_px).toFixed(1)} px`
              : `${label} ${Number(caliper.diameter_mm).toFixed(1)} mm`;
            context.lineWidth = 3 / view.scale;
            context.strokeStyle = "#071b26";
            context.strokeText(displayed, midX + 4 / view.scale, midY - 4 / view.scale);
            context.fillStyle = label === "D1" ? "#62e9e0" : "#ff9f68";
            context.fillText(displayed, midX + 4 / view.scale, midY - 4 / view.scale);
          }
          context.restore();
        }
        if (!peek && !isSecond && pendingCaliper) {
          context.save();
          context.beginPath();
          context.arc(pendingCaliper.point.x, pendingCaliper.point.y, 5 / view.scale, 0, Math.PI * 2);
          context.fillStyle = "#ffbf47";
          context.strokeStyle = "#101820";
          context.lineWidth = 2 / view.scale;
          context.fill();
          context.stroke();
          if (caliperPreviewPoint) {
            context.beginPath();
            context.setLineDash([5 / view.scale, 4 / view.scale]);
            context.moveTo(pendingCaliper.point.x, pendingCaliper.point.y);
            context.lineTo(caliperPreviewPoint.x, caliperPreviewPoint.y);
            context.stroke();
          }
          context.restore();
        }
        if (!isSecond && polygon.length) {
          context.strokeStyle = "#62e9e0";
          context.lineWidth = 1 / view.scale;
          context.beginPath();
          polygon.forEach((p, i) =>
            i ? context.lineTo(p.x, p.y) : context.moveTo(p.x, p.y),
          );
          context.stroke();
        }
      }
    };
    const refreshMask = (region = null) => {
      const data = maskPixels,
        edge = edgePixels,
        minX = Math.max(0, (region?.x0 ?? 0) - 1),
        maxX = Math.min(511, (region?.x1 ?? 511) + 1),
        minY = Math.max(0, (region?.y0 ?? 0) - 1),
        maxY = Math.min(511, (region?.y1 ?? 511) + 1);
      for (let y = minY; y <= maxY; y++)
        for (let x = minX; x <= maxX; x++) {
          const p = y * 512 + x,
            i = p * 4,
            v = image.mask[p],
            boundary =
              v &&
              (x === 0 ||
                y === 0 ||
                x === 511 ||
                y === 511 ||
                !image.mask[p - 1] ||
                !image.mask[p + 1] ||
                !image.mask[p - 512] ||
                !image.mask[p + 512]);
          data.data.set([98, 233, 224, v ? 255 : 0], i);
          edge.data.set([98, 233, 224, boundary ? 255 : 0], i);
        }
      maskCtx.putImageData(
        data,
        0,
        0,
        minX,
        minY,
        maxX - minX + 1,
        maxY - minY + 1,
      );
      outlineCtx.putImageData(
        edge,
        0,
        0,
        minX,
        minY,
        maxX - minX + 1,
        maxY - minY + 1,
      );
      schedule();
    };
    const fit = () => {
      const r = canvas.getBoundingClientRect();
      view.scale = Math.min(r.width / 512, r.height / 512) * 0.94;
      view.x = (r.width - 512 * view.scale) / 2;
      view.y = (r.height - 512 * view.scale) / 2;
      schedule();
    };
    const autoZoomLesion = () => {
      if (!image.mask) return fit();
      let minX = 512, minY = 512, maxX = 0, maxY = 0, hasPixels = false;
      for (let y = 0; y < 512; y++) {
        for (let x = 0; x < 512; x++) {
          if (image.mask[y * 512 + x] > 0) {
            hasPixels = true;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
      if (!hasPixels || (maxX - minX < 8 && maxY - minY < 8)) return fit();
      const r = canvas.getBoundingClientRect();
      const lesionW = Math.max(maxX - minX + 1, 40);
      const lesionH = Math.max(maxY - minY + 1, 40);
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      const targetScale = Math.min(r.width / (lesionW * 2.2), r.height / (lesionH * 2.2));
      view.scale = Math.max(0.6, Math.min(targetScale, 3.5));
      view.x = r.width / 2 - centerX * view.scale;
      view.y = r.height / 2 - centerY * view.scale;
      schedule();
    };
    const updateAccessibleImageSummary = (m) => {
      const summary = $("#viewerImageSummary");
      if (!summary || !m) return;
      const physical = m.calibrated === true;
      const format = (value, unit) =>
        Number.isFinite(value) ? `${value.toFixed(1)} ${unit}` : `chưa có ${unit}`;
      const hasMarkedPixels = image.mask?.some((value) => value > 0) ?? false;
      const side = state.side === "L" ? "trái" : "phải";
      const maskStatus = hasMarkedPixels
        ? "Mask có vùng được đánh dấu."
        : "Mask rỗng, chưa có vùng được đánh dấu.";
      const measurementStatus = m._pending
        ? "Các số đo đang được cập nhật."
        : image.manualCalipers?.length
          ? `Caliper bác sĩ đã đặt: ${image.manualCalipers.map(item => `${item.label} ${format(manualCaliperLength(item, physical), physical ? "milimét" : "pixel")}`).join("; ")}. `
          : `Proxy mask D1 ${format(physical ? m.max_diameter_mm : m.max_diameter_px, physical ? "milimét" : "pixel")}; ` +
          `D2 ${format(physical ? m.ortho_diameter_mm : m.ortho_diameter_px, physical ? "milimét" : "pixel")}; ` +
          `diện tích ${format(physical ? m.total_area_cm2 : m.total_area_px, physical ? "centimét vuông" : "pixel vuông")}.`;
      const calibrationStatus = physical
        ? m.calibration_source === "DICOM"
          ? "Hiệu chuẩn từ DICOM."
          : m.calibration_source === "MANUAL"
            ? "Hiệu chuẩn nhập tay."
            : "Đã có thang đo; nguồn hiệu chuẩn đang chờ xác nhận."
        : "Hiệu chuẩn px→mm: nhập pixel spacing để xem số đo theo đơn vị thực; hiện hiển thị px.";
      summary.textContent =
        `Ảnh siêu âm buồng trứng ${side}. ${maskStatus} ${measurementStatus} ${calibrationStatus} ` +
        "Mask là phân đoạn hỗ trợ rà soát hình ảnh. " +
        (typeof m.warning === "string" ? m.warning : "");
    };
    const updateViewerWarnings = () => {
      const count = image.mask ? components(image.mask).length : 0;
      const warnings = [
        image.workerMeas?.touches ? "Mask chạm biên ảnh" : "",
        count > 1 ? `${count} thành phần mask – kiểm tra từng vùng` : "",
        image.iqa?.is_acceptable === false ? "Chất lượng ảnh thấp" : "",
        typeof image.measurements?.warning === "string" ? image.measurements.warning : "",
      ].filter(Boolean);
      $("#viewerWarnings").innerHTML = warnings
        .map((value) => `<div class="banner warning small">${esc(value)}</div>`)
        .join("");
    };
    const displayMeasurements = (m) => {
      if (!m) return;
      const physical = m.calibrated === true;
      const format = (value) =>
        Number.isFinite(value) ? value.toFixed(1) : "—";
      const manual = image.manualCalipers || [];
      const d1 = manual.find((item) => item.label === "D1");
      const d2 = manual.find((item) => item.label === "D2");
      $("#d1").textContent =
        format(d1 ? manualCaliperLength(d1, physical) : (manual.length ? null : physical ? m.max_diameter_mm : m.max_diameter_px)) +
        (physical ? " mm" : " px");
      $("#d2").textContent =
        format(d2 ? manualCaliperLength(d2, physical) : (manual.length ? null : physical ? m.ortho_diameter_mm : m.ortho_diameter_px)) +
        (physical ? " mm" : " px");
      $("#area").textContent =
        format(physical ? m.total_area_cm2 : m.total_area_px) +
        (physical ? " cm²" : " px²");
      $("#measureValues").classList.toggle("pixel", !physical);
      const calBadge = $("#calibrationBadge");
      if (calBadge) {
        calBadge.textContent = manual.length
          ? `Caliper bác sĩ · ${physical ? (m.calibration_source === "DICOM" ? "DICOM" : m.calibration_source === "MANUAL" ? "nhập tay" : "nguồn chưa xác định") : "px"}`
          : physical
          ? m.calibration_source === "DICOM"
            ? "Đã hiệu chuẩn DICOM"
            : m.calibration_source === "MANUAL" ? "Nhập tay" : "Nguồn chưa xác định"
          : "";
        calBadge.style.display = physical || manual.length ? "" : "none";
      }
      updateAccessibleImageSummary(m);
      updateViewerWarnings();
    };
    const manualCaliperLength = (caliper, physical) => {
      const spacing = image.measurements?.pixel_spacing_mm ?? image.pixel_spacing_mm;
      return measuredCaliperLength(caliper, physical, spacing);
    };
    const sendPendingRegionCaliper = async () => {
      const pending = pendingRegionCaliperRequest;
      const retryButton = $("#regionCaliperRetry");
      if (!pending || pending.sending) return;
      pending.sending = true;
      retryButton.disabled = true;
      $("#regionCaliperStatus").textContent = `Đang lưu ${pending.payload.label} theo vùng ${pending.payload.region_id.slice(0, 8)}…`;
      try {
        const response = await request(pending.endpoint, {
          method: "POST",
          body: pending.payload,
          signal: abort.signal,
        });
        if (response.current === false) {
          if (pendingRegionCaliperRequest !== pending) return;
          pendingRegionCaliperRequest = null;
          retryButton.hidden = true;
          retryButton.disabled = false;
          if (activeRegionContext) {
            $("#regionCaliperStatus").textContent =
              "Caliper này không còn hiện hành. Đang tải lại D1/D2 mới nhất; hãy kiểm tra trước khi tiếp tục.";
            cdssUI.setRegionContext(activeRegionContext);
          } else {
            $("#regionCaliperStatus").textContent =
              response.stale_reason || "Caliper này không còn hiện hành; hãy tải lại vùng trước khi tiếp tục.";
          }
          return;
        }
        if (pendingRegionCaliperRequest !== pending) return;
        pendingRegionCaliperRequest = null;
        retryButton.hidden = true;
        retryButton.disabled = false;
        const isActive = activeRegionContext &&
          activeRegionContext.assignmentRequestId === response.assignment_request_id &&
          activeRegionContext.regionId === response.region_id &&
          image?.image_id === pending.imageId;
        if (isActive) {
          image.regionCalipers ??= {};
          image.regionCalipers[response.label] = response;
          schedule();
          cdssUI.setRegionContext(activeRegionContext);
        }
        $("#regionCaliperStatus").textContent = response.diameter_mm == null
          ? `${response.label} đã lưu: ${Number(response.diameter_px).toFixed(1)} px; không có hiệu chuẩn mm hợp lệ.`
          : `${response.label} đã lưu: ${Number(response.diameter_mm).toFixed(1)} mm (${Number(response.diameter_px).toFixed(1)} px).`;
      } catch (error) {
        if (error?.name === "AbortError" && disposed) return;
        if (pendingRegionCaliperRequest === pending) {
          pending.sending = false;
          retryButton.hidden = false;
          retryButton.disabled = false;
          $("#regionCaliperStatus").textContent = `${error?.message || "Không lưu được caliper."} Dùng nút thử lại để gửi cùng request ID.`;
          if (error?.status === 409) {
            pendingRegionCaliperRequest = null;
            retryButton.hidden = true;
            if (activeRegionContext) cdssUI.setRegionContext(activeRegionContext);
          }
        }
      }
    };
    $("#regionCaliperRetry").addEventListener("click", sendPendingRegionCaliper, events);
    const saveSelectedRegionCaliper = (label, points) => {
      const selected = activeRegionContext;
      if (!selected || !canEvaluateAdnex()) {
        toast("Chọn một vùng đã xác nhận và có lease bác sĩ trước khi đo.", true);
        return;
      }
      if (pendingRegionCaliperRequest) {
        toast("Có caliper chưa được xác nhận bởi máy chủ. Thử lưu lại request đó trước.", true);
        return;
      }
      const current = image.regionCalipers?.[label];
      const payload = {
        request_id: crypto.randomUUID(),
        expected_revision: current?.measurement_revision || 0,
        assignment_request_id: selected.assignmentRequestId,
        review_id: selected.reviewId,
        region_id: selected.regionId,
        mask_sha256: selected.maskSha256,
        label,
        points,
        coordinate_space: "decoded-source-image",
        lease_token: state.editing?.leaseToken,
        page_instance_id: state.editing?.pageInstanceId,
      };
      const endpoint = `/api/cases/${encodeURIComponent(selected.studyId)}/images/${encodeURIComponent(selected.imageId)}/regions/${encodeURIComponent(selected.regionId)}/calipers`;
      pendingRegionCaliperRequest = { payload, endpoint, studyId: selected.studyId, imageId: selected.imageId, sending: false };
      void sendPendingRegionCaliper();
    };
    const measure = () => {
      clearTimeout(timer);
      const current = ++serial;
      let hasPixels = false;
      if (image.mask) {
        for (let idx = 0; idx < image.mask.length; idx++) {
          if (image.mask[idx]) {
            hasPixels = true;
            break;
          }
        }
      }
      if (!hasPixels) {
        const emptyMeas = {
          max_diameter_px: 0,
          ortho_diameter_px: 0,
          total_area_px: 0,
          max_diameter_mm: image.measurements?.calibrated ? 0 : null,
          ortho_diameter_mm: image.measurements?.calibrated ? 0 : null,
          total_area_cm2: image.measurements?.calibrated ? 0 : null,
          calibrated: Boolean(image.measurements?.calibrated),
          calibration_source: image.measurements?.calibration_source,
          pixel_spacing_mm: image.measurements?.pixel_spacing_mm ?? image.pixel_spacing_mm,
        };
        image.measurements = emptyMeas;
        displayMeasurements(emptyMeas);
      } else {
        // UAT-07: Immediately clear stale physical (mm/cm²) measurements while API
        // request is in-flight so old values are never shown after a mask change.
        const wasCalibrated = Boolean(image.measurements?.calibrated);
        const calSource = image.measurements?.calibration_source;
        const interimMeas = {
          max_diameter_px: null,
          ortho_diameter_px: null,
          total_area_px: null,
          max_diameter_mm: null,
          ortho_diameter_mm: null,
          total_area_cm2: null,
          calibrated: wasCalibrated,
          calibration_source: calSource,
          pixel_spacing_mm: image.measurements?.pixel_spacing_mm ?? image.pixel_spacing_mm,
          _pending: true,
        };
        image.measurements = interimMeas;
        // Show "Đang cập nhật..." placeholders immediately
        $("#d1").textContent = "Đang cập nhật…";
        $("#d2").textContent = "Đang cập nhật…";
        $("#area").textContent = "Đang cập nhật…";
        updateAccessibleImageSummary(interimMeas);
      }
      timer = setTimeout(async () => {
        if (current !== serial || disposed) return;
        worker.postMessage({ mask: image.mask, box, serial: current });
        if (image.image_id) {
          measurementQueue.submit(async () => {
          if (current !== serial || disposed) return;
          try {
            const m = await request(
              "/api/images/" +
                encodeURIComponent(image.image_id) +
                "/measurements",
              {
                method: "POST",
                body: { rle_mask: encode(image.mask) },
                signal: abort.signal,
              },
            );
            if (current === serial) {
              image.measurements = m;
              displayMeasurements(m);
              schedule();
            }
          } catch (e) {
            if (e.name !== "AbortError" && current === serial && !disposed) {
              $("#draftStatus").textContent =
                "Chưa cập nhật được số đo máy chủ.";
              if (current === serial) {
                const fallbackMeas = unavailableMeasurements(image.measurements, image.pixel_spacing_mm);
                image.measurements = fallbackMeas;
                displayMeasurements(fallbackMeas);
                schedule();
              }
            }
          }
          });
        }
      }, 180);
    };
    worker.onmessage = ({ data: m }) => {
      if (m.serial !== serial) return;
      image.workerMeas = m;
      if (m.area === 0) {
        const emptyMeas = {
          max_diameter_px: 0,
          ortho_diameter_px: 0,
          total_area_px: 0,
          max_diameter_mm: image.measurements?.calibrated ? 0 : null,
          ortho_diameter_mm: image.measurements?.calibrated ? 0 : null,
          total_area_cm2: image.measurements?.calibrated ? 0 : null,
          calibrated: Boolean(image.measurements?.calibrated),
          calibration_source: image.measurements?.calibration_source,
          pixel_spacing_mm: image.measurements?.pixel_spacing_mm ?? image.pixel_spacing_mm,
        };
        image.measurements = emptyMeas;
        displayMeasurements(emptyMeas);
      }
      image.seen = true;
      $("[data-action=sign]").disabled =
        readonly || !workflowEnabled || !canReviewFullCase();
      $("[data-action=save-review]").disabled =
        readonly || state.busy || !c.images.every((i) => i.seen);

      updateViewerWarnings();
    };
    const history = () => {
      $("#historyList").innerHTML =
        (image.history || [])
          .map((_, i) => `<li>Thao tác ${i + 1}</li>`)
          .join("") || "<li>Chưa chỉnh sửa</li>";
    };
    const beforeEdit = () => {
      activeRegionContext = null;
      if (image) image.regionCalipers = {};
      cdssUI.setRegionContext(null);
      $("#regionCaliperStatus").textContent = "Có thay đổi chưa lưu. Lưu hoặc khôi phục để tiếp tục đo và đánh giá.";
      $('#segmentationDependencyWarning').hidden = false;
      regionReviewUI.setContext({
        studyId: c.study_id,
        imageId: image?.image_id ?? null,
        reviewId: image?.review?.review_id ?? null,
        reviewRevision: c.review_revision ?? 0,
        maskMatchesReview: false,
        canEdit: role() === "BS" && canEditCanvas(),
        leaseToken: state.editing?.leaseToken ?? null,
        pageInstanceId: state.editing?.pageInstanceId ?? null,
      });
      image.history ??= [];
      image.redo ??= [];
      image.history.push(encode(image.mask));
      if (image.history.length > 50) image.history.shift();
      image.redo = [];
      if (!correction) tracker.startStroke(image.image_id);
    };
    const changed = ({
      refreshMeasurements = true,
      persistDraft = true,
      toolName = tool,
      changedPixels = 0,
      candidateParameters = null,
      candidateProvenance = null,
    } = {}) => {
      if (!correction) tracker.commitEdit(image.image_id, {
        tool: toolName,
        changed_pixels: changedPixels,
        candidate_parameters: candidateParameters,
        candidate_provenance: candidateProvenance,
      });
      root.dispatchEvent(new CustomEvent("ova:mask-changed"));
      if (persistDraft) {
        saveDraft();
        saveMaskDraft(c, image);
      }
      syncClinicalInputs();
      syncContentWarning();
      $("#draftStatus").textContent = persistDraft
        ? state.online
          ? "Bản nháp đã lưu trên thiết bị"
          : "Chưa đồng bộ – bản nháp trên thiết bị"
        : "Chưa lưu rà soát";
      history();
      if (refreshMeasurements) measure();
    };
    const canApplyResearchCandidate = () =>
      canEvaluateAdnex() && Boolean(image?.prediction?.prediction_id);
    const researchCandidateUI = bindResearchCandidate(root, {
      getContext: () => ({
        studyId: c.study_id ?? null,
        imageId: image?.image_id ?? null,
        predictionId: image?.prediction?.prediction_id ?? null,
        side: state.side ?? null,
        currentMask: image?.mask ?? null,
        aiMask: image?.aiMask ?? null,
        sourceCanvas: source,
      }),
      canEdit: canApplyResearchCandidate,
      signal: abort.signal,
      onApply: ({ mask, changedPixels, parameters, provenance }) => {
        if (
          !canApplyResearchCandidate() ||
          !(mask instanceof Uint8Array) ||
          mask.length !== 512 * 512
        ) return false;
        beforeEdit();
        image.mask = mask.slice();
        refreshMask();
        changed({
          toolName: "candidate_apply",
          changedPixels,
          candidateParameters: parameters,
          candidateProvenance: provenance,
        });
        return true;
      },
    });
    const regionReviewUI = bindRegionReview(root, {
      request,
      signal: abort.signal,
      getContext: () => ({
        studyId: c.study_id,
        imageId: image?.image_id ?? null,
        reviewId: image?.review?.review_id ?? null,
        reviewRevision: c.review_revision ?? 0,
        maskMatchesReview: Boolean(image?.review?.verified_mask_rle) &&
          JSON.stringify(encode(image.mask)) === JSON.stringify(image.review.verified_mask_rle),
        canEdit: role() === "BS" && state.editing?.caseId === c.study_id && state.editing.allowed,
        leaseToken: state.editing?.leaseToken ?? null,
        pageInstanceId: state.editing?.pageInstanceId ?? null,
      }),
      onSaved: (result) => { c.review_revision = result.review_revision; },
      onSelectRegion: (selectedRegion) => {
        activeRegionContext = selectedRegion;
        if (image) image.regionCalipers = {};
        $("#regionCaliperStatus").textContent = `Đang tải phép đo cho vùng ${selectedRegion.regionId.slice(0, 8)}…`;
        cdssUI.setRegionContext(selectedRegion);
        schedule();
      },
      onCandidates: (candidateSet) => {
        regionGroupsByIndex = new Map();
        regionHighlightCtx.clearRect(0, 0, 512, 512);
        highlightedRegionIndex = null;
        if (candidateSet == null) { schedule(); return true; }
        if (!image?.mask || candidateSet.mask_sha256 == null) return false;
        const bySeed = new Map();
        for (const group of components(image.mask)) {
          let seed = Infinity;
          for (const pixel of group) if (pixel < seed) seed = pixel;
          if (Number.isFinite(seed)) bySeed.set(seed, group);
        }
        for (const candidate of candidateSet.components) {
          const seed = candidate.seed_xy[1] * 512 + candidate.seed_xy[0];
          const group = bySeed.get(seed);
          if (!group || group.length !== candidate.pixel_count) return false;
          regionGroupsByIndex.set(candidate.component_index, group);
        }
        schedule();
        return true;
      },
      onHighlight: (componentIndex) => {
        highlightedRegionIndex = Number.isInteger(componentIndex) && regionGroupsByIndex.has(componentIndex)
          ? componentIndex
          : null;
        regionHighlightCtx.clearRect(0, 0, 512, 512);
        if (highlightedRegionIndex != null) {
          const pixels = regionHighlightCtx.createImageData(512, 512);
          for (const index of regionGroupsByIndex.get(highlightedRegionIndex)) {
            const offset = index * 4;
            pixels.data[offset] = 30;
            pixels.data[offset + 1] = 220;
            pixels.data[offset + 2] = 255;
            pixels.data[offset + 3] = 180;
          }
          regionHighlightCtx.putImageData(pixels, 0, 0);
        }
        if (canvas) canvas.dataset.highlightedRegion = highlightedRegionIndex == null ? "" : String(highlightedRegionIndex);
        schedule();
      },
    });
    window.addEventListener("ova:busy-changed", () => {
      const editable = canEditCanvas() && !state.busy && !selecting;
      adnexUI.setEditable(role() === "BS" && editable && !!state.editing?.leaseToken);
      cdssUI.setEditable(role() === "BS" && editable && !!state.editing?.leaseToken);
      regionReviewUI.setEditable(role() === "BS" && editable);
    }, events);
    const select = async (side, imageId = null) => {
      if (draw || pan || state.busy || selectionActive) return;
      const item = imageId
        ? c.images.find((i) => i.image_id === imageId && i.laterality === side)
        : c.images.find((i) => i.laterality === side);
      if (!item) return toast("Ca chưa có ảnh bên này.", true);
      if (side === state.side && item.image_id === image?.image_id) return;
      if (side !== state.side) dictation.cancel();
      const previousImage = image;
      const previousSide = state.side;
      const version = ++selectionSerial;
      ++serial;
      clearTimeout(timer);
      ++comparisonSerial;
      recordUiEvent(c.study_id, "side_switch", { side });
      selecting = true;
      selectionActive = true;
      syncToolButtons();
      syncImageSelectionControls();
      regionReviewUI.setContext(null);
      activeRegionContext = null;
      if (image) image.regionCalipers = {};
      $("#regionCaliperStatus").textContent = "Đang đổi ảnh; caliper theo vùng đã bỏ chọn.";
      syncClinicalInputs();
      researchCandidateUI.resetForSide();
      adnexUI.resetForSide(side);
      adnexUI.setEditable(false);
      cdssUI.resetForSide();
      cdssUI.setEditable(false);
      polygon = [];
      pendingCaliper = null;
      caliperPreviewPoint = null;
      let bitmap;
      let decodedSourceUrl = null;
      let sourceIsModel = item.sourceIsModel;
      try {
        let sourceImage = item.source;
        if (!sourceImage || sourceIsModel) {
          decodedSourceUrl = await protectedImage(
            "/api/images/" + encodeURIComponent(item.image_id) + "/source.png",
          );
          sourceImage = decodedSourceUrl;
          sourceIsModel = false;
        }
        bitmap = await imageSourceBitmap(sourceImage);
      } catch (error) {
        if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
        if (version === selectionSerial && !disposed) {
          selecting = false;
          selectionActive = false;
          syncClinicalInputs();
          syncToolButtons();
          syncImageSelectionControls();
          adnexUI.resetForSide(state.side);
          adnexUI.setEditable(canEvaluateAdnex());
          cdssUI.resetForSide();
          cdssUI.setEditable(canEvaluateCdss());
        }
        if (!image) throw error;
        if (error.name !== "AbortError") toast(error.message, true);
        return;
      }
      if (version !== selectionSerial || disposed) {
        bitmap.close();
        if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
        if (version === selectionSerial) {
          selecting = false;
          selectionActive = false;
          syncClinicalInputs();
          syncToolButtons();
          syncImageSelectionControls();
        }
        return;
      }
      const imageSelect = $("#viewerImageSelect");
      try {
        image = item;
        ++viewerPreprocessSequence;
        caliperDenoise = false;
        $("#caliperDenoiseToggle").checked = false;
        image.manualCalipers ??= Array.isArray(image.review?.hitl_feedback?.manual_calipers)
          ? image.review.hitl_feedback.manual_calipers.map((caliper) => ({ label: caliper.label, points: caliper.points }))
          : [];
        state.side = side;
        regionReviewUI.setContext({
          studyId: c.study_id,
          imageId: image.image_id,
          reviewId: image.review?.review_id ?? null,
          reviewRevision: c.review_revision ?? 0,
          maskMatchesReview: Boolean(image.review?.verified_mask_rle) &&
            JSON.stringify(encode(image.mask)) === JSON.stringify(image.review.verified_mask_rle),
          canEdit: role() === "BS" && state.editing?.caseId === c.study_id && state.editing.allowed,
          leaseToken: state.editing?.leaseToken ?? null,
          pageInstanceId: state.editing?.pageInstanceId ?? null,
        });
        if (imageSelect) {
          imageSelect.innerHTML = c.images.map((candidate, index) => {
            const sideLabel = candidate.laterality === "L" ? "Trái" : candidate.laterality === "R" ? "Phải" : "Chưa rõ bên";
            return `<option value="${esc(candidate.image_id)}">${sideLabel} · ${index + 1} · ${esc(candidate.filename || candidate.image_id)}</option>`;
          }).join("");
          imageSelect.value = item.image_id;
          imageSelect.disabled = selecting || state.busy || readonly;
          const currentOption = imageSelect.selectedOptions[0];
          imageSelect.setAttribute("aria-label", currentOption?.textContent || "Ảnh hoặc mặt cắt đang xem");
          const currentLabel = $("#viewerImageSelectCurrent");
          if (currentLabel) currentLabel.textContent = `Ảnh ${Math.max(1, c.images.findIndex(candidate => candidate.image_id === item.image_id) + 1)}`;
        }
        researchCandidateUI.resetForSide();
        adnexUI.setEditable(canEvaluateAdnex());
        cdssUI.setEditable(canEvaluateCdss());
        sourceCtx.clearRect(0, 0, 512, 512);
        const dims = image.dimensions || [
          image.width || bitmap.width,
          image.height || bitmap.height,
        ];
        box = letterbox(dims[0], dims[1]);
        if (sourceIsModel) sourceCtx.drawImage(bitmap, 0, 0, 512, 512);
        else
          sourceCtx.drawImage(bitmap, box.left, box.top, box.width, box.height);
        image.seen = true;
        if (!correction) tracker.track(image.image_id, "PREDICTION_VIEWED");
      } catch (error) {
        if (version === selectionSerial && !disposed) {
          selecting = false;
          selectionActive = false;
          image = null;
          state.side = previousSide;
          activeRegionContext = null;
          regionReviewUI.setContext(null);
          regionReviewUI.setEditable(false);
          adnexUI.setEditable(false);
          cdssUI.setEditable(false);
          sourceCtx.clearRect(0, 0, 512, 512);
          maskCtx.clearRect(0, 0, 512, 512);
          outlineCtx.clearRect(0, 0, 512, 512);
          regionHighlightCtx.clearRect(0, 0, 512, 512);
          $("#secondPane").hidden = true;
          uncertainty?.close();
          uncertainty = null;
          showUncertainty = false;
          $("#uncertaintyToggle").checked = false;
          $("#uncertaintyToggle").disabled = true;
          $("#sideLabel").textContent = "Ảnh chưa hiển thị";
          $("#viewerImageSummary").textContent = "Không hiển thị được ảnh. Chọn lại ảnh để thử.";
          const imageSelect = $("#viewerImageSelect");
          if (imageSelect) {
            imageSelect.value = previousImage?.image_id ?? "";
            imageSelect.disabled = state.busy || readonly;
          }
          syncClinicalInputs();
          syncToolButtons();
          syncImageSelectionControls();
          adnexUI.resetForSide(previousSide);
          cdssUI.resetForSide();
          for (const currentSide of ["L", "R"])
            $(`[data-action=side-${currentSide}]`).classList.toggle("primary", currentSide === previousSide);
        }
        throw error;
      } finally {
        bitmap.close();
        if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
      }
      uncertainty?.close();
      uncertainty = null;
      showUncertainty = false;
      $("#uncertaintyToggle").checked = false;
      $("#uncertaintyToggle").disabled = true;
      uncertaintyLabel.hidden = true;
      $('#segmentationDependencyWarning').hidden = true;
      $("#uncertaintyInfo").textContent =
        "Chưa có bản đồ entropy; lớp phủ mặc định tắt và không ảnh hưởng mask.";
      if (image.prediction?.uncertainty_map_base64) {
        const map = await loadUncertaintyMap(
          image.prediction.uncertainty_map_base64,
          window,
        );
        if (version !== selectionSerial || disposed) {
          map?.close();
          return;
        }
        if (map) {
          uncertainty = map;
          $("#uncertaintyToggle").disabled = false;
          uncertaintyLabel.hidden = false;
          $("#uncertaintyInfo").textContent =
            "Bản đồ entropy biểu thị độ bất định của mô hình AI; khác với xác suất chẩn đoán.";
        } else
          $("#uncertaintyInfo").textContent =
            "Bản đồ 512×512 đang tải lại; mask gốc được giữ nguyên.";
      }
      image.mask ??= new Uint8Array(262144);
      image.aiMask ??= image.mask.slice();
      $("#sideLabel").textContent =
        `Buồng trứng ${side === "L" ? "trái" : "phải"} · giữ Space xem ảnh gốc`;
      $("#modelHash").textContent =
        image.prediction?.provenance?.checkpoint_sha256 ||
        image.prediction?.provenance?.model_checksum ||
        "Bản ghi chưa cung cấp SHA-256.";
      renderClassification();
      $("#notes").value = image.notes || "";
      $("#morphology").value = image.morphologyDesc || "";
      if ($("#iotaMorphology")) $("#iotaMorphology").value = image.morphology || "";
      if ($("#oradsScore")) $("#oradsScore").value = image.orads || "";
      selecting = false;
      selectionActive = false;
      if (imageSelect) imageSelect.disabled = state.busy || readonly;
      syncClinicalInputs();
      syncToolButtons();
      syncImageSelectionControls();
      adnexUI.setEditable(canEvaluateAdnex());
      cdssUI.setEditable(canEvaluateCdss());
      for (const s of ["L", "R"])
        $(`[data-action=side-${s}]`).classList.toggle("primary", s === side);
      $("[data-action=sign]").disabled =
        !canEditCanvas() || state.busy || !workflowEnabled || !canReviewFullCase();
      $("[data-action=save-review]").disabled =
        readonly || state.busy || !c.images.every((i) => i.seen);
      syncContentWarning();
      refreshMask();
      fit();
      history();
      measure();
      if (comparison && compareKind !== "original")
        await setComparison(compareKind);
    };
    const paint = (p, q = p) => {
      const radius = brush / 2;
      const steps = Math.max(1, Math.ceil(Math.hypot(p.x - q.x, p.y - q.y)));
      for (let step = 0; step <= steps; step++) {
        const cx = q.x + ((p.x - q.x) * step) / steps,
          cy = q.y + ((p.y - q.y) * step) / steps;
        for (
          let y = Math.max(box.top, Math.floor(cy - radius));
          y < Math.min(box.top + box.height, cy + radius);
          y++
        )
          for (
            let x = Math.max(box.left, Math.floor(cx - radius));
            x < Math.min(box.left + box.width, cx + radius);
            x++
          )
            if ((x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2)
              image.mask[y * 512 + x] = tool === "erase" ? 0 : 1;
      }
      refreshMask({
        x0: Math.floor(Math.min(p.x, q.x) - radius),
        x1: Math.ceil(Math.max(p.x, q.x) + radius),
        y0: Math.floor(Math.min(p.y, q.y) - radius),
        y1: Math.ceil(Math.max(p.y, q.y) + radius),
      });
    };
    const point = (e) =>
      screenToModel(e.clientX, e.clientY, canvas.getBoundingClientRect(), view);
    canvas.addEventListener(
      "pointerdown",
      (e) => {
        if (activePointerId !== null || !e.isPrimary) return;
        canvas.focus();
        canvas.setPointerCapture(e.pointerId);
        activePointerId = e.pointerId;
        if (e.button === 1 || tool === "pan") {
          pan = true;
          last = { x: e.clientX, y: e.clientY };
          e.preventDefault();
          return;
        }
        if (!canEditCanvas() || selecting || state.busy || e.button !== 0 || peek)
          return;
        const p = point(e);
        if (tool === "caliper-d1" || tool === "caliper-d2") {
          const label = tool === "caliper-d1" ? "D1" : "D2";
          if (!pendingCaliper || pendingCaliper.label !== label) {
            pendingCaliper = { label, point: p };
            caliperPreviewPoint = null;
            $("#viewerImageSummary").textContent = `Caliper ${label}: chọn điểm thứ hai.`;
            schedule();
            return;
          }
          const width = image.dimensions?.[0] || image.width || 512;
          const height = image.dimensions?.[1] || image.height || 512;
          const toSource = (point) => [
            (point.x - box.left) * width / box.width,
            (point.y - box.top) * height / box.height,
          ];
      const points = [toSource(pendingCaliper.point), toSource(p)];
          pendingCaliper = null;
          caliperPreviewPoint = null;
          if (points.some(([x, y]) => x < 0 || y < 0 || x >= width || y >= height)) {
            toast("Đặt hai đầu caliper bên trong vùng ảnh nguồn.", true);
            schedule();
            return;
          }
          if (Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) < 1) {
            toast("Hai đầu caliper cần cách nhau ít nhất một pixel.", true);
            schedule();
            return;
          }
          if (activeRegionContext) {
            saveSelectedRegionCaliper(label, points);
            schedule();
            return;
          }
          image.manualCalipers = (image.manualCalipers || []).filter((caliper) => caliper.label !== label);
          image.manualCalipers.push({ label, points });
          state.dirty = true;
          saveDraft();
          saveMaskDraft(c, image);
          syncDraftNotice();
          recordUiEvent(c.study_id, "manual_caliper_set", { image_id: image.image_id, label });
          displayMeasurements(image.measurements);
          schedule();
          return;
        }
        if (tool === "polygon") {
          polygon.push(p);
          schedule();
          return;
        }
        beforeEdit();
        draw = true;
        last = p;
        document.body.classList.add("drawing");
        paint(p);
      },
      events,
    );
    canvas.addEventListener(
      "pointermove",
      (e) => {
        if (activePointerId !== null && e.pointerId !== activePointerId) return;
        const rect = canvas.getBoundingClientRect(),
          cursor = $("#brushCursorV2");
        cursor.hidden = readonly || !["brush", "erase"].includes(tool) || peek;
        cursor.style.width = cursor.style.height = brush * view.scale + "px";
        cursor.style.left = e.clientX - rect.left + "px";
        cursor.style.top = e.clientY - rect.top + "px";
        if (pan) {
          view.x += e.clientX - last.x;
          view.y += e.clientY - last.y;
          last = { x: e.clientX, y: e.clientY };
          schedule();
        } else if (draw) {
          const p = point(e);
          paint(p, last);
          last = p;
        } else if (pendingCaliper) {
          caliperPreviewPoint = point(e);
          schedule();
        }
      },
      events,
    );
    const end = (e) => {
      if (e && (activePointerId === null || e.pointerId !== activePointerId)) return;
      activePointerId = null;
      if (draw) {
        draw = false;
        changed();
      }
      pan = false;
      document.body.classList.remove("drawing");
      if (fitAfterPointer) {
        fitAfterPointer = false;
        fit();
      }
    };
    canvas.addEventListener(
      "pointerleave",
      () => {
        $("#brushCursorV2").hidden = true;
      },
      events,
    );
    canvas.addEventListener("pointerup", end, events);
    canvas.addEventListener("pointercancel", end, events);
    canvas.addEventListener("lostpointercapture", end, events);
    const completePolygon = () => {
      if (
        tool !== "polygon" ||
        polygon.length < 3 ||
        !canEditCanvas() ||
        state.busy
      )
        return false;
      beforeEdit();
      const temp = document.createElement("canvas");
      temp.width = temp.height = 512;
      const g = temp.getContext("2d");
      g.beginPath();
      polygon.forEach((p, i) =>
        i ? g.lineTo(p.x, p.y) : g.moveTo(p.x, p.y),
      );
      g.closePath();
      g.fill();
      const pixels = g.getImageData(0, 0, 512, 512).data;
      for (let y = box.top; y < box.top + box.height; y++)
        for (let x = box.left; x < box.left + box.width; x++)
          if (pixels[(y * 512 + x) * 4 + 3]) image.mask[y * 512 + x] = 1;
      polygon = [];
      refreshMask();
      changed();
      return true;
    };
    canvas.addEventListener(
      "dblclick",
      () => {
        if (!completePolygon()) fit();
      },
      events,
    );
    canvas.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        if (e.altKey) {
          brush = Math.min(64, Math.max(2, brush + (e.deltaY < 0 ? 2 : -2)));
          $("#brushSize").value = brush;
          $("#brushOutput").value = brush;
          const cur = $("#brushCursorV2");
          if (cur) cur.style.width = cur.style.height = brush * view.scale + "px";
          return;
        }
        const p = point(e),
          rect = canvas.getBoundingClientRect();
        view.scale = Math.min(
          12,
          Math.max(0.1, view.scale * (e.deltaY < 0 ? 1.12 : 0.89)),
        );
        view.x = e.clientX - rect.left - p.x * view.scale;
        view.y = e.clientY - rect.top - p.y * view.scale;
        schedule();
      },
      { ...events, passive: false },
    );
    const act = async (action) => {
      if (selecting || state.busy) return;
      if (['brush', 'erase', 'polygon', 'caliper-d1', 'caliper-d2'].includes(action) &&
          !canEditCanvas()) return;
      recordUiEvent(c.study_id, "tool_select", { tool: action });
      if (["brush", "erase", "polygon", "pan", "caliper-d1", "caliper-d2"].includes(action)) {
        tool = action;
        pendingCaliper = null;
        $$("[data-tool]").forEach(
          (b) => (
            b.classList.toggle("active", b.dataset.tool === tool),
            b.setAttribute("aria-pressed", String(b.dataset.tool === tool))
          ),
        );
        canvas.style.cursor = tool === "pan" ? "grab" : tool.startsWith("caliper") ? "copy" : "crosshair";
        return;
      }
      if (action === "fit") return fit();
      if (action === "auto-zoom") return autoZoomLesion();
      if (action === "fullscreen") {
        if (document.fullscreenElement) document.exitFullscreen();
        else root.requestFullscreen();
        return;
      }
      if (!canEditCanvas()) return;
      if (action === "undo") {
        const previous = image.history.pop();
        if (previous) {
          image.redo.push(encode(image.mask));
          image.mask = decode(previous);
          if (!correction) tracker.track(image.image_id, "UNDO");
        }
      } else if (action === "redo") {
        const next = image.redo.pop();
        if (next) {
          image.history.push(encode(image.mask));
          image.mask = decode(next);
          if (!correction) tracker.track(image.image_id, "REDO");
        }
      } else if (["clear", "reset"].includes(action)) {
        if (
          !(await confirmAction(
            action === "clear" ? "Xóa toàn bộ mask?" : "Khôi phục mask AI?",
            "Thao tác có thể hoàn tác. Không thay đổi ảnh gốc.",
          ))
        ) {
          return;
        }
        beforeEdit();
        image.mask =
          action === "clear" ? new Uint8Array(262144) : image.aiMask.slice();
        if (!correction) tracker.track(
          image.image_id,
          action === "clear" ? "CLEAR_MASK" : "RESET_AI",
        );
      } else {
        beforeEdit();
        image.mask = cleanMask(image.mask, action);
      }
      refreshMask();
      changed();
    };
    $$("[data-tool]").forEach((b) => {
      b.onclick = () => act(b.dataset.tool);
    });
    syncToolButtons();
    $$("[data-action^=side-]").forEach(
      (b) =>
        (b.onclick = () =>
          select(b.dataset.action.slice(-1)).catch((e) =>
            { if (e.name !== "AbortError") toast(e.message, true); },
          )),
    );
    $("#viewerImageSelect").onchange = (event) => {
      const selectedImage = c.images.find((candidate) => candidate.image_id === event.target.value);
      if (selectedImage) select(selectedImage.laterality, selectedImage.image_id).catch((error) => {
        if (error.name !== "AbortError") toast(error.message, true);
      });
    };
    $$("[data-action^=layer-]").forEach(
      (b) =>
        (b.onclick = () => {
          layer = Number(b.dataset.action.slice(-1));
          schedule();
        }),
    );
    $$("[data-action^=layer-]").forEach(
      (b) => (b.onclick = () => setLayer(Number(b.dataset.action.slice(-1)))),
    );
    overlayVisibilityButton.onclick = toggleOverlayVisibility;
    $("[data-action=contour]").onclick = () => {
      contour = !contour;
      schedule();
    };
    const setComparison = async (kind) => {
      const comparisonId = ++comparisonSerial,
        selected = image;
      compareKind = kind;
      comparison = true;
      if (kind !== "original") {
        const other =
          kind === "bilateral" ? c.images.find((i) => i !== image) : image;
        if (!other) return toast("Chưa có ảnh bên còn lại.", true);
        let decodedSourceUrl = null;
        let sourceImage = other.source;
        let sourceIsModel = other.sourceIsModel;
        if (!sourceImage || sourceIsModel) {
          decodedSourceUrl = await protectedImage(
            "/api/images/" + encodeURIComponent(other.image_id) + "/source.png",
          );
          sourceImage = decodedSourceUrl;
          sourceIsModel = false;
        }
        let bitmap;
        try {
          bitmap = await imageSourceBitmap(sourceImage);
        } catch (error) {
          if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
          throw error;
        }
        if (
          disposed ||
          comparisonId !== comparisonSerial ||
          selected !== image
        ) {
          bitmap.close();
          if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
          return;
        }
        let g;
        try {
          g = compareCanvas.getContext("2d");
          g.clearRect(0, 0, 512, 512);
          const b = letterbox(
            other.width || other.dimensions?.[0] || bitmap.width,
            other.height || other.dimensions?.[1] || bitmap.height,
          );
          g.drawImage(
            bitmap,
            sourceIsModel ? 0 : b.left,
            sourceIsModel ? 0 : b.top,
            sourceIsModel ? 512 : b.width,
            sourceIsModel ? 512 : b.height,
          );
        } finally {
          bitmap.close();
          if (decodedSourceUrl) URL.revokeObjectURL(decodedSourceUrl);
        }
        const temp = document.createElement("canvas");
        temp.width = temp.height = 512;
        const tc = temp.getContext("2d"),
          pixels = tc.createImageData(512, 512),
          values = kind === "ai" ? other.aiMask : other.mask;
        for (let n = 0; n < values.length; n++)
          if (values[n]) pixels.data.set([98, 233, 224, 90], n * 4);
        tc.putImageData(pixels, 0, 0);
        g.drawImage(temp, 0, 0);
      }
      $("#secondPane .canvas-label").textContent =
        kind === "bilateral"
          ? "Bên còn lại · chỉ xem"
          : kind === "ai"
            ? "Mask AI gốc"
            : "Ảnh gốc";
      $("#secondPane").hidden = false;
      fit();
    };
    $("[data-action=compare]").onclick = () => {
      if (comparison && compareKind === "original") {
        comparison = false;
        $("#secondPane").hidden = true;
        fit();
      } else setComparison("original").catch((e) => toast(e.message, true));
    };
    for (const [action, kind] of [
      ["bilateral", "bilateral"],
      ["ai-compare", "ai"],
    ])
      $("[data-action=" + action + "]").onclick = () =>
        setComparison(kind).catch((e) => toast(e.message, true));
    $("#brushSize").oninput = (e) => {
      brush = Number(e.target.value);
      $("#brushOutput").value = brush;
    };
    $("#opacity").oninput = (e) => {
      opacity = Number(e.target.value) / 100;
      schedule();
    };
    $("#uncertaintyToggle").onchange = (e) => {
      showUncertainty = e.target.checked;
      $('#uncertaintyInfo').hidden = !showUncertainty;
      $('#uncertaintyInfo').textContent = 'Độ bất định của mô hình không phải xác suất ác tính.';
      schedule();
    };
    $("#displayPreset").onchange = (e) => {
      const values = {
        normal: [100, 100],
        dim: [85, 105],
        contrast: [100, 140],
      }[e.target.value];
      [brightness, contrast] = values;
      $("#brightness").value = brightness;
      $("#contrast").value = contrast;
      schedule();
    };
    for (const id of ["brightness", "contrast"])
      $("#" + id).oninput = (e) => {
        if (id === "brightness") brightness = Number(e.target.value);
        else contrast = Number(e.target.value);
        schedule();
      };
    const caliperDenoiseButton = $(`[data-action="toggle-caliper-denoise"]`);
    const caliperDenoiseCheckbox = $(`#caliperDenoiseToggle`);
    let viewerPreprocessSequence = 0;
    const setCaliperDenoise = (activeState) => {
      caliperDenoise = Boolean(activeState);
      if (caliperDenoiseButton) {
        caliperDenoiseButton.setAttribute("aria-pressed", String(caliperDenoise));
        caliperDenoiseButton.classList.toggle("primary", caliperDenoise);
      }
      if (caliperDenoiseCheckbox) {
        caliperDenoiseCheckbox.checked = caliperDenoise;
      }
      toast(
        caliperDenoise
          ? "Đang tải ảnh lọc đốm để đối chiếu…"
          : "Đang khôi phục ảnh hiển thị mặc định…"
      );

      // Live Backend Integration: Fetch enhanced / original image from API with race condition protection (F04)
      if (image?.image_id) {
        const targetImage = image;
        const seq = ++viewerPreprocessSequence;
        const query = caliperDenoise
          ? "?enable_caliper_removal=false&denoise_method=lee"
          : "?enable_caliper_removal=false&denoise_method=none";
        request(`/api/images/${encodeURIComponent(image.image_id)}/viewer-source${query}`)
          .then(async (res) => {
            if (seq !== viewerPreprocessSequence || disposed || image !== targetImage) return;
            if (res?.original_image_base64) {
              const enhancedBitmap = await imageSourceBitmap(res.original_image_base64);
              try {
                if (seq === viewerPreprocessSequence && !disposed && image === targetImage) {
                  sourceCtx.clearRect(0, 0, 512, 512);
                  sourceCtx.drawImage(enhancedBitmap, 0, 0, 512, 512);
                  schedule();
                  if (caliperDenoise) {
                    toast("Đã áp dụng lọc đốm âm học thành công.");
                  }
                }
              } finally {
                enhancedBitmap.close?.();
              }
            }
          })
          .catch((err) => {
            if (seq === viewerPreprocessSequence) {
              console.warn("Lỗi cập nhật ảnh tiền xử lý:", err);
              toast("Lỗi tiền xử lý ảnh: " + (err.message || err), true);
              schedule();
            }
          });
      } else {
        schedule();
      }
    };

    if (caliperDenoiseButton) {
      caliperDenoiseButton.onclick = () => setCaliperDenoise(!caliperDenoise);
    }
    if (caliperDenoiseCheckbox) {
      caliperDenoiseCheckbox.onchange = (e) => setCaliperDenoise(e.target.checked);
    }

    const btnRerunAI = $(`[data-action="rerun-ai-model"]`);
    if (btnRerunAI) {
      btnRerunAI.onclick = async () => {
        if (!image?.image_id) return toast("Chưa chọn ảnh để chạy dự đoán.", true);
        if (state.busy) return toast("Hệ thống đang xử lý tác vụ khác, vui lòng chờ giây lát.", true);
        if (!canEditCanvas() || selecting || correction || state.dirty || image.review) return;
        const targetImage = image;
        setBusy(true);
        const query = "?generate_overlay=true";
        toast("Đang phân tích lại bằng checkpoint đã xác minh…");
        try {
          const headers = { "Idempotency-Key": crypto.randomUUID() };
          if (state.editing?.leaseToken) {
            headers["X-Case-Lease-Token"] = state.editing.leaseToken;
            headers["X-Case-Page-Instance-Id"] = state.editing.pageInstanceId;
          }
          const pred = await request(`/api/predict/${encodeURIComponent(image.image_id)}${query}`, {
            method: "POST",
            headers,
          });
          if (pred && !disposed && image === targetImage && canEditCanvas()) {
            ++viewerPreprocessSequence;
            caliperDenoise = false;
            $("#caliperDenoiseToggle").checked = false;
            image.prediction = pred;
            renderClassification();
            if (pred.rle_mask) {
              const decodedMask = decode(pred.rle_mask);
              image.mask = decodedMask;
              image.aiMask = decodedMask.slice();
            }
            if (pred.measurements) {
              image.measurements = pred.measurements;
              displayMeasurements(pred.measurements);
            }
            if (pred.original_image_base64) {
              const bmp = await imageSourceBitmap(pred.original_image_base64);
              try {
                if (!disposed && image === targetImage) {
                  sourceCtx.clearRect(0, 0, 512, 512);
                  sourceCtx.drawImage(bmp, 0, 0, 512, 512);
                }
              } finally { bmp.close?.(); }
            }
            schedule();
            toast("Đã cập nhật đề xuất AI; cần bác sĩ rà soát.");
          }
        } catch (err) {
          toast(err.message || "Lỗi khi chạy dự đoán mô hình.", true);
        } finally {
          setBusy(false);
        }
      };
    }

    $("[data-action=image-reset]").onclick = () => {
      brightness = contrast = 100;
      $("#brightness").value = $("#contrast").value = 100;
      if (caliperDenoise) {
        caliperDenoise = false;
        if (caliperDenoiseButton) {
          caliperDenoiseButton.setAttribute("aria-pressed", "false");
          caliperDenoiseButton.classList.remove("primary");
        }
        if (caliperDenoiseCheckbox) caliperDenoiseCheckbox.checked = false;
        if (image?.image_id) {
          const resetSeq = ++viewerPreprocessSequence;
          request(`/api/images/${encodeURIComponent(image.image_id)}/viewer-source?enable_caliper_removal=false&denoise_method=none`)
            .then(async (res) => {
              if (resetSeq !== viewerPreprocessSequence || disposed) return;
              if (res?.original_image_base64) {
                const rawBitmap = await imageSourceBitmap(res.original_image_base64);
                try {
                  if (resetSeq === viewerPreprocessSequence && !disposed) {
                    sourceCtx.clearRect(0, 0, 512, 512);
                    sourceCtx.drawImage(rawBitmap, 0, 0, 512, 512);
                    schedule();
                  }
                } finally {
                  rawBitmap.close?.();
                }
              }
            })
            .catch((err) => {
              if (resetSeq === viewerPreprocessSequence) {
                toast("Lỗi khôi phục ảnh: " + (err.message || err), true);
                schedule();
              }
            });
        }
      }
      schedule();
    };
    for (const id of ["notes", "morphology"])
      $("#" + id).oninput = (e) => {
        if (id === "notes") {
          const isBoundaryInput =
            e.inputType === "insertFromPaste" ||
            e.inputType === "insertLineBreak" ||
            e.inputType === "insertParagraph" ||
            (typeof e.data === "string" &&
              /^[\s.,;:!?()[\]{}]+$/u.test(e.data));
          if (isBoundaryInput) {
            const expansion = expandDraftPhrase(
              e.target.value,
              e.target.selectionStart,
              e.target.selectionEnd,
              {
                isComposing: e.isComposing,
                readOnly: state.busy || readonly || selecting || !image || !state.editing?.allowed,
              },
            );
            if (expansion.expanded) {
              e.target.value = expansion.text;
              e.target.setSelectionRange(
                expansion.selectionStart,
                expansion.selectionStart,
              );
            }
          }
        }
        if (state.busy || !canEditCanvas() || selecting || !image) {
          e.target.value = (id === "morphology" ? image?.morphologyDesc : image?.[id]) || "";
          return;
        }
        if (id === "morphology") image.morphologyDesc = e.target.value;
        else image[id] = e.target.value;
        changed({ refreshMeasurements: id !== "notes" });
      };
    if ($("#iotaMorphology")) {
      const handleIota = (e) => {
        if (state.busy || !canEditCanvas() || selecting || !image) {
          if (image) e.target.value = image.morphology || "";
          return;
        }
        if (image) image.morphology = e.target.value;
        state.dirty = true;
        changed();
      };
      $("#iotaMorphology").onchange = handleIota;
      $("#iotaMorphology").oninput = handleIota;
    }
    if ($("#oradsScore")) {
      const handleOrads = (e) => {
        if (state.busy || !canEditCanvas() || selecting || !image) {
          if (image) e.target.value = image.orads || "";
          return;
        }
        if (image) image.orads = e.target.value;
        state.dirty = true;
        recordUiEvent(c.study_id, "field_edit", { field: "oradsScore", value: $("#oradsScore").value, source: "manual" });
        changed({
          refreshMeasurements: false,
          persistDraft: e.detail?.source !== "quick-pick",
        });
      };
      $("#oradsScore").onchange = handleOrads;
      $("#oradsScore").oninput = handleOrads;
    }
    const renderCustomChips = () => {
      const wrap = $("#customChipsWrap");
      if (!wrap) return;
      const customChips = image?.customChips || [];
      wrap.innerHTML = customChips.map((tag) => 
        `<span class="chip-custom-wrap"><button type="button" class="chip custom" data-chip="${esc(tag)}">${esc(tag)}</button><button type="button" class="chip-remove" data-remove-chip="${esc(tag)}" title="Xóa đặc điểm" aria-label="Xóa ${esc(tag)}">×</button></span>`
      ).join("");
      wrap.querySelectorAll("[data-chip]").forEach((b) => {
        b.disabled = readonly;
        b.onclick = () => {
          if (state.busy || !canEditCanvas() || selecting || !image) return;
          image.morphology = [image.morphology, b.dataset.chip]
            .filter(Boolean)
            .join("; ")
            .slice(0, 100);
          $("#morphology").value = image.morphology;
          changed();
        };
      });
      wrap.querySelectorAll("[data-remove-chip]").forEach((btn) => {
        btn.onclick = () => {
          const toRemove = btn.dataset.removeChip;
          image.customChips = (image.customChips || []).filter(c => c !== toRemove);
          renderCustomChips();
        };
      });
    };

    const addChipBtn = $("[data-action=add-chip]");
    if (addChipBtn) {
      addChipBtn.disabled = readonly;
      addChipBtn.onclick = () => {
        if (state.busy || !canEditCanvas() || selecting || !image) return;
        modal(
          "Thêm đặc điểm lâm sàng",
          `<label class="field">Tên đặc điểm mới<input name="custom_tag" type="text" maxlength="30" placeholder="VD: Vách dày, Dịch vẩn..." required></label><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" type="submit">Thêm đặc điểm</button></div>`,
          (event, dialog) => {
            const data = Object.fromEntries(new FormData(event.target));
            const tag = String(data.custom_tag || "").trim();
            if (tag) {
              image.customChips = image.customChips || [];
              if (!image.customChips.includes(tag)) {
                image.customChips.push(tag);
                renderCustomChips();
              }
            }
            dialog.close();
          }
        );
      };
    }
    renderCustomChips();

    $$("[data-chip]").forEach((b) => {
      b.disabled = readonly;
      b.onclick = () => {
        if (state.busy || !canEditCanvas() || selecting || !image) return;
        image.morphology = [image.morphology, b.dataset.chip]
          .filter(Boolean)
          .join("; ")
          .slice(0, 100);
        $("#morphology").value = image.morphology;
        changed();
      };
    });
    $("[data-action=sign]").hidden = role() !== "BS";
    $("[data-action=save-review]").hidden = role() !== "BS";
    $("[data-action=manual]").hidden = $("[data-action=no-lesion]").hidden =
      readonly;
    $("[data-action=manual]").onclick = () => act("clear");
    $("[data-action=no-lesion]").onclick = async () => {
      await act("clear");
    };
    const correctionSave = $("[data-action=save-correction]");
    if (correctionSave) {
      correctionSave.disabled = readonly;
      correctionSave.onclick = () => {
        if (!readonly) saveCorrection();
      };
    }
    $("[data-action=sign]").onclick = () => openSignoff();
    $("[data-action=save-review]").disabled = true;
    $("[data-action=save-review]").onclick = async () => {
      const savedCase = state.case;
      if (!savedCase || state.busy) return;
      if (savedCase.status === "REVIEWED" && !state.dirty) {
        window.dispatchEvent(new CustomEvent("ova:next-case", { detail: 1 }));
        return;
      }
      const startingRevision = savedCase.review_revision ?? 0;
      const saveStatus = $('#assessmentSaveStatus');
      saveStatus.dataset.saving = 'true'; saveStatus.dataset.error = '';
      saveStatus.textContent = 'Đang lưu';
      const savePromise = saveResearchReview();
      root.dispatchEvent(new CustomEvent("ova:review-lock-changed"));
      try {
        const outcome = await savePromise;
        const confirmed = outcome?.status === 'saved' && outcome.clean === true;
        saveStatus.textContent = confirmed ? 'Đã lưu' : 'Lưu không thành công';
        saveStatus.dataset.error = confirmed ? '' : 'true';
      } finally {
        saveStatus.dataset.saving = 'false';
        root.dispatchEvent(new CustomEvent("ova:review-lock-changed"));
      }
      if (
        state.case === savedCase &&
        savedCase.status === "REVIEWED" &&
        (savedCase.review_revision ?? 0) > startingRevision &&
        !state.dirty &&
        !state.busy
      )
        window.dispatchEvent(new CustomEvent("ova:next-case", { detail: 1 }));
    };
    const researchExportButton = $("[data-action=export-research]");
    const researchExportDisabledMessage =
      "Xuất dữ liệu tham khảo đang khóa đến khi có hồ sơ xác minh phê duyệt, consent và khử định danh.";
    researchExportButton.title = researchExportDisabledMessage;
    researchExportButton.setAttribute("aria-label", "Xuất dữ liệu tham khảo — đang khóa");
    researchExportButton.onclick = () => toast(researchExportDisabledMessage, true);
    $("[data-action=shortcuts-help]").onclick = () => {
      location.hash = "#help/shortcuts";
    };
    $("[data-action=logout]").onclick = logout;
    const panelToggle = $("[data-action=panel-toggle]");
    panelToggle.setAttribute("aria-controls", "clinicalPanel");
    panelToggle.setAttribute("aria-expanded", "false");
    panelToggle.onclick = () =>
      panelToggle.setAttribute(
        "aria-expanded",
        String(document.body.classList.toggle("panel-open")),
      );
    const triggerQuickPrint = async () => {
      if (state.busy || !canEditCanvas() || selecting || !image || state.case !== c) return;
      const unseen = c.images.find(img => !img.seen);
      if (unseen) {
        toast("Xem đủ hai bên trước khi lưu rồi in. Dùng Xem phiếu để xem trước kết quả.", true);
        $(`[data-action=side-${unseen.laterality}]`)?.focus();
        return;
      }
      const printButton = $("[data-action=quick-print]");
      printButton.disabled = true;
      try {
        const outcome = await saveResearchReview();
        if (outcome?.status !== "saved" || !outcome.clean || state.case !== c ||
            state.dirty || disposed || !root.isConnected || outcome.studyId !== c.study_id) return;
        recordUiEvent(c.study_id, "print_click");
        location.hash = "#report/" + encodeURIComponent(c.study_id) + "?print=1&revision=" + outcome.revision;
      } finally {
        if (!disposed && root.isConnected) printButton.disabled = !canEditCanvas();
      }
    };
    $("[data-action=quick-print]").disabled = !canEditCanvas();
    $("[data-action=quick-print]").onclick = triggerQuickPrint;
    $("[data-action=report]").onclick = () => {
      location.hash = "#report/" + encodeURIComponent(c.study_id);
    };
    $("[data-action=calibrate]").onclick = () => {
      if (!canEditCanvas() || state.busy || !state.editing.leaseToken)
        return toast("Ca đang ở chế độ chỉ xem hoặc đang lưu.");
      modal(
        "Hiệu chuẩn thước đo",
        field(
          "Khoảng cách trên ảnh gốc (pixel)",
          "pixels",
          "number",
          "",
          'min="1" step="any" required',
        ) +
          field(
            "Khoảng cách trên thước (mm)",
            "mm",
            "number",
            "",
            'min="0.01" step="any" required',
          ) +
          '<p class="small muted">Nhập khoảng cách của vạch thước đã biết. Không suy đoán tỷ lệ từ kích thước ảnh.</p><button class="btn primary" type="submit">Áp dụng</button>',
        async (e, d) => {
          if (!canEditCanvas() || !state.editing.leaseToken) {
            toast("Quyền chỉnh sửa ca đã hết hạn. Hãy tải lại ca để tiếp tục.", true);
            return;
          }
          const data = Object.fromEntries(new FormData(e.target)),
            spacing = Number(data.mm) / Number(data.pixels);
          if (!Number.isFinite(spacing) || spacing <= 0) return;
          const submitButton = e.target.querySelector('button[type="submit"]');
          if (submitButton?.disabled) return;
          if (submitButton) submitButton.disabled = true;
          const targetImage = image;
          ++serial;
          clearTimeout(timer);
          $("#d1").textContent = "Đang cập nhật…";
          $("#d2").textContent = "Đang cập nhật…";
          $("#area").textContent = "Đang cập nhật…";
          try {
            {
              const calibration = await request(
                "/api/images/" +
                  encodeURIComponent(targetImage.image_id) +
                  "/calibrate?pixel_spacing_mm=" +
                  encodeURIComponent(spacing),
                {
                  method: "POST",
                  headers: {
                    "X-Case-Lease-Token": state.editing.leaseToken,
                    "X-Case-Page-Instance-Id": state.editing.pageInstanceId,
                  },
                },
              );
              applyCalibrationAck(targetImage, calibration);
              state.dirty = true;
              syncDraftNotice();
              if (!disposed && image === targetImage) measure();
            }
            d.close();
          } catch (err) {
            if (!disposed && image === targetImage) measure();
            toast(err.message, true);
          } finally {
            if (submitButton) submitButton.disabled = false;
          }
        },
      );
    };
    const key = (e) => {
      if (document.querySelector("dialog[open]")) return;
      if (e.isComposing || e.keyCode === 229) return;
      const reportHash = getReportShortcutHash(e, c.study_id);
      if (reportHash) {
        e.preventDefault();
        // Ctrl+P explicitly opens a labelled draft, without saving or marking images seen.
        if (!state.busy && !selecting) location.hash = reportHash;
        return;
      }
      if (state.busy || selecting) return;
      if (
        (e.ctrlKey || e.metaKey || e.altKey) &&
        String(e.key).toLowerCase() === "p"
      )
        return;
      if (e.target?.closest?.("input,textarea,select,[contenteditable],button,a,summary,[role=button],[role=menuitem]")) return;
      if (e.code === "Space") {
        e.preventDefault();
        peek = true;
        syncOverlayVisibility();
        schedule();
        return;
      }
      if (
        (e.ctrlKey || e.metaKey) &&
        ["s", "enter"].includes(e.key.toLowerCase())
      ) {
        e.preventDefault();
        const saveButton = $("[data-action=save-review]");
        if (!saveButton.hidden && !saveButton.disabled) saveButton.click();
        return;
      }
      if (isUndoShortcut(e)) {
        e.preventDefault();
        act(e.shiftKey || (e.ctrlKey && e.key.toLowerCase() === "y") ? "redo" : "undo");
        return;
      }
      if (isAutoZoomShortcut(e)) {
        e.preventDefault();
        act("auto-zoom");
        return;
      }
      const oradsVal = getOradsShortcutValue(e);
      if (oradsVal) {
        e.preventDefault();
        const oradsSelect = $("#oradsScore");
        if (oradsSelect && !oradsSelect.disabled) {
          oradsSelect.value = oradsVal;
          if (image) image.orads = oradsVal;
          changed();
          saveDraft();
          toast(`Đã gán nhanh ${oradsVal}`);
        }
        return;
      }
      if (
        (e.ctrlKey || e.metaKey) &&
        ["z", "y"].includes(e.key.toLowerCase())
      ) {
        e.preventDefault();
        act(e.key.toLowerCase() === "y" || e.shiftKey ? "redo" : "undo");
        return;
      }
      const k = e.key.toLowerCase();
      const map = {
        b: "brush",
        e: "erase",
        c: image.manualCalipers?.some((caliper) => caliper.label === "D1") ? "caliper-d2" : "caliper-d1",
        h: "pan",
        l: "polygon",
        s: "smooth",
        r: e.shiftKey ? "clear" : "reset",
        f: "fullscreen",
        0: "fit",
      };
      if (map[k]) {
        e.preventDefault();
        act(map[k]);
      } else if (k === "x") act(tool === "erase" ? "brush" : "erase");
      else if (k === "escape" && pendingCaliper) {
        pendingCaliper = null;
        caliperPreviewPoint = null;
        schedule();
      } else if (k === "backspace" && tool.startsWith("caliper")) {
        e.preventDefault();
        const label = tool === "caliper-d1" ? "D1" : "D2";
        image.manualCalipers = (image.manualCalipers || []).filter((caliper) => caliper.label !== label);
        state.dirty = true;
        saveDraft();
        saveMaskDraft(c, image);
        syncDraftNotice();
        displayMeasurements(image.measurements);
        schedule();
      }
      else if (k === "g") {
        e.preventDefault();
        if (!document.querySelector("#modal[open]")) completePolygon();
      }
      else if (k === "o") {
        e.preventDefault();
        toggleOverlayVisibility();
      }
      else if (["1", "2", "3"].includes(k)) {
        setLayer(Number(k) - 1);
      } else if (k === "k") {
        contour = !contour;
        schedule();
      } else if (k === "c") $("[data-action=compare]").click();
      else if (k === "[" || k === "]") {
        brush = Math.max(2, Math.min(64, brush + (k === "]" ? 2 : -2)));
        $("#brushSize").value = brush;
        $("#brushOutput").value = brush;
        const cur = $("#brushCursorV2");
        if (cur) cur.style.width = cur.style.height = brush * view.scale + "px";
      } else if (["arrowleft", "arrowright"].includes(k)) {
        e.preventDefault();
        select(k === "arrowleft" ? "L" : "R");
      } else if (k === "t" || (k === "p" && !e.shiftKey)) {
        e.preventDefault();
        select(k === "t" ? "L" : "R");
      } else if (k === "n" || (k === "p" && e.shiftKey)) {
        e.preventDefault();
        window.dispatchEvent(
          new CustomEvent("ova:next-case", { detail: k === "n" ? 1 : -1 }),
        );
      } else if (k === "?") location.hash = "#help/shortcuts";
    };
    window.addEventListener("keydown", key, events);
    window.addEventListener(
      "keyup",
      (e) => {
        if (e.code !== "Space" || !peek) return;
        peek = false;
        syncOverlayVisibility();
        schedule();
      },
      events,
    );
    window.addEventListener(
      "blur",
      () => {
        peek = false;
        syncOverlayVisibility();
        end();
        schedule();
      },
      events,
    );
    const observer = new ResizeObserver(() => {
      if (activePointerId !== null) {
        fitAfterPointer = true;
        return;
      }
      fit();
    });
    observer.observe($("#pane"));
    window.addEventListener(
      "ova:lease-lost",
      () => {
        readonly = true;
        $("#leaseLostNotice").hidden = false;
        syncToolButtons();
        dictation.cancel();
        $("#dictationRecord").disabled = true;
        $("#dictationInsert").disabled = true;
        $("#dictationDiscard").disabled = true;
        adnexUI.disable();
        cdssUI.setEditable(false);
        researchCandidateUI.resetForSide();
        end();
        state.editing = { caseId: c.study_id, allowed: false };
        for (const action of [
          "sign",
          "quick-print",
          "save-review",
          "save-correction",
          "calibrate",
          "manual",
          "no-lesion",
        ]) {
          const b = $("[data-action=" + action + "]");
          if (b) b.disabled = true;
        }
        $("#notes").disabled = $("#morphology").disabled = true;
        if ($("#iotaMorphology")) $("#iotaMorphology").disabled = true;
        if ($("#oradsScore")) $("#oradsScore").disabled = true;
        $$("[data-chip]").forEach((b) => (b.disabled = true));
      },
      events,
    );
    $("[data-action=lease-reload]").addEventListener("click", () => {
      saveDraft();
      if (image) saveMaskDraft(c, image);
      window.location.reload();
    });
    const onVisibilityChange = () => {
      if (!image) return;
      if (!correction) {
        if (document.hidden) tracker.recordPause(image.image_id);
        else tracker.recordResume(image.image_id);
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    active = {
      select,
      act,
      render: schedule,
    };
    const release = () => {
      disposed = true;
      dictation.dispose();
      adnexUI.destroy();
      cdssUI.destroy();
      researchCandidateUI.destroy();
      regionReviewUI.destroy();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (state.editing?.caseId === c.study_id) state.editing = null;
      lease?.release();
      abort.abort();
      observer.disconnect();
      worker.terminate();
      measurementQueue.dispose();
      for (const item of c.images || []) {
        if (!item.sourceIsObjectUrl || !item.source?.startsWith("blob:")) continue;
        URL.revokeObjectURL(item.source);
        item.source = null;
        item.sourceIsObjectUrl = false;
      }
      uncertainty?.close();
      clearTimeout(timer);
      cancelAnimationFrame(frame);
      active = null;
      document.body.classList.remove("drawing", "panel-open");
    };
    cleanup = release;
    state.cleanup = release;
    if (state.preferences.layout === "side") {
      comparison = true;
      $("#secondPane").hidden = false;
    }
    if (
      lease?.editable &&
      role() === "BS" &&
      (tracker.getStudyId() !== c.study_id || !tracker.getSessionId() || tracker.isComplete())
    ) {
      try {
        const session = await tracker.startSession(
          c.study_id,
          {
            participant_code: state.user.username,
            participant_role: state.capabilities?.synthetic_demo_mode === true ? "technical_tester" : "clinician",
            data_origin: state.capabilities?.synthetic_demo_mode === true ? "demo" : "live",
            local_owner_id: state.user.id,
          },
          {
            "X-Case-Lease-Token": lease.leaseToken(),
            "X-Case-Page-Instance-Id": lease.pageInstanceId,
          },
        );
        state.hitl_session = session.id;
        for (const image of c.images)
          tracker.startTask(image.image_id, image.prediction?.prediction_id ?? null);
      } catch (error) {
        console.warn("HITL session restore notice:", error);
      }
    }
    recordUiEvent(c.study_id, "case_open");
    await select(
      c.images.some((i) => i.laterality === "L")
        ? "L"
        : c.images[0]?.laterality,
    );
    return release;
  } catch (e) {
    cleanup();
    root.innerHTML = errorBox(e.message);
    $("[data-action=retry]")?.addEventListener("click", () =>
      renderViewer(root, id, { readonly }),
    );
  }
}
