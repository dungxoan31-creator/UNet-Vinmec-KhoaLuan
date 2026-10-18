const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  });
  try {
    const page = await browser.newPage();
    const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:8027';
    await page.goto(base + '/#login');
    const image = await page.evaluate(async () => {
      const { imageSourceBlob } = await import('/static/app/image-source.js');
      const blob = await imageSourceBlob('data:image/png;base64,aGVsbG8=');
      const textBlob = await imageSourceBlob('data:text/plain;charset=utf-8,%E2%9C%93');
      return {
        type: blob.type,
        value: await blob.text(),
        unicode: await textBlob.text(),
      };
    });
    assert.deepEqual(image, { type: 'image/png', value: 'hello', unicode: '✓' });
    console.log('PASS: base64 data URI becomes a typed Blob without fetch()');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
