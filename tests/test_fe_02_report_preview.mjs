import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildResearchDraft } from '../frontend/app/research-report-draft.js';
import { isVerifiedResearchEnvironment } from '../frontend/app/environment-notices.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const reportPreviewFile = path.resolve(__dirname, '../frontend/app/report-preview.js');
const indexFile = path.resolve(__dirname, '../frontend/index.html');

const content = fs.readFileSync(reportPreviewFile, 'utf8');
const indexHtml = fs.readFileSync(indexFile, 'utf8');
const {
  formatOradsAttribution,
  formatReportMeasurements,
  mapWithConcurrency,
  renderReportDocument,
  reportImageDimensions,
  reportImageSourceMatchesMetadata,
  reportMaskSource,
  reportReviewStatus,
  savedReviewMeasurements,
  withReportDecodeTimeout,
} = await import('../frontend/app/report-preview.js');

test('report environment verification requires explicit RUO and clinical gate capabilities', () => {
  assert.equal(isVerifiedResearchEnvironment({}), false);
  assert.equal(isVerifiedResearchEnvironment({ synthetic_demo_mode: true }), false);
  assert.equal(isVerifiedResearchEnvironment({
    synthetic_demo_mode: false,
    research_use_only: true,
    clinical_production_ready: true,
    clinical_validation_status: 'BLOCKED',
  }), false);
  assert.equal(isVerifiedResearchEnvironment({
    synthetic_demo_mode: true,
    synthetic_demo_uploads_restricted: true,
    research_use_only: true,
    clinical_production_ready: false,
    clinical_validation_status: 'BLOCKED',
    case_workflow: false,
    research_export: false,
  }), true);
  assert.equal(isVerifiedResearchEnvironment({
    synthetic_demo_mode: false,
    synthetic_demo_uploads_restricted: false,
    research_use_only: true,
    clinical_production_ready: false,
    clinical_validation_status: 'BLOCKED',
    case_workflow: false,
    research_export: false,
  }), true);
});

test('report environment verification rejects contradictory synthetic and clinical workflow flags', () => {
  const verifiedSyntheticMode = {
    synthetic_demo_mode: true,
    synthetic_demo_uploads_restricted: true,
    research_use_only: true,
    clinical_production_ready: false,
    clinical_validation_status: 'BLOCKED',
    case_workflow: false,
    research_export: false,
  };
  assert.equal(isVerifiedResearchEnvironment(verifiedSyntheticMode), true);
  assert.equal(isVerifiedResearchEnvironment({
    ...verifiedSyntheticMode,
    synthetic_demo_uploads_restricted: false,
  }), false);
  assert.equal(isVerifiedResearchEnvironment({
    ...verifiedSyntheticMode,
    case_workflow: true,
  }), false);
  assert.equal(isVerifiedResearchEnvironment({
    ...verifiedSyntheticMode,
    research_export: true,
  }), false);
  assert.equal(isVerifiedResearchEnvironment({
    ...verifiedSyntheticMode,
    synthetic_demo_mode: false,
    synthetic_demo_uploads_restricted: true,
  }), false);
});

test('report images are reduced to a printable bound and invalid source dimensions fail closed', () => {
  assert.deepEqual(reportImageDimensions(800, 600), {
    width: 800,
    height: 600,
    downscaled: false,
  });
  assert.deepEqual(reportImageDimensions(6000, 4000), {
    width: 2048,
    height: 1365,
    downscaled: true,
  });
  assert.throws(() => reportImageDimensions(0, 600), /kích thước ảnh báo cáo không hợp lệ/i);
  assert.throws(() => reportImageDimensions(Number.MAX_SAFE_INTEGER + 1, 600), /kích thước ảnh báo cáo không hợp lệ/i);
  assert.equal(reportImageSourceMatchesMetadata({ width: 6000, height: 4000 }, 6000, 4000), true);
  assert.equal(reportImageSourceMatchesMetadata({ width: 512, height: 512 }, 6000, 4000), false);
  assert.equal(reportImageSourceMatchesMetadata({ width: 0, height: 512 }, 512, 512), false);
});

