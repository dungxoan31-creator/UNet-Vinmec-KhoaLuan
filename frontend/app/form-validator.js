/**
 * form-validator.js
 * Unified validation engine and DOM inline error micro-copy helper
 * for clinical and patient management forms.
 */

export function validatePid(pid, { existingPids = [], currentPid = null } = {}) {
  const str = String(pid ?? "").trim();
  if (!str) {
    return { valid: false, error: "Mã PID không được để trống." };
  }
  if (!/^[0-9]{9}$/.test(str)) {
    return { valid: false, error: "Mã PID bắt buộc gồm đúng 9 chữ số." };
  }
  if (existingPids.includes(str) && str !== currentPid) {
    return { valid: false, error: "Mã PID này đã tồn tại trong danh sách." };
  }
  return { valid: true, error: null };
}

export function validateFullName(name) {
  const str = String(name ?? "").trim();
  if (!str) {
    return { valid: false, error: "Họ và tên không được để trống." };
  }
  if (str.length < 2) {
    return { valid: false, error: "Họ và tên tối thiểu 2 ký tự." };
  }
  if (str.length > 120) {
    return { valid: false, error: "Họ và tên tối đa 120 ký tự." };
  }
  return { valid: true, error: null };
}

export function validateBirthYear(year, currentYear = new Date().getFullYear()) {
  if (year == null || year === "") {
    return { valid: false, error: "Năm sinh không được để trống." };
  }
  const y = Number(year);
  if (!Number.isInteger(y)) {
    return { valid: false, error: "Năm sinh phải là số nguyên." };
  }
  if (y < 1900) {
    return { valid: false, error: "Năm sinh phải từ năm 1900 trở lại." };
  }
  if (y > currentYear) {
    return { valid: false, error: `Năm sinh không được vượt quá ${currentYear}.` };
  }
  const age = currentYear - y;
  return { valid: true, error: null, age };
}

export function validatePhone(phone) {
  const raw = String(phone ?? "").trim();
  if (!raw) {
    return { valid: false, error: "Số điện thoại không được để trống." };
  }
  const digits = raw.replace(/\D/g, "");
  if (digits.length < 9 || digits.length > 12) {
    return { valid: false, error: "Số điện thoại phải từ 9 đến 12 chữ số." };
  }
  const cleanPhone = digits.startsWith("84") && digits.length >= 11
    ? "0" + digits.slice(2)
    : digits;
  return { valid: true, error: null, cleanPhone };
}

export function validateGender(gender) {
  const validGenders = ["female", "male", "other", "unknown"];
  if (!validGenders.includes(String(gender ?? ""))) {
    return { valid: false, error: "Vui lòng chọn giới tính hợp lệ." };
  }
  return { valid: true, error: null };
}

export function validateHometown(hometown) {
  const str = String(hometown ?? "").trim();
  if (!str) {
    return { valid: false, error: "Quê quán không được để trống." };
  }
  if (str.length > 120) {
    return { valid: false, error: "Quê quán tối đa 120 ký tự." };
  }
  return { valid: true, error: null };
}

export function validateStudyDate(dateStr) {
  const str = String(dateStr ?? "").trim();
  if (!str) {
    return { valid: false, error: "Ngày giờ khảo sát không được để trống." };
  }
  const timestamp = Date.parse(str);
  if (Number.isNaN(timestamp)) {
    return { valid: false, error: "Định dạng ngày giờ không hợp lệ." };
  }
  return { valid: true, error: null };
}

export function validateMeasurement(val, { min = 0, max = 500, label = "Kích thước" } = {}) {
  if (val == null || val === "") {
    return { valid: true, error: null };
  }
  const num = Number(val);
  if (!Number.isFinite(num)) {
    return { valid: false, error: `${label} phải là số hợp lệ.` };
  }
  if (num < min || num > max) {
    return { valid: false, error: `${label} phải nằm trong khoảng ${min} - ${max}.` };
  }
  return { valid: true, error: null };
}

/**
 * Attaches real-time validation to a form element.
 * Updates inline `.field-error` elements and toggles `aria-invalid`.
 */
export function attachInlineValidation(formElement, rules = {}, { onValidityChange = null } = {}) {
  if (!formElement) return { validateAll: () => true, reset: () => {} };

  const getErrorElement = (input) => {
    let err = input.parentElement?.querySelector(".field-error");
    if (!err) {
      err = document.createElement("span");
      err.className = "field-error";
      err.setAttribute("role", "alert");
      input.parentElement?.appendChild(err);
    }
    return err;
  };

  const validateField = (input) => {
    const name = input.name || input.id;
    const rule = rules[name];
    if (!rule) return true;

    const result = rule(input.value, input);
    const errEl = getErrorElement(input);

    if (result && !result.valid) {
      input.setAttribute("aria-invalid", "true");
      input.classList.add("input-invalid");
      errEl.textContent = result.error || "Dữ liệu không hợp lệ.";
      errEl.hidden = false;
      return false;
    } else {
      input.removeAttribute("aria-invalid");
      input.classList.remove("input-invalid");
      errEl.textContent = "";
      errEl.hidden = true;
      return true;
    }
  };

  const checkForm = () => {
    const inputs = Array.from(formElement.querySelectorAll("input, select, textarea"))
      .filter((el) => rules[el.name || el.id]);
    let allValid = true;
    for (const input of inputs) {
      if (!validateField(input)) {
        allValid = false;
      }
    }
    if (onValidityChange) onValidityChange(allValid);
    return allValid;
  };

  const onInputHandler = (e) => {
    if (rules[e.target.name || e.target.id]) {
      validateField(e.target);
      if (onValidityChange) {
        const inputs = Array.from(formElement.querySelectorAll("input, select, textarea"))
          .filter((el) => rules[el.name || el.id]);
        const valid = inputs.every((inp) => !inp.getAttribute("aria-invalid"));
        onValidityChange(valid);
      }
    }
  };

  formElement.addEventListener("input", onInputHandler);
  formElement.addEventListener("blur", onInputHandler, true);

  return {
    validateAll: checkForm,
    reset: () => {
      formElement.querySelectorAll(".field-error").forEach((el) => {
        el.textContent = "";
        el.hidden = true;
      });
      formElement.querySelectorAll("[aria-invalid]").forEach((el) => {
        el.removeAttribute("aria-invalid");
        el.classList.remove("input-invalid");
      });
    },
  };
}
