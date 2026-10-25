/* Synthetic fault injection; only auth/capabilities use the isolated backend. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
const out = path.resolve(__dirname, '../artifacts/qa-clinical-fixed');
fs.mkdirSync(out, { recursive: true });
async function login(page, server) {
  await page.goto(server.base + '/#login');
  await page.locator('[name=username]').fill('doctor');
  await page.locator('[name=password]').fill(server.password);
  await page.locator('#authForm button[type=submit]').click();
  await page.waitForFunction(() => location.hash === '#dashboard');
}
async function paint(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function main() {
  const server = await startIsolatedBrowser();
  const errors = [], checks = [], geometries = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => { window.__printCalls = 0; window.print = () => { window.__printCalls++; }; });
    await login(page, server);
    const png = await page.evaluate(() => {
      const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 480;
      const ctx = canvas.getContext('2d'); ctx.fillStyle = '#444'; ctx.fillRect(0, 0, 640, 480);
      ctx.fillStyle = '#bbb'; ctx.fillRect(190, 150, 160, 140);
      return canvas.toDataURL('image/png').split(',')[1];
    });
    const file = name => ({ name, mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-select="0"]').click();
    let held, started;
    const pending = new Promise(resolve => { started = resolve; });
    await page.route('**/api/intake/extract-metadata', route => { held = route; started(); });
    await page.locator('[data-file=L]').setInputFiles(file('left.png'));
    await pending;
    await page.locator('[data-action=change-patient]').click();
    await page.locator('[data-select="1"]').click();
    await page.locator('[name=study-date]').fill('2026-09-01T08:30');
    await json(held, { metadata: { pid: { value: 'SYNTHETIC-A', source: 'dicom', confidence: 1 },
      study_date: { value: '2025-01-01T10:00', source: 'dicom', confidence: 1 } } }).catch(error => {
      // Abort is expected; a late response may be undeliverable at transport level.
      if (!/closed|aborted|handled|invalid|interception/i.test(error.message)) throw error;
    });
    await paint(page);
    assert.equal(await page.locator('[name=pid]').inputValue(), '100000002');
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2026-09-01T08:30');
    assert.equal(await page.locator('#metadataProposals button').count(), 0);
    checks.push('QA-001 stale metadata cannot cross patient/form');
    await page.unroute('**/api/intake/extract-metadata');
    await page.route('**/api/intake/extract-metadata', route => json(route, { metadata: {
      pid: { value: 'SYNTHETIC-CURRENT', source: 'dicom', confidence: 0.99 },
      study_date: { value: '2025-01-02T11:22', source: 'dicom', confidence: 0.98 },
    } }));
    await page.locator('[data-file=L]').setInputFiles(file('left.png'));
    await page.locator('#metadataProposals button').first().waitFor();
    assert.equal(await page.locator('[name=pid]').inputValue(), '100000002');
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2026-09-01T08:30');
    await page.locator('#metadataProposals button').first().click();
    assert.equal(await page.locator('[name=pid]').inputValue(), 'SYNTHETIC-CURRENT');
    checks.push('QA-001 valid metadata is a proposal; only explicit apply changes the field');
    await page.unroute('**/api/intake/extract-metadata');
    await page.route('**/api/intake/extract-metadata', route => json(route, { metadata: {} }));
    await page.locator('.dropzone[data-side=L]').evaluate((element, source) => {
      const bytes = Uint8Array.from(atob(source), char => char.charCodeAt(0));
      const transfer = new DataTransfer();
      for (const name of ['scan-left-1.png', 'scan-left-2.png']) transfer.items.add(new File([bytes], name, { type: 'image/png' }));
      element.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, png);
    await page.locator('[data-confirm=R]').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await page.locator('[data-confirm=L]').check();
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await page.locator('[data-confirm=R]').check();
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    checks.push('QA-004 ambiguous pair requires explicit side confirmations');
    await page.locator('[data-action=swap-sides]').click();
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await page.locator('[data-confirm=L]').check(); await page.locator('[data-confirm=R]').check();
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    checks.push('QA-004 swapping files invalidates prior side confirmations');
    for (const width of [1366, 1024, 768]) {
      await page.setViewportSize({ width, height: 768 });
      await page.evaluate(() => window.scrollTo(0, 0)); await paint(page);
      const geometry = await page.locator('#startSegmentationBtn').evaluate(element => {
        const rect = element.getBoundingClientRect();
        return { top: rect.top, bottom: rect.bottom, height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth + 1 };
      });
      assert.equal(geometry.overflow, false, `no horizontal overflow at ${width}`);
      assert.ok(geometry.top >= 0 && geometry.bottom <= geometry.height - 32, `CTA within viewport at ${width}: ${JSON.stringify(geometry)}`);
      assert.equal(await page.locator('#startSegmentationBtn').evaluate(element => {
        const rect = element.getBoundingClientRect();
        const target = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
        return target === element || element.contains(target);
      }), true, 'CTA must not be covered by toast/shell elements');
      geometries.push({ width, ...geometry });
      await page.screenshot({ path: path.join(out, `intake-${width}.png`) });
    }
    checks.push('QA-006 CTA remains visible at laptop/tablet sizes');

    const rle = { shape: [512, 512], first_val: 0, counts: [1000, 200, 260944] };
    const fixture = { study_id: 'safety-study', study_code: 'SYNTHETIC-SAFETY', patient_id: 'SYNTHETIC-ONLY',
      status: 'ANALYZED', study_date: '2026-10-25', version: 1, review_revision: 0,
      images: ['L', 'R'].map(side => ({ image_id: 'safety-' + side, laterality: side, width: 640, height: 480,
        prediction: { prediction_id: 'pred-' + side, rle_mask: rle, measurements: {}, provenance: { model_name: 'synthetic-fixture' } }, review: null })) };
    let batchCalls = 0, failSave = true, reportReads = 0;
    await page.route('**/api/cases/safety-study', route => { reportReads++; return json(route, fixture); });
    await page.route('**/api/workspace/cases/safety-study/lease', route => route.request().method() === 'DELETE'
      ? route.fulfill({ status: 204, body: '' }) : json(route, { granted: true, lease_token: 'synthetic-lease-token', expires_at: '2099-01-01T00:00:00Z' }));
    await page.route('**/api/hitl/sessions', route => json(route, { id: 'synthetic-safety-session' }));
    await page.route('**/api/hitl/sessions/*/events', route => json(route, { accepted: true, count: 1 }));
    await page.route('**/api/hitl/events', route => json(route, { success: true, count: 1 }));
    let holdRightSource = false, heldRightSource, notifyRightSource;
    await page.route('**/api/images/safety-*/viewer-source', route => {
      if (holdRightSource && route.request().url().includes('/safety-R/')) {
        heldRightSource = route; notifyRightSource(); return;
      }
      return json(route, { original_image_base64: 'data:image/png;base64,' + png });
    });
    await page.route('**/api/images/safety-*/source.png', route => route.fulfill({ contentType: 'image/png', body: Buffer.from(png, 'base64') }));
    await page.route('**/api/images/safety-*/measurements', route => json(route, { calibrated: false, max_diameter_px: 25, ortho_diameter_px: 10, total_area_px: 200, lesions: [] }));
    await page.route('**/api/reviews/batch', route => {
      batchCalls++;
      if (failSave) return json(route, { detail: 'Synthetic save failure' }, 503);
      const payload = route.request().postDataJSON();
      fixture.review_revision++;
      fixture.images.forEach(image => {
        const body = payload.reviews.find(row => row.image_id === image.image_id);
        image.review = { ...body, review_id: 'saved-' + image.image_id, doctor_id: 'actual-reviewer' };
      });
      return json(route, { status: 'SUCCESS', study_id: fixture.study_id, review_revision: fixture.review_revision,
        reviews: fixture.images.map(image => ({ review_id: image.review.review_id, image_id: image.image_id,
          prediction_id: image.prediction.prediction_id, doctor_action: image.review.doctor_action })) });
    });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.evaluate(() => { location.hash = '#viewer/safety-study'; });
    await page.waitForFunction(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case?.study_id === 'safety-study' && state.case.images[0].seen && document.querySelector('#d1')?.textContent !== 'Đang cập nhật...';
    });
    await page.locator('[data-action=quick-print]').click();
    assert.equal(batchCalls, 0);
    assert.equal(page.url().includes('#viewer/safety-study'), true);
    assert.equal(await page.evaluate(async () => (await import('/static/app/state.js')).state.case.images[1].seen || false), false);
    checks.push('QA-002 print never fabricates seen or saves an unviewed side');
    holdRightSource = true;
    const rightSourceStarted = new Promise(resolve => { notifyRightSource = resolve; });
    await page.locator('[data-action=side-R]').click();
    await rightSourceStarted;
    assert.equal(await page.locator('#notes').isDisabled(), true, 'notes are locked while a different image loads');
    await page.locator('#notes').evaluate(element => {
      element.value = 'Synthetic stale input while source is pending';
      element.dispatchEvent(new Event('input', { bubbles: true }));
    });
    assert.equal(await page.evaluate(async () => (await import('/static/app/state.js')).state.case.images[0].notes), '');
    await json(heldRightSource, { original_image_base64: 'data:image/png;base64,' + png });
    holdRightSource = false;
    await page.waitForFunction(async () => (await import('/static/app/state.js')).state.case.images.every(image => image.seen));
    checks.push('viewer source loading locks clinical inputs and rejects stale input events');
    await page.locator('#notes').fill('');
    await page.locator('#notes').pressSequentially('.nang1 ');
    assert.doesNotMatch(await page.locator('#notes').inputValue(), /O-RADS\s*\d|lành tính/iu);
    await page.locator('[data-action=quick-print]').click();
    assert.equal(batchCalls, 0, 'unresolved template placeholders cannot be saved');
    await page.locator('#notes').fill('Nhận định O-RADS 4.');
    await page.locator('#oradsScore').selectOption('O-RADS 2');
    await page.locator('[data-action=quick-print]').click();
    assert.equal(batchCalls, 0, 'conflicting notes/category must be reviewed');
    assert.equal(await page.locator('#reviewContentWarning').isVisible(), true);
    await page.locator('#reviewContentAck').check();
    checks.push('QA-009 neutral templates and unresolved/mismatched content are gated before save');
    await page.locator('[data-action=quick-print]').click();
    await page.waitForFunction(async () => !(await import('/static/app/state.js')).state.busy);
    assert.equal(batchCalls, 1);
    assert.equal(page.url().includes('#viewer/safety-study'), true);
    assert.equal(await page.evaluate(() => window.__printCalls), 0);
    checks.push('QA-002 failed save retains viewer and never prints');
    // Acknowledged save prints only the persisted revision and actual reviewer.
    failSave = false;
    await page.locator('[data-action=quick-print]').click();
    await page.waitForFunction(() => location.hash.includes('revision=1'));
    await page.locator('#reportData .report footer').waitFor();
    await page.waitForFunction(() => window.__printCalls === 1);
    assert.match(await page.locator('#reportData .report').innerText(), /actual-reviewer/);
    assert.doesNotMatch(await page.locator('#reportData .report').innerText(), /Người rà soát: doctor\b/);
    checks.push('QA-002/003 confirmed snapshot prints persisted reviewer and revision');
    // Opening a raw draft explicitly is allowed, but cannot claim a reviewer.
    fixture.images.forEach(image => { image.review = null; }); fixture.review_revision = 0;
    await page.evaluate(() => { location.hash = '#report/safety-study?draft=1'; });
    await page.locator('#reportData .report footer').waitFor();
    assert.match(await page.locator('#reportData .report').innerText(), /Chưa có rà soát được lưu/);
    assert.doesNotMatch(await page.locator('#reportData .report').innerText(), /Người rà soát:/);
    assert.equal(batchCalls, 2);
    await page.screenshot({ path: path.join(out, 'unreviewed-report.png'), fullPage: true });
    checks.push('QA-003 raw draft has no invented reviewer and causes no review write');
    assert.ok(reportReads >= 3);
    // A previously acknowledged revision must not auto-print a newer/different one.
    await page.evaluate(() => { location.hash = '#report/safety-study?print=1&revision=1'; });
    await page.getByText('Phiên bản rà soát đã thay đổi', { exact: false }).waitFor();
    await paint(page);
    assert.equal(await page.evaluate(() => window.__printCalls), 1);
    checks.push('QA-002 stale revision cannot auto-print');

    const quotaPage = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    quotaPage.on('pageerror', error => errors.push(error.message));
    await quotaPage.addInitScript(() => {
      for (const key of Object.keys(localStorage)) if (key.startsWith('ova.demo-patients.')) localStorage.removeItem(key);
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, value) {
        if (String(key).startsWith('ova.demo-patients.')) throw new DOMException('Synthetic quota exhaustion', 'QuotaExceededError');
        return original.call(this, key, value);
      };
    });
    await login(quotaPage, server);
    await quotaPage.evaluate(() => { location.hash = '#intake'; });
    await quotaPage.locator('[data-select="0"]').waitFor();
    assert.equal(await quotaPage.locator('[data-select]').count(), 4);
    assert.match(await quotaPage.locator('main').innerText(), /chỉ giữ trong phiên này/);
    await quotaPage.locator('[data-select="0"]').click();
    await quotaPage.locator('[data-file=L]').waitFor();
    checks.push('QA-005 quota fallback retains usable intake and discloses non-durable state');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'safety-results.json'), JSON.stringify({ status: 'PASS', checks, geometries,
      pageErrors: errors, scope: 'synthetic UI fault injection, real isolated auth; clinical writes mocked' }, null, 2));
    console.log(JSON.stringify({ status: 'PASS', checks, geometries, pageErrors: errors.length }));
  } finally { await server.close(); }
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