test('report image worker bounds concurrent decodes and stops scheduling after failure', async () => {
  let active = 0;
  let peak = 0;
  const ordered = await mapWithConcurrency([0, 1, 2, 3], 2, async (value) => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    active -= 1;
    return value * 2;
  });
  assert.deepEqual(ordered, [0, 2, 4, 6]);
  assert.equal(peak, 2);

  const started = [];
  await assert.rejects(
    mapWithConcurrency([0, 1, 2], 1, async (value) => {
      started.push(value);
      if (value === 1) throw new Error('decode failed');
      return value;
    }),
    /decode failed/,
  );
  assert.deepEqual(started, [0, 1]);
});

test('report image decode has a bounded timeout and preserves decode errors', async () => {
  assert.equal(await withReportDecodeTimeout(Promise.resolve('decoded'), 50), 'decoded');
  await assert.rejects(
    withReportDecodeTimeout(new Promise(() => {}), 5),
    /giải mã ảnh báo cáo quá thời gian/i,
  );
  await assert.rejects(
    withReportDecodeTimeout(Promise.reject(new Error('decode error')), 50),
    /decode error/,
  );
});

test('saved review measurements never inherit warnings or geometry from an older prediction', () => {
  const image = {
    review: { max_diameter_mm: 12, ortho_diameter_mm: 8, total_area_cm2: 0.5 },
    prediction: { measurements: { warning: 'STALE PREDICTION', total_area_px: 999, max_diameter_px: 999 } },
  };
  const result = savedReviewMeasurements(image);
  assert.equal(result.calibrated, false, 'legacy physical values need calibration provenance before use');
  assert.equal(result.max_diameter_mm, null);
  assert.equal(result.max_diameter_px, undefined);
  assert.doesNotMatch(result.warning, /STALE PREDICTION/);
  assert.match(result.warning, /hiệu chuẩn.*không được xác minh/i);
  image.review.hitl_feedback = {
    measurement_context: {
      version: 1, status: 'AVAILABLE', calibration_source: 'DICOM', warning: 'Cảnh báo mask đã duyệt',
    },
  };
  assert.equal(savedReviewMeasurements(image).calibrated, true);
  assert.equal(savedReviewMeasurements(image).max_diameter_mm, 12);
  assert.equal(savedReviewMeasurements(image).warning, 'Cảnh báo mask đã duyệt');
  image.review.hitl_feedback.measurement_context.status = 'UNAVAILABLE';
  assert.match(savedReviewMeasurements(image).warning, /hiệu chuẩn.*không được xác minh/i);
  image.review.hitl_feedback.measurement_context.status = 'AVAILABLE';
  image.review.max_diameter_mm = null;
  assert.equal(savedReviewMeasurements(image).calibrated, true, 'D2 can be the only calibrated caliper');
});

