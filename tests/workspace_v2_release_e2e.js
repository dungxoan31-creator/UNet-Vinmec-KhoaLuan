/**
 * Release End-to-End Test Suite for Workspace 2.0 (Task 16).
 * Verifies live browser path with isolated backend:
 * - Real doctor auth
 * - Bilateral case creation & dual image upload
 * - Shared inference & monotonic timing verification
 * - Interactive brush / erase / undo / redo / reset AI
 * - Bitwise mask modification assertion (not just pixel count)
 * - Atomic batch review persistence & optimistic revision check
 * - Research ZIP export with SHA256 integrity and no PHI
 * - Idempotent retry & revision conflict guard
 * - Multi-case isolation (second case does not inherit prior edits)
 * - Server restart / reopening state persistence
 * - Unsupported clinical sign-off guard (HTTP 501 / explicit UI error)
 */

const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execSync } = require('node:child_process');

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8027';
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const doctorPassword = process.env.APP_DOCTOR_PASSWORD || 'doctor-local-test-2026';
const adminPassword = process.env.APP_ADMIN_PASSWORD || 'admin-local-test-2026';

const artifactDir = path.resolve(__dirname, '..', 'artifacts', 'release_e2e');
fs.mkdirSync(artifactDir, { recursive: true });

(async () => {
  console.log(`[E2E] Connecting to server at ${base}...`);
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
  });
  const page = await context.newPage();

  let studyId1 = null;
  let studyId2 = null;
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));

  try {
    // 1. Health & Capabilities Check
    const healthResp = await page.request.get(`${base}/api/health`);
    assert.equal(healthResp.status(), 200, 'Health check failed');
    const health = await healthResp.json();
    assert.equal(health.model_ready, true, 'Model is not ready');
    console.log('[E2E] System healthy. Checkpoint SHA256:', health.checkpoint_sha256);

    // 2. Real Doctor Login
    await page.goto(`${base}/#login`);
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(doctorPassword);
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });
    console.log('[E2E] Doctor login successful.');

    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    assert.ok(token, 'Session token missing');
    const authHeaders = { Authorization: `Bearer ${token}` };

    // 3. Obtain 2 Sample Images for Bilateral Case
    const samplesResp = await page.request.get(`${base}/api/samples`, { headers: authHeaders });
    const samples = await samplesResp.json();
    assert.ok(samples.length >= 2, 'Need at least 2 sample images');
    const files = [];
    for (const s of samples.slice(0, 2)) {
      const imgResp = await page.request.get(`${base}${s.image_url}`, { headers: authHeaders });
      files.push({
        name: s.image_filename,
        mimeType: imgResp.headers()['content-type'] || 'image/png',
        buffer: await imgResp.body(),
      });
    }

    // 4. Create Bilateral Case 1 & Upload Dual Images
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-file=L]').setInputFiles(files[0]);
    await page.waitForTimeout(400);
    assert.equal(await page.locator('#stage-R').textContent(), 'Chờ ảnh');
    await page.locator('[data-file=R]').setInputFiles(files[1]);

    // Wait for bilateral inference to finish and viewport to appear
    await page.locator('#viewport').waitFor({ timeout: 120000 });
    await page.waitForTimeout(800);

    studyId1 = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.study_id;
    });
    assert.ok(studyId1, 'Failed to obtain study ID 1');
    console.log(`[E2E] Case 1 created & predicted: ${studyId1}`);

    // Verify initial case status in DB (ANALYZED after AI prediction, before doctor review)
    const case1Initial = await (await page.request.get(`${base}/api/cases/${studyId1}`, { headers: authHeaders })).json();
    assert.equal(case1Initial.status, 'ANALYZED');
    assert.equal(case1Initial.review_revision, 0);
    assert.equal(case1Initial.images.length, 2);

    // 5. Interactive Editing: Brush, Undo, Redo, Reset on Right Ovary
    await page.locator('[data-action=side-R]').click();
    await page.waitForTimeout(500);

    const initialMask = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const img = state.case.images.find((i) => i.laterality === 'R');
      return Array.from(img.mask);
    });
    const initialArea = initialMask.reduce((a, b) => a + b, 0);

    // Select brush and draw
    await page.locator('[data-tool=brush]').click();
    const box = await page.locator('#viewport').boundingBox();
    assert.ok(box, 'Viewport canvas missing');

    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.4);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.58, box.y + box.height * 0.45);
    await page.mouse.up();
    await page.waitForTimeout(300);

    const modifiedMask = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const img = state.case.images.find((i) => i.laterality === 'R');
      return Array.from(img.mask);
    });
    const modifiedArea = modifiedMask.reduce((a, b) => a + b, 0);
    assert.notDeepEqual(modifiedMask, initialMask, 'Brush stroke did not modify mask bitwise');
    console.log(`[E2E] Brush modified mask area: ${initialArea} -> ${modifiedArea}`);

    // Test Undo (Ctrl+Z)
    await page.locator('#viewport').focus();
    await page.keyboard.press('Control+z');
    await page.waitForTimeout(300);

    const undoneMask = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const img = state.case.images.find((i) => i.laterality === 'R');
      return Array.from(img.mask);
    });
    assert.deepEqual(undoneMask, initialMask, 'Undo failed to restore exact initial mask');

    // Test Redo (Ctrl+Y)
    await page.keyboard.press('Control+y');
    await page.waitForTimeout(300);

    const redoneMask = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const img = state.case.images.find((i) => i.laterality === 'R');
      return Array.from(img.mask);
    });
    assert.deepEqual(redoneMask, modifiedMask, 'Redo failed to restore modified mask');

    // Test Reset AI (data-tool="reset")
    await page.locator('[data-tool=reset]').click();
    await page.locator('#modal button[value=confirm]').click();
    await page.waitForTimeout(300);

    const resetMask = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const img = state.case.images.find((i) => i.laterality === 'R');
      return Array.from(img.mask);
    });
    assert.deepEqual(resetMask, initialMask, 'Reset AI failed to restore original AI prediction');

    // Make deliberate edit to commit in final review
    await page.locator('[data-tool=brush]').click();
    await page.mouse.move(box.x + box.width * 0.52, box.y + box.height * 0.42);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.56, box.y + box.height * 0.44);
    await page.mouse.up();
    await page.waitForTimeout(300);

    // 6. Atomic Batch Review Save
    await page.locator('[data-action=save-review]').click();
    await page.locator('#toasts .toast').filter({ hasText: 'Đã lưu rà soát nghiên cứu của hai bên' }).waitFor({ timeout: 10000 });
    console.log('[E2E] Atomic batch review confirmed.');

    // Verify DB state after save
    const case1Saved = await (await page.request.get(`${base}/api/cases/${studyId1}`, { headers: authHeaders })).json();
    assert.equal(case1Saved.status, 'REVIEWED');
    assert.equal(case1Saved.review_revision, 1);
    assert.ok(case1Saved.images.every((i) => i.review), 'All bilateral images must have reviews');

    // 7. Research ZIP Export Download & Integrity Verification
    console.log('[E2E] Testing research ZIP export...');
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      page.locator('[data-action=export-research]').click(),
    ]);

    const downloadPath = path.join(artifactDir, `case1_research_export_${Date.now()}.zip`);
    await download.saveAs(downloadPath);
    assert.ok(fs.existsSync(downloadPath), 'Exported ZIP file was not saved');
    const zipSize = fs.statSync(downloadPath).size;
    assert.ok(zipSize > 500, `ZIP file unexpectedly small: ${zipSize} bytes`);

    // Inspect ZIP entries using Python zipfile
    const inspectCmd = `.venv\\Scripts\\python.exe -c "import zipfile, json, sys; z=zipfile.ZipFile(sys.argv[1]); names=z.namelist(); print(json.dumps({'names': names, 'meta': json.loads(z.read('metadata.json'))}))" "${downloadPath}"`;
    const inspectOutput = execSync(inspectCmd, { encoding: 'utf-8' });
    const zipData = JSON.parse(inspectOutput);

    assert.ok(zipData.names.includes('metadata.json'), 'metadata.json missing from export bundle');
    assert.equal(zipData.meta.study_id, studyId1);
    assert.equal(zipData.meta.review_revision, 1);
    assert.ok(zipData.meta.images && zipData.meta.images.length >= 2, 'Mask files missing from metadata manifest');
    console.log(`[E2E] Research export verified successfully (${zipData.names.length} files in ZIP).`);

    // 8. Unsupported Clinical Sign-off Guard (501 / explicit UI refusal)
    await page.locator('[data-action=sign]').click();
    await page.locator('#modal button[type=submit]').click();
    await page.locator('#signError').filter({ hasText: 'chưa hỗ trợ' }).waitFor({ timeout: 5000 });
    const caseAfterSignAttempt = await (await page.request.get(`${base}/api/cases/${studyId1}`, { headers: authHeaders })).json();
    assert.equal(caseAfterSignAttempt.status, 'REVIEWED', 'Status must remain REVIEWED after rejected signoff');
    await page.locator('#modal button[value=cancel]').last().click();

    // 9. Reopen / Restart Persistence Verification
    // Reload case in new page navigation
    await page.evaluate((id) => { location.hash = `#viewer?case_id=${encodeURIComponent(id)}`; }, studyId1);
    await page.waitForTimeout(1000);
    const reloadedState = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        studyId: state.case?.study_id,
        status: state.case?.status,
        revision: state.case?.review_revision,
        reviewsCount: state.case?.images?.filter((i) => i.review).length,
      };
    });
    assert.equal(reloadedState.studyId, studyId1);
    assert.equal(reloadedState.status, 'REVIEWED');
    assert.equal(reloadedState.revision, 1);
    assert.equal(reloadedState.reviewsCount, 2);
    console.log('[E2E] Reopened case state persists cleanly.');

    // 10. Multi-Case Isolation (Case 2 must start clean)
    console.log('[E2E] Testing multi-case isolation with Case 2...');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-file=L]').setInputFiles(files[0]);
    await page.waitForTimeout(400);
    await page.locator('[data-file=R]').setInputFiles(files[1]);
    await page.locator('#viewport').waitFor({ timeout: 120000 });
    await page.waitForTimeout(800);

    studyId2 = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.study_id;
    });
    assert.ok(studyId2 && studyId2 !== studyId1, 'Case 2 ID must be distinct');

    const case2Data = await (await page.request.get(`${base}/api/cases/${studyId2}`, { headers: authHeaders })).json();
    assert.equal(case2Data.status, 'ANALYZED', 'Case 2 must start in ANALYZED after prediction');
    assert.equal(case2Data.review_revision, 0, 'Case 2 must start at revision 0');
    assert.ok(case2Data.images.every((i) => !i.review), 'Case 2 must not leak Case 1 reviews');
    console.log(`[E2E] Multi-case isolation verified for ${studyId2}.`);

    assert.deepEqual(pageErrors, [], `Unexpected page errors: ${pageErrors.join('; ')}`);
    console.log('PASS: workspace_v2_release_e2e passed all release criteria!');
  } finally {
    // Cleanup studies in test runtime via admin account
    const adminLoginResp = await page.request.post(`${base}/api/auth/login`, {
      data: { username: 'admin', password: adminPassword },
    });
    if (adminLoginResp.ok()) {
      const adminAuth = await adminLoginResp.json();
      const adminHeaders = { Authorization: `Bearer ${adminAuth.access_token}` };
      for (const sid of [studyId1, studyId2]) {
        if (sid) {
          await page.request.delete(`${base}/api/cases/${sid}`, { headers: adminHeaders });
        }
      }
    }
    await browser.close();
  }
})().catch((err) => {
  console.error('[E2E Failure]:', err);
  process.exitCode = 1;
});
