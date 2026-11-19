"""Prepare/trim a replay candidate. All edits need a fresh full copper audit."""
import json,sys,copy,math
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union,nearest_points

mode,source,destination=sys.argv[1:4]
j=json.loads(Path(source).read_text())
if mode=='seed':
 saved=json.loads(Path('data/routed-traces.json').read_text())
 for t in saved['traces']:
  r=t['route']
  if len(r)==2 and all(p['route_type']=='wire' for p in r) and r[0]['x']==r[1]['x'] and r[0]['y']==r[1]['y']:
   j.append({**t,'pcb_trace_id':t['pcb_trace_id']+'_wire0','subcircuit_id':'subcircuit_source_group_0'})
 def polygon(p):
  b=p['brep_shape'];return Polygon([(v['x'],v['y']) for v in b['outer_ring']['vertices']], [[(v['x'],v['y']) for v in r['vertices']] for r in b['inner_rings']])
 existing=[(p['layer'],polygon(p)) for p in j if p['type']=='pcb_copper_pour']
 missing=[p for p in saved['planes'] if not any(layer==p['layer'] and polygon(p).symmetric_difference(g).area<1e-5 for layer,g in existing)]
 j.extend(missing)
 Path(destination).write_text(json.dumps(j));print('Restored disks and pours:',10,len(missing))
 # Load the audit's exact copper primitives without running its audit yet.
 old=sys.argv;sys.argv=['checker',destination,'/tmp/unused.json'];g={}
 exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),g);sys.argv=old
 ground=next(n for n,name in g['nets'].items() if name=='GND')
 foreign=unary_union([i['g'] for i in g['items'] if i['net']!=ground]).buffer(.401)
 drills=[]
 for p in j:
  if p['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in p:drills.append(Point(p['x'],p['y']).buffer(p['hole_diameter']/2+.301))
 forbidden=unary_union([foreign,*drills])
 other_ground=unary_union([i['g'] for i in g['items'] if i['net']==ground and i['layer']!='inner1'])
 for k,p in enumerate(missing):
  available=polygon(p).buffer(-.21).difference(forbidden)
  free=available.intersection(other_ground.buffer(-.21))
  if free.is_empty:free=available
  if free.is_empty:
   region=polygon(p)
   others=[i['g'] for i in g['items'] if i['net']==ground and i['layer']==p['layer'] and i['id']!=p['pcb_copper_pour_id']]
   junction=region.buffer(1e-7).intersection(unary_union(others).buffer(1e-7))
   foreign_layer=unary_union([i['g'] for i in g['items'] if i['net']!=ground and i['layer']==p['layer']])
   safe=junction.difference(foreign_layer.buffer(.276))
   if safe.is_empty:
    print('No extra copper fits at ground region',k,'; retain it for native cleanup and re-audit.')
    continue
   q=safe.representative_point()
   source_trace=next(t['source_trace_id'] for t in j if t['type']=='source_trace' and t.get('connected_source_net_ids')==[ground])
   point={'route_type':'wire','x':q.x,'y':q.y,'layer':p['layer'],'width':.15}
   j.append({'type':'pcb_trace','pcb_trace_id':f'replay_ground_bridge_{k}','connection_name':ground,'source_trace_id':source_trace,'subcircuit_id':'subcircuit_source_group_0','route':[point,dict(point)]})
   print('Ground junction reinforcement',k,q.x,q.y)
   continue
  free=max(free.geoms,key=lambda a:a.area) if hasattr(free,'geoms') else free
  q=free.representative_point();x,y=q.x,q.y
  j.append({'type':'pcb_via','pcb_via_id':f'replay_ground_stitch_{k}','x':x,'y':y,'hole_diameter':.2,'outer_diameter':.4,'layers':g['layers'],'from_layer':'top','to_layer':'bottom','source_net_id':ground,'subcircuit_id':'subcircuit_source_group_0'})
  forbidden=forbidden.union(q.buffer(.401));print('Ground stitch',k,x,y)
elif mode=='trim':
 diagnostics=json.loads(Path(sys.argv[4]).read_text())
 old=sys.argv;sys.argv=['checker',source,'/tmp/unused.json'];g={}
 exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),g);sys.argv=old
 traces={t['pcb_trace_id']:t for t in j if t['type']=='pcb_trace'};removed=set();edits=[];unresolved=[]
 for e in diagnostics:
  if e['type']!='pcb_trace_error' or 'dangling endpoint' not in e['message']:continue
  identity=e['pcb_trace_id'];t=traces[identity]
  if identity in removed:continue
  r=t['route'];q=Point(e['center']['x'],e['center']['y'])
  index=0 if q.distance(Point(r[0]['x'],r[0]['y']))<1e-5 else len(r)-1
  step=1 if index==0 else -1;a,b=r[index],r[index+step]
  if a['route_type']!='wire' or b['route_type']!='wire':unresolved.append(identity);continue
  line=LineString([(a['x'],a['y']),(b['x'],b['y'])]);net=g['trace_net'].get(t.get('source_trace_id'),t.get('connection_name'));candidates=[]
  for other in traces.values():
   if other is t or other['pcb_trace_id'] in removed:continue
   if g['trace_net'].get(other.get('source_trace_id'),other.get('connection_name'))!=net:continue
   for c,d in zip(other['route'],other['route'][1:]):
    if c['route_type']!=d['route_type'] or c['route_type']!='wire' or c.get('layer')!=a['layer'] or d.get('layer')!=a['layer']:continue
    target=LineString([(c['x'],c['y']),(d['x'],d['y'])]);u,v=nearest_points(line,target)
    if u.distance(v)>(a['width']+c['width'])/2+1e-7:continue
    move=u.distance(q)
    if move>1e-7:candidates.append((move,u))
  for p in g['items']:
   if p['net']!=net or p['layer']!=a['layer'] or p['kind']=='track':continue
   u,v=nearest_points(line,p['g'])
   if u.distance(v)>a['width']/2+1e-7:continue
   move=u.distance(q)
   if move>1e-7:candidates.append((move,u))
  if not candidates:unresolved.append(identity);continue
  move,u=min(candidates,key=lambda v:v[0]);before=copy.deepcopy(a)
  if u.distance(Point(b['x'],b['y']))<1e-7:
   if len(r)==2:
    if max(p.get('width',0) for p in r)>=.6:unresolved.append(identity);continue
    removed.add(identity)
   else:r.pop(index)
  else:a.update(x=u.x,y=u.y)
  edits.append({'trace':identity,'before':before,'after':{'x':u.x,'y':u.y},'removed':identity in removed})
 j=[e for e in j if e.get('pcb_trace_id') not in removed or e['type']!='pcb_trace']
 Path(destination+'.edits.json').write_text(json.dumps({'edits':edits,'unresolved':unresolved},indent=2))
 print('Trimmed',len(edits),'unresolved',len(unresolved))
else:raise ValueError(mode)
Path(destination).write_text(json.dumps(j))
