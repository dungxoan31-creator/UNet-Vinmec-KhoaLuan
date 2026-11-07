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

const CLINICAL_MACRO_PRESETS = {
  PHYSIOLOGIC_FOLLICLE: {
    locules_count: "1",
    has_solid_component: "false",
    papillary_projections_count: "0",
    fluid_echogenicity: "anechoic",
    acoustic_shadowing: "false",
    wall_irregular: "false",
    color_score: "1",
    has_ascites: "false",
    has_peritoneal_nodules: "false",
    b1_unilocular_cyst: "true",
  },
  HEMORRHAGIC_CYST: {
    locules_count: "1",
    has_solid_component: "false",
    papillary_projections_count: "0",
    fluid_echogenicity: "mixed",
    acoustic_shadowing: "false",
    wall_irregular: "false",
    color_score: "1",
    has_ascites: "false",
    has_peritoneal_nodules: "false",
    b1_unilocular_cyst: "true",
  },
  CLASSIC_DERMOID: {
    locules_count: "1",
    has_solid_component: "false",
    papillary_projections_count: "0",
    fluid_echogenicity: "low_level",
    acoustic_shadowing: "true",
    wall_irregular: "false",
    color_score: "1",
    has_ascites: "false",
    has_peritoneal_nodules: "false",
    b3_acoustic_shadows: "true",
  },
  ENDOMETRIOMA: {
    locules_count: "1",
    has_solid_component: "false",
    papillary_projections_count: "0",
    fluid_echogenicity: "ground_glass",
    acoustic_shadowing: "false",
    wall_irregular: "false",
    color_score: "1",
    has_ascites: "false",
    has_peritoneal_nodules: "false",
    b1_unilocular_cyst: "true",
  },
  SMOOTH_MULTILOCULAR_BENIGN: {
    locules_count: "2",
    has_solid_component: "false",
    papillary_projections_count: "0",
    fluid_echogenicity: "anechoic",
    acoustic_shadowing: "false",
    wall_irregular: "false",
    color_score: "1",
    has_ascites: "false",
    has_peritoneal_nodules: "false",
    b4_smooth_multilocular_lt_100mm: "true",
  },
};

const CLINICAL_FIELD_LABELS = {
  max_diameter_mm: "Đường kính lớn nhất (mm)",
  locules_count: "Số thùy",
  has_solid_component: "Thành phần đặc",
  papillary_projections_count: "Số chồi nhú",
  acoustic_shadowing: "Bóng cản âm",
  fluid_echogenicity: "Độ hồi âm dịch",
  wall_irregular: "Thành không đều",
  color_score: "Thang điểm Doppler màu",
  has_ascites: "Cổ trướng",
  has_peritoneal_nodules: "Nốt phúc mạc",
  is_premenopausal: "Tình trạng tiền mãn kinh",
  is_persistent_adnexal_mass: "Khối phần phụ tồn tại dai dẳng",
  surgery_indicated: "Bác sĩ đánh giá có chỉ định phẫu thuật",
  b1_unilocular_cyst: "B1 · Nang đơn thùy",
  b2_solid_component_lt_7mm: "B2 · Phần đặc nhỏ hơn 7 mm",
  b3_acoustic_shadows: "B3 · Có bóng cản âm",
  b4_smooth_multilocular_lt_100mm: "B4 · Đa thùy, thành nhẵn, dưới 100 mm",
  b5_no_detectable_blood_flow: "B5 · Không thấy dòng máu",
  m1_irregular_solid_tumor: "M1 · U đặc không đều",
  m2_ascites: "M2 · Có cổ trướng",
  m3_four_or_more_papillary_projections: "M3 · Từ 4 chồi nhú",
  m4_irregular_multilocular_solid_ge_100mm: "M4 · Đa thùy đặc không đều, từ 100 mm",
  m5_very_strong_color_doppler: "M5 · Tín hiệu Doppler màu rất mạnh",
};

const STATUS_LABELS = {
  RULE_MATCHED: "Khớp quy tắc",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  UNSUPPORTED_PATTERN: "Mẫu hình chưa được quy tắc RUO hỗ trợ",
  NOT_EVALUATED: "Chưa đối chiếu",
  UNKNOWN: "Không xác định",
};

