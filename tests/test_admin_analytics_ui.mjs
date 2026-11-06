import assert from 'node:assert/strict';
import test from 'node:test';
import { analyticsShare, renderChartDrilldownButton, renderExecutiveMetrics } from '../frontend/app/admin-reports.js';

test('admin metrics show N/A for missing measurements and preserve measured zero with denominators', () => {
  const empty = renderExecutiveMetrics({
    total_cases: 0,
    completed_cases: 0,
    total_reviews: 0,
    overall_consensus_rate_pct: null,
    avg_iqa_score: null,
    iqa_pass_rate_pct: null,
    iqa_scored_count: 0,
    avg_review_seconds: null,
    review_duration_count: 0,
  });
  assert.equal((empty.match(/Chưa có số liệu/g) || []).length, 5);
  assert.match(empty, /0 ảnh có điểm IQA/);
  assert.match(empty, /0 lượt có thời lượng ghi nhận/);

  const measuredZero = renderExecutiveMetrics({
    total_cases: 1,
    completed_cases: 0,
    total_reviews: 1,
    overall_consensus_rate_pct: 0,
    avg_iqa_score: 0,
    iqa_pass_rate_pct: 0,
    iqa_scored_count: 1,
    avg_review_seconds: 0,
    review_duration_count: 1,
  });
  assert.equal((measuredZero.match(/Chưa có số liệu/g) || []).length, 0);
  assert.match(measuredZero, /0%/);
  assert.match(measuredZero, /0 hoàn thành \(0%\)/);
  assert.match(measuredZero, /1 ảnh có điểm IQA/);
  assert.match(measuredZero, /0s/);
  assert.match(measuredZero, /1 lượt có thời lượng ghi nhận/);
});

test('analytics shares distinguish an empty denominator from a measured zero', () => {
  assert.equal(analyticsShare(0, 0), null);
  assert.equal(analyticsShare(0, 4), 0);
  assert.equal(analyticsShare(1, 4), 25);
});

test('admin chart drilldowns render native buttons with selected state and useful accessible names', () => {
  const markup = renderChartDrilldownButton({
    type: 'ORADS', value: 'O-RADS 2', label: 'Lành tính cao (<1%)',
    count: 1, percentage: 100, color: '#0284c7', selected: true,
  });
  assert.match(markup, /<button type="button"/);
  assert.match(markup, /data-orads="O-RADS 2"/);
  assert.match(markup, /aria-pressed="true"/);
  assert.match(markup, /aria-label="Lọc danh sách ca theo O-RADS 2/);
  assert.doesNotMatch(markup, /<div/);

  const noData = renderChartDrilldownButton({
    type: 'LESION', value: 'Nang đơn giản', label: '',
    count: 0, percentage: null, color: '#10b981', selected: false,
  });
  assert.match(noData, /data-lesion="Nang đơn giản"/);
  assert.match(noData, /aria-pressed="false"/);
  assert.match(noData, /tỷ lệ chưa có số liệu/);
});
