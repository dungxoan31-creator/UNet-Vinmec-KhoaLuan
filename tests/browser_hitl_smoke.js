/* Browser smoke for the current modular workstation; never creates a case. */
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || 'playwright-core');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');

const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:8027';
const chromePath = process.env.CHROME_PATH ||
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function main() {
    assert.ok(process.env.APP_DOCTOR_PASSWORD, 'Set APP_DOCTOR_PASSWORD for the browser smoke test');
    const fixtures = ensureSyntheticFixtures();
    const leftImage = fixtures.left;
    const rightImage = fixtures.right;
    const browser = await chromium.launch({ headless: true, executablePath: chromePath });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const pageErrors = [];
    const consoleErrors = [];
    const blockedApiWrites = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('console', message => {
        if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.route('**/api/**', async route => {
        const request = route.request();
        const method = request.method();
        const pathname = new URL(request.url()).pathname;
        const allowedPosts = new Set([
            '/api/auth/login',
            '/api/auth/logout',
            '/api/cases/search', // Read-only search uses POST for its filter payload.
            '/api/intake/extract-metadata', // Read-only metadata inspection uses POST for multipart file payload.
        ]);
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !allowedPosts.has(pathname)) {
            blockedApiWrites.push(`${method} ${pathname}`);
            await route.abort('blockedbyclient');
            return;
        }
        await route.continue();
    });

    try {
        await page.goto(`${baseUrl}/#login`, { waitUntil: 'networkidle' });
        await page.locator('#authForm').waitFor();

        const healthResponse = await page.request.get(`${baseUrl}/api/health`);
        assert.equal(healthResponse.status(), 200);
        const health = await healthResponse.json();
        assert.equal(health.clinical_status, 'RESEARCH_USE_ONLY');
        assert.equal(health.capabilities.manual_review, false);

        await page.locator('#authForm [name=username]').fill('doctor');
        await page.locator('#authForm [name=password]').fill(process.env.APP_DOCTOR_PASSWORD);
        await page.locator('#authForm button[type=submit]').click();
        await page.waitForFunction(() => location.hash === '#dashboard');
        await page.locator('#accountMenu').waitFor({ state: 'visible' });
        await page.locator('#page h1').getByText('Tổng quan').waitFor();

        await page.locator('a[href="#intake"]').first().click();
        await page.locator('#page [data-select="0"]').click();
        const startButton = page.locator('#startSegmentationBtn');
        await startButton.waitFor();
        assert.equal(await startButton.isDisabled(), true, 'Segmentation starts disabled before images and date');

        await page.locator('[data-file="L"]').setInputFiles(leftImage);
        await page.locator('#stage-L').getByText('Ảnh sẵn sàng').waitFor();
        assert.equal(await startButton.isDisabled(), true, 'One image is not enough to start');

        await page.locator('[data-file="R"]').setInputFiles(rightImage);
        await page.locator('#stage-R').getByText('Ảnh sẵn sàng').waitFor();
        await page.locator('[name="study-date"]').fill('');
        await page.locator('[name="study-date"]').dispatchEvent('input');
        assert.equal(await startButton.isDisabled(), true, 'A study date is still required');

        await page.locator('[name="study-date"]').fill('2026-10-01T08:30');
        await page.locator('[name="study-date"]').dispatchEvent('input');
        const confirmations = page.locator('[data-confirm-file]');
        assert.equal(await confirmations.count(), 2);
        for (const checkbox of await confirmations.all()) {
            await checkbox.uncheck();
        }
        assert.equal(await startButton.isDisabled(), true, 'Unconfirmed image sides must keep segmentation disabled');
        for (const checkbox of await confirmations.all()) {
            await checkbox.check();
        }
        await page.waitForFunction(() => !document.querySelector('#startSegmentationBtn').disabled);
        assert.deepEqual(blockedApiWrites, [], 'Selecting local files does not issue any clinical API write');

        await page.locator('#accountMenu').click();
        await page.locator('[data-action="logout"]').click();
        await page.locator('#authForm').waitFor();
        assert.equal(await page.evaluate(() => sessionStorage.getItem('ova.token')), null,
            'Logout clears the browser session token');
        assert.deepEqual(pageErrors, [], pageErrors.join('\n'));
        assert.deepEqual(consoleErrors, [], consoleErrors.join('\n'));

        console.log(JSON.stringify({
            status: 'PASS',
            flow: 'current modular workstation authentication and intake preflight',
            imageSource: 'artifacts/synthetic_fixtures/',
            researchUseOnly: true,
            bothImagesAndStudyDateRequired: true,
            blockedApiWrites: blockedApiWrites.length,
            logoutClearsSession: true,
            pageErrors: pageErrors.length,
            consoleErrors: consoleErrors.length,
        }));
    } finally {
        await browser.close();
    }
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