function clinicalFieldLabel(field) {
  if (typeof field !== "string") return "Trường cần bổ sung";
  const iotaPrefix = "iota_simple_rules.";
  const patientPrefix = "patient_context.";
  if (field.startsWith(iotaPrefix))
    return `Đặc điểm IOTA: ${CLINICAL_FIELD_LABELS[field.slice(iotaPrefix.length)] || field.slice(iotaPrefix.length).replaceAll("_", " ")}`;
  if (field.startsWith(patientPrefix))
    return `Bối cảnh: ${CLINICAL_FIELD_LABELS[field.slice(patientPrefix.length)] || field.slice(patientPrefix.length).replaceAll("_", " ")}`;
  return CLINICAL_FIELD_LABELS[field] || field.replaceAll("_", " ");
}

const IOTA_VERDICT_LABELS = {
  NOT_EVALUATED: "Chưa đối chiếu",
  BENIGN: "Chỉ có đặc điểm lành tính theo IOTA",
  MALIGNANT: "Có đặc điểm M theo IOTA; cần bác sĩ rà soát",
  INCONCLUSIVE: "Đặc điểm IOTA chưa phân định",
};

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
      <p class="cdss-ruo-note">Chỉ đối chiếu quy tắc trong nghiên cứu; không phải chẩn đoán, không chọn O-RADS cuối cùng và không đưa khuyến nghị xử trí. Assessment RUO được lưu theo snapshot vùng và review để có thể truy vết; không ghi thành chẩn đoán hồ sơ.</p>
      <p id="cdssRegionStatus" class="muted small" role="status">Chọn một vùng đã xác nhận để xem số đo và assessment đã lưu.</p>
      <details id="cdssRegionHistory" class="cdss-region-history" hidden>
        <summary>Lịch sử phép đo và assessment RUO của vùng</summary>
        <p id="cdssRegionHistoryStatus" class="muted small" role="status"></p>
        <pre id="cdssRegionHistoryContent" class="cdss-region-history-content"></pre>
        <button id="cdssRegionHistoryMore" class="btn small" type="button" hidden>Tải thêm lịch sử</button>
      </details>
      <div id="aiDiagnosisCard" class="ai-diagnosis-card">
        <div class="model-limit-title">Giới hạn đầu ra mô hình:</div>
        <div id="aiDiagnosisContent" style="font-size: 0.9em; line-height: 1.4;">Checkpoint hiện tại chỉ hỗ trợ phân đoạn và đo lường; không phân loại mô bệnh học hoặc nguy cơ ác tính.</div>
      </div>
      <form id="cdssForm">
        <fieldset id="cdssFields"${disabledAttribute}>
          <legend>Chỉ nhập mô tả bác sĩ xác nhận cho bên đang xem</legend>
          <div class="cdss-macro-strip" role="group" aria-label="Mẫu gợi ý mô tả nhanh (RUO)">
            <span class="muted small" style="align-self:center;margin-right:4px;">Gợi ý nhanh (RUO):</span>
            <button type="button" class="cdss-macro-chip" data-macro="PHYSIOLOGIC_FOLLICLE" title="Nang noãn buồng trứng sinh lý (<30 mm)">Nang sinh lý (&lt;30mm)</button>
            <button type="button" class="cdss-macro-chip" data-macro="HEMORRHAGIC_CYST" title="Nang hoàng thể xuất huyết / lưới sợi fibrin">Nang xuất huyết</button>
            <button type="button" class="cdss-macro-chip" data-macro="CLASSIC_DERMOID" title="U bì / U quái trưởng thành lành tính có bóng cản âm">U bì / U quái</button>
            <button type="button" class="cdss-macro-chip" data-macro="ENDOMETRIOMA" title="U lạc nội mạc tử cung dịch kính mờ">Lạc nội mạc tử cung</button>
            <button type="button" class="cdss-macro-chip" data-macro="SMOOTH_MULTILOCULAR_BENIGN" title="Nang đa thùy thành nhẵn lành tính">Đa thùy nhẵn</button>
          </div>
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
          <label class="check-row"><input id="cdssConfirm" type="checkbox" required> Tôi xác nhận các mô tả đang nhập thuộc đúng vùng đã chọn và do tôi kiểm tra.</label>
          <button id="cdssEvaluate" class="btn small primary" type="submit">Lưu và đối chiếu RUO</button>
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
  const lines = [`Trạng thái RUO: ${STATUS_LABELS[status] || status}`];
  if (status === "RULE_MATCHED" && typeof stratification.category === "string" && stratification.category.trim()) {
    lines.push(`Phân loại theo quy tắc (RUO, cần bác sĩ xác nhận): ${stratification.category}`);
  }
  if (typeof stratification.reason === "string" && stratification.reason.trim())
    lines.push(stratification.reason);

  const missing = Array.isArray(stratification.missing_fields)
    ? stratification.missing_fields
    : Array.isArray(response?.missing_fields) ? response.missing_fields : [];
  if (missing.length) lines.push(`Còn thiếu: ${missing.map(clinicalFieldLabel).join(", ")}`);

  const iota = response?.iota_evaluation;
  if (iota && typeof iota.rule_verdict === "string")
    lines.push(`IOTA Simple Rules (RUO): ${IOTA_VERDICT_LABELS[iota.rule_verdict] || iota.rule_verdict}`);
  const iotaMissing = Array.isArray(iota?.missing_fields) ? iota.missing_fields : [];
  if (iotaMissing.length) lines.push(`IOTA còn thiếu: ${iotaMissing.map(clinicalFieldLabel).join(", ")}`);

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

