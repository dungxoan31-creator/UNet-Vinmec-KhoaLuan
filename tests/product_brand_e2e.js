const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8027';
  try {
    await page.goto(base + '/#login');
    await page.locator('#authForm').waitFor();
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('[data-action^=demo]').count(), 0);
    assert.doesNotMatch(await page.locator('body').innerText(), /demo|minh họa|bản mẫu|thử nghiệm/i);
    const branding = await page.evaluate(() => ({
      font: getComputedStyle(document.body).fontFamily,
      primary: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
      fontLoaded: document.fonts.check('14px Inter'),
      logo: document.querySelector('.vinmec-logo').naturalWidth,
    }));
    assert.match(branding.font, /^Inter/);
    assert.equal(branding.primary, '#0076c0');
    assert.equal(branding.fontLoaded, true);
    assert.ok(branding.logo > 0);
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({width, height:900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path:`artifacts/product-cleanup/login-${width}.png`, fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(process.env.APP_DOCTOR_PASSWORD || 'doctor-local-test-2026');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('#dashData .metrics').waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), /demo|minh họa|bản mẫu|thử nghiệm/i);
    await page.screenshot({path:'artifacts/product-cleanup/dashboard.png',fullPage:true});
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const response = await page.request.get(base + '/api/samples', {headers:{Authorization:'Bearer '+token}});
    assert.equal(response.status(), 200);
    assert.deepEqual(await response.json(), []);
    assert.equal((await page.request.get(base+'/static/app/demo.js')).status(),404);
    await page.evaluate(() => location.hash = '#intake');
    await page.locator('[data-file=L]').waitFor();
    assert.equal(await page.locator('[name=participant_code], [name=participant_role]').count(),0);
    await page.screenshot({path:'artifacts/product-cleanup/intake.png',fullPage:true});
    assert.deepEqual(errors, []);
    console.log('PASS: local Vinmec logo/Inter/colors, responsive login, real authentication, dashboard/intake and retired sample catalog');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
