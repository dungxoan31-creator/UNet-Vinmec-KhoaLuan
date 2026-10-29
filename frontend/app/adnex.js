import { request } from "./api.js";

const OUTCOMES = [
  ["benign", "U lành tính"],
  ["borderline", "U giáp biên"],
  ["stage_i_primary_malignancy", "Ung thư xâm lấn giai đoạn I"],
  ["stage_ii_iv_primary_malignancy", "Ung thư xâm lấn giai đoạn II–IV"],
  ["secondary_metastatic", "Di căn thứ phát đến buồng trứng"],
];
const PROBABILITY_TOLERANCE = 1e-6;

export function isRenderableAdnexEvaluation(evaluation) {
  if (
    !evaluation ||
    typeof evaluation !== "object" ||
    evaluation.status !== "EVALUATED_RUO" ||
    evaluation.eligibility_status !== "ELIGIBLE" ||
    !["WITH_CA125", "WITHOUT_CA125"].includes(evaluation.model_variant) ||
    !evaluation.probabilities ||
    typeof evaluation.probabilities !== "object" ||
    Array.isArray(evaluation.probabilities)
  )
    return false;

  const expectedKeys = OUTCOMES.map(([key]) => key).sort();
  const actualKeys = Object.keys(evaluation.probabilities).sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index])
  )
    return false;

  const values = OUTCOMES.map(([key]) => evaluation.probabilities[key]);
  if (values.some((value) => !Number.isFinite(value) || value < 0 || value > 1))
    return false;

  const declaredTotal = evaluation.total_malignancy_probability;
  if (
    !Number.isFinite(declaredTotal) ||
    declaredTotal < 0 ||
    declaredTotal > 1
  )
    return false;

  const probabilityTotal = values.reduce((sum, value) => sum + value, 0);
  const malignancyTotal = values.slice(1).reduce((sum, value) => sum + value, 0);
  return (
    Math.abs(probabilityTotal - 1) <= PROBABILITY_TOLERANCE &&
    Math.abs(malignancyTotal - declaredTotal) <= PROBABILITY_TOLERANCE
  );
}

export function adnexPanelMarkup(disabled = false) {
  return `<details id="adnexPanel" class="adnex-panel">
    <summary><span>ADNEX nghiên cứu (RUO)</span><span id="adnexSide" class="muted small"></span></summary>
    <div class="adnex-content">
      <p class="adnex-ruo-note">Chỉ hỗ trợ nghiên cứu. Kết quả không phải chẩn đoán, không chọn O-RADS và không đưa khuyến nghị xử trí. Dữ liệu nhập và xác suất không được lưu vào hồ sơ.</p>
      <form id="adnexForm">
        <fieldset id="adnexFields"${disabled ? " disabled" : ""}>
          <legend>Nhập riêng cho khối đang xem</legend>
          <label class="field" for="adnexVariant">Phiên bản ADNEX
            <select id="adnexVariant" name="model_variant" required>
              <option value="">-- Chọn phiên bản --</option>
              <option value="WITH_CA125">Có kết quả CA-125</option>
              <option value="WITHOUT_CA125">Không dùng CA-125</option>
            </select>
          </label>
          <div id="adnexCa125Field" hidden>
            <label class="field" for="adnexCa125">CA-125 (U/mL)
              <input id="adnexCa125" name="ca125_u_ml" type="number" min="0" max="1000000" step="any" inputmode="decimal">
            </label>
          </div>
          <div class="adnex-grid">
            <label class="field" for="adnexAge">Tuổi tại thời điểm siêu âm (năm)
              <input id="adnexAge" name="age_years" type="number" min="0" max="130" step="any" inputmode="decimal" required>
            </label>
            <label class="field" for="adnexOncology">Trung tâm ung bướu
              <select id="adnexOncology" name="is_oncology_center" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexPersistent">Khối phần phụ tồn tại dai dẳng
              <select id="adnexPersistent" name="is_persistent_adnexal_mass" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexSurgery">Bác sĩ đánh giá cần phẫu thuật
              <select id="adnexSurgery" name="surgery_indicated" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexComplete">Siêu âm 2D đầy đủ
              <select id="adnexComplete" name="ultrasound_exam_complete" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexPhysiologic">Đã xác nhận nang noãn sinh lý
              <select id="adnexPhysiologic" name="physiologic_follicle_confirmed" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexDiameter">Đường kính lớn nhất của khối (mm)
              <input id="adnexDiameter" name="max_lesion_diameter_mm" type="number" min="0" max="10000" step="any" inputmode="decimal" required>
            </label>
            <label class="field" for="adnexSolidDiameter">Đường kính phần đặc lớn nhất (mm)
              <input id="adnexSolidDiameter" name="largest_solid_component_mm" type="number" min="0" max="10000" step="any" inputmode="decimal" required>
            </label>
            <label class="field" for="adnexLocules">Số thùy nang
              <input id="adnexLocules" name="cyst_locules_count" type="number" min="0" step="1" inputmode="numeric" required>
            </label>
            <label class="field" for="adnexPapillary">Số chồi nhú
              <input id="adnexPapillary" name="papillary_projections_count" type="number" min="0" step="1" inputmode="numeric" required>
            </label>
            <label class="field" for="adnexShadow">Bóng cản âm
              <select id="adnexShadow" name="acoustic_shadowing" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
            <label class="field" for="adnexAscites">Cổ trướng
              <select id="adnexAscites" name="has_ascites" required>
                <option value="">-- Chọn --</option><option value="true">Có</option><option value="false">Không</option>
              </select>
            </label>
          </div>
          <p class="muted small">Nhập thủ công từ siêu âm 2D. Đường kính toàn khối và phần đặc phải cùng thuộc một tổn thương; không ghép số đo các nang rời rạc. Không dùng tuổi, thước đo mask hoặc mô tả từ lần rà soát trước để điền tự động.</p>
          <button id="adnexEvaluate" class="btn small primary" type="submit">Tính xác suất nghiên cứu</button>
        </fieldset>
      </form>
      <p id="adnexAccessHint" class="muted small" hidden></p>
      <div id="adnexResult" class="adnex-result" data-status="NOT_EVALUATED" role="status" aria-live="polite">
        <p>Chưa tính. Cần nhập và xác nhận đầy đủ dữ liệu.</p>
      </div>
    </div>
  </details>`;
}

