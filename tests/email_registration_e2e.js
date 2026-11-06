const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8027';
const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('requestfailed', (request) => errors.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`));
  try {
    await page.goto(`${base}/#login`);
    await page.locator('#authForm').waitFor();
    assert.equal(await page.locator('[data-action^="quick-"]').count(), 0);
    assert.doesNotMatch(await page.locator('body').innerText(), /doctor-local-test-2026|admin-local-test-2026/);

    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }

    await page.route('**/api/auth/register', async (route) => {
      const body = route.request().postDataJSON();
      assert.equal(body.role, 'DOCTOR');
      assert.equal(body.email, 'doctor@example.org');
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'PENDING_EMAIL_VERIFICATION',
          email: body.email,
          email_verification_required: true,
        }),
      });
    });
    await page.route('**/api/auth/resend-verification', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ACCEPTED' }),
      });
    });
    await page.route('**/api/auth/verify-email', async (route) => {
      const body = route.request().postDataJSON();
      if (body.code === '000000') {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Verification request is invalid or expired.' }),
        });
        return;
      }
      assert.deepEqual(body, { email: 'doctor@example.org', code: '123456' });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'VERIFIED', email_verified: true, activation_pending: true }),
      });
    });

    await page.locator('a[href="#register"]').click();
    await page.locator('h2').filter({ hasText: 'Đăng ký tài khoản bác sĩ' }).waitFor();
    await page.locator('[name=username]').fill('doctor-test');
    await page.locator('[name=full_name]').fill('Doctor Test');
    await page.locator('[name=email]').fill('doctor@example.org');
    await page.locator('[name=department]').fill('Imaging');
    await page.locator('[name=password]').fill('StrongPass123!');
    await page.locator('[name=confirm]').fill('StrongPass123!');
    await page.locator('#authForm button[type=submit]').click();
    try {
      await page.locator('h2').filter({ hasText: 'Xác minh email' }).waitFor({ timeout: 5000 });
    } catch {
      throw new Error(`Registration did not advance: hash=${await page.evaluate(() => location.hash)}, error=${await page.locator('#authError').textContent()}, heading=${await page.locator('h2').textContent()}, errors=${errors.join('; ')}`);
    }
    assert.equal(await page.locator('[name=email]').inputValue(), 'doctor@example.org');
    assert.equal(await page.locator('[name=code]').count(), 1);
    assert.equal(await page.locator('input[name=email]').getAttribute('type'), 'email');

    await page.locator('#resendVerification').click();
    await page.locator('[name=code]').fill('000000');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('.form-error').filter({ hasText: 'invalid or expired' }).waitFor();
    assert.equal(await page.locator('h2').textContent(), 'Xác minh email');

    await page.locator('[name=code]').fill('123456');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('h2').filter({ hasText: 'Đăng nhập hệ thống' }).waitFor();
    assert.match(await page.locator('body').innerText(), /quản trị viên cần duyệt tài khoản/i);
    assert.equal(await page.evaluate(() => sessionStorage.getItem('ova.token')), null);
    assert.deepEqual(errors, []);
    console.log('PASS: registration, email verification, resend, failure state, responsive layout, and no embedded credentials');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
