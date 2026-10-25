import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildResearchDraft } from '../frontend/app/research-report-draft.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const reportPreviewFile = path.resolve(__dirname, '../frontend/app/report-preview.js');
const workspaceCssFile = path.resolve(__dirname, '../frontend/css/workspace.css');

const content = fs.readFileSync(reportPreviewFile, 'utf8');
const workspaceCss = fs.readFileSync(workspaceCssFile, 'utf8');
const { formatOradsAttribution, formatReportMeasurements, reportReviewStatus } = await import('../frontend/app/report-preview.js');

test('reviewer attribution requires a persisted review and never falls back to the viewer', () => {
  assert.match(reportReviewStatus({ review: null }), /Chưa có rà soát được lưu/);
  assert.match(reportReviewStatus({ review: { doctor_id: 'current-viewer' } }), /Chưa có rà soát được lưu/);
  const saved = { review: { review_id: 'revision-L', doctor_id: 'actual-reviewer' } };
  assert.match(reportReviewStatus(saved), /actual-reviewer/);
  assert.match(reportReviewStatus(saved), /revision-L/);
});

assert.equal(
  formatOradsAttribution({ review: { orads_score: 'O-RADS 3' } }),
  'O-RADS do bác sĩ ghi nhận: <strong>O-RADS 3</strong>',
  'Saved clinician-entered O-RADS must stay attributed to the doctor in the report.',
);
assert.equal(
  formatOradsAttribution({}),
  'O-RADS do bác sĩ ghi nhận: <strong>Chưa ghi nhận</strong>',
  'An absent O-RADS value must not read like a CDSS classification.',
);
for (const missingImage of [null, undefined]) {
  assert.equal(
    formatOradsAttribution(missingImage),
    'O-RADS do bác sĩ ghi nhận: <strong>Chưa ghi nhận</strong>',
    'A missing image record must not break report rendering or imply a classification.',
  );
}
assert.equal(
  formatOradsAttribution({ orads: '<script>alert(1)</script>' }),
  'O-RADS do bác sĩ ghi nhận: <strong>&lt;script&gt;alert(1)&lt;/script&gt;</strong>',
  'Dynamic O-RADS text must remain escaped in the printed report.',
);
assert(
  content.includes('${formatOradsAttribution(i)}'),
  'The report template must use the clinician-attribution formatter.',
);

const emptyMaskRows = formatReportMeasurements({
  mask: new Uint8Array(512 * 512),
  measurements: {
    has_lesion: false,
    calibrated: true,
    max_diameter_mm: 0,
    ortho_diameter_mm: 0,
    total_area_cm2: 0,
  },
});
assert(emptyMaskRows.includes('Không có vùng phân đoạn trong mask được lưu'));
assert(emptyMaskRows.includes('không phải kết luận về tình trạng lâm sàng'));
assert(!emptyMaskRows.includes('0.00'));

const measuredRows = formatReportMeasurements({
  mask: new Uint8Array([1]),
  measurements: {
    calibrated: true,
    max_diameter_mm: 12.5,
    ortho_diameter_mm: 8,
    total_area_cm2: 0.42,
    calibration_source: 'DICOM',
  },
});
assert(measuredRows.includes('12.50 × 8.00 mm'));
assert(measuredRows.includes('0.42 cm²'));
assert(measuredRows.includes('DICOM'));
assert(
  content.includes('${formatReportMeasurements(i)}'),
  'The report table must use its tested measurement formatter.',
);

// FE-02: report-preview.js must render saved O-RADS and morphology description
assert(
  content.includes('orads_score') || content.includes('Phân loại O-RADS'),
  "FE-02 VULNERABILITY: report-preview.js does not render saved O-RADS classification!"
);
assert(
  content.includes('morphology_description'),
  "FE-02 VULNERABILITY: report-preview.js does not render saved morphology description!"
);
assert(
  !content.includes('window.prompt') && !content.includes('window.confirm'),
  'Research export must not treat client-entered approval or consent as verified evidence.'
);
assert(
  content.includes('exportDisabledMessage'),
  'Research export must explain that it is disabled until trusted verification is available.'
);

const printImageRule = workspaceCss.match(
  /@media print[\s\S]*?\.report-images img\s*\{([^{}]*)\}/,
);
assert(printImageRule, 'The active print stylesheet must bound report image height.');
assert.match(printImageRule[1], /max-height:\s*80mm/);
assert.match(printImageRule[1], /height:\s*auto/);
assert.match(printImageRule[1], /object-fit:\s*contain/);
const printSectionRule = workspaceCss.match(
  /@media print[\s\S]*?\.report section\s*\{([^{}]*)\}/,
);
assert(printSectionRule, 'The active print stylesheet must allow long sections to span pages.');
assert.match(printSectionRule[1], /break-inside:\s*auto/);

console.log('PASS: FE-02 report content and active print bounds/pagination rules');

test('test_research_report_preview_renders_html_like_text_as_inert', () => {
  const literal = '<img src=x onerror=alert(1)>';
  const draft = buildResearchDraft({
    studyCode: 'CASE-HTML',
    image: {
      laterality: 'L',
      review: { clinical_notes: literal },
      measurements: {},
    },
  });

  assert.ok(draft.text.includes(literal), 'Clinician-entered text is preserved as data.');
  assert.equal(draft.text.includes('<script>'), false);
});
