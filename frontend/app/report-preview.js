import { state } from "./state.js";
import { getCase } from "./cases.js";
import { protectedImage, request } from "./api.js";

import { letterbox } from "./coordinates.js";
import { $, esc, pageHead, button, loading, errorBox, toast } from "./ui.js";
import { buildResearchDraft } from "./research-report-draft.js";

function researchDraftPanel(study) {
  const panel = document.createElement("section");
  panel.className = "research-report-draft";
  panel.setAttribute("aria-labelledby", "researchDraftHeading");

  const heading = document.createElement("h2");
  heading.id = "researchDraftHeading";
  heading.textContent = "Bản nháp nghiên cứu";
  const disclosure = document.createElement("p");
  disclosure.id = "researchDraftDisclosure";
  disclosure.className = "muted small";
  disclosure.textContent = "Chọn một bên để tạo bản nháp từ dữ liệu đã rà soát.";

  const sideLabel = document.createElement("label");
  sideLabel.className = "field";
  sideLabel.htmlFor = "researchDraftSide";
  sideLabel.textContent = "Bên khảo sát";
  const sideSelect = document.createElement("select");
  sideSelect.id = "researchDraftSide";
  sideSelect.setAttribute("aria-label", "Chọn bên cho bản nháp nghiên cứu");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Chọn bên…";
  sideSelect.append(placeholder);
  for (const image of study.images) {
    const option = document.createElement("option");
    option.value = image.image_id;
    option.textContent =
      image.laterality === "L"
        ? "Buồng trứng trái"
        : image.laterality === "R"
          ? "Buồng trứng phải"
          : "Bên chưa xác định";
    sideSelect.append(option);
  }
  sideLabel.append(sideSelect);

  const draftLabel = document.createElement("label");
  draftLabel.className = "field";
  draftLabel.htmlFor = "researchDraftText";
  draftLabel.textContent = "Bản nháp có thể chỉnh sửa · chưa lưu vào hồ sơ";
  const draftText = document.createElement("textarea");
  draftText.id = "researchDraftText";
  draftText.rows = 10;
  draftText.disabled = true;
  draftText.setAttribute(
    "aria-describedby",
    "researchDraftDisclosure researchDraftMissing",
  );
  draftLabel.append(draftText);

  const missing = document.createElement("p");
  missing.id = "researchDraftMissing";
  missing.className = "small";
  missing.setAttribute("role", "status");
  missing.setAttribute("aria-live", "polite");
  const actions = document.createElement("div");
  actions.className = "actions";
  const copyButton = document.createElement("button");
  copyButton.id = "researchDraftCopy";
  copyButton.type = "button";
  copyButton.className = "btn small";
  copyButton.textContent = "Sao chép bản nháp";
  copyButton.disabled = true;
  const copyStatus = document.createElement("span");
  copyStatus.className = "muted small";
  copyStatus.setAttribute("role", "status");
  copyStatus.setAttribute("aria-live", "polite");
  actions.append(copyButton, copyStatus);
  panel.append(heading, disclosure, sideLabel, draftLabel, missing, actions);

  const drafts = new Map();
  let selectedImage = null;
  let selectedDisclosure = "";
  sideSelect.addEventListener("change", () => {
    if (selectedImage) drafts.set(selectedImage.image_id, draftText.value);
    selectedImage =
      study.images.find((image) => image.image_id === sideSelect.value) || null;
    if (!selectedImage) {
      draftText.value = "";
      draftText.textContent = "";
      draftText.disabled = true;
      missing.textContent = "";
      disclosure.textContent = "Chọn một bên để tạo bản nháp từ dữ liệu đã rà soát.";
      selectedDisclosure = "";
      copyButton.disabled = true;
      copyStatus.textContent = "";
      return;
    }

    const result = buildResearchDraft({
      studyCode: study.study_code || study.study_id || null,
      image: selectedImage,
    });
    selectedDisclosure = result.disclosure;
    draftText.textContent = result.text;
    draftText.value = drafts.get(selectedImage.image_id) ?? result.text;
    draftText.disabled = false;
    disclosure.textContent = result.disclosure;
    missing.textContent = result.missingFields.length
      ? `Thiếu dữ liệu: ${result.missingFields.join("; ")}`
      : "Không ghi nhận trường thiếu trong dữ liệu được đưa vào bản nháp.";
    copyButton.disabled = false;
    copyStatus.textContent = "";
  });
  draftText.addEventListener("input", () => {
    if (selectedImage) drafts.set(selectedImage.image_id, draftText.value);
  });
  copyButton.addEventListener("click", async () => {
    if (!selectedImage) return;
    if (!navigator.clipboard?.writeText) {
      copyStatus.textContent = "Trình duyệt không hỗ trợ sao chép tự động.";
      return;
    }
    try {
      await navigator.clipboard.writeText(
        `${draftText.value.trimEnd()}\n\n${selectedDisclosure}`,
      );
      copyStatus.textContent = "Đã sao chép bản nháp nghiên cứu.";
    } catch {
      copyStatus.textContent = "Không thể sao chép; hãy chọn và sao chép thủ công.";
    }
  });

  return panel;
}

