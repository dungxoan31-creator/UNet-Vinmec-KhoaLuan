/* Synthetic fault injection; reviewer queue reads use the isolated backend and SQLite. */
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const { waitForAppState } = require('./helpers/app_state_wait.cjs');
const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
const out = path.resolve(process.env.CLINICAL_SAFETY_EVIDENCE_DIR || path.join(__dirname, '../artifacts/qa-clinical-fixed'));
fs.mkdirSync(out, { recursive: true });
function seedSignedPrelimQueue(server, count, fixturePath, facilityId = '', studyCodePrefix = 'SYNTHETIC-SIGNED') {
  const root = path.resolve(__dirname, '..');
  const python = process.env.PYTHON || path.join(root, process.platform === 'win32'
    ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const stdout = execFileSync(python, [
    path.join(__dirname, 'seed_synthetic_signed_prelim_queue.py'),
    String(count),
    fixturePath,
    facilityId,
    studyCodePrefix,
  ], {
    cwd: root,
    env: { ...process.env, APP_DATA_DIR: server.runtime,
      APP_DB_PATH: path.join(server.runtime, 'safety.sqlite3'), DATABASE_URL: '' },
    encoding: 'utf8',
  });
  return JSON.parse(stdout);
}
async function login(page, server, checks = null, credentials = {}) {
  await page.goto(server.base + '/#login');
  if (checks) {
    const authCopy = await page.locator('.auth-aside').innerText();
    assert.match(authCopy, /HUMAN-IN-THE-LOOP CDSS · RUO/);
    assert.match(authCopy, /Môi trường nghiên cứu hỗ trợ xem phân đoạn/i);
    assert.match(authCopy, /bác sĩ rà soát và xác nhận/i);
    assert.doesNotMatch(authCopy, /kiểm toán lâm sàng/i);
    assert.equal(await page.locator('.ruo-safety-banner').count(), 0);
    assert.doesNotMatch(authCopy, /chưa được xác thực lâm sàng|không dùng cho chăm sóc bệnh nhân/i);
    checks.push('P0 auth copy identifies the RUO research environment and clinician review');
  }
  await page.locator('[name=username]').fill(credentials.username || 'doctor');
  await page.locator('[name=password]').fill(credentials.password || server.password);
  await page.locator('#authForm button[type=submit]').click();
  await page.waitForFunction(() => location.hash === '#dashboard');
  assert.equal(await page.locator('#environmentUnknownBanner').isHidden(), true);
  assert.equal(await page.locator('#syntheticDemoBanner').isHidden(), true,
    'The isolated safety harness defaults to non-demo capabilities.');
}
async function paint(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function main() {
  const fixtures = ensureSyntheticFixtures();
  const pngBytes = fs.readFileSync(fixtures.left);
  const png = pngBytes.toString('base64');
  const server = await startIsolatedBrowser();
    const errors = [], checks = [], geometries = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => { window.__printCalls = 0; window.print = () => { window.__printCalls++; }; });
    await login(page, server, checks);
    const intakeToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    for (const name of ['Synthetic Patient 1', 'Synthetic Patient 2', 'Synthetic Patient 3', 'Synthetic Patient 4']) {
      const response = await page.request.post(server.base + '/api/patient-directory', {
        headers: { Authorization: `Bearer ${intakeToken}` },
        data: { display_name: name },
      });
      assert.equal(response.status(), 201, await response.text());
    }
    const feedbackRequests = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/feedback') feedbackRequests.push(request.method());
    });
    await page.evaluate(() => { location.hash = '#help'; });
    await page.locator('[data-action="feedback"]').click();
    await page.locator('#modal').waitFor();
    const feedbackCopy = await page.locator('#modal').innerText();
    assert.match(feedbackCopy, /Không gửi tên, ngày sinh, PID\/mã bệnh án, ảnh hoặc nội dung lâm sàng của bệnh nhân/);
    assert.match(feedbackCopy, /Góp ý được lưu trong nhật ký hệ thống/);
    await page.locator('#modal button[value="cancel"]').click();
    await page.locator('#modal').waitFor({ state: 'hidden' });
    assert.deepEqual(feedbackRequests, [], 'opening and cancelling feedback must not submit free text');
    checks.push('P0 feedback warns against PHI and discloses audit storage before submission');
    const unavailableExportRequests = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/workspace/cases/export')
        unavailableExportRequests.push(request.method());
    });
    await page.evaluate(() => { location.hash = '#cases'; });
    await page.locator('[data-export-status="disabled"]').waitFor();
    assert.match(await page.locator('[data-export-status="disabled"]').innerText(), /đang bị khóa trên máy chủ/i);
    assert.equal(await page.locator('[data-action="export-selected"], .case-select, #selectAll').count(), 0,
      'Unavailable case export must not expose a dead button or selection controls.');
    assert.deepEqual(unavailableExportRequests, [], 'Worklist must not call an unimplemented bulk export endpoint.');
    checks.push('P0 unavailable bulk case export is explained and exposes no dead endpoint action');
    await page.evaluate(() => { location.hash = '#dashboard'; });
    await page.waitForFunction(() => location.hash === '#dashboard');
    const reviewerPage = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    reviewerPage.on('pageerror', error => errors.push(error.message));
    const reviewerDashboardPromise = reviewerPage.waitForResponse(response =>
      response.request().method() === 'GET' && new URL(response.url()).pathname === '/api/workspace/dashboard/summary');
    await login(reviewerPage, server, null, { username: 'reviewer', password: server.reviewerPassword });
    const reviewerDashboard = await reviewerDashboardPromise;
    assert.equal(reviewerDashboard.status(), 200, await reviewerDashboard.text());
    const reviewerToken = await reviewerPage.evaluate(() => sessionStorage.getItem('ova.token'));
    const reviewerWrite = await reviewerPage.request.post(server.base + '/api/reviews/batch', {
      headers: { Authorization: `Bearer ${reviewerToken}` }, data: {},
    });
    assert.equal(reviewerWrite.status(), 403, await reviewerWrite.text());
    checks.push('P0 reviewer dashboard uses the scoped read-only queue; review-write API denies reviewer role');
    const evaluationRequests = [];
    reviewerPage.on('request', request => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith('/api/evaluation/')) evaluationRequests.push(pathname);
    });
    await reviewerPage.evaluate(() => { location.hash = '#evaluation'; });
    await reviewerPage.locator('#evaluationData .panel').waitFor();
    const evaluationCopy = await reviewerPage.locator('#evaluationData').innerText();
    assert.match(evaluationCopy, /Archive lịch sử: BỊ CHẶN/);
    assert.match(evaluationCopy, /Không hiển thị metrics hoặc ảnh mẫu/);
    assert.equal(await reviewerPage.locator('#evaluationSamples, #errorGroup, [data-sample]').count(), 0,
      'blocked legacy data must not expose sample controls or case imagery');
    assert.deepEqual(evaluationRequests, ['/api/evaluation/metrics'],
      'the page must not fetch unverified archived samples');
    checks.push('P0 evaluation page withholds legacy metrics/samples and issues no sample request');
    await reviewerPage.evaluate(() => { location.hash = '#dashboard'; });
    await reviewerPage.waitForFunction(() => location.hash === '#dashboard');
    const file = name => ({ name, mimeType: 'image/png', buffer: pngBytes });
    const rightPng = fs.readFileSync(fixtures.right).toString('base64');
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
    assert.equal(await page.locator('[name=pid]').count(), 0,
      'Normal intake must not generate or request source patient identifiers.');
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2026-09-01T08:30');
    assert.equal(await page.locator('.intake-file-item').count(), 0,
      'leaving the first patient form must not carry its pending image into the next case');
    assert.equal(await page.locator('#metadataProposals button').count(), 0);
    checks.push('QA-001 stale metadata cannot cross facility-directory selection; intake has no generated PID');
    await page.unroute('**/api/intake/extract-metadata');
    await page.route('**/api/intake/extract-metadata', route => json(route, { metadata: {
      pid: { value: 'SYNTHETIC-CURRENT', source: 'dicom', confidence: 0.99 },
      study_date: { value: '2025-01-02T11:22', source: 'dicom', confidence: 0.98 },
    } }));
    await page.locator('[data-file=L]').setInputFiles(file('left.png'));
    await page.locator('#metadataProposals button').first().waitFor();
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2026-09-01T08:30');
    await page.locator('#metadataProposals button').first().click();
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2025-01-02T11:22');
    checks.push('QA-001 DICOM patient identifiers are ignored; date metadata remains a proposal until explicit apply');
    await page.unroute('**/api/intake/extract-metadata');
    const dicomMetadataBaselineDate = await page.locator('[name=study-date]').inputValue();
    const dicomMetadataResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/intake/extract-metadata');
    await page.locator('[data-file=L]').setInputFiles({
      name: 'synthetic_ovary.dcm',
      mimeType: 'application/dicom',
      buffer: fs.readFileSync(fixtures.dicom),
    });
    const dicomMetadataResponse = await dicomMetadataResponsePromise;
    assert.equal(dicomMetadataResponse.status(), 200, await dicomMetadataResponse.text());
    const dicomMetadataBody = await dicomMetadataResponse.json();
    assert.equal(dicomMetadataBody.metadata.pid.value, '000000001');
    assert.equal(dicomMetadataBody.metadata.pid.source, 'dicom');
    assert.equal(dicomMetadataBody.metadata.study_date.value, '2026-10-25T14:30');
    assert.equal(dicomMetadataBody.calibration.calibrated, true);
    assert.equal(dicomMetadataBody.calibration.pixel_spacing_mm, 0.1);
    await page.waitForTimeout(500);
    const dicomDateProposal = page.locator('#metadataProposals > div')
      .filter({ hasText: 'Ngày DICOM (L, synthetic_ovary.dcm)' });
    assert.equal(await page.locator('#metadataProposals').getByText(/PID nguồn/).count(), 0,
      'Source IDs extracted from DICOM must not be exposed as an intake field or proposal.');
    assert.equal(await dicomDateProposal.count(), 1,
      `DICOM date proposal was not rendered: ${await page.locator('#metadataProposals').innerText()}`);
    assert.equal(await page.locator('[name=study-date]').inputValue(), dicomMetadataBaselineDate);
    await page.locator('#metadataProposals > div')
      .filter({ hasText: 'Ngày DICOM (L, synthetic_ovary.dcm)' }).locator('button').click();
    assert.equal(await page.locator('[name=study-date]').inputValue(), '2026-10-25T14:30');
    checks.push('P0 DICOM source patient IDs stay out of intake; date/spacing metadata remain reviewable proposals');
    await page.route('**/api/intake/extract-metadata', route => json(route, { metadata: {} }));
    await page.locator('#files-L .intake-file-item')
      .filter({ hasText: 'left.png' }).locator('[data-remove-file]').click();
    await page.locator('[data-remove-file]').click();
    assert.equal(await page.locator('[data-confirm-file]').count(), 0);
    await page.unroute('**/api/intake/extract-metadata');
    await page.route('**/api/intake/extract-metadata', route => route.abort());
    await page.locator('[data-file=L]').setInputFiles(file('metadata-network-failure.png'));
    await page.waitForFunction(() => document.querySelector('#files-L .form-error')?.textContent.includes('Không lấy được gợi ý metadata'));
    assert.equal(await page.locator('[data-confirm-file]').isChecked(), false,
      'A metadata network error must not silently confirm the image laterality.');
    await page.locator('[data-confirm-file]').check();
    assert.match(await page.locator('#files-L .intake-side-confirm').innerText(), /xác nhận ảnh này thuộc bên trái/i);
    checks.push('QA-008 metadata network failure is visible and requires an explicit clinician laterality confirmation');
    await page.locator('[data-remove-file]').click();
    await page.unroute('**/api/intake/extract-metadata');
    await page.route('**/api/intake/extract-metadata', route => json(route, { metadata: {} }));
    await page.locator('.dropzone[data-side=L]').evaluate((element, sources) => {
      const transfer = new DataTransfer();
      for (const [index, name] of ['scan-1.png', 'scan-2.png'].entries()) {
        const bytes = Uint8Array.from(atob(sources[index]), char => char.charCodeAt(0));
        transfer.items.add(new File([bytes], name, { type: 'image/png' }));
      }
      element.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, [png, rightPng]);
    const sideConfirmations = page.locator('[data-confirm-file]');
    await sideConfirmations.nth(1).waitFor({ state: 'visible' });
    assert.equal(await sideConfirmations.count(), 2);
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await sideConfirmations.nth(0).check();
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await sideConfirmations.nth(1).check();
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    checks.push('QA-004 ambiguous pair requires explicit side confirmations');
    await page.locator('[data-action=swap-sides]').click();
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    const swappedConfirmations = page.locator('[data-confirm-file]');
    await swappedConfirmations.nth(0).check(); await swappedConfirmations.nth(1).check();
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    checks.push('QA-004 swapping files invalidates prior side confirmations');
    for (const width of [1366, 1024, 768]) {
      await page.setViewportSize({ width, height: 768 });
      await page.evaluate(() => {
        window.scrollTo(0, 0);
        for (const element of document.querySelectorAll('body *')) {
          const overflowY = getComputedStyle(element).overflowY;
          if (['auto', 'scroll'].includes(overflowY)) element.scrollTop = 0;
        }
      }); await paint(page);
      const naturalPlacement = await page.locator('#startSegmentationBtn').evaluate(element => {
        const rect = element.getBoundingClientRect();
        let scroller = element.parentElement;
        while (scroller && scroller.scrollHeight <= scroller.clientHeight + 1) scroller = scroller.parentElement;
        return { top: rect.top, bottom: rect.bottom, height: innerHeight,
          scroller: scroller ? (scroller.id || scroller.className || scroller.tagName) : 'document',
          scrollTop: scroller?.scrollTop ?? document.scrollingElement.scrollTop };
      });
      if (width === 1366) {
        assert.ok(naturalPlacement.top >= 0 && naturalPlacement.bottom <= naturalPlacement.height - 32,
          `CTA is available without scrolling at 1366x768: ${JSON.stringify(naturalPlacement)}`);
      }
      if (width === 1366) {
        await page.screenshot({ path: path.join(out, 'intake-1366-before-action-scroll.png') });
      }
      await page.locator('#startSegmentationBtn').scrollIntoViewIfNeeded();
      await paint(page);
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
      const scrollAfter = await page.locator('#startSegmentationBtn').evaluate(element => {
        let scroller = element.parentElement;
        while (scroller && scroller.scrollHeight <= scroller.clientHeight + 1) scroller = scroller.parentElement;
        return scroller?.scrollTop ?? document.scrollingElement.scrollTop;
      });
      geometries.push({ width, naturalPlacement, scrollTopAfter: scrollAfter, ...geometry });
      await page.screenshot({ path: path.join(out, `intake-${width}.png`) });
    }
    checks.push('QA-006 CTA is reachable without overlap at laptop/tablet sizes; initial below-fold placement is recorded');

    await page.locator('[data-action=change-patient]').click();
    await page.locator('[data-select="2"]').click();
    await page.locator('[name=study-date]').fill('2026-10-27T09:15');
    await page.locator('[data-file=L]').setInputFiles(file('scan-left.png'));
    await page.locator('[data-unavailable=R]').check();
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true,
      'single-sided intake remains blocked until the missing-side state is explicit');
    await page.locator('[data-unavailable-status=R]').selectOption('NOT_VISUALIZED');
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
    assert.match(await page.locator('#intakeHint').textContent(), /khảo sát một bên/i);
    checks.push('GAP-01 one-sided intake requires and accepts an explicit unobserved-side status');

    let createCaseRequests = 0, releaseCreateCase, notifyCreateCase;
    const createCaseStarted = new Promise(resolve => { notifyCreateCase = resolve; });
    const createCaseHeld = new Promise(resolve => { releaseCreateCase = resolve; });
    await page.route('**/api/cases', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      createCaseRequests++;
      notifyCreateCase();
      await createCaseHeld;
      return json(route, { detail: 'Synthetic case-create failure' }, 503);
    });
    const failedCaseCreateResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/cases');
    await page.locator('#startSegmentationBtn').dblclick();
    await createCaseStarted;
    await page.waitForFunction(() => document.querySelector('#startSegmentationBtn')?.disabled);
    await page.waitForTimeout(100);
    assert.equal(createCaseRequests, 1, 'A second click while case creation is pending must not duplicate the request.');
    releaseCreateCase();
    const failedCaseCreateResponse = await failedCaseCreateResponsePromise;
    assert.equal(failedCaseCreateResponse.status(), 503);
    await page.locator('[data-action=retry-upload-error]').waitFor();
    assert.equal(createCaseRequests, 1);
    await page.unroute('**/api/cases');
    checks.push('QA-007 double-click during a pending case-create request sends one request and retains an actionable error');

    const committedStudyIds = [], createIdempotencyKeys = [];
    let notifyFirstCaseCommit;
    const firstCaseCommitted = new Promise(resolve => { notifyFirstCaseCommit = resolve; });
    await page.route('**/api/cases', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      const upstream = await route.fetch();
      const upstreamStatus = upstream.status();
      const upstreamHeaders = upstream.headers();
      const upstreamBody = await upstream.text();
      assert.equal(upstreamStatus, 200, upstreamBody);
      const created = JSON.parse(upstreamBody);
      committedStudyIds.push(created.study_id);
      createIdempotencyKeys.push(route.request().headers()['idempotency-key'] || null);
      if (committedStudyIds.length === 1) {
        notifyFirstCaseCommit(created.study_id);
        return route.abort('connectionreset');
      }
      return route.fulfill({ status: upstreamStatus, headers: upstreamHeaders, body: upstreamBody });
    });
    await page.route('**/api/upload', route => json(route, { detail: 'Synthetic upload failure after case creation' }, 503));
    await page.locator('[data-action=retry-upload-error]').click();
    await firstCaseCommitted;
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'synthetic case creation settled' });
    const intakeAfterLostResponse = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return { busy: state.busy, hint: document.querySelector('#intakeHint')?.textContent,
        startDisabled: document.querySelector('#startSegmentationBtn')?.disabled,
        patientDirectoryId: state.case?.patient_directory_id,
        date: document.querySelector('[name=study-date]')?.value,
        files: [...document.querySelectorAll('.intake-file-item')].map(row => ({
          name: row.querySelector('strong')?.textContent,
          confirmed: row.querySelector('[data-confirm-file]')?.checked,
        })),
        unavailable: [...document.querySelectorAll('[data-unavailable-status]')].map(input => input.value),
        error: document.querySelector('#intakeError')?.innerText };
    });
    assert.equal(committedStudyIds.length, 1,
      `The upstream create must commit even though its browser response was lost; state=${JSON.stringify(intakeAfterLostResponse)}`);
    const uploadFailureResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/upload');
    await page.locator('[data-action=retry-upload-error]').click();
    const actualUploadFailure = await uploadFailureResponse;
    assert.equal(actualUploadFailure.status(), 503);
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'image upload retry settled' });
    assert.equal(committedStudyIds.length, 2, 'Retry must reach the real create endpoint after the lost response.');
    assert.equal(new Set(committedStudyIds).size, 1,
      `A response lost after commit must replay the same case, got ${JSON.stringify(committedStudyIds)}.`);
    assert.ok(createIdempotencyKeys[0], 'Case creation must send a stable Idempotency-Key.');
    assert.equal(createIdempotencyKeys[1], createIdempotencyKeys[0], 'Retry must reuse the original idempotency key.');
    const auth = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const replayedCase = await page.request.get(server.base + `/api/cases/${committedStudyIds[0]}`, {
      headers: { Authorization: `Bearer ${auth}` },
    });
    assert.equal(replayedCase.status(), 200, await replayedCase.text());
    await page.unroute('**/api/cases');
    await page.unroute('**/api/upload');
    checks.push('P0 retry after a lost post-commit response reuses the same persisted case and idempotency key');

    const committedUploadIds = [];
    let notifyFirstUploadCommit;
    const firstUploadCommitted = new Promise(resolve => { notifyFirstUploadCommit = resolve; });
    await page.route('**/api/upload', async route => {
      const upstream = await route.fetch();
      const upstreamStatus = upstream.status();
      const upstreamHeaders = upstream.headers();
      const upstreamBody = await upstream.text();
      assert.equal(upstreamStatus, 200, upstreamBody);
      committedUploadIds.push(JSON.parse(upstreamBody).image_id);
      if (committedUploadIds.length === 1) {
        notifyFirstUploadCommit(committedUploadIds[0]);
        return route.abort('connectionreset');
      }
      return route.fulfill({ status: upstreamStatus, headers: upstreamHeaders, body: upstreamBody });
    });
    await page.route('**/api/validate-image', route => json(route, { detail: 'Synthetic IQA stop after upload replay' }, 503));
    await page.locator('[data-action=retry-upload-error]').click();
    await firstUploadCommitted;
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'image upload replay settled' });
    const committedCaseWithImage = await page.request.get(server.base + `/api/cases/${committedStudyIds[0]}`, {
      headers: { Authorization: `Bearer ${auth}` },
    });
    assert.equal(committedCaseWithImage.status(), 200, await committedCaseWithImage.text());
    assert.equal((await committedCaseWithImage.json()).images.length, 1,
      'The first upload must have committed even though its browser response was dropped.');
    const uploadReplayResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/upload');
    await page.locator('[data-action=retry-upload-error]').click();
    const uploadReplayResponse = await uploadReplayResponsePromise;
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'final upload retry settled' });
    assert.equal(uploadReplayResponse.status(), 200,
      `Retry after committed upload must replay the existing image; body=${await uploadReplayResponse.text()}`);
    assert.equal(committedUploadIds.length, 2);
    assert.equal(committedUploadIds[1], committedUploadIds[0],
      `Upload retry created a different image id: ${JSON.stringify(committedUploadIds)}`);
    const caseAfterUploadReplay = await page.request.get(server.base + `/api/cases/${committedStudyIds[0]}`, {
      headers: { Authorization: `Bearer ${auth}` },
    });
    assert.equal((await caseAfterUploadReplay.json()).images.length, 1,
      'Upload replay must not duplicate the persisted image row.');
    await page.unroute('**/api/upload');
    await page.unroute('**/api/validate-image');
    checks.push('P0 retry after a lost post-commit image response reuses the same image and does not duplicate the row');

    const rle = { shape: [512, 512], first_val: 0, counts: [1000, 200, 260944] };
    const fixture = { study_id: 'safety-study', study_code: 'SYNTHETIC-SAFETY', patient_id: 'SYNTHETIC-ONLY',
      status: 'ANALYZED', study_date: '2026-10-25', version: 1, review_revision: 0,
      images: ['L', 'R'].map(side => ({ image_id: 'safety-' + side, laterality: side, width: 512, height: 512,
        prediction: { prediction_id: 'pred-' + side, rle_mask: rle, measurements: {}, provenance: { model_name: 'synthetic-fixture' } }, review: null })) };
    let batchCalls = 0, failSave = true, reportReads = 0;
    await page.route('**/api/cases/safety-study', route => { reportReads++; return json(route, fixture); });
    await page.route('**/api/workspace/cases/safety-study/lease', route => route.request().method() === 'DELETE'
      ? route.fulfill({ status: 204, body: '' }) : json(route, { granted: true, lease_token: 'synthetic-lease-token', expires_at: '2099-01-01T00:00:00Z' }));
    await page.route('**/api/hitl/sessions', route => json(route, { id: 'synthetic-safety-session' }));
    await page.route('**/api/hitl/sessions/*/events', route => json(route, { accepted: true, count: 1 }));
    await page.route('**/api/hitl/events', route => json(route, { success: true, count: 1 }));
    let holdRightSource = false, heldRightSource, notifyRightSource, failRightApprovalSourceOnce = false;
    let trackApprovalSourceConcurrency = false, activeApprovalSourceReads = 0, maxApprovalSourceReads = 0;
    await page.route('**/api/images/safety-*/viewer-source', route =>
      json(route, { original_image_base64: 'data:image/png;base64,' + png }));
    await page.route('**/api/images/safety-*/source.png', async route => {
      if (trackApprovalSourceConcurrency) {
        activeApprovalSourceReads++;
        maxApprovalSourceReads = Math.max(maxApprovalSourceReads, activeApprovalSourceReads);
        await new Promise(resolve => setTimeout(resolve, 20));
        activeApprovalSourceReads--;
      }
      if (failRightApprovalSourceOnce && route.request().url().includes('/safety-R/')) {
        failRightApprovalSourceOnce = false;
        return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic source image failure' }) });
      }
      if (holdRightSource && route.request().url().includes('/safety-R/')) {
        heldRightSource = route; notifyRightSource(); return;
      }
      return route.fulfill({ contentType: 'image/png', body: pngBytes });
    });
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
    const userScopedMaskKey = await page.evaluate(async () => {
      const { maskDraftKey } = await import('/static/app/state.js');
      return maskDraftKey('safety-study', 'safety-L');
    });
    const legacyUnscopedMaskKey = 'draft_mask_safety-study_safety-L';
    await page.evaluate(({ mask, scopedKey, legacyKey }) => {
      localStorage.setItem(scopedKey, JSON.stringify({
        schema_version: 2, study_id: 'safety-study', image_id: 'safety-L', side: 'L',
        base_version: 1, base_review_id: null, saved_at: Date.now(), mask_rle: mask,
      }));
      localStorage.setItem(legacyKey, JSON.stringify({
        schema_version: 1, study_id: 'safety-study', image_id: 'safety-L', side: 'L',
        base_version: 1, base_review_id: null, saved_at: Date.now(), mask_rle: mask,
      }));
    }, { mask: rle, scopedKey: userScopedMaskKey, legacyKey: legacyUnscopedMaskKey });
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.evaluate(() => { location.hash = '#viewer/safety-study'; });
    await waitForAppState(page, snapshot => snapshot.case?.study_id === 'safety-study' &&
      snapshot.case.images[0]?.seen && snapshot.case.images[0]?.mask_samples?.['1000'] === 1 &&
      !snapshot.dom.measurement_d1?.includes('Đang cập nhật'),
    { maskIndices: [1000], message: 'scoped mask draft restoration and first measurement' });
    await page.getByText('Đã phục hồi bản nháp chưa lưu gần nhất', { exact: true }).waitFor();
    await page.locator('#toasts [role=alert]').filter({ hasText: 'Phát hiện bản nháp mask cũ' }).waitFor();
    checks.push('RSK-02 restores only the current user’s mask draft and warns about unowned legacy data');
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
    assert.equal(await page.locator('#viewerImageSelect').isDisabled(), true,
      'image selection must lock while the selected source is still loading');
    assert.equal(await page.locator('[data-action^="side-"]:not(:disabled)').count(), 0,
      'side switching controls must lock while the selected source is still loading');
    await page.locator('#notes').evaluate(element => {
      element.value = 'Synthetic stale input while source is pending';
      element.dispatchEvent(new Event('input', { bubbles: true }));
    });
    assert.equal(await page.evaluate(async () => (await import('/static/app/state.js')).state.case.images[0].notes), '');
    await heldRightSource.fulfill({ contentType: 'image/png', body: pngBytes });
    holdRightSource = false;
    await waitForAppState(page, snapshot => snapshot.case?.images?.every(image => image.seen),
      { message: 'both synthetic sides viewed after source load' });
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
    await page.locator('#notes').fill('Nhận định O-RADS 2.');
    await page.locator('[data-action=quick-print]').click();
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'failed review save settled' });
    assert.equal(batchCalls, 1);
    assert.ok(await page.evaluate(key => localStorage.getItem(key), userScopedMaskKey),
      'failed review save must retain the local mask draft');
    assert.equal(page.url().includes('#viewer/safety-study'), true);
    assert.equal(await page.evaluate(() => window.__printCalls), 0);
    checks.push('QA-002 failed save retains viewer and never prints');
    // Acknowledged save prints only the persisted revision and actual reviewer.
    failSave = false;
    await page.locator('[data-action=quick-print]').click();
    await page.waitForFunction(() => location.hash.includes('revision=1'));
    await page.locator('#reportData .report-footer').first().waitFor();
    await page.waitForFunction(() => window.__printCalls === 1);
    assert.equal(await page.evaluate(key => localStorage.getItem(key), userScopedMaskKey), null,
      'a successfully acknowledged review must remove the per-side mask draft');
    assert.notEqual(await page.evaluate(key => localStorage.getItem(key), legacyUnscopedMaskKey), null,
      'an unowned legacy draft must not be deleted as if it belonged to the current clinician');
    assert.match(await page.locator('#reportData .report').innerText(), /actual-reviewer/);
    assert.doesNotMatch(await page.locator('#reportData .report').innerText(), /Người rà soát: doctor\b/);
    checks.push('QA-002/003 confirmed snapshot prints persisted reviewer and revision');
    const printRoot = page.locator('#printRoot .report');
    await printRoot.waitFor({ state: 'attached' });
    const printText = await printRoot.innerText();
    assert.match(printText, /O-RADS 2/);
    assert.match(printText, /Nhận định O-RADS 2\./);
    await page.emulateMedia({ media: 'print' });
    await page.pdf({ path: path.join(out, 'remediated-actual-print.pdf'), format: 'A4', printBackground: true });
    await page.emulateMedia({ media: 'screen' });
    fs.writeFileSync(path.join(out, 'remediated-actual-print-text.json'), JSON.stringify({
      scope: 'synthetic saved review rendered by the real browser print handler',
      reportPages: await printRoot.locator('.report-summary-page, .report-evidence-page').count(),
      text: printText,
    }, null, 2));
    // Opening a raw draft explicitly is allowed, but cannot claim a reviewer.
    fixture.images.forEach(image => { image.review = null; }); fixture.review_revision = 0;
    await page.evaluate(() => { location.hash = '#report/safety-study?draft=1'; });
    await page.locator('#reportData .report-footer').first().waitFor();
    const draftReport = await page.locator('#reportData .report').innerText();
    assert.match(draftReport, /Trạng thái lưu rà soát\s+Chưa lưu rà soát/);
    assert.match(draftReport, /Mask AI chưa được rà soát/);
    assert.match(draftReport, /Reviewer ID\s+Chưa có trong bản ghi/);
    assert.doesNotMatch(draftReport, /Người rà soát:/);
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

    const seededQueueCases = seedSignedPrelimQueue(server, 51, fixtures.left);
    assert.equal(seededQueueCases.length, 51);
    const foreignQueueCases = seedSignedPrelimQueue(server, 1, fixtures.left,
      'synthetic-other-facility', 'SYNTHETIC-FOREIGN');
    const reviewerScopeDenied = await reviewerPage.request.post(server.base + '/api/workspace/cases/search', {
      headers: { Authorization: `Bearer ${reviewerToken}` },
      data: { status: 'PENDING', limit: 50, offset: 0 },
    });
    assert.equal(reviewerScopeDenied.status(), 403, await reviewerScopeDenied.text());
    const foreignDetail = await reviewerPage.request.get(server.base + `/api/cases/${foreignQueueCases[0].study_id}`, {
      headers: { Authorization: `Bearer ${reviewerToken}` },
    });
    assert.equal(foreignDetail.status(), 403, await foreignDetail.text());
    checks.push('P0 reviewer cannot broaden the queue to pending cases or read another facility case');
    const reviewerSearchRequests = [];
    let queueTransitionWrites = 0;
    reviewerPage.on('request', request => {
      const url = new URL(request.url());
      if (request.method() === 'POST' && url.pathname === '/api/workspace/cases/search') {
        reviewerSearchRequests.push(request.postDataJSON());
      }
      if (request.method() === 'POST' && url.pathname.endsWith('/transitions')) queueTransitionWrites += 1;
    });
    const firstQueuePageResponsePromise = reviewerPage.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/workspace/cases/search');
    await reviewerPage.evaluate(() => { location.hash = '#approval'; });
    const firstQueuePageResponse = await firstQueuePageResponsePromise;
    assert.equal(firstQueuePageResponse.status(), 200, await firstQueuePageResponse.text());
    const firstQueuePage = await firstQueuePageResponse.json();
    assert.equal(firstQueuePage.total, 51);
    assert.equal(firstQueuePage.items.length, 50);
    assert.ok(firstQueuePage.items.every(item => item.status === 'SIGNED_PRELIM'));
    assert.equal(await reviewerPage.locator('#approvalData tbody tr').count(), 50);
    assert.match(await reviewerPage.locator('#approvalData').innerText(), /51 ca · Trang 1\/2/);
    assert.equal(reviewerSearchRequests[0].status, 'SIGNED_PRELIM');
    assert.equal(reviewerSearchRequests[0].statuses, null);
    assert.equal(reviewerSearchRequests[0].limit, 50);
    assert.equal(reviewerSearchRequests[0].offset, 0);

    const secondQueuePageResponsePromise = reviewerPage.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/workspace/cases/search');
    await reviewerPage.locator('#approvalNext').click();
    const secondQueuePageResponse = await secondQueuePageResponsePromise;
    assert.equal(secondQueuePageResponse.status(), 200, await secondQueuePageResponse.text());
    const secondQueuePage = await secondQueuePageResponse.json();
    assert.equal(secondQueuePage.items.length, 1);
    assert.equal(secondQueuePage.items[0].study_id, seededQueueCases[0].study_id);
    assert.ok(secondQueuePage.items.every(item => item.status === 'SIGNED_PRELIM'));
    assert.equal(await reviewerPage.locator('#approvalData tbody tr').count(), 1);
    assert.match(await reviewerPage.locator('#approvalData').innerText(), /51 ca · Trang 2\/2/);
    assert.equal(reviewerSearchRequests[1].offset, 50);
    checks.push('P0 live synthetic SIGNED_PRELIM reviewer queue filters and paginates correctly across 50 rows');

    const queueDetailResponsePromise = reviewerPage.waitForResponse(response =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname === `/api/cases/${seededQueueCases[0].study_id}`);
    const sourceImagePromise = reviewerPage.waitForResponse(response =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname === `/api/images/${seededQueueCases[0].image_id}/source.png`);
    await reviewerPage.locator(`#approvalData a[href="#approval/${seededQueueCases[0].study_id}"]`).click();
    const sourceImageResponse = await sourceImagePromise;
    assert.equal(sourceImageResponse.status(), 200, await sourceImageResponse.text());
    const queueDetailResponse = await queueDetailResponsePromise;
    assert.equal(queueDetailResponse.status(), 200, await queueDetailResponse.text());
    const signedQueueDetail = await queueDetailResponse.json();
    assert.equal(signedQueueDetail.status, 'SIGNED_PRELIM');
    assert.equal(signedQueueDetail.patient_id, 'SYNTHETIC-QUEUE-0001');
    assert.equal(signedQueueDetail.images.length, 1);
    assert.ok(signedQueueDetail.images[0].review);
    await reviewerPage.locator('.ruo-approval-notice').waitFor();
    await reviewerPage.waitForFunction(() => document.querySelectorAll('#page .approval-images img').length === 3);
    assert.match(await reviewerPage.locator('#page').innerText(), /chỉ để đối chiếu nội bộ/);
    assert.equal(await reviewerPage.locator('#page [data-action=approve], #page [data-action=reject], #page [data-action=lock]').count(), 0);
    assert.equal(queueTransitionWrites, 0);
    checks.push('P0 persisted SIGNED_PRELIM detail loads synthetic image/review evidence and remains read-only');

    fixture.status = 'SIGNED_PRELIM';
    fixture.signed_by = 'doctor';
    let transitionWrites = 0;
    page.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/transitions')) transitionWrites++;
    });
    trackApprovalSourceConcurrency = true;
    await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      state.user.role = 'SENIOR';
      location.hash = '#approval/safety-study';
    });
    await page.locator('.ruo-approval-notice').waitFor();
    const approvalCopy = await page.locator('#page').innerText();
    await page.waitForFunction(() => document.querySelectorAll('#page .approval-images img').length === 6,
      null, { timeout: 10000 });
    assert.match(approvalCopy, /Chức năng ký duyệt, chuyển trạng thái và phát hành kết quả lâm sàng chưa được triển khai/);
    assert.equal(await page.locator('#page [data-action=approve], #page [data-action=reject], #page [data-action=lock]').count(), 0,
      'The RUO review page must not expose unsupported approval or transition controls.');
    assert.equal(await page.locator('#page .approval-images img').count(), 6,
      'Both RUO sides must render the source image and clinician/AI outlines under the configured CSP.');
    assert.equal(maxApprovalSourceReads, 1,
      'Full-resolution source images must be decoded sequentially to bound peak browser memory.');
    trackApprovalSourceConcurrency = false;
    assert.equal(transitionWrites, 0, 'Opening a read-only RUO review page must not call an unimplemented transition endpoint.');
    checks.push('P0 approval queue is an explicit read-only RUO comparison page');
    failRightApprovalSourceOnce = true;
    await page.evaluate(() => { location.hash = '#dashboard'; });
    await waitForAppState(page, snapshot => snapshot.dom.hash === '#dashboard' &&
      snapshot.route === 'dashboard' && !snapshot.busy,
    { timeout: 10000, message: 'dashboard navigation after approval page' });
    await page.evaluate(() => { location.hash = '#approval/safety-study'; });
    await page.locator('#page [data-action=retry]').waitFor();
    assert.match(await page.locator('#approvalData').innerText(), /Không tải được ảnh\./);
    assert.equal(await page.locator('#page .approval-images img').count(), 0,
      'a failed source image must not leave the approval comparison looking complete');
    await page.locator('#page [data-action=retry]').click();
    await page.waitForFunction(() => document.querySelectorAll('#page .approval-images img').length === 6,
      null, { timeout: 10000 });
    assert.equal(failRightApprovalSourceOnce, false);
    checks.push('P0 approval image failure is visible and retry restores all six previews');

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
    assert.doesNotMatch(await quotaPage.locator('main').innerText(), /chỉ giữ trong phiên này/,
      'Facility directory records are loaded from the isolated server, not local browser storage.');
    await quotaPage.locator('[data-select="0"]').click();
    await quotaPage.locator('[data-file=L]').waitFor();
    checks.push('QA-005 independent browser reads the server-backed directory regardless of local storage quota');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'safety-results.json'), JSON.stringify({ status: 'PASS', checks, geometries,
      pageErrors: errors, scope: 'synthetic UI fault injection; isolated auth and reviewer queue reads; clinical writes mocked' }, null, 2));
    console.log(JSON.stringify({ status: 'PASS', checks, geometries, pageErrors: errors.length }));
  } finally {
    const isolatedRuntime = server.runtime;
    await server.close();
    assert.equal(fs.existsSync(isolatedRuntime), false,
      'The isolated safety database containing seeded synthetic reviewer cases must be removed.');
  }
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
