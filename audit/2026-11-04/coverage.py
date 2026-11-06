import json,csv,re,subprocess,hashlib
from pathlib import Path
from collections import Counter
O=Path(__file__).parent;R=Path.cwd()
screens=[]
def scr(route,status,evidence,reason): screens.append(dict(route=route,status=status,evidence=evidence,reason=reason))
for a in ('login','register','verify-email','forgot','reset','first','expired'):
 scr('#'+a,'PARTIALLY TESTED',a+'.png; browser-results.json','Rendered form/text/controls; email/OTP/recovery execution not tested' if a!='login' else 'Doctor/admin login executed; exhaustive auth edge cases not tested')
for route,ev in [('dashboard','dashboard'),('intake','intake-seeds'),('cases','doctor-cases'),('case/:id','case-detail'),('viewer/:id','viewer-with-inference'),('report/:id','report-reviewed'),('notifications','doctor-notifications'),('help','doctor-help'),('preferences','doctor-preferences'),('profile','doctor-profile')]:
 scr('#'+route,'PARTIALLY TESTED',ev+'.png; browser-results.json; deep-browser-results.json','Screenshot/text/control scan; selected interactions only, not every modal/role/conditional state')
scr('#approval/:id','BLOCKED','doctor-approval.png','Doctor request reaches 403; actual reviewer/approval content not inspected')
scr('#evaluation','NOT TESTED','doctor-evaluation.png','Doctor redirected to dashboard; screenshot is NOT evidence evaluation content inspected')
for a in ('reports','users','departments','models','audit','cases','settings','system'):
 scr('#admin/'+a,'PARTIALLY TESTED','admin-'+a+'.png','Rendered section; write actions mostly not executed. Backup/list blocked intentionally.' if a=='system' else 'Rendered section; selected API/source checks, not complete CRUD/exports')
for a in ('403','404','maintenance'):scr('#'+a,'PARTIALLY TESTED','doctor-'+a+'.png','Direct error route rendered; not an actual service outage test')
scr('/slides','NOT TESTED','backend/app/main.py','Secondary presentation asset route discovered; not inspected live')
features=[]
def feat(n,status,ev,reason):features.append(dict(feature=n,status=status,evidence=ev,reason=reason))
for n,ev in [('Doctor/admin login','browser-results.json'),('Create patient local persistence boundary','browser-results.json'),('Fresh-context patient visibility','browser-results.json'),('Patient-store stale update reproduction','store-probe-results.json'),('Patient-store empty reopening reproduction','store-probe-results.json'),('Scoped-admin global settings boundary','tenant-results.json'),('Cross-facility identical PID identity mapping','tenant-results.json; probe-results.json'),('Cross-facility case read denial','tenant-results.json'),('Single-side case creation','probe-results.json'),('Synthetic source-image upload','probe-results.json'),('Whole-image classifier abstention','probe-results.json'),('Single image review save/reopen','deep-browser-results.json'),('Network failure save feedback/draft','deep-browser-results.json'),('Clinical PDF explicit 501 boundary','probe-results.json'),('CDSS missing descriptor fail-closed','probe-results.json'),('Unauthenticated case denial','probe-results.json'),('Browser RUO print handler','final-browser-results.json; actual-print.pdf'),('Profile password-change session continuity','deep-browser-results.json')]:
 feat(n,'TESTED',ev,'Tested only the named bounded scenario; not full feature/regression coverage')
for n,ev in [('Segmentation inference/geometry','probe-results.json'),('Manual scale calibration persistence','probe-results.json'),('Desktop/tablet/mobile layout','browser-results.json; deep-browser-results.json'),('Patient demographic validation fields','field-inventory.json'),('Account bootstrap password durability','source-evidence.md'),('Report saved data and laterality','actual-print-text.json'),('Administration analytics/metrics','admin-reports.png'),('Administrative users/departments/model registry','browser-results.json'),('Audit events list','admin-audit.png'),('Notifications/empty state','doctor-notifications.png'),('Keyboard/a11y controls','field-inventory.json; source-evidence.md'),('Voice local-only guard','node-tests.log'),('Model/data provenance and loss protocol','source-evidence.md'),('CUA visible browser observation','cua-state.json')]:
 feat(n,'PARTIALLY TESTED',ev,'Selected source/runtime/layout observations; remaining branches explicitly untested')
for n,reason in [('SMTP registration/OTP/reset','No verified isolated SMTP target'),('PostgreSQL/Docker runtime','No verified isolated service'),('Backup archive/restore','Backup default path outside audit'),('Clinical validation/signature workflow','RUO capabilities disabled; no clinical validation package')]:feat(n,'BLOCKED','REPORT.md §8',reason)
for n in ['Full bilateral consecutive-patient UI workflow','UI Create Visit reservation/lost response replay','Nonempty-mask drawing/eraser/undo gesture matrix','Native microphone/touch/actual browser zoom','Reviewer approval/correction workflow','Evaluation/clinical external dataset review']:
 feat(n,'NOT TESTED','REPORT.md §8','No execution in this audit; no pass claimed')
