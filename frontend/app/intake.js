import { inspectDicom } from "./dicom-inspect.js";
import { getLateralityHint, suggestLaterality } from "./laterality-hint.js";
import { createIntakeSession, planBilateralDrop } from "./intake-session.js?v=20261104-directory";
import { autofillState, state } from "./state.js";
import { esc, button, field, modal, pageHead, icon, toast } from "./ui.js";
import { startBilateral } from "./upload.js?v=20261104-directory";
import { request } from "./api.js";
import { DEMO_PATIENTS, patientSearchKey } from "./demo-patients.js";
import { validateFullName, validateBirthYear, attachInlineValidation } from "./form-validator.js";

const PAGE_SIZE = 20;
const DEMO_PATIENT_ROWS = DEMO_PATIENTS.map((patient, index) => ({
  id: `demo-${index + 1}`,
  name: patient.name,
  age: patient.age,
  synthetic: true,
}));

export function renderIntake(root) {
  let cleanupUpload, search = "", page = 0, sequence = 0, searchTimer;
  const identity = state.user?.id;
  const active = () => root.isConnected && identity === state.user?.id;
  const isSynthetic = () => state.capabilities?.synthetic_demo_mode === true;

  const renderList = async ({ focusSearch = false } = {}) => {
    cleanupUpload?.();
    cleanupUpload = null;
    if (!active()) return;
    const requestId = ++sequence;
    let patients, total;
    if (isSynthetic()) {
      const filtered = DEMO_PATIENT_ROWS.filter(patient => patientSearchKey(patient.name).includes(patientSearchKey(search.trim())));
      total = filtered.length;
      patients = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
    } else {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
      if (search.trim()) params.set("search", search.trim());
      root.innerHTML = pageHead("Bắt đầu khảo sát", "Chọn hồ sơ có sẵn hoặc bắt đầu ca nghiên cứu không định danh.") +
        '<div class="banner info" role="status">Đang tải danh bạ của cơ sở hiện tại…</div>';
      try {
        const result = await request(`/api/patient-directory?${params}`);
        if (!active() || requestId !== sequence) return;
        patients = result.items.map(patient => ({ ...patient, name: patient.display_name }));
        total = result.total;
      } catch (error) {
        if (!active() || requestId !== sequence || error?.name === "AbortError") return;
        root.innerHTML = pageHead("Bắt đầu khảo sát", "Không tải được danh bạ của cơ sở hiện tại.") +
          `<div class="banner danger" role="alert">${esc(error.message)}</div>${button("Thử lại", "retry-directory", "primary")}`;
        root.querySelector('[data-action="retry-directory"]').onclick = () => renderList({ focusSearch });
        return;
      }
    }

    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (page >= pageCount) {
      page = pageCount - 1;
      return renderList({ focusSearch });
    }
    const notice = isSynthetic()
      ? '<div class="banner warning" role="status">Danh sách chỉ là dữ liệu tổng hợp cục bộ; ca tạo từ lựa chọn này không được gắn với hồ sơ bệnh nhân.</div>'
      : '<div class="banner info" role="status">Danh bạ được lưu trên máy chủ của cơ sở đang đăng nhập. Chỉ lưu họ tên và năm sinh tùy chọn.</div>';
    const actions = isSynthetic() ? "" :
      button("Tạo hồ sơ", "add-patient", "small", "plus") + button("Khảo sát không định danh", "anonymous-study", "primary");
    root.innerHTML = pageHead("Bắt đầu khảo sát", "Chọn hồ sơ có sẵn hoặc bắt đầu ca nghiên cứu không định danh.", actions) + notice +
      `<label class="field">Tìm theo tên bệnh nhân<input id="patientSearch" type="search" placeholder="Nhập tên bệnh nhân" value="${esc(search)}"></label>` +
      `<section class="panel"><div class="panel-head"><h2>${isSynthetic() ? "Hồ sơ mẫu" : "Danh bạ bệnh nhân"}</h2><span class="badge">${total} hồ sơ</span></div><div class="table-wrap intake-patient-list" role="region" aria-label="Danh sách bệnh nhân" tabindex="0"><table><thead><tr><th>Bệnh nhân</th><th>${isSynthetic() ? "Tuổi mẫu" : "Năm sinh"}</th><th>Thao tác</th></tr></thead><tbody>${patients.map((patient, index) => `<tr><td data-label="Bệnh nhân"><strong>${esc(patient.name)}</strong></td><td data-label="${isSynthetic() ? "Tuổi mẫu" : "Năm sinh"}">${isSynthetic() ? `${patient.age} tuổi` : (patient.birth_year || "Chưa ghi nhận")}</td><td data-label="Thao tác"><div class="table-actions-compact"><button class="btn small primary" type="button" data-select="${index}">Chọn hồ sơ</button>${isSynthetic() ? "" : `<button class="btn small icon-only" type="button" data-edit-patient="${esc(patient.id)}" title="Sửa hồ sơ" aria-label="Sửa thông tin ${esc(patient.name)}">${icon("edit", 16)}</button><button class="btn small danger icon-only" type="button" data-delete-patient="${esc(patient.id)}" title="Gỡ hồ sơ khỏi danh bạ" aria-label="Gỡ hồ sơ ${esc(patient.name)}">${icon("trash", 16)}</button>`}</div></td></tr>`).join("")}</tbody></table>${patients.length ? "" : `<p class="muted">${search.trim() ? "Không tìm thấy hồ sơ phù hợp." : "Chưa có hồ sơ trong danh bạ."}</p>`}</div></section>` +
      `<div class="actions"><button type="button" class="btn small" id="patientPrev" ${page === 0 ? "disabled" : ""}>Trang trước</button><span role="status">Trang ${page + 1} / ${pageCount}</span><button type="button" class="btn small" id="patientNext" ${page + 1 >= pageCount ? "disabled" : ""}>Trang sau</button></div>`;

    const searchInput = root.querySelector("#patientSearch");
    searchInput.oninput = event => {
      search = event.target.value;
      page = 0;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => renderList({ focusSearch: true }), 180);
    };
    if (focusSearch) {
      searchInput.focus();
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }
    root.querySelector("#patientPrev").onclick = () => { page--; renderList(); };
    root.querySelector("#patientNext").onclick = () => { page++; renderList(); };
    const open = patient => {
      if (!active()) return;
      cleanupUpload?.();
      cleanupUpload = renderUpload(root, patient, () => renderList());
    };
    root.querySelector('[data-action="anonymous-study"]')?.addEventListener("click", () => {
      open({ id: null, name: "Ca nghiên cứu không định danh" });
    });
    root.querySelectorAll("[data-select]").forEach(element => {
      element.onclick = () => open(patients[Number(element.dataset.select)]);
    });

    const openPatientModal = existingPatient => {
      const editing = Boolean(existingPatient);
      const currentYear = new Date().getFullYear();
      const title = editing ? `Sửa hồ sơ · ${esc(existingPatient.name)}` : "Tạo hồ sơ bệnh nhân";
      modal(title,
        '<p class="small muted">Chỉ lưu họ tên và năm sinh tùy chọn trong danh bạ của cơ sở.</p>' +
        field("Họ và tên", "display_name", "text", existingPatient?.name || "", 'required maxlength="120" autocomplete="name"') +
        `<label class="field">Năm sinh (không bắt buộc)<input name="birth_year" type="number" value="${esc(existingPatient?.birth_year || "")}" min="1900" max="${currentYear}"></label>` +
        '<p class="form-error" data-patient-error role="alert" hidden></p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" type="submit">' + (editing ? "Lưu thay đổi" : "Tạo và tiếp tục") + "</button></div>",
        async (event, dialog) => {
          if (!active()) return dialog.close();
          const data = Object.fromEntries(new FormData(event.target));
          const nameResult = validateFullName(data.display_name);
          const birthYear = String(data.birth_year || "").trim();
          const yearResult = birthYear ? validateBirthYear(birthYear, currentYear) : { valid: true };
          const error = dialog.querySelector("[data-patient-error]");
          if (!nameResult.valid || !yearResult.valid) {
            error.textContent = nameResult.error || yearResult.error;
            error.hidden = false;
            return;
          }
          const submit = dialog.querySelector('button[type="submit"]');
          submit.disabled = true;
          error.hidden = true;
          try {
            const result = await request(editing ? `/api/patient-directory/${encodeURIComponent(existingPatient.id)}` : "/api/patient-directory", {
              method: editing ? "PUT" : "POST",
              body: {
                display_name: String(data.display_name).trim(),
                birth_year: birthYear ? Number(birthYear) : null,
                ...(editing ? { expected_version: existingPatient.version } : {}),
              },
            });
            if (!active()) return dialog.close();
            const patient = { ...result, name: result.display_name };
            dialog.close();
            if (editing) {
              toast("Đã lưu hồ sơ trong danh bạ của cơ sở.");
              await renderList();
            } else {
              toast("Đã tạo hồ sơ trong danh bạ của cơ sở.");
              open(patient);
            }
          } catch (requestError) {
            submit.disabled = false;
            error.textContent = requestError.status === 409
              ? "Hồ sơ đã thay đổi ở phiên khác. Tải lại danh bạ rồi mở lại trước khi sửa."
              : requestError.message;
            error.hidden = false;
          }
        });
      attachInlineValidation(document.querySelector("#modal form"), {
        display_name: value => validateFullName(value),
        birth_year: value => String(value).trim() ? validateBirthYear(value, currentYear) : { valid: true, error: null },
      });
    };

    root.querySelectorAll("[data-edit-patient]").forEach(element => {
      element.onclick = () => {
        const patient = patients.find(row => row.id === element.dataset.editPatient);
        if (patient) openPatientModal(patient);
      };
    });
    root.querySelectorAll("[data-delete-patient]").forEach(element => {
      element.onclick = () => {
        const patient = patients.find(row => row.id === element.dataset.deletePatient);
        if (!patient) return;
        modal("Gỡ hồ sơ khỏi danh bạ",
          `<p>Gỡ <strong>${esc(patient.name)}</strong> khỏi danh bạ của cơ sở?</p><p class="small muted">Các ca đã liên kết vẫn giữ thông tin lịch sử.</p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn danger" type="submit">Gỡ hồ sơ</button></div>`,
          async (_event, dialog) => {
            const submit = dialog.querySelector('button[type="submit"]');
            submit.disabled = true;
            try {
              await request(`/api/patient-directory/${encodeURIComponent(patient.id)}?expected_version=${patient.version}`, { method: "DELETE" });
              dialog.close();
              toast(`Đã gỡ ${patient.name} khỏi danh bạ.`);
              await renderList();
            } catch (error) {
              dialog.close();
              toast(error.status === 409 ? "Hồ sơ đã thay đổi ở phiên khác. Danh bạ đã được tải lại." : error.message, true);
              await renderList();
            }
          });
      };
    });
    root.querySelector("[data-action=add-patient]")?.addEventListener("click", () => openPatientModal(null));
  };

  renderList();
  return () => { clearTimeout(searchTimer); sequence++; cleanupUpload?.(); };
}
function nowLocal() {
  const d = new Date(), two = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}T${two(d.getHours())}:${two(d.getMinutes())}`;
}
function renderUpload(root, patient, onBack) {
  const session = createIntakeSession(() => `${state.user?.id ?? ""}:${state.token ?? ""}`);
  const intakeRequestId = crypto.randomUUID();
  let preparedVisit = null, visitPayload = null, creatingVisit = false;
  const active = () => session.active() && root.isConnected;
  const q = selector => root.querySelector(selector);
  const files = { L: [], R: [] }, unavailableStatus = { L: null, R: null };
  const syntheticDemoMode = state.capabilities?.synthetic_demo_mode === true;
  const urls = new Set();
  let running = false, assigning = false, selecting = 0, selectionOrder = 0;
  const choiceQueue = [];
  let activeChoices = 0;
  const contentDigests = new WeakMap();
  const contentDigest = file => {
    if (!globalThis.crypto?.subtle?.digest) return Promise.resolve(null);
    if (!contentDigests.has(file)) contentDigests.set(file, file.arrayBuffer()
      .then(bytes => crypto.subtle.digest("SHA-256", bytes))
      .then(bytes => Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join(""))
      .catch(() => null));
    return contentDigests.get(file);
  };
  const reasonField = syntheticDemoMode
    ? '<label class="field">Lý do khảo sát<select name="reason" disabled><option>Khác / chưa ghi nhận</option></select></label>'
    : '<label class="field">Lý do khảo sát<select name="reason"><option value="">Chưa ghi nhận</option><option value="Theo dõi hình thái">Theo dõi hình thái</option><option value="Khảo sát định kỳ">Khảo sát định kỳ</option></select></label>';
  const ageField = syntheticDemoMode
    ? ""
    : '<label class="field">Tuổi tại ngày khảo sát (nếu đã xác minh)<input name="patient-age" type="number" min="0" max="120" step="1" inputmode="numeric"><small class="muted">Năm sinh trong danh bạ không được dùng để suy ra tuổi.</small></label>';
  autofillState.reset(); root.classList.add("intake-workspace");
  root.innerHTML = `<div class="intake-identity banner info"><div><strong>${esc(patient.name)}</strong> · ${patient.id && !patient.synthetic ? "Hồ sơ cơ sở" : "Không gắn hồ sơ"} · Visit No <span class="mono" data-visit-no aria-live="polite">Chưa cấp</span> ${button("Tạo Visit", "create-visit", "small")}</div>${button("Chọn bệnh nhân khác", "change-patient", "small")}</div>` +
    pageHead("Khảo sát buồng trứng", "Kiểm tra ngày khảo sát, ảnh và bên. Có thể khảo sát một hoặc hai bên.") +
    `<section class="panel intake-metadata"><div class="panel-body grid-2">
      <label class="field">Ngày giờ khảo sát<div class="intake-date"><input type="datetime-local" name="study-date" value="${nowLocal()}" required>${button("Hiện tại", "set-now", "small")}</div></label>
      ${ageField}
      ${reasonField}
      <div id="metadataProposals" class="intake-metadata-proposals" role="status" aria-live="polite"></div></div></section>
    <details class="intake-privacy"><summary>Thông tin về ảnh DICOM</summary><p class="small muted">Intake không yêu cầu PID nguồn. Máy chủ lọc một số metadata văn bản và thay UID nguồn, nhưng không làm sạch pixel ảnh. Cờ BurnedInAnnotation không xác nhận ảnh sạch; không tải ảnh có chữ định danh. Metadata chỉ là gợi ý và cần được kiểm tra trước khi áp dụng.</p></details>
    <div class="actions intake-swap">${button("Đổi bên ảnh (Trái ⇄ Phải)", "swap-sides", "small", "refresh")}</div>
    <div class="intake-action-bar"><p class="small" id="intakeHint" role="status">Chọn ít nhất một ảnh siêu âm.</p><button type="button" class="btn primary" id="startSegmentationBtn" data-action="start-segmentation" aria-describedby="intakeHint" disabled>${icon("arrow")} Phân tích ảnh AI</button></div>
    <div class="grid-2 intake-images">${["L", "R"].map(side => `<section class="upload-card side-${side}"><h2><span class="badge side-${side}">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái (L)" : "phải (R)"}</h2>
      <div class="dropzone" data-side="${side}">${icon("upload", 24)}<p>Kéo thả ảnh vào bên ${side === "L" ? "trái" : "phải"}</p><small class="muted">Tối đa 20 ảnh · PNG, JPG, JPEG, DICOM · tối đa 20 MB/ảnh</small><label class="btn small">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" multiple class="visually-hidden"></label></div>
      <div id="files-${side}" class="intake-file-list" aria-live="polite"><p class="small muted">Chưa chọn ảnh</p></div>
      <label class="intake-side-unavailable"><input type="checkbox" data-unavailable="${side}"> Đã phẫu thuật cắt bỏ / Không khảo sát được</label>
      <label class="field small" data-unavailable-wrap="${side}" hidden><span>Tình trạng bên không có ảnh</span><select data-unavailable-status="${side}" disabled><option value="">Chọn tình trạng</option><option value="SURGICALLY_ABSENT">Đã phẫu thuật cắt bỏ</option><option value="NOT_VISUALIZED">Không quan sát được</option></select></label>
      <progress id="progress-${side}" max="100" value="0" aria-label="Tiến trình tải ảnh ${side}"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p></section>`).join("")}</div>
    <div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div>
    <div id="intakeError" role="alert"></div><div class="actions intake-recovery">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}</div>`;
  const hasImages = () => ["L", "R"].some(side => files[side].length > 0);
  const sideIsConfirmed = side => files[side].length > 0
    ? files[side].every(entry => entry.confirmed)
    : ["SURGICALLY_ABSENT", "NOT_VISUALIZED"].includes(unavailableStatus[side]);
  const ready = () => active() && !state.busy && !creatingVisit && !(visitPayload && !preparedVisit) && !running && !assigning && !selecting && hasImages() && ["L", "R"].every(sideIsConfirmed) && q("[name=study-date]").validity.valid && q("[name=study-date]").value && (!q("[name=patient-age]") || q("[name=patient-age]").validity.valid);
  const updateStatus = () => {
    if (!active()) return;
    const visitButton = q("[data-action=create-visit]");
    visitButton.hidden = Boolean(preparedVisit) || q(".dropzone")?.dataset.uploadLocked === "true";
    visitButton.disabled = creatingVisit || running || Boolean(state.busy) || !q("[name=study-date]").value || !q("[name=study-date]").validity.valid || (q("[name=patient-age]") && !q("[name=patient-age]").validity.valid);
    visitButton.textContent = creatingVisit ? "Đang tạo…" : visitPayload ? "Thử lại tạo Visit" : "Tạo Visit";
    visitButton.setAttribute("aria-busy", String(creatingVisit));
    const imageSides = ["L", "R"].filter(side => files[side].length > 0);
    const imageCount = imageSides.reduce((total, side) => total + files[side].length, 0);
    const unconfirmedSide = imageSides.find(side => files[side].some(entry => !entry.confirmed));
    const unreportedSide = ["L", "R"].find(side => !sideIsConfirmed(side));
    const missingSide = imageSides.length === 1 ? (imageSides[0] === "L" ? "R" : "L") : null;
    const unavailableLabel = unavailableStatus[missingSide] === "SURGICALLY_ABSENT" ? "đã phẫu thuật cắt bỏ" : "không quan sát được";
    const readyMessage = imageSides.length === 1
      ? `${imageCount} ảnh đã xác nhận bên. Khảo sát một bên; bên ${missingSide === "L" ? "trái" : "phải"} được ghi nhận ${unavailableLabel}. Sẵn sàng phân đoạn từng ảnh.`
      : `${imageCount} ảnh đã xác nhận bên. Sẵn sàng phân đoạn từng ảnh.`;
    q("#startSegmentationBtn").disabled = !ready();
    q("#startSegmentationBtn").innerHTML = running ? "Đang phân tích ảnh…" : `${icon("arrow")} Phân tích ảnh AI`;
    q("#startSegmentationBtn").setAttribute("aria-busy", String(running));
    q("#intakeHint").textContent = running ? "Đang xử lý; có thể dừng chờ phản hồi." : selecting ? "Đang kiểm tra ảnh…" : !imageSides.length ? "Chọn ít nhất một ảnh siêu âm." : unconfirmedSide ? `Có ảnh bên ${unconfirmedSide === "L" ? "trái" : "phải"} chưa xác nhận. Kiểm tra từng ảnh.` : unreportedSide ? "Ghi nhận bên không có ảnh và chọn đúng tình trạng trước khi tiếp tục." : !q("[name=study-date]").value || !q("[name=study-date]").validity.valid ? "Chọn ngày giờ khảo sát hợp lệ." : readyMessage;
    q("[data-action=retry-upload]").disabled = !ready();
    q("[data-action=swap-sides]").disabled = running || Boolean(state.busy) || Boolean(selecting);
    q("[data-action=change-patient]").disabled = creatingVisit || running || Boolean(state.busy);
    const imageListLocked = q(".dropzone")?.dataset.uploadLocked === "true";
    root.querySelectorAll("[data-file], [data-confirm-file], [data-remove-file], [data-unavailable]").forEach(input => { input.disabled = running || assigning || Boolean(state.busy) || (imageListLocked && (input.matches("[data-file], [data-remove-file], [data-unavailable]"))); });
    for (const side of ["L", "R"]) {
      const checkbox = q(`[data-unavailable="${side}"]`);
      const select = q(`[data-unavailable-status="${side}"]`);
      const wrapper = q(`[data-unavailable-wrap="${side}"]`);
      checkbox.checked = Boolean(unavailableStatus[side]) || (checkbox.checked && !select.value);
      checkbox.disabled = running || assigning || Boolean(state.busy) || files[side].length > 0;
      wrapper.hidden = !checkbox.checked;
      select.disabled = running || Boolean(state.busy) || !checkbox.checked || files[side].length > 0;
    }
    root.querySelectorAll('[name=study-date], [name=patient-age], [name=reason], [data-action=set-now]').forEach(input => {
      const syntheticReasonLocked = syntheticDemoMode && input.name === "reason";
      input.disabled = Boolean(visitPayload) || running || Boolean(state.busy) || syntheticReasonLocked;
    });
  };
  const renderProposals = () => {
    if (!active()) return;
    const target = q("#metadataProposals"); target.replaceChildren();
    const pendingActions = [];
    for (const side of ["L", "R"]) for (const image of files[side]) {
      const proposal = image.proposal;
      if (!proposal) continue;
      for (const [key, label, name] of [["study_date", "Ngày DICOM", "study-date"]]) {
        const candidate = proposal[key];
        if (!candidate?.value || candidate.source !== "dicom" || String(candidate.value) === q(`[name=${name}]`).value) continue;
        const row = document.createElement("div"), caption = document.createElement("span"), apply = document.createElement("button");
        row.className = "small"; caption.textContent = `${label} (${side}, ${image.file.name}): ${candidate.value} `;
        apply.type = "button"; apply.className = "btn small"; apply.textContent = "Áp dụng";
        const doApply = () => {
          if (!active() || !image.selection.current() || state.busy || running) return;
          const input = q(`[name=${name}]`); if (input.disabled || input.readOnly) return;
          const value = String(candidate.value).trim();
          const previous = input.value;
          input.value = value;
          if (!input.value || !input.validity.valid) {
            input.value = previous;
            return toast("Gợi ý metadata không đúng định dạng trường. Kiểm tra nguồn trước khi nhập.", true);
          }
          const fieldName = "studyDate";
          autofillState.set(fieldName, input.value, "dicom", candidate.confidence); autofillState.confirm(fieldName);
          renderProposals(); updateStatus();
        };
        apply.onclick = doApply;
        pendingActions.push(doApply);
        row.append(caption, apply); target.append(row);
      }
    }
    if (pendingActions.length >= 2) {
      const bulkRow = document.createElement("div");
      bulkRow.className = "proposals-bulk-action small";
      bulkRow.style.marginTop = "6px";
      const bulkBtn = document.createElement("button");
      bulkBtn.type = "button";
      bulkBtn.className = "btn small primary";
      bulkBtn.textContent = "Áp dụng tất cả gợi ý DICOM";
      bulkBtn.onclick = () => {
        if (!active() || state.busy || running) return;
        for (const action of [...pendingActions]) action();
      };
      bulkRow.append(bulkBtn);
      target.append(bulkRow);
    }
  };
  const renderFiles = side => {
    const target = q(`#files-${side}`);
    target.replaceChildren();
    if (!files[side].length) {
      const empty = document.createElement("p"); empty.className = "small muted"; empty.textContent = "Chưa chọn ảnh"; target.append(empty); return;
    }
    files[side].forEach((image, index) => {
      const row = document.createElement("article"); row.className = "intake-file-item";
      if (image.url) { const preview = document.createElement("img"); preview.src = image.url; preview.alt = `Ảnh ${index + 1}, buồng trứng ${side === "L" ? "trái" : "phải"}`; row.append(preview); }
      const details = document.createElement("div"); details.className = "intake-file-details";
      const name = document.createElement("strong"); name.textContent = image.file.name;
      const size = document.createElement("small"); size.className = "muted"; size.textContent = `${Math.max(1, Math.round(image.file.size / 1024))} KB · ${image.dicom?.label || "Ảnh tĩnh"}`;
      const confirmLabel = document.createElement("label"); confirmLabel.className = "intake-side-confirm";
      const confirm = document.createElement("input"); confirm.type = "checkbox"; confirm.checked = image.confirmed; confirm.disabled = running || assigning || Boolean(state.busy); confirm.dataset.confirmFile = image.id;
      const confirmText = document.createElement("span"); confirmText.textContent = `Xác nhận ảnh này thuộc bên ${side === "L" ? "trái" : "phải"}`;
      confirmLabel.append(confirm, confirmText);
      const hint = document.createElement("small"); hint.className = image.confirmed ? "muted" : "form-error"; hint.textContent = image.hint;
      const removeButton = document.createElement("button"); removeButton.type = "button"; removeButton.className = "btn small quiet"; removeButton.textContent = "Bỏ ảnh"; removeButton.dataset.removeFile = image.id; removeButton.disabled = running || assigning || Boolean(state.busy);
      details.append(name, size, confirmLabel, hint, removeButton); row.append(details); target.append(row);
    });
  };
  const remove = (side, image) => {
    image.controller.abort();
    if (image.url) { URL.revokeObjectURL(image.url); urls.delete(image.url); }
    files[side] = files[side].filter(item => item !== image);
    if (!files[side].length) {
      q(`#stage-${side}`).textContent = "Chờ ảnh"; q(`#progress-${side}`).value = 0;
    }
    renderFiles(side); q(`[data-file=${side}]`).value = ""; q("#intakeError").replaceChildren();
    renderProposals(); updateStatus();
  };
  const metadata = async (side, image) => {
    if (syntheticDemoMode || state.capabilities.feature_autofill === false) return;
    try {
      const form = new FormData(); form.append("file", image.file);
      const data = await request("/api/intake/extract-metadata", { method: "POST", body: form, signal: image.selection.signal, timeoutMs: 12000 });
      if (!image.selection.current() || !active()) return;
      image.proposal = data.metadata;
      const sourceSide = data.metadata?.laterality?.value;
      if ((sourceSide === "L" || sourceSide === "R") && sourceSide !== side && data.metadata.laterality.source === "dicom") {
        image.confirmed = false;
        image.hint = `DICOM gợi ý bên ${sourceSide}, khác bên ${side}. Kiểm tra ảnh và xác nhận.`;
      }
      renderFiles(side); renderProposals(); updateStatus();
    } catch (error) {
      if (error.name !== "AbortError" && image.selection.current() && active()) {
        image.hint = "Không lấy được gợi ý metadata; kiểm tra ảnh và xác nhận bên."; image.confirmed = false;
        renderFiles(side); updateStatus();
      }
    }
  };
  const processChoice = async (side, file, needsConfirmation = false) => {
    if (!active() || state.busy || running || !file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["png", "jpg", "jpeg", "dcm"].includes(ext) || file.size > 20 * 1024 * 1024 || !file.size) return toast("Ảnh cần đúng định dạng và không vượt quá 20 MB.", true);
    if (files[side].length >= 20) return toast(`Mỗi bên chỉ nhận tối đa 20 ảnh.`, true);
    const image = { id: crypto.randomUUID(), file, selectionOrder: selectionOrder++, confirmed: false, hint: "Đang kiểm tra ảnh…", dicom: null, proposal: null, url: null, contentSha256: null, controller: new AbortController() };
    image.side = side;
    image.selection = { signal: image.controller.signal, current: () => active() && files[image.side].includes(image) && !image.controller.signal.aborted };
    files[side].push(image); selecting++; renderFiles(side); updateStatus();
    try {
      const fingerprint = await contentDigest(file);
      if (fingerprint) {
        image.contentSha256 = fingerprint;
        const earlierCandidates = ["L", "R"].flatMap(candidateSide => files[candidateSide])
          .filter(candidate => candidate !== image && candidate.selectionOrder < image.selectionOrder && candidate.file.size === file.size);
        for (const candidate of earlierCandidates) {
          if (!candidate.selection.current()) continue;
          const candidateFingerprint = candidate.contentSha256 || await contentDigest(candidate.file);
          if (image.selection.current() && candidate.selection.current() && candidateFingerprint === fingerprint) {
            remove(side, image);
            toast("Ảnh có cùng nội dung đã được thêm vào ca khảo sát.", true);
            return;
          }
        }
      }
      if (!image.selection.current() || !active()) return;
      if (ext === "dcm") {
        const info = await inspectDicom(file, side); if (!image.selection.current() || !active()) return; image.dicom = info;
      } else {
        const bitmap = await createImageBitmap(file); bitmap.close(); if (!image.selection.current() || !active()) return;
        image.url = URL.createObjectURL(file); urls.add(image.url);
      }
      const hint = getLateralityHint(file.name, side);
      image.confirmed = !needsConfirmation && !hint?.mismatch;
      image.hint = hint?.message || (needsConfirmation ? "Không có cặp gợi ý L/R duy nhất. Kiểm tra và xác nhận bên đã chọn." : "Bên được chọn trong thẻ ảnh; tên tệp chỉ là gợi ý.");
      unavailableStatus[side] = null;
      q(`[data-unavailable="${side}"]`).checked = false;
      q(`[data-unavailable-status="${side}"]`).value = "";
      q(`[data-unavailable-wrap="${side}"]`).hidden = true;
      q(`#stage-${side}`).textContent = "Ảnh sẵn sàng"; renderFiles(side);
      await metadata(side, image);
    } catch (error) {
      if (image.selection.current() && active()) {
        remove(side, image);
        toast(ext === "dcm" ? error.message : "Không giải mã được ảnh.", true);
      }
    } finally { selecting--; updateStatus(); }
  };
  const pumpChoiceQueue = () => {
    while (activeChoices < 2 && choiceQueue.length) {
      const job = choiceQueue.shift();
      activeChoices++;
      processChoice(job.side, job.file, job.needsConfirmation)
        .catch(error => {
          if (active() && error?.name !== "AbortError")
            toast("Không thể kiểm tra ảnh đã chọn. Thử lại hoặc chọn tệp khác.", true);
        })
        .finally(() => {
          activeChoices--;
          job.resolve();
          pumpChoiceQueue();
        });
    }
  };
  const choose = (side, file, needsConfirmation = false) => new Promise(resolve => {
    choiceQueue.push({ side, file, needsConfirmation, resolve });
    pumpChoiceQueue();
  });
  q("[data-action=create-visit]").onclick = async () => {
    if (creatingVisit || preparedVisit || state.busy || !q("[name=study-date]").reportValidity()) return;
    visitPayload ??= {
      patient_directory_id: !syntheticDemoMode && patient.id ? patient.id : null,
      patient_age: q("[name=patient-age]")?.value ? q("[name=patient-age]").value : null,
      study_date: q("[name=study-date]").value,
      clinical_notes: syntheticDemoMode ? null : (q("[name=reason]").value || null),
      active_ovary_side: "UNKNOWN", contralateral_status: "UNKNOWN",
    };
    creatingVisit = true; updateStatus();
    try {
      const result = await request("/api/cases", {
        method: "POST", body: visitPayload, headers: { "Idempotency-Key": intakeRequestId },
      });
      if (!active()) return;
      preparedVisit = result;
      q("[data-visit-no]").textContent = result.visit_no;
      toast(`Đã tạo Visit ${result.visit_no}. Chọn ảnh để tiếp tục khảo sát.`);
    } catch (error) {
      if ([400, 403, 422].includes(error.status)) visitPayload = null;
      if (active() && error?.name !== "AbortError") toast(
        !error.status || error.status === 408
          ? "Chưa nhận được phản hồi. Bấm thử lại tạo Visit để tiếp tục cùng lượt khảo sát."
          : error.message, true);
    } finally { creatingVisit = false; updateStatus(); }
  };
  const run = async () => {
    if (!ready()) return toast("Kiểm tra đủ ảnh, ngày khảo sát và xác nhận bên trước khi chạy.", true);
    running = true; updateStatus();
    const activeSide = files.L.length && files.R.length ? "BOTH" : files.L.length ? "LEFT" : "RIGHT";
    const missingSide = files.L.length ? "R" : "L";
    try {
      await startBilateral(files, {
        patient_directory_id: !syntheticDemoMode && patient.id ? patient.id : null,
        patient_age: q("[name=patient-age]")?.value || null,
        reason: q("[name=reason]").value,
        idempotency_key: intakeRequestId,
        prepared_case: preparedVisit,
        active_ovary_side: activeSide,
        contralateral_status: files.L.length && files.R.length ? "UNKNOWN" : unavailableStatus[missingSide],
        study_date: q("[name=study-date]").value, participant_code: state.user.username,
        participant_role: state.capabilities?.synthetic_demo_mode === true ? "technical_tester" : "clinician",
        data_origin: state.capabilities?.synthetic_demo_mode === true ? "demo" : "live",
        onRetry: run, isCurrent: active });
    } finally { running = false; updateStatus(); }
  };
  for (const side of ["L", "R"]) {
    q(`[data-file=${side}]`).onchange = async event => {
      if (assigning) return;
      const selected = Array.from(event.target.files || []); event.target.value = "";
      await Promise.all(selected.map(file => choose(side, file)));
    };
    q(`#files-${side}`).addEventListener("change", event => {
      const confirm = event.target.closest("[data-confirm-file]");
      if (!confirm || state.busy || running) return;
      const image = files[side].find(item => item.id === confirm.dataset.confirmFile);
      if (!image) return;
      image.confirmed = confirm.checked;
      image.hint = confirm.checked
        ? `Bác sĩ xác nhận ảnh này thuộc bên ${side === "L" ? "trái" : "phải"}. Metadata chỉ là gợi ý.`
        : "Cần kiểm tra ảnh và xác nhận bên trước khi tiếp tục.";
      renderFiles(side); updateStatus();
    });
    q(`#files-${side}`).addEventListener("click", event => {
      const removeButton = event.target.closest("[data-remove-file]");
      if (!removeButton || state.busy || running) return;
      const image = files[side].find(item => item.id === removeButton.dataset.removeFile);
      if (image) remove(side, image);
    });
    q(`[data-unavailable=${side}]`).onchange = event => {
      if (state.busy || running || files[side].length) { event.target.checked = !event.target.checked; return; }
      const wrapper = q(`[data-unavailable-wrap="${side}"]`);
      const select = q(`[data-unavailable-status="${side}"]`);
      if (!event.target.checked) {
        unavailableStatus[side] = null;
        select.value = "";
      }
      wrapper.hidden = !event.target.checked;
      select.disabled = !event.target.checked;
      updateStatus();
    };
    q(`[data-unavailable-status=${side}]`).onchange = event => {
      if (state.busy || running || files[side].length) return;
      unavailableStatus[side] = ["SURGICALLY_ABSENT", "NOT_VISUALIZED"].includes(event.target.value) ? event.target.value : null;
      updateStatus();
    };
    const zone = q(`[data-side=${side}]`);
    zone.ondragover = event => { event.preventDefault(); zone.classList.add("drag"); }; zone.ondragleave = () => zone.classList.remove("drag");
    zone.ondrop = async event => {
      event.preventDefault(); zone.classList.remove("drag"); if (running || assigning || state.busy || selecting) return;
      const dropped = Array.from(event.dataTransfer.files);
      if (!dropped.length) return;
      if (dropped.length === 2 && !files.L.length && !files.R.length) {
        const plan = planBilateralDrop(dropped, suggestLaterality);
        assigning = true; updateStatus();
        try { await Promise.all(plan.map(item => choose(item.side, item.file, item.needsConfirmation))); }
        finally { assigning = false; updateStatus(); }
        if (active()) toast(plan.some(item => item.needsConfirmation) ? "Kiểm tra từng ảnh và xác nhận bên trước khi phân đoạn." : "Kiểm tra đề xuất phân bổ theo tên tệp trước khi phân đoạn.");
        return;
      }
      if (files[side].length + dropped.length > 20) return toast("Mỗi bên chỉ nhận tối đa 20 ảnh.", true);
      assigning = true; updateStatus();
      try { await Promise.all(dropped.map(file => choose(side, file))); }
      finally { assigning = false; updateStatus(); }
    };
  }
  q("[data-action=swap-sides]").onclick = async () => {
    if (state.busy || running || selecting) return;
    if (q(".dropzone")?.dataset.uploadLocked === "true") return toast("Ca đã được tạo trên máy chủ; không thể đổi bên ảnh. Hãy tạo ca mới.", true);
    const oldLeft = files.L, oldRight = files.R;
    const oldUnavailable = { ...unavailableStatus };
    files.L = oldRight; files.R = oldLeft;
    unavailableStatus.L = oldUnavailable.R; unavailableStatus.R = oldUnavailable.L;
    q('[data-unavailable-status="L"]').value = unavailableStatus.L || "";
    q('[data-unavailable-status="R"]').value = unavailableStatus.R || "";
    assigning = true;
    for (const image of files.L) { image.side = "L"; image.confirmed = false; image.hint = "Đã đổi bên; xác nhận lại."; }
    for (const image of files.R) { image.side = "R"; image.confirmed = false; image.hint = "Đã đổi bên; xác nhận lại."; }
    renderFiles("L"); renderFiles("R"); updateStatus();
    try { }
    finally { assigning = false; updateStatus(); }
    if (active()) toast("Đã đổi bên cho toàn bộ ảnh. Xác nhận lại từng ảnh trước khi phân đoạn.");
  };
  q("[name=patient-age]")?.addEventListener("input", updateStatus);
  q("[name=study-date]").addEventListener("input", () => {
    autofillState.set("studyDate", q("[name=study-date]").value, "manual"); renderProposals(); updateStatus();
  });
  q("[data-action=set-now]").onclick = () => {
    if (state.busy || running) return; q("[name=study-date]").value = nowLocal();
    autofillState.set("studyDate", q("[name=study-date]").value, "manual"); renderProposals(); updateStatus();
  };
  q("[data-action=change-patient]").onclick = () => { if (!running && !state.busy) onBack(); };
  q("[data-action=start-segmentation]").onclick = run; q("[data-action=retry-upload]").onclick = run;
  q("[data-action=cancel-upload]").onclick = () => state.controller?.abort(); updateStatus();
  return () => { session.dispose(); state.controller?.abort(); for (const side of ["L", "R"]) for (const image of files[side]) image.controller.abort(); for (const url of urls) URL.revokeObjectURL(url); root.classList.remove("intake-workspace"); };
}
