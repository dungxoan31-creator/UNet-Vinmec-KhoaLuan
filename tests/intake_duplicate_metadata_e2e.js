const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function addPngTextChunk(source, targetSize, label) {
  assert.equal(source.subarray(-8, -4).toString('ascii'), 'IEND');
  const extraBytes = targetSize - source.length;
  assert.ok(extraBytes >= 20, 'test fixture must have room for its PNG text chunk');
  const dataLength = extraBytes - 12;
  const data = Buffer.alloc(dataLength, 0x20);
  data.write(`Comment\0${label}`, 'ascii');
  const type = Buffer.from('tEXt', 'ascii');
  const crcInput = Buffer.concat([type, data]);
  const header = Buffer.alloc(4);
  header.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(crcInput));
  const chunk = Buffer.concat([header, type, data, checksum]);
  return Buffer.concat([source.subarray(0, -12), chunk, source.subarray(-12)]);
}

async function selectFiles(page, side, payloads, name, lastModified) {
  await page.locator(`[data-file=${side}]`).evaluate((input, selection) => {
    const transfer = new DataTransfer();
    for (const encoded of selection.payloads) {
      const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      transfer.items.add(new File([bytes], selection.name, {
        type: 'image/png', lastModified: selection.lastModified,
      }));
    }
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, { payloads: payloads.map(buffer => buffer.toString('base64')), name, lastModified });
}

async function dropFiles(page, side, payloads, names) {
  await page.locator(`.dropzone[data-side=${side}]`).evaluate((zone, selection) => {
    const transfer = new DataTransfer();
    for (const [index, encoded] of selection.payloads.entries()) {
      const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      transfer.items.add(new File([bytes], selection.names[index], { type: 'image/png' }));
    }
    zone.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: transfer }));
  }, { payloads: payloads.map(buffer => buffer.toString('base64')), names });
}

