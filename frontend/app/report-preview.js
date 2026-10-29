import { state } from "./state.js";
import { getCase } from "./cases.js";
import { protectedImage, request } from "./api.js";

import { letterbox } from "./coordinates.js";
import { $, esc, pageHead, button, loading, errorBox, toast } from "./ui.js";
import { buildResearchDraft } from "./research-report-draft.js";
import { isVerifiedResearchEnvironment, updateEnvironmentNotices } from "./environment-notices.js";

export const REPORT_IMAGE_MAX_DIMENSION = 2048;
export const REPORT_IMAGE_CONCURRENCY = 2;
export const REPORT_IMAGE_DECODE_TIMEOUT_MS = 45_000;

export async function withReportDecodeTimeout(decodePromise, timeoutMs = REPORT_IMAGE_DECODE_TIMEOUT_MS) {
  const timeout = Number.isFinite(timeoutMs) && timeoutMs > 0
    ? timeoutMs
    : REPORT_IMAGE_DECODE_TIMEOUT_MS;
  let timer;
  try {
    return await Promise.race([
      decodePromise,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error("Giải mã ảnh báo cáo quá thời gian cho phép; hãy thử tải lại.")),
          timeout,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

export function reportImageDimensions(width, height) {
  if (!Number.isSafeInteger(width) || width <= 0 || !Number.isSafeInteger(height) || height <= 0) {
    throw new Error("Kích thước ảnh báo cáo không hợp lệ.");
  }
  const scale = Math.min(1, REPORT_IMAGE_MAX_DIMENSION / Math.max(width, height));
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
    downscaled: scale < 1,
  };
}

export function reportImageSourceMatchesMetadata(image, width, height) {
  if (!Number.isSafeInteger(width) || width <= 0 || !Number.isSafeInteger(height) || height <= 0) return false;
  return [
    [image?.width, width],
    [image?.height, height],
  ].every(([stored, actual]) =>
    stored == null || (Number.isSafeInteger(stored) && stored === actual),
  );
}

export async function mapWithConcurrency(items, concurrency, mapper) {
  if (!Array.isArray(items) || typeof mapper !== "function" || !Number.isSafeInteger(concurrency) || concurrency < 1) {
    throw new TypeError("Danh sách, giới hạn đồng thời hoặc mapper không hợp lệ.");
  }
  const results = new Array(items.length);
  let nextIndex = 0;
  let failed = false;
  let firstError;
  const worker = async () => {
    while (!failed) {
      const index = nextIndex++;
      if (index >= items.length) return;
      try {
        results[index] = await mapper(items[index], index);
      } catch (error) {
        if (!failed) {
          failed = true;
          firstError = error;
        }
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker));
  if (failed) throw firstError;
  return results;
}

function researchDraftPanel(study) {
  const panel = document.createElement("details");
  panel.className = "research-report-draft";

  const heading = document.createElement("summary");
  heading.id = "researchDraftHeading";
  heading.textContent = "Tạo bản nháp nghiên cứu (chưa lưu vào hồ sơ)";
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
  return `<strong>${esc(value)}</strong>`;
}

export function reportReviewStatus(image) {
  const review = image?.review;
  if (review?.verified_mask_rle) return "Mask đã được bác sĩ rà soát";
  if (review?.review_id) return "Đã lưu lần rà soát · mask chưa xác nhận";
  if (image?.prediction?.rle_mask) return "Mask AI chưa được rà soát";
  return "Chưa có mask";
}

export function reportClinicalReviewStatus(image) {
  const review = image?.review;
  const morphology = Boolean(
    review?.morphology_description || image?.morphologyDesc || image?.morphology,
  );
  const orads = Boolean(review?.orads_score || review?.orads || image?.orads);
  return `Mô tả: ${morphology ? "đã ghi nhận" : "chưa ghi nhận"} · O-RADS: ${orads ? "đã ghi nhận" : "chưa ghi nhận"}`;
}

export function reportMaskSource(image) {
  if (image?.review?.verified_mask_rle) return "Lớp phủ đã được rà soát";
  if (image?.prediction?.rle_mask) return "Lớp phủ AI · chưa rà soát";
  return "Nguồn lớp phủ chưa xác định";
}

const formatReportNumber = (value) =>
  Number.isFinite(value) ? value.toFixed(2) : "Chưa ghi nhận";

const hasTrustedCalibrationSource = (source) => ["MANUAL", "DICOM"].includes(source);

export function savedReviewMeasurements(image) {
  const review = image?.review || {};
  const context = review.hitl_feedback?.measurement_context;
  const contextKnown = context && context.version === 1 && context.status === "AVAILABLE";
  const hasStoredPhysicalValues = [review.max_diameter_mm, review.ortho_diameter_mm, review.total_area_cm2]
    .some(Number.isFinite);
  const calibrated = Boolean(
    contextKnown && hasTrustedCalibrationSource(context.calibration_source) && hasStoredPhysicalValues,
  );
  const warning = calibrated
    ? (typeof context.warning === "string" ? context.warning : null)
    : hasStoredPhysicalValues
      ? "Nguồn hiệu chuẩn không được xác minh; số đo vật lý đã lưu bị ẩn."
      : contextKnown
        ? (typeof context.warning === "string" ? context.warning : null)
        : "Thông tin vùng bị loại khỏi phép đo chưa được lưu trong lần rà soát này.";
  return {
    calibrated,
    max_diameter_mm: calibrated ? review.max_diameter_mm : null,
    ortho_diameter_mm: calibrated ? review.ortho_diameter_mm : null,
    total_area_cm2: calibrated ? review.total_area_cm2 : null,
    calibration_source: calibrated
      ? context.calibration_source
      : hasStoredPhysicalValues ? "UNKNOWN" : "NONE",
    warning,
  };
}

function reportMeasurementValues(image) {
  const manual = image?.review?.hitl_feedback?.manual_measurements || {};
  const manualLabels = [...new Set([
    ...Object.keys(manual),
    ...(image?.review?.hitl_feedback?.manual_calipers || []).map((caliper) => caliper?.label),
  ])].filter((label) => ["D1", "D2"].includes(label));
  const hasManualCalipers = manualLabels.length > 0;
  if (!image?.mask?.some(Boolean) && !hasManualCalipers) return null;
  const measurements = image.measurements || {};
  const trustedImageCalibration = measurements.calibrated === true &&
    hasTrustedCalibrationSource(measurements.calibration_source);
  const trustedManualMeasurement = (value) => value?.calibrated === true &&
    hasTrustedCalibrationSource(value.calibration_source) && Number.isFinite(value.diameter_mm);
  const trustedManualCalipers = hasManualCalipers &&
    manualLabels.every((label) => trustedManualMeasurement(manual[label]));
  const calibrated = hasManualCalipers
    ? trustedManualCalipers && (!image?.mask?.some(Boolean) || trustedImageCalibration)
    : trustedImageCalibration;
  const sources = new Set();
  if (trustedImageCalibration) sources.add(measurements.calibration_source);
  if (trustedManualCalipers) {
    for (const label of manualLabels) sources.add(manual[label].calibration_source);
  }
  const calibrationSource = sources.size === 1 && ["DICOM", "MANUAL"].includes([...sources][0])
    ? [...sources][0] : "UNKNOWN";
  const manualValue = (label) => {
    if (!hasManualCalipers) return undefined;
    const value = manual[label];
    if (!value) return null;
    return calibrated ? value.diameter_mm : value.diameter_px;
  };
  const d1 = hasManualCalipers
    ? manualValue("D1")
    : calibrated ? measurements.max_diameter_mm : measurements.max_diameter_px;
  const d2 = hasManualCalipers
    ? manualValue("D2")
    : calibrated ? measurements.ortho_diameter_mm : measurements.ortho_diameter_px;
  const area = image?.mask?.some(Boolean)
    ? calibrated
      ? Number.isFinite(measurements.total_area_mm2)
        ? measurements.total_area_mm2
        : Number.isFinite(measurements.total_area_cm2)
          ? measurements.total_area_cm2 * 100
          : Number.NaN
      : measurements.total_area_px
    : Number.NaN;
  const diameterUnit = calibrated ? "mm" : "px";
  const areaUnit = calibrated ? "mm²" : "px²";
  const hasDiameter = Number.isFinite(d1) || Number.isFinite(d2);

  return {
    diameter: hasDiameter
      ? `${Number.isFinite(d1) ? formatReportNumber(d1) : "Chưa ghi nhận"} × ${Number.isFinite(d2) ? formatReportNumber(d2) : "Chưa ghi nhận"} ${diameterUnit}`
      : "Chưa ghi nhận",
    area: Number.isFinite(area) ? `${formatReportNumber(area)} ${areaUnit}` : "Chưa ghi nhận",
    calibrated,
    source: reportMaskSource(image),
    manual: hasManualCalipers,
    calibrationSource,
    warning: typeof measurements.warning === "string"
      ? measurements.warning
      : (measurements.calibrated === true || Object.values(manual).some((value) => value?.calibrated === true)) && !calibrated
        ? "Nguồn hiệu chuẩn không được xác minh; số đo vật lý đã lưu bị ẩn."
        : null,
  };
}

export function formatReportMeasurements(image) {
  const values = reportMeasurementValues(image);
  if (!values) {
    return '<p class="report-no-measurement">Chưa có vùng phân đoạn trong mask để hiển thị số đo.</p>';
  }

  const measurementNotes = [
    values.manual
      ? `D₁/D₂ theo caliper bác sĩ đã lưu; diện tích theo ${values.source}.`
      : `Nguồn số đo: ${values.source}.`,
    values.calibrated ? null : "Chưa hiệu chuẩn · số đo đang hiển thị theo pixel.",
    values.calibrated
      ? `Nguồn hiệu chuẩn: ${values.calibrationSource === "DICOM" ? "DICOM" : values.calibrationSource === "MANUAL" ? "nhập tay" : "chưa xác định"}.`
      : null,
    values.warning,
  ]
    .filter(Boolean)
    .map(esc)
    .join(" ");
  return `<dl class="report-measurements"><div><dt>Kích thước</dt><dd>${esc(values.diameter)}</dd></div><div><dt>Diện tích</dt><dd>${esc(values.area)}</dd></div></dl><p class="report-measurement-note">${measurementNotes}</p>`;
}

function reportLaterality(image) {
  return image?.laterality === "L"
    ? "Buồng trứng trái"
    : image?.laterality === "R"
      ? "Buồng trứng phải"
      : "Chưa xác định bên";
}

function reportSideName(side) {
  return side === "L" ? "BÊN TRÁI" : side === "R" ? "BÊN PHẢI" : "BÊN CHƯA XÁC ĐỊNH";
}

function reportDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value || "Chưa ghi nhận";
}

function reportSideOverview(images, side) {
  const summary = images.length
    ? `<p>${images.length} ảnh tĩnh đã được gắn với bên này. Số đo và nhận định được liệt kê riêng theo từng ảnh ở các trang hình ảnh.</p>`
    : '<p class="report-missing-side">Chưa có ảnh khảo sát bên này.</p>';
  return `<section class="report-result-side"><h3>${esc(reportSideName(side))}</h3>${summary}</section>`;
}

function reportEvidenceSide(entries, side) {
  if (!entries.length) {
    return `<section class="report-evidence-side"><h3>${esc(reportSideName(side))}</h3><p class="report-missing-side">Chưa có ảnh khảo sát bên này.</p></section>`;
  }

  const evidence = entries
    .map(({ image, assets, imageNumber }, index) => {
      const itemLabel = `<p class="report-entry-index">Ảnh ${imageNumber || index + 1}</p>`;
      const [original, overlay, downscaled] = assets;
      const resolutionNote = downscaled
        ? " · BẢN HIỂN THỊ GIẢM ĐỘ PHÂN GIẢI; xem ảnh nguồn trong máy trạm"
        : "";
      const morphology = image.review?.morphology_description || image.morphologyDesc || image.morphology || image.review?.lesion_type || "Chưa ghi nhận";
      const notes = image.review?.clinical_notes || image.notes || "Chưa ghi nhận";
      return `<article class="report-evidence-entry">${itemLabel}<p class="report-overlay-status">${esc(reportReviewStatus(image))}</p><div class="report-image-pair"><figure><img src="${original}" alt="Ảnh gốc ${esc(reportLaterality(image))}"><figcaption>ẢNH GỐC${resolutionNote}</figcaption></figure><figure><img src="${overlay}" alt="Lớp phủ trên ảnh ${esc(reportLaterality(image))}"><figcaption>LỚP PHỦ${resolutionNote}</figcaption></figure></div><p class="report-clinical-review-status">${esc(reportClinicalReviewStatus(image))}</p>${formatReportMeasurements(image)}<dl class="report-observations"><div><dt>O-RADS do bác sĩ ghi nhận</dt><dd>${formatOradsAttribution(image)}</dd></div><div><dt>Mô tả</dt><dd>${esc(morphology)}</dd></div><div><dt>Ghi chú</dt><dd>${esc(notes)}</dd></div></dl></article>`;
    })
    .join("");

  return `<section class="report-evidence-side"><h3>${esc(reportSideName(side))}</h3>${evidence}</section>`;
}

function reportTechnicalValue(entries, getter) {
  if (!entries.length) return "Chưa có trong bản ghi";
  const values = entries.map(({ image }) => getter(image) || "Chưa có trong bản ghi");
  const distinct = [...new Set(values)];
  if (distinct.length === 1) return distinct[0];
  return `Có ${distinct.length} giá trị khác nhau trên ${values.length} ảnh`;
}

function reportTechnicalInformation(entries) {
  const model = (image) =>
    image.prediction?.provenance?.architecture ||
    image.prediction?.provenance?.model_name ||
    image.prediction?.model_version ||
    null;
  const checksum = (image) =>
    image.prediction?.provenance?.checkpoint_sha256 ||
    image.prediction?.provenance?.model_checksum ||
    null;
  const reviewer = (image) => image.review?.doctor_id || null;

  return `<section class="report-support"><h2>THÔNG TIN HỖ TRỢ</h2><dl><div><dt>Model</dt><dd>${esc(reportTechnicalValue(entries, model))}</dd></div><div><dt>Checkpoint · SHA-256</dt><dd class="mono">${esc(reportTechnicalValue(entries, checksum))}</dd></div><div><dt>Reviewer ID</dt><dd>${esc(reportTechnicalValue(entries, reviewer))}</dd></div></dl></section>`;
}

export function renderReportDocument(study, assets) {
  const syntheticDemoDisclosure = state.capabilities?.synthetic_demo_mode === true
    ? '<div class="report-synthetic-demo-banner">DEMO DỮ LIỆU TỔNG HỢP · KHÔNG PHẢI HỒ SƠ BỆNH NHÂN</div>'
    : "";
  const orderedImages = study.images
    .map((image, index) => ({ image, assets: assets[index] }))
    .sort((a, b) => {
      const rank = (side) => (side === "L" ? 0 : side === "R" ? 1 : 2);
      return rank(a.image.laterality) - rank(b.image.laterality);
    })
    .map((entry, index) => ({ ...entry, imageNumber: index + 1 }));
  const sides = { L: [], R: [], U: [] };
  for (const entry of orderedImages) {
    const side = entry.image.laterality === "L" ? "L" : entry.image.laterality === "R" ? "R" : "U";
    sides[side].push(entry);
  }
  const status = study.images?.length && study.images.every((image) => image.review?.review_id)
    ? "Đã lưu rà soát cho các ảnh trong hồ sơ"
    : study.images?.some((image) => image.review?.review_id)
      ? "Đã lưu rà soát một phần"
      : "Chưa lưu rà soát";
  const caseCode = study.study_code || study.study_id || "Chưa ghi nhận";
  const visitNumber = study.visit_no || "Chưa được cấp";
  const pageCount = 1 + orderedImages.length;
  const evidencePages = orderedImages.map((entry, index) => {
    const side = entry.image.laterality === "L" ? "L" : entry.image.laterality === "R" ? "R" : "U";
    const oneSide = { L: [], R: [], U: [] };
    oneSide[side].push(entry);
    const body = side === "U"
      ? `<div class="report-evidence-unassigned"><h2>ẢNH CHƯA XÁC ĐỊNH BÊN</h2>${reportEvidenceSide(oneSide.U, "U")}</div>`
      : `<div class="report-evidence-grid single-column">${reportEvidenceSide(oneSide[side], side)}</div>`;
  return `<section class="report-page report-evidence-page"><header class="report-evidence-header"><h1>HÌNH ẢNH KHẢO SÁT · ẢNH ${entry.imageNumber}</h1><div class="report-patient-line"><p>PID: <strong>${esc(study.patient_id || "Chưa ghi nhận")}</strong></p><p>Visit: <strong>${esc(visitNumber)}</strong></p><p>${esc(reportLaterality(entry.image))}</p></div></header><div class="report-ruo-banner"><strong>BẢN NGHIÊN CỨU (RUO)</strong><span>Chưa được xác thực lâm sàng · Không dùng cho chăm sóc bệnh nhân · Không thay thế đánh giá của bác sĩ · Nguồn dữ liệu chưa được xác minh · Chưa có chữ ký số</span></div>${syntheticDemoDisclosure}${body}<section class="report-note-block report-image-notes"><h2>LƯU Ý</h2><ul><li>Lớp phủ chỉ mang tính hỗ trợ; cần đối chiếu ảnh gốc.</li><li>Trạng thái đã lưu rà soát mask không đồng nghĩa đã hoàn tất mô tả hoặc phân tầng.</li><li>Phiếu không có chữ ký số xác thực và không dùng để chỉ định điều trị.</li></ul></section><footer class="report-footer"><span>Study ID: ${esc(study.study_id)}</span><span>Revision: ${esc(study.review_revision ?? 0)}</span><span>Trang ${index + 2}/${pageCount}</span></footer></section>`;
  }).join("");

  return `<article class="report" aria-label="Kết quả khảo sát buồng trứng">
    <section class="report-page report-summary-page">
      <header class="report-header">
        <h1>KẾT QUẢ KHẢO SÁT</h1>
      </header>
      <div class="report-ruo-banner"><strong>BẢN NGHIÊN CỨU (RUO)</strong><span>Chưa được xác thực lâm sàng · Không dùng cho chăm sóc bệnh nhân · Không thay thế đánh giá của bác sĩ · Nguồn dữ liệu chưa được xác minh · Chưa có chữ ký số</span></div>
      ${syntheticDemoDisclosure}
      <div class="report-patient-line"><p>PID: <strong>${esc(study.patient_id || "Chưa ghi nhận")}</strong></p><p>Visit: <strong>${esc(visitNumber)}</strong></p><p>Ngày khảo sát: <strong>${esc(reportDate(study.study_date))}</strong></p></div>

      <section class="report-block report-case-block">
        <h2>THÔNG TIN CA</h2>
        <dl><div><dt>Mã ca</dt><dd>${esc(caseCode)}</dd></div><div><dt>Trạng thái lưu rà soát</dt><dd>${esc(status)}</dd><small>Trạng thái lưu không xác nhận đã hoàn tất mô tả, O-RADS hoặc kết luận.</small></div></dl>
      </section>

      <section class="report-block report-results-block">
        <h2>KẾT QUẢ GHI NHẬN</h2>
        <div class="report-results-grid">${reportSideOverview(sides.L.map(({ image }) => image), "L")}${reportSideOverview(sides.R.map(({ image }) => image), "R")}</div>
        ${sides.U.length ? `<div class="report-unassigned">${reportSideOverview(sides.U.map(({ image }) => image), "U")}</div>` : ""}
      </section>

      ${reportTechnicalInformation(orderedImages)}

      <section class="report-note-block">
        <h2>LƯU Ý</h2>
        <p>Số đo hỗ trợ được tính từ lớp phủ và ghi rõ nguồn ngay dưới số đo; ảnh gốc cùng lớp phủ được trình bày ở phần hình ảnh. Mô tả và O-RADS chỉ hiển thị khi có trong bản ghi rà soát. Hệ thống không tự đưa ra kết luận chẩn đoán. Phiếu này chưa phải hướng dẫn theo dõi hoặc điều trị cho bệnh nhân.</p>
      </section>

      <footer class="report-footer"><span>Study ID: ${esc(study.study_id)}</span><span>Revision: ${esc(study.review_revision ?? 0)}</span><span>Trang 1/${pageCount}</span></footer>
    </section>
    ${evidencePages}
  </article>`;
}

async function reportImages(i) {
  const url = await protectedImage("/api/images/" + i.image_id + "/source.png");
  let sourceImage;
  try {
    sourceImage = new Image();
    sourceImage.src = url;
    await withReportDecodeTimeout(sourceImage.decode());
    if (!i.mask || i.mask.length !== 512 * 512) {
      throw new Error("Mask báo cáo không có kích thước 512 × 512 đã kiểm tra.");
    }
    const sourceWidth = sourceImage.naturalWidth;
    const sourceHeight = sourceImage.naturalHeight;
    if (!reportImageSourceMatchesMetadata(i, sourceWidth, sourceHeight)) {
      throw new Error("Kích thước ảnh nguồn khác với snapshot; không thể căn chỉnh caliper chính xác.");
    }
    const dimensions = reportImageDimensions(sourceWidth, sourceHeight);
    const c = document.createElement("canvas");
    c.width = dimensions.width;
    c.height = dimensions.height;
    const g = c.getContext("2d");
    if (!g) throw new Error("Không thể khởi tạo canvas báo cáo.");
    g.imageSmoothingEnabled = true;
    g.imageSmoothingQuality = "high";
    g.drawImage(sourceImage, 0, 0, dimensions.width, dimensions.height);
    const original = c.toDataURL();
    const mask = document.createElement("canvas");
    mask.width = mask.height = 512;
    const mg = mask.getContext("2d");
    if (!mg) throw new Error("Không thể khởi tạo lớp phủ báo cáo.");
    const pixels = mg.createImageData(512, 512);
    for (let n = 0; n < i.mask.length; n++) {
      if (i.mask[n]) {
        const offset = n * 4;
        pixels.data[offset] = 98;
        pixels.data[offset + 1] = 233;
        pixels.data[offset + 2] = 224;
        pixels.data[offset + 3] = 255;
      }
    }
    mg.putImageData(pixels, 0, 0);
    const box = letterbox(dimensions.width, dimensions.height);
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
    const drawCaliper = (points, color, lineWidth) => {
      if (!Array.isArray(points) || points.length !== 2 || points.some(
        (point) => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite),
      )) return;
      const scaledPoints = points.map(([x, y]) => [
        x * dimensions.width / sourceWidth,
        y * dimensions.height / sourceHeight,
      ]);
      g.strokeStyle = color;
      g.lineWidth = lineWidth;
      g.beginPath();
      g.moveTo(...scaledPoints[0]);
      g.lineTo(...scaledPoints[1]);
      g.stroke();
    };
    for (const points of [dmaxPoints, dorthPoints]) {
      if (Array.isArray(points) && points.length === 2) {
        drawCaliper(points, "#fff", 2);
      }
    }
    const manualCalipers = i.review?.hitl_feedback?.manual_calipers || [];
    for (const caliper of manualCalipers) {
      if (caliper?.coordinate_space !== "decoded-source-image" ||
          !["D1", "D2"].includes(caliper.label) || !Array.isArray(caliper.points) ||
          caliper.points.length !== 2 || caliper.points.some(point => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))) continue;
      const points = caliper.points.map(([x, y]) => [
        x * dimensions.width / sourceWidth,
        y * dimensions.height / sourceHeight,
      ]);
      drawCaliper(points, "#101820", Math.max(3, dimensions.width / 400));
      drawCaliper(points, "#ffbf47", Math.max(1.5, dimensions.width / 900));
      g.font = `bold ${Math.max(14, dimensions.width / 45)}px system-ui, sans-serif`;
      g.lineWidth = Math.max(3, dimensions.width / 500);
      g.strokeStyle = "#101820";
      g.strokeText(`BS · ${caliper.label}`, (points[0][0] + points[1][0]) / 2 + 5, (points[0][1] + points[1][1]) / 2 - 5);
      g.fillStyle = "#ffbf47";
      g.fillText(`BS · ${caliper.label}`, (points[0][0] + points[1][0]) / 2 + 5, (points[0][1] + points[1][1]) / 2 - 5);
    }
    const overlay = c.toDataURL();
    return [original, overlay, dimensions.downscaled];
  } finally {
    if (sourceImage) sourceImage.src = "data:,";
    URL.revokeObjectURL(url);
  }
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

  const verifyEnvironment = async () => {
    try {
      const capabilities = await request("/api/capabilities");
      if (!active()) return false;
      const currentCapabilities = capabilities && typeof capabilities === "object" && !Array.isArray(capabilities)
        ? capabilities
        : {};
      state.capabilities = currentCapabilities;
      updateEnvironmentNotices();
      return isVerifiedResearchEnvironment(currentCapabilities);
    } catch {
      if (active()) {
        state.capabilities = {};
        updateEnvironmentNotices();
      }
      return false;
    }
  };

  const showEnvironmentBlock = () => {
    printBtn.disabled = true;
    if (exportBtn) exportBtn.disabled = true;
    target.innerHTML = `<section class="banner warning report-environment-block" role="alert">
      <strong>Đã khóa phiếu vì chưa xác minh được môi trường dữ liệu.</strong>
      <p>Không tải nội dung ca hoặc cho phép in cho đến khi máy chủ xác nhận chế độ RUO, trạng thái xác thực và nguồn dữ liệu.</p>
      <button class="btn small" type="button" data-action="retry-environment">Kiểm tra lại môi trường</button>
      <p class="muted small" data-environment-status aria-live="polite"></p>
    </section>`;
    const retryEnvironment = target.querySelector("[data-action=retry-environment]");
    retryEnvironment.onclick = async () => {
      retryEnvironment.disabled = true;
      const verified = await verifyEnvironment();
      if (!active()) return;
      if (verified) {
        window.dispatchEvent(new Event("ova:rerender"));
        return;
      }
      target.querySelector("[data-environment-status]").textContent =
        "Chưa xác minh được. Nút in vẫn bị khóa; kiểm tra kết nối rồi thử lại.";
      retryEnvironment.disabled = false;
    };
  };

  if (!(await verifyEnvironment())) {
    if (!active()) return;
    showEnvironmentBlock();
    return () => { disposed = true; clearTimeout(printTimer); };
  }

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
        if (i.review && (i.review.max_diameter_mm != null || i.review.ortho_diameter_mm != null || i.review.total_area_cm2 != null)) {
          i.measurements = savedReviewMeasurements(i);
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
    const assets = await mapWithConcurrency(c.images, REPORT_IMAGE_CONCURRENCY, reportImages);
    if (!active()) return;
    target.innerHTML = renderReportDocument(c, assets);
    target.prepend(researchDraftPanel(c));
    printBtn.disabled = false;
    printBtn.onclick = async () => {
      if (!active() || printBtn.disabled) return;
      printBtn.disabled = true;
      try {
        if (!(await verifyEnvironment())) {
          if (active()) showEnvironmentBlock();
          return;
        }
        if (!active()) return;
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
        if (active() && target.querySelector(".report")) printBtn.disabled = false;
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
        <strong class="report-error-title">Chưa thể hiển thị phiếu kết quả</strong>
      </div>
      <p class="report-error-description">${esc(e.message)}</p>
      <div class="actions" style="margin-top:8px;display:flex;gap:12px">
        <button type="button" class="btn primary" data-action="retry-report">Thử tải lại phiếu</button>
        <a class="btn primary" href="#viewer/${encodeURIComponent(studyId)}">Mở máy trạm để xem ca này</a>
        <a class="btn" href="#cases">Danh sách ca khám</a>
      </div>
    </div>`;
    const retry = target.querySelector("[data-action=retry-report]");
    if (retry)
      retry.onclick = () => window.dispatchEvent(new Event("ova:rerender"));
  }
}
