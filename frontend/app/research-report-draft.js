const disclosure =
  "Bản nháp nghiên cứu RUO; chưa được xác thực lâm sàng và không thay thế nhận định của bác sĩ.";

const textValue = (...values) =>
  values.find((value) => typeof value === "string" && value.trim())?.trim() ||
  null;

const numberValue = (value) =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const formatNumber = (value) => value.toFixed(2);

export function buildResearchDraft({ studyCode, image } = {}) {
  const lines = [];
  const missingFields = [];
  const code = textValue(studyCode);
  const laterality =
    image?.laterality === "L"
      ? "Buồng trứng trái"
      : image?.laterality === "R"
        ? "Buồng trứng phải"
        : null;
  const review = image?.review || {};

  if (code) lines.push(`Mã ca: ${code}`);
  else missingFields.push("Mã ca");
  if (laterality) lines.push(`Bên: ${laterality}`);
  else missingFields.push("Bên khảo sát");

  const orads = textValue(review.orads_score, review.orads, image?.orads);
  const morphology = textValue(
    review.morphology_description,
    image?.morphologyDesc,
  );
  const notes = textValue(review.clinical_notes, image?.notes);

  if (orads)
    lines.push(`O-RADS do bác sĩ ghi nhận: ${orads}`);
  else missingFields.push("O-RADS do bác sĩ ghi nhận");
  if (morphology)
    lines.push(`Mô tả hình thái do bác sĩ ghi nhận: ${morphology}`);
  else missingFields.push("Mô tả hình thái do bác sĩ ghi nhận");
  if (notes)
    lines.push(`Ghi chú lâm sàng do bác sĩ ghi nhận: ${notes}`);
  else missingFields.push("Ghi chú lâm sàng do bác sĩ ghi nhận");

  const measurements = image?.measurements || {};
  const manual = image?.review?.hitl_feedback?.manual_measurements || {};
  const hasManualCalipers = Object.keys(manual).some((key) => ["D1", "D2"].includes(key));
  const calibrated = measurements.calibrated === true ||
    (hasManualCalipers && Object.values(manual).some((value) => value?.calibrated === true));
  const diameterUnit = calibrated ? "mm" : "px";
  const areaUnit = calibrated ? "cm²" : "px²";
  const d1 = numberValue(hasManualCalipers
    ? (calibrated ? manual.D1?.diameter_mm : manual.D1?.diameter_px)
    : (calibrated ? measurements.max_diameter_mm : measurements.max_diameter_px));
  const d2 = numberValue(hasManualCalipers
    ? (calibrated ? manual.D2?.diameter_mm : manual.D2?.diameter_px)
    : (calibrated ? measurements.ortho_diameter_mm : measurements.ortho_diameter_px));
  const area = numberValue(
    calibrated ? measurements.total_area_cm2 : measurements.total_area_px,
  );

  if (d1 !== null && d2 !== null)
    lines.push(
      `Kích thước: ${formatNumber(d1)} × ${formatNumber(d2)} ${diameterUnit}`,
    );
  else
    missingFields.push(
      `Kích thước d₁ × d₂ (${diameterUnit})`,
    );
  if (area !== null)
    lines.push(`Diện tích: ${formatNumber(area)} ${areaUnit}`);
  else missingFields.push(`Diện tích (${areaUnit})`);
  if (typeof measurements.warning === "string" && measurements.warning.trim())
    lines.push(`Cảnh báo số đo: ${measurements.warning.trim()}`);

  if (calibrated) {
    const volume = numberValue(measurements.total_volume_cm3);
    if (volume !== null)
      lines.push(`Thể tích: ${formatNumber(volume)} cm³`);
    else missingFields.push("Thể tích (cm³)");
    const source = textValue(measurements.calibration_source);
    if (source) lines.push(`Hiệu chuẩn: ${source}`);
  } else {
    missingFields.push("Thể tích (chưa hiệu chuẩn)");
  }

  if (missingFields.length)
    lines.push(`Trường còn thiếu: ${missingFields.join("; ")}`);

  return {
    text: lines.join("\n"),
    missingFields,
    disclosure: calibrated
      ? disclosure
      : `${disclosure} Chưa hiệu chuẩn: chỉ hiển thị số đo px/px², không quy đổi sang đơn vị thực.`,
  };
}