async function selectSameBytesOnBothSidesAtOnce(page, payload) {
  await page.evaluate(encoded => {
    for (const [side, name] of [['L', 'left-copy.png'], ['R', 'right-copy.png']]) {
      const input = document.querySelector(`[data-file=${side}]`);
      const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      const transfer = new DataTransfer();
      transfer.items.add(new File([bytes], name, { type: 'image/png', lastModified: 1700000001000 }));
      input.files = transfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }, payload.toString('base64'));
}

async function main() {
  const fixtures = ensureSyntheticFixtures();
  const leftSource = fs.readFileSync(fixtures.left);
  const rightSource = fs.readFileSync(fixtures.right);
  const targetSize = Math.max(leftSource.length, rightSource.length) + 128;
  const payloads = [
    addPngTextChunk(leftSource, targetSize, 'distinct-left-content'),
    addPngTextChunk(rightSource, targetSize, 'distinct-right-content'),
  ];
  assert.equal(payloads[0].length, payloads[1].length);
  assert.notEqual(crypto.createHash('sha256').update(payloads[0]).digest('hex'),
    crypto.createHash('sha256').update(payloads[1]).digest('hex'));

  const server = await startIsolatedBrowser();
  const errors = [];
  try {
    const page = await server.browser.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(server.base + '/#login');
    await page.locator('[name=username]').fill('doctor');
    await page.locator('[name=password]').fill(server.password);
    await page.locator('#authForm button[type=submit]').click();
    await page.waitForFunction(() => location.hash === '#dashboard');
    await page.evaluate(() => { location.hash = '#intake'; });
    await page.locator('[data-select="0"]').click();
    let delayMetadataResponses = false;
    let activeMetadataRequests = 0;
    let maxMetadataRequests = 0;
    let metadataRequestCount = 0;
    await page.route('**/api/intake/extract-metadata', async route => {
      metadataRequestCount++;
      activeMetadataRequests++;
      maxMetadataRequests = Math.max(maxMetadataRequests, activeMetadataRequests);
      try {
        if (delayMetadataResponses) await new Promise(resolve => setTimeout(resolve, 150));
        await route.fulfill({
          status: 200, contentType: 'application/json', body: JSON.stringify({ metadata: {} }),
        });
      } finally { activeMetadataRequests--; }
    });

    await selectFiles(page, 'L', payloads, 'same-name.png', 1700000000000);

    await page.waitForTimeout(750);
    const selectedCount = await page.locator('#files-L .intake-file-item').count();
    assert.equal(selectedCount, 2, JSON.stringify({ selectedCount,
      fileList: await page.locator('#files-L').innerText(),
      toast: await page.locator('#toasts').innerText(),
      pageErrors: errors }));
    assert.equal(await page.locator('[data-confirm-file]').count(), 2);

    await selectFiles(page, 'L', [payloads[0]], 'renamed-copy.png', 1700000000001);
    await page.waitForTimeout(500);
    assert.equal(await page.locator('#files-L .intake-file-item').count(), 2,
      'identical bytes must be rejected even when filename and lastModified differ');
    assert.match(await page.locator('#toasts').innerText(), /cùng nội dung/i);

    await dropFiles(page, 'R', [payloads[0]], ['same-bytes-other-side.png']);
    await page.waitForTimeout(500);
    assert.equal(await page.locator('#files-R .intake-file-item').count(), 0,
      'dragging duplicate bytes to the opposite ovary must also be rejected before case creation');
    assert.match(await page.locator('#toasts').innerText(), /cùng nội dung/i);

    while (await page.locator('#files-L [data-remove-file]').count())
      await page.locator('#files-L [data-remove-file]').first().click();
    await selectSameBytesOnBothSidesAtOnce(page, payloads[0]);
    await page.waitForTimeout(750);
    const concurrentCounts = {
      left: await page.locator('#files-L .intake-file-item').count(),
      right: await page.locator('#files-R .intake-file-item').count(),
    };
    assert.deepEqual(concurrentCounts, { left: 1, right: 0 },
      'simultaneous same-content selections must retain only the first selection');

    await page.locator('[data-unavailable=R]').check();
    await page.locator('[data-unavailable-status=R]').selectOption('NOT_VISUALIZED');
    await dropFiles(page, 'R', [payloads[0]], ['duplicate-of-left.png']);
    await page.waitForTimeout(500);
    assert.equal(await page.locator('[data-unavailable-status=R]').inputValue(), 'NOT_VISUALIZED',
      'rejecting a duplicate upload must preserve the already recorded unavailable-side status');
    assert.equal(await page.locator('[data-unavailable=R]').isChecked(), true);
    assert.equal(await page.locator('#files-R .intake-file-item').count(), 0);
    await selectFiles(page, 'R', [payloads[1]], 'new-right-content.png', 1700000000003);
    await page.waitForTimeout(500);
    assert.equal(await page.locator('#files-R .intake-file-item').count(), 1);
    assert.equal(await page.locator('[data-unavailable=R]').isChecked(), false,
      'a successfully decoded image must clear the previously recorded unavailable-side status');
    assert.equal(await page.locator('[data-unavailable-status=R]').inputValue(), '');

    while (await page.locator('#files-L [data-remove-file]').count())
      await page.locator('#files-L [data-remove-file]').first().click();
    const batch = Array.from({ length: 6 }, (_, index) =>
      addPngTextChunk(leftSource, targetSize, `metadata-batch-${index}`));
    const initialMetadataRequestCount = metadataRequestCount;
    delayMetadataResponses = true;
    maxMetadataRequests = activeMetadataRequests;
    const metadataBatchStarted = Date.now();
    await selectFiles(page, 'L', batch, 'batch.png', 1700000000010);
    const metadataBatchDeadline = Date.now() + 10000;
    while ((metadataRequestCount < initialMetadataRequestCount + batch.length || activeMetadataRequests > 0) &&
      Date.now() < metadataBatchDeadline)
      await new Promise(resolve => setTimeout(resolve, 20));
    const metadataBatchDurationMs = Date.now() - metadataBatchStarted;
    delayMetadataResponses = false;
    assert.equal(await page.locator('#files-L .intake-file-item').count(), batch.length);
    assert.equal(metadataRequestCount - initialMetadataRequestCount, batch.length,
      'every accepted image must finish its metadata request');
    assert.equal(activeMetadataRequests, 0);
    assert.equal(maxMetadataRequests, 2,
      `bulk intake should overlap metadata checks with a global concurrency cap of 2; observed ${maxMetadataRequests}`);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: 'PASS', distinctPngs: payloads.length,
      sameName: true, sameSizeBytes: payloads[0].length, sameLastModified: 1700000000000,
      selectedImages: 2, renamedDuplicateRejected: true, crossSideDropDuplicateRejected: true,
      concurrentDuplicateCounts: concurrentCounts, duplicateDropPreservedUnavailableSide: true,
      lateralityRestoredByValidImage: true, bulkMetadataRequests: batch.length,
      metadataConcurrency: maxMetadataRequests, metadataBatchDurationMs, pageErrors: errors.length }));
  } finally {
    await server.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
