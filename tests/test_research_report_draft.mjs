import assert from "node:assert/strict";
import test from "node:test";

import { buildResearchDraft } from "../frontend/app/research-report-draft.js";

test("test_research_draft_uses_only_reviewed_values", () => {
  const { text, missingFields, disclosure } = buildResearchDraft({
    studyCode: "CASE-01",
    image: {
      laterality: "L",
      orads: "O-RADS 5 (legacy draft)",
      morphologyDesc: "Mô tả chưa lưu",
      notes: "Ghi chú chưa lưu",
      review: {
        orads_score: "O-RADS 3",
        morphology_description: "Nang đơn thùy",
        clinical_notes: "Bờ đều",
      },
      measurements: {
        calibrated: true,
        max_diameter_mm: 12.5,
        ortho_diameter_mm: 8,
        total_area_cm2: 0.42,
        total_volume_cm3: 0.85,
        max_diameter_px: 250,
        ortho_diameter_px: 160,
        total_area_px: 20000,
        calibration_source: "DICOM PixelSpacing",
      },
    },
  });

  assert.equal(text, [
    "Mã ca: CASE-01",
    "Bên: Buồng trứng trái",
    "O-RADS do bác sĩ ghi nhận: O-RADS 3",
    "Mô tả hình thái do bác sĩ ghi nhận: Nang đơn thùy",
    "Ghi chú lâm sàng do bác sĩ ghi nhận: Bờ đều",
    "Kích thước: 12.50 × 8.00 mm",
    "Diện tích: 0.42 cm²",
    "Thể tích: 0.85 cm³",
    "Hiệu chuẩn: DICOM PixelSpacing",
  ].join("\n"));
  assert.deepEqual(missingFields, []);
  assert.match(disclosure, /RUO/);
  assert.match(disclosure, /chưa được xác thực lâm sàng/i);
  assert.doesNotMatch(text, /legacy draft|chưa lưu|20000|250/);
});

test("test_research_draft_lists_missing_fields", () => {
  const result = buildResearchDraft({
    studyCode: "CASE-02",
    image: { laterality: "R", measurements: {} },
  });

  assert.deepEqual(result.missingFields, [
    "O-RADS do bác sĩ ghi nhận",
    "Mô tả hình thái do bác sĩ ghi nhận",
    "Ghi chú lâm sàng do bác sĩ ghi nhận",
    "Kích thước d₁ × d₂ (px)",
    "Diện tích (px²)",
    "Thể tích (chưa hiệu chuẩn)",
  ]);
  assert.match(result.text, /Trường còn thiếu:/);
  for (const field of result.missingFields) assert.ok(result.text.includes(field));
});

test("test_research_draft_uses_pixels_when_uncalibrated", () => {
  const result = buildResearchDraft({
    studyCode: "CASE-03",
    image: {
      laterality: "R",
      measurements: {
        calibrated: false,
        max_diameter_px: 42,
        ortho_diameter_px: 21,
        total_area_px: 600,
        max_diameter_mm: 20,
        ortho_diameter_mm: 10,
        total_area_cm2: 0.2,
        total_volume_cm3: 0.1,
      },
    },
  });

  assert.match(result.text, /Kích thước: 42\.00 × 21\.00 px/);
  assert.match(result.text, /Diện tích: 600\.00 px²/);
  assert.doesNotMatch(result.text, /mm|cm[²³]?/);
  assert.match(result.disclosure, /chưa hiệu chuẩn/i);
  assert.ok(result.missingFields.includes("Thể tích (chưa hiệu chuẩn)"));
});

test("test_research_draft_omits_nonfinite_measurements", () => {
  const result = buildResearchDraft({
    studyCode: "CASE-04",
    image: {
      laterality: "L",
      measurements: {
        calibrated: true,
        max_diameter_mm: Number.NaN,
        ortho_diameter_mm: Number.POSITIVE_INFINITY,
        total_area_cm2: 0.4,
        total_volume_cm3: Number.NEGATIVE_INFINITY,
      },
    },
  });

  assert.doesNotMatch(result.text, /NaN|Infinity/);
  assert.match(result.text, /Diện tích: 0\.40 cm²/);
  assert.ok(result.missingFields.includes("Kích thước d₁ × d₂ (mm)"));
  assert.ok(result.missingFields.includes("Thể tích (cm³)"));
});

test("test_research_draft_never_emits_management", () => {
  const result = buildResearchDraft({
    studyCode: "CASE-05",
    image: { laterality: "L", measurements: {} },
  });

  assert.doesNotMatch(result.text, /chẩn đoán|nguy cơ ác tính|phẫu thuật|điều trị|khuyến nghị xử trí/i);
  assert.doesNotMatch(result.disclosure, /chẩn đoán|nguy cơ ác tính|phẫu thuật|điều trị|khuyến nghị xử trí/i);
});

test("test_research_draft_preserves_html_like_note_as_literal_text", () => {
  const clinicianText = "<img src=x onerror=alert(1)>";
  const result = buildResearchDraft({
    studyCode: "CASE-06",
    image: {
      laterality: "L",
      review: { clinical_notes: clinicianText },
      measurements: {},
    },
  });

  assert.ok(result.text.includes(clinicianText), "the draft preserves the clinician's literal note");
  assert.doesNotMatch(result.text, /<\/?(script|iframe)\b/i,
    "the builder does not generate executable markup, while the browser test covers DOM rendering");
});
