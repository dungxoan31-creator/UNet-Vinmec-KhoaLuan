const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
const base=process.env.E2E_BASE_URL||'http://127.0.0.1:8027';
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});const page=await browser.newPage();try{
    await page.goto(base+'/#login');
    await page.evaluate(async()=>{const {confirmAction}=await import('/static/app/ui.js');window.firstConfirm=confirmAction('Xác nhận thứ nhất','Thao tác thử');});
    await page.locator('#modal button[value=confirm]').click();assert.equal(await page.evaluate(()=>window.firstConfirm),true);
    await page.evaluate(async()=>{const {confirmAction}=await import('/static/app/ui.js');window.secondConfirm=confirmAction('Xác nhận thứ hai','Hủy bằng Escape');});
    await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>window.secondConfirm),false,'Escape must not reuse a prior confirmation');
    console.log('PASS: Escape cancels a reused confirmation dialog');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
