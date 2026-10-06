const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || 'playwright-core');

const root = path.resolve(__dirname, '..');
const baseUrl = process.env.E2E_BASE_URL || 'http://127.0.0.1:8000';
const validationCsv = process.env.SMOKE_VALIDATION_CSV || 'ai_training/splits/val.csv';
const selectionManifest = process.env.MODEL_SELECTION_MANIFEST || 'evaluation/selected_model.json';
const validationRows = fs.readFileSync(path.resolve(root, validationCsv), 'utf8').trim().split(/\r?\n/);
const columns = validationRows[0].split(',');
const imageColumn = columns.indexOf('image_path');
const modalityColumn = columns.indexOf('modality');
const emptyMaskColumn = columns.indexOf('is_empty_mask');
assert.ok(imageColumn >= 0, 'Validation CSV includes image_path');
const availableRows = validationRows.slice(1).map(row => row.split(',')).filter(row =>
    row[imageColumn] && fs.existsSync(path.resolve(root, row[imageColumn]))
);
const preferredRow = modalityColumn >= 0 && emptyMaskColumn >= 0
    ? availableRows.find(row => row[emptyMaskColumn] === 'False' && row[modalityColumn].toLowerCase().includes('2d'))
    : null;
const selectedRow = preferredRow || availableRows[0];
assert.ok(selectedRow, 'Validation contains at least one readable image');
const imagePath = path.resolve(root, selectedRow[imageColumn]);

async function maskAlpha(page, point) {
    return page.evaluate(({ x, y }) => maskCtx.getImageData(x, y, 1, 1).data[3], point);
}

function rlePixel(rle, point) {
    const position = point.y * 512 + point.x;
    let offset = 0;
    let value = rle.first_val;
    for (const count of rle.counts) {
        if (position < offset + count) return value;
        offset += count;
        value = 1 - value;
    }
    throw new Error('RLE does not cover selected pixel');
}

