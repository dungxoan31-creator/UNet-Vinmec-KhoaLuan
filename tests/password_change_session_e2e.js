const assert = require('node:assert/strict');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

(async () => {
  const isolated = await startIsolatedBrowser();
  try {
    const page = await isolated.browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${isolated.base}/#login`);
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(isolated.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => { location.hash = '#profile'; });
    await page.locator('[data-action=change-password]').click();

    const oldToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    await page.locator('#modal [name=current_password]').fill(isolated.password);
    await page.locator('#modal [name=new_password]').fill('SyntheticNewPassword2026!');
    await page.locator('#modal [name=confirmation]').fill('SyntheticNewPassword2026!');
    await page.locator('#modal button[type=submit]').click();
    await page.locator('#modal').waitFor({ state: 'hidden' });

    const newToken = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    assert.ok(newToken && newToken !== oldToken, 'password change must replace the active token');
    const currentUser = await page.evaluate(async token => {
      const response = await fetch('/api/auth/current-user', {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: response.status, body: response.ok ? await response.json() : null };
    }, newToken);
    assert.equal(currentUser.status, 200);
    assert.equal(currentUser.body.username, 'doctor');
    console.log('PASS: new password token is active for the next authenticated request');
  } finally {
    await isolated.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