test('report suppresses saved physical measurements without trusted calibration provenance', () => {
  const saved = savedReviewMeasurements({
    review: {
      max_diameter_mm: 12,
      ortho_diameter_mm: 8,
      total_area_cm2: 0.42,
      hitl_feedback: {
        measurement_context: {
          version: 1,
          status: 'AVAILABLE',
          calibration_source: 'UNKNOWN',
        },
      },
    },
  });
  assert.equal(saved.calibrated, false);
  assert.equal(saved.max_diameter_mm, null);
  assert.equal(saved.ortho_diameter_mm, null);
  assert.equal(saved.total_area_cm2, null);
  assert.match(saved.warning, /hiệu chuẩn.*không được xác minh/i);

  const untrustedImageMeasurements = formatReportMeasurements({
    mask: new Uint8Array([1]),
    measurements: {
      calibrated: true,
      calibration_source: 'UNKNOWN',
      max_diameter_mm: 12,
      ortho_diameter_mm: 8,
      total_area_cm2: 0.42,
      max_diameter_px: 120,
      ortho_diameter_px: 80,
      total_area_px: 420,
    },
  });
  assert.match(untrustedImageMeasurements, /120\.00 × 80\.00 px/);
  assert.match(untrustedImageMeasurements, /420\.00 px²/);
  assert.doesNotMatch(untrustedImageMeasurements, /12\.00 × 8\.00 mm|42\.00 mm²/);

  const untrustedManualCaliper = formatReportMeasurements({
    mask: new Uint8Array([1]),
    measurements: { calibrated: false, max_diameter_px: 120, total_area_px: 420 },
    review: {
      hitl_feedback: {
        manual_calipers: [{ label: 'D1', points: [[10, 20], [110, 20]] }],
        manual_measurements: {
          D1: {
            diameter_px: 100,
            diameter_mm: 10,
            calibrated: true,
            calibration_source: 'UNKNOWN',
          },
        },
      },
    },
  });
  assert.match(untrustedManualCaliper, /100\.00 × Chưa ghi nhận px/);
  assert.doesNotMatch(untrustedManualCaliper, /10\.00 mm/);
});

test('overlay status distinguishes saved review from an unreviewed model mask', () => {
  assert.equal(reportReviewStatus({}), 'Chưa có mask');
  assert.equal(reportReviewStatus({ prediction: { rle_mask: { counts: [1] } } }), 'Mask AI chưa được rà soát');
  assert.equal(
    reportReviewStatus({ review: { review_id: 'review-L', verified_mask_rle: { counts: [1] } } }),
    'Mask đã được bác sĩ rà soát',
  );
  assert.equal(
    reportReviewStatus({ review: { review_id: 'review-L' } }),
    'Đã lưu lần rà soát · mask chưa xác nhận',
  );
});

assert.equal(
  reportMaskSource({ review: { verified_mask_rle: { counts: [1] } } }),
  'Lớp phủ đã được rà soát',
);
assert.equal(
  reportMaskSource({ prediction: { rle_mask: { counts: [1] } } }),
  'Lớp phủ AI · chưa rà soát',
);
assert.equal(reportMaskSource({}), 'Nguồn lớp phủ chưa xác định');

