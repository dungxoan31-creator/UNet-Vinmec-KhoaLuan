import { inspectDicom } from "./dicom-inspect.js";
import { getLateralityHint, suggestLaterality } from "./laterality-hint.js";
import { createIntakeSession, createDemoPatientStore, planBilateralDrop } from "./intake-session.js";
import { autofillState, state } from "./state.js";
import { esc, button, field, modal, pageHead, icon, toast } from "./ui.js";
import { startBilateral } from "./upload.js";
import { request } from "./api.js";
import { DEMO_PATIENTS, patientSearchKey } from "./demo-patients.js";
import {
  validatePid,
  validateFullName,
  validateBirthYear,
  validatePhone,
  validateGender,
  validateHometown,
  validateStudyDate,
  attachInlineValidation,
} from "./form-validator.js";

const patientsKey = () => `ova.demo-patients.v1.${encodeURIComponent(state.user?.id ?? "anonymous")}`;
const patientsStore = createDemoPatientStore([
  { pid: "100000001", name: "Nguyễn Minh Anh", age: 32 },
  { pid: "100000002", name: "Trần Thu Hà", age: 41 },
  { pid: "100000003", name: "Lê Ngọc Mai", age: 28 },
  { pid: "100000004", name: "Phạm Thanh Vy", age: 36 },
]);
const readPatients = () => {
  const legacySeeds = new Map([['100000001', 'Nguyễn Minh Anh'], ['100000002', 'Trần Thu Hà'], ['100000003', 'Lê Ngọc Mai'], ['100000004', 'Phạm Thanh Vy']]);
  const rows = patientsStore.read(patientsKey()).map(row => /^DEMO-SYNTHETIC-\d{4}$/.test(row.pid)
    ? { ...row, pid: String(900000000 + Number(row.pid.slice(-4))), synthetic: true }
    : { ...row, synthetic: row.synthetic === true || legacySeeds.get(row.pid) === row.name || DEMO_PATIENTS.some(seed => seed.pid === row.pid && seed.name === row.name) });
  const ids = new Set(rows.map(row => row.pid));
  const syntheticMode = state.capabilities?.synthetic_demo_mode === true;
  const additions = syntheticMode ? DEMO_PATIENTS.filter(row => !ids.has(row.pid)) : [];
  return patientsStore.save(patientsKey(), [...rows, ...additions]).filter(row => row.synthetic === syntheticMode);
};
const storageNotice = () => patientsStore.isTransient(patientsKey())
  ? '<div class="banner warning" role="status">Không ghi được danh sách bệnh nhân trên thiết bị. Dữ liệu mới chỉ giữ trong phiên này; tải lại trang có thể làm mất dữ liệu chưa lưu.</div>' : "";
