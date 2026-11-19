"""Escape the clock output around opposite-face phase copper using a dogbone."""
import json,sys,math
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.strtree import STRtree
target_ref=sys.argv[3] if len(sys.argv)>3 else 'U18';target_pin=int(sys.argv[4]) if len(sys.argv)>4 else 7
src=Path(sys.argv[1]);out=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/encoder-clock-escape.circuit.json');s={'__name__':'clock_escape'};sys.argv=['check-copper.py',str(src),'/tmp/unused-clock-escape.json'];exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'clock_escape','exec'),s)
j=s['j'];port=next(p for p in s['ports'].values() if s['sources'].get(s['sourceports'].get(p.get('source_port_id'),{}).get('source_component_id'))==target_ref and s['sourceports'][p['source_port_id']].get('pin_number')==target_pin);net=s['portnet'][port['pcb_port_id']];face=port['layers'][0];placement=json.load(open('data/placement.json'));cx,cy=placement[target_ref]['bodyCenter'];copper=[a for a in s['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in copper]);drills=[]
for a in j:
 if a['type']=='pcb_trace':drills.extend((v['x'],v['y'],v.get('via_hole_diameter',.3)/2,a['pcb_trace_id']) for v in a['route'] if v['route_type']=='via')
 elif a['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in a:drills.append((a['x'],a['y'],a['hole_diameter']/2,a.get('pcb_via_id',a.get('pcb_plated_hole_id',a.get('pcb_hole_id')))))
options=[]
for dx in [-4.,-3.,-2.5,-2.,-1.5,-1.,-.5,0,.5,1.,1.5,2.,2.5,3.,4.]:
 for dy in [-4.,-3.,-2.5,-2.,-1.5,-1.,-.5,0,.5,1.,1.5,2.,2.5,3.,4.]:
  x,y=port['x']+dx,port['y']+dy;points=[(port['x'],port['y']),(x,port['y']),(x,y)];vg=Point(x,y).buffer(.2,quad_segs=32);wg=LineString(points).buffer(.075,quad_segs=32);hits=[]
  for g,ls in [(vg,s['layers']),(wg,[face])]:
   hits.extend(copper[int(k)] for k in tree.query(g,predicate='dwithin',distance=.2) if copper[int(k)]['net']!=net and copper[int(k)]['layer'] in ls and g.distance(copper[int(k)]['g'])<.2-1e-5)
  rip={a['id'].rsplit(':',1)[0] for a in hits}
  if len(rip)>3 or any(not identity.startswith('finish_') for identity in rip):continue
  if any(identity not in rip and math.hypot(x-a,y-b)<r+.1+.2-1e-5 for a,b,r,identity in drills):continue
  options.append((abs(dx)+abs(dy)+4*len(rip),x,y,points,rip))
if not options:raise RuntimeError('No clock output escape avoids protected copper')
_,x,y,points,rip=min(options,key=lambda v:v[0]);st=next(a['source_trace_id'] for a in j if a['type']=='source_trace' and net in a.get('connected_source_net_ids',[]));route=[*[{'route_type':'wire','x':a,'y':b,'layer':face,'width':.15} for a,b in points],{'route_type':'via','x':x,'y':y,'from_layer':face,'to_layer':'inner2','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}];j=[a for a in j if a.get('pcb_trace_id') not in rip and a.get('pcb_trace_id')!='seed_61000']+[{'type':'pcb_trace','pcb_trace_id':'seed_61000','source_trace_id':st,'connection_name':net,'route':route}];out.write_text(json.dumps(j));report={'sourcePort':[port['x'],port['y']],'dogbone':points,'via':[x,y],'displacedSignalRoutes':sorted(rip),'output':str(out)};Path('routing-work/revision/encoder-clock-escape-status.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
