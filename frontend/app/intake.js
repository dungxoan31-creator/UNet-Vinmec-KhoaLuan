import { inspectDicom } from "./dicom-inspect.js";
import { getLateralityHint, suggestLaterality } from "./laterality-hint.js";
import { createIntakeSession, createDemoPatientStore, planBilateralDrop } from "./intake-session.js";
import { autofillState, state } from "./state.js";
import { esc, button, field, modal, pageHead, icon, toast } from "./ui.js";
import { startBilateral } from "./upload.js";
import { request } from "./api.js";

const patientsKey = () => `ova.demo-patients.v1.${encodeURIComponent(state.user?.id ?? "anonymous")}`;
const patientsStore = createDemoPatientStore([
  { pid: "100000001", visit: "000001", name: "Nguyễn Minh Anh", age: 32 },
  { pid: "100000002", visit: "000002", name: "Trần Thu Hà", age: 41 },
  { pid: "100000003", visit: "000003", name: "Lê Ngọc Mai", age: 28 },
  { pid: "100000004", visit: "000004", name: "Phạm Thanh Vy", age: 36 },
]);
const storageNotice = () => patientsStore.isTransient(patientsKey())
  ? '<div class="banner warning" role="status">Không ghi được danh sách mô phỏng trên thiết bị. Dữ liệu mới chỉ giữ trong phiên này; tải lại trang có thể làm mất dữ liệu chưa lưu.</div>' : "";
