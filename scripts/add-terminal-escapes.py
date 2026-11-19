"""Give trapped single-face signal islands a checked through-via escape."""
import json,sys,math,collections
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.strtree import STRtree
src=Path(sys.argv[1]);out=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/terminal-escapes.circuit.json');scope={'__name__':'escape_geometry'};sys.argv=['check-copper.py',str(src),'routing-work/revision/terminal-escape-input-audit.json']
try:exec(compile(Path('scripts/check-copper.py').read_text(),'check-copper.py','exec'),scope)
except SystemExit:pass
j=scope['j'];nets=scope['nets'];layers=scope['layers'];groups={l:[a for a in scope['items'] if a['layer']==l and a['kind']!='pour'] for l in layers};trees={l:STRtree([a['g'] for a in values]) for l,values in groups.items()};extra=[];new=[];notes=[]
ports_by_label=collections.defaultdict(list)
for pid,p in scope['ports'].items():ports_by_label[scope['portlabel'](pid)].append(p)
traces={}
for t in j:
 if t['type']=='source_trace':
  for n in t.get('connected_source_net_ids',[]):traces[n]=t['source_trace_id']
drills=[]
for t in j:
 if t['type']=='pcb_trace':drills.extend((v['x'],v['y'],v.get('via_hole_diameter',.3)/2) for v in t['route'] if v['route_type']=='via')
 elif t['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in t:drills.append((t['x'],t['y'],t['hole_diameter']/2))
def collisions(g,ls,net):
 found=[]
 for l in ls:
  for k in trees[l].query(g,predicate='dwithin',distance=.2):
   a=groups[l][int(k)]
   if a['net']!=net and g.distance(a['g'])<.2-1e-5:found.append(a)
  found.extend(a for a in extra if a['layer']==l and a['net']!=net and g.distance(a['g'])<.2-1e-5)
 return found
for net,name in sorted(nets.items(),key=lambda item:item[1]):
 graph=scope['netGraphs'][net]
 if len(graph['terminals'])<=1 or name=='GND' or name.startswith('SHUNT_'):continue
 for root,labels in graph['terminals'].items():
  ls={graph['layers'][k] for k,r in enumerate(graph['roots']) if r==root}
  if ls&{'inner1','inner2'}:continue
  pp=[p for label in labels for p in ports_by_label[label] if len(p['layers'])==1 and label.split('.')[0] not in ['U1','U2']]
  candidates=[]
  for p in pp:
   x,y=p['x'],p['y'];face=p['layers'][0]
   candidates.append((0,x,y,face,p))
   for radius in [.6,.8,1.,1.25,1.5,2.,2.5,3.]:
    for angle in range(0,360,45):
     a=math.radians(angle);candidates.append((radius,x+radius*math.cos(a),y+radius*math.sin(a),face,p))
  chosen=None
  for _,x,y,face,p in sorted(candidates,key=lambda v:v[0]):
   if any(math.hypot(x-a,y-b)<r+.1+.2-1e-5 for a,b,r in drills):continue
   vg=Point(x,y).buffer(.2,quad_segs=32);wire=LineString([(p['x'],p['y']),(x,y)]).buffer(.075,quad_segs=32)
   if not scope['interior'].covers(vg) or vg.intersection(scope['hole_union']).area>1e-8 or wire.intersection(scope['hole_union']).area>1e-8:continue
   if collisions(vg,layers,net) or collisions(wire,[face],net):continue
   chosen=(x,y,face,p,vg,wire);break
  if not chosen:notes.append({'net':name,'island':labels,'escape':'requires local revision'});continue
  x,y,face,p,vg,wire=chosen;identity='seed_'+str(30000+len(new));route=[{'route_type':'wire','x':p['x'],'y':p['y'],'layer':face,'width':.15},{'route_type':'wire','x':x,'y':y,'layer':face,'width':.15},{'route_type':'via','x':x,'y':y,'from_layer':face,'to_layer':'inner2','layers':layers,'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}];new.append({'type':'pcb_trace','pcb_trace_id':identity,'source_trace_id':traces[net],'connection_name':net,'route':route});drills.append((x,y,.1))
  for l in layers:extra.append({'g':vg,'layer':l,'net':net})
  extra.append({'g':wire,'layer':face,'net':net});notes.append({'net':name,'island':labels,'escape':identity,'via':[x,y],'face':face});print(name,labels,'escaped at',round(x,3),round(y,3),flush=True)
out.write_text(json.dumps([a for a in j if a['type']!='pcb_copper_pour']+new));Path('routing-work/revision/terminal-escape-status.json').write_text(json.dumps({'newEscapes':len(new),'islands':notes},indent=2)+'\n');print('Added',len(new),'checked terminal escapes.')
