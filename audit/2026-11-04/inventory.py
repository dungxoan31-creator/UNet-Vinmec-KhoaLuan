import ast, hashlib, json, re, subprocess
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / 'audit/2026-11-04'
OUT.mkdir(parents=True, exist_ok=True)
files = [p for base in ('backend','frontend','ai_training','tests','deploy') for p in (ROOT/base).rglob('*') if p.is_file() and not any(x in p.parts for x in ('__pycache__','node_modules'))]
hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'source-hashes-before.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
apis, entities = [], []
for p in (ROOT/'backend').rglob('*.py'):
    try: tree=ast.parse(p.read_text(encoding='utf-8-sig'))
    except (SyntaxError, UnicodeError): continue
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('get','post','put','patch','delete') and d.args and isinstance(d.args[0],ast.Constant):
                    apis.append(dict(file=p.relative_to(ROOT).as_posix(),line=d.lineno,method=d.func.attr.upper(),path=d.args[0].value,function=node.name,status='NOT TESTED'))
        if isinstance(node,ast.ClassDef):
            for s in node.body:
                if isinstance(s,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__tablename__' for t in s.targets):
                    entities.append(dict(file=p.relative_to(ROOT).as_posix(),line=node.lineno,entity=node.name,table=ast.literal_eval(s.value),status='PARTIALLY TESTED'))
inv=dict(files=list(hashes),apis=apis,entities=entities,counts=dict(files=len(files),apis=len(apis),entities=len(entities)),git_status=subprocess.check_output(['git','status','--porcelain'],text=True),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
(OUT/'inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8')
print(inv['counts'])
