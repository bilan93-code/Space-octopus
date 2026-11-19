"""Merge the four repaired nets after the main routing pass, preserving fixed copper."""
import json,sys
from pathlib import Path
from shapely.strtree import STRtree

main=Path(sys.argv[1]);repair=Path(sys.argv[2]);out=Path(sys.argv[3])
selected_names=json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv)>4 else ['GND','V3V3','DRV_ENABLE','IU_RAW']
j=json.loads(main.read_text());r=json.loads(repair.read_text())
names={a['source_net_id']:a['name'] for a in j if a['type']=='source_net'}
selected={k for k,v in names.items() if v in selected_names}
assert len(selected)==len(set(selected_names)),'Unknown selected repair net.'
def net(a):return a.get('connection_name',a.get('source_net_id'))
fixed=[a for a in j if a['type'] not in ['pcb_trace','pcb_via','pcb_copper_pour'] or a['type'] in ['pcb_trace','pcb_via'] and net(a) not in selected]
numbers=[int(a['pcb_trace_id'].split('_')[1]) for a in j if a['type']=='pcb_trace' and a['pcb_trace_id'].startswith('finish_')]
counter=max(numbers,default=0)+1
for a in r:
    if a['type'] not in ['pcb_trace','pcb_via'] or net(a) not in selected:continue
    if a['type']=='pcb_trace' and a['pcb_trace_id'].startswith('finish_'):
        a={**a,'pcb_trace_id':'finish_'+str(counter)};counter+=1
    fixed.append(a)
out.write_text(json.dumps(fixed))
s={};sys.argv=['check-copper.py',str(out),'/tmp/local-merge-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
foreign=[a for a in s['items'] if a['net'] not in selected]
tree=STRtree([a['g'] for a in foreign]);bad=set()
wide={a['pcb_trace_id'] for a in s['bytype']['pcb_trace'] if any(v.get('width',0)>=2 for v in a['route'])}
for a in s['items']:
    if a['net'] not in selected:continue
    for k in tree.query(a['g'],predicate='dwithin',distance=.2):
        b=foreign[int(k)]
        if a['layer']!=b['layer'] or a['g'].distance(b['g'])>=.2-1e-5:continue
        ident=b['id'].rsplit(':',1)[0]
        if b['kind']=='pad' or b['kind']=='via' and b['g'].bounds[2]-b['g'].bounds[0]>=.59 or ident.startswith(('seed_','kelvin_','plane_stitch_')) or ident in wide:raise RuntimeError('Repair conflicts with protected copper '+ident)
        bad.add(ident)
out.write_text(json.dumps([a for a in fixed if a.get('pcb_trace_id',a.get('pcb_via_id')) not in bad]))
ids=[a['pcb_trace_id'] for a in fixed if a['type']=='pcb_trace']
assert len(ids)==len(set(ids)),'Merged trace IDs are not unique.'
print('Merged repaired nets; displaced',len(bad),'later signal routes:',sorted(bad))