def write(name,rows):
 with (O/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write('SCREEN_COVERAGE.csv',screens);write('FEATURE_COVERAGE.csv',features)
issues=json.loads((O/'issues.json').read_text(encoding='utf-8'))
sourcefiles=set();excerpt=['# Source evidence snapshot','', 'Line numbers correspond to the current dirty worktree on 2026-11-04. No remediation applied.','']
for i in issues:
 refs=re.findall(r'\[([^\]]+):(\d+)\]\(\.\./\.\./',i['Evidence'])
 for file,line in refs:
  sourcefiles.add(file);lines=(R/file).read_text(encoding='utf-8-sig').splitlines();line=int(line);start=max(1,line-3);end=min(len(lines),line+14)
  excerpt += [f"## {i['Issue_ID']} — {file}:{line}",'','```text']+[f'{n}: {lines[n-1]}' for n in range(start,end+1)]+['```','']
(O/'source-evidence.md').write_text('\n'.join(excerpt),encoding='utf-8')
inv=json.loads((O/'inventory.json').read_text(encoding='utf-8'))
reviewed=sourcefiles|{'backend/app/main.py','backend/app/config.py','backend/app/security.py','backend/services/facility_service.py','backend/services/preprocessor.py','backend/services/inference_engine.py','backend/services/image_classifier.py','backend/services/disease_classifier.py','backend/services/model_service.py','backend/services/cdss_engine.py','backend/schemas/schemas.py','backend/app/routers/visits.py','backend/app/routers/reviews.py','backend/app/routers/v1_endpoints.py','backend/app/routers/inference.py','backend/app/routers/cases.py','backend/app/routers/health.py','frontend/app/navigation.js','frontend/app/state.js','frontend/app/leases.js','frontend/app/voice-dictation.js','frontend/app/environment-notices.js','frontend/app/research-report-draft.js','frontend/app/patients.js','frontend/app/main.js','frontend/app/demo-patients.js','tests/serve_isolated_app.py','tests/conftest.py','tests/helpers/isolated_browser.cjs','tests/helpers/synthetic_fixtures.cjs'}
module=[]
for file in inv['files']:
 module.append(dict(file=file,status='PARTIALLY TESTED' if file in reviewed else 'NOT TESTED',reason='Relevant excerpts inspected; module not exhaustively audited' if file in reviewed else 'Inventory/discovery only; runtime may exercise imports but no full-file audit claim'))
write('MODULE_COVERAGE.csv',module)
allfiles=subprocess.check_output(['rg','--files','-g','!audit/**'],text=True,encoding='utf-8',errors='replace');(O/'repository-files.txt').write_text(allfiles,encoding='utf-8')
inputs=[]
for p in (R/'frontend').rglob('*'):
 if p.suffix not in ('.html','.js'):continue
 text=p.read_text(encoding='utf-8-sig')
 for m in re.finditer(r'<(?:input|select|textarea)\b[^>]*>',text,re.I):
  inputs.append(dict(file=p.relative_to(R).as_posix(),line=text[:m.start()].count('\n')+1,markup=m.group(0),status='PARTIALLY TESTED' if p.relative_to(R).as_posix() in reviewed else 'NOT TESTED',reason='Source markup inventory; dynamic templates and unrendered states not behaviorally certified'))
(O/'input-source-inventory.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2),encoding='utf-8')
summary={'screens_discovered':len(screens),'screens_content_inspected_partially':sum(x['status']=='PARTIALLY TESTED' for x in screens),'screen_statuses':dict(Counter(x['status'] for x in screens)),'features_discovered':len(features),'features_tested_bounded':sum(x['status']=='TESTED' for x in features),'features_exercised_or_inspected':sum(x['status'] in ('TESTED','PARTIALLY TESTED') for x in features),'feature_statuses':dict(Counter(x['status'] for x in features)),'source_input_occurrences':len(inputs),'defects':len(issues),'severity':dict(Counter(x['Severity'] for x in issues))}
(O/'coverage-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
report=(O/'REPORT.md').read_text(encoding='utf-8')
for name,start,end in [('FRICTION_REPORT.md','## 5.','## 6.'),('DATA_BUSINESS_REPORT.md','## 6.','## 7.'),('AI_SAFETY_REPORT.md','## 7.','## 8.'),('USER_FLOW_REPORT.md','## 4.','## 5.')]:
 content=report[report.index(start):report.index(end)];(O/name).write_text(content+'\nSee [full report](REPORT.md) and [complete issue register](ISSUE_REGISTER.md) for evidence, priorities and limitations.\n',encoding='utf-8')
before=json.loads((O/'source-hashes-before.json').read_text());changed=[p for p,h in before.items() if not (R/p).is_file() or hashlib.sha256((R/p).read_bytes()).hexdigest()!=h]
(O/'source-integrity.json').write_text(json.dumps({'baseline_files':len(before),'changed_or_deleted':changed},indent=2))
assert not changed,changed
assert len(issues)==len(set(i['Issue_ID'] for i in issues))
assert len(screens)==31 and len(features)==42
assert all(i['Evidence'] and i['Root_Cause'] and i['Recommendation'] for i in issues)
print(json.dumps(summary,ensure_ascii=True,indent=2));print('Source integrity and register checks PASS')
