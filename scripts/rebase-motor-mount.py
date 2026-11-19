"""Reuse reviewed copper against the revised, freshly captured footprint pads."""
import json,sys,subprocess,collections
from pathlib import Path

work=Path('routing-work/motor-mount-revision')
fresh=json.loads((work/'fresh.circuit.json').read_text())
saved=json.loads((work/'baseline/data/routed-traces.json').read_text())
netid={a['name']:a['source_net_id'] for a in fresh if a['type']=='source_net'}
traceid={}
for a in fresh:
 if a['type']=='source_trace':
  for n in a.get('connected_source_net_ids',[]):traceid.setdefault(n,a['source_trace_id'])
raw=[]
for tr in saved['traces']:
 name=saved['netNamesById'].get(tr.get('connection_name'))
 if name not in netid:raise RuntimeError('Unmapped net '+str(name))
 n=netid[name]
 raw.append({'type':'pcb_trace','pcb_trace_id':tr['pcb_trace_id'],'connection_name':n,'source_trace_id':traceid[n],
             'route':[{k:v for k,v in p.items() if k not in ['pcb_port_id','start_pcb_port_id','end_pcb_port_id']} for p in tr['route']]})
base=[a for a in fresh if a['type'] not in ['pcb_trace','pcb_via','pcb_copper_pour','cad_component'] and 'error' not in a['type']]
path=work/'rebased.circuit.json';auditpath=work/'rebase-audit.json'
path.write_text(json.dumps(base+raw))
subprocess.run([sys.executable,'scripts/check-copper.py',str(path),str(auditpath)],stdout=subprocess.DEVNULL,check=False)
audit=json.loads(auditpath.read_text());bad=set();ids={tr['pcb_trace_id'] for tr in raw}
for c in audit['clearances']:
 for k in ['a','b']:
  ident=c[k].rsplit(':',1)[0]
  if ident in ids:bad.add(ident)
for c in audit['edges']+audit['holes']:
 ident=c['id'].rsplit(':',1)[0]
 if ident in ids:bad.add(ident)
protected=[i for i in bad if i.startswith('kelvin_')]
if protected:raise RuntimeError('Revised parts obstruct protected Kelvin pickups: '+str(protected))
kept=[tr for tr in raw if tr['pcb_trace_id'] not in bad]
path.write_text(json.dumps(base+kept))
(work/'removed-copper.json').write_text(json.dumps(sorted(bad),indent=2)+'\n')
print('Preserved',len(kept),'routes; removed',len(bad),'routes conflicting with revised pads.')
