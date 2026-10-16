import { acquireLease } from "./leases.js";
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
let active = null;
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
    state.editing = { caseId: c.study_id, allowed: !readonly };
    root.innerHTML = `<div class="viewer-head"><div class="actions"><a class="icon-btn" href="#cases" aria-label="Về danh sách">${icon("list")}</a><strong>${esc(c.study_code || c.study_id)}</strong><span class="muted small">${esc(c.patient_id)}</span>${badge(c.status)}</div><div class="actions">${button("Trái", "side-L", "small primary")}${button("Phải", "side-R", "small")}${button("Lưu rà soát", "save-review", "small")}${button("Tải kết quả", "export-research", "small")}${button("Ký sơ bộ", "sign", "primary")}${correction ? button("Lưu phiên bản sửa", "save-correction", "primary") : ""}${button("Phiếu", "report", "small")}${button("Rà soát", "panel-toggle", "small")}</div></div><div class="viewer-grid"><aside class="toolrail" aria-label="Công cụ chỉnh mask">${[
      ["brush", "brush", "Cọ vẽ (B)"],
      ["erase", "erase", "Tẩy (E)"],
      ["polygon", "polygon", "Đa giác (L)"],
      ["pan", "hand", "Di chuyển (H)"],
      ["fill", "plus", "Lấp lỗ"],
      ["smooth", "settings", "Làm trơn (S)"],
      ["small", "grid", "Xóa mảnh nhỏ"],
      ["undo", "undo", "Hoàn tác"],
      ["redo", "history", "Làm lại"],
      ["reset", "history", "Về mask AI"],
      ["clear", "close", "Xóa toàn bộ mask"],
      ["fit", "fit", "Vừa khung"],
      ["fullscreen", "fit", "Toàn màn hình"],
    ]
      .map(
        ([a, i, label]) =>
          `<button type="button" class="icon-btn" data-tool="${a}" title="${label}" aria-label="${label}">${icon(i)}</button>`,
      )
      .join(
        "",
      )}</aside><section class="viewer-center"><div class="viewer-controls">${["Gốc", "Mask", "Lớp phủ"].map((v, i) => button(v, "layer-" + i, "small")).join("")}${button("Đường viền", "contour", "small")}${button("Đối chiếu gốc", "compare", "small")}${button("Hai bên", "bilateral", "small")}${button("Mask AI", "ai-compare", "small")}<label class="range-row">Cọ <input type="range" id="brushSize" min="2" max="64" value="16" aria-label="Cỡ cọ"><output id="brushOutput">16</output></label><label class="range-row">Độ mờ<input id="opacity" type="range" min="0" max="100" value="35"></label></div><div class="viewport-wrap"><div class="canvas-pane" id="pane"><span class="canvas-label" id="sideLabel">Buồng trứng trái · giữ Space xem ảnh gốc</span><div id="brushCursorV2" class="brush-cursor" hidden></div><canvas id="viewport" tabindex="0" aria-label="Khung ảnh phân đoạn, phím B vẽ, E tẩy, H di chuyển"></canvas></div><div class="canvas-pane" id="secondPane" hidden><span class="canvas-label">Đối chiếu ảnh gốc</span><canvas id="secondViewport" aria-label="Ảnh gốc đối chiếu"></canvas></div></div><div class="measure-strip"><div class="measure-values pixel" id="measureValues"><div><small>d₁</small><strong id="d1">—</strong></div><div><small>d₂</small><strong id="d2">—</strong></div><div><small>Diện tích</small><strong id="area">—</strong></div></div><div><span class="badge" id="calibrationBadge">Chưa hiệu chuẩn – chỉ có px</span>${button("Hiệu chuẩn thước", "calibrate", "small")}</div></div><div class="viewer-controls"><label class="range-row">Sáng<input type="range" id="brightness" min="50" max="180" value="100"></label><label class="range-row">Tương phản<input type="range" id="contrast" min="50" max="180" value="100"></label>${button("Mặc định", "image-reset", "small")}<span class="muted small" id="draftStatus">Bản nháp trên thiết bị</span></div></section><aside class="viewer-panel"><h3>Kết quả phân đoạn</h3><p id="modelName">Đang đọc mô hình…</p><details><summary class="small">Nguồn mô hình</summary><p id="modelHash" class="mono"></p></details><h3>Trạng thái rà soát</h3><ol class="timeline"><li>AI đề xuất</li><li>Người rà soát hiệu chỉnh</li><li>Ký sơ bộ hai bên</li></ol>${lease ? `<div class="banner info small">${esc(lease.label)}</div>` : ""}${c.reason ? `<div class="banner warning small">Yêu cầu sửa: ${esc(c.reason)}</div>` : ""}${state.draftConflict ? `<div class="banner warning small">Bản nháp dựa trên phiên bản cũ. Đang hiển thị bản máy chủ.${button("Tải bản nháp cũ", "download-conflict", "small")}${button("Giữ bản máy chủ", "keep-server", "small")}</div>` : ""}<div id="viewerWarnings"></div><h3>Mô tả hình thái</h3><div class="chips">${["Dạng nang", "Dạng đặc", "Hỗn hợp", "Bờ chưa rõ"].map((v) => `<button class="chip" data-chip="${v}">${v}</button>`).join("")}</div><label class="field">Mô tả bổ sung<input id="morphology" maxlength="100"></label><label class="field">Ghi chú rà soát<textarea id="notes" rows="3"></textarea></label>${button("Không có vùng tổn thương cần phân đoạn", "no-lesion", "small")}${button("Bỏ mask AI, vẽ mới", "manual", "small")}<p class="muted small">Mask rỗng ghi nhận vùng phân đoạn rỗng, không đưa kết luận bệnh lý.</p><details><summary class="small">Lịch sử chỉnh sửa</summary><ol id="historyList" class="small"></ol></details></aside></div>`;
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
    const presetLabel = document.createElement("label");
    presetLabel.className = "range-row";
    presetLabel.innerHTML =
      'Hiển thị <select id="displayPreset" aria-label="Thiết lập sáng và tương phản"><option value="normal">Mặc định</option><option value="dim">Ít chói</option><option value="contrast">Tăng tương phản</option></select>';
    $(".viewer-center > .viewer-controls:last-child").prepend(presetLabel);
    const uncertaintyLabel = document.createElement("label");
    uncertaintyLabel.className = "field small";
    uncertaintyLabel.innerHTML =
      '<span><input id="uncertaintyToggle" type="checkbox" disabled> Xem bản đồ bất định</span><small id="uncertaintyInfo">Máy chủ chưa cung cấp; mặc định tắt.</small>';
    $(".viewer-panel").append(uncertaintyLabel);
    const abort = new AbortController(),
      events = { signal: abort.signal };
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
      selecting = false,
      comparisonSerial = 0;
    const schedule = () => {
      if (!frame)
        frame = requestAnimationFrame(() => {
          frame = 0;
          render();
        });
    };
    const render = () => {
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
      $("#calibrationBadge").textContent = physical
        ? m.calibration_source === "DICOM"
          ? "Đã hiệu chuẩn DICOM"
          : "Nhập tay"
        : "Chưa hiệu chuẩn – chỉ có px";
    };
    const measure = () => {
      clearTimeout(timer);
      const current = ++serial;
      timer = setTimeout(async () => {
        worker.postMessage({ mask: image.mask, box, serial: current });
        if (!state.demo && image.image_id) {
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
            }
          } catch (e) {
            if (e.name !== "AbortError")
              $("#draftStatus").textContent =
                "Chưa cập nhật được số đo máy chủ.";
          }
        }
      }, 180);
    };
    worker.onmessage = ({ data: m }) => {
      if (m.serial !== serial) return;
      image.seen = true;
      $("[data-action=sign]").disabled =
        readonly || c.images.length !== 2 || !c.images.every((i) => i.seen);
      $("[data-action=save-review]").disabled =
        readonly || !c.images.every((i) => i.seen);
      if (state.demo) {
        image.measurements = {
          calibrated: false,
          max_diameter_px: m.d1,
          ortho_diameter_px: m.d2,
          total_area_px: m.area,
        };
        displayMeasurements(image.measurements);
      }
      const count = components(image.mask).length;
      const warnings = [
        !image.measurements?.calibrated ? "Chưa hiệu chuẩn – chỉ có px" : "",
        m.touches ? "Mask chạm biên ảnh" : "",
        count > 1 ? `${count} thành phần mask – kiểm tra từng vùng` : "",
        image.iqa?.is_acceptable === false ? "Chất lượng ảnh thấp" : "",
        image.anonymization?.status === "DEMO"
          ? "Ảnh sơ đồ demo"
          : "Ẩn danh chưa được máy chủ xác minh",
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
    };
    const changed = () => {
      saveDraft();
      $("#draftStatus").textContent = state.online
        ? "Bản nháp đã lưu trên thiết bị"
        : "Chưa đồng bộ – bản nháp trên thiết bị";
      history();
      measure();
    };
    const select = async (side) => {
      if (draw || pan || state.busy) return;
      const item = c.images.find((i) => i.laterality === side);
      if (!item) return toast("Ca chưa có ảnh bên này.", true);
      const version = ++serial;
      ++comparisonSerial;
      selecting = true;
      polygon = [];
      if (!item.source) {
        const data = await request(
          "/api/images/" + encodeURIComponent(item.image_id) + "/viewer-source",
          { signal: abort.signal },
        );
        if (version !== serial || disposed) return;
        item.source = data.original_image_base64;
        item.sourceIsModel = true;
      }
      const bitmap = await createImageBitmap(
        await (await fetch(item.source)).blob(),
      );
      if (version !== serial || disposed) {
        bitmap.close();
        return;
      }
      image = item;
      state.side = side;
      selecting = false;
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
        "Máy chủ chưa cung cấp; mặc định tắt.";
      if (image.prediction?.uncertainty_map_base64) {
        try {
          const map = await createImageBitmap(
            await (await fetch(image.prediction.uncertainty_map_base64)).blob(),
          );
          if (
            version !== serial ||
            disposed ||
            map.width !== 512 ||
            map.height !== 512
          )
            map.close();
          else {
            uncertainty = map;
            $("#uncertaintyToggle").disabled = false;
            $("#uncertaintyInfo").textContent =
              "Bản đồ từ máy chủ, không phải xác suất chẩn đoán.";
          }
        } catch {
          if (version === serial && !disposed)
            $("#uncertaintyInfo").textContent =
              "Chưa tải được bản đồ bất định.";
        }
        if (version !== serial || disposed) return;
      }
      image.mask ??= new Uint8Array(262144);
      image.aiMask ??= image.mask.slice();
      $("#sideLabel").textContent =
        `Buồng trứng ${side === "L" ? "trái" : "phải"} · giữ Space xem ảnh gốc`;
      $("#modelName").textContent =
        image.prediction?.provenance?.model_name ||
        image.prediction?.model_version ||
        "Vẽ tay – chưa có dự đoán";
      $("#modelHash").textContent =
        image.prediction?.provenance?.model_checksum ||
        "Bản ghi chưa cung cấp SHA-256.";
      $("#notes").value = image.notes || "";
      $("#morphology").value = image.morphology || "";
      for (const s of ["L", "R"])
        $(`[data-action=side-${s}]`).classList.toggle("primary", s === side);
      $("#notes").disabled = $("#morphology").disabled = readonly;
      $("[data-action=sign]").disabled =
        readonly || !c.images.every((i) => i.seen) || c.images.length !== 2;
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
    canvas.addEventListener(
      "dblclick",
      () => {
        if (
          tool === "polygon" &&
          polygon.length >= 3 &&
          !readonly &&
          !state.busy
        ) {
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
        } else fit();
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
        }
      } else if (action === "redo") {
        const next = image.redo.pop();
        if (next) {
          image.history.push(encode(image.mask));
          image.mask = decode(next);
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
          await (await fetch(other.source)).blob(),
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
        if (state.busy) {
          e.target.value = image[id] || "";
          return;
        }
        image[id] = e.target.value;
        changed();
      };
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
    $("[data-action=save-review]").onclick = () => saveResearchReview();
    $("[data-action=export-research]").onclick = async () => {
      const revIds = c.images.map((i) => i.review?.review_id).filter(Boolean);
      if (state.dirty || revIds.length !== c.images.length) {
        return toast(
          "Cần lưu rà soát đầy đủ và không có bản nháp chưa lưu trước khi tải ZIP.",
          true,
        );
      }
      try {
        const token = sessionStorage.getItem("ova.token");
        const headers = { "Content-Type": "application/json" };
        if (token) headers.Authorization = "Bearer " + token;
        toast("Đang tải kết quả nghiên cứu...");
        const resp = await fetch(
          `/api/cases/${encodeURIComponent(c.study_id)}/research-export`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              review_ids: revIds,
              expected_revision: c.review_revision ?? 0,
            }),
          },
        );
        if (!resp.ok) {
          const err = await resp
            .json()
            .catch(() => ({ detail: "Lỗi tải kết quả." }));
          return toast(err.detail || "Không thể tải kết quả nghiên cứu.", true);
        }
        const blob = await resp.blob();
        if (blob.size === 0) return toast("File rỗng.", true);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `study_${c.study_code || c.study_id}_research_export.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast("Đã tải tệp ZIP kết quả nghiên cứu.");
      } catch (err) {
        toast(err.message || "Lỗi tải tệp ZIP.", true);
      }
    };
    $("[data-action=panel-toggle]").onclick = () =>
      document.body.classList.toggle("panel-open");
    $("[data-action=report]").onclick = () => {
      location.hash = "#report/" + c.study_id;
    };
    $("[data-action=calibrate]").onclick = () => {
      if (readonly || state.busy)
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
          const data = Object.fromEntries(new FormData(e.target)),
            spacing = Number(data.mm) / Number(data.pixels);
          if (!Number.isFinite(spacing) || spacing <= 0) return;
          try {
            if (state.demo) {
              toast("Ảnh sơ đồ không có thước vật lý. Giữ đơn vị pixel.");
            } else {
              await request(
                "/api/images/" +
                  image.image_id +
                  "/calibrate?pixel_spacing_mm=" +
                  encodeURIComponent(spacing),
                { method: "POST" },
              );
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
      if (state.busy || selecting) return;
      if (
        document.querySelector("dialog[open]") ||
        e.target.closest("input,textarea,select,[contenteditable]")
      )
        return;
      if (e.code === "Space") {
        e.preventDefault();
        peek = true;
        schedule();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        if (!$("[data-action=sign]").disabled) openSignoff();
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
      else if (["1", "2", "3"].includes(k)) {
        layer = Number(k) - 1;
        schedule();
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
      } else if (k === "n" || k === "p") {
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
          schedule();
        }
      },
      events,
    );
    window.addEventListener(
      "blur",
      () => {
        peek = false;
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
        $$("[data-tool]").forEach((b) => {
          if (!["fit", "pan", "fullscreen"].includes(b.dataset.tool))
            b.disabled = true;
        });
        for (const action of ["sign", "save-review", "save-correction"]) {
          const b = $("[data-action=" + action + "]");
          if (b) b.disabled = true;
        }
        $("#notes").disabled = $("#morphology").disabled = true;
        $$("[data-chip]").forEach((b) => (b.disabled = true));
      },
      events,
    );
    active = { select, act, render: schedule };
    const release = () => {
      disposed = true;
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
