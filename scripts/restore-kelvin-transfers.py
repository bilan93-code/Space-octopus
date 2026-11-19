"""Protect the plated barrels as well as the wires of every Kelvin branch."""
import json,sys,collections
from pathlib import Path
from shapely.geometry import Point,LineString
path=Path(sys.argv[1]);s={};old=sys.argv;sys.argv=['check-copper.py',str(path),'/tmp/kelvin-unused']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s);sys.argv=old
base=json.loads(Path('routing-work/motor-mount-revision/baseline/data/routed-traces.json').read_text());guard=collections.defaultdict(list)
for tr in base['traces']:
 if not tr['pcb_trace_id'].startswith('kelvin_'):continue
 for a,b in zip(tr['route'],tr['route'][1:]):
  if a['route_type']==b['route_type']=='wire':guard[tr['connection_name']].append(LineString([(a['x'],a['y']),(b['x'],b['y'])]).buffer(b['width']/2))
ids={a.get('pcb_trace_id') for a in s['j']};netid={v:k for k,v in s['nets'].items()};traceid={n:a['source_trace_id'] for a in s['bytype']['source_trace'] for n in a.get('connected_source_net_ids',[])};new=[];geometries=[]
for tr in base['traces']:
 if tr['pcb_trace_id'] in ids:continue
 for v in tr['route']:
  if v['route_type']!='via':continue
  g=Point(v['x'],v['y']).buffer(v['via_diameter']/2,quad_segs=32)
  if any(g.intersects(w) for w in guard[tr['connection_name']]):
   n=netid[base['netNamesById'][tr['connection_name']]];new.append({**tr,'connection_name':n,'source_trace_id':traceid[n]});geometries.append((n,g));break
bad={'seed_50006_wire0','finish_527_wire1'}
baseline_ids={a['pcb_trace_id'] for a in base['traces']}
if '--preserve-ground' not in sys.argv:
 for a in s['j']:
  if a['type']=='pcb_trace' and a['pcb_trace_id'].startswith('finish_') and a['pcb_trace_id'] not in baseline_ids and s['nets'].get(s['trace_net'].get(a.get('source_trace_id')) or a.get('connection_name'))=='GND':bad.add(a['pcb_trace_id'])
print('Pickup barrels needing restoration:',[v['pcb_trace_id'] for v in new],flush=True)
for a in s['items']:
 if a['kind']=='pour':continue
 if any(a['net']!=n and a['g'].distance(g)<.2-1e-5 for n,g in geometries):
  if a['kind']=='pad' or a['id'].startswith('kelvin_'):raise RuntimeError('Cannot restore Kelvin via: '+a['id']+' '+s['portlabel'](a.get('port')))
  bad.add(a['id'].rsplit(':',1)[0])
j=[a for a in s['j'] if a['type']!='pcb_copper_pour' and a.get('pcb_trace_id') not in bad];path.write_text(json.dumps(j+new));print('Restored',len(new),'protected pickup barrels; displaced copper:',sorted(bad))
