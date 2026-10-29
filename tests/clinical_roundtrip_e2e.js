/* Real API/DB/model roundtrip with generated non-patient grayscale fixtures. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const { waitForAppState } = require('./helpers/app_state_wait.cjs');

async function main() {
  const fixtures = ensureSyntheticFixtures();
  const server = await startIsolatedBrowser({ syntheticFixtureDir: fixtures.directory });
  const errors = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1366, height: 768 } });
    page.on('pageerror', error => errors.push(error.stack || error.message));
    // Successful responses and clinical writes use the isolated backend; only declared network-fault cases are intercepted.
    let hitlSessionRequest = null;
    const leaseTrace = [];
    page.on('request', request => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.endsWith('/lease')) {
        const body = ['POST', 'DELETE'].includes(request.method()) ? request.postDataJSON() : null;
        leaseTrace.push({ event: 'request', method: request.method(), tabId: body?.tab_id,
          pageInstanceId: body?.page_instance_id, hasLeaseToken: Boolean(body?.lease_token) });
      }
      if (request.method() === 'POST' && pathname === '/api/hitl/sessions') {
        hitlSessionRequest = { body: request.postDataJSON(), headers: request.headers() };
      }
    });
    page.on('response', response => {
      if (new URL(response.url()).pathname.endsWith('/lease')) {
        const leaseRequest = ['POST', 'DELETE'].includes(response.request().method())
          ? response.request().postDataJSON()
          : null;
        const entry = { event: 'response', status: response.status(),
          method: response.request().method(), tabId: leaseRequest?.tab_id,
          pageInstanceId: leaseRequest?.page_instance_id,
          hasPriorToken: Boolean(leaseRequest?.lease_token) };
        leaseTrace.push(entry);
        response.json().then(body => {
          entry.granted = body.granted;
          entry.expiresAt = body.expires_at;
          entry.released = body.released;
        }).catch(() => {});
      }
    });
    await page.goto(server.base + '/#login');
    assert.equal(await page.locator('.ruo-safety-banner').isVisible(), true);
    assert.match(await page.locator('.ruo-safety-banner').innerText(), /không dùng cho chăm sóc bệnh nhân/i);
    assert.match(await page.locator('.ruo-safety-banner').innerText(), /nguồn dữ liệu chưa được xác minh/i);
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.waitForFunction(() => document.querySelector('#syntheticDemoBanner')?.hidden === false);
    assert.equal(await page.locator('#environmentUnknownBanner').isHidden(), true);
    assert.match(await page.locator('#syntheticDemoBanner').innerText(), /không phải hồ sơ bệnh nhân/i);
    const demoHealthResponse = await page.request.get(server.base + '/api/health');
    assert.equal(demoHealthResponse.status(), 200);
    const demoHealth = await demoHealthResponse.json();
    assert.equal(demoHealth.capabilities.synthetic_demo_mode, true);
    assert.equal(demoHealth.capabilities.synthetic_demo_uploads_restricted, true);
    assert.equal(demoHealth.capabilities.clinical_production_ready, false);
    const readiness = await (await page.request.get(server.base + '/api/health/ready')).json();
    assert.equal(readiness.readiness_scope, 'TECHNICAL_SERVICE_ONLY');
    assert.equal(readiness.clinical_production_ready, false);
    let authToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const demoEvaluationResponse = await page.request.get(server.base + '/api/evaluation/metrics', {
      headers: { Authorization: 'Bearer ' + authToken },
    });
    assert.equal(demoEvaluationResponse.status(), 200);
    const demoEvaluation = await demoEvaluationResponse.json();
    assert.equal(demoEvaluation.current_run, null);
    assert.equal(demoEvaluation.current_run_status.status, 'SYNTHETIC_DEMO_BLOCKED');
    assert.equal(demoEvaluation.validation.dice_mean, null);
    assert.equal(demoEvaluation.test.dice_mean, null);

    for (const path of [
      '/api/evaluation/samples',
      '/api/evaluation/samples/known-case/workstation-bundle',
      '/api/evaluation/samples/known-case/download/image',
    ]) {
      const response = await page.request.get(server.base + path, {
        headers: { Authorization: 'Bearer ' + authToken },
      });
      const body = await response.text();
      assert.equal(response.status(), 403, `${path}: ${body}`);
      assert.match(body, /synthetic-only demo mode/i);
    }
    const ordinaryCase = await page.request.post(server.base + '/api/cases', {
      headers: { Authorization: 'Bearer ' + authToken, 'Idempotency-Key': 'ed1c7c2c-28f6-48e5-a6ec-2a4d2712875c' },
      data: { patient_id: '001234567', study_date: '2026-10-28', active_ovary_side: 'LEFT' },
    });
    const ordinaryCaseBody = await ordinaryCase.text();
    assert.equal(ordinaryCase.status(), 422, ordinaryCaseBody);
    assert.match(ordinaryCaseBody, /DEMO-SYNTHETIC/i);
    const caseWithPatientDetails = await page.request.post(server.base + '/api/cases', {
      headers: { Authorization: 'Bearer ' + authToken, 'Idempotency-Key': '739d26b4-17c8-4b25-b15b-1fdbcbff3a1d' },
      data: {
        patient_id: 'DEMO-SYNTHETIC-BLOCKED', study_date: '2026-10-28', active_ovary_side: 'LEFT',
        patient_age: '28', clinical_notes: 'Thông tin lâm sàng không được ghi trong sandbox demo',
      },
    });
    const caseWithPatientDetailsBody = await caseWithPatientDetails.text();
    assert.equal(caseWithPatientDetails.status(), 422, caseWithPatientDetailsBody);
    assert.match(caseWithPatientDetailsBody, /không nhận tuổi hoặc ghi chú lâm sàng/i);
    const changedFixture = Buffer.concat([fs.readFileSync(fixtures.left), Buffer.from([0])]);
    const rejectedMetadata = await page.request.post(server.base + '/api/intake/extract-metadata', {
      headers: { Authorization: 'Bearer ' + authToken },
      multipart: { file: { name: 'synthetic_tampered.png', mimeType: 'image/png', buffer: changedFixture } },
    });
    const rejectedMetadataBody = await rejectedMetadata.text();
    assert.equal(rejectedMetadata.status(), 422, rejectedMetadataBody);
    assert.match(rejectedMetadataBody, /fixture tổng hợp/i);
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-select="0"]').click();
    assert.match(await page.locator('.intake-metadata label.field').first().innerText(), /Mã ca demo.*DEMO-SYNTHETIC/i);
    assert.match(await page.locator('[name=pid]').getAttribute('placeholder'), /DEMO-SYNTHETIC/);
    assert.equal(await page.locator('[name=reason]').isDisabled(), true,
      'Demo mode must not collect clinical indication text.');
    await page.locator('[name=pid]').fill('DEMO-SYNTHETIC-0001');
    // Exercise the real browser→API→database path with a non-square source image.
    // This fixture is synthetic and its SHA-256 is already pinned by the RUO demo allowlist.
    await page.locator('[data-file=L]').setInputFiles(fixtures.letterbox);
    await page.locator('[data-file=R]').setInputFiles(fixtures.right);
    await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled, null, { timeout: 30000 }).catch(async error => {
      const intake = await page.evaluate(async () => ({
        busy: (await import('/static/app/state.js')).state.busy,
        user: (await import('/static/app/state.js')).state.user?.id,
        hint: document.querySelector('#intakeHint')?.textContent,
        buttonDisabled: document.querySelector('#startSegmentationBtn')?.disabled,
        date: document.querySelector('[name=study-date]')?.value,
        files: [...document.querySelectorAll('.intake-file-item')].map(row => ({
          name: row.querySelector('strong')?.textContent,
          confirmed: row.querySelector('[data-confirm-file]')?.checked,
          hint: row.querySelector('.form-error, .muted')?.textContent,
        })),
        proposals: document.querySelector('#metadataProposals')?.innerText,
      }));
      throw new Error(`Intake did not become ready: ${JSON.stringify(intake)}; ${error.message}`);
    });
    const committedPredictions = [];
    let notifyFirstPredictionCommit;
    const firstPredictionCommitted = new Promise(resolve => { notifyFirstPredictionCommit = resolve; });
    await page.route('**/api/predict/*', async route => {
      const upstream = await route.fetch();
      const upstreamStatus = upstream.status();
      const upstreamHeaders = upstream.headers();
      const upstreamBody = await upstream.text();
      if (upstreamStatus !== 200) {
        if (committedPredictions.length === 0)
          notifyFirstPredictionCommit({ status: upstreamStatus, body: upstreamBody });
        return route.fulfill({ status: upstreamStatus, headers: upstreamHeaders, body: upstreamBody });
      }
      const result = JSON.parse(upstreamBody);
      committedPredictions.push({
        image_id: result.image_id,
        prediction_id: result.prediction_id,
        idempotency_key: route.request().headers()['idempotency-key'] || null,
      });
      if (committedPredictions.length === 1) {
        notifyFirstPredictionCommit(result.prediction_id);
        return route.abort('connectionreset');
      }
      return route.fulfill({ status: upstreamStatus, headers: upstreamHeaders, body: upstreamBody });
    });
    const caseCreateResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/cases');
    await page.locator('#startSegmentationBtn').click();
    const createdCase = await caseCreateResponse;
    assert.equal(createdCase.status(), 200, await createdCase.text());
    assert.equal(createdCase.request().postDataJSON().clinical_notes, null,
      'The real intake request must not persist demo clinical notes.');
    await page.waitForFunction(() => /^\d{6}$/.test(document.querySelector('[data-visit-no]')?.textContent || ''));
    const visitNo = await page.locator('[data-visit-no]').textContent();
    const firstPredictionOutcome = await firstPredictionCommitted;
    assert.equal(firstPredictionOutcome?.status ?? 200, 200, firstPredictionOutcome?.body);
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'lost inference response retry settled' });
    await page.locator('[data-action=retry-upload-error]').waitFor();
    const predictionReplayResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.startsWith('/api/predict/'));
    await page.locator('[data-action=retry-upload-error]').click();
    const predictionReplayResponse = await predictionReplayResponsePromise;
    assert.equal(predictionReplayResponse.status(), 200, await predictionReplayResponse.text());
    assert.equal(committedPredictions.length, 2,
      `The first predict response must be dropped and the retry must replay once: ${JSON.stringify(committedPredictions)}`);
    assert.equal(committedPredictions[0].prediction_id, committedPredictions[1].prediction_id,
      `Lost inference response created a second prediction: ${JSON.stringify(committedPredictions)}`);
    assert.ok(committedPredictions[0].idempotency_key,
      'Each image inference must send a stable Idempotency-Key.');
    assert.equal(committedPredictions[0].idempotency_key, committedPredictions[1].idempotency_key,
      'Inference retry must reuse the original request key.');
    await page.unroute('**/api/predict/*');
    console.log('PASS: P0 lost inference response replays the committed prediction and preserves its prediction id');
    await page.waitForFunction(() => location.hash.startsWith('#viewer/'), { timeout: 90000 });
    await page.locator('#notes').waitFor();
    const id = await page.evaluate(() => location.hash.slice('#viewer/'.length));
    for (let attempt = 0; attempt < 50 && !hitlSessionRequest; attempt++) await page.waitForTimeout(100);
    assert.ok(hitlSessionRequest, 'The real UI must create an auditable HITL session for the synthetic case.');
    const rightImageId = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case?.images?.find(image => image.laterality === 'R')?.image_id;
    });
    assert.ok(rightImageId, 'The live roundtrip must finish inference for the right-side synthetic image.');
    const reusedForOtherImage = await page.request.post(
      server.base + `/api/predict/${rightImageId}`,
      { headers: {
        Authorization: 'Bearer ' + authToken,
        'Idempotency-Key': committedPredictions[0].idempotency_key,
        'X-Case-Lease-Token': hitlSessionRequest.headers['x-case-lease-token'],
        'X-Case-Page-Instance-Id': hitlSessionRequest.headers['x-case-page-instance-id'],
      } },
    );
    assert.equal(reusedForOtherImage.status(), 409, await reusedForOtherImage.text());
    console.log('PASS: inference idempotency key cannot be reused for another image snapshot');
    assert.equal(hitlSessionRequest.body.participant_role, 'technical_tester');
    assert.equal(hitlSessionRequest.body.data_origin, 'demo');
    assert.ok(hitlSessionRequest.headers['x-case-lease-token']);
    assert.ok(hitlSessionRequest.headers['x-case-page-instance-id']);
    const rejectedUpload = await page.request.post(server.base + '/api/upload', {
      headers: {
        Authorization: 'Bearer ' + authToken,
        'X-Case-Lease-Token': hitlSessionRequest.headers['x-case-lease-token'],
        'X-Case-Page-Instance-Id': hitlSessionRequest.headers['x-case-page-instance-id'],
      },
      multipart: {
        file: { name: 'synthetic_tampered.png', mimeType: 'image/png', buffer: changedFixture },
        study_id: id,
        laterality: 'L',
      },
    });
    const rejectedUploadBody = await rejectedUpload.text();
    if (rejectedUpload.status() !== 422) {
      const leaseState = await page.evaluate(async (capturedToken) => {
        const { state } = await import('/static/app/state.js');
        return {
          editingAllowed: state.editing?.allowed === true,
          editingCaseMatches: state.editing?.caseId === state.case?.study_id,
          activeTokenMatchesCaptured: state.editing?.leaseToken === capturedToken,
          hasActivePageId: Boolean(state.editing?.pageInstanceId),
          busy: state.busy,
          route: state.route,
        };
      }, hitlSessionRequest.headers['x-case-lease-token']);
      assert.equal(rejectedUpload.status(), 422, JSON.stringify({ body: rejectedUploadBody, leaseState, leaseTrace,
        capturedLeaseToken: Boolean(hitlSessionRequest.headers['x-case-lease-token']),
        capturedPageInstance: Boolean(hitlSessionRequest.headers['x-case-page-instance-id']) }));
    }
    assert.match(rejectedUploadBody, /fixture tổng hợp/i);
    const rejectedRawSegment = await page.request.post(server.base + '/api/v1/segment', {
      headers: { Authorization: 'Bearer ' + authToken },
      multipart: { file: { name: 'synthetic_tampered.png', mimeType: 'image/png', buffer: changedFixture } },
    });
    const rejectedRawSegmentBody = await rejectedRawSegment.text();
    assert.equal(rejectedRawSegment.status(), 422, rejectedRawSegmentBody);
    assert.match(rejectedRawSegmentBody, /fixture tổng hợp/i);
    const forcedDemoSession = await page.request.post(server.base + '/api/hitl/sessions', {
      headers: {
        Authorization: 'Bearer ' + authToken,
        'X-Case-Lease-Token': hitlSessionRequest.headers['x-case-lease-token'],
        'X-Case-Page-Instance-Id': hitlSessionRequest.headers['x-case-page-instance-id'],
      },
      data: { ...hitlSessionRequest.body, participant_role: 'clinician', data_origin: 'live' },
    });
    const forcedDemoSessionBody = await forcedDemoSession.text();
    if (forcedDemoSession.status() !== 200) {
      const leaseState = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          editingAllowed: state.editing?.allowed === true,
          editingCaseMatches: state.editing?.caseId === state.case?.study_id,
          hasEditingToken: Boolean(state.editing?.leaseToken),
          editingPageIdLength: state.editing?.pageInstanceId?.length ?? 0,
          busy: state.busy,
          route: state.route,
        };
      });
      assert.equal(forcedDemoSession.status(), 200, JSON.stringify({
        body: forcedDemoSessionBody,
        leaseState,
        leaseTrace,
        capturedLeaseToken: Boolean(hitlSessionRequest.headers['x-case-lease-token']),
        capturedPageInstance: Boolean(hitlSessionRequest.headers['x-case-page-instance-id']),
      }));
    }
    assert.equal(JSON.parse(forcedDemoSessionBody).participant_role, 'technical_tester');
    assert.equal(JSON.parse(forcedDemoSessionBody).data_origin, 'demo');
    await page.waitForFunction(() => {
      const side = document.querySelector('#sideLabel')?.textContent || '';
      const summary = document.querySelector('#viewerImageSummary')?.textContent || '';
      return side.includes('trái') && summary.includes('Mask');
    }, null, { timeout: 30000 }).catch(async error => {
      const debug = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js').catch(() => ({ state: {} }));
        return {
          route: state.route,
          side: state.side,
          editingAllowed: state.editing?.allowed,
          busy: state.busy,
          sideLabel: document.querySelector('#sideLabel')?.textContent,
          summary: document.querySelector('#viewerImageSummary')?.textContent,
          selectorOptions: document.querySelector('#viewerImageSelect')?.options?.length,
          error: document.querySelector('.error-page')?.innerText || document.querySelector('#page')?.innerText?.slice(0, 400),
          pageText: document.body.innerText.slice(-500),
        };
      });
      throw new Error(`Initial image did not finish rendering: ${JSON.stringify({ debug, pageErrors: errors, timeout: error.message })}`);
    });
    const activeImageId = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case?.images?.find(image => image.laterality === state.side)?.image_id;
    });
    assert.ok(activeImageId);
    assert.notEqual(activeImageId, rightImageId);
    const bitmapProbeInstalled = await page.evaluate(() => {
      const bitmapPrototype = window.ImageBitmap?.prototype;
      const canvasPrototype = window.CanvasRenderingContext2D?.prototype;
      const createDescriptor = Object.getOwnPropertyDescriptor(window, 'createImageBitmap');
      const closeDescriptor = bitmapPrototype && Object.getOwnPropertyDescriptor(bitmapPrototype, 'close');
      const drawDescriptor = canvasPrototype && Object.getOwnPropertyDescriptor(canvasPrototype, 'drawImage');
      if (!createDescriptor?.configurable || !closeDescriptor?.configurable || !drawDescriptor?.configurable) return false;
      let failNextBitmapDraw = true;
      const trackedBitmaps = new WeakSet();
      const originalCreate = window.createImageBitmap.bind(window);
      window.__closedViewerBitmaps = 0;
      window.__createdViewerBitmaps = 0;
      const originalClose = closeDescriptor.value;
      const originalDraw = drawDescriptor.value;
      Object.defineProperty(window, 'createImageBitmap', {
        ...createDescriptor,
        value: async function (...args) {
          const bitmap = await originalCreate(...args);
          trackedBitmaps.add(bitmap);
          window.__createdViewerBitmaps += 1;
          return bitmap;
        },
      });
      Object.defineProperty(bitmapPrototype, 'close', {
        ...closeDescriptor,
        value: function (...args) {
          if (trackedBitmaps.has(this)) window.__closedViewerBitmaps += 1;
          return originalClose.apply(this, args);
        },
      });
      Object.defineProperty(canvasPrototype, 'drawImage', {
        ...drawDescriptor,
        value: function (source, ...args) {
          if (failNextBitmapDraw && source instanceof window.ImageBitmap) {
            failNextBitmapDraw = false;
            throw new Error('Injected source-canvas draw failure.');
          }
          return originalDraw.call(this, source, ...args);
        },
      });
      window.__restoreViewerBitmapProbe = () => {
        Object.defineProperty(window, 'createImageBitmap', createDescriptor);
        Object.defineProperty(bitmapPrototype, 'close', closeDescriptor);
        Object.defineProperty(canvasPrototype, 'drawImage', drawDescriptor);
      };
      return true;
    });
    assert.equal(bitmapProbeInstalled, true, 'Browser must support reversible bitmap lifecycle instrumentation.');
    await page.locator('#viewerImageSelect').selectOption(rightImageId);
    await page.waitForFunction(() => document.querySelector('#viewerImageSummary')?.textContent
      .includes('Không hiển thị được ảnh. Chọn lại ảnh để thử.')).catch(async error => {
      const debug = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          side: state.side,
          selecting: document.querySelector('#viewerImageSelect')?.disabled,
          selected: document.querySelector('#viewerImageSelect')?.value,
          summary: document.querySelector('#viewerImageSummary')?.textContent,
          label: document.querySelector('#sideLabel')?.textContent,
          closedBitmaps: window.__closedViewerBitmaps,
          rightSeen: state.case?.images?.find(image => image.laterality === 'R')?.seen,
        };
      });
      throw new Error(`Bitmap draw fault was not handled as expected: ${JSON.stringify({ debug, pageErrors: errors, timeout: error.message })}`);
    });
    const failedImageSwitch = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const right = state.case?.images?.find(image => image.laterality === 'R');
      return {
        createdBitmaps: window.__createdViewerBitmaps,
        closedBitmaps: window.__closedViewerBitmaps,
        side: state.side,
        failedImageSeen: right?.seen === true,
        selectorValue: document.querySelector('#viewerImageSelect')?.value,
        selectorDisabled: document.querySelector('#viewerImageSelect')?.disabled,
        brushDisabled: document.querySelector('[data-tool="brush"]')?.disabled,
        saveDisabled: document.querySelector('[data-action="save-review"]')?.disabled,
      };
    });
    assert.equal(failedImageSwitch.createdBitmaps, 1, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.closedBitmaps, failedImageSwitch.createdBitmaps, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.side, 'L', JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.failedImageSeen, false, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.selectorValue, activeImageId, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.selectorDisabled, false, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.brushDisabled, true, JSON.stringify(failedImageSwitch));
    assert.equal(failedImageSwitch.saveDisabled, true, JSON.stringify(failedImageSwitch));
    await page.evaluate(() => window.__restoreViewerBitmapProbe());
    await page.locator('#viewerImageSelect').selectOption(rightImageId);
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('#viewerImageSelect').selectOption(activeImageId);
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('trái'));
    await page.evaluate(() => {
      const details = document.querySelector('.view-more');
      if (details && !details.open) details.querySelector('summary')?.click();
    });
    await page.locator('[data-action="bilateral"]').click();
    await page.locator('#secondPane').waitFor({ state: 'visible' });
    await page.evaluate(() => {
      const prototype = CanvasRenderingContext2D.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, 'drawImage');
      const originalDraw = descriptor.value;
      let failNextBitmapDraw = true;
      Object.defineProperty(prototype, 'drawImage', {
        ...descriptor,
        value(source, ...args) {
          if (failNextBitmapDraw && source instanceof window.ImageBitmap) {
            failNextBitmapDraw = false;
            throw new Error('Injected primary draw failure while bilateral comparison is visible.');
          }
          return originalDraw.call(this, source, ...args);
        },
      });
      window.__restorePrimaryDrawProbe = () => Object.defineProperty(prototype, 'drawImage', descriptor);
    });
    await page.locator('#viewerImageSelect').selectOption(rightImageId);
    await page.waitForFunction(() => document.querySelector('#viewerImageSummary')?.textContent
      .includes('Không hiển thị được ảnh. Chọn lại ảnh để thử.'));
    const failedComparisonImageSwitch = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        paneHidden: document.querySelector('#secondPane')?.hidden,
        selectedImageId: document.querySelector('#viewerImageSelect')?.value,
        side: state.side,
      };
    });
    assert.equal(failedComparisonImageSwitch.paneHidden, true,
      'A failed primary image switch must hide the comparison pane to avoid pairing a blank canvas with a stale image');
    assert.equal(failedComparisonImageSwitch.selectedImageId, activeImageId, JSON.stringify(failedComparisonImageSwitch));
    assert.equal(failedComparisonImageSwitch.side, 'L', JSON.stringify(failedComparisonImageSwitch));
    await page.evaluate(() => window.__restorePrimaryDrawProbe());
    await page.locator('#viewerImageSelect').selectOption(rightImageId);
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('#secondPane').waitFor({ state: 'visible' });
    await page.locator('#viewerImageSelect').selectOption(activeImageId);
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('trái'));
    await page.locator('#secondPane').waitFor({ state: 'visible' });
    await page.evaluate(() => {
      const details = document.querySelector('.view-more');
      if (details && !details.open) details.querySelector('summary')?.click();
    });
    await page.locator('[data-action="compare"]').click();
    await page.waitForFunction(() => document.querySelector('#secondPane .canvas-label')?.textContent === 'Ảnh gốc');
    await page.evaluate(() => {
      const details = document.querySelector('.view-more');
      if (details && !details.open) details.querySelector('summary')?.click();
    });
    await page.locator('[data-action="compare"]').click();
    await page.waitForFunction(() => document.querySelector('#secondPane')?.hidden);
    await page.locator('#notes').fill('Rà soát kỹ thuật ảnh tổng hợp bên trái.');
    console.log('PASS: failed viewer bitmap draw closes the resource, hides stale bilateral comparison and leaves retry safe');
    const clickSourcePoint = async (x, y) => {
      const point = await page.locator('#viewport').evaluate((canvas, sourcePoint) => {
        const rect = canvas.getBoundingClientRect();
        const scale = Math.min(rect.width / 512, rect.height / 512) * 0.94;
        return {
          x: rect.left + (rect.width - 512 * scale) / 2 + sourcePoint.x * scale,
          y: rect.top + (rect.height - 512 * scale) / 2 + sourcePoint.y * scale,
        };
      }, { x, y });
      await page.mouse.click(point.x, point.y);
    };
    // Ensure a known synthetic component exists even if the model legitimately
    // returns an empty mask for this generated frame.
    await page.locator('[data-tool="brush"]').click();
    const canvasRect = await page.locator('#viewport').evaluate(canvas => {
      const rect = canvas.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    });
    await page.mouse.click(canvasRect.x, canvasRect.y);
    const brushDebug = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      const maskPixels = left?.mask?.reduce((sum, value) => sum + Number(Boolean(value)), 0);
      const aiPixels = left?.aiMask?.reduce((sum, value) => sum + Number(Boolean(value)), 0);
      return { allowed: state.editing?.allowed, busy: state.busy, dirty: state.dirty,
        maskLength: left?.mask?.length, aiLength: left?.aiMask?.length,
        maskPixels, aiPixels,
        changed: left?.mask?.some((value, index) => value !== left.aiMask[index]),
        brushActive: document.querySelector('[data-tool="brush"]')?.classList.contains('active'),
        status: document.querySelector('#draftStatus')?.textContent };
    });
    assert.equal(brushDebug.allowed, true, 'The synthetic reviewer must hold the active edit lease.');
    assert.equal(brushDebug.changed, true,
      `The real Canvas stroke must modify the displayed mask before saving: ${JSON.stringify(brushDebug)}`);
    assert.ok(brushDebug.maskPixels > 0, 'The saved synthetic review must contain the Canvas-painted component.');
    const draftBeforeLeaseReload = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      return {
        allowed: state.editing?.allowed,
        imageId: left?.image_id,
        notes: left?.notes,
        maskPixels: left?.mask?.reduce((sum, value) => sum + Number(Boolean(value)), 0),
      };
    });
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('ova:lease-lost')));
    await page.locator('#leaseLostNotice').waitFor({ state: 'visible' });
    assert.equal(await page.locator('[data-tool="caliper-d1"]').isDisabled(), true,
      'Losing the lease must disable clinical editing tools immediately.');
    assert.equal(await page.locator('[data-action=lease-reload]').isVisible(), true,
      'Lease loss must leave a persistent recovery action, not only a transient toast.');
    const sourceImagePattern = `**/api/images/${draftBeforeLeaseReload.imageId}/source.png`;
    let releaseSourceImage;
    let notifySourceImageBlocked;
    const sourceImageBlocked = new Promise(resolve => { notifySourceImageBlocked = resolve; });
    const sourceImageRelease = new Promise(resolve => { releaseSourceImage = resolve; });
    let holdNextSourceImage = true;
    await page.route(sourceImagePattern, async route => {
      if (holdNextSourceImage) {
        holdNextSourceImage = false;
        notifySourceImageBlocked();
        await sourceImageRelease;
      }
      await route.continue();
    });
    const reloadNavigation = page.waitForNavigation({ waitUntil: 'domcontentloaded' });
    await page.locator('[data-action=lease-reload]').click();
    await reloadNavigation;
    await page.locator('#notes').waitFor();
    await sourceImageBlocked;
    assert.equal(await page.locator('[data-tool="caliper-d1"]').isDisabled(), true,
      'Canvas tools must stay disabled while the selected image is loading.');
    const sourceImageLoaded = page.waitForResponse(response =>
      new URL(response.url()).pathname === `/api/images/${draftBeforeLeaseReload.imageId}/source.png`);
    releaseSourceImage();
    await sourceImageLoaded;
    await page.unroute(sourceImagePattern);
    await waitForAppState(page, snapshot => snapshot.editing?.caseId === id &&
      snapshot.editing.allowed && !snapshot.draftConflict,
    { timeout: 30000, message: 'same-user lease reacquired without draft conflict' });
    const draftAfterLeaseReload = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      return {
        conflict: Boolean(state.draftConflict),
        notes: left?.notes,
        maskPixels: left?.mask?.reduce((sum, value) => sum + Number(Boolean(value)), 0),
      };
    });
    assert.equal(draftAfterLeaseReload.conflict, false);
    assert.equal(draftAfterLeaseReload.notes, draftBeforeLeaseReload.notes,
      'The local clinical draft must be restored after a successful lease reacquire.');
    assert.equal(draftAfterLeaseReload.maskPixels, draftBeforeLeaseReload.maskPixels,
      'The local mask draft must be restored byte-for-byte when its base revision matches.');
    assert.equal(await page.locator('#leaseLostNotice').isHidden(), true,
      'A reloaded viewer with a renewed lease must clear the persistent recovery notice.');
    await page.locator('[data-tool="caliper-d1"]').click();
    await clickSourcePoint(100, 256);
    await page.waitForFunction(() => document.querySelector('#viewerImageSummary')?.textContent.includes('Caliper D1: chọn điểm thứ hai.'));
    await clickSourcePoint(400, 256);
    await page.waitForFunction(() => document.querySelector('#viewerImageSummary')?.textContent.includes('Caliper bác sĩ đã đặt: D1'));
    const leftD1Text = await page.locator('#d1').textContent();
    const leftD1 = Number.parseFloat(leftD1Text);
    assert.ok(leftD1 > 374 && leftD1 < 376,
      `The clinician D1 caliper should be 375 decoded-source px after 640×480 letterboxing, got ${leftD1Text}.`);
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('#notes').fill('Rà soát kỹ thuật ảnh tổng hợp bên phải.');
    await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      window.__reviewNavigationTrace = [];
      const record = event => window.__reviewNavigationTrace.push({
        event,
        busy: state.busy,
        route: state.route,
        hash: location.hash,
        time: performance.now(),
      });
      window.addEventListener('ova:busy-changed', () => record('busy'));
      window.addEventListener('hashchange', () => record('hashchange'));
    });
    const failedReviewResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/reviews/batch');
    await page.route('**/api/reviews/batch', route => route.request().method() === 'POST'
      ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic review service unavailable' }) })
      : route.continue());
    await page.locator('[data-action=save-review]').click();
    const failedReview = await failedReviewResponse;
    assert.equal(failedReview.status(), 503, await failedReview.text());
    // Wait on the visible UI state, then inspect the app model from the page context.
    await page.waitForFunction(
      () => document.querySelector('[data-action="save-review"]')?.disabled === false,
      null,
      { timeout: 10000 },
    );
    const draftBeforeNavigation = await page.evaluate(async () => {
      const { state, draftKey, maskDraftKey } = await import('/static/app/state.js');
      const left = state.case.images.find(image => image.laterality === 'L');
      const right = state.case.images.find(image => image.laterality === 'R');
      return {
        userId: state.user?.id,
        dirty: state.dirty,
        reviewRevision: state.case.review_revision,
        conflict: Boolean(state.draftConflict),
        leftNotes: left.notes,
        rightNotes: right.notes,
        leftMaskPixels: Array.from(left.mask).reduce((sum, pixel) => sum + pixel, 0),
        liveDraftSaved: Boolean(localStorage.getItem(draftKey(state.case.study_id))),
        maskDraftSaved: Boolean(localStorage.getItem(maskDraftKey(state.case.study_id, left.image_id))),
        tabId: sessionStorage.getItem('ova.tab_id'),
        pageInstanceId: sessionStorage.getItem('ova.page_instance_id'),
        hasServerLeaseToken: Boolean(sessionStorage.getItem('ova.server-lease.' + state.case.study_id)),
      };
    });
    assert.equal(draftBeforeNavigation.dirty, true);
    assert.equal(draftBeforeNavigation.reviewRevision, 0,
      'a failed review POST must not advance the saved revision');
    assert.equal(draftBeforeNavigation.conflict, false);
    assert.ok(draftBeforeNavigation.liveDraftSaved);
    assert.ok(draftBeforeNavigation.maskDraftSaved);
    await page.unroute('**/api/reviews/batch');
    const idleBeforeNavigation = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return { busy: state.busy, route: state.route, hash: location.hash,
        trace: window.__reviewNavigationTrace };
    });
    assert.equal(idleBeforeNavigation.busy, false, JSON.stringify(idleBeforeNavigation));
    await page.evaluate(() => { location.hash = '#cases'; });
    await page.locator('#caseResults').waitFor({ timeout: 10000 }).catch(async error => {
      const stateAtFailure = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          hash: location.hash,
          route: state.route,
          busy: state.busy,
          dirty: state.dirty,
          studyId: state.case?.study_id,
          draftConflict: Boolean(state.draftConflict),
          navigationTrace: window.__reviewNavigationTrace,
          pageText: document.querySelector('#page')?.innerText?.slice(0, 600),
        };
      });
      throw new Error(`Case list did not render after failed save: ${JSON.stringify({ ...stateAtFailure, pageErrors: errors })}; ${error.message}`);
    });
    await page.evaluate(studyId => { location.hash = '#viewer/' + studyId; }, id);
    await page.waitForFunction(({ expected }) =>
      document.querySelector('#notes')?.value === expected.leftNotes &&
      document.querySelector('#leaseLostNotice')?.hidden === true,
    { expected: draftBeforeNavigation }, { timeout: 15000 });
    const recoveredDraftAfterNavigation = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        dirty: state.dirty,
        reviewRevision: state.case.review_revision,
        conflict: Boolean(state.draftConflict),
        leftNotes: state.case.images.find(image => image.laterality === 'L').notes,
        rightNotes: state.case.images.find(image => image.laterality === 'R').notes,
        leftMaskPixels: Array.from(state.case.images.find(image => image.laterality === 'L').mask)
          .reduce((sum, pixel) => sum + pixel, 0),
      };
    });
    assert.deepEqual(recoveredDraftAfterNavigation, {
      dirty: true,
      reviewRevision: 0,
      conflict: false,
      leftNotes: draftBeforeNavigation.leftNotes,
      rightNotes: draftBeforeNavigation.rightNotes,
      leftMaskPixels: draftBeforeNavigation.leftMaskPixels,
    }, 'navigating away after a failed save must restore the same draft without claiming it is saved');
    console.log('PASS: failed real review POST preserves the per-user draft across navigation and API-backed reopen');

    const preReloadLeaseState = await page.evaluate(async studyId => {
      const { state } = await import('/static/app/state.js');
      return {
        studyId: state.editing?.caseId,
        editingAllowed: state.editing?.allowed,
        editingPageInstanceId: state.editing?.pageInstanceId,
        tabId: sessionStorage.getItem('ova.tab_id'),
        pageInstanceId: sessionStorage.getItem('ova.page_instance_id'),
        hasServerLeaseToken: Boolean(sessionStorage.getItem('ova.server-lease.' + studyId)),
        localLease: JSON.parse(localStorage.getItem('ova.lease.live.' + studyId) || 'null'),
      };
    }, id);
    assert.equal(preReloadLeaseState.editingAllowed, true,
      'the API-backed reopen must finish reacquiring its edit lease before reload: ' +
        JSON.stringify({ preReloadLeaseState, leaseTrace }));
    let reloadDialogType = null;
    page.once('dialog', async dialog => {
      reloadDialogType = dialog.type();
      await dialog.accept();
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    assert.equal(reloadDialogType, 'beforeunload',
      'dirty clinical drafts must require explicit confirmation before a browser reload');
    await page.waitForFunction(expectedNotes =>
      document.querySelector('#notes')?.value === expectedNotes,
    draftBeforeNavigation.leftNotes, { timeout: 15000 });
    const recoveredDraftAfterReload = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      const right = state.case?.images?.find(image => image.laterality === 'R');
      return {
        userId: state.user?.id,
        studyId: state.case?.study_id,
        dirty: state.dirty,
        reviewRevision: state.case?.review_revision,
        conflict: Boolean(state.draftConflict),
        editable: state.editing?.allowed,
        leftNotes: left?.notes,
        rightNotes: right?.notes,
        leftMaskPixels: Array.from(left?.mask || []).reduce((sum, pixel) => sum + pixel, 0),
      };
    });
    const reloadDebug = await page.evaluate(studyId => ({
      navigationType: performance.getEntriesByType('navigation')?.[0]?.type,
      tabId: sessionStorage.getItem('ova.tab_id'),
      pageInstanceId: sessionStorage.getItem('ova.page_instance_id'),
      hasServerLeaseToken: Boolean(sessionStorage.getItem('ova.server-lease.' + studyId)),
      localLease: JSON.parse(localStorage.getItem('ova.lease.live.' + studyId) || 'null'),
      leaseNotice: document.querySelector('#leaseLostNotice')?.innerText,
    }), id);
    assert.deepEqual(recoveredDraftAfterReload, {
      userId: draftBeforeNavigation.userId,
      studyId: id,
      dirty: true,
      reviewRevision: 0,
      conflict: false,
      editable: true,
      leftNotes: draftBeforeNavigation.leftNotes,
      rightNotes: draftBeforeNavigation.rightNotes,
      leftMaskPixels: draftBeforeNavigation.leftMaskPixels,
    }, 'confirming reload must recover the same user-owned unsaved mask and notes without advancing revision; reload=' +
      JSON.stringify({ preReloadLeaseState, reloadDebug, previousTabId: draftBeforeNavigation.tabId,
        previousPageInstanceId: draftBeforeNavigation.pageInstanceId,
        previousLeaseTokenPresent: draftBeforeNavigation.hasServerLeaseToken, leaseTrace }));
    console.log('PASS: confirmed browser reload protects first, then restores the user-owned failed-save draft with a fresh edit lease');

    const logoutDraftKeys = await page.evaluate(async () => {
      const { state, draftKey, maskDraftKey } = await import('/static/app/state.js');
      const left = state.case.images.find(image => image.laterality === 'L');
      return {
        userId: state.user.id,
        studyId: state.case.study_id,
        leftImageId: left.image_id,
        liveKey: draftKey(state.case.study_id),
        maskKey: maskDraftKey(state.case.study_id, left.image_id),
        liveValue: localStorage.getItem(draftKey(state.case.study_id)),
        maskValue: localStorage.getItem(maskDraftKey(state.case.study_id, left.image_id)),
      };
    });
    assert.ok(logoutDraftKeys.liveValue);
    assert.ok(logoutDraftKeys.maskValue);
    const revokedAuthToken = authToken;
    let logoutResponseError = null;
    const logoutResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/auth/logout',
      { timeout: 10000 },
    ).catch(error => {
      logoutResponseError = error.message;
      return null;
    });
    await page.locator('details.viewer-more-actions > summary').click();
    await page.locator('details.viewer-more-actions [data-action=logout]').waitFor({ state: 'visible', timeout: 5000 });
    await page.locator('details.viewer-more-actions [data-action=logout]').click();
    const logoutAck = await logoutResponse;
    assert.ok(logoutAck, `The logout dialog did not call the API: ${logoutResponseError}`);
    assert.equal(logoutAck.status(), 200, await logoutAck.text());
    await page.locator('[name=username]').waitFor({ timeout: 10000 });
    const draftsAfterLogout = await page.evaluate(({ liveKey, maskKey }) => ({
      liveValue: localStorage.getItem(liveKey),
      maskValue: localStorage.getItem(maskKey),
      tokenCleared: sessionStorage.getItem('ova.token') === null,
    }), { liveKey: logoutDraftKeys.liveKey, maskKey: logoutDraftKeys.maskKey });
    assert.deepEqual(draftsAfterLogout, {
      liveValue: logoutDraftKeys.liveValue,
      maskValue: logoutDraftKeys.maskValue,
      tokenCleared: true,
    }, 'logout must clear authentication while retaining only the owner-scoped recoverable local draft');
    console.log('PASS: logout API revokes the client session while preserving the same user-scoped live and mask drafts');
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    authToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    assert.ok(authToken, 'Successful same-user login must install a fresh browser token.');
    const currentUserAfterRelogin = await page.request.get(`${server.base}/api/auth/current-user`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    assert.equal(currentUserAfterRelogin.status(), 200, await currentUserAfterRelogin.text());
    const revokedSessionCheck = await page.request.get(`${server.base}/api/auth/current-user`, {
      headers: { Authorization: `Bearer ${revokedAuthToken}` },
    });
    assert.equal(revokedSessionCheck.status(), 401, await revokedSessionCheck.text());
    await page.evaluate(studyId => { location.hash = '#viewer/' + studyId; }, id);
    try {
      await page.waitForFunction(({ studyId, notes }) =>
        location.hash === '#viewer/' + studyId &&
        document.querySelector('#notes')?.value === notes &&
        document.querySelector('#leaseLostNotice')?.hidden === true,
      { studyId: id, notes: draftBeforeNavigation.leftNotes }, { timeout: 15000 });
    } catch (error) {
      const recoveryDebug = await page.evaluate(async studyId => {
        const { state, draftKey } = await import('/static/app/state.js');
        const left = state.case?.images?.find(image => image.laterality === 'L');
        return {
          hash: location.hash,
          route: state.route,
          userId: state.user?.id,
          tokenPresent: Boolean(sessionStorage.getItem('ova.token')),
          appText: document.querySelector('#app')?.innerText?.slice(0, 300),
          pageText: document.querySelector('#page')?.innerText?.slice(0, 700),
          stateCaseId: state.case?.study_id,
          stateReviewRevision: state.case?.review_revision,
          noteField: document.querySelector('#notes')?.value,
          stateNotes: left?.notes,
          draftStored: Boolean(localStorage.getItem(draftKey(studyId))),
          dirty: state.dirty,
          draftConflict: state.draftConflict && { caseId: state.draftConflict.caseId },
          leaseNotice: document.querySelector('#leaseLostNotice')?.innerText,
          editing: state.editing && { allowed: state.editing.allowed, caseId: state.editing.caseId },
        };
      }, id);
      throw new Error(`Same-user draft recovery after logout timed out: ${JSON.stringify(recoveryDebug)}; ${error.message}`);
    }
    const recoveredDraftAfterLogout = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      const right = state.case?.images?.find(image => image.laterality === 'R');
      return {
        userId: state.user?.id,
        studyId: state.case?.study_id,
        dirty: state.dirty,
        reviewRevision: state.case?.review_revision,
        conflict: Boolean(state.draftConflict),
        editable: state.editing?.allowed,
        leftNotes: left?.notes,
        rightNotes: right?.notes,
        leftMaskPixels: Array.from(left?.mask || []).reduce((sum, pixel) => sum + pixel, 0),
      };
    });
    assert.deepEqual(recoveredDraftAfterLogout, {
      userId: logoutDraftKeys.userId,
      studyId: id,
      dirty: true,
      reviewRevision: 0,
      conflict: false,
      editable: true,
      leftNotes: draftBeforeNavigation.leftNotes,
      rightNotes: draftBeforeNavigation.rightNotes,
      leftMaskPixels: draftBeforeNavigation.leftMaskPixels,
    }, 'the same account must recover its unsaved mask and notes after logout/login and regain a lease before editing');
    console.log('PASS: logout revokes the client session, preserves owner-scoped drafts, and same-user login restores the case with a fresh lease');

    // A reopened case must be reviewed again on both sides before resubmission;
    // persisted drafts do not carry forward the previous viewer's seen state.
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('trái'));
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('[data-action=side-L]').click();
    await page.waitForFunction(() =>
      document.querySelector('#sideLabel')?.textContent.includes('trái') &&
      document.querySelector('[data-action="save-review"]')?.disabled === false,
    null, { timeout: 15000 });

    let reviewBatchRequests = 0;
    const countReviewBatchRequests = request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/reviews/batch')
        reviewBatchRequests++;
    };
    page.on('request', countReviewBatchRequests);
    const reviewRequestsBeforeOffline = reviewBatchRequests;
    await page.context().setOffline(true);
    await waitForAppState(page, snapshot => snapshot.dom.navigator_online === false &&
      snapshot.online === false, { message: 'offline state propagated to app' });
    await page.locator('[data-action=save-review]').click();
    await page.locator('#toasts .toast').filter({ hasText: 'Chưa đồng bộ. Bản rà soát sẽ gửi lại khi có mạng trong phiên này.' })
      .waitFor({ state: 'visible', timeout: 5000 });
    const offlineSaveState = await page.evaluate(async studyId => {
      const { state, draftKey } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      const maskKey = `draft_mask_v2:${JSON.stringify([String(state.user?.id), String(studyId), String(left?.image_id)])}`;
      return {
        online: state.online,
        pendingReview: state.pendingReview,
        dirty: state.dirty,
        reviewRevision: state.case?.review_revision,
        note: left?.notes,
        liveDraft: localStorage.getItem(draftKey(studyId)),
        maskDraft: localStorage.getItem(maskKey),
      };
    }, id);
    assert.deepEqual(offlineSaveState, {
      online: false,
      pendingReview: { caseId: id, userId: logoutDraftKeys.userId },
      dirty: true,
      reviewRevision: 0,
      note: draftBeforeNavigation.leftNotes,
      liveDraft: logoutDraftKeys.liveValue,
      maskDraft: logoutDraftKeys.maskValue,
    }, 'an offline review attempt must keep both owner-scoped drafts, leave the server revision untouched, and queue only this user/case');
    assert.equal(reviewBatchRequests, reviewRequestsBeforeOffline,
      'An offline save must not issue a review write before the browser reports connectivity.');

    await page.route('**/api/reviews/batch', route => route.abort('failed'));
    const onlineRetryRequest = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname === '/api/reviews/batch',
      { timeout: 10000 },
    ).catch(error => ({ waitError: error.message }));
    await page.context().setOffline(false);
    const automaticRetry = await onlineRetryRequest;
    assert.equal(automaticRetry.waitError, undefined, automaticRetry.waitError);
    const automaticRetryPayload = JSON.parse(automaticRetry.postData());
    assert.equal(automaticRetryPayload.study_id, id);
    assert.equal(automaticRetryPayload.expected_revision, 0);
    assert.equal(automaticRetryPayload.reviews.length, 2);
    await waitForAppState(page, snapshot => !snapshot.busy, { message: 'failed reconnect retry settled' });
    await page.unroute('**/api/reviews/batch');
    const offlineRecoveryState = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return { dirty: state.dirty, reviewRevision: state.case?.review_revision,
        pendingReview: state.pendingReview, online: state.online };
    });
    assert.deepEqual(offlineRecoveryState, {
      dirty: true,
      reviewRevision: 0,
      pendingReview: { caseId: id, userId: logoutDraftKeys.userId },
      online: true,
    }, 'a failed automatic reconnect attempt must leave the draft pending for a visible/manual retry');
    const serverReviewAfterOfflineFailure = await page.request.get(`${server.base}/api/cases/${encodeURIComponent(id)}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    assert.equal(serverReviewAfterOfflineFailure.status(), 200, await serverReviewAfterOfflineFailure.text());
    assert.equal((await serverReviewAfterOfflineFailure.json()).review_revision, 0,
      'An aborted reconnect attempt must not advance the persisted review revision.');
    let offlineReloadDialogType = null;
    page.once('dialog', async dialog => {
      offlineReloadDialogType = dialog.type();
      await dialog.accept();
    });
    await page.reload();
    assert.equal(offlineReloadDialogType, 'beforeunload',
      'Reloading a dirty case after an offline save attempt must warn before leaving the editor.');
    await page.waitForFunction(({ studyId, notes }) =>
      location.hash === '#viewer/' + studyId &&
      document.querySelector('#notes')?.value === notes &&
      document.querySelector('#leaseLostNotice')?.hidden === true,
    { studyId: id, notes: draftBeforeNavigation.leftNotes }, { timeout: 15000 });
    const restoredAfterOfflineReload = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const left = state.case?.images?.find(image => image.laterality === 'L');
      const right = state.case?.images?.find(image => image.laterality === 'R');
      return {
        userId: state.user?.id,
        studyId: state.case?.study_id,
        dirty: state.dirty,
        reviewRevision: state.case?.review_revision,
        conflict: Boolean(state.draftConflict),
        editable: state.editing?.allowed,
        leftNotes: left?.notes,
        rightNotes: right?.notes,
        leftMaskPixels: Array.from(left?.mask || []).reduce((sum, pixel) => sum + pixel, 0),
      };
    });
    assert.deepEqual(restoredAfterOfflineReload, {
      userId: logoutDraftKeys.userId,
      studyId: id,
      dirty: true,
      reviewRevision: 0,
      conflict: false,
      editable: true,
      leftNotes: draftBeforeNavigation.leftNotes,
      rightNotes: draftBeforeNavigation.rightNotes,
      leftMaskPixels: draftBeforeNavigation.leftMaskPixels,
    }, 'the same user must recover the offline review draft from local storage after a confirmed reload and receive a fresh lease');
    assert.equal(await page.locator('#localReviewDraftNotice').isVisible(), true,
      'A restored but uncommitted review must remain visibly marked after the transient recovery toast disappears.');
    assert.match(await page.locator('#localReviewDraftNotice').innerText(), /chưa được lưu lên máy chủ/i);
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('trái'));
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.locator('[data-action=side-L]').click();
    await page.waitForFunction(() =>
      document.querySelector('#sideLabel')?.textContent.includes('trái') &&
      document.querySelector('[data-action="save-review"]')?.disabled === false,
    null, { timeout: 15000 });
    page.off('request', countReviewBatchRequests);
    console.log('PASS: offline review keeps user/case drafts, failed automatic retry preserves dirty state and server revision, confirmed reload restores mask/notes with a fresh lease, then both sides can be reviewed again');

    const saveResponse = page.waitForResponse(
      response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/reviews/batch',
      { timeout: 10000 },
    ).catch(error => ({ waitError: error.message }));
    await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      window.__reviewDraftAckSnapshots = [];
      window.addEventListener('ova:review-draft-state-changed', () => {
        const notice = document.querySelector('#localReviewDraftNotice');
        window.__reviewDraftAckSnapshots.push({
          busy: state.busy,
          dirty: state.dirty,
          status: state.case?.status,
          reviewRevision: state.case?.review_revision,
          noticeHidden: notice?.hidden,
        });
      });
    });
    let releaseReviewBatch;
    let notifyReviewBatchBlocked;
    const reviewBatchBlocked = new Promise(resolve => { notifyReviewBatchBlocked = resolve; });
    const reviewBatchRelease = new Promise(resolve => { releaseReviewBatch = resolve; });
    await page.route('**/api/reviews/batch', async route => {
      if (route.request().method() === 'POST') {
        notifyReviewBatchBlocked();
        await reviewBatchRelease;
      }
      await route.continue();
    });
    await page.locator('[data-action=save-review]').click();
    const reviewRequestStarted = await Promise.race([
      reviewBatchBlocked.then(() => true),
      new Promise(resolve => setTimeout(() => resolve(false), 5000)),
    ]);
    if (!reviewRequestStarted) {
      const retryContext = await page.evaluate(async () => {
        const [{ state }, { reviewWarnings, hasUnresolvedReviewWarning }] = await Promise.all([
          import('/static/app/state.js'),
          import('/static/app/review-content.js'),
        ]);
        return {
          busy: state.busy,
          dirty: state.dirty,
          status: state.case?.status,
          editing: state.editing,
          capabilityManualReview: state.capabilities?.manual_review,
          buttonDisabled: document.querySelector('[data-action="save-review"]')?.disabled,
          images: state.case?.images?.map(image => ({
            side: image.laterality,
            seen: image.seen,
            predictionId: image.prediction?.prediction_id,
            warning: reviewWarnings(image),
            unresolved: hasUnresolvedReviewWarning(image),
            consistencyAcknowledgement: image.consistencyAcknowledgement,
            notes: image.notes,
            orads: image.orads,
            morphology: image.morphology,
            morphologyDesc: image.morphologyDesc,
          })),
          toast: document.querySelector('[role="alert"]')?.textContent,
        };
      });
      throw new Error(`Review retry did not reach API after failed-save recovery: ${JSON.stringify({ retryContext, pageErrors: errors })}`);
    }
    assert.equal(await page.locator('[data-tool="brush"]').isDisabled(), true,
      'The Canvas toolbar must stay disabled while the review transaction is saving.');
    assert.equal(await page.locator('[data-action=no-lesion]').isDisabled(), true,
      'Mask reset actions must stay disabled while the review transaction is saving.');
    assert.equal(await page.locator('[data-chip]').first().isDisabled(), true,
      'Clinical descriptor shortcuts must stay disabled while the review transaction is saving.');
    let dropReviewTelemetryOnce = true;
    const telemetryFailure = page.waitForEvent('requestfailed', {
      predicate: request => request.method() === 'POST' &&
        /^\/api\/hitl\/sessions\/[^/]+\/events$/.test(new URL(request.url()).pathname),
      timeout: 10000,
    }).catch(error => ({ waitError: error.message }));
    await page.route('**/api/hitl/sessions/*/events', route => {
      if (dropReviewTelemetryOnce && route.request().method() === 'POST') {
        dropReviewTelemetryOnce = false;
        return route.abort('failed');
      }
      return route.continue();
    });
    releaseReviewBatch();
    const response = await saveResponse;
    await page.unroute('**/api/reviews/batch');
    assert.equal(response.waitError, undefined, response.waitError);
    assert.equal(response.status(), 200, await response.text());
    const saved = await response.json();
    assert.equal(saved.status, 'SUCCESS');
    assert.equal(saved.review_revision, 1);
    await page.waitForFunction(() => window.__reviewDraftAckSnapshots?.length === 1);
    const stateAtReviewAck = await page.evaluate(() => window.__reviewDraftAckSnapshots[0]);
    assert.deepEqual(stateAtReviewAck, {
      busy: true,
      dirty: false,
      status: 'REVIEWED',
      reviewRevision: 1,
      noticeHidden: true,
    }, 'The persistent notice clears at server ACK before the primary save operation unlocks.');
    await page.waitForFunction(() => document.querySelector('[data-action="save-review"]')?.disabled === false);
    const savedReviewState = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return { dirty: state.dirty, reviewRevision: state.case?.review_revision };
    });
    assert.deepEqual(savedReviewState, { dirty: false, reviewRevision: 1 },
      'A server-confirmed clean review must remain clean after the primary save operation returns.');
    const failedTelemetryRequest = await telemetryFailure;
    assert.equal(failedTelemetryRequest.waitError, undefined, failedTelemetryRequest.waitError);
    await page.locator('#toasts .toast').filter({ hasText: 'Nhật ký HITL chưa đồng bộ' })
      .waitFor({ state: 'visible', timeout: 5000 });
    const pendingTelemetryState = await page.evaluate(async () => {
      const [{ state }, { tracker }] = await Promise.all([
        import('/static/app/state.js'),
        import('/static/app/hitl-tracker.js'),
      ]);
      return {
        pendingStudyId: state.pendingReviewTelemetryAck?.studyId,
        pendingSessionId: state.pendingReviewTelemetryAck?.sessionId,
        queuedEvents: tracker.getQueueLength(),
        persistedOutbox: sessionStorage.getItem('ova.hitl.outbox.v1'),
      };
    });
    assert.equal(pendingTelemetryState.pendingStudyId, id,
      'A telemetry transport failure must retain a retry marker for the committed study.');
    assert.ok(pendingTelemetryState.pendingSessionId);
    assert.ok(pendingTelemetryState.queuedEvents > 0,
      'Unacknowledged HITL events must stay queued after telemetry transport failure.');
    assert.ok(pendingTelemetryState.persistedOutbox,
      'The unacknowledged event queue must survive a browser reload.');
    const telemetryReplay = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      /^\/api\/hitl\/sessions\/[^/]+\/events$/.test(new URL(response.url()).pathname),
    { timeout: 15000 });
    await page.reload();
    await waitForAppState(page, snapshot => snapshot.dom.hash === '#viewer/' + id &&
      snapshot.editing?.caseId === id && snapshot.editing.allowed && snapshot.editing.leaseToken,
    { timeout: 15000, message: 'same-case lease restored after reload' });
    const replayedTelemetryResponse = await telemetryReplay;
    assert.ok(replayedTelemetryResponse.ok(), await replayedTelemetryResponse.text());
    await page.locator('#toasts .toast').filter({ hasText: 'khôi phục và đồng bộ nhật ký HITL' })
      .waitFor({ state: 'visible', timeout: 5000 });
    const telemetryOutboxAfterReplay = await page.evaluate(() => {
      const serialized = sessionStorage.getItem('ova.hitl.outbox.v1');
      return serialized ? JSON.parse(serialized) : [];
    });
    assert.equal(telemetryOutboxAfterReplay.some(record =>
      record.sessionId === pendingTelemetryState.pendingSessionId), false,
    'A successful same-case replay must remove the acknowledged session; a new session may already have queued fresh events.');
    const pendingTelemetryAckAfterReplay = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.pendingReviewTelemetryAck;
    });
    assert.equal(pendingTelemetryAckAfterReplay, null,
      'A successful same-case replay must clear the pending telemetry retry marker.');
    await page.unroute('**/api/hitl/sessions/*/events');
    const draftNoticeHiddenAfterSave = await page.locator('#localReviewDraftNotice').isHidden();
    if (!draftNoticeHiddenAfterSave) {
      const draftNoticeDebug = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        const notice = document.querySelector('#localReviewDraftNotice');
        return {
          dirty: state.dirty,
          busy: state.busy,
          caseStatus: state.case?.status,
          reviewRevision: state.case?.review_revision,
          hiddenAttribute: notice?.hidden,
          computedDisplay: notice ? getComputedStyle(notice).display : null,
          noticeText: notice?.innerText,
          images: state.case?.images?.map(image => ({
            side: image.laterality,
            manualCalipers: image.manualCalipers,
            notes: image.notes,
            morphology: image.morphology,
            morphologyDesc: image.morphologyDesc,
            orads: image.orads,
          })),
        };
      });
      assert.fail(`Persistent unsaved-draft warning did not clear after server ACK: ${JSON.stringify(draftNoticeDebug)}`);
    }
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const detail = await page.request.get(server.base + '/api/cases/' + encodeURIComponent(id), { headers: { Authorization: 'Bearer ' + token } });
    assert.equal(detail.status(), 200);
    const persisted = await detail.json();
    assert.equal(persisted.review_revision, 1);
    for (const image of persisted.images) {
      assert.ok(image.review.review_id);
      assert.equal(image.review.doctor_id, 'doctor');
      assert.equal(image.review.clinical_notes, `Rà soát kỹ thuật ảnh tổng hợp bên ${image.laterality === 'L' ? 'trái' : 'phải'}.`);
      assert.equal(image.review.max_diameter_mm, null, 'no invented physical calibration');
      if (image.laterality === 'L') {
        assert.equal(image.review.doctor_action, 'MODIFIED');
        assert.notDeepEqual(image.review.verified_mask_rle, image.prediction.rle_mask,
          'Canvas edit must be persisted in the reviewed synthetic mask.');
      } else {
        assert.equal(image.review.doctor_action, 'ACCEPTED_RAW');
        assert.deepEqual(image.review.verified_mask_rle, image.prediction.rle_mask);
      }
    }
    const leftReview = persisted.images.find(image => image.laterality === 'L').review;
    assert.ok(leftReview.hitl_feedback.manual_measurements.D1.diameter_px > 298);
    assert.equal(leftReview.hitl_feedback.manual_measurements.D1.calibrated, false);
    assert.equal(leftReview.hitl_feedback.manual_measurements.D1.calibration_source, 'NONE');
    // Leave and reopen: validate server persistence, not just the in-memory save result.
    await page.evaluate(() => { location.hash = '#cases'; });
    await page.locator('#caseResults').waitFor({ timeout: 10000 }).catch(async error => {
      const stateAtFailure = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return { hash: location.hash, route: state.route, busy: state.busy,
          pageText: document.querySelector('#page')?.innerText?.slice(0, 500) };
      });
      throw new Error(`Case list did not render after leaving viewer: ${JSON.stringify({ ...stateAtFailure, pageErrors: errors })}; ${error.message}`);
    });
    await page.evaluate(studyId => { location.hash = '#viewer/' + studyId; }, id);
    await page.waitForFunction(() => document.querySelector('#notes')?.value === 'Rà soát kỹ thuật ảnh tổng hợp bên trái.');
    await page.locator('#researchTab').click();
    const leftImage = persisted.images.find(image => image.laterality === 'L');
    const leftImageId = leftImage.image_id;
    assert.equal(leftImage.width, 640);
    assert.equal(leftImage.height, 480,
      'The live roundtrip must retain the non-square decoded source dimensions in PostgreSQL/SQLite.');
    const leftReviewId = persisted.images.find(image => image.laterality === 'L').review.review_id;
    let dropCandidateOnce = true;
    const candidateRoute = `**/api/cases/${id}/images/${leftImageId}/reviews/${leftReviewId}/region-candidates`;
    await page.route(candidateRoute, route => {
      if (dropCandidateOnce) {
        dropCandidateOnce = false;
        return route.abort('failed');
      }
      return route.continue();
    });
    await page.locator('[data-region-load]').click();
    await page.locator('#regionReviewMount [role="alert"]').waitFor();
    assert.equal(await page.locator('[data-region-load]').isVisible(), true,
      'A failed candidate request must leave a direct retry action.');
    const retriedCandidateResponse = page.waitForResponse(response =>
      response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/region-candidates'));
    await page.locator('[data-region-load]').click();
    const actualCandidateResponse = await retriedCandidateResponse;
    assert.equal(actualCandidateResponse.status(), 200, await actualCandidateResponse.text());
    await page.unroute(candidateRoute);
    const candidates = await actualCandidateResponse.json();
    await page.waitForFunction(expectedCount => {
      const panel = document.querySelector('.region-review');
      return panel && document.querySelectorAll('[data-region-component]').length === expectedCount &&
        (expectedCount > 0 || panel.textContent.includes('0 vùng'));
    }, candidates.components.length);
    assert.equal(await page.locator('[data-region-component]').count(), candidates.components.length,
      'The UI must display exactly the candidate components returned by the real backend.');
    if (candidates.components.length) {
      const firstRegion = page.locator('[data-region-component]').first();
      await firstRegion.hover();
      await page.waitForFunction(() => document.querySelector('#viewport')?.dataset.highlightedRegion === '1');
      await page.mouse.move(10, 10);
      await page.waitForFunction(() => document.querySelector('#viewport')?.dataset.highlightedRegion === '');
    }
    await page.locator('[data-region-accepted]').check();
    const regionWrite = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/region-assignments'));
    await page.locator('[data-region-submit]').click();
    const regionWriteResponse = await regionWrite;
    assert.equal(regionWriteResponse.status(), 200, await regionWriteResponse.text());
    const confirmedRegions = await regionWriteResponse.json();
    assert.equal(confirmedRegions.review_id, candidates.review_id);
    assert.equal(confirmedRegions.mask_sha256, candidates.mask_sha256);
    assert.equal(confirmedRegions.assignments.length, candidates.components.length);
    assert.equal(new Set(confirmedRegions.assignments.map(row => row.region_id)).size, candidates.components.length);
    const regionStateResponse = await page.request.get(
      `${server.base}/api/cases/${encodeURIComponent(id)}/images/${encodeURIComponent(persisted.images.find(image => image.laterality === 'L').image_id)}/region-assignments`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    assert.equal(regionStateResponse.status(), 200, await regionStateResponse.text());
    const savedRegionState = await regionStateResponse.json();
    assert.equal(savedRegionState.stale, false);
    assert.equal(savedRegionState.assignment.review_revision, 2);

    const targetComponent = [...candidates.components].sort((a, b) => b.pixel_count - a.pixel_count)[0];
    const targetAssignment = confirmedRegions.assignments.find(row => row.component_index === targetComponent.component_index);
    assert.ok(targetAssignment, 'The largest reviewed component must have an explicit persisted region assignment.');
    const selectRegion = page.locator(`[data-region-select="${targetAssignment.region_id}"]`);
    await selectRegion.waitFor();
    await selectRegion.click();
    await page.waitForFunction(() => document.querySelector('#cdssRegionStatus')?.textContent.includes('D1 chưa có'));

    const calibrationWrite = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/images/${leftImageId}/calibrate`);
    await page.locator('[data-action=calibrate]').click();
    await page.locator('#modal input[name=pixels]').fill('100');
    await page.locator('#modal input[name=mm]').fill('10');
    await page.locator('#modal button[type=submit]').click();
    const calibrationResponse = await calibrationWrite;
    assert.equal(calibrationResponse.status(), 200, await calibrationResponse.text());
    await page.waitForFunction(() => document.querySelector('#toasts .toast:not(.danger)')?.textContent ||
      document.querySelector('#regionCaliperStatus')?.textContent);
    await page.locator(`[data-region-select="${targetAssignment.region_id}"]`).click();
    await page.waitForFunction(() => document.querySelector('#cdssRegionStatus')?.textContent.includes('D1 chưa có'));

    const [x, y, width, height] = targetComponent.bounding_box_xywh;
    const modelY = y + Math.floor(height / 2);
    const modelX1 = x + Math.max(1, Math.floor(width * 0.2));
    const modelX2 = x + Math.min(width - 2, Math.floor(width * 0.8));
    assert.ok(modelX2 - modelX1 >= 2, 'Selected synthetic region must have a measurable major axis.');
    const canvasBox = await page.locator('#viewport').boundingBox();
    const view = {
      scale: Math.min(canvasBox.width / 512, canvasBox.height / 512) * 0.94,
      x: 0,
      y: 0,
    };
    view.x = (canvasBox.width - 512 * view.scale) / 2;
    view.y = (canvasBox.height - 512 * view.scale) / 2;
    const zoomAnchor = { x: canvasBox.x + canvasBox.width * 0.62, y: canvasBox.y + canvasBox.height * 0.43 };
    const anchorModel = {
      x: (zoomAnchor.x - canvasBox.x - view.x) / view.scale,
      y: (zoomAnchor.y - canvasBox.y - view.y) / view.scale,
    };
    await page.mouse.move(zoomAnchor.x, zoomAnchor.y);
    await page.mouse.wheel(0, -120);
    view.scale = Math.min(12, view.scale * 1.12);
    view.x = zoomAnchor.x - canvasBox.x - anchorModel.x * view.scale;
    view.y = zoomAnchor.y - canvasBox.y - anchorModel.y * view.scale;
    await page.locator('[data-tool="pan"]').click();
    const panStart = { x: canvasBox.x + canvasBox.width * 0.5, y: canvasBox.y + canvasBox.height * 0.5 };
    const panDelta = { x: 29, y: 17 };
    await page.mouse.move(panStart.x, panStart.y);
    await page.mouse.down();
    await page.mouse.move(panStart.x + panDelta.x, panStart.y + panDelta.y, { steps: 4 });
    await page.mouse.up();
    view.x += panDelta.x;
    view.y += panDelta.y;
    const clickTransformedSourcePoint = async (sourceX, sourceY) => {
      const rect = await page.locator('#viewport').boundingBox();
      await page.mouse.click(
        rect.x + view.x + sourceX * view.scale,
        rect.y + view.y + sourceY * view.scale,
      );
    };
    assert.equal(await page.locator('#regionCaliperRetry').isVisible(), false,
      'Retry action must stay hidden until a caliper request fails.');
    await page.locator('[data-tool=caliper-d1]').click();
    const caliperUrl = `**/api/cases/${id}/images/${leftImageId}/regions/${targetAssignment.region_id}/calipers`;
    let dropCaliperOnce = true;
    await page.route(caliperUrl, route => {
      if (dropCaliperOnce && route.request().method() === 'POST') {
        dropCaliperOnce = false;
        return route.abort('failed');
      }
      return route.continue();
    });
    const firstCaliperAttempt = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    await clickTransformedSourcePoint(modelX1, modelY);
    await clickTransformedSourcePoint(modelX2, modelY);
    const failedCaliperRequest = await firstCaliperAttempt;
    const failedCaliperPayload = JSON.parse(failedCaliperRequest.postData());
    await page.locator('#regionCaliperRetry').waitFor({ state: 'visible' });
    assert.match(await page.locator('#regionCaliperStatus').innerText(), /nút thử lại để gửi cùng request ID/i);
    const retryCaliperAttempt = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    const regionCaliperWrite = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    await page.locator('#regionCaliperRetry').click();
    const retriedCaliperRequest = await retryCaliperAttempt;
    assert.equal(JSON.parse(retriedCaliperRequest.postData()).request_id, failedCaliperPayload.request_id,
      'Caliper retry must reuse its idempotency key after a lost response.');
    const caliperResponse = await regionCaliperWrite;
    await page.unroute(caliperUrl);
    assert.equal(caliperResponse.status(), 200, await caliperResponse.text());
    let savedRegionCaliper = await caliperResponse.json();
    assert.equal(savedRegionCaliper.assignment_request_id, confirmedRegions.assignment_request_id);
    assert.equal(savedRegionCaliper.region_id, targetAssignment.region_id);
    assert.ok(savedRegionCaliper.diameter_mm > 0);
    const expectedSourcePoint = (modelX, modelY) => [modelX * 1.25, (modelY - 64) * 1.25];
    const expectedD1Start = expectedSourcePoint(modelX1, modelY);
    const expectedD1End = expectedSourcePoint(modelX2, modelY);
    const expectedD1Length = expectedD1End[0] - expectedD1Start[0];
    assert.ok(Math.abs(savedRegionCaliper.diameter_px - expectedD1Length) <= 1,
      'Zoom/pan and 640×480 letterboxing must preserve the decoded-source caliper length.');
    assert.ok(Math.abs(savedRegionCaliper.points[0][0] - expectedD1Start[0]) <= 1 &&
      Math.abs(savedRegionCaliper.points[1][0] - expectedD1End[0]) <= 1 &&
      Math.abs(savedRegionCaliper.points[0][1] - expectedD1Start[1]) <= 1 &&
      Math.abs(savedRegionCaliper.points[1][1] - expectedD1End[1]) <= 1,
      'Caliper endpoints must persist in decoded-source coordinates after zoom/pan and letterboxing.');
    assert.equal(savedRegionCaliper.calibration_source, 'MANUAL');
    await page.waitForFunction(() => document.querySelector('#regionCaliperStatus')?.textContent.includes('mm'));

    // Persist a newer D1 while losing the browser response, then supersede it from a second real API request.
    // Retrying the first request must release the stale pending action and reload the latest D1.
    let persistThenDropCaliperResponse = true;
    await page.route(caliperUrl, async route => {
      if (persistThenDropCaliperResponse && route.request().method() === 'POST') {
        persistThenDropCaliperResponse = false;
        const persistedResponse = await route.fetch();
        assert.equal(persistedResponse.status(), 200, await persistedResponse.text());
        await route.abort('failed');
        return;
      }
      await route.continue();
    });
    const lostButCommittedRequest = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    await clickTransformedSourcePoint(modelX1, modelY);
    await clickTransformedSourcePoint(modelX2, modelY);
    const lostCommittedRequest = await lostButCommittedRequest;
    const lostCommittedPayload = JSON.parse(lostCommittedRequest.postData());
    await page.locator('#regionCaliperRetry').waitFor({ state: 'visible' });

    const supersedingPayload = {
      ...lostCommittedPayload,
      request_id: crypto.randomUUID(),
      expected_revision: lostCommittedPayload.expected_revision + 1,
    };
    const supersedingResponse = await page.request.post(
      `${server.base}/api/cases/${id}/images/${leftImageId}/regions/${targetAssignment.region_id}/calipers`,
      { headers: { Authorization: `Bearer ${authToken}` }, data: supersedingPayload },
    );
    assert.equal(supersedingResponse.status(), 200, await supersedingResponse.text());
    const supersedingCaliper = await supersedingResponse.json();
    assert.equal(supersedingCaliper.measurement_revision, lostCommittedPayload.expected_revision + 2);
    assert.equal(supersedingCaliper.current, true);

    const staleRetryResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    const latestCalipersReload = page.waitForResponse(response =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    const staleRetryRequest = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    await page.locator('#regionCaliperRetry').click();
    const retriedStaleRequest = await staleRetryRequest;
    assert.equal(JSON.parse(retriedStaleRequest.postData()).request_id, lostCommittedPayload.request_id,
      'Retry after a lost response must keep the idempotency key for the committed event.');
    const staleResponse = await staleRetryResponse;
    assert.equal(staleResponse.status(), 200, await staleResponse.text());
    const staleCaliperResponse = await staleResponse.json();
    assert.equal(staleCaliperResponse.current, false,
      'An idempotent replay must disclose that its measurement was superseded.');
    const reloadedCalipersResponse = await latestCalipersReload;
    assert.equal(reloadedCalipersResponse.status(), 200, await reloadedCalipersResponse.text());
    const reloadedCalipers = await reloadedCalipersResponse.json();
    assert.equal(reloadedCalipers.measurements.D1.request_id, supersedingCaliper.request_id,
      'The viewer must reload the newer D1 after discarding the stale retry.');
    await page.waitForFunction(() => document.querySelector('#regionCaliperRetry')?.hidden === true);
    await page.waitForFunction(() =>
      document.querySelector('#regionCaliperStatus')?.textContent.includes('D1:') &&
      !document.querySelector('#regionCaliperStatus')?.textContent.includes('thử lại để gửi cùng request ID'));
    await page.unroute(caliperUrl);

    const followupD1Write = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`));
    await clickTransformedSourcePoint(modelX1, modelY);
    await clickTransformedSourcePoint(modelX2, modelY);
    const followupD1Response = await followupD1Write;
    assert.equal(followupD1Response.status(), 200, await followupD1Response.text());
    savedRegionCaliper = await followupD1Response.json();
    assert.equal(savedRegionCaliper.current, true);
    assert.equal(savedRegionCaliper.measurement_revision, supersedingCaliper.measurement_revision + 1,
      'The clinician must be able to save a fresh D1 after the stale retry is resolved.');

    const modelXForD2 = x + Math.floor(width / 2);
    const modelY1 = y + Math.max(1, Math.floor(height * 0.2));
    const modelY2 = y + Math.min(height - 2, Math.floor(height * 0.8));
    assert.ok(modelY2 - modelY1 >= 2,
      'Selected synthetic region must have a measurable orthogonal axis.');
    await page.locator('[data-tool="caliper-d2"]').click();
    const d2Write = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/regions/' + targetAssignment.region_id + '/calipers'));
    await clickTransformedSourcePoint(modelXForD2, modelY1);
    await clickTransformedSourcePoint(modelXForD2, modelY2);
    const d2Response = await d2Write;
    assert.equal(d2Response.status(), 200, await d2Response.text());
    const savedRegionCaliperD2 = await d2Response.json();
    assert.equal(savedRegionCaliperD2.label, 'D2');
    assert.equal(savedRegionCaliperD2.assignment_request_id, confirmedRegions.assignment_request_id);
    assert.equal(savedRegionCaliperD2.region_id, targetAssignment.region_id);
    const expectedD2Start = expectedSourcePoint(modelXForD2, modelY1);
    const expectedD2End = expectedSourcePoint(modelXForD2, modelY2);
    const expectedD2Length = expectedD2End[1] - expectedD2Start[1];
    assert.ok(Math.abs(savedRegionCaliperD2.diameter_px - expectedD2Length) <= 1,
      'Zoom/pan and 640×480 letterboxing must preserve the decoded-source D2 length.');
    assert.ok(Math.abs(savedRegionCaliperD2.points[0][0] - expectedD2Start[0]) <= 1 &&
      Math.abs(savedRegionCaliperD2.points[1][0] - expectedD2End[0]) <= 1 &&
      Math.abs(savedRegionCaliperD2.points[0][1] - expectedD2Start[1]) <= 1 &&
      Math.abs(savedRegionCaliperD2.points[1][1] - expectedD2End[1]) <= 1,
      'D2 endpoints must persist in decoded-source coordinates after zoom/pan and letterboxing.');
    assert.equal(savedRegionCaliperD2.calibration_source, 'MANUAL');

    // Seed a long synthetic D1 history through the live API so the browser must page it.
    const historyLease = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        caseId: state.editing?.caseId,
        allowed: state.editing?.allowed,
        leaseToken: state.editing?.leaseToken,
        pageInstanceId: state.editing?.pageInstanceId,
      };
    });
    assert.equal(historyLease.caseId, id);
    assert.equal(historyLease.allowed, true);
    assert.ok(historyLease.leaseToken, 'Synthetic history writes use the active viewer lease, not a stale HITL session header.');
    assert.ok(historyLease.pageInstanceId);
    let seededD1Revision = savedRegionCaliper.measurement_revision;
    for (let index = 0; index < 100; index += 1) {
      const response = await page.request.post(
        `${server.base}/api/cases/${id}/images/${leftImageId}/regions/${targetAssignment.region_id}/calipers`,
        {
          headers: { Authorization: `Bearer ${authToken}` },
          data: {
            request_id: crypto.randomUUID(),
            expected_revision: seededD1Revision,
            assignment_request_id: confirmedRegions.assignment_request_id,
            review_id: confirmedRegions.review_id,
            region_id: targetAssignment.region_id,
            mask_sha256: confirmedRegions.mask_sha256,
            label: 'D1',
            points: savedRegionCaliper.points,
            coordinate_space: 'decoded-source-image',
            lease_token: historyLease.leaseToken,
            page_instance_id: historyLease.pageInstanceId,
          },
        },
      );
      assert.equal(response.status(), 200, `Synthetic caliper history revision ${seededD1Revision + 1}: ${await response.text()}`);
      savedRegionCaliper = await response.json();
      seededD1Revision += 1;
      assert.equal(savedRegionCaliper.measurement_revision, seededD1Revision);
      assert.equal(savedRegionCaliper.current, true);
    }
    await page.locator(`[data-region-select="${targetAssignment.region_id}"]`).click();
    await page.waitForFunction(() =>
      /D1 .* mm .* D2 .* mm/.test(document.querySelector('#cdssRegionStatus')?.textContent || ''));

    await page.locator('#cdssPanel > summary').click();
    await page.locator('#cdssForm [name=assessment_source]').selectOption('clinician');
    await page.locator('#cdssForm [name=modality]').selectOption('ultrasound_2d');
    await page.locator('#cdssForm [name=ultrasound_exam_complete]').selectOption('false');
    assert.equal(Number(await page.locator('#cdssForm [name=max_diameter_mm]').inputValue()), savedRegionCaliper.diameter_mm,
      'D1 may prefill the exact measured diameter only when calibration provenance is valid.');
    await page.locator('#cdssConfirm').check();
    const assessmentUrl = `**/api/cases/${id}/images/${leftImageId}/regions/${targetAssignment.region_id}/cdss-assessments`;
    let dropAssessmentOnce = true;
    await page.route(assessmentUrl, route => {
      if (dropAssessmentOnce && route.request().method() === 'POST') {
        dropAssessmentOnce = false;
        return route.abort('failed');
      }
      return route.continue();
    });
    const firstAssessmentAttempt = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/cdss-assessments`));
    await page.locator('#cdssEvaluate').click();
    const failedAssessmentRequest = await firstAssessmentAttempt;
    const failedAssessmentPayload = JSON.parse(failedAssessmentRequest.postData());
    const expectedAssessmentFindings = {
      assessment_source: 'clinician',
      modality: 'ultrasound_2d',
      ultrasound_exam_complete: false,
      max_diameter_mm: savedRegionCaliper.diameter_mm,
    };
    assert.equal(failedAssessmentPayload.assignment_request_id, confirmedRegions.assignment_request_id);
    assert.equal(failedAssessmentPayload.region_id, targetAssignment.region_id);
    assert.equal(failedAssessmentPayload.review_id, leftReviewId);
    assert.equal(failedAssessmentPayload.expected_assessment_revision, 0);
    assert.equal(failedAssessmentPayload.confirmed, true);
    assert.deepEqual(failedAssessmentPayload.vision_findings, expectedAssessmentFindings,
      'The live CDSS request must contain the exact clinician-entered fields and the selected region D1.');
    assert.deepEqual(failedAssessmentPayload.patient_context, {});
    await page.waitForFunction(() => document.querySelector('#cdssResult')?.dataset.status === 'ERROR');
    assert.equal(await page.locator('#cdssEvaluate').isEnabled(), true,
      'A failed CDSS request must leave an explicit retry action available.');
    const retryAssessmentAttempt = page.waitForRequest(request =>
      request.method() === 'POST' && new URL(request.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/cdss-assessments`));
    const assessmentWrite = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith(`/regions/${targetAssignment.region_id}/cdss-assessments`));
    await page.locator('#cdssEvaluate').click();
    const retriedAssessmentRequest = await retryAssessmentAttempt;
    assert.equal(JSON.parse(retriedAssessmentRequest.postData()).request_id, failedAssessmentPayload.request_id,
      'CDSS retry must reuse its idempotency key after a lost response.');
    const assessmentResponse = await assessmentWrite;
    await page.unroute(assessmentUrl);
    assert.equal(assessmentResponse.status(), 200, await assessmentResponse.text());
    const savedAssessment = await assessmentResponse.json();
    assert.equal(savedAssessment.status, 'SAVED_RUO');
    assert.equal(savedAssessment.assessment_revision, 1);
    assert.equal(savedAssessment.assignment_request_id, confirmedRegions.assignment_request_id);
    assert.equal(savedAssessment.region_id, targetAssignment.region_id);
    assert.equal(savedAssessment.review_id, leftReviewId);
    assert.equal(savedAssessment.review_revision, savedRegionState.assignment.review_revision);
    assert.deepEqual(savedAssessment.vision_findings, expectedAssessmentFindings);
    assert.deepEqual(savedAssessment.patient_context, {});
    assert.equal(savedAssessment.source_caliper_event_id, savedRegionCaliper.request_id);
    assert.equal(savedAssessment.result.status, 'INSUFFICIENT_DATA');
    assert.equal(savedAssessment.result.orads_stratification.category, null);
    assert.match(await page.locator('#cdssResult').innerText(), /Assessment RUO đã lưu · phiên bản 1/);

    // Seed older RUO assessment revisions through the live endpoint; they remain traceable but stale.
    let seededAssessmentRevision = savedAssessment.assessment_revision;
    let latestSeededAssessment = savedAssessment;
    for (let index = 0; index < 100; index += 1) {
      const response = await page.request.post(
        `${server.base}/api/cases/${id}/images/${leftImageId}/regions/${targetAssignment.region_id}/cdss-assessments`,
        {
          headers: { Authorization: `Bearer ${authToken}` },
          data: {
            ...failedAssessmentPayload,
            request_id: crypto.randomUUID(),
            expected_assessment_revision: seededAssessmentRevision,
            vision_findings: {
              ...failedAssessmentPayload.vision_findings,
              max_diameter_mm: savedRegionCaliper.diameter_mm,
            },
            source_caliper_event_id: savedRegionCaliper.request_id,
          },
        },
      );
      assert.equal(response.status(), 200, `Synthetic assessment history revision ${seededAssessmentRevision + 1}: ${await response.text()}`);
      latestSeededAssessment = await response.json();
      seededAssessmentRevision += 1;
      assert.equal(latestSeededAssessment.assessment_revision, seededAssessmentRevision);
      assert.deepEqual(latestSeededAssessment.vision_findings, expectedAssessmentFindings);
      assert.equal(latestSeededAssessment.current, true);
    }

    // Leave and reopen again: both the region caliper and exact RUO assessment must hydrate from SQLite.
    await page.evaluate(() => { location.hash = '#cases'; });
    await page.locator('#caseResults').waitFor();
    await page.evaluate(studyId => { location.hash = '#viewer/' + studyId; }, id);
    await page.locator('#researchTab').click();
    await page.locator('[data-region-load]').click();
    await page.locator(`[data-region-select="${targetAssignment.region_id}"]`).waitFor();
    await page.locator(`[data-region-select="${targetAssignment.region_id}"]`).click();
    await page.waitForFunction(expectedRevision =>
      document.querySelector('#cdssResult')?.textContent.includes(`Assessment RUO đã lưu · phiên bản ${expectedRevision}`),
    latestSeededAssessment.assessment_revision);
    await page.waitForFunction(() =>
      /D1 .* mm .* D2 .* mm/.test(document.querySelector('#cdssRegionStatus')?.textContent || ''));
    assert.equal(Number(await page.locator('#cdssForm [name=max_diameter_mm]').inputValue()), savedRegionCaliper.diameter_mm);
    assert.equal(await page.locator('#cdssForm [name=assessment_source]').inputValue(), 'clinician');
    assert.equal(await page.locator('#cdssForm [name=modality]').inputValue(), 'ultrasound_2d');
    assert.equal(await page.locator('#cdssForm [name=ultrasound_exam_complete]').inputValue(), 'false');
    assert.match(await page.locator('#regionCaliperStatus').innerText(), /D1: .* mm/);
    assert.equal(await page.locator('#cdssConfirm').isChecked(), false);

    await page.locator('#cdssPanel > summary').click();
    await page.locator('#cdssRegionHistory > summary').click();
    await page.locator('#cdssRegionHistoryMore').waitFor({ state: 'visible' });
    const historyBeforePage = await page.locator('#cdssRegionHistoryContent').innerText();
    assert.equal(historyBeforePage.split('\n').filter(line => /^D1 · revision /.test(line)).length, 100);
    assert.equal(historyBeforePage.split('\n').filter(line => /^Revision \d+ · /.test(line)).length, 100);
    const cursorPageResponses = [
      page.waitForResponse(response => {
        const url = new URL(response.url());
        return response.request().method() === 'GET' &&
          url.pathname.endsWith(`/regions/${targetAssignment.region_id}/calipers`) && url.searchParams.has('cursor');
      }),
      page.waitForResponse(response => {
        const url = new URL(response.url());
        return response.request().method() === 'GET' &&
          url.pathname.endsWith(`/regions/${targetAssignment.region_id}/cdss-assessments`) && url.searchParams.has('cursor');
      }),
    ];
    await page.locator('#cdssRegionHistoryMore').click();
    const [caliperHistoryPage, assessmentHistoryPage] = await Promise.all(cursorPageResponses);
    assert.equal(caliperHistoryPage.status(), 200, await caliperHistoryPage.text());
    assert.equal(assessmentHistoryPage.status(), 200, await assessmentHistoryPage.text());
    const caliperHistoryBody = await caliperHistoryPage.json();
    const assessmentHistoryBody = await assessmentHistoryPage.json();
    assert.equal(caliperHistoryBody.history.length, 5);
    assert.equal(assessmentHistoryBody.history.length, 1);
    assert.equal(caliperHistoryBody.history_has_more, false);
    assert.equal(assessmentHistoryBody.history_has_more, false);
    await page.waitForFunction(() => document.querySelector('#cdssRegionHistoryMore')?.hidden === true);
    const completeHistory = await page.locator('#cdssRegionHistoryContent').innerText();
    assert.equal(completeHistory.split('\n').filter(line => /^D1 · revision /.test(line)).length,
      seededD1Revision);
    assert.equal(completeHistory.split('\n').filter(line => /^D2 · revision /.test(line)).length, 1);
    assert.equal(completeHistory.split('\n').filter(line => /^Revision \d+ · /.test(line)).length,
      latestSeededAssessment.assessment_revision);
    assert.match(completeHistory, new RegExp(`D1 · revision ${seededD1Revision} · .*hiện hành`));
    assert.match(completeHistory, new RegExp(`Revision ${latestSeededAssessment.assessment_revision} · .*hiện hành`));
    assert.match(completeHistory, /D1 · revision 1 · .*lịch sử \/ stale/);
    assert.match(completeHistory, /Revision 1 · .*lịch sử \/ stale/);
    console.log(`PASS: browser loads live paginated history without duplicates; ${seededD1Revision} D1 + 1 D2 events, ${latestSeededAssessment.assessment_revision} assessments; cursor pages ${caliperHistoryBody.history.length}/${assessmentHistoryBody.history.length}; stale rows stay historical`);

    // Exercise ADNEX through the real browser request and isolated backend, using synthetic test inputs.
    await page.locator('#adnexPanel > summary').click();
    await page.locator('#adnexVariant').selectOption('WITHOUT_CA125');
    await page.locator('#adnexAge').fill('45');
    await page.locator('#adnexOncology').selectOption('false');
    await page.locator('#adnexPersistent').selectOption('true');
    await page.locator('#adnexSurgery').selectOption('true');
    await page.locator('#adnexComplete').selectOption('true');
    await page.locator('#adnexPhysiologic').selectOption('false');
    await page.locator('#adnexDiameter').fill('40');
    await page.locator('#adnexSolidDiameter').fill('0');
    await page.locator('#adnexLocules').fill('1');
    await page.locator('#adnexPapillary').fill('0');
    await page.locator('#adnexShadow').selectOption('false');
    await page.locator('#adnexAscites').selectOption('false');
    const liveAdnexResponse = page.waitForResponse(response =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/v1/cdss/evaluate');
    await page.locator('#adnexEvaluate').click();
    const liveAdnexHttpResponse = await liveAdnexResponse;
    assert.equal(liveAdnexHttpResponse.status(), 200, await liveAdnexHttpResponse.text());
    const liveAdnexBody = await liveAdnexHttpResponse.json();
    const liveAdnex = liveAdnexBody.adnex_evaluation;
    assert.equal(liveAdnex.status, 'EVALUATED_RUO');
    assert.equal(liveAdnex.eligibility_status, 'ELIGIBLE');
    assert.equal(liveAdnex.model_variant, 'WITHOUT_CA125');
    const liveProbabilities = Object.values(liveAdnex.probabilities);
    assert.equal(liveProbabilities.length, 5);
    assert.ok(liveProbabilities.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
    assert.ok(Math.abs(liveProbabilities.reduce((sum, value) => sum + value, 0) - 1) <= 1e-6);
    const liveMalignancyTotal = liveProbabilities.slice(1).reduce((sum, value) => sum + value, 0);
    assert.ok(Math.abs(liveMalignancyTotal - liveAdnex.total_malignancy_probability) <= 1e-6);
    await page.locator('#adnexResult[data-status="EVALUATED_RUO"]').waitFor();
    assert.equal(await page.locator('#adnexProbabilityList [data-adnex-probability]').count(), 5);
    console.log('PASS: ADNEX browser → live isolated backend → probability-vector validation/rendering on synthetic inputs');

    console.log('PASS: region review, source-coordinate calibrated caliper, live CDSS persistence and reload through browser/API/SQLite');
    await page.locator('[data-action=side-R]').click();
    await page.waitForFunction(() => document.querySelector('#notes')?.value === 'Rà soát kỹ thuật ảnh tổng hợp bên phải.');
    await page.evaluate(() => {
      const canvasPrototype = window.CanvasRenderingContext2D?.prototype;
      const drawDescriptor = canvasPrototype && Object.getOwnPropertyDescriptor(canvasPrototype, 'drawImage');
      if (!drawDescriptor?.configurable)
        throw new Error('Browser does not support reversible report image instrumentation.');
      const originalDraw = drawDescriptor.value;
      window.__reportImageProbe = { failedDraws: 0, lastImage: null };
      Object.defineProperty(canvasPrototype, 'drawImage', {
        ...drawDescriptor,
        value: function (source, ...args) {
          if (source instanceof window.HTMLImageElement && window.__reportImageProbe.failedDraws === 0) {
            window.__reportImageProbe.failedDraws += 1;
            window.__reportImageProbe.lastImage = source;
            throw new Error('Injected report canvas draw failure.');
          }
          return originalDraw.call(this, source, ...args);
        },
      });
      window.__restoreReportBitmapProbe = () => {
        Object.defineProperty(canvasPrototype, 'drawImage', drawDescriptor);
      };
    });
    await page.locator('[data-action=report]').click();
    await page.locator('#reportData [data-action=retry-report]').waitFor();
    const failedReportImageState = await page.evaluate(() => ({
      failedDraws: window.__reportImageProbe?.failedDraws,
      releasedSource: window.__reportImageProbe?.lastImage?.src === 'data:,',
      message: document.querySelector('#reportData [role=alert]')?.innerText,
    }));
    assert.equal(failedReportImageState.failedDraws, 1, JSON.stringify(failedReportImageState));
    assert.equal(failedReportImageState.releasedSource, true, JSON.stringify(failedReportImageState));
    assert.match(failedReportImageState.message, /Injected report canvas draw failure\./);
    await page.evaluate(() => window.__restoreReportBitmapProbe());
    await page.locator('#reportData [data-action=retry-report]').click();
    await page.locator('#reportData .report').waitFor();
    console.log('PASS: report source image releases its URL after a canvas failure and report route retries successfully');
    const report = await page.locator('#reportData .report').innerText();
    assert.equal(await page.locator('#reportData .patient-friendly-summary-panel').count(), 0);
    assert.match(report, /Không dùng cho chăm sóc bệnh nhân/);
    assert.match(report, /DEMO DỮ LIỆU TỔNG HỢP · KHÔNG PHẢI HỒ SƠ BỆNH NHÂN/);
    assert.equal(await page.locator('#reportData .report-synthetic-demo-banner').count(), 3,
      'The summary and every printed image page must identify the synthetic demo data.');
    assert.match(report, /Nguồn dữ liệu chưa được xác minh/);
    assert.doesNotMatch(report, /Bình thường|lành tính|tái khám|hướng xử trí|xác suất ác tính/iu);
    assert.deepEqual(await page.locator('#toasts .toast.danger').allTextContents(), [],
      'Normal report navigation must not leave an error toast.');
    const supportIndex = report.indexOf('THÔNG TIN HỖ TRỢ');
    assert.match(report, /Revision:\s*2/);
    assert.match(report, new RegExp(`Visit:\\s*${visitNo}`));
    assert.match(report, /Trạng thái lưu rà soát\s+Đã lưu rà soát cho các ảnh trong hồ sơ/);
    assert.match(report, /Mask đã được bác sĩ rà soát/);
    assert.ok(supportIndex > 0, 'Technical metadata belongs in the lower support block.');
    assert.doesNotMatch(report.slice(0, supportIndex), /doctor|Reviewer ID|Người rà soát:/i);
    assert.match(report.slice(supportIndex), /Reviewer ID\s+doctor/);
    assert.match(report, /KẾT QUẢ GHI NHẬN/);
    assert.match(report, /BÊN TRÁI/);
    assert.match(report, /BÊN PHẢI/);
    assert.match(report, /HÌNH ẢNH KHẢO SÁT/);
    assert.match(report, /Rà soát kỹ thuật ảnh tổng hợp bên trái/);
    assert.match(report, /Rà soát kỹ thuật ảnh tổng hợp bên phải/);
    assert.match(report, /D₁\/D₂ theo caliper bác sĩ đã lưu/);
    assert.equal(await page.locator('#reportData .report-overlay-status').count(), 2);
    if (process.env.E2E_REPORT_SCREENSHOT) {
      await page.locator('#reportData .report').screenshot({ path: process.env.E2E_REPORT_SCREENSHOT });
    }
    await page.evaluate(() => { window.print = () => { window.__printCalled = true; }; });
    await page.locator('[data-action=print]').click();
    await page.waitForFunction(() => window.__printCalled === true);
    assert.deepEqual(await page.locator('#toasts .toast.danger').allTextContents(), [], 'Printing a saved RUO report must not leave an error toast.');
    assert.equal(await page.locator('#printRoot .report').count(), 1);
    assert.equal(await page.locator('#printRoot .patient-friendly-summary-panel').count(), 0);
    const reportPdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
    const pdfPageCount = (reportPdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
    assert.equal(pdfPageCount, 3, `Expected one summary page plus one page per image, got ${pdfPageCount} pages.`);
    if (process.env.E2E_REPORT_PRINT_PAGE1_SCREENSHOT || process.env.E2E_REPORT_PRINT_PAGE2_SCREENSHOT) {
      await page.emulateMedia({ media: 'print' });
      if (process.env.E2E_REPORT_PRINT_PAGE1_SCREENSHOT) {
        await page.locator('#printRoot .report-summary-page').screenshot({ path: process.env.E2E_REPORT_PRINT_PAGE1_SCREENSHOT });
      }
      if (process.env.E2E_REPORT_PRINT_PAGE2_SCREENSHOT) {
        await page.locator('#printRoot .report-evidence-page').first().screenshot({ path: process.env.E2E_REPORT_PRINT_PAGE2_SCREENSHOT });
      }
      await page.emulateMedia({ media: 'screen' });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileFits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    assert.equal(mobileFits, true, 'The report preview must not overflow a 390px viewport.');
    if (process.env.E2E_REPORT_MOBILE_SCREENSHOT) {
      await page.locator('#reportData .report').screenshot({ path: process.env.E2E_REPORT_MOBILE_SCREENSHOT });
    }
    assert.deepEqual(errors, []);
    await page.route('**/api/health', route => route.abort('failed'));
    await page.route('**/api/capabilities', route => route.abort('failed'));
    await page.reload();
    await page.locator('#reportData [data-action=retry-environment]').waitFor();
    assert.equal(await page.locator('#environmentUnknownBanner').isVisible(), true,
      'The environment must remain visibly unverified when both capability endpoints fail.');
    assert.equal(await page.locator('[data-action=print]').isDisabled(), true,
      'Printing must remain blocked until RUO/data-origin capabilities have been confirmed.');
    assert.equal(await page.locator('#reportData .report-synthetic-demo-banner').count(), 0,
      'Unknown mode must not render report content without its synthetic-data marker.');
    assert.equal(await page.locator('#reportData .report').count(), 0,
      'The report must not load case details while the environment is unverified.');
    await page.unroute('**/api/health');
    await page.unroute('**/api/capabilities');
    const capabilitiesResponse = await page.request.get(server.base + '/api/capabilities');
    assert.equal(capabilitiesResponse.status(), 200);
    const inconsistentCapabilities = await capabilitiesResponse.json();
    inconsistentCapabilities.synthetic_demo_uploads_restricted = false;
    await page.route('**/api/capabilities', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(inconsistentCapabilities),
    }));
    await page.locator('#reportData [data-action=retry-environment]').click();
    await page.locator('#reportData [data-environment-status]').waitFor();
    assert.match(await page.locator('#reportData [data-environment-status]').innerText(), /chưa xác minh/i);
    assert.equal(await page.locator('[data-action=print]').isDisabled(), true,
      'A contradictory capability response must not unlock report printing.');
    assert.equal(await page.locator('#reportData .report').count(), 0,
      'A contradictory capability response must not load case details.');
    await page.unroute('**/api/capabilities');
    await page.locator('#reportData [data-action=retry-environment]').click();
    await page.locator('#reportData .report').waitFor();
    assert.equal(await page.locator('#environmentUnknownBanner').isHidden(), true,
      'A successful capability retry must clear the unknown-environment warning.');
    assert.equal(await page.locator('#reportData .report-synthetic-demo-banner').count(), 3,
      'The report may load only after the verified synthetic mode is restored.');
    assert.equal(await page.locator('[data-action=print]').isDisabled(), false,
      'Printing the RUO draft becomes available after the environment is verified.');
    await page.route('**/api/capabilities', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(inconsistentCapabilities),
    }));
    await page.locator('[data-action=print]').click();
    await page.locator('#reportData [data-action=retry-environment]').waitFor();
    assert.equal(await page.locator('#reportData .report').count(), 0,
      'Printing must refresh capabilities and remove the report if the current environment is contradictory.');
    assert.equal(await page.locator('[data-action=print]').isDisabled(), true,
      'Printing must remain disabled after a contradictory capability refresh.');
    await page.unroute('**/api/capabilities');
    await page.locator('#reportData [data-action=retry-environment]').click();
    await page.locator('#reportData .report').waitFor();
    assert.equal(await page.locator('[data-action=print]').isDisabled(), false,
      'A successful retry must restore the report and its RUO print action.');
    await page.route('**/api/capabilities', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(inconsistentCapabilities),
    }));
    await page.evaluate(() => { location.hash = '#dashboard'; });
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(studyId => { location.hash = `#report/${encodeURIComponent(studyId)}`; }, persisted.study_id);
    await page.locator('#reportData .report, #reportData [data-action=retry-environment]').waitFor();
    assert.equal(await page.locator('#reportData [data-action=retry-environment]').count(), 1,
      'Opening another report must refresh capabilities instead of trusting a previously verified cache.');
    assert.equal(await page.locator('#reportData .report').count(), 0,
      'A capability change while the app remains open must keep report content locked.');
    assert.equal(await page.locator('[data-action=print]').isDisabled(), true,
      'A capability change while the app remains open must keep printing locked.');
    console.log('PASS: report content and printing fail closed on unavailable, contradictory, and newly changed capabilities; retry recovers with the synthetic disclosure');
    console.log(JSON.stringify({ status: 'PASS', scope: 'isolated auth/intake/upload/IQA/model/review/region-assignment/DB/reopen/report/print with synthetic images; success responses are live and request failures are fault-injected', reviewRevision: saved.review_revision, regionRevision: savedRegionState.assignment.review_revision, images: persisted.images.length, pdfPages: pdfPageCount, pageErrors: errors.length }));
  } finally {
    const isolatedRuntime = server.runtime;
    await server.close();
    assert.equal(fs.existsSync(isolatedRuntime), false,
      'The temporary synthetic case database and uploaded files must be removed after the demo run.');
  }
}
main().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
