const assert = require('node:assert/strict');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

(async () => {
  const isolated = await startIsolatedBrowser();
  try {
    const page = await isolated.browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${isolated.base}/#login`);
    await page.locator('[name=username]').fill('admin');
    await page.locator('[name=password]').fill(isolated.adminPassword);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard' || location.hash === '#admin');
    await page.evaluate(() => { location.hash = '#admin/users'; });
    const row = page.locator('tr').filter({ hasText: 'dungnh' });
    await row.waitFor();
    assert.match(await row.innerText(), /Nguyễn Hữu Dũng \(tổng hợp\)/);
    console.log('PASS: synthetic doctor name and username displayed from isolated API');
  } finally {
    await isolated.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