export function formatOradsAttribution(image) {
  const value =
    image?.review?.orads_score ||
    image?.review?.orads ||
    image?.orads ||
    "Chưa ghi nhận";
  return `O-RADS do bác sĩ ghi nhận: <strong>${esc(value)}</strong>`;
}

export function reportReviewStatus(image) {
  const review = image?.review;
  if (!review?.review_id || !review?.doctor_id)
    return "Chưa có rà soát được lưu · Bản nháp chưa rà soát";
  return `Người rà soát: ${review.doctor_id} · Bản ghi ${review.review_id}`;
}

const formatReportNumber = (value) =>
  Number.isFinite(value) ? value.toFixed(2) : "Chưa ghi nhận";

export function formatReportMeasurements(image) {
  if (!image?.mask?.some(Boolean)) {
    return `<tr><td colspan="3">Không có vùng phân đoạn trong mask được lưu hoặc xem trước; điều này không phải kết luận về tình trạng lâm sàng.</td></tr>`;
  }

  const measurements = image.measurements || {};
  const calibrated = measurements.calibrated === true;
  const d1 = calibrated ? measurements.max_diameter_mm : measurements.max_diameter_px;
  const d2 = calibrated ? measurements.ortho_diameter_mm : measurements.ortho_diameter_px;
  const area = calibrated ? measurements.total_area_cm2 : measurements.total_area_px;
  const diameterUnit = calibrated ? "mm" : "px";
  const areaUnit = calibrated ? "cm²" : "px²";

  return `<tr><td>${formatReportNumber(d1)} × ${formatReportNumber(d2)} ${diameterUnit}</td><td>${formatReportNumber(area)} ${areaUnit}</td><td>${calibrated ? esc(measurements.calibration_source || "Đã hiệu chuẩn") : "Chưa hiệu chuẩn"}</td></tr>`;
}

