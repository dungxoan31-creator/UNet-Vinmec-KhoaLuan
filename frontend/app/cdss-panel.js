import { request } from "./api.js";

const BOOLEAN_OPTIONS = [
  ["true", "Có"],
  ["false", "Không"],
];

const IOTA_RULES = [
  ["b1_unilocular_cyst", "B1 · Nang đơn thùy"],
  ["b2_solid_component_lt_7mm", "B2 · Phần đặc nhỏ hơn 7 mm"],
  ["b3_acoustic_shadows", "B3 · Có bóng cản âm"],
  ["b4_smooth_multilocular_lt_100mm", "B4 · Đa thùy, thành nhẵn, dưới 100 mm"],
  ["b5_no_detectable_blood_flow", "B5 · Không thấy dòng máu"],
  ["m1_irregular_solid_tumor", "M1 · U đặc không đều"],
  ["m2_ascites", "M2 · Có cổ trướng"],
  ["m3_four_or_more_papillary_projections", "M3 · Từ 4 chồi nhú"],
  ["m4_irregular_multilocular_solid_ge_100mm", "M4 · Đa thùy đặc không đều, từ 100 mm"],
  ["m5_very_strong_color_doppler", "M5 · Tín hiệu Doppler màu rất mạnh"],
];

const PATIENT_CONTEXT = [
  ["is_premenopausal", "Bác sĩ xác nhận tiền mãn kinh"],
  ["is_persistent_adnexal_mass", "Bác sĩ xác nhận khối phần phụ tồn tại dai dẳng"],
  ["surgery_indicated", "Bác sĩ đánh giá có chỉ định phẫu thuật"],
];

function selectMarkup(name, label, options, { id = name } = {}) {
  const choices = options
    .map(([value, text]) => `<option value="${value}">${text}</option>`)
    .join("");
  return `<label class="field" for="${id}">${label}
    <select id="${id}" name="${name}" autocomplete="off">
      <option value="">-- Chưa chọn --</option>${choices}
    </select>
  </label>`;
}

function booleanSelect(name, label) {
  return selectMarkup(name, label, BOOLEAN_OPTIONS);
}

function numberMarkup(name, label, { min = 0, step = 1 } = {}) {
  return `<label class="field" for="${name}">${label}
    <input id="${name}" name="${name}" type="number" min="${min}" step="${step}" inputmode="${step === 1 ? "numeric" : "decimal"}" autocomplete="off">
  </label>`;
}

export function cdssPanelMarkup(disabled = false) {
  const disabledAttribute = disabled ? " disabled" : "";
  const iotaFields = IOTA_RULES.map(([name, label]) => booleanSelect(name, label)).join("");
  const contextFields = PATIENT_CONTEXT.map(([name, label]) => booleanSelect(name, label)).join("");

  return `<details id="cdssPanel" class="cdss-panel">
    <summary>O-RADS / IOTA · nhập liệu nghiên cứu (RUO)</summary>
    <div class="cdss-content">
      <p class="cdss-ruo-note">Chỉ đối chiếu quy tắc trong nghiên cứu; không phải chẩn đoán, không chọn O-RADS cuối cùng và không đưa khuyến nghị xử trí. Kết quả không được lưu vào hồ sơ.</p>
      <form id="cdssForm">
        <fieldset id="cdssFields"${disabledAttribute}>
          <legend>Chỉ nhập mô tả bác sĩ xác nhận cho bên đang xem</legend>
          <div class="cdss-grid">
            ${selectMarkup("assessment_source", "Nguồn mô tả", [["clinician", "Bác sĩ nhập"]])}
            ${selectMarkup("modality", "Phương thức", [["ultrasound_2d", "Siêu âm 2D"]])}
            ${booleanSelect("ultrasound_exam_complete", "Khảo sát siêu âm 2D đầy đủ")}
            ${numberMarkup("max_diameter_mm", "Đường kính lớn nhất của tổn thương (mm)", { min: 0, step: "any" })}
            ${numberMarkup("locules_count", "Số thùy nang", { min: 1 })}
            ${booleanSelect("has_solid_component", "Có thành phần đặc")}
            ${numberMarkup("papillary_projections_count", "Số chồi nhú", { min: 0 })}
            ${selectMarkup("fluid_echogenicity", "Độ hồi âm dịch", [
              ["anechoic", "Trống âm"],
              ["low_level", "Hồi âm mức thấp"],
              ["ground_glass", "Kính mờ"],
              ["hemorrhagic", "Xuất huyết"],
              ["mixed", "Hỗn hợp"],
            ])}
            ${booleanSelect("acoustic_shadowing", "Có bóng cản âm")}
            ${booleanSelect("wall_irregular", "Thành không đều")}
            ${selectMarkup("color_score", "Color score (1–4)", [
              ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"],
            ])}
            ${booleanSelect("has_ascites", "Có cổ trướng")}
            ${booleanSelect("has_peritoneal_nodules", "Có nốt phúc mạc")}
          </div>
          <details class="cdss-optional-inputs">
            <summary>Đặc điểm IOTA Simple Rules (không bắt buộc)</summary>
            <div class="cdss-grid">${iotaFields}</div>
          </details>
          <details class="cdss-optional-inputs">
            <summary>Bối cảnh do bác sĩ xác nhận (không bắt buộc)</summary>
            <div class="cdss-grid">${contextFields}</div>
          </details>
          <p class="muted small">Không tự lấy số đo từ mask, tuổi, tên ảnh hoặc bên đối diện. Ô chưa chọn sẽ được gửi dưới dạng thiếu; không đồng nghĩa với “Không”.</p>
          <button id="cdssEvaluate" class="btn small primary" type="submit">Đối chiếu quy tắc RUO</button>
        </fieldset>
      </form>
      <p id="cdssAccessHint" class="muted small" hidden></p>
      <div id="cdssResult" class="cdss-result" data-status="NOT_EVALUATED" role="status" aria-live="polite" aria-busy="false">Chưa đối chiếu. Các mô tả hiện đang để trống.</div>
    </div>
  </details>`;
}

