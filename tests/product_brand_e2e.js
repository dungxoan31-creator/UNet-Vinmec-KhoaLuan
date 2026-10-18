const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright-core');

const screenshotDir = 'reports/comprehensive-system-test-2026-10-18/product-brand';
fs.mkdirSync(screenshotDir, { recursive: true });

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
      await page.screenshot({path:`${screenshotDir}/login-${width}.png`, fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(process.env.APP_DOCTOR_PASSWORD || 'doctor-local-test-2026');
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('#dashData .metrics').waitFor();
    assert.doesNotMatch(await page.locator('body').innerText(), /demo|minh họa|bản mẫu|thử nghiệm/i);
    await page.screenshot({path:`${screenshotDir}/dashboard.png`,fullPage:true});
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const response = await page.request.get(base + '/api/samples', {headers:{Authorization:'Bearer '+token}});
    assert.equal(response.status(), 200);
    assert.deepEqual(await response.json(), []);
    assert.equal((await page.request.get(base+'/static/app/demo.js')).status(),404);
    await page.evaluate(() => location.hash = '#intake');
    await page.locator('[data-select]').first().waitFor();
    assert.equal(await page.locator('[data-select]').count(), 4);
    await page.locator('[data-select]').first().click();
    await page.locator('[data-file=L]').waitFor();
    assert.equal(await page.locator('[name=participant_code], [name=participant_role]').count(),0);
    assert.match(await page.locator('body').innerText(), /Nguyễn Minh Anh/);
    await page.locator('[data-action=change-patient]').click();
    await page.locator('[data-action=add-patient]').click();
    const patientForm = page.locator('#modal form');
    await patientForm.waitFor();
    for (const name of ['full_name', 'birth_year', 'phone', 'gender', 'hometown']) {
      assert.equal(await patientForm.locator(`[name=${name}]`).count(), 1);
    }
    await patientForm.locator('[name=full_name]').fill('Nguyễn Thị Kiểm Thử');
    await patientForm.locator('[name=birth_year]').fill('1990');
    await patientForm.locator('[name=phone]').fill('abc');
    await patientForm.locator('[name=gender]').selectOption('female');
    await patientForm.locator('[name=hometown]').fill('Hà Nội');
    await patientForm.locator('button[type=submit]').click();
    await page.locator('[data-patient-error]').waitFor();
    assert.match(await page.locator('[data-patient-error]').innerText(), /số điện thoại/i);
    await patientForm.locator('[name=phone]').fill('0912345678');
    await patientForm.locator('button[type=submit]').click();
    await page.locator('[data-file=L]').waitFor();
    assert.match(await page.locator('body').innerText(), /Nguyễn Thị Kiểm Thử/);
    assert.match(await page.locator('body').innerText(), /PID/);
    const createdPatient = await page.evaluate(() => {
      const patients = JSON.parse(localStorage.getItem('ova.demo-patients.v1'));
      return patients.find(patient => patient.name === 'Nguyễn Thị Kiểm Thử');
    });
    assert.equal(createdPatient.birth_year, 1990);
    assert.equal(createdPatient.age, new Date().getFullYear() - 1990);
    assert.equal(createdPatient.phone, '0912345678');
    assert.equal(createdPatient.gender, 'female');
    assert.equal(createdPatient.hometown, 'Hà Nội');
    await page.screenshot({path:`${screenshotDir}/intake-new-patient.png`,fullPage:true});
    assert.deepEqual(errors, []);
    console.log('PASS: local Vinmec logo/Inter/colors, responsive login, real authentication, dashboard/intake and retired sample catalog');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