assert.equal(
  formatOradsAttribution({ review: { orads_score: 'O-RADS 3' } }),
  '<strong>O-RADS 3</strong>',
  'The O-RADS field must show the saved value once, without a duplicated label.',
);
assert.equal(
  formatOradsAttribution({}),
  '<strong>Chưa ghi nhận</strong>',
  'An absent O-RADS value must not read like a CDSS classification.',
);
for (const missingImage of [null, undefined]) {
  assert.equal(
    formatOradsAttribution(missingImage),
    '<strong>Chưa ghi nhận</strong>',
    'A missing image record must not break report rendering or imply a classification.',
  );
}
assert.equal(
  formatOradsAttribution({ orads: '<script>alert(1)</script>' }),
  '<strong>&lt;script&gt;alert(1)&lt;/script&gt;</strong>',
  'Dynamic O-RADS text must remain escaped in the printed report.',
);
assert(
  content.includes('${formatOradsAttribution(image)}'),
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
assert(emptyMaskRows.includes('Chưa có vùng phân đoạn trong mask để hiển thị số đo'));
assert(!emptyMaskRows.includes('chẩn đoán'));
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
const excludedRegionRows = formatReportMeasurements({
  mask: new Uint8Array([1]),
  measurements: { calibrated: false, total_area_px: 900, warning: 'Vùng nhỏ bị loại <script>' },
});
assert(excludedRegionRows.includes('Vùng nhỏ bị loại &lt;script&gt;'));
assert(!excludedRegionRows.includes('<script>'));
assert(measuredRows.includes('12.50 × 8.00 mm'));
assert(measuredRows.includes('42.00 mm²'));
assert(measuredRows.includes('Nguồn số đo: Nguồn lớp phủ chưa xác định.'));
const clinicianCaliperRows = formatReportMeasurements({
  mask: new Uint8Array([1]),
  measurements: { calibrated: false, max_diameter_px: 88, ortho_diameter_px: 44, total_area_px: 1 },
  review: {
    hitl_feedback: {
      manual_calipers: [{ label: 'D1', points: [[10, 20], [110, 20]], coordinate_space: 'decoded-source-image' }],
      manual_measurements: { D1: { diameter_px: 100, diameter_mm: null, calibrated: false } },
    },
  },
});
assert(clinicianCaliperRows.includes('100.00 × Chưa ghi nhận px'));
assert(clinicianCaliperRows.includes('D₁/D₂ theo caliper bác sĩ đã lưu'));
assert(!clinicianCaliperRows.includes('88.00'), 'manual caliper values take precedence over mask proxies');
assert(
  content.includes('hitl_feedback?.manual_calipers'),
  'Saved source-coordinate calipers must be rendered in the report overlay.',
);
assert(
  content.includes('formatReportMeasurements(image)'),
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
  content.includes('Mô tả và O-RADS chỉ hiển thị khi có trong bản ghi rà soát'),
  'The printed report must not attribute AI-derived measurements or unsupported clinical labels to the clinician.',
);
assert(
  !content.includes('window.prompt') && !content.includes('window.confirm'),
  'Research export must not treat client-entered approval or consent as verified evidence.'
);
assert(
  content.includes('exportDisabledMessage'),
  'Research export must explain that it is disabled until trusted verification is available.'
);

const reportCss = fs.readFileSync(
  path.resolve(__dirname, '../frontend/css/report-preview.css'),
  'utf8',
);
const printImageRule = reportCss.match(
  /@media print[\s\S]*?#printRoot \.report-image-pair img\s*\{([^{}]*)\}/,
);
assert(printImageRule, 'The active print stylesheet must bound report image height.');
assert.match(printImageRule[1], /max-height:\s*62mm/);
assert.match(printImageRule[1], /height:\s*62mm/);
assert.match(printImageRule[1], /object-fit:\s*contain/);
assert.match(reportCss, /\.report\s*\{[^}]*font:\s*14px\/1\.5/s, 'Report body text should remain comfortably readable.');
assert.match(reportCss, /\.report-case-block dt,[\s\S]*?font-size:\s*12px/, 'Field labels should not fall back to tiny print.');
assert.match(reportCss, /\.report-result-side h3,[\s\S]*?background:\s*#f1f2f3/, 'Left/right sections need a visible neutral header band.');
assert.match(indexHtml, /report-preview\.css/);
assert.match(reportCss, /\.report-page \+ \.report-page\s*\{[^}]*break-before:\s*page/s);
assert.match(reportCss, /#printRoot \.report-result-side,[\s\S]*?break-inside:\s*avoid/s);
assert.match(reportCss, /\.report-evidence-grid\.single-column\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/s);
assert.match(content, /study\.visit_no/);
assert.match(content, /KẾT QUẢ KHẢO SÁT/);
assert.match(content, /Trang 1\/\$\{pageCount\}/);
assert.match(content, /Trang \$\{index \+ 2\}\/\$\{pageCount\}/);
assert.match(content, /class="report-ruo-banner"[\s\S]*?BẢN NGHIÊN CỨU \(RUO\)/);
assert.match(indexHtml, /class="ruo-safety-banner"[\s\S]*?Không dùng cho chăm sóc bệnh nhân/);
assert.match(indexHtml, /Nguồn dữ liệu chưa được xác minh/);
assert.doesNotMatch(content, /buildPatientSummaryData|patientFriendlyPanel|patient-friendly-summary-panel/);
assert.doesNotMatch(content, /Bình thường \/ Nang sinh lý|nang cơ năng \/ hoàng thể lành tính|Lời khuyên dành cho bạn/);
assert.match(content, /Nguồn dữ liệu chưa được xác minh/);
assert.doesNotMatch(content, /LỜI DẶN DÀNH CHO BỆNH NHÂN|Đa số các nang buồng trứng là sinh lý hoặc lành tính/);
assert.match(content, /THÔNG TIN HỖ TRỢ/);
const printableTemplate = content.slice(
  content.indexOf('function renderReportDocument'),
  content.indexOf('async function reportImages'),
);
const supportTemplate = content.slice(
  content.indexOf('function reportTechnicalInformation'),
  content.indexOf('function renderReportDocument'),
);
assert.match(supportTemplate, /Reviewer ID/);
assert.match(supportTemplate, /image\.review\?\.doctor_id/);
assert.match(printableTemplate, /reportTechnicalInformation\(orderedImages\)/);
assert.match(printableTemplate, /orderedImages\.map\(\(entry, index\)/);

const multiStillReport = renderReportDocument({
  study_id: 'study-multi-report',
  study_code: 'CASE-MULTI',
  patient_id: 'PID-001',
  visit_no: '000123',
  study_date: '2026-10-27',
  review_revision: 3,
  images: ['L', 'L', 'R'].map((laterality, index) => ({
    image_id: `image-${index + 1}`,
    laterality,
    mask: new Uint8Array(512 * 512),
    review: null,
    prediction: null,
  })),
}, [
  ['data:image/png;base64,original1', 'data:image/png;base64,overlay1', true],
  ['data:image/png;base64,original2', 'data:image/png;base64,overlay2'],
  ['data:image/png;base64,original3', 'data:image/png;base64,overlay3'],
]);
assert.equal((multiStillReport.match(/class="report-page report-evidence-page"/g) || []).length, 3);
assert.match(multiStillReport, /Trang 1\/4/);
assert.match(multiStillReport, /Trang 4\/4/);
assert.match(multiStillReport, /Ảnh 1/);
assert.match(multiStillReport, /Ảnh 3/);
assert.match(multiStillReport, /BẢN HIỂN THỊ GIẢM ĐỘ PHÂN GIẢI; xem ảnh nguồn trong máy trạm/);

const reversedSideReport = renderReportDocument({
  study_id: 'study-reversed-sides',
  images: [
    { image_id: 'image-right-first', laterality: 'R', mask: new Uint8Array(512 * 512), review: null },
    { image_id: 'image-left-second', laterality: 'L', mask: new Uint8Array(512 * 512), review: null },
  ],
}, [
  ['data:image/png;base64,right-original', 'data:image/png;base64,right-overlay'],
  ['data:image/png;base64,left-original', 'data:image/png;base64,left-overlay'],
]);
assert.ok(
  reversedSideReport.indexOf('HÌNH ẢNH KHẢO SÁT · ẢNH 1') < reversedSideReport.indexOf('HÌNH ẢNH KHẢO SÁT · ẢNH 2'),
  'Report image numbers must follow the rendered left-to-right page order.',
);

console.log('PASS: FE-02 report content, dynamic A4 pagination, and Visit No');

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

test('report has no automatic patient-facing classification or care advice', () => {
  const report = renderReportDocument({
    study_id: 'ruo-source-unverified',
    images: [{ image_id: 'image-ruo', laterality: 'L', mask: new Uint8Array(512 * 512), review: null }],
  }, [['data:image/png;base64,source', 'data:image/png;base64,overlay']]);
  assert.match(report, /BẢN NGHIÊN CỨU \(RUO\)/);
  assert.match(report, /Không dùng cho chăm sóc bệnh nhân/);
  assert.match(report, /Nguồn dữ liệu chưa được xác minh/);
  assert.doesNotMatch(report, /Bình thường|lành tính|tái khám|hướng xử trí|xác suất ác tính/iu);
});
