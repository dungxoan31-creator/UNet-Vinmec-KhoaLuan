const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
const base=process.env.E2E_BASE_URL||'http://127.0.0.1:8027';
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});const page=await browser.newPage();try{
    await page.route('**/api/capabilities',async route=>{await new Promise(r=>setTimeout(r,250));await route.fulfill({json:{dicom_inspection:true,case_leases:true}});});
    await page.goto(base+'/#login');await page.locator('[name=username]').fill('doctor');await page.locator('[name=password]').fill('doctor-local-test-2026');await page.locator('#authForm button[type=submit]').click();await page.locator('h1').filter({hasText:'Tổng quan'}).waitFor();await page.waitForTimeout(400);
    assert.equal(await page.evaluate(async()=>{const {state}=await import('/static/app/state.js');return state.capabilities.dicom_inspection;}),true);
    console.log('PASS: capability probe survives login-to-dashboard navigation');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
