const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});const context=await browser.newContext(),a=await context.newPage(),b=await context.newPage();try{
    async function open(page){await page.goto('http://127.0.0.1:8027/#login');await page.locator('[data-action=demo-TK]').click();await page.evaluate(async()=>{const {demoDB}=await import('/static/app/demo.js');const c=demoDB.cases.find(c=>c.study_id==='demo-case-2');c.status='IN_REVIEW';c.correction_by='tk-demo';location.hash='#viewer/'+c.study_id;});await page.locator('[data-action=save-correction]').waitFor();await page.waitForTimeout(300);}
    await open(a);await open(b);assert.equal(await b.locator('[data-action=save-correction]').isDisabled(),true);
    assert.equal(await b.evaluate(async()=>{const {saveCorrection}=await import('/static/app/corrections.js');const {state}=await import('/static/app/state.js');await saveCorrection();return state.case.correction_by;}),'tk-demo');
    await b.evaluate(()=>localStorage.setItem('ova.lease.demo.demo-case-2',JSON.stringify({tab_id:'other-tab',expires_at:Date.now()+45000})));
    await a.waitForFunction(()=>document.querySelector('[data-chip]').disabled);
    assert.equal(await a.locator('[data-action=save-correction]').isDisabled(),true);
    const allowed=await a.evaluate(async()=>{const {state}=await import('/static/app/state.js');return state.editing.allowed;});assert.equal(allowed,false);
    console.log('PASS: read-only correction cannot save; lease loss blocks tools, morphology and mutation boundary');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
