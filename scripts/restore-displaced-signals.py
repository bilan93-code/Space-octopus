"""Recover earlier signal paths only where the revised copper permits them."""
import json,sys
from pathlib import Path
from shapely.strtree import STRtree

original,before_pruning,current,selected_path,out=map(Path,sys.argv[1:])
code=Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0]
def geometry(path):
    scope={};sys.argv=['check-copper.py',str(path),'/tmp/restore-unused.json']
    exec(compile(code,'copper_geometry','exec'),scope)
    return scope
old=geometry(original);now=geometry(current)
before=json.loads(before_pruning.read_text());selected=set(json.loads(selected_path.read_text()))
present={a['pcb_trace_id'] for a in before if a['type']=='pcb_trace'}
existing={a['pcb_trace_id'] for a in now['j'] if a['type']=='pcb_trace'}
items=[a for a in now['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in items])
bytrace={}
for a in old['items']:
    if a['kind'] in ['track','via']:bytrace.setdefault(a['id'].rsplit(':',1)[0],[]).append(a)
restored=[];blocked=[]
for t in old['bytype']['pcb_trace']:
    identity=t['pcb_trace_id'];net=t.get('connection_name') or old['trace_net'].get(t.get('source_trace_id'))
    if identity in present or identity in existing or old['nets'].get(net) in selected:continue
    assert identity.startswith(('finish_','saved_pcb_via_')),'Unexpected missing fixed route '+identity
    collisions=set()
    for a in bytrace.get(identity,[]):
        for k in tree.query(a['g'],predicate='dwithin',distance=.2):
            b=items[int(k)]
            if a['layer']==b['layer'] and a['net']!=b['net'] and a['g'].distance(b['g'])<.2-1e-5:collisions.add(b['id'])
    if collisions:blocked.append({'trace':identity,'net':old['nets'][net],'blockedBy':sorted(collisions)})
    else:restored.append(t)
result=[a for a in now['j'] if a['type']!='pcb_copper_pour']+restored
ids=[a['pcb_trace_id'] for a in result if a['type']=='pcb_trace'];assert len(ids)==len(set(ids))
out.write_text(json.dumps(result))
report={'restoredCount':len(restored),'blockedCount':len(blocked),'restored':[a['pcb_trace_id'] for a in restored],'blocked':blocked}
out.with_suffix('.restore.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='blocked'},indent=2))
