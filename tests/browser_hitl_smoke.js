/* Browser smoke for the current modular workstation; never creates a case. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || 'playwright-core');

const root = path.resolve(__dirname, '..');
const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const validationCsv = process.env.SMOKE_VALIDATION_CSV ||
    'ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv';
const chromePath = process.env.CHROME_PATH ||
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

function readValidationImages() {
    const lines = fs.readFileSync(path.resolve(root, validationCsv), 'utf8')
        .trim().split(/\r?\n/);
    const columns = lines[0].split(',');
    const imageIndex = columns.indexOf('image_path');
    const hashIndex = columns.indexOf('image_sha256');
    assert.ok(imageIndex >= 0, 'Validation CSV includes image_path');

    const available = lines.slice(1).map(line => line.split(',')).map(row => {
        const recorded = row[imageIndex]?.replaceAll('\\', '/');
        if (!recorded) return null;
        let imagePath = path.resolve(root, recorded);
        if (!fs.existsSync(imagePath)) {
            for (const [source, target] of [
                ['dataset/Vinmec/Vinmec_2d/images/', 'dataset/2d/images/'],
                ['dataset/Vinmec/Vinmec_3d/images/', 'dataset/3d/images/'],
            ]) {
                if (recorded.startsWith(source)) {
                    imagePath = path.resolve(root, target, recorded.slice(source.length));
                    break;
                }
            }
        }
        if (!fs.existsSync(imagePath)) return null;
        if (hashIndex >= 0) {
            const actualHash = crypto.createHash('sha256').update(fs.readFileSync(imagePath)).digest('hex');
            assert.equal(actualHash, row[hashIndex], 'Resolved image matches its frozen validation record');
        }
        return imagePath;
    }).filter(Boolean);

    assert.ok(available.length >= 2, 'Validation contains two readable images for local preflight checks');
    return available.slice(0, 2);
}

async function main() {
    assert.ok(process.env.APP_DOCTOR_PASSWORD, 'Set APP_DOCTOR_PASSWORD for the browser smoke test');
    const [leftImage, rightImage] = readValidationImages();
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
        assert.equal(await startButton.isEnabled(), true, 'The UI enables the next step only after both images and date exist');
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
            sourceSplit: validationCsv,
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