export function bindAdnexPanel(root, { getContext, canEvaluate, routeSignal }) {
  const form = root.querySelector("#adnexForm");
  if (!form)
    return {
      resetForSide() {},
      setEditable() {},
      disable() {},
      destroy() {},
    };

  const fields = form.querySelector("#adnexFields");
  const variant = form.querySelector("#adnexVariant");
  const caField = form.querySelector("#adnexCa125Field");
  const caInput = form.querySelector("#adnexCa125");
  const result = root.querySelector("#adnexResult");
  const button = form.querySelector("#adnexEvaluate");
  const sideLabel = root.querySelector("#adnexSide");
  const accessHint = root.querySelector("#adnexAccessHint");
  const listeners = new AbortController();
  let requestController = null;
  let requestSequence = 0;

  const showStatus = (message, status = "NOT_EVALUATED") => {
    result.dataset.status = status;
    result.replaceChildren();
    const text = document.createElement("p");
    text.textContent = message;
    result.append(text);
  };

  const cancelRequest = () => {
    requestSequence += 1;
    requestController?.abort();
    requestController = null;
  };

  const clearResult = (message = "Thông tin đã thay đổi. Tính lại để xem kết quả.") => {
    cancelRequest();
    showStatus(message);
    button.textContent = "Tính xác suất nghiên cứu";
    result.setAttribute("aria-busy", "false");
    fields.disabled = !canEvaluate();
  };

  const syncVariant = () => {
    const usesCa125 = variant.value === "WITH_CA125";
    caField.hidden = !usesCa125;
    caInput.required = usesCa125;
    if (!usesCa125) caInput.value = "";
    caInput.setCustomValidity("");
  };

  const clearCustomValidity = () => {
    form.elements.largest_solid_component_mm.setCustomValidity("");
    caInput.setCustomValidity("");
  };

  const setEditable = (editable) => {
    fields.disabled = !editable;
    button.disabled = !editable;
    accessHint.hidden = editable;
    accessHint.textContent = editable
      ? ""
      : "Chế độ chỉ xem hoặc quyền chỉnh sửa đã hết hạn. Tải lại ca khi cần tiếp tục.";
  };

  const resetForSide = (side) => {
    clearResult("Chọn lại các mô tả cho buồng trứng đang xem.");
    form.reset();
    clearCustomValidity();
    syncVariant();
    sideLabel.textContent = side === "L" ? "Buồng trứng trái" : "Buồng trứng phải";
    setEditable(canEvaluate());
  };

  const renderEvaluation = (evaluation) => {
    if (evaluation?.status !== "EVALUATED_RUO") {
      showStatus(
        evaluation?.reason || "Thiếu dữ liệu hợp lệ; chưa tính xác suất.",
        "NOT_EVALUATED",
      );
      return;
    }
    if (!isRenderableAdnexEvaluation(evaluation)) {
      showStatus(
        "Response ADNEX không hợp lệ; đã ẩn các xác suất.",
        "ERROR",
      );
      return;
    }

    result.dataset.status = "EVALUATED_RUO";
    result.replaceChildren();
    const heading = document.createElement("p");
    heading.id = "adnexOutputVariant";
    heading.textContent = evaluation.model_variant;
    result.append(heading);

    const list = document.createElement("dl");
    list.id = "adnexProbabilityList";
    list.className = "adnex-probabilities";
    for (const [key, label] of OUTCOMES) {
      const row = document.createElement("div");
      const term = document.createElement("dt");
      const value = document.createElement("dd");
      const probability = evaluation.probabilities[key];
      row.dataset.adnexProbability = String(probability);
      term.textContent = label;
      value.textContent = Number.isFinite(probability)
        ? new Intl.NumberFormat("vi-VN", {
            style: "percent",
            maximumFractionDigits: 1,
          }).format(probability)
        : "—";
      row.append(term, value);
      list.append(row);
    }
    result.append(list);

    const total = document.createElement("p");
    total.id = "adnexTotalMalignancyProbability";
    total.textContent = `Tổng xác suất các nhóm ác tính: ${new Intl.NumberFormat(
      "vi-VN",
      { style: "percent", maximumFractionDigits: 1 },
    ).format(evaluation.total_malignancy_probability)}`;
    result.append(total);
  };

  variant.addEventListener(
    "change",
    () => {
      syncVariant();
      clearResult();
    },
    { signal: listeners.signal },
  );
  form.addEventListener(
    "input",
    () => {
      clearCustomValidity();
      clearResult();
    },
    { signal: listeners.signal },
  );
  form.addEventListener(
    "change",
    (event) => {
      clearCustomValidity();
      if (event.target !== variant) clearResult();
    },
    { signal: listeners.signal },
  );
  form.addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();
      if (!canEvaluate()) {
        setEditable(false);
        return;
      }
      if (!form.reportValidity()) return;

      const diameter = Number(form.elements.max_lesion_diameter_mm.value);
      const solidDiameter = Number(form.elements.largest_solid_component_mm.value);
      const ca125Value = Number(caInput.value);
      form.elements.largest_solid_component_mm.setCustomValidity(
        solidDiameter > diameter
          ? "Đường kính phần đặc không thể lớn hơn đường kính toàn khối."
          : "",
      );
      caInput.setCustomValidity(
        variant.value === "WITH_CA125" && ca125Value <= 0
          ? "CA-125 phải lớn hơn 0 cho phiên bản này."
          : "",
      );
      if (!form.reportValidity()) return;

      const boolean = (name) => form.elements[name].value === "true";
      const adnexInputs = {
        model_variant: variant.value,
        age_years: Number(form.elements.age_years.value),
        is_oncology_center: boolean("is_oncology_center"),
        is_persistent_adnexal_mass: boolean("is_persistent_adnexal_mass"),
        surgery_indicated: boolean("surgery_indicated"),
        assessment_source: "clinician",
        modality: "ultrasound_2d",
        ultrasound_exam_complete: boolean("ultrasound_exam_complete"),
        max_lesion_diameter_mm: diameter,
        largest_solid_component_mm: solidDiameter,
        cyst_locules_count: Number(form.elements.cyst_locules_count.value),
        papillary_projections_count: Number(
          form.elements.papillary_projections_count.value,
        ),
        acoustic_shadowing: boolean("acoustic_shadowing"),
        has_ascites: boolean("has_ascites"),
        physiologic_follicle_confirmed: boolean(
          "physiologic_follicle_confirmed",
        ),
      };
      if (variant.value === "WITH_CA125") adnexInputs.ca125_u_ml = ca125Value;

      const context = getContext();
      const sequence = ++requestSequence;
      requestController?.abort();
      requestController = new AbortController();
      const currentController = requestController;
      const abortOnRouteExit = () => currentController.abort();
      routeSignal?.addEventListener("abort", abortOnRouteExit, { once: true });
      button.disabled = true;
      button.textContent = "Đang tính…";
      result.setAttribute("aria-busy", "true");
      showStatus("Đang tính xác suất nghiên cứu…", "PROCESSING");
      result.setAttribute("aria-busy", "true");
      fields.disabled = true;

      try {
        const response = await request("/api/v1/cdss/evaluate", {
          method: "POST",
          body: { adnex_inputs: adnexInputs },
          signal: currentController.signal,
        });
        const current = getContext();
        if (
          sequence !== requestSequence ||
          current.side !== context.side ||
          current.imageId !== context.imageId
        )
          return;
        renderEvaluation(response.adnex_evaluation);
      } catch (error) {
        if (error.name !== "AbortError" && sequence === requestSequence) {
          showStatus(error.message || "Không tính được ADNEX; thử lại sau.", "ERROR");
        }
      } finally {
        routeSignal?.removeEventListener("abort", abortOnRouteExit);
        if (sequence === requestSequence) {
          requestController = null;
          result.setAttribute("aria-busy", "false");
          button.disabled = !canEvaluate();
          button.textContent = "Tính xác suất nghiên cứu";
          fields.disabled = !canEvaluate();
        }
      }
    },
    { signal: listeners.signal },
  );

  syncVariant();
  setEditable(canEvaluate());
  return {
    resetForSide,
    setEditable,
    disable() {
      clearResult("Quyền chỉnh sửa đã hết hạn. Tải lại ca để tiếp tục.");
      setEditable(false);
    },
    destroy() {
      cancelRequest();
      listeners.abort();
    },
  };
}
