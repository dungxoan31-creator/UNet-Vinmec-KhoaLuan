// Worker geometry uses a different method from the server's minAreaRect.
// Keep manual caliper calibration but never substitute worker proxy values.
export function unavailableMeasurements(measurements, imageSpacing) {
  const spacing = measurements?.pixel_spacing_mm ?? imageSpacing;
  const calibrated = Boolean(measurements?.calibrated) && Number.isFinite(spacing) && spacing > 0;
  return {
    max_diameter_px: null,
    ortho_diameter_px: null,
    total_area_px: null,
    max_diameter_mm: null,
    ortho_diameter_mm: null,
    total_area_cm2: null,
    calibrated,
    calibration_source: measurements?.calibration_source,
    pixel_spacing_mm: calibrated ? spacing : null,
  };
}

export function manualCaliperLength(caliper, physical, spacing) {
  const pixels = Math.hypot(
    caliper.points[1][0] - caliper.points[0][0],
    caliper.points[1][1] - caliper.points[0][1],
  );
  if (!physical) return pixels;
  return Number.isFinite(spacing) && spacing > 0 ? pixels * spacing : null;
}

export function applyCalibrationAck(image, response) {
  if (!image || response?.image_id !== image.image_id ||
      !Number.isFinite(response.pixel_spacing_mm) || response.pixel_spacing_mm <= 0) {
    throw new Error("Máy chủ chưa xác nhận hiệu chuẩn hợp lệ cho ảnh này.");
  }
  image.pixel_spacing_mm = response.pixel_spacing_mm;
  if (image.measurements) {
    image.measurements.calibrated = true;
    image.measurements.calibration_source = "MANUAL";
    image.measurements.pixel_spacing_mm = response.pixel_spacing_mm;
  }
}
