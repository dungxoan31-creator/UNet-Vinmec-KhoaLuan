import sqlite3,json,httpx,uuid
from pathlib import Path
out=Path(__file__).parent
db=sqlite3.connect(out/'probe-runtime/probe.sqlite3')
db.execute("UPDATE users SET token_version=1,tokens_revoked_at=NULL WHERE username IN ('audit-scoped-admin','audit-b-doctor')");db.commit();db.close()
c=httpx.Client(base_url='http://127.0.0.1:18048');results=[]
def login(u,p):
    r=c.post('/api/auth/login',json={'username':u,'password':p});r.raise_for_status();return {'Authorization':'Bearer '+r.json()['access_token']}
sh=login('audit-scoped-admin','audit-probe-admin-2026');bh=login('audit-b-doctor','audit-probe-doctor-2026');ah=login('admin','audit-probe-admin-2026')
def request(n,m,u,h,**kw):
    r=c.request(m,u,headers={**h,'Idempotency-Key':str(uuid.uuid4())},**kw);results.append(dict(name=n,method=m,path=u,status=r.status_code,body=r.json()));return r.json()
request('scoped admin global counts','GET','/api/admin/metadata',sh)
request('scoped admin changes global report header','PUT','/api/admin/settings',sh,json={'report_header':'AUDIT FACILITY A GLOBAL HEADER','unit':'auto'})
request('global admin observes facility write','GET','/api/admin/settings',ah)
request('scoped admin departments','GET','/api/admin/departments',sh)
sid=json.loads((out/'case-for-browser.json').read_text())['study_id']
request('other facility cannot read case','GET',f'/api/cases/{sid}',bh)
request('same source PID at unrelated facility','POST','/api/cases',bh,json={'patient_id':'123456789','study_date':'2026-11-04','active_ovary_side':'LEFT','contralateral_status':'NOT_VISUALIZED'})
(out/'tenant-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print([(r['name'],r['status']) for r in results])
