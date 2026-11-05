import json,hashlib,re,csv
from pathlib import Path
out=Path(__file__).parent;root=Path.cwd()
browser=json.loads((out/'browser-results.json').read_text(encoding='utf-8'))
deep=json.loads((out/'deep-browser-results.json').read_text(encoding='utf-8'))
probe=json.loads((out/'probe-results.json').read_text(encoding='utf-8'))
tenant=json.loads((out/'tenant-results.json').read_text(encoding='utf-8'))
before=json.loads((out/'source-hashes-before.json').read_text())
changes=[p for p,h in before.items() if not (root/p).is_file() or hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
(out/'source-integrity.json').write_text(json.dumps({'baseline_files':len(before),'changed_or_deleted':changes},indent=2))
summary={'screens_captures':len(browser['screens'])+len(deep['screens']),'browser_errors':browser['errors']+deep['errors'],'flows':browser['flows']+deep['flows'],'deep_checks':deep['checks'],'patient_checks':[x for x in browser['checks'] if 'patient visibility' in x['name']],'api_probes':[{k:x.get(k) for k in ('name','status','ms')} for x in probe+tenant if 'path' in x]}
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[]
for screen in browser['screens']+deep['screens']:
 for c in screen['controls']:
  if c.get('tag') in ('INPUT','SELECT','TEXTAREA') or c.get('name') or c.get('id') in ('notes','morphology','oradsScore'):
   rows.append({'screen':screen['name'],**c})
(out/'field-inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
apiobs=browser['api']+deep['responses']+[x for x in probe+tenant if 'path' in x]
inv=json.loads((out/'inventory.json').read_text(encoding='utf-8'))
for api in inv['apis']:
 prefix='/api/v1' if api['file'].endswith('v1_endpoints.py') else '/api/hitl' if api['file'].endswith('/hitl.py') else '/api/evaluation' if api['file'].endswith('evaluation.py') else ''
 full=prefix+api['path'];pattern='^'+re.sub(r'\{[^}]+\}',r'[^/]+',full)+'$'
 hits=[o for o in apiobs if o['method']==api['method'] and re.match(pattern,o['path'])]
 api['effective_path']=full;api['status']='PARTIALLY TESTED' if hits else 'NOT TESTED';api['observed_statuses']=sorted(set(o['status'] for o in hits));api['evidence']='browser-results.json / deep-browser-results.json / probe-results.json / tenant-results.json' if hits else 'Source inventory only; no behavioral claim'
with (out/'api-coverage.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(inv['apis'][0]));w.writeheader();w.writerows(inv['apis'])
print(json.dumps({'integrity':changes,'captures':summary['screens_captures'],'flows':summary['flows'],'deep_checks':deep['checks'],'api_decorators_exercised':sum(x['status']=='PARTIALLY TESTED' for x in inv['apis']),'fields_snapshots':len(rows)},ensure_ascii=False,indent=2))
try:
 import fitz
 doc=fitz.open(out/'report-reviewed-print.pdf');report=[]
 for i,p in enumerate(doc):
  report.append({'page':i+1,'text':p.get_text(),'width':p.rect.width,'height':p.rect.height})
  p.get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(str(out/f'print-page-{i+1}.png'))
 (out/'print-text.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PDF pages',len(doc))
except ImportError: print('PDF text/render verification BLOCKED: PyMuPDF unavailable')
