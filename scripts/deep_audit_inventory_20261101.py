"""Read-only source inventory for the 2026-11-01 audit; does not import app code."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/deep_audit_20261101'
OUT.mkdir(parents=True, exist_ok=True)
paths = subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.tmp*'], cwd=ROOT, text=True).splitlines()
extensions = {'.py','.js','.mjs','.cjs','.html','.css','.sql','.ps1','.yml','.yaml','.toml'}
files, endpoints, parse_errors, signals = [], [], [], []
for name in paths:
    path = ROOT/name
    if path.suffix not in extensions or any(part in {'artifacts','.tmp-verify-20261101','.impeccable','.taste-skill'} for part in path.parts):
        continue
    data = path.read_bytes()
    source = data.decode('utf-8-sig',errors='replace')
    files.append({'path':name,'lines':len(source.splitlines()),'sha256':hashlib.sha256(data).hexdigest(),'review':'automated inventory; manual coverage in report'})
    for number,line in enumerate(source.splitlines(),1):
        if any(token in line for token in ('console.log(', 'TODO', 'Lorem ipsum', 'FIXME')):
            signals.append({'path':name,'line':number,'kind':'manual triage required'})
    if path.suffix == '.py':
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if isinstance(decorator,ast.Call) and isinstance(decorator.func,ast.Attribute) and decorator.func.attr in {'get','post','put','patch','delete','websocket'}:
                            endpoints.append({'file':name,'line':node.lineno,'method':decorator.func.attr,'path':ast.unparse(decorator.args[0]) if decorator.args else '?','handler':node.name})
        except SyntaxError as exc:
            parse_errors.append({'file':name,'line':exc.lineno,'message':exc.msg})
result={'source_file_count':len(files),'source_lines':sum(f['lines'] for f in files),'route_decorator_count':len(endpoints),'syntax_errors':parse_errors,'files':files,'routes':endpoints,'scan_signals':signals}
(OUT/'source_inventory.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'files','routes','scan_signals'}}))