async function main() {
    const browser = await chromium.launch({
        headless: true,
        executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    });
    let page;
    let createdStudyId;
    try {
        page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const pageErrors = [];
        const consoleErrors = [];
        let reviewPayload;
        let failFirstPrediction = true;
        let failFirstReview = true;
        page.on('pageerror', error => pageErrors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error') consoleErrors.push(message.text());
        });
        page.on('request', request => {
            if (request.url() === `${baseUrl}/api/review`) reviewPayload = request.postDataJSON();
        });
        page.on('response', async response => {
            if (response.url() === `${baseUrl}/api/upload` && response.ok()) {
                createdStudyId = (await response.json()).study_id;
            }
        });
        await page.route('**/api/upload', async route => {
            await page.waitForTimeout(120);
            await route.continue();
        });
        await page.route('**/api/predict/**', async route => {
            if (failFirstPrediction) {
                failFirstPrediction = false;
                await page.waitForTimeout(120);
                await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary inference failure' }) });
                return;
            }
            await route.continue();
        });
        await page.route('**/api/review', async route => {
            if (failFirstReview) {
                failFirstReview = false;
                await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary review failure' }) });
                return;
            }
            await route.continue();
        });
        await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' });
        await page.waitForFunction(() => ['screenDashboard', 'screenDualUpload'].some(id =>
            document.getElementById(id)?.classList.contains('active')));
        await page.evaluate(() => navigateTo('upload'));
        await page.waitForSelector('#screenUpload.active');
        const expectedPatientId = await page.evaluate(() => currentCase.patient_id);
        assert.ok(await page.locator('#uploadDropzone').isVisible(), 'The empty upload state is visible');
        assert.equal(await page.locator('#btnGoToIQA').isDisabled(), true, 'Upload progression starts disabled');
        await page.locator('#fileUploadInput').setInputFiles(path.join(root, 'frontend/vinmec_logo.svg'));
        await page.waitForFunction(() => document.getElementById('toastNotification').style.display === 'flex');
        assert.match(await page.locator('#toastMsg').textContent(), /PNG, JPG, JPEG/i,
            'Unsupported files show the accepted formats in a toast');
        await page.locator('#fileUploadInput').setInputFiles(imagePath);
        await page.waitForSelector('#screenAIProgress.active');
        await page.waitForFunction(() => document.getElementById('inferenceErrorBox').style.display === 'block');
        assert.match(await page.locator('#inferenceErrorBox').textContent(), /Temporary inference failure/);
        await page.unroute('**/api/predict/**');
        await page.locator('#inferenceErrorBox button[onclick="executeInference()"]:visible').click();
        await page.waitForFunction(() => currentPrediction && document.getElementById('screenResults').classList.contains('active'));
        await page.waitForFunction(() => undoStack.length > 0);

        const layerButton = name => page.locator(`#btnLayer${name}`);
        await layerButton('AI').click();
        await layerButton('Doc').click();
        assert.deepEqual(await page.evaluate(() => window.activeLayers),
            { original: true, gt: false, ai: false, doc: false }, 'Original-only view is available');
        await layerButton('Original').click();
        await layerButton('AI').click();
        assert.deepEqual(await page.evaluate(() => window.activeLayers),
            { original: false, gt: false, ai: true, doc: false }, 'Mask-only view is available');
        await layerButton('Original').click();
        await layerButton('Doc').click();
        assert.deepEqual(await page.evaluate(() => window.activeLayers),
            { original: true, gt: false, ai: true, doc: true }, 'Original and mask overlay view is available');

        const identifiers = await page.evaluate(() => ({
            studyId: currentPrediction.study_id,
            imageId: currentCase.image_id,
            predictionId: currentPrediction.prediction_id,
        }));
        createdStudyId = identifiers.studyId;
        const modelName = await page.evaluate(() => currentPrediction.provenance.model_name);
        const selectedModel = JSON.parse(fs.readFileSync(path.resolve(root, selectionManifest), 'utf8'));
        const modelChecksum = await page.evaluate(() => currentPrediction.provenance.model_checksum);
        assert.equal(modelChecksum, selectedModel.checkpoint_sha256, 'Server uses the selected checkpoint');
        const displayedModelName = await page.locator('#workstationModelName').textContent();
        assert.equal(displayedModelName, modelName, 'Workstation shows the model actually used for inference');
        const point = await page.evaluate(() => {
            for (let y = 100; y < 412; y += 25) {
                for (let x = 100; x < 412; x += 25) {
                    if (maskCtx.getImageData(x, y, 1, 1).data[3] === 0) return { x, y };
                }
            }
            throw new Error('No empty canvas pixel found');
        });
        const editor = page.locator('#editorCanvas');
        const box = await editor.boundingBox();
        assert.ok(box, 'Editor canvas is visible');
        assert.ok(Math.abs(box.width - box.height) / box.width < 0.03,
            `The ultrasound canvas keeps a square image ratio (${box.width}x${box.height})`);
        const clickPoint = {
            x: box.x + point.x * box.width / 512,
            y: box.y + point.y * box.height / 512,
        };

        await page.locator('#btnToolBrush').click();
        await page.mouse.click(clickPoint.x, clickPoint.y);
        assert.ok((await maskAlpha(page, point)) > 0, 'Brush adds a mask pixel');
        await page.locator('#btnToolEraser').click();
        await page.mouse.click(clickPoint.x, clickPoint.y);
        assert.equal(await maskAlpha(page, point), 0, 'Eraser clears the mask pixel');
        await page.locator('#btnToolBrush').click();
        await page.mouse.click(clickPoint.x, clickPoint.y);
        assert.ok((await maskAlpha(page, point)) > 0, 'Brush restores an edited pixel');

        await page.evaluate(() => zoomInCanvas());
        const panStart = await page.evaluate(() => ({ x: panOffsetX, y: panOffsetY }));
        const maskBeforePan = await maskAlpha(page, point);
        const zoomedBox = await editor.boundingBox();
        await page.keyboard.down('Shift');
        await page.mouse.move(zoomedBox.x + zoomedBox.width / 2, zoomedBox.y + zoomedBox.height / 2);
        await page.mouse.down();
        await page.mouse.move(zoomedBox.x + zoomedBox.width / 2 + 40, zoomedBox.y + zoomedBox.height / 2 + 25);
        await page.mouse.up();
        await page.keyboard.up('Shift');
        const panEnd = await page.evaluate(() => ({ x: panOffsetX, y: panOffsetY }));
        assert.ok(panEnd.x > panStart.x && panEnd.y > panStart.y, 'Shift-drag pans the zoomed image');
        assert.equal(await maskAlpha(page, point), maskBeforePan, 'Panning does not edit the mask');
        await page.evaluate(() => resetZoomCanvas());
        assert.deepEqual(await page.evaluate(() => ({ zoom: currentZoom, x: panOffsetX, y: panOffsetY })),
            { zoom: 1, x: 0, y: 0 }, '1:1 resets zoom and pan');

        for (const width of [1280, 1024, 768, 390]) {
            await page.setViewportSize({ width, height: width < 500 ? 844 : 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width,
                `The review workspace fits a ${width}px viewport`);
        }
        await page.setViewportSize({ width: 1440, height: 1000 });

        await page.evaluate(() => onOpacityChange(65));
        assert.equal(await page.locator('#valOpacity').textContent(), '65%');
        assert.equal(await maskAlpha(page, point), maskBeforePan, 'Opacity changes only the overlay');
        const historyBeforeReset = await page.evaluate(() => undoStack.length);
        await page.evaluate(() => resetMaskToAI());
        await page.waitForTimeout(150);
        assert.equal(await page.evaluate(() => undoStack.length), historyBeforeReset + 1,
            'Reset adds one AI-mask snapshot to undo history');
        assert.equal(await maskAlpha(page, point), 0, 'Reset restores the original AI mask');
        const historyAtPoint = await page.evaluate(({ x, y }) => undoStack.map(entry => entry.data[(y * 512 + x) * 4 + 3]), point);
        await page.evaluate(() => undoCanvas());
        assert.ok((await maskAlpha(page, point)) > 0, `Undo restores the reviewed edit; history=${historyAtPoint}`);
        assert.equal(await page.evaluate(() => currentCase.doctor_action), 'MODIFIED',
            'Undo keeps the review action consistent with the restored edit');

        await page.locator('button[onclick="openConfirmationModal()"]:visible').first().click();
        await page.locator('#confirmSignoffModal button[onclick="executeDoctorSignOff()"]:visible').click();
        await page.waitForFunction(() => document.getElementById('toastMsg').textContent.includes('Temporary review failure'));
        assert.equal(await page.locator('#confirmSignoffModal').isVisible(), false,
            'A failed save closes the confirmation dialog and reports the error in a toast');
        await page.locator('button[onclick="openConfirmationModal()"]:visible').first().click();
        await page.locator('#confirmSignoffModal button[onclick="executeDoctorSignOff()"]:visible').click();
        await page.waitForFunction(() => document.getElementById('hudStatus').textContent.includes('Đã xác nhận'));

        const caseResponse = await page.request.get(`${baseUrl}/api/cases/${identifiers.studyId}`);
        assert.equal(caseResponse.status(), 200);
        const savedCase = await caseResponse.json();
        const savedImage = savedCase.images.find(image => image.image_id === identifiers.imageId);
        assert.equal(savedCase.patient_id, expectedPatientId,
            `Direct upload preserves the supplied anonymous patient identifier (${expectedPatientId} => ${savedCase.patient_id})`);
        assert.ok(savedImage, 'Uploaded image is returned on reopening the case');
        assert.equal(savedImage.prediction.prediction_id, identifiers.predictionId);
        assert.ok(savedImage.review, 'Final mask is returned on reopening the case');
        assert.equal(savedImage.review.doctor_action, 'MODIFIED');
        assert.equal(savedImage.review.doctor_id, 'UNVERIFIED_REVIEWER');
        assert.ok(reviewPayload.time_spent_seconds >= 1, 'Review duration is measured from result display');
        assert.equal(savedImage.review.time_spent_seconds, reviewPayload.time_spent_seconds);
        assert.equal(rlePixel(savedImage.prediction.rle_mask, point), 0);
        assert.equal(rlePixel(savedImage.review.verified_mask_rle, point), 1);
        assert.equal(savedCase.status, 'REVIEWED');

        await page.reload();
        await page.waitForFunction(() => ['screenDashboard', 'screenDualUpload'].some(id =>
            document.getElementById(id)?.classList.contains('active')));
        await page.evaluate(() => navigateTo('history'));
        await page.waitForFunction(studyId => document.querySelector(`#historyTableBody button[onclick="openCaseDetailModal('${studyId}')"]`), identifiers.studyId);
        await page.locator(`#historyTableBody button[onclick="openCaseDetailModal('${identifiers.studyId}')"]`).click();
        await page.waitForFunction(() => document.getElementById('caseDetailModal').classList.contains('active'));
        assert.equal(await page.locator('#btnDownloadReportModal').isDisabled(), true);
        assert.equal(pageErrors.length, 0, pageErrors.join('\n'));
        const unexpectedConsoleErrors = consoleErrors.filter(message =>
            !message.includes('503 (Service Unavailable)') && !message.includes('Temporary inference failure'));
        assert.equal(unexpectedConsoleErrors.length, 0, unexpectedConsoleErrors.join('\n'));
        const deleted = await page.request.delete(`${baseUrl}/api/cases/${identifiers.studyId}`);
        assert.equal(deleted.status(), 200, 'Smoke-test case is removed after verification');
        createdStudyId = null;
        console.log(JSON.stringify({ status: 'PASS', split: 'val', sourceSplitCsv: validationCsv, selectionManifest, caseId: path.basename(imagePath), checkpointSha256: modelChecksum, emptyUpload: true, uploadError: true, loading: true, inferenceRetry: true, views: true, responsive: true, brush: true, eraser: true, pan: true, opacity: true, resetUndo: true, reviewErrorRetry: true, savedMask: true, reopenedCase: true, unexpectedConsoleErrors: unexpectedConsoleErrors.length }));
    } finally {
        if (page && createdStudyId) {
            await page.request.delete(`${baseUrl}/api/cases/${createdStudyId}`);
        }
        await browser.close();
    }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
