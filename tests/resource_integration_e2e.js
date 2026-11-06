/* Live isolated API + synthetic upload. One explicitly labelled UI-only AI proposal fixture. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');

async function main() {
  const server = await startIsolatedBrowser();
  const out = path.resolve('artifacts/resource_audit');
  fs.mkdirSync(out, { recursive: true });
  const errors = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.goto(server.base + '/#login');
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-action=anonymous-study]').click();
    assert.equal(await page.locator('[name=pid]').inputValue(), '');
    // Simulate a committed reservation whose response is lost in transit.
    let reservedVisit;
    let createRequests = 0;
    await page.route('**/api/cases', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      createRequests++;
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      const result = await response.json();
      if (!reservedVisit) {
        reservedVisit = result;
        return route.abort('failed');
      }
      assert.equal(result.study_id, reservedVisit.study_id);
      assert.equal(result.visit_no, reservedVisit.visit_no);
      await route.fulfill({ response });
    });
    await page.locator('[data-action=create-visit]').click();
    await page.getByRole('button', { name: 'Thử lại tạo Visit', exact: true }).waitFor();
    await page.locator('[data-action=create-visit]').click();
    await page.waitForFunction(() => /^\d{6}$/.test(document.querySelector('[data-visit-no]').textContent));
    assert.equal(await page.locator('[data-visit-no]').innerText(), reservedVisit.visit_no);
    assert.equal(await page.locator('[data-action=create-visit]').isVisible(), false);
    assert.equal(await page.locator('[name=study-date]').isDisabled(), true);
    await page.screenshot({ path: path.join(out, 'reserved-visit.png'), fullPage: true });
    const fixtures = ensureSyntheticFixtures();
    await page.locator('[data-file=L]').setInputFiles(fixtures.letterbox);
    await page.locator('[data-file=R]').setInputFiles(fixtures.right);
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn')?.disabled, null, { timeout: 30000 });
    await page.locator('#startSegmentationBtn').click();
    await page.waitForFunction(() => location.hash.startsWith('#viewer/') && document.querySelector('#notes'), null, { timeout: 90000 });
    await page.waitForFunction(async () => {
      const {state} = await import('/static/app/state.js');
      return state.editing?.allowed && !state.busy && !document.querySelector('#notes').disabled;
    });
    const id = await page.evaluate(() => location.hash.slice('#viewer/'.length));
    assert.equal(id, reservedVisit.study_id, 'Analysis must reuse the reserved examination');
    assert.equal(createRequests, 2, 'Only the reservation and its replay may create/request a case');
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const headers = { Authorization: 'Bearer ' + token };
    const detailResponse = await page.request.get(server.base + '/api/cases/' + id, { headers });
    assert.equal(detailResponse.status(), 200);
    const detail = await detailResponse.json();
    assert.equal(detail.visit_no, reservedVisit.visit_no);
    assert.equal(detail.ovary_side, 'BOTH');
    assert.equal(detail.patient_id, null, 'Patientless intake must not create a fake PID');
    assert.equal(detail.images.length, 2);
    assert.equal(await page.locator('#selectModelZoo').count(), 0);
    assert.equal(await page.locator('#btnCaliperDenoise').count(), 0);
    assert.equal(await page.locator('#assessmentAdvanced').count(), 0);
    assert.doesNotMatch(await page.locator('#clinicalPanel').innerText(), /Chi tiết nâng cao|Nguồn mô hình|Lịch sử chỉnh sửa|Điều kiện áp dụng/);
    assert.equal(await page.locator('#viewerInternalData').isVisible(), false);
    assert.equal(await page.locator('#regionReviewMount').isVisible(), false);
    assert.equal(await page.locator('#researchCandidateMount').isVisible(), false);
    const prediction = detail.images[0].prediction;
    assert.match(prediction.ai_diagnosis.provenance.checkpoint_sha256, /^[0-9a-f]{64}$/);
    assert.equal(prediction.ai_diagnosis.research_use_only, true);
    assert.equal(prediction.ai_diagnosis.requires_clinician_confirmation, true);

    const rerunResponse = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.startsWith('/api/predict/'));
    await page.locator('#btnRerunAI').click();
    const rerun = await rerunResponse;
    assert.equal(rerun.status(), 200, await rerun.text());
    assert.ok(rerun.request().headers()['idempotency-key']);
    assert.equal(new URL(rerun.url()).searchParams.has('model_key'), false);
    await page.waitForFunction(() => !document.querySelector('#notes').disabled);

    let releaseFilter, notifyFilter;
    const filterStarted = new Promise(resolve => { notifyFilter = resolve; });
    const delayedFilter = new Promise(resolve => { releaseFilter = resolve; });
    await page.route('**/api/images/*/viewer-source?*', async route => {
      const upstream = await route.fetch();
      notifyFilter();
      await delayedFilter;
      await route.fulfill({ response: upstream });
    });
    await page.locator('details').filter({ has: page.locator('#caliperDenoiseToggle') }).locator('summary').click();
    await page.locator('#caliperDenoiseToggle').check();
    await filterStarted;
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải') && !document.querySelector('#notes').disabled);
    const rightPixels = await page.locator('#viewport').evaluate(canvas => canvas.toDataURL());
    releaseFilter();
    await page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/viewer-source'));
    await page.waitForTimeout(150);
    assert.equal(await page.locator('#viewport').evaluate(canvas => canvas.toDataURL()), rightPixels,
      'Late filtered pixels from the previous image must not replace the selected image');
    assert.equal(await page.locator('#caliperDenoiseToggle').isChecked(), false);
    await page.unroute('**/api/images/*/viewer-source?*');
    await page.locator('[data-action=side-L]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('trái') && !document.querySelector('#notes').disabled);

    // Real synthetic classifier may abstain. This labelled fixture tests only
    // reviewer interaction; it is not an accuracy result or stored prediction.
    await page.locator('#notes').fill('Ghi chú của bác sĩ trên ảnh tổng hợp.');
    await page.locator('#morphology').fill('Mô tả hình thái đã nhập.');
    await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const { currentViewer } = await import('/static/app/viewer.js');
      const image = state.case.images.find(row => row.laterality === 'L');
      image.prediction.ai_diagnosis = {
        status:'PREDICTED', suggested_label:'simple_cyst',
        probabilities:{simple_cyst:.85, normal_ovary:.1, teratoma:.05},
        research_use_only:true, requires_clinician_confirmation:true,
      };
      await currentViewer().select('L', image.image_id);
    });
    await page.locator('#btnApplyAiDiagnosis').click();
    const notes = await page.locator('#notes').inputValue();
    assert.match(notes, /^Ghi chú của bác sĩ/);
    assert.match(notes, /Gợi ý AI \(RUO, chưa xác nhận\)/);
    assert.equal(await page.locator('#morphology').inputValue(), 'Mô tả hình thái đã nhập.');
    await page.locator('#btnApplyAiDiagnosis').click();
    assert.equal(await page.locator('#notes').inputValue(), notes, 'Repeated insertion is idempotent');
    assert.equal(await page.locator('#btnRerunAI').isDisabled(), true, 'Rerun protects edited drafts');
    assert.equal(await page.locator('#localReviewDraftNotice').isVisible(), true);
    assert.equal(await page.evaluate(async () => (await import('/static/app/state.js')).state.dirty), true);
    const drafts = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith('ova.draft.')).map(key => localStorage.getItem(key)));
    assert.ok(drafts.some(value => value.includes('Gợi ý AI')));

    await page.screenshot({ path: path.join(out, 'viewer-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(out, 'viewer-mobile.png'), fullPage: true });
    const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    assert.ok(layout.scrollWidth <= layout.width + 1, JSON.stringify(layout));
    await page.setViewportSize({ width: 1440, height: 900 });
    console.log('READY_FOR_GUI_INSPECTION: synthetic patientless viewer (UI-only AI proposal fixture)');
    if (process.env.E2E_HEADED === 'true') await page.waitForTimeout(60000);
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log(JSON.stringify({status:'PASS', reservedVisitReused:true, lostReservationResponseReplayed:true, createRequests, patientlessStudy:true, liveRerun:true,
      duplicatedModelSelectorRemoved:true, clinicianTextPreserved:true, noteInsertedOnce:true,
      localDraftPersisted:true, viewports:[1440,390], pageErrors:errors.length,
      scope:'Synthetic live auth/intake/upload/inference/rerun; UI-only predicted-class fixture for note insertion; no accuracy inference'}));
  } finally { await server.close(); }
}
main().catch(error => { console.error(error.stack || error); process.exitCode=1; });
