"""Give relocated bypass pads short plane access, preserving Kelvin isolation."""
import json,sys,math
from pathlib import Path
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
path=Path(sys.argv[1]);s={'__name__':'ground_geometry'};old=sys.argv;sys.argv=['check-copper.py',str(path),'/tmp/ground-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s);sys.argv=old
j=[a for a in s['j'] if a['type']!='pcb_copper_pour'];n=next(k for k,v in s['nets'].items() if v=='GND');tid=next(t['source_trace_id'] for t in j if t['type']=='source_trace' and n in t.get('connected_source_net_ids',[]));copper=[a for a in s['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in copper]);guard=unary_union([a['g'] for a in copper if a['net']==n and a['id'].startswith('kelvin_')]);drills=[]
for a in j:
 if a['type']=='pcb_trace':drills.extend((p['x'],p['y'],p.get('via_hole_diameter',.2)/2) for p in a['route'] if p['route_type']=='via')
 elif a['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in a:drills.append((a['x'],a['y'],a['hole_diameter']/2))
count=0
for pad in s['bytype']['pcb_smtpad']:
 pid=pad.get('pcb_port_id')
 if s['portnet'].get(pid)!=n:continue
 label=s['portlabel'](pid)
 if label in ['U2.10','U2.11','U2.20']:continue
 x,y=pad['x'],pad['y'];p=Point(x,y);g=p.buffer(.2,quad_segs=32)
 if not label.startswith('RSH') and g.distance(guard)<.25:continue
 if any(math.hypot(x-a,y-b)<r+.1+.2-1e-5 for a,b,r in drills):continue
 if any(copper[int(k)]['net']!=n and g.distance(copper[int(k)]['g'])<.2-1e-5 for k in tree.query(g,predicate='dwithin',distance=.2)):continue
 j.append({'type':'pcb_trace','pcb_trace_id':'plane_stitch_mount_'+str(count),'connection_name':n,'source_trace_id':tid,'route':[{'route_type':'wire','x':x,'y':y,'layer':pad['layer'],'width':.15},{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'top','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner1','width':.15}]});drills.append((x,y,.1));count+=1
path.write_text(json.dumps(j));print('Added',count,'local reference vias, with filled/capped via-in-pad manufacture required.')
