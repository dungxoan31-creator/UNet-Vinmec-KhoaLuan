const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});const page=await browser.newPage();try{
    await page.goto('http://127.0.0.1:8027/#login');await page.locator('[data-action=demo-BS]').click();await page.evaluate(()=>location.hash='#viewer/demo-case-1');await page.locator('#viewport').waitFor();
    const result=await page.evaluate(async()=>{const {state,saveDraft,restoreDraft}=await import('/static/app/state.js');const c=state.case;c.version=1;c.images[0].mask.fill(1);saveDraft();c.version=2;c.images[0].mask.fill(0);const restored=restoreDraft(c);return {restored,count:c.images[0].mask.reduce((n,v)=>n+v,0),conflict:Boolean(state.draftConflict)};});
    assert.equal(result.restored,false);assert.equal(result.count,0);assert.equal(result.conflict,true);console.log('PASS: an old draft cannot overwrite a newer version');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