export function renderIntake(root) {
  let cleanupUpload;
  let search = '', page = 0;
  const pageSize = 20;
  const identity = state.user?.id;
  const active = () => root.isConnected && identity === state.user?.id;
  const renderList = () => {
    cleanupUpload?.(); cleanupUpload = null;
    if (!active()) return;
    const allPatients = readPatients();
    const filtered = allPatients.filter(p => patientSearchKey(`${p.pid} ${p.name}`).includes(patientSearchKey(search.trim())));
    const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.min(page, pageCount - 1);
    const patients = filtered.slice(page * pageSize, (page + 1) * pageSize);
    root.innerHTML = pageHead("Chọn bệnh nhân", "Chọn hồ sơ bệnh nhân để bắt đầu khảo sát.", button("Tạo bệnh nhân", "add-patient", "primary", "plus")) + storageNotice() +
      `<section class="panel"><div class="panel-head"><h2>Danh sách bệnh nhân</h2><span class="badge">${patients.length} hồ sơ</span></div><div class="table-wrap intake-patient-list" role="region" aria-label="Danh sách bệnh nhân" tabindex="0"><table><thead><tr><th>Mã bệnh nhân (PID)</th><th>Bệnh nhân</th><th>Tuổi</th><th>Thao tác</th></tr></thead><tbody>${patients.map((p, i) => `<tr><td class="mono">${esc(p.pid)}</td><td><strong>${esc(p.name)}</strong></td><td>${p.age} tuổi</td><td><div class="table-actions-compact"><button class="btn small primary" type="button" data-select="${i}">Chọn bệnh nhân</button><button class="btn small icon-only" type="button" data-edit-patient="${esc(p.pid)}" title="Sửa thông tin bệnh nhân" aria-label="Sửa thông tin ${esc(p.name)}">${icon("edit", 16)}</button><button class="btn small danger icon-only" type="button" data-delete-patient="${esc(p.pid)}" title="Xóa bệnh nhân" aria-label="Xóa hồ sơ ${esc(p.name)}">${icon("trash", 16)}</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
    const table = root.querySelector('.intake-patient-list');
    table.insertAdjacentHTML('beforebegin', `${state.capabilities?.synthetic_demo_mode === true ? '<div class="banner info small">Dữ liệu tổng hợp, không phải hồ sơ bệnh nhân thật.</div>' : ''}<label class="field">Tìm theo tên hoặc mã hồ sơ<input id="patientSearch" type="search" placeholder="Nhập tên có dấu hoặc không dấu" value="${esc(search)}"></label>`);
    root.querySelector('.panel .badge').textContent = `${filtered.length} / ${allPatients.length} hồ sơ`;
    table.insertAdjacentHTML('afterend', `<div class="actions"><button type="button" class="btn small" id="patientPrev" ${page === 0 ? 'disabled' : ''}>Trang trước</button><span role="status">Trang ${page + 1} / ${pageCount}</span><button type="button" class="btn small" id="patientNext" ${page + 1 >= pageCount ? 'disabled' : ''}>Trang sau</button></div>`);
    if (!patients.length) table.insertAdjacentHTML('afterbegin', '<p class="muted">Không tìm thấy hồ sơ phù hợp.</p>');
    root.querySelector('#patientSearch').oninput = event => {
      search = event.target.value; page = 0;
      renderList();
      root.querySelector('#patientSearch').focus();
    };
    root.querySelector('#patientPrev').onclick = () => { page--; renderList(); };
    root.querySelector('#patientNext').onclick = () => { page++; renderList(); };
    const open = patient => {
      if (!active()) return;
      cleanupUpload?.(); cleanupUpload = renderUpload(root, patient, renderList);
    };
    root.querySelectorAll("[data-select]").forEach(el => { el.onclick = () => open(patients[Number(el.dataset.select)]); });
    const openPatientModal = (existingPatient = null) => {
      const isEditing = Boolean(existingPatient);
      const currentYear = new Date().getFullYear();
      const currentPid = existingPatient?.pid || "";
      const currentList = readPatients();
      const existingPids = currentList.map(p => p.pid);

      const initialBirthYear = existingPatient?.birth_year ?? (existingPatient?.age ? currentYear - existingPatient.age : "");
      const initialAgeText = initialBirthYear ? `(${currentYear - Number(initialBirthYear)} tuổi)` : "";
      const title = isEditing ? `Sửa hồ sơ bệnh nhân · ${esc(existingPatient.name)}` : "Tạo hồ sơ bệnh nhân";
      const submitText = isEditing ? "Lưu thay đổi" : "Tạo và tiếp tục";

      modal(title,
        `<p class="small muted">${isEditing ? "Cập nhật thông tin bệnh nhân để khảo sát." : "Nhập thông tin bệnh nhân để phục vụ khảo sát siêu âm."}</p>` +
        field("Mã bệnh nhân (PID) · 9 chữ số", "pid", "text", currentPid, 'required pattern="[0-9]{9}" minlength="9" maxlength="9" inputmode="numeric"' + (isEditing ? ' readonly title="PID không thể thay đổi sau khi tạo"' : "")) +
        field("Họ và tên", "full_name", "text", existingPatient?.name || "", 'required maxlength="120"') +
        `<label class="field"><span>Năm sinh <span class="age-badge-preview" id="agePreview">${initialAgeText}</span></span><input name="birth_year" type="number" value="${esc(initialBirthYear)}" required min="1900" max="${currentYear}"></label>` +
        field("Số điện thoại", "phone", "tel", existingPatient?.phone || "", 'required maxlength="24"') +
        `<label class="field">Giới tính<select name="gender" required>
          <option value="">Chọn giới tính</option>
          <option value="female"${existingPatient?.gender === "female" ? " selected" : ""}>Nữ</option>
          <option value="male"${existingPatient?.gender === "male" ? " selected" : ""}>Nam</option>
          <option value="other"${existingPatient?.gender === "other" ? " selected" : ""}>Khác</option>
          <option value="unknown"${existingPatient?.gender === "unknown" ? " selected" : ""}>Không muốn nêu</option>
        </select></label>` +
        field("Quê quán", "hometown", "text", existingPatient?.hometown || "", 'required maxlength="120"') +
        '<p class="form-error" data-patient-error role="alert" hidden></p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" type="submit">' + submitText + '</button></div>',
        (event, dialog) => {
          if (!active()) return dialog.close();
          const data = Object.fromEntries(new FormData(event.target));
          const pidVal = validatePid(data.pid, { existingPids, currentPid: isEditing ? currentPid : null });
          const nameVal = validateFullName(data.full_name);
          const yearVal = validateBirthYear(data.birth_year, currentYear);
          const phoneVal = validatePhone(data.phone);
          const genderVal = validateGender(data.gender);
          const hometownVal = validateHometown(data.hometown);

          const error = dialog.querySelector("[data-patient-error]");
          if (!pidVal.valid || !nameVal.valid || !yearVal.valid || !phoneVal.valid || !genderVal.valid || !hometownVal.valid) {
            error.textContent = pidVal.error || nameVal.error || yearVal.error || phoneVal.error || genderVal.error || hometownVal.error;
            error.hidden = false;
            return;
          }

          const patient = {
            pid: String(data.pid).trim(),
            synthetic: isEditing ? existingPatient.synthetic : (state.capabilities?.synthetic_demo_mode === true),
            name: String(data.full_name).trim(),
            age: yearVal.age,
            birth_year: Number(data.birth_year),
            phone: phoneVal.cleanPhone,
            gender: data.gender,
            hometown: String(data.hometown).trim(),
          };

          if (isEditing) {
            patientsStore.update(patientsKey(), currentPid, patient);
            toast("Đã cập nhật thông tin bệnh nhân.");
            dialog.close();
            renderList();
          } else {
            patientsStore.add(patientsKey(), patient);
            toast("Đã tạo hồ sơ bệnh nhân.");
            dialog.close();
            open(patient);
          }
        });

      const d = document.querySelector("#modal");
      if (d) {
        const birthYearInput = d.querySelector('[name="birth_year"]');
        const agePreview = d.querySelector("#agePreview");
        if (birthYearInput && agePreview) {
          birthYearInput.addEventListener("input", () => {
            const res = validateBirthYear(birthYearInput.value, currentYear);
            agePreview.textContent = res.valid ? `(${res.age} tuổi)` : "";
          });
        }
        attachInlineValidation(d.querySelector("form"), {
          pid: val => validatePid(val, { existingPids, currentPid: isEditing ? currentPid : null }),
          full_name: val => validateFullName(val),
          birth_year: val => validateBirthYear(val, currentYear),
          phone: val => validatePhone(val),
          gender: val => validateGender(val),
          hometown: val => validateHometown(val),
        });
      }
    };

    root.querySelectorAll("[data-edit-patient]").forEach(el => {
      el.onclick = () => {
        const pidToEdit = el.dataset.editPatient;
        const patientToEdit = readPatients().find(p => p.pid === pidToEdit);
        if (patientToEdit) openPatientModal(patientToEdit);
      };
    });

    root.querySelectorAll("[data-delete-patient]").forEach(el => {
      el.onclick = () => {
        const pidToDelete = el.dataset.deletePatient;
        const patientToDelete = readPatients().find(p => p.pid === pidToDelete);
        if (!patientToDelete) return;
        modal(
          "Xác nhận xóa hồ sơ bệnh nhân",
          `<p>Bạn có chắc chắn muốn xóa hồ sơ bệnh nhân <strong>${esc(patientToDelete.name)}</strong> (PID: <span class="mono">${esc(patientToDelete.pid)}</span>)?</p>
           <p class="small muted">Hành động này sẽ gỡ hồ sơ khỏi danh sách khảo sát.</p>
           <div class="actions">
             <button class="btn" value="cancel">Hủy</button>
             <button class="btn danger" type="submit">Xác nhận xóa</button>
           </div>`,
          (event, dialog) => {
            patientsStore.remove(patientsKey(), pidToDelete);
            toast(`Đã xóa hồ sơ bệnh nhân ${patientToDelete.name}.`);
            dialog.close();
            renderList();
          }
        );
      };
    });

    root.querySelector("[data-action=add-patient]").onclick = () => openPatientModal();
  };
  renderList();
  return () => cleanupUpload?.();
}
function nowLocal() {
  const d = new Date(), two = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}T${two(d.getHours())}:${two(d.getMinutes())}`;
}
function renderUpload(root, patient, onBack) {
  const session = createIntakeSession(() => `${state.user?.id ?? ""}:${state.token ?? ""}`);
  const intakeRequestId = crypto.randomUUID();
  const active = () => session.active() && root.isConnected;
  const q = selector => root.querySelector(selector);
  const files = { L: [], R: [] }, unavailableStatus = { L: null, R: null };
  const syntheticDemoMode = state.capabilities?.synthetic_demo_mode === true;
  const validPid = () => /^[0-9]{9}$/.test(q("[name=pid]").value);
  const validSyntheticDemoPid = () => validPid() && Number(q("[name=pid]").value) >= 900000001 && Number(q("[name=pid]").value) <= 900000300;
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
  const pidField = syntheticDemoMode
    ? field("Mã bệnh nhân (PID)", "pid", "text", patient.synthetic ? patient.pid : "", 'placeholder="900000001" inputmode="numeric" minlength="9" maxlength="9" required pattern="[0-9]{9}"')
    : field("Mã bệnh nhân (PID)", "pid", "text", patient.pid || "", 'placeholder="Để trống cho ca nghiên cứu không định danh" inputmode="numeric" minlength="9" maxlength="9" required pattern="[0-9]{9}"');
  const reasonField = syntheticDemoMode
    ? '<label class="field">Lý do khảo sát<select name="reason"><option>Khác / chưa ghi nhận</option><option>Theo dõi hình thái</option><option>Khảo sát định kỳ</option></select></label>'
    : '<label class="field">Lý do khảo sát<select name="reason"><option>Khác / chưa ghi nhận</option><option>Theo dõi hình thái</option><option>Khảo sát định kỳ</option></select></label>';
  autofillState.reset(); root.classList.add("intake-workspace");
  root.innerHTML = `<div class="intake-identity banner info"><div><strong>${esc(patient.name)}</strong> · PID: <span class="mono">${esc(patient.pid || "Chưa cấp")}</span> · Visit No <span class="mono" data-visit-no>Chưa cấp</span></div>${button("Chọn bệnh nhân khác", "change-patient", "small")}</div>` +
    pageHead("Khảo sát buồng trứng", "Kiểm tra mã ca, ảnh và bên. Có thể khảo sát một hoặc hai bên.") + storageNotice() +
    `<section class="panel intake-metadata"><div class="panel-body grid-2">${pidField}
      <label class="field">Ngày giờ khảo sát<div class="intake-date"><input type="datetime-local" name="study-date" value="${nowLocal()}" required>${button("Hiện tại", "set-now", "small")}</div></label>
      ${reasonField}
      <div id="metadataProposals" class="intake-metadata-proposals" role="status" aria-live="polite"></div></div></section>
    <details class="intake-privacy"><summary>Không tải ảnh có chữ định danh. Thông tin bảo mật và dữ liệu nguồn</summary><p class="small muted">Máy chủ lưu PID giả danh và dấu HMAC thay cho PID nguồn. DICOM chưa được khử định danh đầy đủ: máy chủ lọc metadata văn bản, ngày giờ và thay UID nguồn; pixel không được làm sạch hay rà soát. Cờ BurnedInAnnotation từ máy siêu âm không xác nhận ảnh sạch; không tải ảnh có chữ định danh. Metadata chỉ là gợi ý; không thay giá trị đã nhập nếu chưa được bác sĩ áp dụng.</p></details>
    <div class="actions intake-swap">${button("Đổi bên ảnh (Trái ⇄ Phải)", "swap-sides", "small", "refresh")}</div>
    <div class="grid-2 intake-images">${["L", "R"].map(side => `<section class="upload-card side-${side}"><h2><span class="badge side-${side}">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái (L)" : "phải (R)"}</h2>
      <div class="dropzone" data-side="${side}">${icon("upload", 24)}<p>Kéo thả ảnh vào bên ${side === "L" ? "trái" : "phải"}</p><small class="muted">Tối đa 20 ảnh · PNG, JPG, JPEG, DICOM · tối đa 20 MB/ảnh</small><label class="btn small">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" multiple class="visually-hidden"></label></div>
      <div id="files-${side}" class="intake-file-list" aria-live="polite"><p class="small muted">Chưa chọn ảnh</p></div>
      <label class="intake-side-unavailable"><input type="checkbox" data-unavailable="${side}"> Đã phẫu thuật cắt bỏ / Không khảo sát được</label>
      <label class="field small" data-unavailable-wrap="${side}" hidden><span>Tình trạng bên không có ảnh</span><select data-unavailable-status="${side}" disabled><option value="">Chọn tình trạng</option><option value="SURGICALLY_ABSENT">Đã phẫu thuật cắt bỏ</option><option value="NOT_VISUALIZED">Không quan sát được</option></select></label>
      <progress id="progress-${side}" max="100" value="0" aria-label="Tiến trình tải ảnh ${side}"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p></section>`).join("")}</div>
    <div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div>
    <div id="intakeError" role="alert"></div><div class="actions intake-recovery">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}</div>
    <div class="intake-action-bar"><p class="small" id="intakeHint" role="status">Chọn ít nhất một ảnh siêu âm.</p><button type="button" class="btn primary" id="startSegmentationBtn" data-action="start-segmentation" aria-describedby="intakeHint" disabled>${icon("arrow")} Phân tích ảnh AI</button></div>`;
  const hasImages = () => ["L", "R"].some(side => files[side].length > 0);
  const sideIsConfirmed = side => files[side].length > 0
    ? files[side].every(entry => entry.confirmed)
    : ["SURGICALLY_ABSENT", "NOT_VISUALIZED"].includes(unavailableStatus[side]);
  const ready = () => active() && !state.busy && !running && !assigning && !selecting && validPid() && hasImages() && ["L", "R"].every(sideIsConfirmed) && q("[name=study-date]").validity.valid && q("[name=study-date]").value && (!syntheticDemoMode || validSyntheticDemoPid());
  const updateStatus = () => {
    if (!active()) return;
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
    q("#intakeHint").textContent = running ? "Đang xử lý; có thể dừng chờ phản hồi." : selecting ? "Đang kiểm tra ảnh…" : !imageSides.length ? "Chọn ít nhất một ảnh siêu âm." : unconfirmedSide ? `Có ảnh bên ${unconfirmedSide === "L" ? "trái" : "phải"} chưa xác nhận. Kiểm tra từng ảnh.` : unreportedSide ? "Ghi nhận bên không có ảnh và chọn đúng tình trạng trước khi tiếp tục." : syntheticDemoMode && !validSyntheticDemoPid() ? "Nhập mã ca tổng hợp bắt đầu bằng DEMO-SYNTHETIC-." : !q("[name=study-date]").value || !q("[name=study-date]").validity.valid ? "Chọn ngày giờ khảo sát hợp lệ." : readyMessage;
    q("[data-action=retry-upload]").disabled = !ready();
    if (!running && !selecting && !validPid()) q("#intakeHint").textContent = "PID bắt buộc gồm đúng 9 chữ số từ 0 đến 9.";
    else if (!running && !selecting && syntheticDemoMode && !validSyntheticDemoPid()) q("#intakeHint").textContent = "Vui lòng nhập mã bệnh nhân hợp lệ gồm 9 chữ số.";
    q("[data-action=swap-sides]").disabled = running || Boolean(state.busy) || Boolean(selecting);
    q("[data-action=change-patient]").disabled = running || Boolean(state.busy);
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
    root.querySelectorAll('[name=pid], [name=study-date], [name=reason], [data-action=set-now]').forEach(input => {
      const serverIdentityLocked = input.name === "pid" && Boolean(input.title);
      const syntheticReasonLocked = syntheticDemoMode && input.name === "reason";
      input.disabled = running || Boolean(state.busy) || serverIdentityLocked || syntheticReasonLocked;
    });
  };
  const renderProposals = () => {
    if (!active()) return;
    const target = q("#metadataProposals"); target.replaceChildren();
    const pendingActions = [];
    for (const side of ["L", "R"]) for (const image of files[side]) {
      const proposal = image.proposal;
      if (!proposal) continue;
      for (const [key, label, name] of [["pid", "PID nguồn", "pid"], ["study_date", "Ngày DICOM", "study-date"]]) {
        const candidate = proposal[key];
        if (!candidate?.value || candidate.source !== "dicom" || String(candidate.value) === q(`[name=${name}]`).value) continue;
        const row = document.createElement("div"), caption = document.createElement("span"), apply = document.createElement("button");
        row.className = "small"; caption.textContent = `${label} (${side}, ${image.file.name}): ${candidate.value} `;
        apply.type = "button"; apply.className = "btn small"; apply.textContent = "Áp dụng";
        const doApply = () => {
          if (!active() || !image.selection.current() || state.busy || running) return;
          const input = q(`[name=${name}]`); if (input.disabled || input.readOnly) return;
          const value = String(candidate.value).trim();
          if (name === "pid" && (!value || value.length > input.maxLength))
            return toast("PID nguồn vượt giới hạn cho phép. Kiểm tra và nhập mã phù hợp.", true);
          const previous = input.value;
          input.value = value;
          if (!input.value || !input.validity.valid) {
            input.value = previous;
            return toast("Gợi ý metadata không đúng định dạng trường. Kiểm tra nguồn trước khi nhập.", true);
          }
          const fieldName = key === "pid" ? "pid" : "studyDate";
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
  const run = async () => {
    if (!ready()) return toast("Kiểm tra đủ ảnh, ngày khảo sát và xác nhận bên trước khi chạy.", true);
    running = true; updateStatus();
    const activeSide = files.L.length && files.R.length ? "BOTH" : files.L.length ? "LEFT" : "RIGHT";
    const missingSide = files.L.length ? "R" : "L";
    try {
      await startBilateral(files, { pid: q("[name=pid]").value.trim(), reason: q("[name=reason]").value,
        idempotency_key: intakeRequestId,
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
  for (const name of ["pid", "study-date"]) q(`[name=${name}]`).addEventListener("input", () => {
    autofillState.set(name === "pid" ? "pid" : "studyDate", q(`[name=${name}]`).value, "manual"); renderProposals(); updateStatus();
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
