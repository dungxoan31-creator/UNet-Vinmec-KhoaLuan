/**
 * End-to-End Browser verification of newly implemented UI/UX features:
 * 1. Account registration flow (#register)
 * 2. 1-click quick-login buttons on #login
 * 3. Manual AI activation button (#startSegmentationBtn) on #intake
 * 4. Full segmentation, measurements, and viewer loading
 */

const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const path = require('node:path');

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  console.log('[Test Live UI] Starting browser verification on ' + base + '...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));

  try {
    // ==========================================
    // 1. Verify Login Screen & Quick Login buttons
    // ==========================================
    await page.goto(base + '/#login');
    await page.locator('#authForm').waitFor({ timeout: 10000 });
    assert.equal(await page.locator('[data-action=quick-bs]').count(), 1, 'Quick BS button must exist');
    assert.equal(await page.locator('[data-action=quick-admin]').count(), 1, 'Quick Admin button must exist');

    // ==========================================
    // 2. Test Account Registration
    // ==========================================
    const regLink = page.locator('a[href="#register"]');
    assert.equal(await regLink.count(), 1, 'Register link must exist on login page');
    await regLink.click();
    await page.waitForTimeout(400);

    assert.equal(await page.locator('h2').textContent(), 'Đăng ký tài khoản bác sĩ');
    assert.equal(await page.locator('[name=full_name]').count(), 1);
    assert.equal(await page.locator('[name=department]').count(), 1);

    // Test form mismatch validation
    const testUsername = 'dr_test_' + Date.now().toString().slice(-5);
    await page.locator('[name=username]').fill(testUsername);
    await page.locator('[name=full_name]').fill('BS.CKI Kiểm Thử Giao Diện');
    await page.locator('[name=password]').fill('StrongPass123!');
    await page.locator('[name=confirm]').fill('MismatchPass456!');
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForTimeout(300);
    assert.equal(await page.locator('#authError').textContent(), 'Hai mật khẩu chưa trùng khớp.');

    // Fix password match and submit valid registration
    await page.locator('[name=confirm]').fill('StrongPass123!');
    await page.locator('#authForm button[type=submit]').click();

    // Verify successful registration logs in directly to #dashboard
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });
    console.log('[Test Live UI] Registration successful for ' + testUsername);

    // Verify user name in topbar
    const accountName = await page.locator('.account-name').textContent();
    assert.equal(accountName, 'BS.CKI Kiểm Thử Giao Diện');

    // ==========================================
    // 3. Test Logout & Login with Registered Account
    // ==========================================
    await page.evaluate(() => {
      // Trigger logout via hash or state
      sessionStorage.removeItem('ova.token');
      location.hash = '#login';
    });
    await page.goto(base + '/#login');
    await page.locator('#authForm').waitFor();

    await page.locator('[name=username]').fill(testUsername);
    await page.locator('[name=password]').fill('StrongPass123!');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });
    console.log('[Test Live UI] Login with new registered account verified.');

    // ==========================================
    // 4. Test 1-Click Quick Login
    // ==========================================
    await page.evaluate(() => {
      sessionStorage.removeItem('ova.token');
      location.hash = '#login';
    });
    await page.goto(base + '/#login');
    await page.locator('[data-action=quick-bs]').click();
    await page.locator('h1').filter({ hasText: 'Tổng quan' }).waitFor({ timeout: 10000 });
    console.log('[Test Live UI] 1-Click quick login as Doctor verified.');

    // ==========================================
    // 5. Test Intake & Manual AI Activation Button
    // ==========================================
    await page.evaluate(() => { location.hash = '#intake'; });
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
    // Button must now be enabled
    assert.equal(await page.locator('#startSegmentationBtn').isEnabled(), true);
    console.log('[Test Live UI] startSegmentationBtn enabled after dual images selected.');

    // Click the manual activation button
    await page.locator('#startSegmentationBtn').click();
    console.log('[Test Live UI] Clicked startSegmentationBtn, waiting for bilateral inference...');

    // Viewport canvas should load after inference completes
    await page.locator('#viewport').waitFor({ timeout: 120000 });
    await page.waitForTimeout(1000);

    const studyId = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.study_id;
    });
    assert.ok(studyId, 'Study ID must be created');
    console.log('[Test Live UI] AI inference completed, viewer loaded study ' + studyId);

    // Cleanup created study
    const adminPassword = process.env.APP_ADMIN_PASSWORD || 'admin-local-test-2026';
    const authR = await page.request.post(base + '/api/auth/login', {
      data: { username: 'admin', password: adminPassword },
    });
    const auth = await authR.json();
    await page.request.delete(base + '/api/cases/' + studyId, {
      headers: { Authorization: 'Bearer ' + auth.access_token },
    });

    assert.deepEqual(errors, []);
    console.log('ALL TESTS PASSED: Registration, 1-Click login, manual AI trigger, bilateral segmentation & review!');
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
