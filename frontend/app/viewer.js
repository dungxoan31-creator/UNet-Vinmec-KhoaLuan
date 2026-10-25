import { acquireLease } from "./leases.js";
import { logout } from "./auth.js";
import { saveCorrection } from "./corrections.js";
import { state, role, saveDraft, keepServerVersion } from "./state.js";
import { openCase } from "./cases.js";
import { request } from "./api.js";
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
import { imageSourceBlob } from "./image-source.js";
import { adnexPanelMarkup, bindAdnexPanel } from "./adnex.js";
import { bindCdssPanel, cdssPanelMarkup } from "./cdss-panel.js";
import { bindResearchCandidate, researchCandidateMarkup } from "./research-candidate.js";
import { loadUncertaintyMap } from "./uncertainty-map.js";
import { bindLocalDictation } from "./voice-dictation.js";
import { getReportShortcutHash } from "./viewer-shortcuts.js";
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
    const correction = role() === "TK" && c.correction_by === state.user.id;
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
    if (lease?.editable) {
      const telemetryLeaseHeaders = {
        "X-Case-Lease-Token": lease.leaseToken(),
        "X-Case-Page-Instance-Id": lease.pageInstanceId,
      };
      tracker
        .flushPendingEvents(c.study_id, telemetryLeaseHeaders, state.user?.id)
        .then(({ replayedEventCount, skippedSessionCount }) => {
          if (replayedEventCount > 0)
            toast("Đã khôi phục và đồng bộ nhật ký HITL của phiên trước.");
          if (skippedSessionCount > 0)
            console.warn("Pending HITL events belong to another signed-in user.");
        })
        .catch((error) => {
          console.warn("Pending HITL telemetry replay failed:", error);
          toast("Nhật ký HITL của phiên trước chưa đồng bộ; thử lại khi mở lại ca.", true);
        });
    }
    const workflowEnabled = state.capabilities?.case_workflow === true;
    const workflowStage =
      workflowEnabled
        ? "<li>Ký sơ bộ hai bên</li>"
        : "<li>Lưu rà soát nghiên cứu (RUO)</li>";
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
          <span class="muted small case-pid">PID ${ esc(c.patient_id)}</span>
        </div>
        ${ badge(c.status)}
      </div>
      <div class="side-switch" role="group" aria-label="Buồng trứng đang xem">
        ${ button("Trái (T)", "side-L", "small primary")}
        ${ button("Phải (P)", "side-R", "small")}
      </div>
      <div class="viewer-head-actions actions">
        ${ button("Lưu rồi in", "quick-print", "small primary viewer-quick-print-action", "print")}
        ${ button("Xem phiếu", "report", "small quiet viewer-report-action")}
        ${ button("?", "shortcuts-help", "small quiet viewer-help-action")}
        <div class="viewer-save-action">
          ${ button("Lưu & Tiếp tục", "save-review", "quiet")}
          <kbd>Ctrl+S</kbd>
        </div>
        <details class="viewer-more-actions">
          <summary class="icon-btn" aria-label="Thao tác khác" title="Thao tác khác">${ icon("menu")}</summary>
          <div class="viewer-more-menu">
            ${ button("Tải kết quả nghiên cứu", "export-research", "small")}
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
              ${ button("Mặc định", "image-reset", "small")}
              <span class="muted small" id="draftStatus">Bản nháp trên thiết bị</span>
            </div>
          </details>
        </div>
      </section>
      <aside class="viewer-panel" aria-label="Thông tin lâm sàng">
        <div class="panel-tabs" role="tablist" aria-label="Thông tin ca">
          <button type="button" class="active" id="clinicalTab" role="tab" aria-selected="true" aria-controls="clinicalPanel" tabindex="0" data-panel-tab="clinical">Lâm sàng</button>
          <button type="button" id="researchTab" role="tab" aria-selected="false" aria-controls="researchPanel" tabindex="-1" data-panel-tab="research">Mở rộng &amp; RUO</button>
        </div>
        <section class="viewer-tabpanel" id="clinicalPanel" role="tabpanel" aria-labelledby="clinicalTab" tabindex="0">
          <div class="clinical-panel-notices">
            ${ lease && lease.label ? '<div class="banner info small">' + esc(lease.label) + "</div>" : ""}
            ${ c.reason ? '<div class="banner warning small">Yêu cầu sửa: ' + esc(c.reason) + "</div>" : ""}
            ${ state.draftConflict ? '<div class="banner warning small">Bản nháp dựa trên phiên bản cũ. Đang hiển thị bản máy chủ.' + button("Tải bản nháp cũ", "download-conflict", "small") + button("Giữ bản máy chủ", "keep-server", "small") + "</div>" : ""}
          </div>
          <div id="viewerWarnings"></div>
          <h3>Phân loại hình thái &amp; nguy cơ</h3>
          <label class="field">Hình thái IOTA (ISUOG)
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
              <option value="">-- Chọn O-RADS --</option>
              <option value="O-RADS 1">O-RADS 1 - Bình thường / Nang sinh lý (&lt;30mm)</option>
              <option value="O-RADS 2">O-RADS 2 - Lành tính (&lt;1% nguy cơ)</option>
              <option value="O-RADS 3">O-RADS 3 - Nguy cơ thấp (1% - &lt;10%)</option>
              <option value="O-RADS 4">O-RADS 4 - Nguy cơ trung bình (10% - &lt;50%)</option>
              <option value="O-RADS 5">O-RADS 5 - Nguy cơ cao (≥50%)</option>
            </select>
          </label>
          <details class="orads-quick-pick-menu" id="oradsQuickPickMenu">
            <summary class="btn small">Chọn nhanh O-RADS</summary>
            <div class="orads-quick-pick" id="oradsQuickPick" role="group" aria-label="Chọn mức O-RADS"></div>
          </details>
          <p id="oradsHelp" class="muted small">Lựa chọn này do bác sĩ nhập; hệ thống không tự suy luận O-RADS. Để trống khi chưa đủ thông tin.</p>
          <p class="muted small">Giới hạn đối chiếu nang noãn: &lt;30 mm theo policy nghiên cứu; mốc ACR US v2022 là ≤3 cm. Ngoài phạm vi không đồng nghĩa bất thường.</p>
          <div class="chips clinical-morphology-chips">${ ["Dạng nang", "Dạng đặc", "Hỗn hợp", "Bóng cản âm"].map((label) => '<button type="button" class="chip" data-chip="' + esc(label) + '">' + esc(label) + "</button>").join("")}</div>
          <label class="field">Mô tả bổ sung
            <input id="morphology" maxlength="100" placeholder="Chi tiết âm vang, vách ngăn...">
          </label>
          <label class="field">Ghi chú lâm sàng của bác sĩ
            <textarea id="notes" rows="2" placeholder="Kết luận hoặc lưu ý theo dõi..."></textarea>
          </label>
          <div id="reviewContentWarning" class="banner warning small" hidden>
            <p id="reviewContentWarningText" role="alert"></p>
            <label id="reviewContentAckLabel"><input type="checkbox" id="reviewContentAck"> Tôi đã kiểm tra nhận định và bối cảnh của ghi chú/O-RADS.</label>
          </div>
          <div class="field small" id="localDictation">
            <button class="btn small" type="button" id="dictationRecord">Đọc chính tả cục bộ</button>
            <p id="dictationStatus" class="small muted" role="status" aria-live="polite">Chỉ bật khi trình duyệt xác nhận vi-VN xử lý trên thiết bị; bản chép cần được kiểm tra trước khi chèn.</p>
            <p id="dictationPreview" class="small" aria-live="polite" hidden></p>
            <div class="actions">
              <button class="btn small" type="button" id="dictationInsert" disabled>Chèn bản xem trước</button>
              <button class="btn small" type="button" id="dictationDiscard" disabled>Bỏ bản chép</button>
            </div>
          </div>
          <div class="clinical-actions">
            ${ button("Không có vùng tổn thương cần phân đoạn", "no-lesion", "small")}
            ${ button("Bỏ mask AI, vẽ mới", "manual", "small")}
          </div>
          <p class="muted small clinical-mask-note">Mask rỗng ghi nhận vùng phân đoạn rỗng, không đưa kết luận bệnh lý.</p>
        </section>
        <section class="viewer-tabpanel" id="researchPanel" role="tabpanel" aria-labelledby="researchTab" tabindex="0" hidden>
          <h3>Phân tích mở rộng &amp; RUO</h3>
          <p class="muted small">Chỉ phục vụ nghiên cứu; không thay thế nhận định lâm sàng.</p>
          <div id="adnexMount"></div>
          <div id="researchCandidateMount"></div>
          <details>
            <summary class="small">Nguồn mô hình</summary>
            <p id="modelHash" class="mono"></p>
          </details>
          <details>
            <summary class="small">Lịch sử chỉnh sửa</summary>
            <ol id="historyList" class="small"></ol>
          </details>
          <h3>Trạng thái rà soát</h3>
          <ol class="timeline"><li>AI đề xuất phân đoạn</li><li>Người rà soát hiệu chỉnh</li>${ workflowStage}</ol>
        </section>
      </aside>
    </div>`;
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
      trackUIEvent(c.study_id, "field_edit", { field: "review_consistency_ack", source: "manual" });
    };
    const oradsQuickPick = $("#oradsQuickPick");
    const oradsQuickPickButtons = [];
    const syncOradsQuickPick = () => {
      for (const quickButton of oradsQuickPickButtons) {
        quickButton.disabled = oradsSelect.disabled;
        const selected = quickButton.dataset.value === oradsSelect.value;
        quickButton.setAttribute("aria-pressed", String(selected));
        quickButton.classList.toggle("primary", selected);
      }
    };
    for (const option of oradsSelect.options) {
      if (!option.value) continue;
      const quickButton = document.createElement("button");
      quickButton.type = "button";
      quickButton.className = "btn small";
      quickButton.dataset.action = "orads-quick-pick";
      quickButton.dataset.value = option.value;
      quickButton.textContent = option.value;
      quickButton.setAttribute("aria-label", option.textContent.trim());
      quickButton.title = option.textContent.trim();
      quickButton.setAttribute("aria-pressed", "false");
      quickButton.addEventListener("click", () => {
        if (oradsSelect.disabled || quickButton.disabled) return;
        oradsSelect.value = option.value;
        oradsSelect.dispatchEvent(new CustomEvent("change", {
          bubbles: true,
          detail: { source: "quick-pick" },
        }));
      });
      oradsQuickPick.append(quickButton);
      oradsQuickPickButtons.push(quickButton);
    }
    syncOradsQuickPick();
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
      draw = false,
      pan = false,
      last = null,
      polygon = [],
      serial = 0,
      timer = null,
      frame = 0;
    let uncertainty = null,
      showUncertainty = false;
    const dictation = bindLocalDictation({
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
    uncertaintyLabel.innerHTML =
      '<span><input id="uncertaintyToggle" type="checkbox" disabled> Xem bản đồ bất định</span><small id="uncertaintyInfo">Entropy chưa hiệu chuẩn lâm sàng; không phải xác suất chẩn đoán. Mặc định tắt.</small>';
    $("#researchPanel").append(uncertaintyLabel);
    const abort = new AbortController(),
      events = { signal: abort.signal };
    const panelTabs = Array.from($$("[data-panel-tab]", root));
    const activatePanelTab = (selectedTab) => {
      for (const tab of panelTabs) {
        const selected = tab === selectedTab;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        tab.classList.toggle("active", selected);
        root.querySelector("#" + tab.getAttribute("aria-controls")).hidden =
          !selected;
      }
    };
    panelTabs.forEach((tab) => {
      tab.addEventListener("click", () => activatePanelTab(tab), events);
      tab.addEventListener(
        "keydown",
        (event) => {
          const index = panelTabs.indexOf(tab);
          const nextIndex =
            event.key === "ArrowRight"
              ? (index + 1) % panelTabs.length
              : event.key === "ArrowLeft"
                ? (index + panelTabs.length - 1) % panelTabs.length
                : event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? panelTabs.length - 1
                    : -1;
          if (nextIndex < 0) return;
          event.preventDefault();
          event.stopPropagation();
          panelTabs[nextIndex].focus();
          activatePanelTab(panelTabs[nextIndex]);
        },
        events,
      );
    });
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
    const source = document.createElement("canvas");
    source.width = source.height = 512;
    const sourceCtx = source.getContext("2d");
    const maskCanvas = document.createElement("canvas");
    maskCanvas.width = maskCanvas.height = 512;
    const maskCtx = maskCanvas.getContext("2d");
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
      comparisonSerial = 0;
    const syncClinicalInputs = () => {
      const blocked = readonly || state.busy || selecting || !image || disposed;
      for (const id of ["notes", "morphology", "iotaMorphology", "oradsScore", "reviewContentAck"])
        if ($("#" + id)) $("#" + id).disabled = blocked;
      $("[data-action=quick-print]").disabled = blocked;
      $("[data-action=save-review]").disabled = blocked || !c.images.every(i => i.seen);
      $("#dictationRecord").disabled = blocked;
      syncOradsQuickPick();
    };
    syncClinicalInputs();
    root.addEventListener("ova:review-lock-changed", syncClinicalInputs, events);
    const canEvaluateAdnex = () =>
      role() === "BS" &&
      !disposed &&
      !state.busy &&
      !readonly &&
      !selecting &&
      !!image &&
      state.editing?.caseId === c.study_id &&
      state.editing.allowed &&
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
      }),
      canEvaluate: canEvaluateCdss,
      signal: abort.signal,
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
          context.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
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
        : `D1 ${format(physical ? m.max_diameter_mm : m.max_diameter_px, physical ? "milimét" : "pixel")}; ` +
          `D2 ${format(physical ? m.ortho_diameter_mm : m.ortho_diameter_px, physical ? "milimét" : "pixel")}; ` +
          `diện tích ${format(physical ? m.total_area_cm2 : m.total_area_px, physical ? "centimét vuông" : "pixel vuông")}.`;
      const calibrationStatus = physical
        ? m.calibration_source === "DICOM"
          ? "Hiệu chuẩn từ DICOM."
          : "Hiệu chuẩn nhập tay."
        : "Chưa hiệu chuẩn; chỉ có số đo theo pixel.";
      summary.textContent =
        `Ảnh siêu âm buồng trứng ${side}. ${maskStatus} ${measurementStatus} ${calibrationStatus} ` +
        "Mask là phân đoạn tham khảo, không phải kết luận bệnh lý.";
    };
    const displayMeasurements = (m) => {
      if (!m) return;
      const physical = m.calibrated === true;
      const format = (value) =>
        Number.isFinite(value) ? value.toFixed(1) : "—";
      $("#d1").textContent =
        format(physical ? m.max_diameter_mm : m.max_diameter_px) +
        (physical ? " mm" : " px");
      $("#d2").textContent =
        format(physical ? m.ortho_diameter_mm : m.ortho_diameter_px) +
        (physical ? " mm" : " px");
      $("#area").textContent =
        format(physical ? m.total_area_cm2 : m.total_area_px) +
        (physical ? " cm²" : " px²");
      $("#measureValues").classList.toggle("pixel", !physical);
      const calBadge = $("#calibrationBadge");
      if (calBadge) {
        calBadge.textContent = physical
          ? m.calibration_source === "DICOM"
            ? "Đã hiệu chuẩn DICOM"
            : "Nhập tay"
          : "";
        calBadge.style.display = physical ? "" : "none";
      }
      updateAccessibleImageSummary(m);
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
        worker.postMessage({ mask: image.mask, box, serial: current });
        if (image.image_id) {
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
            if (e.name !== "AbortError") {
              $("#draftStatus").textContent =
                "Chưa cập nhật được số đo máy chủ.";
              if (current === serial) {
                let hasPx = false;
                if (image.mask) {
                  for (let idx = 0; idx < image.mask.length; idx++) {
                    if (image.mask[idx]) {
                      hasPx = true;
                      break;
                    }
                  }
                }
                const fallbackMeas = {
                  max_diameter_px: hasPx && image.workerMeas ? image.workerMeas.d1 : 0,
                  ortho_diameter_px: hasPx && image.workerMeas ? image.workerMeas.d2 : 0,
                  total_area_px: hasPx && image.workerMeas ? image.workerMeas.area : 0,
                  // UAT-07: API failed — physical mm/cm² must be null (not stale old values)
                  max_diameter_mm: null,
                  ortho_diameter_mm: null,
                  total_area_cm2: null,
                  calibrated: false,
                  calibration_source: image.measurements?.calibration_source,
                };
                image.measurements = fallbackMeas;
                displayMeasurements(fallbackMeas);
                schedule();
              }
            }
          }
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
        };
        image.measurements = emptyMeas;
        displayMeasurements(emptyMeas);
      }
      image.seen = true;
      $("[data-action=sign]").disabled =
        readonly || !workflowEnabled || c.images.length !== 2 || !c.images.every((i) => i.seen);
      $("[data-action=save-review]").disabled =
        readonly || !c.images.every((i) => i.seen);

      const count = components(image.mask).length;
      const warnings = [
        m.touches ? "Mask chạm biên ảnh" : "",
        count > 1 ? `${count} thành phần mask – kiểm tra từng vùng` : "",
        image.iqa?.is_acceptable === false ? "Chất lượng ảnh thấp" : "",
      ].filter(Boolean);
      $("#viewerWarnings").innerHTML = warnings
        .map((v) => `<div class="banner warning small">${esc(v)}</div>`)
        .join("");
    };
    const history = () => {
      $("#historyList").innerHTML =
        (image.history || [])
          .map((_, i) => `<li>Thao tác ${i + 1}</li>`)
          .join("") || "<li>Chưa chỉnh sửa</li>";
    };
    const beforeEdit = () => {
      image.history ??= [];
      image.redo ??= [];
      image.history.push(encode(image.mask));
      if (image.history.length > 50) image.history.shift();
      image.redo = [];
      tracker.startStroke(image.image_id);
    };
    const changed = ({
      refreshMeasurements = true,
      persistDraft = true,
      toolName = tool,
      changedPixels = 0,
      candidateParameters = null,
      candidateProvenance = null,
    } = {}) => {
      tracker.commitEdit(image.image_id, {
        tool: toolName,
        changed_pixels: changedPixels,
        candidate_parameters: candidateParameters,
        candidate_provenance: candidateProvenance,
      });
      root.dispatchEvent(new CustomEvent("ova:mask-changed"));
      if (persistDraft) saveDraft();
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
    const select = async (side) => {
      if (draw || pan || state.busy) return;
      const item = c.images.find((i) => i.laterality === side);
      if (!item) return toast("Ca chưa có ảnh bên này.", true);
      if (side !== state.side) dictation.cancel();
      const version = ++serial;
      ++comparisonSerial;
      trackUIEvent(c.study_id, "side_switch", { side });
      selecting = true;
      syncClinicalInputs();
      researchCandidateUI.resetForSide();
      adnexUI.resetForSide(side);
      adnexUI.setEditable(false);
      cdssUI.resetForSide();
      cdssUI.setEditable(false);
      polygon = [];
      let bitmap;
      try {
        if (!item.source) {
          const data = await request(
            "/api/images/" + encodeURIComponent(item.image_id) + "/viewer-source",
            { signal: abort.signal },
          );
          if (version !== serial || disposed) return;
          item.source = data.original_image_base64;
          item.sourceIsModel = true;
        }
        bitmap = await createImageBitmap(
          await imageSourceBlob(item.source),
        );
      } catch (error) {
        if (version === serial && !disposed) {
          selecting = false;
          syncClinicalInputs();
          adnexUI.resetForSide(state.side);
          adnexUI.setEditable(canEvaluateAdnex());
          cdssUI.resetForSide();
          cdssUI.setEditable(canEvaluateCdss());
        }
        if (!image) throw error;
        toast(error.message, true);
        return;
      }
      if (version !== serial || disposed) {
        bitmap.close();
        return;
      }
      image = item;
      image.seen = true;
      state.side = side;
      researchCandidateUI.resetForSide();
      adnexUI.setEditable(canEvaluateAdnex());
      cdssUI.setEditable(canEvaluateCdss());
      tracker.track(image.image_id, "PREDICTION_VIEWED");
      sourceCtx.clearRect(0, 0, 512, 512);
      const dims = image.dimensions || [
        image.width || bitmap.width,
        image.height || bitmap.height,
      ];
      box = letterbox(dims[0], dims[1]);
      if (image.sourceIsModel) sourceCtx.drawImage(bitmap, 0, 0, 512, 512);
      else
        sourceCtx.drawImage(bitmap, box.left, box.top, box.width, box.height);
      bitmap.close();
      uncertainty?.close();
      uncertainty = null;
      showUncertainty = false;
      $("#uncertaintyToggle").checked = false;
      $("#uncertaintyToggle").disabled = true;
      $("#uncertaintyInfo").textContent =
        "Chưa có bản đồ entropy; lớp phủ mặc định tắt và không ảnh hưởng mask.";
      if (image.prediction?.uncertainty_map_base64) {
        const map = await loadUncertaintyMap(
          image.prediction.uncertainty_map_base64,
          window,
        );
        if (version !== serial || disposed) {
          map?.close();
          return;
        }
        if (map) {
          uncertainty = map;
          $("#uncertaintyToggle").disabled = false;
          $("#uncertaintyInfo").textContent =
            "Entropy chưa hiệu chuẩn lâm sàng; chỉ tham khảo RUO, không phải xác suất chẩn đoán.";
        } else
          $("#uncertaintyInfo").textContent =
            "Không tải được bản đồ 512×512; mask gốc không thay đổi.";
      }
      image.mask ??= new Uint8Array(262144);
      image.aiMask ??= image.mask.slice();
      $("#sideLabel").textContent =
        `Buồng trứng ${side === "L" ? "trái" : "phải"} · giữ Space xem ảnh gốc`;
      $("#modelHash").textContent =
        image.prediction?.provenance?.checkpoint_sha256 ||
        image.prediction?.provenance?.model_checksum ||
        "Bản ghi chưa cung cấp SHA-256.";
      $("#notes").value = image.notes || "";
      $("#morphology").value = image.morphologyDesc || "";
      if ($("#iotaMorphology")) $("#iotaMorphology").value = image.morphology || "";
      if ($("#oradsScore")) $("#oradsScore").value = image.orads || "";
      selecting = false;
      syncClinicalInputs();
      adnexUI.setEditable(canEvaluateAdnex());
      cdssUI.setEditable(canEvaluateCdss());
      for (const s of ["L", "R"])
        $(`[data-action=side-${s}]`).classList.toggle("primary", s === side);
      $("#notes").disabled = $("#morphology").disabled = readonly;
      if ($("#iotaMorphology")) $("#iotaMorphology").disabled = readonly;
      if ($("#oradsScore")) $("#oradsScore").disabled = readonly;
      syncOradsQuickPick();
      $("[data-action=sign]").disabled =
        readonly || !workflowEnabled || !c.images.every((i) => i.seen) || c.images.length !== 2;
      $("[data-action=save-review]").disabled =
        readonly || !c.images.every((i) => i.seen);
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
        canvas.focus();
        canvas.setPointerCapture(e.pointerId);
        if (e.button === 1 || tool === "pan") {
          pan = true;
          last = { x: e.clientX, y: e.clientY };
          e.preventDefault();
          return;
        }
        if (readonly || selecting || state.busy || e.button !== 0 || peek)
          return;
        const p = point(e);
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
        }
      },
      events,
    );
    const end = () => {
      if (draw) {
        draw = false;
        changed();
      }
      pan = false;
      document.body.classList.remove("drawing");
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
        readonly ||
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
      trackUIEvent(c.study_id, "tool_select", { tool: action });
      if (["brush", "erase", "polygon", "pan"].includes(action)) {
        tool = action;
        $$("[data-tool]").forEach(
          (b) => (
            b.classList.toggle("active", b.dataset.tool === tool),
            b.setAttribute("aria-pressed", String(b.dataset.tool === tool))
          ),
        );
        canvas.style.cursor = tool === "pan" ? "grab" : "crosshair";
        return;
      }
      if (action === "fit") return fit();
      if (action === "fullscreen") {
        if (document.fullscreenElement) document.exitFullscreen();
        else root.requestFullscreen();
        return;
      }
      if (readonly) return;
      if (action === "undo") {
        const previous = image.history.pop();
        if (previous) {
          image.redo.push(encode(image.mask));
          image.mask = decode(previous);
          tracker.track(image.image_id, "UNDO");
        }
      } else if (action === "redo") {
        const next = image.redo.pop();
        if (next) {
          image.history.push(encode(image.mask));
          image.mask = decode(next);
          tracker.track(image.image_id, "REDO");
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
        tracker.track(
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
      b.disabled =
        readonly && !["fit", "pan", "fullscreen"].includes(b.dataset.tool);
      b.onclick = () => act(b.dataset.tool);
    });
    $$("[data-action^=side-]").forEach(
      (b) =>
        (b.onclick = () =>
          select(b.dataset.action.slice(-1)).catch((e) =>
            toast(e.message, true),
          )),
    );
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
        if (!other.source) {
          const data = await request(
            "/api/images/" + other.image_id + "/viewer-source",
            { signal: abort.signal },
          );
          other.source = data.original_image_base64;
          other.sourceIsModel = true;
        }
        const bitmap = await createImageBitmap(
          await imageSourceBlob(other.source),
        );
        if (
          disposed ||
          comparisonId !== comparisonSerial ||
          selected !== image
        ) {
          bitmap.close();
          return;
        }
        const g = compareCanvas.getContext("2d");
        g.clearRect(0, 0, 512, 512);
        const b = letterbox(
          other.width || other.dimensions?.[0] || bitmap.width,
          other.height || other.dimensions?.[1] || bitmap.height,
        );
        g.drawImage(
          bitmap,
          other.sourceIsModel ? 0 : b.left,
          other.sourceIsModel ? 0 : b.top,
          other.sourceIsModel ? 512 : b.width,
          other.sourceIsModel ? 512 : b.height,
        );
        bitmap.close();
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
    $("[data-action=image-reset]").onclick = () => {
      brightness = contrast = 100;
      $("#brightness").value = $("#contrast").value = 100;
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
        if (state.busy || readonly || selecting || !image || !state.editing?.allowed) {
          e.target.value = (id === "morphology" ? image?.morphologyDesc : image?.[id]) || "";
          return;
        }
        if (id === "morphology") image.morphologyDesc = e.target.value;
        else image[id] = e.target.value;
        changed({ refreshMeasurements: id !== "notes" });
      };
    if ($("#iotaMorphology")) {
      const handleIota = (e) => {
        if (state.busy || readonly || selecting || !image || !state.editing?.allowed) {
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
        if (state.busy || readonly || selecting || !image || !state.editing?.allowed) {
          if (image) e.target.value = image.orads || "";
          syncOradsQuickPick();
          return;
        }
        if (image) image.orads = e.target.value;
        state.dirty = true;
        trackUIEvent(c.study_id, "field_edit", { field: "oradsScore", value: $("#oradsScore").value, source: "manual" });
        changed({
          refreshMeasurements: false,
          persistDraft: e.detail?.source !== "quick-pick",
        });
        syncOradsQuickPick();
      };
      $("#oradsScore").onchange = handleOrads;
      $("#oradsScore").oninput = handleOrads;
    }
    $$("[data-chip]").forEach((b) => {
      b.disabled = readonly;
      b.onclick = () => {
        if (state.busy || readonly) return;
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
      const savePromise = saveResearchReview();
      root.dispatchEvent(new CustomEvent("ova:review-lock-changed"));
      try {
        await savePromise;
      } finally {
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
      "Xuất dữ liệu nghiên cứu đang khóa đến khi có hồ sơ xác minh phê duyệt, consent và khử định danh.";
    researchExportButton.title = researchExportDisabledMessage;
    researchExportButton.setAttribute("aria-label", "Xuất dữ liệu nghiên cứu — đang khóa");
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
      if (state.busy || readonly || selecting || !image || state.case !== c) return;
      const unseen = c.images.find(img => !img.seen);
      if (unseen) {
        toast("Xem đủ hai bên trước khi lưu rồi in. Dùng Xem phiếu để xem bản nháp RUO.", true);
        $(`[data-action=side-${unseen.laterality}]`)?.focus();
        return;
      }
      const printButton = $("[data-action=quick-print]");
      printButton.disabled = true;
      try {
        const outcome = await saveResearchReview();
        if (outcome?.status !== "saved" || !outcome.clean || state.case !== c ||
            state.dirty || disposed || !root.isConnected || outcome.studyId !== c.study_id) return;
        trackUIEvent(c.study_id, "print_click");
        location.hash = "#report/" + encodeURIComponent(c.study_id) + "?print=1&revision=" + outcome.revision;
      } finally {
        if (!disposed && root.isConnected) printButton.disabled = readonly;
      }
    };
    $("[data-action=quick-print]").disabled = readonly;
    $("[data-action=quick-print]").onclick = triggerQuickPrint;
    $("[data-action=report]").onclick = () => {
      location.hash = "#report/" + encodeURIComponent(c.study_id);
    };
    $("[data-action=calibrate]").onclick = () => {
      if (readonly || state.busy || !state.editing?.allowed || !state.editing.leaseToken)
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
          if (readonly || !state.editing?.allowed || !state.editing.leaseToken) {
            toast("Quyền chỉnh sửa ca đã hết hạn. Hãy tải lại ca để tiếp tục.", true);
            return;
          }
          const data = Object.fromEntries(new FormData(e.target)),
            spacing = Number(data.mm) / Number(data.pixels);
          if (!Number.isFinite(spacing) || spacing <= 0) return;
          try {
            {
              await request(
                "/api/images/" +
                  image.image_id +
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
              image.pixel_spacing_mm = spacing;
              if (image.measurements) {
                image.measurements.calibrated = true;
                image.measurements.calibration_source = "Nhập tay";
              }
              state.dirty = true;
              measure();
            }
            d.close();
          } catch (err) {
            toast(err.message, true);
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
        // Ctrl+P explicitly opens a labelled RUO draft, without saving or marking images seen.
        if (!state.busy && !selecting) location.hash = reportHash;
        return;
      }
      if (state.busy || selecting) return;
      if (
        (e.ctrlKey || e.metaKey || e.altKey) &&
        String(e.key).toLowerCase() === "p"
      )
        return;
      if (e.target?.closest?.("input,textarea,select,[contenteditable]")) return;
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
        if (e.code === "Space") {
          peek = false;
          syncOverlayVisibility();
          schedule();
        }
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
    const observer = new ResizeObserver(fit);
    observer.observe($("#pane"));
    window.addEventListener(
      "ova:lease-lost",
      () => {
        readonly = true;
        dictation.cancel();
        $("#dictationRecord").disabled = true;
        $("#dictationInsert").disabled = true;
        $("#dictationDiscard").disabled = true;
        adnexUI.disable();
        cdssUI.setEditable(false);
        researchCandidateUI.resetForSide();
        end();
        state.editing = { caseId: c.study_id, allowed: false };
        $$("[data-tool]").forEach((b) => {
          if (!["fit", "pan", "fullscreen"].includes(b.dataset.tool))
            b.disabled = true;
        });
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
        syncOradsQuickPick();
        $$("[data-chip]").forEach((b) => (b.disabled = true));
      },
      events,
    );
    const onVisibilityChange = () => {
      if (!image) return;
      if (document.hidden) tracker.recordPause(image.image_id);
      else tracker.recordResume(image.image_id);
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    active = { select, act, render: schedule };
    const release = () => {
      disposed = true;
      dictation.dispose();
      adnexUI.destroy();
      cdssUI.destroy();
      researchCandidateUI.destroy();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (state.editing?.caseId === c.study_id) state.editing = null;
      lease?.release();
      abort.abort();
      observer.disconnect();
      worker.terminate();
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
            participant_role: "clinician",
            data_origin: "live",
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
    trackUIEvent(c.study_id, "case_open");
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
