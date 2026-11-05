/**
 * End-to-End Browser verification of newly implemented UI/UX features:
 * 1. Email registration and verification flow
 * 2. Login without embedded development credentials
 * 3. Manual AI activation button (#startSegmentationBtn) on #intake
 * 4. Full segmentation, measurements, and viewer loading
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const { waitForAppState } = require('./helpers/app_state_wait.cjs');

let base = '';

function clinicalWriteCount(requests) {
  return requests.filter(({ method, path: pathname }) =>
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) &&
    pathname !== '/api/cases/search' &&
    pathname !== '/api/workspace/cases/search',
  ).length;
}

function clinicalMutationCount(requests) {
  return requests.filter(({ method, path: pathname }) =>
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) &&
    pathname !== '/api/cases/search' &&
    pathname !== '/api/workspace/cases/search' &&
    pathname !== '/api/v1/cdss/evaluate' &&
    pathname !== '/api/v1/segment/candidate' &&
    !/^\/api\/images\/[^/]+\/measurements$/.test(pathname),
  ).length;
}

async function test_cdss_requires_a_saved_region_and_sends_no_defaults(page, requests) {
  const panel = page.locator('#cdssPanel');
  await panel.waitFor();
  await panel.locator('summary').first().click();
  const unanswered = await page.locator('#cdssForm select').evaluateAll(selects =>
    selects.every(select => select.value === ''),
  );
  assert.equal(unanswered, true, 'all clinical descriptors, IOTA rules and context begin unanswered');
  const requestTraceBefore = requests.length;
  assert.equal(await page.locator('#cdssEvaluate').isDisabled(), true,
    'CDSS must remain unavailable until the clinician selects a persisted, confirmed region.');
  assert.match(await page.locator('#cdssRegionStatus').textContent(), /Chọn một vùng đã xác nhận/);
  const cdssCalls = requests.slice(requestTraceBefore).filter(({ path: pathname }) =>
    pathname.includes('/cdss-assessments') || pathname === '/api/v1/cdss/evaluate',
  );
  assert.deepEqual(cdssCalls, [], 'an unscoped assessment must not be sent or persisted');
}

async function test_grid_reuses_filtered_rows_thumbnails_and_case_route(page, studyId, reviewedStudy, requests) {
  const gridButton = page.locator('#caseGridView');
  assert.equal(await gridButton.count(), 1, 'the worklist grid view control is present');
  const writesBefore = clinicalWriteCount(requests);
  const studyImageIds = new Set(reviewedStudy.images.map(image => image.image_id));
  const thumbnailReadCount = () => requests.filter(({ method, path: pathname }) =>
    method === 'GET' && [...studyImageIds].some(id => pathname === `/api/images/${id}/source.png`),
  ).length;
  await page.waitForFunction(ids => {
    const images = [...document.querySelectorAll('#caseResults .table-wrap img[data-thumb]')];
    return images.length === ids.length && images.every(image => image.complete && image.naturalWidth > 0);
  }, [...studyImageIds], { timeout: 15000 });
  const readsBeforeViewSwitch = thumbnailReadCount();
  await gridButton.click();
  await page.waitForFunction(() => document.querySelectorAll('#caseResults [data-worklist-card]').length === 1);
  const card = page.locator(`#caseResults [data-worklist-card="${studyId}"]`);
  assert.equal(await card.count(), 1, 'grid contains only the case returned by the current exact search');
  const thumbnails = card.locator('img[data-thumb]');
  assert.deepEqual(await thumbnails.evaluateAll(images => images.map(image => image.dataset.thumb).sort()),
    reviewedStudy.images.map(image => image.image_id).sort());
  await page.waitForFunction(id => {
    const images = [...document.querySelectorAll(`#caseResults [data-worklist-card="${id}"] img[data-thumb]`)];
    return images.length === 2 && images.every(image => image.complete && image.naturalWidth > 0);
  }, studyId, { timeout: 15000 });
  assert.equal(thumbnailReadCount(), readsBeforeViewSwitch,
    'switching from table to grid reuses already loaded thumbnail images');
  assert.match(await card.innerText(), new RegExp(reviewedStudy.study_code));

  await page.locator('#caseStatus').selectOption('ANALYZED');
  await page.waitForFunction(() => document.querySelector('#caseResults .pagination span')?.textContent.startsWith('0 ca'));
  assert.equal(await page.locator('#caseResults [data-worklist-card]').count(), 0,
    'status filtering removes cards outside the current API result');
  await page.locator('#caseStatus').selectOption('');
  await page.waitForFunction(() => document.querySelector('#caseResults .pagination span')?.textContent.startsWith('1 ca'));
  assert.equal(await page.locator('#caseResults [data-worklist-card]').count(), 1,
    'resetting the filter restores only the matching API row');

  await page.locator('#caseTableView').click();
  await page.locator('#caseResults .table-wrap').waitFor();
  assert.equal(await page.locator('#caseResults .case-select, #selectAll, [data-action="export-selected"]').count(), 0,
    'RUO worklist must not expose unsupported bulk selection/export controls.');
  assert.match(await page.locator('[data-export-status="disabled"]').innerText(), /đang bị khóa trên máy chủ/i);
  await gridButton.click();
  await page.locator(`#caseResults [data-worklist-card="${studyId}"]`).waitFor();
  assert.equal(await card.locator('.worklist-grid-open').getAttribute('href'), `#viewer/${studyId}`);
  assert.equal(thumbnailReadCount(), readsBeforeViewSwitch,
    'filter restore and repeated view switches do not reload the same thumbnails');
  assert.equal(clinicalWriteCount(requests), writesBefore, 'grid, filters and selection do not submit clinical writes');
  return { writesBefore, status: reviewedStudy.status, revision: reviewedStudy.review_revision };
}

async function test_grid_display_never_marks_reviewed_or_bulk_signs(page, studyId, doctorToken, requests, before) {
  const card = page.locator(`#caseResults [data-worklist-card="${studyId}"]`);
  assert.equal(await card.locator('[data-action="sign"], [data-action="sign-all"]').count(), 0,
    'individual review cards expose no sign or bulk-sign action');
  assert.doesNotMatch(await card.innerText(), /ký hàng loạt|duyệt tất cả/i);
  const beforeResponse = await page.request.get(base + '/api/cases/' + studyId, {
    headers: { Authorization: 'Bearer ' + doctorToken },
  });
  const beforeStudy = await beforeResponse.json();
  assert.equal(beforeStudy.status, before.status);
  assert.equal(beforeStudy.review_revision, before.revision);
  assert.equal(clinicalWriteCount(requests), before.writesBefore,
    'displaying thumbnails does not issue a review, sign or status write');
  const afterResponse = await page.request.get(base + '/api/cases/' + studyId, {
    headers: { Authorization: 'Bearer ' + doctorToken },
  });
  const afterStudy = await afterResponse.json();
  assert.equal(afterStudy.status, beforeStudy.status, 'thumbnail display does not change review status');
  assert.equal(afterStudy.review_revision, beforeStudy.review_revision, 'thumbnail display does not create a review revision');
}

async function test_worklist_thumbnail_failure_recovers_after_refresh(page, studyId, imageId, studyCode, doctorToken, requests, errors, httpFailures) {
  const imagePath = `/api/images/${encodeURIComponent(imageId)}/source.png`;
  const routePattern = `**${imagePath}`;
  const failureCountBefore = httpFailures.length;
  const consoleErrorCountBefore = errors.length;
  const mutationsBefore = requests.filter(({ method }) =>
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method),
  ).length;
  const studyBeforeResponse = await page.request.get(base + '/api/cases/' + studyId, {
    headers: { Authorization: 'Bearer ' + doctorToken },
  });
  assert.equal(studyBeforeResponse.status(), 200);
  const studyBefore = await studyBeforeResponse.json();
  let failOnce = true;
  await page.route(routePattern, async route => {
    if (failOnce && route.request().method() === 'GET') {
      failOnce = false;
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'temporary synthetic thumbnail failure' }),
      });
    }
    return route.continue();
  });

  await page.evaluate(id => { location.hash = `#viewer/${encodeURIComponent(id)}`; }, studyId);
  await page.locator('#viewport').waitFor({ timeout: 15000 });
  await page.evaluate(() => { location.hash = '#cases'; });
  await page.locator('[data-action="refresh-cases"]').waitFor({ timeout: 15000 });
  await page.waitForFunction(() =>
    document.querySelectorAll('#caseResults .case-thumb-placeholder[role="img"][aria-label="Chưa tải được ảnh xem trước"]').length === 1,
  null, { timeout: 15000 });

  assert.equal(failOnce, false, 'the isolated thumbnail request must be fault-injected once');
  const injectedFailures = httpFailures.slice(failureCountBefore);
  assert.equal(injectedFailures.length, 1, JSON.stringify(injectedFailures));
  assert.equal(injectedFailures[0].status, 503);
  assert.equal(new URL(injectedFailures[0].url).pathname, imagePath);
  const injectedConsoleErrors = errors.slice(consoleErrorCountBefore);
  assert.equal(injectedConsoleErrors.length, 1, JSON.stringify(injectedConsoleErrors));
  assert.match(injectedConsoleErrors[0], /503.*Service Unavailable/i);
  errors.splice(consoleErrorCountBefore, 1);

  const attemptsBeforeRetry = requests.filter(request =>
    request.method === 'GET' && request.path === imagePath,
  ).length;
  await page.locator('[data-action="refresh-cases"]').click();
  await page.waitForFunction(id => {
    const image = [...document.querySelectorAll('#caseResults img[data-thumb]')]
      .find(candidate => candidate.dataset.thumb === id);
    return image?.complete && image.naturalWidth > 0;
  }, imageId, { timeout: 15000 });
  const attemptsAfterRetry = requests.filter(request =>
    request.method === 'GET' && request.path === imagePath,
  ).length;
  assert.equal(attemptsAfterRetry, attemptsBeforeRetry + 1,
    'refresh retries the failed preview request instead of keeping a cached rejection');

  httpFailures.splice(failureCountBefore, 1);
  await page.unroute(routePattern);
  await page.locator('#caseSearch').fill(studyCode);
  await page.waitForFunction(() =>
    document.querySelector('#caseResults .pagination span')?.textContent.startsWith('1 ca'),
  null, { timeout: 15000 });
  await page.locator('#caseGridView').click();
  await page.locator(`#caseResults [data-worklist-card="${studyId}"]`).waitFor();

  const mutations = requests.filter(({ method }) =>
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method),
  ).slice(mutationsBefore);
  const leasePath = `/api/workspace/cases/${studyId}/lease`;
  const unexpectedMutations = mutations.filter(({ method, path: pathname }) =>
    !(pathname === leasePath && ['POST', 'DELETE'].includes(method)) &&
    !(pathname === '/api/hitl/sessions' && method === 'POST') &&
    !(pathname === '/api/cases/search' && method === 'POST') &&
    !(pathname === '/api/workspace/cases/search' && method === 'POST'),
  );
  assert.deepEqual(unexpectedMutations, [],
    'thumbnail failure and refresh must not submit review, sign, or status changes');
  const studyAfterResponse = await page.request.get(base + '/api/cases/' + studyId, {
    headers: { Authorization: 'Bearer ' + doctorToken },
  });
  assert.equal(studyAfterResponse.status(), 200);
  const studyAfter = await studyAfterResponse.json();
  assert.equal(studyAfter.status, studyBefore.status);
  assert.equal(studyAfter.review_revision, studyBefore.review_revision);
}

async function test_research_report_preview_renders_html_like_text_as_inert(page, study, requests) {
  const draftPanel = page.locator('.research-report-draft');
  if (!(await draftPanel.evaluate(element => element.open)))
    await draftPanel.locator('summary').click();
  const right = study.images.find(image => image.laterality === 'R');
  const writesBefore = clinicalWriteCount(requests);
  const clinicalStateBefore = await page.evaluate(async () => {
    const { state } = await import('/static/app/state.js');
    return state.case.images.map(image => ({
      imageId: image.image_id,
      notes: image.review?.clinical_notes ?? image.notes ?? '',
      orads: image.review?.orads_score ?? image.orads ?? '',
    }));
  });

  await page.locator('#researchDraftSide').selectOption(right.image_id);
  const draft = page.locator('#researchDraftText');
  const generated = await draft.inputValue();
  assert.ok(generated.includes('Mô tả nang noãn: kích thước 24 mm, nội dung trống và thành mỏng trong dữ liệu tổng hợp.'),
    'the completed clinical dot-phrase is preserved in report draft');
  assert.ok(generated.includes('<img src=x onerror=alert(1)>'),
    'the clinician literal is included as draft text');
  assert.equal(await page.locator('.research-report-draft img, .research-report-draft script').count(), 0,
    'HTML-like clinician text does not create DOM elements');
  assert.match(await page.locator('#researchDraftDisclosure').textContent(), /RUO/i);

  const edited = `${generated}\nBản chỉnh sửa cục bộ`;
  await draft.fill(edited);
  const afterEdit = await page.evaluate(async () => {
    const { state } = await import('/static/app/state.js');
    return {
      dirty: state.dirty,
      clinical: state.case.images.map(image => ({
        imageId: image.image_id,
        notes: image.review?.clinical_notes ?? image.notes ?? '',
        orads: image.review?.orads_score ?? image.orads ?? '',
      })),
    };
  });
  assert.equal(afterEdit.dirty, false, 'editing report preview does not dirty the clinical review');
  assert.deepEqual(afterEdit.clinical, clinicalStateBefore,
    'preview edits do not change saved notes or O-RADS fields');

  await page.evaluate(() => {
    window.__copiedResearchDraft = null;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async text => { window.__copiedResearchDraft = text; } },
    });
  });
  await page.locator('#researchDraftCopy').click();
  await page.waitForFunction(() => window.__copiedResearchDraft !== null);
  const disclosure = await page.locator('#researchDraftDisclosure').textContent();
  assert.equal(await page.evaluate(() => window.__copiedResearchDraft),
    `${edited.trimEnd()}\n\n${disclosure}`,
    'the explicit copy action includes the RUO disclosure');
  assert.equal(clinicalWriteCount(requests), writesBefore, 'preview selection, editing and copying issue no clinical writes');
}

(async () => {
  const server = await startIsolatedBrowser();
  base = server.base;
  const doctorPassword = server.password;
  const adminPassword = server.adminPassword;
  const browser = server.browser;
  console.log('[Test Live UI] Starting isolated browser verification on ' + base + '...');

  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  const httpFailures = [];
  const browserRequests = [];
  let createdStudyId = null;
  page.on('request', request => {
    const url = new URL(request.url());
    browserRequests.push({ method: request.method(), path: url.pathname });
  });
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', message => {
    if (message.type() === 'error') {
      errors.push(message.text());
      console.log('[Browser console error]', JSON.stringify({ text: message.text(), location: message.location() }));
    }
  });
  page.on('response', response => {
    if (response.status() >= 400) {
      httpFailures.push({ status: response.status(), url: response.url() });
      console.log('[Browser HTTP failure]', JSON.stringify({ status: response.status(), url: response.url() }));
    }
  });
  page.on('requestfailed', request => {
    console.log('[Browser request failed]', JSON.stringify({ url: request.url(), error: request.failure()?.errorText }));
  });

  try {
    // ==========================================
    // 1. Verify Login Screen does not expose development credentials
    // ==========================================
    await page.goto(base + '/#login');
    await page.locator('#authForm').waitFor({ timeout: 10000 });
    assert.equal(await page.locator('link[rel="icon"]').getAttribute('href'),
      '/static/assets/brand/vinmec-logo.png?v=20261029-vinmec-tab',
      'the browser tab must use the supplied VINMEC logo');
    assert.ok(browserRequests.some(request => request.path === '/static/assets/brand/vinmec-logo.png'),
      'the RUO app must load its local VINMEC tab logo');
    assert.equal(await page.locator('[data-action^=quick-]').count(), 0, 'Quick-login shortcuts must not exist');
    assert.doesNotMatch(await page.locator('body').innerText(), /doctor-local-test-2026|admin-local-test-2026/);

    // ==========================================
    // 2. Test Account Registration
    // ==========================================
    const regLink = page.locator('a[href="#register"]');
    assert.equal(await regLink.count(), 1, 'Register link must exist on login page');
    await regLink.click();
    await page.waitForTimeout(400);

    assert.equal(await page.locator('h2').textContent(), 'Đăng ký tài khoản bác sĩ');
    assert.equal(await page.locator('[name=full_name]').count(), 1);
    assert.equal(await page.locator('[name=email]').count(), 1);
    assert.equal(await page.locator('[name=department]').count(), 1);

    await page.route('**/api/auth/register', async (route) => {
      const request = route.request().postDataJSON();
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'PENDING_EMAIL_VERIFICATION',
          email: request.email.toLowerCase(),
          email_verification_required: true,
        }),
      });
    });
    await page.route('**/api/auth/verify-email', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'VERIFIED', email_verified: true, activation_pending: true }),
      });
    });
    await page.route('**/api/auth/resend-verification', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ACCEPTED' }) });
    });

    // Test form mismatch validation
    const testUsername = 'dr_test_' + Date.now().toString().slice(-5);
    await page.locator('[name=username]').fill(testUsername);
    await page.locator('[name=full_name]').fill('BS.CKI Kiểm Thử Giao Diện');
    await page.locator('[name=email]').fill(`${testUsername}@example.org`);
    await page.locator('[name=password]').fill('StrongPass123!');
    await page.locator('[name=confirm]').fill('MismatchPass456!');
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForTimeout(300);
    assert.equal(await page.locator('#authError').textContent(), 'Hai mật khẩu chưa trùng khớp.');

    // Fix password match and submit valid registration
    await page.locator('[name=confirm]').fill('StrongPass123!');
    await page.locator('#authForm button[type=submit]').click();

    await page.locator('h2').filter({ hasText: 'Xác minh email' }).waitFor({ timeout: 10000 });
    assert.equal(await page.locator('[name=email]').inputValue(), `${testUsername}@example.org`);
    await page.locator('#resendVerification').click();
    await page.locator('[name=code]').fill('123456');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('h2').filter({ hasText: 'Đăng nhập hệ thống' }).waitFor({ timeout: 10000 });
    assert.match(await page.locator('body').innerText(), /tài khoản do đơn vị quản trị cấp/i);

    // ==========================================
    // 3. Sign in with operator-provisioned test account
    // ==========================================
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(doctorPassword);
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });
    console.log('[Test Live UI] Email verification UI and provisioned login verified.');

    // ==========================================
    // 5. Test Intake & Manual AI Activation Button
    // ==========================================
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-action="anonymous-study"]').click();
    await page.locator('#startSegmentationBtn').waitFor({ timeout: 5000 });

    // Verify initial button state is disabled
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);

    const files = require('./validation_files.cjs');
    assert.equal(files.length, 2, 'Validation files must exist');

    // Upload Left image
    await page.locator('[data-file=L]').setInputFiles(files[0]);
    await page.waitForTimeout(400);
    assert.equal(await page.locator('#stage-R').textContent(), 'Chờ ảnh');
    // Button still disabled because Right image is not yet chosen
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);

    // Upload Right image
    await page.locator('[data-file=R]').setInputFiles(files[1]);
    await page.waitForTimeout(400);
    // The confirmed study date is also required: verify when empty it is disabled
    await page.locator('[name=study-date]').fill('');
    await page.locator('[name=study-date]').dispatchEvent('input');
    assert.equal(await page.locator('#startSegmentationBtn').isDisabled(), true);
    await page.locator('[name=study-date]').fill('2026-10-21T09:00');
    await page.locator('[name=study-date]').dispatchEvent('input');
    assert.equal(await page.locator('#startSegmentationBtn').isEnabled(), true);
    console.log('[Test Live UI] startSegmentationBtn enabled after date and bilateral images are set.');

    // Click the manual activation button
    const firstInferenceResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.startsWith('/api/predict/'),
    );
    await page.locator('#startSegmentationBtn').click();
    console.log('[Test Live UI] Clicked startSegmentationBtn, waiting for bilateral inference...');

    const firstInferenceResponse = await firstInferenceResponsePromise;
    const inferenceBody = await firstInferenceResponse.text();
    if (firstInferenceResponse.status() === 503 &&
      /Checkpoint mô hình chưa được nạp hoặc không khớp SHA-256 đã chọn/i.test(inferenceBody)) {
      await waitForAppState(page, snapshot => !snapshot.busy, { message: 'provenance gate response settled' });
      const blockedUi = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          route: state.route,
          busy: state.busy,
          predictionIds: state.case?.images?.map(image => image.prediction_id ?? null) ?? [],
          intakeError: document.querySelector('#intakeError')?.innerText || '',
        };
      });
      const expectedProvenanceConsoleErrors = errors.filter(message =>
        /Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)/i.test(message));
      const unexpectedBrowserErrors = errors.filter(message =>
        !/Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)/i.test(message));
      const evidenceDir = path.resolve(__dirname, '../artifacts/qa-clinical-fixed');
      fs.mkdirSync(evidenceDir, { recursive: true });
      const evidence = {
        status: 'BLOCKED',
        blocker: 'Inference returned HTTP 503 because the selected checkpoint is not loaded or its SHA-256 does not match the verified selection.',
        apiStatus: firstInferenceResponse.status(),
        ui: blockedUi,
        expectedProvenanceConsoleErrors,
        unexpectedBrowserErrors,
        pageErrors: [],
        scope: 'isolated browser/server/SQLite with generated synthetic images; registration, login, anonymous intake, bilateral upload, and pre-inference controls executed',
      };
      fs.writeFileSync(path.join(evidenceDir, 'live-ui-provenance-blocked.json'), JSON.stringify(evidence, null, 2));
      await page.screenshot({ path: path.join(evidenceDir, 'live-ui-provenance-blocked.png'), fullPage: true });
      assert.deepEqual(unexpectedBrowserErrors, [], 'The fail-closed provenance response must not cause unexpected browser errors.');
      console.log('[Test Live UI BLOCKED] ' + JSON.stringify(evidence));
      return;
    }
    assert.equal(firstInferenceResponse.status(), 200, inferenceBody);

    // Viewport canvas should load after inference completes
    await page.locator('#viewport').waitFor({ timeout: 120000 });
    await waitForAppState(page, snapshot => snapshot.case?.images?.some(
      image => image.laterality === 'L' && image.seen === true),
    { timeout: 30000, message: 'left synthetic image viewed' });

    const studyId = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.study_id;
    });
    createdStudyId = studyId;
    assert.ok(studyId, 'Study ID must be created');
    console.log('[Test Live UI] AI inference completed, viewer loaded study ' + studyId);

    const doctorToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const initialCaseResponse = await page.request.get(base + '/api/cases/' + studyId, {
      headers: { Authorization: 'Bearer ' + doctorToken },
    });
    assert.equal(initialCaseResponse.status(), 200);
    const initialCase = await initialCaseResponse.json();
    const leftPrediction = initialCase.images.find(image => image.laterality === 'L')?.prediction;
    const hasUncertaintyMap = Boolean(leftPrediction?.uncertainty_map_base64);
    if (await page.locator('#researchTab').count() > 0) await page.locator('#researchTab').click();
    await test_cdss_requires_a_saved_region_and_sends_no_defaults(page, browserRequests);
    const uncertaintyToggle = page.locator('#uncertaintyToggle');
    assert.equal(await uncertaintyToggle.isEnabled(), hasUncertaintyMap,
      'The entropy control must follow map availability: ' + await page.locator('#uncertaintyInfo').textContent());
    if (hasUncertaintyMap) {
      assert.match(await page.locator('#uncertaintyInfo').textContent(), /độ bất định.*khác với xác suất chẩn đoán/i);
      await uncertaintyToggle.check();
      assert.equal(await uncertaintyToggle.isChecked(), true);
      await uncertaintyToggle.uncheck();
      assert.equal(await uncertaintyToggle.isChecked(), false);
    }
    if (await page.locator('#clinicalTab').count() > 0) await page.locator('#clinicalTab').click();

    await page.locator('[data-action="side-R"]').click();
    await page.waitForFunction(() => document.querySelector('#sideLabel')?.textContent.includes('phải'));
    await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      window.__liveState = state;
    });
    let seenCheck;
    try {
      seenCheck = await page.waitForFunction(() =>
        window.__liveState.side === 'R' && window.__liveState.case?.images?.length === 2 &&
        window.__liveState.case.images.every(image => image.seen === true), null, { timeout: 10000 });
    } catch (error) {
      const viewerState = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          side: state.side,
          images: state.case.images.map(image => ({
            laterality: image.laterality,
            seen: image.seen,
            maskPixels: image.mask?.reduce((sum, value) => sum + value, 0),
            workerMeas: image.workerMeas ? { area: image.workerMeas.area, serial: image.workerMeas.serial } : null,
          })),
          editing: state.editing,
          workerLabel: document.querySelector('#sideLabel')?.textContent,
          saveDisabled: document.querySelector('[data-action="save-review"]')?.disabled,
        };
      });
      throw new Error(`${error.message}; viewerState=${JSON.stringify(viewerState)}; browserErrors=${JSON.stringify(errors)}`);
    }
    assert.equal(await seenCheck.jsonValue(), true);
    const reviewReadiness = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        disabled: document.querySelector('[data-action="save-review"]').disabled,
        readonly: document.querySelector('[data-action="save-review"]').disabled && !state.editing?.allowed,
        seen: state.case.images.map(image => ({ side: image.laterality, seen: image.seen })),
        activeSide: state.side,
        role: state.user?.role,
        editing: state.editing,
        capabilities: state.capabilities,
      };
    });
    assert.equal(await page.locator('[data-action="save-review"]').isEnabled(), true, JSON.stringify(reviewReadiness));
    assert.equal(await page.locator('[data-action="sign"]').isDisabled(), true,
      'Research-use-only mode must keep clinical sign-off unavailable');

    // Test clinical dot-phrase typing expansion (.nang1 + Space)
    await page.locator('#notes').fill('');
    await page.locator('#notes').pressSequentially('.nang1 ');
    const expandedNotes = await page.locator('#notes').inputValue();
    assert.match(expandedNotes, /Mô tả nang noãn: \[bác sĩ xác nhận/,
      'Dot-phrase .nang1 opens a neutral template requiring clinician completion');
    assert.doesNotMatch(expandedNotes, /O-RADS\s*\d/iu);
    const reviewBatchCountBeforePlaceholderSave = browserRequests.filter(request =>
      request.method === 'POST' && request.path === '/api/reviews/batch').length;
    await page.locator('[data-action="save-review"]').click();
    await page.locator('#toasts .toast').filter({ hasText: 'hoàn tất các chỗ trống' }).waitFor({ timeout: 5000 });
    assert.equal(await page.locator('#reviewContentWarning').isVisible(), true,
      'an unresolved dot-phrase must display the review warning');
    assert.equal(browserRequests.filter(request =>
      request.method === 'POST' && request.path === '/api/reviews/batch').length,
    reviewBatchCountBeforePlaceholderSave,
    'an unresolved dot-phrase must not reach the review API');

    // Complete the neutral template, then combine it with an HTML-like probe.
    const completedNotes = expandedNotes.replace(
      '[bác sĩ xác nhận kích thước, hình thái và bối cảnh]',
      'kích thước 24 mm, nội dung trống và thành mỏng trong dữ liệu tổng hợp',
    );
    await page.locator('#notes').fill(`${completedNotes}\nBác sĩ ghi nhận mô tả trên ảnh tổng hợp. <img src=x onerror=alert(1)>`);
    await page.locator('#notes').dispatchEvent('input');

    await page.evaluate(async id => {
      const { state } = await import('/static/app/state.js');
      state.queue = [id];
    }, studyId);
    await page.evaluate(() => {
      window.__reviewNextCaseDispatched = false;
      window.addEventListener('ova:next-case', () => {
        window.__reviewNextCaseDispatched = true;
      }, { once: true });
    });
    const batchResponseWait = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/reviews/batch', { timeout: 30000 });
    await page.locator('[data-action="save-review"]').click();
    const batchResponse = await batchResponseWait;
    assert.equal(batchResponse.status(), 200, await batchResponse.text());
    const batchBody = await batchResponse.json();
    assert.equal(batchBody.status, 'SUCCESS');
    assert.equal(batchBody.review_revision, 1);
    await waitForAppState(page, snapshot => snapshot.case?.status === 'REVIEWED' &&
      snapshot.case.review_revision > 0 && !snapshot.busy,
    { timeout: 30000, message: 'review persisted in frontend state' });
    await waitForAppState(page, snapshot => snapshot.case?.study_id === studyId &&
      snapshot.route === 'viewer' && !snapshot.busy,
    { timeout: 10000, message: 'viewer route restored after review' });
    await page.waitForFunction(() => window.__reviewNextCaseDispatched === true, null, { timeout: 10000 });

    const reviewedResponse = await page.request.get(base + '/api/cases/' + studyId, {
      headers: { Authorization: 'Bearer ' + doctorToken },
    });
    assert.equal(reviewedResponse.status(), 200);
    const reviewedStudy = await reviewedResponse.json();
    assert.equal(reviewedStudy.review_revision, 1, JSON.stringify({
      studyId,
      batchResponse: batchBody,
      status: reviewedStudy.status,
      review_revision: reviewedStudy.review_revision,
      reviews: reviewedStudy.images.map(image => Boolean(image.review)),
    }));
    assert.equal(reviewedStudy.images.length, 2);
    assert.ok(reviewedStudy.images.every(image => image.review?.doctor_id === 'doctor'));
    console.log('[Test Live UI] Bilateral research review persisted with doctor attribution.');

    await page.evaluate(() => { location.hash = '#cases'; });
    await waitForAppState(page, snapshot => snapshot.dom.hash === '#cases' &&
      snapshot.route === 'cases' && !snapshot.busy,
    { timeout: 15000, message: 'worklist navigation' });
    const navState = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        hash: location.hash,
        route: state.route,
        busy: state.busy,
        hasSearch: Boolean(document.querySelector('#caseSearch')),
        pageSnippet: document.querySelector('#page')?.innerText?.slice(0, 300) || '',
      };
    });
    console.log('[Test Live UI] Nav state after #cases:', JSON.stringify(navState));
    await page.locator('#caseSearch').waitFor();
    await page.locator('#caseSearch').fill(reviewedStudy.study_code);
    const gridState = await test_grid_reuses_filtered_rows_thumbnails_and_case_route(
      page, studyId, reviewedStudy, browserRequests,
    );
    await test_worklist_thumbnail_failure_recovers_after_refresh(
      page, studyId, reviewedStudy.images[0].image_id, reviewedStudy.study_code,
      doctorToken, browserRequests, errors, httpFailures,
    );
    gridState.writesBefore = clinicalWriteCount(browserRequests);
    await test_grid_display_never_marks_reviewed_or_bulk_signs(
      page, studyId, doctorToken, browserRequests, gridState,
    );
    const openCaseLink = page.locator(`#caseResults .worklist-grid-open[href="#viewer/${studyId}"]`);
    await openCaseLink.waitFor({ timeout: 15000 });
    await openCaseLink.click();
    await page.locator('#viewport').waitFor({ timeout: 30000 });
    await waitForAppState(page, snapshot => snapshot.case?.study_id === studyId &&
      snapshot.editing?.allowed === true,
    { timeout: 30000, message: 'worklist case lease acquired' });
    console.log('[Test Live UI] Worklist search reopened the persisted case under an active lease.');

    await page.evaluate(id => { location.hash = `#report/${id}`; }, studyId);
    await page.locator('#reportData .report').waitFor({ timeout: 30000 });
    assert.equal(await page.locator('#reportData .report-image-pair img').count(), 4);
    const reportText = await page.locator('#reportData .report').innerText();
    assert.match(reportText, /THÔNG TIN NGHIÊN CỨU RUO/i);
    assert.match(reportText, /Xác thực chữ ký số: ngoài phạm vi tài liệu này/i);
    assert.match(reportText, /Đơn vị hiển thị: pixel/i);
    assert.doesNotMatch(reportText, /Không dùng cho chăm sóc bệnh nhân|Chưa được xác thực lâm sàng|Không thay thế đánh giá của bác sĩ/i);
    await test_research_report_preview_renders_html_like_text_as_inert(page, reviewedStudy, browserRequests);
    await page.evaluate(() => {
      window.print = () => { window.__e2ePrintCalled = true; };
    });
    await page.locator('[data-action="print"]').click();
    await page.waitForFunction(() => window.__e2ePrintCalled === true);
    assert.equal(await page.locator('#printRoot .report').count(), 1);
    console.log('[Test Live UI] Report preview and browser print path remain research-only.');

    // Cleanup created study
    const authR = await page.request.post(base + '/api/auth/login', {
      data: { username: 'admin', password: adminPassword },
    });
    const auth = await authR.json();
    const deletion = await page.request.delete(base + '/api/cases/' + studyId, {
      headers: { Authorization: 'Bearer ' + auth.access_token },
    });
    assert.equal(deletion.status(), 200, 'Isolated E2E case cleanup must succeed');
    createdStudyId = null;

    assert.deepEqual(errors, [], JSON.stringify(httpFailures));
    assert.deepEqual(httpFailures, []);
    console.log('ALL TESTS PASSED: Email verification UI, provisioned login, manual AI trigger, bilateral segmentation & review!');
  } finally {
    let cleanupError = null;
    if (createdStudyId) {
      try {
        const authR = await page.request.post(base + '/api/auth/login', {
          data: { username: 'admin', password: adminPassword },
        });
        if (!authR.ok()) throw new Error(`Unable to authenticate cleanup for synthetic case ${createdStudyId}.`);
        const auth = await authR.json();
        const deletion = await page.request.delete(base + '/api/cases/' + createdStudyId, {
          headers: { Authorization: 'Bearer ' + auth.access_token },
        });
        if (deletion.status() !== 200 && deletion.status() !== 404)
          throw new Error(`Unable to clean synthetic case ${createdStudyId}: HTTP ${deletion.status()}.`);
        createdStudyId = null;
      } catch (error) {
        cleanupError = error;
      }
    }
    await server.close();
    if (cleanupError) throw cleanupError;
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