function makeId(length, used) {
  let value;
  do { value = Array.from(crypto.getRandomValues(new Uint8Array(length)), digit => digit % 10).join(""); } while (used.has(value));
  return value;
}
export function renderIntake(root) {
  let cleanupUpload;
  const identity = state.user?.id;
  const active = () => root.isConnected && identity === state.user?.id;
  const renderList = () => {
    cleanupUpload?.(); cleanupUpload = null;
    if (!active()) return;
    const patients = patientsStore.read(patientsKey());
    root.innerHTML = pageHead("Chọn bệnh nhân", "Chọn hồ sơ mô phỏng để bắt đầu khảo sát.", button("Tạo bệnh nhân", "add-patient", "primary", "plus")) + storageNotice() +
      `<section class="panel"><div class="panel-head"><h2>Danh sách bệnh nhân mô phỏng</h2><span class="badge">${patients.length} hồ sơ mẫu</span></div><div class="table-wrap"><table><thead><tr><th>PID</th><th>Visit No</th><th>Bệnh nhân</th><th>Tuổi</th><th></th></tr></thead><tbody>${patients.map((p, i) => `<tr><td class="mono">${esc(p.pid)}</td><td class="mono">${esc(p.visit)}</td><td><strong>${esc(p.name)}</strong><small>Dữ liệu mô phỏng</small></td><td>${p.age} tuổi</td><td><button class="btn small primary" type="button" data-select="${i}">Chọn bệnh nhân</button></td></tr>`).join("")}</tbody></table></div></section>`;
    const open = patient => {
      if (!active()) return;
      cleanupUpload?.(); cleanupUpload = renderUpload(root, patient, renderList);
    };
    root.querySelectorAll("[data-select]").forEach(el => { el.onclick = () => open(patients[Number(el.dataset.select)]); });
    root.querySelector("[data-action=add-patient]").onclick = () => {
      const currentYear = new Date().getFullYear();
      modal("Tạo bệnh nhân mô phỏng",
        '<p class="small muted">Danh sách mô phỏng trên trình duyệt này, không phải hồ sơ bệnh nhân trên máy chủ. Không nhập thông tin nhận diện thật.</p>' +
        field("Họ và tên", "full_name", "text", "", 'required maxlength="120"') +
        field("Năm sinh", "birth_year", "number", "", `required min="1900" max="${currentYear}"`) +
        field("Số điện thoại", "phone", "tel", "", 'required maxlength="24"') +
        '<label class="field">Giới tính<select name="gender" required><option value="">Chọn giới tính</option><option value="female">Nữ</option><option value="male">Nam</option><option value="other">Khác</option><option value="unknown">Không muốn nêu</option></select></label>' +
        field("Quê quán", "hometown", "text", "", 'required maxlength="120"') +
        '<p class="form-error" data-patient-error role="alert" hidden></p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" type="submit">Tạo và tiếp tục</button></div>',
        (event, dialog) => {
          if (!active()) return dialog.close();
          const data = Object.fromEntries(new FormData(event.target));
          const digits = String(data.phone).replace(/\D/g, "");
          const year = Number(data.birth_year);
          const error = dialog.querySelector("[data-patient-error]");
          if (!String(data.full_name).trim() || !String(data.hometown).trim() || digits.length < 9 || digits.length > 12 || !Number.isInteger(year) || year < 1900 || year > currentYear) {
            error.textContent = "Kiểm tra họ tên, năm sinh, quê quán và số điện thoại từ 9 đến 12 chữ số."; error.hidden = false; return;
          }
          const rows = patientsStore.read(patientsKey());
          const patient = { pid: makeId(9, new Set(rows.map(p => p.pid))), visit: makeId(6, new Set(rows.map(p => p.visit))),
            name: String(data.full_name).trim(), age: currentYear - year, birth_year: year,
            phone: String(data.phone).trim(), gender: data.gender, hometown: String(data.hometown).trim() };
          patientsStore.save(patientsKey(), [...rows, patient]); dialog.close(); open(patient);
        });
    };
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
  const active = () => session.active() && root.isConnected;
  const q = selector => root.querySelector(selector);
  const files = { L: null, R: null }, confirmed = { L: false, R: false }, dicom = {};
  const urls = new Map(), proposals = new Map();
  let running = false, assigning = false, selecting = 0;
  autofillState.reset(); root.classList.add("intake-workspace");
  root.innerHTML = `<div class="intake-identity banner info"><div><strong>${esc(patient.name)}</strong> · Hồ sơ mô phỏng · Visit <span class="mono">${esc(patient.visit)}</span></div>${button("Chọn bệnh nhân khác", "change-patient", "small")}</div>` +
    pageHead("Khảo sát hai bên", "Kiểm tra đúng mã ca, ảnh và bên trước khi phân đoạn.") + storageNotice() +
    `<section class="panel intake-metadata"><div class="panel-body grid-2">${field("Mã bệnh nhân (PID)", "pid", "text", patient.pid || "", 'placeholder="Để trống để tự cấp BN-XXXX" maxlength="64"')}
      <label class="field">Ngày giờ khảo sát<div class="intake-date"><input type="datetime-local" name="study-date" value="${nowLocal()}" required>${button("Hiện tại", "set-now", "small")}</div></label>
      <label class="field">Lý do khảo sát<select name="reason"><option>Khác / chưa ghi nhận</option><option>Theo dõi hình thái</option><option>Khảo sát định kỳ</option></select></label>
      <div id="metadataProposals" class="intake-metadata-proposals" role="status" aria-live="polite"></div></div></section>
    <details class="intake-privacy"><summary>Không tải ảnh có chữ định danh. Thông tin bảo mật và dữ liệu nguồn</summary><p class="small muted">Máy chủ lưu PID giả danh và dấu HMAC thay cho PID nguồn. DICOM chưa được khử định danh đầy đủ: máy chủ lọc metadata văn bản, ngày giờ và thay UID nguồn; pixel không được làm sạch hay rà soát. Cờ BurnedInAnnotation từ máy siêu âm không xác nhận ảnh sạch; không tải ảnh có chữ định danh. Metadata chỉ là gợi ý; không thay giá trị đã nhập nếu chưa được bác sĩ áp dụng.</p></details>
    <div class="actions intake-swap">${button("Đổi bên ảnh (Trái ⇄ Phải)", "swap-sides", "small", "refresh")}</div>
    <div class="grid-2 intake-images">${["L", "R"].map(side => `<section class="upload-card side-${side}"><h2><span class="badge side-${side}">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái (L)" : "phải (R)"}</h2>
      <div class="dropzone" data-side="${side}">${icon("upload", 24)}<p>Kéo thả 1 hoặc 2 ảnh</p><small class="muted">PNG, JPG, JPEG, DICOM · tối đa 20 MB/ảnh</small><label class="btn small">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" class="visually-hidden"></label></div>
      <div id="file-${side}" class="small muted">Chưa chọn ảnh</div><p id="laterality-hint-${side}" class="small muted" role="status"></p>
      <label class="intake-side-confirm" hidden><input type="checkbox" data-confirm="${side}"> Tôi xác nhận ảnh này thuộc bên ${side === "L" ? "trái" : "phải"}</label>
      <progress id="progress-${side}" max="100" value="0" aria-label="Tiến trình tải ảnh ${side}"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p></section>`).join("")}</div>
    <div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div>
    <div id="intakeError" role="alert"></div><div class="actions intake-recovery">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}</div>
    <div class="intake-action-bar"><p class="small" id="intakeHint" role="status">Chọn đủ ảnh hai bên.</p><button type="button" class="btn primary" id="startSegmentationBtn" data-action="start-segmentation" disabled>${icon("arrow")} Kích hoạt phân đoạn AI & Đo kích thước</button></div>`;
  const ready = () => active() && !state.busy && !running && !assigning && !selecting && files.L && files.R && confirmed.L && confirmed.R && q("[name=study-date]").validity.valid && q("[name=study-date]").value;
  const updateStatus = () => {
    if (!active()) return;
    q("#startSegmentationBtn").disabled = !ready();
    q("#startSegmentationBtn").innerHTML = running ? "Đang xử lý phân đoạn AI…" : `${icon("arrow")} Kích hoạt phân đoạn AI & Đo kích thước`;
    q("#intakeHint").textContent = running ? "Đang xử lý; có thể dừng chờ phản hồi." : selecting ? "Đang kiểm tra ảnh…" : !files.L || !files.R ? "Chọn đủ ảnh buồng trứng trái và phải." : !confirmed.L || !confirmed.R ? "Có bên chưa được xác nhận. Kiểm tra gợi ý cạnh ảnh." : !q("[name=study-date]").value || !q("[name=study-date]").validity.valid ? "Chọn ngày giờ khảo sát hợp lệ." : "Đủ hai ảnh và bên đã xác nhận. Sẵn sàng phân đoạn.";
    q("[data-action=retry-upload]").disabled = !ready();
    q("[data-action=swap-sides]").disabled = running || Boolean(state.busy) || Boolean(selecting);
    q("[data-action=change-patient]").disabled = running || Boolean(state.busy);
    root.querySelectorAll("[data-file], [data-confirm]").forEach(input => { input.disabled = running || assigning || Boolean(state.busy); });
    root.querySelectorAll('[name=pid], [name=study-date], [name=reason], [data-action=set-now]').forEach(input => {
      const serverIdentityLocked = input.name === "pid" && Boolean(input.title);
      input.disabled = running || Boolean(state.busy) || serverIdentityLocked;
    });
  };
  const renderProposals = () => {
    if (!active()) return;
    const target = q("#metadataProposals"); target.replaceChildren();
    for (const [side, proposal] of proposals) for (const [key, label, name] of [["pid", "PID nguồn", "pid"], ["study_date", "Ngày DICOM", "study-date"]]) {
      const entry = proposal.metadata?.[key];
      if (!entry?.value || entry.source !== "dicom" || String(entry.value) === q(`[name=${name}]`).value) continue;
      const row = document.createElement("div"), caption = document.createElement("span"), apply = document.createElement("button");
      row.className = "small"; caption.textContent = `${label} (${side}, DICOM): ${entry.value} `;
      apply.type = "button"; apply.className = "btn small"; apply.textContent = "Áp dụng";
      apply.onclick = () => {
        if (!active() || !proposal.current() || state.busy || running) return;
        const input = q(`[name=${name}]`); if (input.disabled || input.readOnly) return;
        const value = String(entry.value).trim();
        if (name === "pid" && (!value || value.length > input.maxLength))
          return toast("PID nguồn vượt giới hạn cho phép. Kiểm tra và nhập mã phù hợp.", true);
        const previous = input.value;
        input.value = value;
        if (!input.value || !input.validity.valid) {
          input.value = previous;
          return toast("Gợi ý metadata không đúng định dạng trường. Kiểm tra nguồn trước khi nhập.", true);
        }
        const fieldName = key === "pid" ? "pid" : "studyDate";
        autofillState.set(fieldName, input.value, "dicom", entry.confidence); autofillState.confirm(fieldName);
        renderProposals(); updateStatus();
      };
      row.append(caption, apply); target.append(row);
    }
  };
  const remove = side => {
    session.remove(side); files[side] = null; confirmed[side] = false; delete dicom[side]; proposals.delete(side);
    if (urls.has(side)) URL.revokeObjectURL(urls.get(side)); urls.delete(side);
    const zone = q(`[data-side=${side}]`); zone.querySelector("img")?.remove(); zone.classList.remove("has-file");
    q(`[data-file=${side}]`).value = ""; q(`#file-${side}`).textContent = "Chưa chọn ảnh"; q(`#laterality-hint-${side}`).textContent = "";
    q(`#laterality-hint-${side}`).dataset.message = "";
    const check = q(`[data-confirm=${side}]`); check.checked = false; check.parentElement.hidden = true;
    q(`#stage-${side}`).textContent = "Chờ ảnh"; q(`#progress-${side}`).value = 0;
    q("#intakeError").replaceChildren();
    renderProposals(); updateStatus();
  };
  const metadata = async (side, file, selection) => {
    if (state.capabilities.feature_autofill === false) return;
    try {
      const form = new FormData(); form.append("file", file);
      const data = await request("/api/intake/extract-metadata", { method: "POST", body: form, signal: selection.signal, timeoutMs: 12000 });
      if (!selection.current() || !active() || files[side] !== file) return;
      proposals.set(side, { metadata: data.metadata, current: selection.current });
      const sourceSide = data.metadata?.laterality?.value;
      if ((sourceSide === "L" || sourceSide === "R") && sourceSide !== side && data.metadata.laterality.source === "dicom") {
        confirmed[side] = false; q(`[data-confirm=${side}]`).checked = false; q(`[data-confirm=${side}]`).parentElement.hidden = false;
        q(`#laterality-hint-${side}`).textContent = `DICOM gợi ý bên ${sourceSide}, khác ô ${side}. Kiểm tra và xác nhận bên.`; q(`#laterality-hint-${side}`).classList.add("form-error");
        q(`#laterality-hint-${side}`).dataset.message = q(`#laterality-hint-${side}`).textContent;
      }
      renderProposals(); updateStatus();
    } catch (error) {
      if (error.name !== "AbortError" && selection.current() && active()) q(`#stage-${side}`).textContent = "Ảnh sẵn sàng · không lấy được gợi ý metadata";
    }
  };
  const choose = async (side, file, needsConfirmation = false) => {
    if (!active() || state.busy || running || !file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["png", "jpg", "jpeg", "dcm"].includes(ext) || file.size > 20 * 1024 * 1024 || !file.size) return toast("Ảnh cần đúng định dạng và không vượt quá 20 MB.", true);
    remove(side); const selection = session.select(side, file); selecting++; updateStatus();
    try {
      if (ext === "dcm") {
        const info = await inspectDicom(file, side); if (!selection.current() || !active()) return; dicom[side] = info;
      } else {
        const bitmap = await createImageBitmap(file); bitmap.close(); if (!selection.current() || !active()) return;
        const url = URL.createObjectURL(file); urls.set(side, url);
        const image = document.createElement("img"); image.src = url; image.alt = `Ảnh xem trước bên ${side}`;
        q(`[data-side=${side}]`).prepend(image); q(`[data-side=${side}]`).classList.add("has-file");
      }
      files[side] = file; const hint = getLateralityHint(file.name, side);
      confirmed[side] = !needsConfirmation && !hint?.mismatch;
      const check = q(`[data-confirm=${side}]`); check.checked = confirmed[side]; check.parentElement.hidden = confirmed[side];
      const hintEl = q(`#laterality-hint-${side}`);
      hintEl.textContent = hint?.message || (needsConfirmation ? "Không có cặp gợi ý L/R duy nhất. Kiểm tra và xác nhận bên đã chọn." : "Bên do bác sĩ chọn; tên tệp không cung cấp gợi ý.");
      hintEl.dataset.message = hintEl.textContent;
      hintEl.classList.toggle("form-error", !confirmed[side]);
      const fileEl = q(`#file-${side}`); fileEl.textContent = `${file.name} · ${Math.round(file.size / 1024)} KB `;
      const removeButton = document.createElement("button"); removeButton.type = "button"; removeButton.className = "btn small quiet"; removeButton.textContent = "Bỏ chọn";
      removeButton.onclick = () => { if (!state.busy && !running) remove(side); }; fileEl.append(removeButton);
      q(`#stage-${side}`).textContent = dicom[side]?.label || "Ảnh sẵn sàng"; await metadata(side, file, selection);
    } catch (error) { if (selection.current() && active()) toast(ext === "dcm" ? error.message : "Không giải mã được ảnh.", true); }
    finally { selecting--; updateStatus(); }
  };
  const run = async () => {
    if (!ready()) return toast("Kiểm tra đủ ảnh, ngày khảo sát và xác nhận bên trước khi chạy.", true);
    running = true; updateStatus();
    try {
      await startBilateral({ ...files }, { pid: q("[name=pid]").value.trim(), reason: q("[name=reason]").value,
        study_date: q("[name=study-date]").value, participant_code: state.user.username,
        participant_role: "clinician", data_origin: "live", dicom: { ...dicom }, onRetry: run, isCurrent: active });
    } finally { running = false; updateStatus(); }
  };
  for (const side of ["L", "R"]) {
    q(`[data-file=${side}]`).onchange = event => { if (!assigning) void choose(side, event.target.files[0]); };
    q(`[data-confirm=${side}]`).onchange = event => {
      if (state.busy || running) { event.target.checked = confirmed[side]; return; }
      confirmed[side] = event.target.checked;
      const hint = q(`#laterality-hint-${side}`);
      hint.classList.toggle("form-error", !confirmed[side]);
      hint.textContent = confirmed[side] ? `Bác sĩ đã xác nhận bên ${side === "L" ? "trái" : "phải"}. Tên tệp và DICOM chỉ là gợi ý.` : hint.dataset.message;
      updateStatus();
    };
    const zone = q(`[data-side=${side}]`);
    zone.ondragover = event => { event.preventDefault(); zone.classList.add("drag"); }; zone.ondragleave = () => zone.classList.remove("drag");
    zone.ondrop = async event => {
      event.preventDefault(); zone.classList.remove("drag"); if (running || assigning || state.busy || selecting) return;
      const dropped = Array.from(event.dataTransfer.files);
      if (dropped.length === 1) return choose(side, dropped[0]);
      if (dropped.length !== 2) return toast("Vui lòng kéo thả 1 hoặc 2 ảnh.", true);
      const plan = planBilateralDrop(dropped, suggestLaterality);
      assigning = true; remove("L"); remove("R"); updateStatus();
      try { for (const item of plan) await choose(item.side, item.file, item.needsConfirmation); }
      finally { assigning = false; updateStatus(); }
      if (active()) toast(plan.some(item => item.needsConfirmation) ? "Kiểm tra thumbnail và xác nhận bên cho từng ảnh trước khi phân đoạn." : "Đã đề xuất phân bổ theo gợi ý L/R của tên tệp; bác sĩ kiểm tra trước khi chạy.");
    };
  }
  q("[data-action=swap-sides]").onclick = async () => {
    if (state.busy || running || selecting) return;
    const old = { ...files }; assigning = true; remove("L"); remove("R"); updateStatus();
    try { if (old.R) await choose("L", old.R, true); if (old.L) await choose("R", old.L, true); }
    finally { assigning = false; updateStatus(); }
    if (active()) toast("Đã đổi vị trí. Xác nhận lại bên trước khi phân đoạn.");
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
  return () => { session.dispose(); state.controller?.abort(); for (const url of urls.values()) URL.revokeObjectURL(url); root.classList.remove("intake-workspace"); };
}
