const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
    const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'});
    const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const go=async route=>{await page.evaluate(r=>location.hash='#'+r,route);await page.waitForTimeout(400);};
    const demo=async role=>{await go('login');await page.locator('[data-action=demo-'+role+']').click();await page.locator('h1').filter({hasText:'Tổng quan'}).waitFor();};
    const shot=name=>page.screenshot({path:path.resolve('artifacts/workspace-v2/'+name+'.png'),fullPage:true});
    try{
        await page.goto('http://127.0.0.1:8027/#login');await demo('BS');
        await go('notifications');assert.equal(await page.locator('#notificationsData a[href="#case/demo-case-1"]').count(),1,'Case notification must have a working link');
        await page.locator('[data-action=read-all]').click();assert.equal(await page.locator('[data-read]:disabled').count(),2);await shot('13-notifications-read');
        await go('patients');await page.locator('details[data-comparison]').first().click();await page.locator('#visitOpacity').waitFor();await shot('10-patient-comparison');
        await go('cases');await page.locator('#selectAll').check();assert.match(await page.locator('#selectionCount').textContent(),/Đã chọn/);await page.locator('[data-action=save-filter]').click();await shot('04-worklist-selected');
        await go('viewer/demo-case-1');await page.locator('#viewport').waitFor();await page.waitForTimeout(300);
        const second=await context.newPage();second.on('pageerror',e=>errors.push(e.message));await second.goto('http://127.0.0.1:8027/#login');await second.locator('[data-action=demo-BS]').click();await second.evaluate(()=>location.hash='#viewer/demo-case-1');await second.locator('#viewport').waitFor();assert.equal(await second.locator('[data-tool=brush]').isDisabled(),true,'A second tab must be read-only');await second.close();
        await demo('TK');await go('approval/demo-case-2');await page.locator('[data-action=correct]').click();await page.locator('#modal textarea').fill('Rà soát đường biên trên phiên bản mới');await page.locator('#modal button[type=submit]').click();await page.locator('[data-action=save-correction]').waitFor();await page.waitForTimeout(350);
        assert.equal(await page.locator('[data-tool=brush]').isEnabled(),true);await page.locator('[data-action=side-R]').click();await page.waitForTimeout(350);
        const before=await page.evaluate(async()=>{const {state}=await import('/static/app/state.js');return state.case.versions[0].images.find(i=>i.laterality==='R').mask.reduce((n,v)=>n+v,0);});
        await page.locator('[data-tool=clear]').click();await page.locator('#modal button[value=confirm]').click();
        assert.equal(await page.evaluate(async()=>{const {state}=await import('/static/app/state.js');return state.case.versions[0].images.find(i=>i.laterality==='R').mask.reduce((n,v)=>n+v,0);}),before,'Old version must remain immutable');
        await shot('07-correction-version');await page.locator('[data-action=save-correction]').click();await page.locator('h2').filter({hasText:'Lịch sử phiên bản'}).waitFor();
        await demo('QT');await go('notifications');assert.equal(await page.locator('#notificationsData a[href^="#case/"]').count(),0,'QT must not have clinical case links');
        await go('admin/users');await page.locator('[data-action=add-user]').click();await page.locator('#modal [name=username]').fill('new.demo');await page.locator('#modal [name=full_name]').fill('Tài khoản thử');await page.locator('#modal [name=department]').fill('Kỹ thuật');await page.locator('#modal button[type=submit]').click();await page.getByText('new.demo',{exact:true}).waitFor();
        await page.locator('tr').filter({hasText:'new.demo'}).locator('[data-delete]').click();await page.locator('#modal button[value=confirm]').click();await page.waitForTimeout(200);assert.equal(await page.getByText('new.demo',{exact:true}).count(),0);
        await go('admin/departments');await page.locator('[data-action=add-dept]').click();await page.locator('#modal [name=id]').fill('TEST');await page.locator('#modal [name=name]').fill('Khoa thử');await page.locator('#modal button[type=submit]').click();await page.locator('#adminData').getByText('Khoa thử',{exact:true}).waitFor();await page.locator('[data-delete-dept="TEST"]').click();await page.locator('#modal button[value=confirm]').click();await page.waitForTimeout(200);assert.equal(await page.locator('#adminData').getByText('Khoa thử',{exact:true}).count(),0);
        await go('admin/cases');assert.equal(await page.locator('#metadataRows img').count(),0);await shot('12-admin-metadata');
        await go('admin/audit');await page.locator('[name=action]').selectOption('MASK_EDIT');await page.waitForTimeout(300);await shot('12-admin-audit-filter');
        assert.deepEqual(errors,[]);console.log('PASS: notifications, visit overlay, worklist selection, cross-tab read-only, TK version preservation, user/department CRUD, QT metadata-only');
    }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
