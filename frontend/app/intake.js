import { inspectDicom } from "./dicom-inspect.js";
import { state } from "./state.js";
import { demoDB, demoImage, log } from "./demo.js";
import { $, $$, esc, button, field, pageHead, icon, toast } from "./ui.js";
import { startBilateral } from "./upload.js";
export function renderIntake(root) {
  root.innerHTML =
    pageHead(
      "Khảo sát hai bên",
      "Tải ảnh buồng trứng trái và phải để bắt đầu.",
    ) +
    `<div class="panel" style="margin-bottom:24px"><div class="panel-body grid-2">${field("Mã nghiên cứu (PID)", "pid", "text", "", 'placeholder="Để trống để tự cấp BN-XXXX" maxlength="64"')}<label class="field">Lý do khảo sát<select name="reason"><option>Khác / chưa ghi nhận</option><option>Theo dõi hình thái</option><option>Khảo sát định kỳ</option></select></label>${field("Mã người tham gia (HITL)", "participant_code", "text", "TECH_01", 'placeholder="Mã người thực hiện" maxlength="64"')}<label class="field">Vai trò thực nghiệm<select name="participant_role"><option value="technical_tester">technical_tester (Kiểm thử kỹ thuật)</option><option value="clinician">clinician (Bác sĩ lâm sàng)</option></select></label></div></div><div class="grid-2">${["L", "R"].map((side) => `<section class="upload-card"><h2><span class="side-letter">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái" : "phải"}</h2><div class="dropzone" data-side="${side}">${icon("upload", 28)}<p>Kéo thả ảnh vào đây</p><small class="muted">PNG, JPG, JPEG, DICOM · tối đa 20 MB</small><label class="btn" style="margin-top:16px">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" class="visually-hidden"></label></div><p class="small muted" id="file-${side}">Chưa chọn ảnh</p><progress id="progress-${side}" max="100" value="0"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p><span class="badge">Ẩn danh: chưa được xác minh</span></section>`).join("")}</div><div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div><div id="intakeError" role="alert"></div><div class="banner info">${icon("help")}<div>Hệ thống tự bắt đầu khi đủ hai ảnh hợp lệ. Chỉ sử dụng ảnh đã được ẩn danh. Không nhập tên, ngày sinh hoặc mã định danh thật.</div></div><div class="actions">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}${state.demo ? button("Dùng cặp ảnh sơ đồ demo", "demo-pair", "primary") : ""}</div>`;
  const files = { L: null, R: null };
  const dicom = {};
  const urls = [];
  const choose = async (side, file) => {
    if (state.busy) return;
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (
      !["png", "jpg", "jpeg", "dcm"].includes(ext) ||
      file.size > 20 * 1024 * 1024 ||
      !file.size
    )
      return toast("Ảnh cần đúng định dạng và không vượt quá 20 MB.", true);
    if (ext !== "dcm") {
      const bitmap = await createImageBitmap(file).catch(() => null);
      if (!bitmap) return toast("Không giải mã được ảnh.", true);
      bitmap.close();
      const url = URL.createObjectURL(file);
      urls.push(url);
      const zone = $(`[data-side=${side}]`);
      zone.querySelector("img")?.remove();
      const img = document.createElement("img");
      img.src = url;
      img.alt = "Ảnh xem trước bên " + side;
      zone.prepend(img);
    }
    if (ext === "dcm") {
      try {
        dicom[side] = await inspectDicom(file, side);
        if (dicom[side].anonymous_pid && !$("[name=pid]").value)
          $("[name=pid]").value = dicom[side].anonymous_pid;
      } catch (e) {
        return toast(e.message, true);
      }
    } else delete dicom[side];
    files[side] = file;
    $("#file-" + side).textContent =
      "Ảnh " +
      (side === "L" ? "trái" : "phải") +
      " · " +
      Math.round(file.size / 1024) +
      " KB";
    $("#stage-" + side).textContent = dicom[side]?.label || "Ảnh sẵn sàng";
    if (files.L && files.R) run();
  };
  const run = () =>
    startBilateral(files, {
      pid: $("[name=pid]").value.trim(),
      reason: $("[name=reason]").value,
      participant_code: ($("[name=participant_code]")?.value || "TECH_01").trim(),
      participant_role: $("[name=participant_role]")?.value || "technical_tester",
      data_origin: state.demo ? "demo" : "live",
      dicom,
    });
  $$("[data-file]").forEach(
    (i) => (i.onchange = () => choose(i.dataset.file, i.files[0])),
  );
  $$(".dropzone").forEach((z) => {
    z.ondragover = (e) => {
      e.preventDefault();
      z.classList.add("drag");
    };
    z.ondragleave = () => z.classList.remove("drag");
    z.ondrop = (e) => {
      e.preventDefault();
      z.classList.remove("drag");
      if (e.dataTransfer.files.length !== 1)
        return toast("Chọn đúng một ảnh cho mỗi bên.", true);
      choose(z.dataset.side, e.dataTransfer.files[0]);
    };
  });
  $("[data-action=retry-upload]").onclick = run;
  $("[data-action=cancel-upload]").onclick = () => state.controller?.abort();
  $("[data-action=demo-pair]")?.addEventListener("click", () => {
    const c = {
      study_id: crypto.randomUUID(),
      study_code: "DEMO-" + Date.now().toString().slice(-6),
      patient_id:
        $("[name=pid]").value || "DEMO-" + crypto.randomUUID().slice(0, 4),
      owner_id: state.user.id,
      status: "AI_DONE",
      study_date: new Date().toISOString().slice(0, 10),
      created_at: new Date().toISOString(),
      version: 1,
      images: [demoImage("L", Date.now()), demoImage("R", Date.now())],
      timeline: [],
      clinical_indication: $("[name=reason]").value,
    };
    demoDB.cases.unshift(c);
    state.case = c;
    log("UPLOAD_IMAGE", c.study_id);
    location.hash = "#viewer/" + c.study_id;
  });
  return () => {
    state.controller?.abort();
    urls.forEach(URL.revokeObjectURL);
  };
}
