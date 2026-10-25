/* Real API/DB/model roundtrip with generated non-patient grayscale fixtures. */
const assert = require('node:assert/strict');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

async function main() {
  const server = await startIsolatedBrowser();
  const errors = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.on('pageerror', error => errors.push(error.message));
    // Preserve truthful test provenance; all responses and clinical writes remain real.
    await page.route('**/api/hitl/sessions', route => route.continue({ postData: JSON.stringify({
      ...route.request().postDataJSON(), participant_role: 'technical_tester', data_origin: 'technical_fixture',
    }) }));
    await page.goto(server.base + '/#login');
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-select="0"]').click();
    await page.locator('[name=pid]').fill('SYNTHETIC-RUNTIME-ROUNDTRIP');
    for (const [side, seed] of [['L', 17], ['R', 937]]) {
      const png = await page.evaluate(seedValue => {
        const canvas = document.createElement('canvas'); canvas.width = 320; canvas.height = 240;
        const context = canvas.getContext('2d'), pixels = context.createImageData(320, 240);
        let value = seedValue;
        for (let y = 0; y < 240; y++) for (let x = 0; x < 320; x++) {
          value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
          const inside = (x - 160) ** 2 / 55 ** 2 + (y - 120) ** 2 / 45 ** 2 < 1;
          const intensity = inside ? 15 + (value % 20) : 35 + (value % 175);
          pixels.data.set([intensity, intensity, intensity, 255], 4 * (y * 320 + x));
        }
        context.putImageData(pixels, 0, 0);
        return canvas.toDataURL('image/png').split(',')[1];
      }, seed);
      await page.locator(`[data-file=${side}]`).setInputFiles({ name: `synthetic-${side === 'L' ? 'left' : 'right'}.png`, mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
    }
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    await page.locator('#startSegmentationBtn').click();
    await page.waitForFunction(() => location.hash.startsWith('#viewer/'), { timeout: 90000 });
    await page.locator('#notes').waitFor();
    const id = await page.evaluate(() => location.hash.slice('#viewer/'.length));
    await page.locator('#notes').fill('Rà soát kỹ thuật ảnh tổng hợp bên trái.');
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('#notes').fill('Rà soát kỹ thuật ảnh tổng hợp bên phải.');
    const saveResponse = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/reviews/batch');
    await page.locator('[data-action=save-review]').click();
    const response = await saveResponse;
    assert.equal(response.status(), 200, await response.text());
    const saved = await response.json();
    assert.equal(saved.status, 'SUCCESS');
    assert.equal(saved.review_revision, 1);
    await page.waitForFunction(async () => !(await import('/static/app/state.js')).state.busy);
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const detail = await page.request.get(server.base + '/api/cases/' + encodeURIComponent(id), { headers: { Authorization: 'Bearer ' + token } });
    assert.equal(detail.status(), 200);
    const persisted = await detail.json();
    assert.equal(persisted.review_revision, 1);
    for (const image of persisted.images) {
      assert.ok(image.review.review_id);
      assert.equal(image.review.doctor_id, 'doctor');
      assert.equal(image.review.clinical_notes, `Rà soát kỹ thuật ảnh tổng hợp bên ${image.laterality === 'L' ? 'trái' : 'phải'}.`);
      assert.deepEqual(image.review.verified_mask_rle, image.prediction.rle_mask);
      assert.equal(image.review.max_diameter_mm, null, 'no invented physical calibration');
    }
    // Leave and reopen: validate server persistence, not just the in-memory save result.
    await page.evaluate(() => { location.hash = '#cases'; });
    await page.locator('#caseResults').waitFor();
    await page.evaluate(studyId => { location.hash = '#viewer/' + studyId; }, id);
    await page.waitForFunction(() => document.querySelector('#notes')?.value === 'Rà soát kỹ thuật ảnh tổng hợp bên trái.');
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#notes')?.value === 'Rà soát kỹ thuật ảnh tổng hợp bên phải.');
    await page.locator('[data-action=report]').click();
    await page.locator('#reportData .report footer').waitFor();
    const report = await page.locator('#reportData .report').innerText();
    assert.match(report, /Revision 1/);
    assert.match(report, /Người rà soát: doctor/);
    assert.match(report, /Rà soát kỹ thuật ảnh tổng hợp bên trái/);
    assert.match(report, /Rà soát kỹ thuật ảnh tổng hợp bên phải/);
    assert.equal(await page.locator('#reportData .report-review-status').count(), 2);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: 'PASS', scope: 'real isolated auth/intake/upload/IQA/model/review/DB/reopen/report with synthetic images; no response mocks', revision: saved.review_revision, images: persisted.images.length, pageErrors: errors.length }));
  } finally { await server.close(); }
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
