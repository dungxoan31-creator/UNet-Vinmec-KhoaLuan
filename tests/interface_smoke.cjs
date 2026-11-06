const assert = require('node:assert/strict');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
(async () => {
  const server = await startIsolatedBrowser();
  try {
    const page = await server.browser.newPage();
    const errors = [];
    page.on('pageerror', error => { errors.push(error.message); console.error(error.message); });
    await page.goto(server.base + '/#login');
    await page.locator('#authForm [name=username]').fill('doctor');
    await page.locator('#authForm [name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('.intake-patient-list').waitFor();
    assert.equal(await page.locator('[data-select]').count(), 0, 'Normal intake must not show generated patients');
    assert.equal(errors.length, 0);
    console.log('PASS: login, dashboard and normal intake excludes synthetic patients');
  } finally { await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
