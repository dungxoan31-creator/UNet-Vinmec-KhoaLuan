const assert = require('node:assert/strict');
const fs = require('node:fs');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

const screenshotDir = 'reports/comprehensive-system-test-2026-10-18/product-brand';
fs.mkdirSync(screenshotDir, { recursive: true });

(async () => {
  const isolated = await startIsolatedBrowser();
  const { browser, base, password } = isolated;
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '/#login');
    await page.locator('#authForm').waitFor();
    await page.evaluate(() => document.fonts.ready);
    const safetyBanner = page.locator('.ruo-safety-banner');
    assert.equal(await safetyBanner.isVisible(), true, 'The RUO notice must be visible before sign-in.');
    assert.equal((await safetyBanner.innerText()).replace(/\s+/g, ' ').trim(),
      'BẢN NGHIÊN CỨU (RUO) — Chưa được phê duyệt lâm sàng — Không dùng cho quyết định điều trị');
    assert.equal(await page.locator('[data-action^=demo]').count(), 0);
    assert.doesNotMatch(await page.locator('body').innerText(), /demo|minh họa|bản mẫu|thử nghiệm/i);
    const branding = await page.evaluate(() => ({
      font: getComputedStyle(document.body).fontFamily,
      primary: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
      fontLoaded: document.fonts.check('14px Inter'),
      logo: document.querySelector('.vinmec-logo').naturalWidth,
    }));
    assert.match(branding.font, /^Inter/);
    assert.equal(branding.primary, '#187DBB');
    assert.equal(branding.fontLoaded, true);
    assert.ok(branding.logo > 0);
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({width, height:900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const bannerLayout = await safetyBanner.evaluate(element => {
        const rect = element.getBoundingClientRect();
        return { height: rect.height, clientWidth: element.clientWidth, scrollWidth: element.scrollWidth };
      });
      assert.equal(bannerLayout.height, width <= 640 ? 48 : 32, JSON.stringify(bannerLayout));
      assert.ok(bannerLayout.scrollWidth <= bannerLayout.clientWidth, JSON.stringify(bannerLayout));
      const passwordGeometry = await page.evaluate(() => {
        const input = document.querySelector('#authForm [name=password]').getBoundingClientRect();
        const button = document.querySelector('#showPassword').getBoundingClientRect();
        return { delta: Math.abs((input.top + input.bottom - button.top - button.bottom) / 2),
          buttonTop: button.top, buttonBottom: button.bottom, inputTop: input.top, inputBottom: input.bottom };
      });
      assert.ok(passwordGeometry.delta <= 1, JSON.stringify(passwordGeometry));
      await page.screenshot({path:`${screenshotDir}/login-${width}.png`, fullPage:true});
    }
    await page.locator('#showPassword').click();
    assert.equal(await page.locator('#authForm [name=password]').getAttribute('type'), 'text');
    await page.locator('#showPassword').click();
    assert.equal(await page.locator('#authForm [name=password]').getAttribute('type'), 'password');
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(password);
    await page.locator('#authForm button[type=submit]').click();
    await page.locator('#dashData .metrics').waitFor();
    assert.match(await page.locator('.statusbar').innerText(), /RUO · Không dùng cho quyết định điều trị/i);
    await page.evaluate(() => { location.hash = '#evaluation'; });
    await page.waitForFunction(() => location.hash === '#dashboard');
    assert.equal(await page.locator('#evaluationData').count(), 0,
      'A physician without reviewer privileges must be redirected before evaluation content loads.');
    await page.locator('#collapseNav').click();
    assert.ok(await page.getByRole('link', {name: 'Tùy chọn'}).isVisible(),
      'Collapsed navigation must retain an accessible name for preferences');
    await page.locator('#collapseNav').click();
    assert.doesNotMatch(await page.locator('body').innerText(), /demo|minh họa|bản mẫu|thử nghiệm/i);
    await page.screenshot({path:`${screenshotDir}/dashboard.png`,fullPage:true});
    const token = await page.evaluate(() => sessionStorage.getItem('ova.token'));
    const response = await page.request.get(base + '/api/samples', {headers:{Authorization:'Bearer '+token}});
    assert.equal(response.status(), 200);
    assert.deepEqual(await response.json(), []);
    assert.equal((await page.request.get(base+'/static/app/demo.js')).status(),404);
    await page.evaluate(() => location.hash = '#intake');
    await page.locator('.intake-patient-list').waitFor();
    assert.equal(await page.locator('[data-select]').count(), 0);
    assert.match(await page.locator('body').innerText(), /Chưa có hồ sơ trong danh bạ/);
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-action=anonymous-study]').click();
    await page.locator('[data-file=L]').waitFor();
    const leftUpload = await page.locator('.upload-card.side-L').boundingBox();
    const rightUpload = await page.locator('.upload-card.side-R').boundingBox();
    assert.ok(rightUpload.y >= leftUpload.y + leftUpload.height - 1, 'Bilateral upload panels stack on mobile');
    for (const viewport of [{width:1366,height:768},{width:1440,height:900},{width:390,height:844}]) {
      await page.setViewportSize(viewport);
      const actionBar = page.locator('.intake-action-bar');
      await actionBar.scrollIntoViewIfNeeded();
      const layout = await page.evaluate(() => {
        const rect = element => {
          const box = element.getBoundingClientRect();
          return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width, height: box.height };
        };
        const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
        const bar = document.querySelector('.intake-action-bar');
        const date = document.querySelector('[name="study-date"]');
        const status = document.querySelector('.statusbar');
        const action = document.querySelector('#startSegmentationBtn');
        const barRect = rect(bar);
        const overlappedSections = [...document.querySelectorAll('.intake-workspace > *:not(.intake-action-bar)')]
          .filter(element => getComputedStyle(element).display !== 'none' && overlaps(barRect, rect(element)))
          .map(element => element.id || element.className || element.tagName);
        return {
          innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          date: rect(date),
          bar: rect(bar),
          button: rect(action),
          status: rect(status),
          overlappedSections,
          dateBarOverlap: overlaps(rect(date), rect(bar)),
          statusBarOverlap: overlaps(rect(status), rect(bar)),
        };
      });
      assert.ok(layout.documentWidth <= viewport.width, JSON.stringify(layout));
      assert.ok(layout.date.left >= 0 && layout.date.right <= viewport.width, JSON.stringify(layout));
      assert.ok(layout.date.width >= 230, JSON.stringify(layout));
      assert.ok(layout.bar.left >= 0 && layout.bar.right <= viewport.width, JSON.stringify(layout));
      assert.ok(layout.button.height >= 44, JSON.stringify(layout));
      assert.equal(layout.dateBarOverlap, false, JSON.stringify(layout));
      assert.equal(layout.statusBarOverlap, false, JSON.stringify(layout));
      assert.deepEqual(layout.overlappedSections, [], JSON.stringify(layout));
      await page.screenshot({path:`${screenshotDir}/intake-layout-${viewport.width}x${viewport.height}.png`,fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    const lightLaterality = {};
    for (const side of ['L', 'R']) {
      const badge = page.locator(`.upload-card .badge.side-${side}`);
      assert.equal(await badge.count(), 1);
      assert.equal(await badge.getAttribute('style'), null);
      lightLaterality[side] = await badge.evaluate(element => {
        const style = getComputedStyle(element);
        return {background: style.backgroundColor, color: style.color};
      });
    }
    await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
    for (const side of ['L', 'R']) {
      const darkLaterality = await page.locator(`.upload-card .badge.side-${side}`).evaluate(element => {
        const style = getComputedStyle(element);
        return {background: style.backgroundColor, color: style.color};
      });
      assert.notEqual(darkLaterality.background, lightLaterality[side].background);
      assert.notEqual(darkLaterality.color, lightLaterality[side].color);
    }
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    await page.setViewportSize({width:390,height:844});
    const mobileLayout = await page.evaluate(() => {
      const elements = [document.documentElement, document.body, ...document.querySelectorAll('body *')];
      const overflow = elements
        .map(element => {
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return {
            tag: element.tagName,
            id: element.id,
            className: typeof element.className === 'string' ? element.className : '',
            left: rect.left,
            right: rect.right,
            width: rect.width,
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
            boxSizing: style.boxSizing,
            minWidth: style.minWidth,
          };
        })
        .filter(element => element.right > innerWidth + 0.5 || element.left < -0.5 || element.scrollWidth > element.clientWidth + 1)
        .sort((first, second) => second.right - first.right)
        .slice(0, 8);
      return {
        innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        documentClientWidth: document.documentElement.clientWidth,
        bodyWidth: document.body.scrollWidth,
        bodyClientWidth: document.body.clientWidth,
        overflow,
      };
    });
    assert.ok(mobileLayout.documentWidth <= mobileLayout.innerWidth, JSON.stringify(mobileLayout));
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-action=change-patient]').click();
    await page.locator('.intake-patient-list').waitFor();
    const tableLayout = await page.evaluate(() => {
      const region = document.querySelector('.intake-patient-list');
      const box = region.getBoundingClientRect();
      return {
        innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        left: box.left,
        right: box.right,
        clientWidth: region.clientWidth,
        scrollWidth: region.scrollWidth,
        role: region.getAttribute('role'),
        tabIndex: region.tabIndex,
      };
    });
    assert.ok(tableLayout.documentWidth <= tableLayout.innerWidth, JSON.stringify(tableLayout));
    assert.ok(tableLayout.left >= 0 && tableLayout.right <= tableLayout.innerWidth, JSON.stringify(tableLayout));
    if (tableLayout.scrollWidth > tableLayout.clientWidth) {
      assert.equal(tableLayout.role, 'region', JSON.stringify(tableLayout));
      assert.equal(tableLayout.tabIndex, 0, JSON.stringify(tableLayout));
    }
    await page.screenshot({path:`${screenshotDir}/patient-directory-390x844.png`,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-action=add-patient]').click();
    const patientForm = page.locator('#modal form');
    await patientForm.waitFor();
    const patientFormLayout = await page.evaluate(() => {
      const rect = element => {
        const box = element.getBoundingClientRect();
        return { left: box.left, right: box.right, width: box.width, height: box.height };
      };
      return {
        innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        modal: rect(document.querySelector('#modal')),
        name: rect(document.querySelector('#modal [name="display_name"]')),
        birthYear: rect(document.querySelector('#modal [name="birth_year"]')),
      };
    });
    assert.ok(patientFormLayout.documentWidth <= patientFormLayout.innerWidth, JSON.stringify(patientFormLayout));
    assert.ok(patientFormLayout.modal.left >= 0 && patientFormLayout.modal.right <= patientFormLayout.innerWidth, JSON.stringify(patientFormLayout));
    assert.ok(patientFormLayout.name.width >= 240 && patientFormLayout.name.height >= 36, JSON.stringify(patientFormLayout));
    assert.ok(patientFormLayout.birthYear.width >= 240 && patientFormLayout.birthYear.height >= 36, JSON.stringify(patientFormLayout));
    for (const name of ['display_name', 'birth_year']) {
      assert.equal(await patientForm.locator(`[name=${name}]`).count(), 1);
    }
    assert.equal(await patientForm.locator('[name=phone], [name=gender], [name=hometown], [name=national_id], [name=pid]').count(), 0);
    await patientForm.locator('[name=display_name]').fill('Nguyễn Thị Kiểm Thử');
    await patientForm.locator('[name=birth_year]').fill('1990');
    await patientForm.locator('button[type=submit]').click();
    await page.locator('[data-file=L]').waitFor();
    assert.match(await page.locator('body').innerText(), /Nguyễn Thị Kiểm Thử/);
    assert.doesNotMatch(await page.locator('body').innerText(), /PID|100000001/);
    const createdPatient = await page.request.get(base + '/api/patient-directory?limit=20&offset=0', {
      headers:{Authorization:'Bearer '+await page.evaluate(() => sessionStorage.getItem('ova.token'))},
    });
    assert.equal(createdPatient.status(), 200);
    const directory = await createdPatient.json();
    assert.equal(directory.total, 1);
    assert.equal(directory.items[0].display_name, 'Nguyễn Thị Kiểm Thử');
    assert.equal(directory.items[0].birth_year, 1990);
    assert.equal(Object.hasOwn(directory.items[0], 'phone'), false);
    await page.screenshot({path:`${screenshotDir}/intake-new-patient.png`,fullPage:true});
    await page.locator('[data-action=change-patient]').click();
    await page.locator('.intake-patient-list').waitFor();
    const savedRowLayout = await page.evaluate(() => {
      const region = document.querySelector('.intake-patient-list');
      const box = region.getBoundingClientRect();
      return {
        innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        left: box.left,
        right: box.right,
        clientWidth: region.clientWidth,
        scrollWidth: region.scrollWidth,
        role: region.getAttribute('role'),
        tabIndex: region.tabIndex,
        rows: region.querySelectorAll('tbody tr').length,
      };
    });
    assert.ok(savedRowLayout.documentWidth <= savedRowLayout.innerWidth, JSON.stringify(savedRowLayout));
    assert.ok(savedRowLayout.left >= 0 && savedRowLayout.right <= savedRowLayout.innerWidth, JSON.stringify(savedRowLayout));
    assert.equal(savedRowLayout.rows, 1, JSON.stringify(savedRowLayout));
    if (savedRowLayout.scrollWidth > savedRowLayout.clientWidth) {
      assert.equal(savedRowLayout.role, 'region', JSON.stringify(savedRowLayout));
      assert.equal(savedRowLayout.tabIndex, 0, JSON.stringify(savedRowLayout));
    }
    await page.screenshot({path:`${screenshotDir}/patient-directory-row-390x844.png`,fullPage:true});
    await context.close();
    const secondContext = await browser.newContext({viewport:{width:1440,height:1000}});
    const secondPage = await secondContext.newPage();
    await secondPage.goto(base + '/#login');
    await secondPage.locator('#authForm [name=username]').fill('doctor');
    await secondPage.locator('#authForm [name=password]').fill(password);
    await secondPage.locator('#authForm button[type=submit]').click();
    await secondPage.locator('#dashData .metrics').waitFor();
    await secondPage.locator('#primaryNav a[href="#intake"]').click();
    await secondPage.locator('.intake-patient-list').waitFor();
    await secondPage.getByText('Nguyễn Thị Kiểm Thử', {exact:true}).waitFor();
    await secondContext.close();
    assert.deepEqual(errors, []);
    console.log('PASS: isolated Vinmec logo/Inter/colors, responsive login, authentication, empty directory, facility-scoped patient creation and persistence');
  } finally { await isolated.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
