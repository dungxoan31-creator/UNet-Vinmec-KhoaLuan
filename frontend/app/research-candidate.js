import { request } from "./api.js";
import { decode } from "./coordinates.js";

const MASK_LENGTH = 512 * 512;
const AREA_OPTIONS = [0, 50, 100, 250, 500, 1000];
const KERNEL_OPTIONS = [0, 3, 5, 7, 11];
const SMOOTHING_OPTIONS = [3, 5, 7, 11];
const BASELINE_COLOR = [98, 233, 224];
const CANDIDATE_COLOR = [255, 193, 89];
const BACKGROUND_COLOR = [20, 26, 36];
const overlayCanvases = new WeakMap();

function selectMarkup(name, label, options) {
  return `<label class="field" for="researchCandidate-${name}">${label}
    <select id="researchCandidate-${name}" name="${name}" autocomplete="off" required>
      <option value="">-- Chưa chọn --</option>${options
        .map(([value, text]) => `<option value="${value}">${text}</option>`)
        .join("")}
    </select>
  </label>`;
}

export function researchCandidateMarkup() {
  return `<details id="researchCandidatePanel" class="research-candidate">
    <summary>Thử nghiệm xử lý mask · RUO</summary>
    <div class="research-candidate-content">
      <p class="research-candidate-note">Candidate chỉ phục vụ nghiên cứu, không phải kết quả lâm sàng. Chọn rõ từng phép biến đổi; mask AI gốc không bị thay đổi cho đến khi bác sĩ chủ động áp dụng.</p>
      <form id="researchCandidateForm">
        <fieldset id="researchCandidateFields">
          <legend>Tham số candidate — không có giá trị mặc định</legend>
          <div class="research-candidate-grid">
            ${selectMarkup("min_component_area", "Diện tích thành phần tối thiểu (px²)", AREA_OPTIONS.map((value) => [value, value === 0 ? "Không lọc" : `${value} px²`]))}
            ${selectMarkup("closing_kernel_size", "Đóng hình thái", KERNEL_OPTIONS.map((value) => [value, value === 0 ? "Không áp dụng" : `${value} × ${value}`]))}
            ${selectMarkup("fill_holes", "Lấp lỗ khép kín", [["true", "Áp dụng"], ["false", "Không áp dụng"]])}
            ${selectMarkup("smoothing_kernel_size", "Làm trơn biên", [["none", "Không áp dụng"], ...SMOOTHING_OPTIONS.map((value) => [value, `${value} × ${value}`])])}
          </div>
          <button id="researchCandidatePreview" class="btn small" type="submit" disabled>Xem candidate</button>
        </fieldset>
      </form>
      <p id="researchCandidateStatus" class="research-candidate-status" role="status" aria-live="polite" aria-busy="false">Chưa tạo candidate.</p>
      <div class="research-candidate-previews" aria-describedby="researchCandidateStatus">
        <figure><figcaption>Mask AI gốc</figcaption><canvas id="researchCandidateBaseline" width="512" height="512" aria-label="Xem trước mask AI gốc"></canvas></figure>
        <figure><figcaption>Candidate · chỉ xem</figcaption><canvas id="researchCandidateCandidate" width="512" height="512" aria-label="Xem trước candidate RUO"></canvas></figure>
      </div>
      <button id="researchCandidateApply" class="btn small primary" type="button" disabled>Áp dụng vào mask chỉnh sửa</button>
    </div>
  </details>`;
}

function isMask(mask) {
  if (!(mask instanceof Uint8Array) || mask.length !== MASK_LENGTH) return false;
  for (const value of mask) if (value !== 0 && value !== 1) return false;
  return true;
}

function cloneMask(mask) {
  return isMask(mask) ? new Uint8Array(mask) : null;
}

function sameMask(left, right) {
  if (!isMask(left) || !isMask(right)) return false;
  for (let index = 0; index < MASK_LENGTH; index++)
    if (left[index] !== right[index]) return false;
  return true;
}

