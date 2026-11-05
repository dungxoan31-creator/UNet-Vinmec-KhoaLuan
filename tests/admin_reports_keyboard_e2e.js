const assert = require('node:assert/strict');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

const summary = {
  generated_at: '2026-11-05T00:00:00Z',
  total_cases: 2,
  completed_cases: 1,
  total_reviews: 1,
  overall_consensus_rate_pct: 100,
  avg_iqa_score: 0.8,
  iqa_pass_rate_pct: 100,
  iqa_scored_count: 1,
  avg_review_seconds: 10,
  review_duration_count: 1,
  total_images: 1,
  total_predictions: 1,
  orads_distribution: { 'O-RADS 2': 1 },
  lesion_distribution: { 'Nang đơn giản': 1 },
  action_distribution: {},
  iqa_tiers: {},
  demographics: {},
  timeline_trend: [],
};

(async () => {
  const isolated = await startIsolatedBrowser();
  const { browser, base, adminPassword } = isolated;
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const filteredRequests = [];
  await page.route('**/api/admin/analytics/summary**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(summary) }));
  await page.route('**/api/admin/reports/cases**', (route) => {
    filteredRequests.push(route.request().url());
    return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  try {
    await page.goto(base + '/#login');
    await page.locator('#authForm [name=username]').fill('admin');
    await page.locator('#authForm [name=password]').fill(adminPassword);
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('#dashData .metrics').waitFor();
    await page.evaluate(() => { location.hash = '#admin/reports'; });
    const drilldown = page.locator('button[data-orads="O-RADS 2"]');
    await drilldown.waitFor();
    assert.equal(await drilldown.getAttribute('aria-pressed'), 'false');

    await drilldown.focus();
    await drilldown.press('Enter');
    await page.waitForFunction(() => document.querySelector('button[data-orads="O-RADS 2"]')?.getAttribute('aria-pressed') === 'true');
    await page.waitForFunction(() => [...document.querySelectorAll('a#exportFilteredCsvBtn')]
      .some((anchor) => anchor.href.includes('orads=O-RADS+2') || anchor.href.includes('orads=O-RADS%202')));
    assert.ok(filteredRequests.some((url) => new URL(url).searchParams.get('orads') === 'O-RADS 2'));

    await page.locator('button[data-orads="O-RADS 2"]').focus();
    await page.locator('button[data-orads="O-RADS 2"]').press('Space');
    await page.waitForFunction(() => document.querySelector('button[data-orads="O-RADS 2"]')?.getAttribute('aria-pressed') === 'false');
    console.log('PASS: admin O-RADS drilldown supports keyboard focus, Enter, Space, and exposes pressed state');
  } finally {
    await context.close();
    await isolated.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
