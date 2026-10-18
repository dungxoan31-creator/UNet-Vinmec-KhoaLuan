import { inspectDicom } from "./dicom-inspect.js";
import { state } from "./state.js";

import { $, $$, esc, button, field, pageHead, icon, toast } from "./ui.js";
import { startBilateral } from "./upload.js";
export function renderIntake(root) {
  root.innerHTML =
    pageHead(
      "Khảo sát hai bên",
      "Tải ảnh buồng trứng trái và phải để bắt đầu.",
    ) +
    `<div class="panel" style="margin-bottom:24px"><div class="panel-body grid-2">${field("Mã bệnh nhân (PID)", "pid", "text", "", 'placeholder="Để trống để tự cấp BN-XXXX" maxlength="64"')}<label class="field">Lý do khảo sát<select name="reason"><option>Khác / chưa ghi nhận</option><option>Theo dõi hình thái</option><option>Khảo sát định kỳ</option></select></label></div></div><div class="grid-2">${["L", "R"].map((side) => `<section class="upload-card side-${side}"><h2><span class="side-letter">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái (L)" : "phải (R)"}</h2><div class="dropzone" data-side="${side}">${icon("upload", 28)}<p>Kéo thả ảnh vào đây</p><small class="muted">PNG, JPG, JPEG, DICOM · tối đa 20 MB</small><label class="btn" style="margin-top:16px">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" class="visually-hidden"></label></div><div id="file-${side}" class="small muted" style="min-height:24px;margin-top:6px">Chưa chọn ảnh</div><progress id="progress-${side}" max="100" value="0"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p><span class="badge" style="background:${side === 'L' ? '#e0f2fe' : '#f3e8ff'};color:${side === 'L' ? '#0369a1' : '#7e22ce'};font-weight:600">${side === 'L' ? 'Buồng trứng Trái' : 'Buồng trứng Phải'}</span></section>`).join("")}</div><div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div><div id="intakeError" role="alert"></div><div class="actions" style="margin:20px 0 6px 0"><button class="btn primary wide" id="startSegmentationBtn" data-action="start-segmentation" disabled style="padding:14px 20px;font-size:16px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:8px;">${icon("arrow")} Kích hoạt phân đoạn AI & Đo kích thước</button></div><p class="small muted" id="intakeHint" style="margin-top:4px;margin-bottom:14px;text-align:center;">Vui lòng tải đủ ảnh buồng trứng trái và phải để kích hoạt phân tích.</p><div class="banner info">${icon("help")}<div>Chọn đủ hai ảnh buồng trứng trái và phải, sau đó bấm <strong>Kích hoạt phân đoạn AI</strong> để hệ thống tiến hành kiểm tra chất lượng, suy luận U-Net và tự động đo kích thước tổn thương.</div></div><div class="actions">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}</div>`;
  const files = { L: null, R: null };
  const dicom = {};
  const urls = [];
  const updateStatus = () => {
    const trigger = $("#startSegmentationBtn");
    const hint = $("#intakeHint");
    const ready = !!(files.L && files.R);
    if (trigger) trigger.disabled = !ready;
    if (hint) {
      if (!files.L && !files.R) {
        hint.textContent = "Vui lòng chọn ảnh buồng trứng trái và phải để kích hoạt phân tích.";
      } else if (files.L && !files.R) {
        hint.innerHTML = "<span style='color:var(--accent,#0076c0);font-weight:600'>Đã có ảnh Trái.</span> Vui lòng chọn thêm ảnh buồng trứng Phải.";
      } else if (!files.L && files.R) {
        hint.innerHTML = "<span style='color:var(--accent,#0076c0);font-weight:600'>Đã có ảnh Phải.</span> Vui lòng chọn thêm ảnh buồng trứng Trái.";
      } else {
        hint.innerHTML = "<span style='color:var(--success,#059669);font-weight:600'>✓ Đã đủ 2 ảnh siêu âm hợp lệ.</span> Sẵn sàng kích hoạt phân đoạn AI & đo kích thước.";
      }
    }
  };
  const remove = (side) => {
    files[side] = null;
    delete dicom[side];
    const zone = $(`[data-side=${side}]`);
    if (zone) {
      zone.querySelector("img")?.remove();
      zone.classList.remove("has-file");
    }
    const input = $(`[data-file=${side}]`);
    if (input) input.value = "";
    $("#file-" + side).textContent = "Chưa chọn ảnh";
    $("#stage-" + side).textContent = "Chờ ảnh";
    $("#progress-" + side).value = 0;
    updateStatus();
  };
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
      zone.classList.add("has-file");
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
    const fileEl = $("#file-" + side);
    if (fileEl) {
      fileEl.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between"><span>Ảnh ${side === "L" ? "trái" : "phải"} · <b>${Math.round(file.size / 1024)} KB</b></span><button type="button" class="btn small quiet" data-remove="${side}" style="padding:2px 8px;font-size:11px;color:var(--danger,#e11d48)">✕ Bỏ chọn</button></div>`;
      fileEl.querySelector(`[data-remove=${side}]`).onclick = () => remove(side);
    }
    $("#stage-" + side).textContent = dicom[side]?.label || "Ảnh sẵn sàng";
    updateStatus();
  };
  const run = () => {
    const trigger = $("#startSegmentationBtn");
    if (trigger) {
      trigger.disabled = true;
      trigger.textContent = "Đang xử lý phân đoạn AI…";
    }
    return startBilateral(files, {
      pid: $("[name=pid]").value.trim(),
      reason: $("[name=reason]").value,
      participant_code: state.user.username,
      participant_role: "clinician",
      data_origin: "live",
      dicom,
    }).finally(() => {
      const btn = $("#startSegmentationBtn");
      if (btn) {
        btn.disabled = !(files.L && files.R);
        btn.innerHTML = `${icon("arrow")} Kích hoạt phân đoạn AI & Đo kích thước`;
      }
    });
  };
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
  const trigger = $("#startSegmentationBtn");
  if (trigger) {
    trigger.onclick = () => {
      if (!files.L || !files.R) {
        return toast("Cần chọn đủ hai ảnh buồng trứng trái và phải trước khi kích hoạt.", true);
      }
      run();
    };
  }
  return () => {
    state.controller?.abort();
    urls.forEach(URL.revokeObjectURL);
  };
}