function sameContext(left, right) {
  return Boolean(left && right) &&
    left.studyId === right.studyId &&
    left.imageId === right.imageId &&
    left.predictionId === right.predictionId &&
    left.side === right.side;
}

function hasSource(context) {
  return Boolean(
    context &&
      typeof context.studyId === "string" && context.studyId.trim() &&
      typeof context.imageId === "string" && context.imageId.trim() &&
      typeof context.predictionId === "string" && context.predictionId.trim() &&
      ["L", "R"].includes(context.side) &&
      isMask(context.aiMask) &&
      isMask(context.currentMask),
  );
}

function readParameters(elements) {
  const areaText = elements.min_component_area?.value;
  const closingText = elements.closing_kernel_size?.value;
  const fillText = elements.fill_holes?.value;
  const smoothingText = elements.smoothing_kernel_size?.value;
  if ([areaText, closingText, fillText, smoothingText].some((value) => value === "" || value == null))
    return null;

  const minComponentArea = Number(areaText);
  const closingKernelSize = Number(closingText);
  const fillHoles = fillText === "true" ? true : fillText === "false" ? false : null;
  const smoothingKernelSize = smoothingText === "none" ? null : Number(smoothingText);
  if (
    !Number.isInteger(minComponentArea) || !AREA_OPTIONS.includes(minComponentArea) ||
    !Number.isInteger(closingKernelSize) || !KERNEL_OPTIONS.includes(closingKernelSize) ||
    fillHoles === null ||
    (smoothingKernelSize !== null &&
      (!Number.isInteger(smoothingKernelSize) || !SMOOTHING_OPTIONS.includes(smoothingKernelSize)))
  ) return null;

  return {
    min_component_area: minComponentArea,
    closing_kernel_size: closingKernelSize,
    fill_holes: fillHoles,
    smoothing_kernel_size: smoothingKernelSize,
  };
}

function paintMask(canvas, mask, color, sourceCanvas = null) {
  const context = canvas?.getContext?.("2d");
  if (!context) return;
  if (sourceCanvas && mask && typeof context.drawImage === "function") {
    context.clearRect(0, 0, 512, 512);
    context.drawImage(sourceCanvas, 0, 0, 512, 512);
  }
  const frame = context.createImageData(512, 512);
  for (let pixel = 0; pixel < MASK_LENGTH; pixel++) {
    const offset = pixel * 4;
    const foreground = Boolean(mask?.[pixel]);
    const tint = foreground ? color : BACKGROUND_COLOR;
    frame.data[offset] = tint[0];
    frame.data[offset + 1] = tint[1];
    frame.data[offset + 2] = tint[2];
    frame.data[offset + 3] = foreground ? 150 : sourceCanvas ? 0 : 255;
  }
  if (sourceCanvas && typeof document !== "undefined") {
    let overlay = overlayCanvases.get(canvas);
    if (!overlay) {
      overlay = document.createElement("canvas");
      overlay.width = overlay.height = 512;
      overlayCanvases.set(canvas, overlay);
    }
    overlay.getContext("2d").putImageData(frame, 0, 0);
    context.drawImage(overlay, 0, 0);
  } else context.putImageData(frame, 0, 0);
}

function clearPreview(baselineCanvas, candidateCanvas) {
  paintMask(baselineCanvas, null, BASELINE_COLOR);
  paintMask(candidateCanvas, null, CANDIDATE_COLOR);
}

function changedPixelCount(left, right) {
  let changed = 0;
  for (let index = 0; index < MASK_LENGTH; index++)
    if (left[index] !== right[index]) changed++;
  return changed;
}

