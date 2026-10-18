const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
const base=process.env.E2E_BASE_URL||'http://127.0.0.1:8027';
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});const page=await browser.newPage();try{
    await page.goto(base+'/#login');
    const result=await page.evaluate(async()=>{const {request}=await import('/static/app/api.js');const fetchOriginal=window.fetch;try{window.fetch=async()=>({status:200,ok:true,json:async()=>{throw new DOMException('Body read aborted','AbortError');}});try{await request('/contract-abort');return 'unexpected success';}catch(e){return e.name;}}finally{window.fetch=fetchOriginal;}});
    assert.equal(result,'AbortError');console.log('PASS: aborted JSON body cannot become a successful empty API response');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