export function bindCdssPanel(root, { canEvaluate, getContext, signal, requireSavedRegion = false, onCalipers } = {}) {
  const form = root?.querySelector?.("#cdssForm");
  const noop = {
    resetForSide() {},
    setEditable() {},
    setRegionContext() {},
    destroy() {},
  };
  if (!form || typeof canEvaluate !== "function" || typeof getContext !== "function")
    return noop;

  const fields = form.querySelector("#cdssFields");
  const button = form.querySelector("#cdssEvaluate");
  const result = root.querySelector("#cdssResult");
  const accessHint = root.querySelector("#cdssAccessHint");
  const regionStatus = root.querySelector("#cdssRegionStatus");
  const regionHistoryPanel = root.querySelector("#cdssRegionHistory");
  const regionHistoryStatus = root.querySelector("#cdssRegionHistoryStatus");
  const regionHistoryContent = root.querySelector("#cdssRegionHistoryContent");
  const regionHistoryMore = root.querySelector("#cdssRegionHistoryMore");
  const confirmation = form.querySelector("#cdssConfirm");
  if (!fields || !button || !result) return noop;
  if (confirmation) confirmation.required = Boolean(requireSavedRegion);

  const listeners = new AbortController();
  const macroButtons = root?.querySelectorAll ? Array.from(root.querySelectorAll(".cdss-macro-chip")) : [];
  let requestController = null;
  let regionController = null;
  let requestSequence = 0;
  let regionSequence = 0;
  let editable = false;
  let regionContext = null;
  let regionReady = !requireSavedRegion;
  let assessmentRevision = 0;
  let pendingSave = null;
  let sourceCaliperEventId = null;
  let sourceCaliperDiameter = null;
  let regionHistory = { calipers: [], assessments: [], caliperCursor: null, assessmentCursor: null };
  let historyLoading = false;

  const accessState = () => {
    if (!canEvaluate() || signal?.aborted)
      return { allowed: false, message: "Chế độ chỉ xem hoặc quyền chỉnh sửa đã hết hạn." };
    if (requireSavedRegion && !regionContext)
      return { allowed: false, message: "Chọn một vùng hình học đã được bác sĩ xác nhận." };
    if (requireSavedRegion && !regionReady)
      return { allowed: false, message: "Đang tải dữ liệu vùng; chờ hoặc tải lại trước khi tiếp tục." };
    return { allowed: true, message: "" };
  };

  const sameRegion = (left, right) => Boolean(left && right) &&
    left.studyId === right.studyId && left.imageId === right.imageId &&
    left.assignmentRequestId === right.assignmentRequestId && left.regionId === right.regionId &&
    left.reviewId === right.reviewId && left.maskSha256 === right.maskSha256;

  const regionQuery = (region) => new URLSearchParams({
    assignment_request_id: region.assignmentRequestId,
    review_id: region.reviewId,
    mask_sha256: region.maskSha256,
  }).toString();

  const renderRegionHistory = (message = "") => {
    if (!regionHistoryPanel || !regionHistoryContent || !regionHistoryMore) return;
    regionHistoryPanel.hidden = !regionContext;
    const lines = [];
    if (regionHistory.calipers.length) {
      lines.push("Caliper:");
      for (const item of regionHistory.calipers) {
        const value = item.diameter_mm != null && Number.isFinite(Number(item.diameter_mm))
          ? `${Number(item.diameter_mm).toFixed(3)} mm`
          : Number.isFinite(Number(item.diameter_px))
            ? `${Number(item.diameter_px).toFixed(1)} px · chưa có mm hợp lệ`
            : "kích thước chưa hợp lệ";
        const state = item.current ? "hiện hành" : "lịch sử / stale";
        lines.push(`${item.label || "Caliper"} · revision ${item.measurement_revision} · ${value} · ${state} · ${item.created_at || "thời điểm chưa rõ"}`);
      }
    }
    if (regionHistory.assessments.length) {
      if (lines.length) lines.push("");
      lines.push("Assessment RUO:");
      for (const item of regionHistory.assessments) {
        const state = item.current ? "hiện hành" : "lịch sử / stale";
        const status = STATUS_LABELS[item.result?.status] || "Trạng thái RUO chưa được xác định";
        lines.push(`Revision ${item.assessment_revision} · ${status} · ${state} · ${item.created_at || "thời điểm chưa rõ"}`);
      }
    }
    regionHistoryContent.textContent = lines.length ? lines.join("\n") : "Chưa có lịch sử phép đo hoặc assessment cho vùng này.";
    if (regionHistoryStatus)
      regionHistoryStatus.textContent = message || `Đang hiển thị ${regionHistory.calipers.length} caliper và ${regionHistory.assessments.length} assessment RUO.`;
    regionHistoryMore.hidden = !regionHistory.caliperCursor && !regionHistory.assessmentCursor;
    regionHistoryMore.disabled = historyLoading;
    regionHistoryMore.textContent = historyLoading ? "Đang tải lịch sử…" : "Tải thêm lịch sử";
  };

  const loadMoreRegionHistory = async () => {
    if (historyLoading || !regionContext || (!regionHistory.caliperCursor && !regionHistory.assessmentCursor)) return;
    const selected = { ...regionContext };
    const sequence = regionSequence;
    const controller = regionController;
    if (!controller || controller.signal.aborted) return;
    const base = `/api/cases/${encodeURIComponent(selected.studyId)}/images/${encodeURIComponent(selected.imageId)}`;
    const query = (cursor) => {
      const params = new URLSearchParams(regionQuery(selected));
      params.set("limit", "100");
      params.set("cursor", cursor);
      return params.toString();
    };
    historyLoading = true;
    renderRegionHistory();
    try {
      const [calipers, assessments] = await Promise.all([
        regionHistory.caliperCursor
          ? request(`${base}/regions/${encodeURIComponent(selected.regionId)}/calipers?${query(regionHistory.caliperCursor)}`, { signal: controller.signal })
          : Promise.resolve(null),
        regionHistory.assessmentCursor
          ? request(`${base}/regions/${encodeURIComponent(selected.regionId)}/cdss-assessments?${query(regionHistory.assessmentCursor)}`, { signal: controller.signal })
          : Promise.resolve(null),
      ]);
      if (sequence !== regionSequence || controller.signal.aborted || !sameRegion(selected, regionContext)) return;
      for (const [name, page] of [["calipers", calipers], ["assessments", assessments]]) {
        if (!page) continue;
        if (!Array.isArray(page.history) || (page.history_next_cursor != null && typeof page.history_next_cursor !== "string"))
          throw new Error("Phản hồi trang lịch sử vùng không hợp lệ.");
        const idKey = "request_id";
        const known = new Set(regionHistory[name].map((row) => row[idKey]));
        regionHistory[name].push(...page.history.filter((row) => !known.has(row[idKey])));
        regionHistory[name === "calipers" ? "caliperCursor" : "assessmentCursor"] = page.history_next_cursor || null;
      }
      renderRegionHistory();
    } catch (error) {
      if (error?.name !== "AbortError" && sequence === regionSequence)
        renderRegionHistory(error?.message || "Không tải được lịch sử cũ; thử lại.");
    } finally {
      if (sequence === regionSequence) {
        historyLoading = false;
        renderRegionHistory(regionHistoryStatus?.textContent || "");
      }
    }
  };

  const refreshRegionHistory = async (selected) => {
    const sequence = regionSequence;
    const controller = regionController;
    if (!controller || controller.signal.aborted) return;
    const base = `/api/cases/${encodeURIComponent(selected.studyId)}/images/${encodeURIComponent(selected.imageId)}`;
    try {
      const [calipers, assessments] = await Promise.all([
        request(`${base}/regions/${encodeURIComponent(selected.regionId)}/calipers?${regionQuery(selected)}`, { signal: controller.signal }),
        request(`${base}/regions/${encodeURIComponent(selected.regionId)}/cdss-assessments?${regionQuery(selected)}`, { signal: controller.signal }),
      ]);
      if (sequence !== regionSequence || controller.signal.aborted || !sameRegion(selected, regionContext)) return;
      if (!calipers.current || !assessments.current)
        throw new Error("Dữ liệu vùng đã stale; hãy tải lại vùng trước khi tiếp tục.");
      regionHistory = {
        calipers: Array.isArray(calipers.history) ? calipers.history : [],
        assessments: Array.isArray(assessments.history) ? assessments.history : [],
        caliperCursor: calipers.history_next_cursor || null,
        assessmentCursor: assessments.history_next_cursor || null,
      };
      renderRegionHistory();
    } catch (error) {
      if (error?.name !== "AbortError" && sequence === regionSequence)
        renderRegionHistory(error?.message || "Không làm mới được lịch sử vùng.");
    }
  };

  const fillValue = (name, value) => {
    const control = form.elements?.[name];
    if (control && value != null) control.value = typeof value === "boolean" ? String(value) : String(value);
  };

  const fillAssessment = (assessment) => {
    form.reset();
    const findings = assessment?.vision_findings || {};
    for (const [name, value] of Object.entries(findings)) {
      if (name === "iota_simple_rules" && value && typeof value === "object") {
        for (const [rule, selected] of Object.entries(value)) fillValue(rule, selected);
      } else fillValue(name, value);
    }
    for (const [name, value] of Object.entries(assessment?.patient_context || {})) fillValue(name, value);
    if (confirmation) confirmation.checked = false;
  };

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
    button.textContent = requireSavedRegion ? "Lưu và đối chiếu RUO" : "Đối chiếu quy tắc RUO";
    const access = accessState();
    button.disabled = !editable || !access.allowed;
    fields.disabled = !editable || !access.allowed;
    if (confirmation) confirmation.disabled = !editable || !access.allowed;
    for (const btn of macroButtons) btn.disabled = !editable || !access.allowed;
  };

  const setEditable = (enabled) => {
    const access = accessState();
    editable = Boolean(enabled) && access.allowed;
    if (!editable && requestController) cancelRequest();
    fields.disabled = !editable;
    button.disabled = !editable;
    if (confirmation) confirmation.disabled = !editable;
    for (const btn of macroButtons) btn.disabled = !editable;
    if (accessHint) {
      accessHint.hidden = editable;
      accessHint.textContent = editable ? "" : access.message;
    }
    if (!editable && !requireSavedRegion) setStatus("Không có quyền đối chiếu hoặc phiên đánh giá đã kết thúc.");
  };

  const resetForSide = () => {
    cancelRequest();
    regionSequence += 1;
    regionController?.abort();
    regionController = null;
    regionContext = null;
    regionReady = !requireSavedRegion;
    assessmentRevision = 0;
    pendingSave = null;
    sourceCaliperEventId = null;
    sourceCaliperDiameter = null;
    regionHistory = { calipers: [], assessments: [], caliperCursor: null, assessmentCursor: null };
    historyLoading = false;
    renderRegionHistory();
    form.reset();
    if (confirmation) confirmation.checked = false;
    if (regionStatus) regionStatus.textContent = "Chọn một vùng đã xác nhận để xem số đo và assessment đã lưu.";
    setStatus("Bên ảnh đã thay đổi. Hãy nhập lại mô tả riêng cho bên đang xem.");
    setEditable(canEvaluate());
  };

  const setRegionContext = (next) => {
    cancelRequest();
    regionSequence += 1;
    regionController?.abort();
    regionController = null;
    regionContext = next || null;
    regionReady = !requireSavedRegion;
    regionHistory = { calipers: [], assessments: [], caliperCursor: null, assessmentCursor: null };
    historyLoading = false;
    renderRegionHistory();
    assessmentRevision = 0;
    pendingSave = null;
    sourceCaliperEventId = null;
    sourceCaliperDiameter = null;
    form.reset();
    if (confirmation) confirmation.checked = false;
    if (!regionContext) {
      if (regionStatus) regionStatus.textContent = "Chọn một vùng đã xác nhận để xem số đo và assessment đã lưu.";
      setStatus("Chưa chọn vùng; không thể đối chiếu hoặc lưu assessment.");
      setEditable(canEvaluate());
      return;
    }
    if (regionStatus) regionStatus.textContent = "Đang tải số đo và lịch sử assessment của vùng…";
    setStatus("Đang xác minh snapshot vùng và dữ liệu nguồn…", "PROCESSING");
    setEditable(canEvaluate());
    const selected = { ...regionContext };
    const sequence = regionSequence;
    const controller = new AbortController();
    regionController = controller;
    const base = `/api/cases/${encodeURIComponent(selected.studyId)}/images/${encodeURIComponent(selected.imageId)}`;
    const query = regionQuery(selected);
    Promise.all([
      request(`${base}/regions/${encodeURIComponent(selected.regionId)}/calipers?${query}`, { signal: controller.signal }),
      request(`${base}/regions/${encodeURIComponent(selected.regionId)}/cdss-assessments?${query}`, { signal: controller.signal }),
    ]).then(([calipers, assessments]) => {
      if (sequence !== regionSequence || controller.signal.aborted || !sameRegion(selected, regionContext)) return;
      if (!calipers.current || !assessments.current)
        throw new Error("Review hoặc snapshot vùng đã cũ; tải lại các vùng đã xác nhận trước khi tiếp tục.");
      regionHistory = {
        calipers: Array.isArray(calipers.history) ? calipers.history : [],
        assessments: Array.isArray(assessments.history) ? assessments.history : [],
        caliperCursor: calipers.history_next_cursor || null,
        assessmentCursor: assessments.history_next_cursor || null,
      };
      renderRegionHistory();
      const d1 = calipers.measurements?.D1;
      const d2 = calipers.measurements?.D2;
      onCalipers?.(calipers);
      const measurement = (item) => !item ? "chưa có" : item.diameter_mm == null
        ? `${Number(item.diameter_px).toFixed(1)} px · chưa có mm hợp lệ`
        : `${Number(item.diameter_mm).toFixed(1)} mm · ${item.calibration_source || "nguồn chưa rõ"}`;
      if (regionStatus) regionStatus.textContent =
        `Vùng ${selected.regionId.slice(0, 8)} · review ${selected.reviewRevision} · D1 ${measurement(d1)} · D2 ${measurement(d2)}. Chỉ dùng nghiên cứu.`;

      const latest = assessments.latest;
      assessmentRevision = latest?.assessment_revision ?? assessments.latest_revision ?? 0;
      pendingSave = null;
      form.reset();
      if (latest?.current) {
        fillAssessment(latest);
        sourceCaliperEventId = latest.source_caliper_event_id || null;
        sourceCaliperDiameter = sourceCaliperEventId && d1?.request_id === sourceCaliperEventId
          ? Number(d1.diameter_mm).toFixed(3) : null;
        renderResponse(result, latest.result);
        result.textContent = `Assessment RUO đã lưu · phiên bản ${assessmentRevision}\n${result.textContent}`;
      } else {
        sourceCaliperEventId = d1?.usable_for_cdss ? d1.request_id : null;
        sourceCaliperDiameter = sourceCaliperEventId ? Number(d1.diameter_mm).toFixed(3) : null;
        if (sourceCaliperDiameter != null) fillValue("max_diameter_mm", Number(sourceCaliperDiameter));
        if (assessments.history?.length)
          setStatus("Assessment cũ đã stale theo vùng, review hoặc số đo nguồn; kiểm tra lại trước khi lưu.", "STALE");
        else setStatus("Chưa có assessment RUO đã lưu cho snapshot vùng này.");
      }
      if (confirmation) confirmation.checked = false;
      regionReady = true;
      setEditable(canEvaluate());
    }).catch((error) => {
      if (error?.name === "AbortError" || sequence !== regionSequence) return;
      regionReady = false;
      if (regionStatus) regionStatus.textContent = error?.message || "Không tải được dữ liệu vùng.";
      setStatus(error?.message || "Không tải được số đo và assessment; chọn lại vùng để thử lại.", "ERROR");
      setEditable(false);
    });
  };

  const onRouteAbort = () => {
    cancelRequest();
    regionSequence += 1;
    regionController?.abort();
    setStatus("Phiên xem đã kết thúc; kết quả đang xử lý đã bị hủy.");
    setEditable(false);
  };

  form.addEventListener("input", () => {
    cancelRequest();
    pendingSave = null;
    if (requireSavedRegion && sourceCaliperEventId &&
        Number(form.elements.max_diameter_mm?.value) !== Number(sourceCaliperDiameter))
      sourceCaliperEventId = null;
    setStatus("Thông tin đã thay đổi. Đối chiếu lại để cập nhật kết quả.");
  }, { signal: listeners.signal });
  form.addEventListener("change", () => {
    cancelRequest();
    pendingSave = null;
    if (requireSavedRegion && sourceCaliperEventId &&
        Number(form.elements.max_diameter_mm?.value) !== Number(sourceCaliperDiameter))
      sourceCaliperEventId = null;
    setStatus("Thông tin đã thay đổi. Đối chiếu lại để cập nhật kết quả.");
  }, { signal: listeners.signal });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const access = accessState();
    if (!editable || !access.allowed || !canEvaluate() || signal?.aborted) {
      setEditable(false);
      return;
    }
    if (!form.reportValidity()) return;

    const context = { ...getContext() };
    if (!context.studyId || !context.imageId || (!requireSavedRegion && !context.side)) {
      setStatus("Chưa có ảnh và bên đang xem để đối chiếu.");
      return;
    }

    const submittedRegion = regionContext ? { ...regionContext } : null;
    let endpoint = "/api/v1/cdss/evaluate";
    let body = buildRequestBody(form.elements);
    if (requireSavedRegion) {
      if (!confirmation?.checked) {
        setStatus("Hãy xác nhận các mô tả thuộc đúng vùng trước khi lưu assessment RUO.");
        return;
      }
      if (!submittedRegion || submittedRegion.studyId !== context.studyId || submittedRegion.imageId !== context.imageId) {
        setStatus("Ca hoặc ảnh đã đổi so với vùng đang chọn; chọn lại vùng trước khi lưu.", "STALE");
        return;
      }
      const content = {
        expected_assessment_revision: assessmentRevision,
        assignment_request_id: submittedRegion.assignmentRequestId,
        review_id: submittedRegion.reviewId,
        region_id: submittedRegion.regionId,
        mask_sha256: submittedRegion.maskSha256,
        confirmed: true,
        vision_findings: body.vision_findings,
        patient_context: body.patient_context || {},
        ...(sourceCaliperEventId ? { source_caliper_event_id: sourceCaliperEventId } : {}),
      };
      const signature = JSON.stringify(content);
      if (!pendingSave || pendingSave.signature !== signature)
        pendingSave = { signature, request_id: crypto.randomUUID(), content };
      body = {
        ...pendingSave.content,
        request_id: pendingSave.request_id,
        lease_token: context.leaseToken,
        page_instance_id: context.pageInstanceId,
      };
      endpoint = `/api/cases/${encodeURIComponent(submittedRegion.studyId)}/images/${encodeURIComponent(submittedRegion.imageId)}/regions/${encodeURIComponent(submittedRegion.regionId)}/cdss-assessments`;
    }

    const sequence = ++requestSequence;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    const abortOnRoute = () => controller.abort();
    signal?.addEventListener("abort", abortOnRoute, { once: true });
    button.disabled = true;
    button.textContent = requireSavedRegion ? "Đang lưu và đối chiếu…" : "Đang đối chiếu…";
    fields.disabled = true;
    result.dataset.status = "PROCESSING";
    result.textContent = requireSavedRegion
      ? "Đang lưu mô tả bác sĩ và đối chiếu bằng engine RUO…"
      : "Đang đối chiếu dữ liệu nhập với bộ quy tắc RUO…";
    result.setAttribute("aria-busy", "true");

    try {
      const response = await request(endpoint, {
        method: "POST",
        body,
        signal: controller.signal,
      });
      if (sequence !== requestSequence || signal?.aborted || !sameContext(context, getContext()) ||
          (requireSavedRegion && !sameRegion(submittedRegion, regionContext))) return;
      if (requireSavedRegion) {
        if (response.current === false) {
          pendingSave = null;
          regionReady = false;
          if (confirmation) confirmation.checked = false;
          setStatus(
            "Assessment vừa lưu đã stale vì dữ liệu nguồn thay đổi. Chọn lại vùng để tải phiên bản mới nhất, rồi kiểm tra và xác nhận lại mô tả.",
            "STALE",
          );
          return;
        }
        assessmentRevision = response.assessment_revision || assessmentRevision;
        pendingSave = null;
        if (confirmation) confirmation.checked = false;
        renderResponse(result, response.result);
        result.textContent = `Assessment RUO đã lưu · phiên bản ${assessmentRevision}\n${result.textContent}`;
        refreshRegionHistory(submittedRegion);
      } else renderResponse(result, response);
    } catch (error) {
      if (error?.name !== "AbortError" && sequence === requestSequence)
        setStatus(error?.message || "Không đối chiếu/lưu được dữ liệu; hãy thử lại.", "ERROR");
    } finally {
      signal?.removeEventListener("abort", abortOnRoute);
      if (sequence === requestSequence) {
        requestController = null;
        result.setAttribute("aria-busy", "false");
        const canEditAgain = editable && canEvaluate() && !signal?.aborted &&
          (!requireSavedRegion || (regionReady && Boolean(regionContext)));
        fields.disabled = !canEditAgain;
        if (confirmation) confirmation.disabled = !canEditAgain;
        button.disabled = !canEditAgain;
        button.textContent = requireSavedRegion ? "Lưu và đối chiếu RUO" : "Đối chiếu quy tắc RUO";
      }
    }
  }, { signal: listeners.signal });

  signal?.addEventListener("abort", onRouteAbort, { once: true });
  regionHistoryMore?.addEventListener("click", loadMoreRegionHistory, { signal: listeners.signal });
  for (const btn of macroButtons) {
    btn.addEventListener("click", () => {
      const access = accessState();
      if (!editable || !access.allowed || fields.disabled) return;
      const macroId = btn.getAttribute("data-macro");
      const preset = CLINICAL_MACRO_PRESETS[macroId];
      if (!preset) return;
      for (const [name, val] of Object.entries(preset)) {
        fillValue(name, val);
      }
      setStatus(`Đã điền nhanh mẫu RUO: ${btn.textContent.trim()}. Kiểm tra lại trước khi lưu.`);
    }, { signal: listeners.signal });
  }
  setEditable(canEvaluate());

  return {
    resetForSide,
    setEditable,
    setRegionContext,
    destroy() {
      cancelRequest();
      regionSequence += 1;
      regionController?.abort();
      signal?.removeEventListener("abort", onRouteAbort);
      listeners.abort();
    },
  };
}


export function updateAIDiagnosisCard(root) {
  const card = root.querySelector("#aiDiagnosisCard");
  const content = root.querySelector("#aiDiagnosisContent");
  if (!card || !content) return;

  content.textContent =
    "Checkpoint hiện tại chỉ hỗ trợ phân đoạn và đo lường; không phân loại mô bệnh học hoặc nguy cơ ác tính.";
}