export function bindResearchCandidate(
  root,
  { getContext, canEdit, signal, onApply } = {},
) {
  const noop = { resetForSide() {}, destroy() {} };
  const form = root?.querySelector?.("#researchCandidateForm");
  if (!form || typeof getContext !== "function" || typeof canEdit !== "function" || typeof onApply !== "function")
    return noop;

  const fields = form.querySelector("#researchCandidateFields");
  const previewButton = form.querySelector("#researchCandidatePreview");
  const applyButton = root.querySelector("#researchCandidateApply");
  const status = root.querySelector("#researchCandidateStatus");
  const baselineCanvas = root.querySelector("#researchCandidateBaseline");
  const candidateCanvas = root.querySelector("#researchCandidateCandidate");
  if (!fields || !previewButton || !applyButton || !status || !baselineCanvas || !candidateCanvas)
    return noop;

  const listeners = new AbortController();
  let requestController = null;
  let requestSequence = 0;
  let pending = false;
  let routeAborted = Boolean(signal?.aborted);
  let preview = null;

  const contextNow = () => {
    try {
      return getContext();
    } catch {
      return null;
    }
  };
  const setStatus = (message, kind = "IDLE", busy = false) => {
    status.textContent = message;
    status.dataset.status = kind;
    status.setAttribute("aria-busy", String(busy));
  };
  const cancelRequest = () => {
    requestSequence++;
    requestController?.abort();
    requestController = null;
    pending = false;
    status.setAttribute("aria-busy", "false");
  };
  const canApplyNow = () => {
    if (!preview || routeAborted || signal?.aborted || !canEdit()) return false;
    const context = contextNow();
    if (!hasSource(context) || !sameContext(preview.context, context)) return false;
    if (!sameMask(context.currentMask, preview.baselineMask)) return false;
    if (!preview.candidateMask.some((value) => value === 1) && preview.baselineMask.some((value) => value === 1))
      return false;
    return changedPixelCount(preview.baselineMask, preview.candidateMask) > 0;
  };
  const syncControls = () => {
    const hasValidContext = hasSource(contextNow());
    const params = readParameters(form.elements);
    fields.disabled = routeAborted || signal?.aborted || !hasValidContext;
    previewButton.disabled =
      routeAborted || signal?.aborted || !hasValidContext || !params || pending;
    applyButton.disabled = !canApplyNow();
  };
  const clearCurrentPreview = () => {
    preview = null;
    clearPreview(baselineCanvas, candidateCanvas);
    applyButton.disabled = true;
  };
  const invalidateParameters = () => {
    cancelRequest();
    clearCurrentPreview();
    setStatus("Thông số đã thay đổi. Tạo lại candidate để xem trước.");
    syncControls();
  };
  const onChange = () => invalidateParameters();

  form.addEventListener("input", onChange, { signal: listeners.signal });
  form.addEventListener("change", onChange, { signal: listeners.signal });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const context = contextNow();
    const parameters = readParameters(form.elements);
    if (routeAborted || signal?.aborted || !hasSource(context) || !parameters) {
      syncControls();
      return;
    }

    const baselineMask = cloneMask(context.aiMask);
    const sequence = ++requestSequence;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    pending = true;
    clearCurrentPreview();
    setStatus("Đang tạo candidate RUO; mask gốc chưa thay đổi…", "PROCESSING", true);
    syncControls();

    const abortOnRoute = () => controller.abort();
    signal?.addEventListener("abort", abortOnRoute, { once: true });
    try {
      const response = await request("/api/v1/segment/candidate", {
        method: "POST",
        body: {
          study_id: context.studyId,
          image_id: context.imageId,
          prediction_id: context.predictionId,
          ...parameters,
        },
        signal: controller.signal,
      });
      if (
        sequence !== requestSequence ||
        signal?.aborted ||
        routeAborted ||
        !sameContext(context, contextNow())
      ) return;

      const responseBaseline = decode(response?.baseline_mask_rle);
      const candidateMask = decode(response?.candidate_mask_rle);
      if (response?.success !== true || !sameMask(responseBaseline, baselineMask)) {
        setStatus("Nguồn mask đã thay đổi hoặc phản hồi không khớp. Candidate bị loại bỏ; mask hiện tại được giữ nguyên.", "ERROR");
        return;
      }

      preview = {
        context: { ...context },
        baselineMask,
        candidateMask,
        parameters,
        provenance: response.provenance && typeof response.provenance === "object"
          ? { ...response.provenance }
          : {},
      };
      paintMask(baselineCanvas, baselineMask, BASELINE_COLOR, context.sourceCanvas);
      paintMask(candidateCanvas, candidateMask, CANDIDATE_COLOR, context.sourceCanvas);
      const provenance = preview.provenance;
      const modelVersion = typeof provenance.model_version === "string" && provenance.model_version.trim()
        ? provenance.model_version.trim().slice(0, 100)
        : "không có";
      const algorithmVersion = provenance.algorithm === "explicit_morphology_candidate" &&
        provenance.algorithm_version === "1.0.0"
        ? "explicit_morphology_candidate v1.0.0"
        : "candidate không xác định phiên bản";
      if (!candidateMask.some((value) => value === 1) && baselineMask.some((value) => value === 1))
        setStatus(`Candidate đã loại toàn bộ vùng foreground; chỉ xem, không thể áp dụng. Nguồn prediction ${context.predictionId}; model ${modelVersion}; ${algorithmVersion}.`, "PREVIEW_ONLY");
      else
        setStatus(`Đang xem candidate RUO cạnh mask AI gốc. Nguồn prediction ${context.predictionId}; model ${modelVersion}; ${algorithmVersion}. Chưa thay đổi mask chỉnh sửa hoặc lưu hồ sơ.`, "PREVIEW");
    } catch (error) {
      if (error?.name !== "AbortError" && sequence === requestSequence && !signal?.aborted) {
        clearCurrentPreview();
        setStatus(error?.message || "Không tạo được candidate; mask AI gốc vẫn dùng được.", "ERROR");
      }
    } finally {
      signal?.removeEventListener("abort", abortOnRoute);
      if (sequence === requestSequence) {
        requestController = null;
        pending = false;
        status.setAttribute("aria-busy", "false");
        syncControls();
      }
    }
  }, { signal: listeners.signal });

  applyButton.addEventListener("click", (event) => {
    event.preventDefault();
    if (!canApplyNow()) {
      syncControls();
      return;
    }
    const current = preview;
    try {
      const accepted = onApply({
        mask: current.candidateMask.slice(),
        changedPixels: changedPixelCount(current.baselineMask, current.candidateMask),
        parameters: { ...current.parameters },
        provenance: { ...current.provenance },
      });
      if (accepted === false) {
        setStatus("Quyền chỉnh sửa đã thay đổi. Candidate chưa được áp dụng.", "ERROR");
        syncControls();
        return;
      }
      setStatus("Đã chép candidate vào mask chỉnh sửa. Có thể hoàn tác; chưa lưu rà soát.", "APPLIED");
      syncControls();
    } catch (error) {
      setStatus(error?.message || "Không áp dụng được candidate; mask gốc được giữ nguyên.", "ERROR");
      syncControls();
    }
  }, { signal: listeners.signal });

  root.addEventListener("ova:mask-changed", syncControls, { signal: listeners.signal });
  root.addEventListener("ova:review-lock-changed", syncControls, { signal: listeners.signal });
  root.addEventListener("ova:lease-lost", syncControls, { signal: listeners.signal });
  root.addEventListener("ova:lease-restored", syncControls, { signal: listeners.signal });

  const onRouteAbort = () => {
    routeAborted = true;
    cancelRequest();
    clearCurrentPreview();
    setStatus("Phiên xem đã kết thúc; candidate đã bị hủy.", "CANCELLED");
    syncControls();
  };
  signal?.addEventListener("abort", onRouteAbort, { once: true });

  const resetForSide = () => {
    cancelRequest();
    clearCurrentPreview();
    form.reset();
    setStatus("Bên ảnh đã thay đổi. Hãy chọn lại từng tham số để tạo candidate.");
    syncControls();
  };
  const destroy = () => {
    cancelRequest();
    clearCurrentPreview();
    listeners.abort();
    signal?.removeEventListener("abort", onRouteAbort);
  };

  clearCurrentPreview();
  setStatus("Chưa tạo candidate.");
  syncControls();
  return { resetForSide, destroy };
}