async function reportImages(i) {
  const url = await protectedImage("/api/images/" + i.image_id + "/source.png");
  let bitmap;
  try {
    const sourceImage = new Image();
    sourceImage.src = url;
    await sourceImage.decode();
    bitmap = await createImageBitmap(sourceImage);
  } finally {
    URL.revokeObjectURL(url);
  }
  const c = document.createElement("canvas");
  c.width = bitmap.width;
  c.height = bitmap.height;
  const g = c.getContext("2d");
  g.drawImage(bitmap, 0, 0);
  const original = c.toDataURL();
  const mask = document.createElement("canvas");
  mask.width = mask.height = 512;
  const mg = mask.getContext("2d"),
    pixels = mg.createImageData(512, 512);
  for (let n = 0; n < i.mask.length; n++)
    if (i.mask[n]) pixels.data.set([98, 233, 224, 255], n * 4);
  mg.putImageData(pixels, 0, 0);
  const box = letterbox(bitmap.width, bitmap.height);
  g.fillStyle = "#20262c";
  g.fillRect(0, 0, c.width, c.height);
  g.drawImage(
    mask,
    box.left,
    box.top,
    box.width,
    box.height,
    0,
    0,
    c.width,
    c.height,
  );
  const binary = c.toDataURL();
  g.drawImage(bitmap, 0, 0);
  g.globalAlpha = 0.35;
  g.drawImage(
    mask,
    box.left,
    box.top,
    box.width,
    box.height,
    0,
    0,
    c.width,
    c.height,
  );
  g.globalAlpha = 1;
  const m = i.measurements;
  const primaryLesion = m?.lesions?.[0];
  const dmaxPoints = m?.caliper_dmax_points || primaryLesion?.caliper_dmax_points;
  const dorthPoints = m?.caliper_dorth_points || primaryLesion?.caliper_dorth_points;
  for (const points of [dmaxPoints, dorthPoints])
    if (points?.length === 2) {
      g.strokeStyle = "#fff";
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(...points[0]);
      g.lineTo(...points[1]);
      g.stroke();
    }
  const overlay = c.toDataURL();
  bitmap.close();
  return [original, binary, overlay];
}
export async function renderReport(root, id) {
  const rawId = String(id || "").split("?")[0];
  const studyId = decodeURIComponent(rawId);
  const options = new URLSearchParams(location.hash.split("?")[1] || "");
  const shouldAutoPrint = options.get("print") === "1";
  const requiredRevision = options.has("revision") ? Number(options.get("revision")) : null;

  root.innerHTML =
    pageHead(
      "Phiếu kết quả",
      "Bản nghiên cứu RUO; trạng thái rà soát và nguồn dữ liệu được ghi riêng cho từng bên.",
      button("← Quay lại máy trạm", "back-to-viewer", "small quiet") +
        " " +
        button("Tải hồ sơ kết quả", "export-research", "small") +
        " " +
        button("In bản RUO / Lưu PDF", "print", "primary"),
    ) + `<div id="reportData">${loading()}</div>`;
  const target = root.querySelector("#reportData"),
    identity = state.user?.id,
    token = state.token;
  let disposed = false, printTimer;
  const active = () => !disposed && root.isConnected && target.isConnected && root.contains(target) && identity === state.user?.id && token === state.token;
  const printBtn = root.querySelector("[data-action=print]");
  const exportBtn = root.querySelector("[data-action=export-research]");
  const backBtn = root.querySelector("[data-action=back-to-viewer]");
  if (backBtn) {
    backBtn.onclick = () => {
      location.hash = "#viewer/" + encodeURIComponent(studyId);
    };
  }
  const exportDisabledMessage =
    "Xuất dữ liệu nghiên cứu đang khóa đến khi có hồ sơ xác minh phê duyệt, consent và khử định danh.";
  printBtn.disabled = true;
  if (exportBtn) exportBtn.disabled = true;
  try {
    // Reports read server snapshots; opening one must not restore/mutate a viewer draft.
    const c = await getCase(studyId);
    if (!active()) return;
    if (requiredRevision !== null && (!Number.isSafeInteger(requiredRevision) ||
        c.review_revision !== requiredRevision || !c.images?.every(i => i.review?.review_id && i.review?.doctor_id)))
      throw Error("Phiên bản rà soát đã thay đổi hoặc chưa được máy chủ xác nhận. Mở lại máy trạm để kiểm tra trước khi in.");
    if (exportBtn) {
      exportBtn.disabled = false;
      exportBtn.title = exportDisabledMessage;
      exportBtn.setAttribute("aria-label", "Tải hồ sơ kết quả — xuất nghiên cứu đang khóa");
      exportBtn.onclick = () => toast(exportDisabledMessage, true);
    }
    if (!c.images || c.images.length === 0) {
      throw Error("Ca khám chưa có ảnh siêu âm. Vui lòng tải ảnh trong phần Tiếp nhận trước khi xuất phiếu.");
    }
    {
      for (const i of c.images) {
        if (i.review && (i.review.max_diameter_mm != null || i.review.total_area_cm2 != null)) {
          const prevM = i.measurements || i.prediction?.measurements || {};
          i.measurements = {
            ...prevM,
            calibrated: i.review.max_diameter_mm != null,
            max_diameter_mm: i.review.max_diameter_mm,
            ortho_diameter_mm: i.review.ortho_diameter_mm,
            total_area_cm2: i.review.total_area_cm2,
            calibration_source: i.review.max_diameter_mm != null ? "Đã hiệu chuẩn" : "Chưa hiệu chuẩn",
          };
        } else {
          const liveM = await request(
            "/api/images/" + i.image_id + "/measurements",
            { method: "POST", body: { rle_mask: i.review?.verified_mask_rle || i.prediction?.rle_mask || { shape: [512, 512], first_val: 0, counts: [262144] } } },
          );
          if (!active()) return;
          // Review without stored physical units stays uncalibrated; do not retrofit
          // a subsequently changed image calibration into the saved review.
          i.measurements = {
            ...liveM,
            ...(i.review ? { calibrated: false, max_diameter_mm: null, ortho_diameter_mm: null, total_area_cm2: null } : {}),
          };
        }
      }
    }
    const assets = await Promise.all(c.images.map(reportImages));
    if (!active()) return;
    target.innerHTML = `<article class="report"><header class="report-header"><div><img class="vinmec-logo" src="/static/assets/brand/vinmec-logo.png?v=20261018-transparent-logo" alt="Vinmec" width="100" height="62"><p class="eyebrow">HỖ TRỢ PHÂN ĐOẠN SIÊU ÂM</p><h1>Phiếu rà soát phân đoạn siêu âm</h1><p>Khảo sát buồng trứng hai bên</p></div><div class="mono">${esc(c.study_code || c.study_id)}</div></header><p class="report-notice">Bản nghiên cứu RUO · Chưa được xác thực lâm sàng · Không thay thế đánh giá của bác sĩ</p><div class="grid-2"><p>PID: <strong>${esc(c.patient_id)}</strong></p><p>Ngày khảo sát: ${esc(c.study_date)}</p></div>${c.images
      .map((i, index) => {
        const morphDesc = i.review?.morphology_description || i.morphologyDesc || i.morphology || i.review?.lesion_type || "Chưa ghi nhận";
        const notes = i.review?.clinical_notes || i.notes || "Chưa ghi nhận";
        const maskLabel = i.review?.review_id ? "Mask rà soát đã lưu" : i.prediction ? "Mask AI · chưa rà soát" : "Chưa có mask AI/rà soát";
        return `<section><h2>Buồng trứng ${i.laterality === "L" ? "trái" : i.laterality === "R" ? "phải" : "chưa xác định bên"}</h2><p class="report-review-status">${esc(reportReviewStatus(i))}</p><div class="report-images">${assets[index].map((url, n) => `<figure><img src="${url}" alt="${["Ảnh gốc", maskLabel, "Lớp phủ và thước đo"][n]}"><figcaption>${["Ảnh gốc", maskLabel, "Lớp phủ; caliper nếu có"][n]}</figcaption></figure>`).join("")}</div><table><thead><tr><th>d₁ × d₂</th><th>Diện tích</th><th>Hiệu chuẩn</th></tr></thead><tbody>${formatReportMeasurements(i)}</tbody></table><p>${formatOradsAttribution(i)}<br>Mô tả hình thái: ${esc(morphDesc)}<br>Ghi chú lâm sàng: ${esc(notes)}</p><p class="small">Mô hình: ${esc(i.prediction?.provenance?.architecture || i.prediction?.provenance?.model_name || i.prediction?.model_version || "Chưa có")}<br>SHA-256: <span class="mono">${esc(i.prediction?.provenance?.checkpoint_sha256 || i.prediction?.provenance?.model_checksum || "Bản ghi chưa cung cấp")}</span></p></section>`;
      })
      .join(
        "",
      )}<footer>Mã ca ${esc(c.study_id)} · Revision ${esc(c.review_revision ?? 0)} · Nguồn rà soát được ghi theo từng bên.<br>${c.images.every(i => i.review?.review_id && i.review?.doctor_id) ? "Bản rà soát nghiên cứu đã lưu." : "Bản nháp chưa rà soát đầy đủ; không phải kết quả đã xác nhận."}<br>Chưa có chữ ký số xác thực. </footer></article>`;
    target.prepend(researchDraftPanel(c));
    printBtn.disabled = false;
    printBtn.onclick = async () => {
      if (!active() || printBtn.disabled) return;
      printBtn.disabled = true;
      try {
        if (state.capabilities?.case_workflow === true) {
          await request(
              "/api/workspace/cases/" + c.study_id + "/report-export",
              { method: "POST", body: { version: c.version } },
            );
        }
        document.getElementById("printRoot")?.remove();
        const print = document.createElement("div");
        print.id = "printRoot";
        print.hidden = true;
        if (!active()) return;
        print.append(target.querySelector(".report").cloneNode(true));
        document.body.append(print);
        await Promise.all(
          [...print.querySelectorAll("img")].map((i) => i.decode()),
        );
        if (!active()) { print.remove(); return; }
        window.print();
      } catch (e) {
        if (active()) toast(e.message, true);
      } finally {
        if (active()) printBtn.disabled = false;
      }
    };
    if (shouldAutoPrint) {
      printTimer = setTimeout(() => {
        if (active() && !printBtn.disabled) {
          printBtn.click();
        }
      }, 350);
    }
    return () => { disposed = true; clearTimeout(printTimer); document.getElementById("printRoot")?.remove(); };
  } catch (e) {
    if (!active()) return;
    target.innerHTML = `<div class="banner warning" role="alert" style="padding:20px;display:flex;flex-direction:column;gap:12px;margin:24px 0">
      <div style="display:flex;align-items:center;gap:10px">
        <strong style="font-size:16px;color:var(--text,#0f172a)">Chưa thể hiển thị phiếu kết quả</strong>
      </div>
      <p style="margin:0;line-height:1.6;color:var(--muted,#64748b)">${esc(e.message)}</p>
      <div class="actions" style="margin-top:8px;display:flex;gap:12px">
        <a class="btn primary" href="#viewer/${encodeURIComponent(studyId)}">👉 Mở Máy trạm (Workstation) để xem ca này</a>
        <a class="btn" href="#cases">Danh sách ca khám</a>
      </div>
    </div>`;
  }
}
