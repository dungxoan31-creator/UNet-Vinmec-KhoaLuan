import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unavailableMeasurements, manualCaliperLength, applyCalibrationAck } from '../frontend/app/measurement-fallback.js';

test('failed server measurement stays unavailable while manual calibration survives', () => {
  const result = unavailableMeasurements({ calibrated: true, calibration_source: 'DICOM', pixel_spacing_mm: 0.2 }, null);
  assert.equal(result.max_diameter_px, null);
  assert.equal(result.ortho_diameter_px, null);
  assert.equal(result.total_area_px, null);
  assert.equal(result.max_diameter_mm, null);
  assert.equal(result.pixel_spacing_mm, 0.2);
  assert.equal(result.calibrated, true);
});

test('manual caliper never presents pixels as millimeters when spacing is lost', () => {
  const caliper = { points: [[0, 0], [30, 40]] };
  assert.equal(manualCaliperLength(caliper, true, undefined), null);
  assert.equal(manualCaliperLength(caliper, true, 0), null);
  assert.equal(manualCaliperLength(caliper, true, 0.2), 10);
  assert.equal(manualCaliperLength(caliper, false, undefined), 50);
});

test('missing or invalid physical scale cannot label pixels as millimeters', () => {
  for (const spacing of [undefined, 0, -1, Infinity]) {
    const result = unavailableMeasurements({ calibrated: true, pixel_spacing_mm: spacing }, null);
    assert.equal(result.calibrated, false);
    assert.equal(result.pixel_spacing_mm, null);
  }
});

test('calibration uses the committed server scale for both image and existing measurement', () => {
  const image = { image_id: 'img-a', pixel_spacing_mm: 0.3,
    measurements: { calibrated: true, pixel_spacing_mm: 0.3 } };
  applyCalibrationAck(image, { image_id: 'img-a', pixel_spacing_mm: 0.1235 });
  assert.equal(image.pixel_spacing_mm, 0.1235);
  assert.equal(image.measurements.pixel_spacing_mm, 0.1235);
  assert.equal(manualCaliperLength({ points: [[0, 0], [100, 0]] }, true, image.measurements.pixel_spacing_mm), 12.35);
});

test('invalid or wrong-image calibration acknowledgement cannot change state', () => {
  const image = { image_id: 'img-a', pixel_spacing_mm: 0.3, measurements: {} };
  assert.throws(() => applyCalibrationAck(image, { image_id: 'img-b', pixel_spacing_mm: 0.2 }));
  assert.throws(() => applyCalibrationAck(image, { image_id: 'img-a', pixel_spacing_mm: 0 }));
  assert.equal(image.pixel_spacing_mm, 0.3);
});
