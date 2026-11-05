import os, sys, json, time, subprocess, sqlite3, uuid, io
from pathlib import Path
import httpx
from PIL import Image
import numpy as np

ROOT=Path.cwd(); OUT=ROOT/'audit/2026-11-04'; RUN=OUT/'probe-runtime'; RUN.mkdir(exist_ok=True)
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','DATABASE_URL':'','APP_DATA_DIR':str(RUN),'APP_DB_PATH':str(RUN/'probe.sqlite3'),'APP_JWT_SECRET':'audit-isolated-probe-jwt-20261104-at-least32','APP_PATIENT_PID_HMAC_SECRET':'audit-isolated-probe-pid-20261104-at-least32','APP_DOCTOR_PASSWORD':'audit-probe-doctor-2026','APP_ADMIN_PASSWORD':'audit-probe-admin-2026','APP_DOCTOR_FACILITY_ID':'fac-vinmec-times-city','APP_SYNTHETIC_DEMO_MODE':'false','HOST':'127.0.0.1','PORT':'18048'}
log=(OUT/'probe-server.log').open('w'); child=subprocess.Popen([sys.executable,'-B','tests/serve_isolated_app.py'],env=env,stdout=log,stderr=log)
results=[]; client=httpx.Client(base_url='http://127.0.0.1:18048',timeout=180)
def call(name,method,url,headers=None,**kwargs):
    start=time.monotonic(); r=client.request(method,url,headers=headers,**kwargs)
    try: body=r.json()
    except ValueError: body=r.text[:1000]
    results.append(dict(name=name,method=method,path=url,status=r.status_code,ms=round((time.monotonic()-start)*1000),body=body)); (OUT/'probe-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');return body
