/* RUO doctor journey on a disposable synthetic-only backend and SQLite database. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');
const { waitForAppState } = require('./helpers/app_state_wait.cjs');

async function captureResponsive(page, evidenceDir, screen, { shell = false } = {}) {
  const widths = [1440, 1366, 1280, 768, 390, 375];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const layout = await page.evaluate(() => {
      const rect = selector => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const { x, y, width, height, right, bottom } = element.getBoundingClientRect();
        return { x, y, width, height, right, bottom };
      };
      const notices = [...document.querySelectorAll('.ruo-safety-banner, #environmentUnknownBanner, #syntheticDemoBanner')]
        .filter(element => !element.hidden && getComputedStyle(element).display !== 'none');
      return {
        width: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        noticeBottom: Math.max(0, ...notices.map(element => element.getBoundingClientRect().bottom)),
        header: rect('.topbar'),
        main: rect('.main'),
        statusbar: rect('.statusbar'),
        sidebar: rect('.sidebar'),
        logo: (() => {
          const image = document.querySelector('.vinmec-logo');
          return image && { loaded: image.complete, naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight };
        })(),
        imageSurface: getComputedStyle(document.querySelector('.viewer-center') || document.body).backgroundColor,
        viewerSurfaceToken: (() => {
          const probe = document.createElement('span');
          probe.style.backgroundColor = 'var(--viewer-surface)';
          document.body.append(probe);
          const value = getComputedStyle(probe).backgroundColor;
          probe.remove();
          return value;
        })(),
      };
    });
    assert.ok(layout.documentWidth <= width, `${screen} has horizontal overflow at ${width}px: ${JSON.stringify(layout)}`);
    if (screen === 'viewer') {
      assert.notEqual(layout.viewerSurfaceToken, 'rgba(0, 0, 0, 0)', 'Viewer surface token must be defined');
      assert.equal(layout.imageSurface, layout.viewerSurfaceToken, `viewer image surface differs from its token at ${width}px`);
    }
    if (screen === 'doctor-cases') {
      const selectedView = width <= 620 ? '#caseGridView' : '#caseTableView';
      assert.equal(await page.locator(selectedView).getAttribute('aria-pressed'), 'true',
        `Case list should use the ${width <= 620 ? 'card' : 'table'} layout at ${width}px.`);
      if (width <= 620) assert.equal(await page.locator('#caseResults [role="list"]').count(), 1,
        'Mobile case list should show cards rather than clipped table columns.');
    }
    if (layout.logo) {
      assert.deepEqual(layout.logo, { loaded: true, naturalWidth: 1616, naturalHeight: 973 }, `${screen} VINMEC logo dimensions at ${width}px`);
    }
    if (shell) {
      assert.ok(layout.header && layout.main, `${screen} shell is missing its header or content sheet at ${width}px`);
      assert.ok(layout.header.y >= layout.noticeBottom - 1, `${screen} header covers a safety notice at ${width}px: ${JSON.stringify(layout)}`);
      assert.ok(layout.main.y >= layout.header.bottom - 1, `${screen} content overlaps its header at ${width}px: ${JSON.stringify(layout)}`);
      assert.ok(layout.main.bottom <= layout.statusbar.y + 1, `${screen} content sits underneath the status bar at ${width}px: ${JSON.stringify(layout)}`);
      if (width <= 800) {
        const toggle = page.locator('#collapseNav');
        assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
        await toggle.click();
        await page.locator('body.nav-open').waitFor();
        assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#primaryNav a').first().isVisible(), true);
        const firstNavLink = page.locator('#primaryNav a').first();
        const lastNavLink = page.locator('#primaryNav a').last();
        await page.keyboard.press('Shift+Tab');
        assert.equal(await lastNavLink.evaluate(element => document.activeElement === element), true,
          `${screen} mobile drawer must keep reverse keyboard focus inside the menu`);
        await page.keyboard.press('Tab');
        assert.equal(await firstNavLink.evaluate(element => document.activeElement === element), true,
          `${screen} mobile drawer must keep forward keyboard focus inside the menu`);
        await page.screenshot({ path: path.join(evidenceDir, `${screen}-${width}-nav-open.png`), fullPage: true });
        await page.keyboard.press('Escape');
        await page.locator('body:not(.nav-open)').waitFor();
        assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
        assert.equal(await toggle.evaluate(element => document.activeElement === element), true,
          `${screen} mobile drawer must return focus to its toggle when closed`);
        await toggle.click();
        await page.locator('#navScrim').click({ position: { x: width - 8, y: 8 } });
        await page.locator('body:not(.nav-open)').waitFor();
        assert.equal(await toggle.evaluate(element => document.activeElement === element), true,
          `${screen} mobile drawer must return focus after the scrim closes it`);
      } else {
        assert.equal(await page.locator('#primaryNav').evaluate(element => getComputedStyle(element).visibility), 'visible');
      }
    }
    await page.screenshot({ path: path.join(evidenceDir, `${screen}-${width}.png`), fullPage: true });
    if (['viewer', 'dashboard'].includes(screen) && width === 1440 && process.env.UI_AXE_PROBE === '1') {
      await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
      const results = await page.evaluate(() => window.axe.run(document, { runOnly: ['color-contrast'] }));
      const incompleteStyles = await page.evaluate((groups) => groups.flatMap(group => group.nodes.map(node => {
        const element = document.querySelector(node.target[0]);
        if (!element) return { target: node.target, unavailable: true };
        const ancestors = [];
        for (let parent = element; parent && ancestors.length < 5; parent = parent.parentElement) {
          const css = getComputedStyle(parent);
          ancestors.push({ tag: parent.tagName, color: css.color, background: css.backgroundColor, backgroundImage: css.backgroundImage });
        }
        return { target: node.target, text: element.textContent.trim(), ancestors };
      })), results.incomplete);
      const summary = { violations: results.violations, incomplete: results.incomplete, incompleteStyles, passes: results.passes.length };
      fs.writeFileSync(path.join(evidenceDir, `${screen}-axe-color-contrast-2026-10-29.json`), JSON.stringify(summary, null, 2));
      console.log(`Axe ${screen} color contrast: ${summary.violations.length} violations, ${summary.incomplete.length} incomplete`);
    }
    if (screen === 'viewer' && width === 768) {
      const panelToggle = page.locator('[data-action="panel-toggle"]');
      assert.equal(await panelToggle.isVisible(), true, 'Viewer clinical panel toggle must remain reachable at tablet width.');
      await panelToggle.click();
      assert.equal(await panelToggle.getAttribute('aria-expanded'), 'true');
      const panelBounds = await page.locator('.viewer-panel').evaluate(element => {
        const panel = element.getBoundingClientRect();
        const grid = document.querySelector('.viewer-grid').getBoundingClientRect();
        return { panelTop: panel.top, panelBottom: panel.bottom, gridTop: grid.top, gridBottom: grid.bottom };
      });
      assert.ok(panelBounds.panelTop >= panelBounds.gridTop - 1 && panelBounds.panelBottom <= panelBounds.gridBottom + 1,
        `Viewer clinical panel must stay below the header and within the image workspace: ${JSON.stringify(panelBounds)}`);
      await page.screenshot({ path: path.join(evidenceDir, 'viewer-768-panel-open.png'), fullPage: true });
      await panelToggle.click();
      assert.equal(await panelToggle.getAttribute('aria-expanded'), 'false');
    }
  }
}

async function main() {
  const fixtures = ensureSyntheticFixtures();
  const server = await startIsolatedBrowser({ syntheticFixtureDir: fixtures.directory });
  const evidenceDir = path.resolve(process.env.DOCTOR_WORKFLOW_EVIDENCE_DIR ||
    path.join(__dirname, '../artifacts/audit_remediation_2026_10_28/evidence/ui-redesign-2026-10-29'));
  fs.mkdirSync(evidenceDir, { recursive: true });
  const pageErrors = [];
  try {
    const page = await server.browser.newPage({ viewport: { width: 1440, height: 1000 }, bypassCSP: process.env.UI_AXE_PROBE === '1' });
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.addInitScript(() => {
      window.__printCalls = 0;
      window.print = () => { window.__printCalls += 1; };
    });

    await page.goto(server.base + '/#login');
    assert.equal(await page.locator('link[rel="icon"]').getAttribute('href'),
      '/static/assets/brand/vinmec-logo.png?v=20261029-vinmec-tab', 'Browser tab must use the current supplied VINMEC logo.');
    const faviconResponse = await page.request.get(server.base + '/static/assets/brand/vinmec-logo.png?v=20261029-vinmec-tab');
    assert.equal(faviconResponse.status(), 200, 'VINMEC favicon must be served by the application.');
    assert.match(faviconResponse.headers()['content-type'], /image\/png/i);
    const faviconRaster = await page.evaluate(async src => {
      const image = new Image();
      image.src = src;
      await image.decode();
      return { width: image.naturalWidth, height: image.naturalHeight, complete: image.complete };
    }, '/static/assets/brand/vinmec-logo.png?v=20261029-vinmec-tab');
    assert.deepEqual(faviconRaster, { width: 1616, height: 973, complete: true },
      'the supplied VINMEC logo must decode unchanged as the browser tab icon source');
    const loginLogo = page.locator('.auth-aside .vinmec-logo');
    await loginLogo.waitFor();
    assert.equal(await loginLogo.getAttribute('alt'), 'Vinmec International Hospital');
    assert.deepEqual(await loginLogo.evaluate(image => ({
      complete: image.complete,
      width: image.naturalWidth,
      height: image.naturalHeight,
    })), { complete: true, width: 1616, height: 973 }, 'latest supplied logo must load on the login screen');
    assert.equal(await page.locator('.ruo-safety-banner').count(), 0);
    await captureResponsive(page, evidenceDir, 'login');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    const shellLogo = page.locator('.topbar .vinmec-logo');
    await shellLogo.waitFor();
    assert.equal(await shellLogo.evaluate(image => image.complete && image.naturalWidth === 1616), true,
      'latest supplied logo must load in the application navigation');
    await page.waitForFunction(() => document.querySelector('#syntheticDemoBanner')?.hidden === false);
    assert.match(await page.locator('#syntheticDemoBanner').innerText(), /Dữ liệu tổng hợp/i);
    assert.match(await page.locator('#accountMenu').getAttribute('aria-label'), /^Mở tài khoản của\s+\S+/i,
      'The mobile account control must retain an accessible name when its visible name is hidden.');
    await page.locator('#dashData .metrics').waitFor();
    await captureResponsive(page, evidenceDir, 'dashboard', { shell: true });
    await page.setViewportSize({ width: 1440, height: 1000 });

    const healthResponse = await page.request.get(server.base + '/api/health');
    assert.equal(healthResponse.status(), 200);
    const health = await healthResponse.json();
    assert.equal(health.capabilities.synthetic_demo_mode, true);
    assert.equal(health.capabilities.synthetic_demo_uploads_restricted, true);
    assert.equal(health.capabilities.clinical_production_ready, false);
    assert.equal(health.capabilities.case_workflow, false);

    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-select="0"]').waitFor();
    await captureResponsive(page, evidenceDir, 'intake', { shell: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.locator('[data-select="0"]').click();
    await page.locator('[name=study-date]').fill('2026-10-29T09:00');
    await page.locator('[data-file=L]').setInputFiles(fixtures.left);
    await page.locator('[data-file=R]').setInputFiles(fixtures.right);
    await page.waitForFunction(
      () => document.querySelector('#startSegmentationBtn')?.disabled === false,
      null,
      { timeout: 30000 },
    );
    assert.equal(await page.locator('[name=reason]').isDisabled(), true,
      'Synthetic-only intake must not accept free-text clinical indication.');

    const caseCreateResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/cases',
    );
    const firstInferenceResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname.startsWith('/api/predict/'),
    );
    await page.locator('#startSegmentationBtn').click();
    const caseCreateResponse = await caseCreateResponsePromise;
    assert.equal(caseCreateResponse.status(), 200, await caseCreateResponse.text());
    assert.equal(caseCreateResponse.request().postDataJSON().patient_id, null);
    assert.equal(caseCreateResponse.request().postDataJSON().patient_directory_id, null);
    assert.equal(caseCreateResponse.request().postDataJSON().clinical_notes, null);
    const firstInferenceResponse = await firstInferenceResponsePromise;
    if (firstInferenceResponse.status() === 503 &&
      /Checkpoint mô hình chưa được nạp hoặc không khớp SHA-256 đã chọn/i.test(await firstInferenceResponse.text())) {
      await waitForAppState(page, snapshot => !snapshot.busy, { message: 'provenance gate response settled' });
      const blockedUi = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          route: state.route,
          busy: state.busy,
          syntheticDemoMode: state.capabilities?.synthetic_demo_mode,
          predictionIds: state.case?.images?.map(image => image.prediction_id ?? null) ?? [],
          visibleError: document.querySelector('#intakeHint')?.textContent ||
            document.querySelector('#toasts')?.innerText || '',
        };
      });
      const evidence = {
        status: 'BLOCKED',
        blocker: 'Inference returned HTTP 503 because the selected checkpoint is not loaded or its SHA-256 does not match the verified selection.',
        apiStatus: firstInferenceResponse.status(),
        ui: blockedUi,
        pageErrors,
        scope: 'synthetic-only disposable browser, server, and SQLite runtime; login, responsive intake, and isolated case creation executed',
      };
      fs.writeFileSync(path.join(evidenceDir, 'doctor-workflow-provenance-blocked.json'), JSON.stringify(evidence, null, 2));
      await page.screenshot({ path: path.join(evidenceDir, 'doctor-workflow-provenance-blocked.png'), fullPage: true });
      assert.deepEqual(pageErrors, [], 'The fail-closed provenance response must not cause browser exceptions.');
      console.log(JSON.stringify(evidence));
      return;
    }
    await page.waitForFunction(() => location.hash.startsWith('#viewer/'), null, { timeout: 120000 });
    await waitForAppState(page, snapshot => !snapshot.busy && snapshot.case?.images?.length === 2 &&
      snapshot.case.images.every(image => image.prediction_id), { timeout: 120000, message: 'live inference completion' });
    await page.waitForFunction(() => {
      const selector = document.querySelector('#viewerImageSelect');
      return selector?.options.length === 2 && !selector.disabled &&
        document.querySelector('#sideLabel')?.textContent.startsWith('Buồng trứng');
    }, null, { timeout: 30000 });
    const initialCase = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return {
        studyId: state.case.study_id,
        patientCode: state.case.patient_id,
        imageCount: state.case.images.length,
      };
    });
    assert.equal(initialCase.patientCode, null,
      'Synthetic demo selections are local fixtures and must not be persisted as patient identities.');
    assert.equal(initialCase.imageCount, 2);

    const imageIds = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      return state.case.images.map(image => ({ imageId: image.image_id, side: image.laterality }));
    });
    assert.equal(imageIds.length, 2);
    const initialSelection = await page.evaluate(async () => {
      const { state } = await import('/static/app/state.js');
      const imageId = document.querySelector('#viewerImageSelect')?.value;
      const image = state.case?.images?.find(candidate => candidate.image_id === imageId);
      return { imageId, side: state.side, laterality: image?.laterality, seen: image?.seen };
    });
    assert.equal(initialSelection.side, initialSelection.laterality,
      `Initial image selector and laterality must agree: ${JSON.stringify(initialSelection)}`);
    assert.equal(initialSelection.seen, true,
      'The initially displayed synthetic image must be marked as viewed.');
    const otherImage = imageIds.find(image => image.imageId !== initialSelection.imageId);
    assert.ok(otherImage, 'The synthetic case must expose a second image for review.');
    await page.locator('#viewerImageSelect').selectOption(otherImage.imageId);
    await waitForAppState(page, snapshot => {
      const image = snapshot.case?.images?.find(candidate => candidate.image_id === otherImage.imageId);
      const expectedLabel = otherImage.side === 'L' ? 'Buồng trứng trái' : 'Buồng trứng phải';
      return snapshot.side === otherImage.side && image?.seen === true &&
        snapshot.dom.selected_image_id === otherImage.imageId && !snapshot.dom.selector_disabled &&
        snapshot.dom.side_label?.startsWith(expectedLabel);
    }, { timeout: 30000, stableMs: 100, message: 'stable second-image selection' });
    await waitForAppState(page, snapshot => snapshot.editing?.caseId === initialCase.studyId &&
      snapshot.editing.allowed && !snapshot.busy && snapshot.case?.images?.every(image => image.seen) &&
      snapshot.dom.selector_disabled === false && snapshot.dom.save_review_disabled === false,
    { timeout: 30000, stableMs: 250, message: 'stable bilateral review readiness' });
    const overlayVisibility = page.locator('[data-action="overlay-visibility"]');
    const initialOverlayState = await overlayVisibility.getAttribute('aria-pressed');
    assert.ok(['true', 'false'].includes(initialOverlayState));
    await overlayVisibility.focus();
    assert.equal(await overlayVisibility.evaluate(element => document.activeElement === element), true,
      'Keyboard overlay control must receive focus before activation.');
    await overlayVisibility.press('Space');
    await page.waitForFunction(initial =>
      document.querySelector('[data-action="overlay-visibility"]')?.getAttribute('aria-pressed') !== initial,
    initialOverlayState);
    await overlayVisibility.press('Space');
    await page.waitForFunction(initial =>
      document.querySelector('[data-action="overlay-visibility"]')?.getAttribute('aria-pressed') === initial,
    initialOverlayState);
    await captureResponsive(page, evidenceDir, 'viewer');
    await page.setViewportSize({ width: 1440, height: 1000 });
    const saveButton = page.locator('[data-action=save-review]');
    const finalReviewState = await page.evaluate(async () => {
        const { state } = await import('/static/app/state.js');
        return {
          editing: state.editing,
          busy: state.busy,
          role: state.user?.role,
          caseStatus: state.case?.status,
          dirty: state.dirty,
          side: state.side,
          selectedImageId: document.querySelector('#viewerImageSelect')?.value,
          selectorDisabled: document.querySelector('#viewerImageSelect')?.disabled,
          images: state.case?.images?.map(image => ({ imageId: image.image_id, side: image.laterality, seen: image.seen })),
          saveButton: (() => {
            const button = document.querySelector('[data-action="save-review"]');
            return button && { disabled: button.disabled, hidden: button.hidden, display: getComputedStyle(button).display };
          })(),
        };
      });
    assert.equal(await saveButton.isEnabled(), true,
      `Saved RUO review must be available after viewing both synthetic sides and acquiring a lease: ${JSON.stringify(finalReviewState)}`);
    const saveResponsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/reviews/batch',
    );
    await saveButton.click();
    const saveResponse = await saveResponsePromise;
    assert.equal(saveResponse.status(), 200, await saveResponse.text());
    await waitForAppState(page, snapshot => !snapshot.busy &&
      snapshot.case?.images?.every(image => image.review_id),
    { timeout: 30000, stableMs: 100, message: 'persisted review revisions' });

    await page.locator('[data-action=report]').click();
    await page.waitForFunction(() => location.hash.startsWith('#report/'));
    await page.locator('#reportData .report').waitFor({ timeout: 20000 });
    const reportText = await page.locator('#reportData .report').innerText();
    assert.match(reportText, /CHẾ ĐỘ DEMO · DỮ LIỆU TỔNG HỢP/);
    assert.match(reportText, /THÔNG TIN NGHIÊN CỨU RUO/);
    assert.match(reportText, /Phạm vi: nghiên cứu kỹ thuật/);
    assert.equal(await page.locator('#reportData .report-synthetic-demo-banner').count(), 3);
    assert.equal(await page.locator('#reportData .patient-friendly-summary-panel').count(), 0);
    assert.match(reportText, /Chưa cấp/);
    assert.doesNotMatch(reportText, /DEMO-SYNTHETIC-DOCTOR-001/,
      'No fabricated patient identity may appear in the report.');
    await captureResponsive(page, evidenceDir, 'report', { shell: true });
    await page.setViewportSize({ width: 1440, height: 1000 });

    await page.locator('[data-action=print]').click();
    await page.waitForFunction(() => window.__printCalls === 1);
    const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
    const pdfPages = (pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
    assert.equal(pdfPages, 4,
      `Expected one RUO summary page, one evidence page per image, and one provenance page, got ${pdfPages}.`);

    const doctorPages = ['cases', `case/${initialCase.studyId}`, 'profile', 'preferences', 'notifications', 'help'];
    for (const route of doctorPages) {
      await page.evaluate(nextRoute => { location.hash = `#${nextRoute}`; }, route);
      await page.locator('#page h1').first().waitFor({ state: 'visible', timeout: 15000 });
      await captureResponsive(page, evidenceDir, `doctor-${route.replace('/', '-')}`, { shell: true });
    }

    await page.locator('#accountMenu').click();
    await page.locator('[data-action=logout]').click();
    await page.locator('#authForm').waitFor();
    await page.locator('[name=username]').fill('admin');
    await page.locator('[name=password]').fill(server.adminPassword);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.locator('#dashData .metrics').waitFor();
    await captureResponsive(page, evidenceDir, 'admin-dashboard', { shell: true });
    for (const route of ['admin', 'notifications', 'preferences', 'profile', 'help']) {
      await page.evaluate(nextRoute => { location.hash = `#${nextRoute}`; }, route);
      await page.locator('#page h1').first().waitFor({ state: 'visible', timeout: 15000 });
      await captureResponsive(page, evidenceDir, `admin-${route}`, { shell: true });
    }
    assert.deepEqual(pageErrors, []);
    console.log(JSON.stringify({
      status: 'PASS',
      scope: 'doctor login/intake/live inference/two-side review/RUO report plus admin route matrix on synthetic-only isolated API+SQLite',
      images: initialCase.imageCount,
      reviewStatus: 'persisted',
      pdfPages,
      doctorPages,
      adminPages: ['dashboard', 'admin', 'notifications', 'preferences', 'profile', 'help'],
      pageErrors: pageErrors.length,
    }));
  } finally {
    const isolatedRuntime = server.runtime;
    await server.close();
    assert.equal(fs.existsSync(isolatedRuntime), false,
      'The synthetic-only doctor E2E runtime must be removed after the isolated server stops.');
  }
}

main().catch(error => {
  console.error('[Doctor E2E Failed]', error.stack || error);
  process.exitCode = 1;
});