function selectedBoolean(value) {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

function addBooleanIfSelected(target, name, control) {
  const value = selectedBoolean(control?.value);
  if (value !== undefined) target[name] = value;
}

function addNumberIfValid(target, name, control, { integer = false, min = -Infinity } = {}) {
  if (!control || control.value === "") return;
  const value = Number(control.value);
  if (
    Number.isFinite(value) &&
    value >= min &&
    (!integer || Number.isSafeInteger(value))
  ) target[name] = value;
}

function buildRequestBody(elements) {
  const visionFindings = {};
  for (const name of ["assessment_source", "modality", "fluid_echogenicity"]) {
    const value = elements[name]?.value;
    if (typeof value === "string" && value !== "") visionFindings[name] = value;
  }
  for (const name of ["ultrasound_exam_complete", "has_solid_component", "acoustic_shadowing", "wall_irregular", "has_ascites", "has_peritoneal_nodules"]) {
    addBooleanIfSelected(visionFindings, name, elements[name]);
  }
  addNumberIfValid(visionFindings, "max_diameter_mm", elements.max_diameter_mm, { min: 0 });
  addNumberIfValid(visionFindings, "locules_count", elements.locules_count, { integer: true, min: 1 });
  addNumberIfValid(visionFindings, "papillary_projections_count", elements.papillary_projections_count, { integer: true, min: 0 });
  const colorScore = elements.color_score?.value;
  if (colorScore !== "" && colorScore != null) {
    const parsed = Number(colorScore);
    if (Number.isInteger(parsed) && parsed >= 1 && parsed <= 4)
      visionFindings.color_score = parsed;
  }

  const iotaSimpleRules = {};
  for (const [name] of IOTA_RULES) addBooleanIfSelected(iotaSimpleRules, name, elements[name]);
  if (Object.keys(iotaSimpleRules).length)
    visionFindings.iota_simple_rules = iotaSimpleRules;

  const patientContext = {};
  for (const [name] of PATIENT_CONTEXT) addBooleanIfSelected(patientContext, name, elements[name]);

  return {
    vision_findings: visionFindings,
    ...(Object.keys(patientContext).length ? { patient_context: patientContext } : {}),
  };
}

function sameContext(left, right) {
  return Boolean(left && right) &&
    left.studyId === right.studyId &&
    left.imageId === right.imageId &&
    left.side === right.side;
}

function renderResponse(result, response) {
  const status = typeof response?.status === "string" ? response.status : "UNKNOWN";
  const stratification = response?.orads_stratification ?? {};
  const lines = [`Trạng thái RUO: ${status}`];
  if (status === "RULE_MATCHED" && typeof stratification.category === "string" && stratification.category.trim()) {
    lines.push(`Phân loại theo quy tắc (RUO, cần bác sĩ xác nhận): ${stratification.category}`);
  }
  if (typeof stratification.reason === "string" && stratification.reason.trim())
    lines.push(stratification.reason);

  const missing = Array.isArray(stratification.missing_fields)
    ? stratification.missing_fields
    : Array.isArray(response?.missing_fields) ? response.missing_fields : [];
  if (missing.length) lines.push(`Còn thiếu: ${missing.join(", ")}`);

  const iota = response?.iota_evaluation;
  if (iota && typeof iota.rule_verdict === "string")
    lines.push(`IOTA Simple Rules (RUO): ${iota.rule_verdict}`);
  const iotaMissing = Array.isArray(iota?.missing_fields) ? iota.missing_fields : [];
  if (iotaMissing.length) lines.push(`IOTA còn thiếu: ${iotaMissing.join(", ")}`);

  const citations = Array.isArray(response?.citations) ? response.citations : [];
  const citationTitles = citations
    .map((citation) => {
      const title = typeof citation?.title === "string" ? citation.title.trim() : "";
      const url = typeof citation?.url === "string" ? citation.url.trim() : "";
      return title ? `${title}${url ? ` · ${url}` : ""}` : "";
    })
    .filter(Boolean);
  if (citationTitles.length) lines.push(`Nguồn: ${citationTitles.join("; ")}`);

  result.dataset.status = status;
  result.textContent = lines.join("\n");
}

export function bindCdssPanel(root, { canEvaluate, getContext, signal } = {}) {
  const form = root?.querySelector?.("#cdssForm");
  const noop = {
    resetForSide() {},
    setEditable() {},
    destroy() {},
  };
  if (!form || typeof canEvaluate !== "function" || typeof getContext !== "function")
    return noop;

  const fields = form.querySelector("#cdssFields");
  const button = form.querySelector("#cdssEvaluate");
  const result = root.querySelector("#cdssResult");
  const accessHint = root.querySelector("#cdssAccessHint");
  if (!fields || !button || !result) return noop;

  const listeners = new AbortController();
  let requestController = null;
  let requestSequence = 0;
  let editable = false;

  const setStatus = (message, status = "NOT_EVALUATED") => {
    result.dataset.status = status;
    result.textContent = message;
    result.setAttribute("aria-busy", "false");
  };

  const cancelRequest = () => {
    requestSequence += 1;
    requestController?.abort();
    requestController = null;
    result.setAttribute("aria-busy", "false");
  };

  const setEditable = (enabled) => {
    editable = Boolean(enabled) && canEvaluate() && !signal?.aborted;
    if (!editable) cancelRequest();
    fields.disabled = !editable;
    button.disabled = !editable;
    if (accessHint) {
      accessHint.hidden = editable;
      accessHint.textContent = editable
        ? ""
        : "Chế độ chỉ xem hoặc quyền chỉnh sửa đã hết hạn.";
    }
    if (!editable) setStatus("Không có quyền đối chiếu hoặc phiên đánh giá đã kết thúc.");
  };

  const resetForSide = () => {
    cancelRequest();
    form.reset();
    setStatus("Bên ảnh đã thay đổi. Hãy nhập lại mô tả riêng cho bên đang xem.");
    setEditable(canEvaluate());
  };

  const onRouteAbort = () => {
    cancelRequest();
    setStatus("Phiên xem đã kết thúc; kết quả đang xử lý đã bị hủy.");
    setEditable(false);
  };

  form.addEventListener("input", () => {
    cancelRequest();
    setStatus("Thông tin đã thay đổi. Đối chiếu lại để cập nhật kết quả.");
  }, { signal: listeners.signal });
  form.addEventListener("change", () => {
    cancelRequest();
    setStatus("Thông tin đã thay đổi. Đối chiếu lại để cập nhật kết quả.");
  }, { signal: listeners.signal });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!editable || !canEvaluate() || signal?.aborted) {
      setEditable(false);
      return;
    }
    if (!form.reportValidity()) return;

    const context = { ...getContext() };
    if (!context.studyId || !context.imageId || !context.side) {
      setStatus("Chưa có ảnh và bên đang xem để đối chiếu.");
      return;
    }

    const sequence = ++requestSequence;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    const abortOnRoute = () => controller.abort();
    signal?.addEventListener("abort", abortOnRoute, { once: true });
    button.disabled = true;
    button.textContent = "Đang đối chiếu…";
    fields.disabled = true;
    result.dataset.status = "PROCESSING";
    result.textContent = "Đang đối chiếu dữ liệu nhập với bộ quy tắc RUO…";
    result.setAttribute("aria-busy", "true");

    try {
      const response = await request("/api/v1/cdss/evaluate", {
        method: "POST",
        body: buildRequestBody(form.elements),
        signal: controller.signal,
      });
      if (sequence !== requestSequence || signal?.aborted || !sameContext(context, getContext())) return;
      renderResponse(result, response);
    } catch (error) {
      if (error?.name !== "AbortError" && sequence === requestSequence)
        setStatus(error?.message || "Không đối chiếu được dữ liệu; hãy thử lại.", "ERROR");
    } finally {
      signal?.removeEventListener("abort", abortOnRoute);
      if (sequence === requestSequence) {
        requestController = null;
        result.setAttribute("aria-busy", "false");
        const canEditAgain = editable && canEvaluate() && !signal?.aborted;
        fields.disabled = !canEditAgain;
        button.disabled = !canEditAgain;
        button.textContent = "Đối chiếu quy tắc RUO";
      }
    }
  }, { signal: listeners.signal });

  signal?.addEventListener("abort", onRouteAbort, { once: true });
  setEditable(canEvaluate());

  return {
    resetForSide,
    setEditable,
    destroy() {
      cancelRequest();
      signal?.removeEventListener("abort", onRouteAbort);
      listeners.abort();
    },
  };
}