try:
    for _ in range(180):
        try:
            if client.get('/api/health/live').is_success: break
        except httpx.TransportError: pass
        if child.poll() is not None: raise RuntimeError('isolated server exited')
        time.sleep(.5)
    doctor=client.post('/api/auth/login',json={'username':'doctor','password':env['APP_DOCTOR_PASSWORD']}).json(); dh={'Authorization':'Bearer '+doctor['access_token']}
    admin=client.post('/api/auth/login',json={'username':'admin','password':env['APP_ADMIN_PASSWORD']}).json(); ah={'Authorization':'Bearer '+admin['access_token']}
    # Provision only synthetic audit identities directly in the isolated SQLite database.
    conn=sqlite3.connect(RUN/'probe.sqlite3');conn.execute('PRAGMA foreign_keys=ON')
    conn.execute("INSERT OR IGNORE INTO facilities(id,facility_code,name,is_active) VALUES('AUDIT-B','AUDIT-B','Synthetic facility B',1)")
    aid=str(uuid.uuid4());bid=str(uuid.uuid4());
    for uid,username,facility,role in [(aid,'audit-scoped-admin','fac-vinmec-times-city','ADMIN'),(bid,'audit-b-doctor','AUDIT-B','DOCTOR')]:
        conn.row_factory=sqlite3.Row
        values=dict(conn.execute('SELECT * FROM users WHERE username=?',('admin' if role=='ADMIN' else 'doctor',)).fetchone())
        values.update(id=uid,username=username,full_name='Synthetic audit identity',role=role,facility_id=facility,is_active=1,must_change_password=0,is_global_admin=0,token_version=0,email=None)
        conn.execute('DELETE FROM users WHERE username=?',(username,))
        columns=list(values);conn.execute('INSERT INTO users('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',list(values.values()))
    conn.commit()
    scoped=client.post('/api/auth/login',json={'username':'audit-scoped-admin','password':env['APP_ADMIN_PASSWORD']}).json(); sh={'Authorization':'Bearer '+scoped['access_token']}
    bdoc=client.post('/api/auth/login',json={'username':'audit-b-doctor','password':env['APP_DOCTOR_PASSWORD']}).json(); bh={'Authorization':'Bearer '+bdoc['access_token']}
    call('scoped admin metadata global counts','GET','/api/admin/metadata',sh)
    call('scoped admin settings read','GET','/api/admin/settings',sh)
    call('scoped admin global setting write','PUT','/api/admin/settings',sh,json={'report_header':'AUDIT FACILITY A HEADER','unit':'auto'})
    call('global admin sees scoped write','GET','/api/admin/settings',ah)
    call('scoped departments membership','GET','/api/admin/departments',sh)
    created=call('create left case','POST','/api/cases',{**dh,'Idempotency-Key':str(uuid.uuid4())},json={'patient_id':'123456789','study_date':'2026-11-04','active_ovary_side':'LEFT','contralateral_status':'NOT_VISUALIZED'})
    sid=created['study_id'];call('other tenant case blocked','GET',f'/api/cases/{sid}',bh)
    second=call('other facility same local PID','POST','/api/cases',{**bh,'Idempotency-Key':str(uuid.uuid4())},json={'patient_id':'123456789','study_date':'2026-11-04','active_ovary_side':'LEFT','contralateral_status':'NOT_VISUALIZED'})
    results.append({'name':'cross facility identical local PID maps same patient','equal':created['patient_id']==second.get('patient_id'),'patient_a':created['patient_id'],'patient_b':second.get('patient_id')})
    tab=str(uuid.uuid4());pageid=str(uuid.uuid4());lease=call('acquire lease','POST',f'/api/workspace/cases/{sid}/lease',dh,json={'tab_id':tab,'page_instance_id':pageid})
    wh={**dh,'X-Case-Lease-Token':lease['lease_token'],'X-Case-Page-Instance-Id':pageid}
    rng=np.random.default_rng(42);pixels=rng.integers(20,170,(480,640),dtype=np.uint8);yy,xx=np.ogrid[:480,:640];pixels[((xx-320)/100)**2+((yy-240)/70)**2<1]=35
    buff=io.BytesIO();Image.fromarray(pixels).save(buff,format='PNG');(OUT/'synthetic-audit.png').write_bytes(buff.getvalue())
    upload=call('upload nonsquare synthetic','POST','/api/upload',{**wh,'Idempotency-Key':str(uuid.uuid4())},data={'study_id':sid,'laterality':'L'},files={'file':('synthetic-audit.png',buff.getvalue(),'image/png')})
    if upload.get('image_id'):
        iid=upload['image_id']; pred=call('predict real checkpoint synthetic','POST',f'/api/predict/{iid}',wh)
        call('cross tenant image blocked','GET',f'/api/images/{iid}/viewer-source',bh)
        call('classify synthetic whole image','POST',f'/api/images/{iid}/classify',wh)
        call('calibrate after inference','POST',f'/api/images/{iid}/calibrate?pixel_spacing_mm=0.1',wh)
        call('case reopen after calibration','GET',f'/api/cases/{sid}',dh)
        call('release API lease','DELETE',f'/api/workspace/cases/{sid}/lease',dh,json={'lease_token':lease['lease_token'],'page_instance_id':pageid})
        (OUT/'case-for-browser.json').write_text(json.dumps({'study_id':sid,'image_id':iid,'base':'http://127.0.0.1:18048'}),encoding='utf-8')
    call('clinical PDF explicitly unsupported','POST','/api/generate-report',dh,json={})
    call('missing descriptors fail closed','POST','/api/v1/cdss/evaluate',dh,json={})
    call('unauthenticated case blocked','GET',f'/api/cases/{sid}')
    # Keep alive for the separate browser UI exercise; marker is confined to audit.
    (OUT/'probe-ready.json').write_text(json.dumps({'pid':child.pid,'study_id':sid}),encoding='utf-8')
    print('PROBES COMPLETE; server retained for bounded browser check',flush=True)
    time.sleep(240)
except Exception as e:
    results.append({'fatal':repr(e)});raise
finally:
    (OUT/'probe-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');client.close();child.terminate();child.wait(timeout=20);log.close()
