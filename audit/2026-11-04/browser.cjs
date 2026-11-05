const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {spawn}=require('child_process');
const {chromium}=require(path.resolve('node_modules/playwright-core'));
const out=__dirname, runtime=path.join(out,'runtime');fs.mkdirSync(runtime,{recursive:true});
const results={screens:[],flows:[],api:[],errors:[],checks:[]};
const log=fs.openSync(path.join(out,'server.log'),'a');
const child=spawn(path.resolve('.venv/Scripts/python.exe'),['-B','tests/serve_isolated_app.py'],{cwd:process.cwd(),env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',DATABASE_URL:'',APP_DATA_DIR:runtime,APP_DB_PATH:path.join(runtime,'audit.sqlite3'),APP_JWT_SECRET:'audit-only-isolated-jwt-20261104-32chars',APP_PATIENT_PID_HMAC_SECRET:'audit-only-isolated-pid-20261104',APP_DOCTOR_PASSWORD:'audit-doctor-only-2026',APP_ADMIN_PASSWORD:'audit-admin-only-2026',APP_DOCTOR_FACILITY_ID:'fac-vinmec-times-city',APP_SYNTHETIC_DEMO_MODE:'false',HOST:'127.0.0.1',PORT:'18047'},stdio:['ignore',log,log],windowsHide:true});
const base='http://127.0.0.1:18047';let browser;
const save=()=>fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify(results,null,2));
async function main(){
 for(let n=0;n<180;n++){try{if((await fetch(base+'/api/health/live')).ok)break;}catch{}if(child.exitCode!==null)throw Error('server exited');await new Promise(r=>setTimeout(r,500));}
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
 page.on('pageerror',e=>results.errors.push(e.stack));
 page.on('response',r=>{if(r.url().startsWith(base+'/api'))results.api.push({method:r.request().method(),path:new URL(r.url()).pathname,status:r.status()});});
 async function capture(name){await page.waitForTimeout(450);const data=await page.evaluate(()=>({hash:location.hash,title:document.querySelector('#page h1,h1')?.innerText,text:document.body.innerText,viewport:{w:innerWidth,h:innerHeight},scrollWidth:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('input,select,textarea,button,a')].filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,id:e.id,name:e.name,type:e.type,text:(e.innerText||'').slice(0,180),label:e.getAttribute('aria-label'),labels:e.labels?[...e.labels].map(x=>x.innerText):[],required:e.required,readOnly:e.readOnly,value:e.type==='password'?'<redacted>':e.value,disabled:e.disabled,box:{x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}}))}));data.name=name;results.screens.push(data);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});save();}
 await page.route('**/api/admin/backups/**',r=>r.abort('blockedbyclient'));
 async function nav(route,name){await page.goto(base+'/?audit='+Date.now()+'#'+route);await page.waitForTimeout(650);await capture(name||route.replaceAll('/','_'));}
 await nav('login');
 for(const r of ['register','forgot','reset','verify-email','first','expired'])await nav(r);
 await nav('login','login-return');let t=Date.now();await page.locator('[name=username]').fill('doctor');await page.locator('[name=password]').fill('audit-doctor-only-2026');await page.locator('#authForm button[type=submit]').click();await page.waitForFunction(()=>location.hash==='#dashboard');results.flows.push({name:'doctor login',actions:3,ms:Date.now()-t});await capture('dashboard');
 for(const r of ['intake','cases','approval','evaluation','notifications','help','preferences','profile','403','404','maintenance'])await nav(r,'doctor-'+r);
 await nav('intake','intake-seeds');await page.locator('[data-action=add-patient]').click();await capture('patient-create');
 const synthetic={full_name:'Audit Synthetic Alpha',birth_year:'1990',phone:'0901234567',hometown:'Synthetic audit town'};t=Date.now();
 for(const [k,v]of Object.entries(synthetic))await page.locator('#modal [name='+k+']').fill(v);
 await page.locator('#modal [name=gender]').selectOption('female');
 const pid=await page.locator('#modal [name=pid]').inputValue();await page.locator('#modal button[type=submit]').click();await capture('patient-created-upload');results.flows.push({name:'synthetic patient creation after modal open',actions:6,ms:Date.now()-t,pid});
 const storage=await page.evaluate(()=>Object.entries(localStorage).filter(([k])=>k.startsWith('ova.demo-patients')).map(([k,v])=>({key:k,value:JSON.parse(v)})));results.checks.push({name:'patient browser storage',data:storage});
 const other=await browser.newContext();const p2=await other.newPage();await p2.goto(base+'/#login');await p2.locator('[name=username]').fill('doctor');await p2.locator('[name=password]').fill('audit-doctor-only-2026');await p2.locator('#authForm button[type=submit]').click();await p2.waitForFunction(()=>location.hash==='#dashboard');await p2.goto(base+'/#intake');await p2.waitForTimeout(600);results.checks.push({name:'same user fresh browser patient visibility',pid,found:(await p2.locator('body').innerText()).includes(pid)});await other.close();
 const token=await page.evaluate(()=>sessionStorage.getItem('ova.token'));const headers={Authorization:'Bearer '+token};
 async function api(method,url,data){const r=await page.request.fetch(base+url,{method,headers:{...headers,'Idempotency-Key':crypto.randomUUID()},data});let body;try{body=await r.json()}catch{body=await r.text()}results.checks.push({name:method+' '+url,status:r.status(),body});save();return body;}
 const created=await api('POST','/api/cases',{patient_id:pid,study_date:'2026-11-04',active_ovary_side:'LEFT',contralateral_status:'NOT_VISUALIZED'});const id=created.study_id;
 if(id){await nav('case/'+id,'case-detail');await nav('viewer/'+id,'viewer-empty');await nav('report/'+id,'report-empty');}
 await api('POST','/api/generate-report',{});await api('POST','/api/v1/cdss/evaluate',{});
 for(const size of [[1920,1080],[1440,900],[1366,768],[768,1024],[390,844]]){await page.setViewportSize({width:size[0],height:size[1]});await nav('intake','intake-'+size[0]);await page.locator('[data-select="0"]').click();await capture('upload-'+size[0]);}
 await page.setViewportSize({width:1440,height:900});await nav('login','admin-login');await page.locator('[name=username]').fill('admin');await page.locator('[name=password]').fill('audit-admin-only-2026');await page.locator('#authForm button[type=submit]').click();await page.waitForTimeout(900);
 for(const r of ['reports','users','departments','models','audit','cases','settings','system'])await nav('admin/'+r,'admin-'+r);
 results.completed=true;
}
main().catch(e=>{results.fatal=e.stack;console.error(e);process.exitCode=1}).finally(async()=>{save();await browser?.close();child.kill();fs.closeSync(log);console.log(JSON.stringify({screens:results.screens.length,errors:results.errors,fatal:results.fatal}));});
