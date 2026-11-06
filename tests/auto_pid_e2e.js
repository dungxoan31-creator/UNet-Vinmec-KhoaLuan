/* Verify that normal intake creates facility-directory records without inventing patient IDs. */
const assert = require('node:assert/strict');
const {startIsolatedBrowser} = require('./helpers/isolated_browser.cjs');

(async () => {
  const server = await startIsolatedBrowser();
  try {
    const page = await server.browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(server.base + '/#login');
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => {location.hash = '#intake';});
    await page.locator('.intake-patient-list').waitFor();
    assert.equal(await page.locator('[data-select]').count(), 0);
    assert.equal(await page.locator('[name=pid]').count(), 0);
    assert.equal(await page.locator('body').innerText().then(text => /100000001|900000001/.test(text)), false);
    await page.locator('[data-action=add-patient]').click();
    assert.equal(await page.locator('#modal [name=pid]').count(), 0);
    assert.equal(await page.locator('#modal [name=phone]').count(), 0);
    assert.equal(await page.locator('#modal [name=national_id]').count(), 0);
    assert.equal(await page.locator('#modal [name=birth_year]').evaluate(input => input.required), false);
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('PASS: empty facility directory, no fake PID, no redundant identity fields, and optional birth year.');
  } finally {await server.close();}
})().catch(error => {console.error(error.stack || error); process.exitCode = 1;});
