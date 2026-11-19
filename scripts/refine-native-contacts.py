"""Resolve endpoint contacts with real copper; reject each unsafe proposal.

Every accepted edit preserves the affected net's terminal partition, 0.2 mm
foreign-copper spacing, and the board/hole keepouts. A full audit is still due.
"""
import json,sys,copy,math,collections
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree
src,out,diagnostics=map(Path,sys.argv[1:4]);old=sys.argv;sys.argv=['checker',str(src),'/tmp/unused.json'];g={}
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),g);sys.argv=old
j=g['j'];traces={t['pcb_trace_id']:t for t in j if t['type']=='pcb_trace'}
base=[i for i in g['items'] if i['kind']!='track' and ':v' not in i['id']]
layers=g['layers'];ports=g['ports'];netof=lambda t:g['trace_net'].get(t.get('source_trace_id'),t.get('connection_name'))
def wires(t):
 for a,b in zip(t['route'],t['route'][1:]):
  if a['route_type']==b['route_type']=='wire' and a['layer']==b['layer']:
   yield a['layer'],LineString([(a['x'],a['y']),(b['x'],b['y'])]).buffer(b.get('width',a['width'])/2,quad_segs=16)
def partition(net,changes=None,extra=None):
 objects=[(i['layer'],i['g']) for i in base if i['net']==net]
 for t in traces.values():
  if netof(t)!=net:continue
  r=changes if changes is not None and changes['pcb_trace_id']==t['pcb_trace_id'] else t
  objects.extend(wires(r))
 if extra:objects.extend(wires(extra))
 nodes=[];ls=[]
 for layer in layers:
  u=unary_union([p for l,p in objects if l==layer]).buffer(1e-7)
  shapes=list(u.geoms) if u.geom_type=='MultiPolygon' else ([] if u.is_empty else [u])
  nodes.extend(shapes);ls.extend([layer]*len(shapes))
 parents=list(range(len(nodes)))
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def join(ids):
  for k in ids[1:]:parents[root(k)]=root(ids[0])
 for bn,span,p in g['barrels']:
  if bn==net:join([i for i,q in enumerate(nodes) if ls[i] in span and p.intersects(q)])
 for c in g['bytype']['source_component']:
  for ids in c.get('internally_connected_source_port_ids',[]):
   pp=[p for p in ports.values() if p.get('source_port_id') in ids and g['portnet'].get(p['pcb_port_id'])==net]
   join([i for i,p in enumerate(nodes) if any(ls[i] in a['layers'] and p.distance(Point(a['x'],a['y']))<1e-5 for a in pp)])
 groups=collections.defaultdict(set)
 for pid in {i['port'] for i in base if i['net']==net and i.get('port')}:
  p=ports[pid];ids=[i for i,q in enumerate(nodes) if ls[i] in p['layers'] and q.distance(Point(p['x'],p['y']))<1e-5]
  groups[root(ids[0]) if ids else 'missing:'+pid].add(pid)
 return sorted([sorted(a) for a in groups.values()])
baseline={};extra=[];edits=[];unresolved=[]
indexed={layer:[i for i in g['items'] if i['layer']==layer] for layer in layers}
trees={layer:STRtree([i['g'] for i in items]) for layer,items in indexed.items()}
board=g['bytype']['pcb_board'][0];allowed=Polygon([(p['x'],p['y']) for p in board['outline']]).buffer(-.5)
holes=[]
for p in g['bytype']['pcb_hole']:holes.append(Point(p['x'],p['y']).buffer(p['hole_diameter']/2+.5,quad_segs=128))
for p in g['bytype']['pcb_cutout']:holes.append(Point(p['center']['x'],p['center']['y']).buffer(p['radius']+.5,quad_segs=128))
mech=json.loads(Path('data/board-geometry.json').read_text());refs={c['pcb_component_id']:g['sources'].get(c.get('source_component_id'),'') for c in g['bytype']['pcb_component']}
for p in g['bytype']['pcb_hole']:
 if refs.get(p.get('pcb_component_id'),'').startswith('H'):
  r=mech['mounting']['keepoutDiameterMm']/2;holes.append(box(p['x']-r,p['y']-r,p['x']+r,p['y']+r).buffer(mech['mounting'].get('copperKeepoutGapMm',.2)))
blocked=unary_union(holes)
def safe(t,net):
 for layer,p in wires(t):
  if not allowed.buffer(1e-5).covers(p) or p.intersection(blocked).area>1e-8:return False
  for k in trees[layer].query(p.buffer(.2)):
   i=indexed[layer][int(k)]
   if i['net']!=net and p.distance(i['g'])<.2-1e-5:return False
  for n,l,q in extra:
   if n!=net and l==layer and p.distance(q)<.2-1e-5:return False
 return True
def bridge(t,a,b,index):
 while f'replay_contact_{index}' in traces:index+=1
 point=lambda p:{'route_type':'wire','x':p.x,'y':p.y,'layer':a['layer'],'width':.15}
 return {'type':'pcb_trace','pcb_trace_id':f'replay_contact_{index}','source_trace_id':t['source_trace_id'],'connection_name':netof(t),'subcircuit_id':'subcircuit_source_group_0','route':[point(Point(a['x'],a['y'])),point(b)]}
for e in json.loads(diagnostics.read_text()):
 if e['type']!='pcb_trace_error' or 'dangling endpoint' not in e['message']:continue
 identity=e['pcb_trace_id'];t=traces[identity];r=t['route'];net=netof(t)
 point=Point(e['center']['x'],e['center']['y']);idx=0 if point.distance(Point(r[0]['x'],r[0]['y']))<1e-5 else len(r)-1
 a,b=r[idx],r[1 if idx==0 else -2];line=LineString([(a['x'],a['y']),(b['x'],b['y'])]);radius=a['width']/2
 proposals=[]
 # A route can cross a pad and continue beyond it. End it inside that pad,
 # retaining a full-width contact while removing the actual unused tail.
 for pad in base:
  if pad['kind']!='pad' or pad['net']!=net or pad['layer']!=a['layer']:continue
  inside=line.intersection(pad['g'].buffer(-radius-.001))
  if inside.is_empty:continue
  target=nearest_points(point,inside)[1]
  if target.distance(point)<1e-7:continue
  candidate=copy.deepcopy(t);candidate['route'][idx].update(x=target.x,y=target.y)
  proposals.append((point.distance(target),candidate,None,'trim past pad'))
 for pad in base:
  if pad['kind']!='pad' or pad['net']!=net or pad['layer']!=a['layer'] or line.distance(pad['g'])>radius+1e-7:continue
  inner=pad['g'].buffer(-radius-.001)
  if inner.is_empty:continue
  u,v=nearest_points(line,inner);candidate=copy.deepcopy(t)
  points=[{**a,'x':u.x,'y':u.y},{**a,'x':v.x,'y':v.y}]
  for p in points:p.pop('start_pcb_port_id',None);p.pop('end_pcb_port_id',None)
  if idx==0:candidate['route']=list(reversed(points))+candidate['route'][1:]
  else:candidate['route']=candidate['route'][:-1]+points
  proposals.append((point.distance(u)+u.distance(v),candidate,None,'pad junction'))
 # Explicit centerline entries into pads whose copper already touches the cap.
 for pad in base:
  if pad['kind']!='pad' or pad['net']!=net or pad['layer']!=a['layer'] or pad['g'].distance(point)>radius+1e-7:continue
  port=ports[pad['port']];target=Point(port['x'],port['y'])
  if pad['g'].covers(point):continue
  added=bridge(t,a,target,len(edits));proposals.append((0,copy.deepcopy(t),added,'pad entry'))
 # Trim the overhang to a junction, and make the junction a real centerline join.
 for other in traces.values():
  if other is t or netof(other)!=net:continue
  for c,d in zip(other['route'],other['route'][1:]):
   if c['route_type']!=d['route_type'] or c['route_type']!='wire' or c.get('layer')!=a['layer'] or d.get('layer')!=a['layer']:continue
   target=LineString([(c['x'],c['y']),(d['x'],d['y'])]);u,v=nearest_points(line,target)
   if u.distance(v)>radius+c['width']/2+1e-7:continue
   if point.distance(u)<1e-7 and u.distance(v)<1e-7:continue
   candidate=copy.deepcopy(t)
   points=[{**a,'x':u.x,'y':u.y}]
   if u.distance(v)>1e-7:points.append({**a,'x':v.x,'y':v.y})
   for p in points:p.pop('start_pcb_port_id',None);p.pop('end_pcb_port_id',None)
   if idx==0:candidate['route']=list(reversed(points))+candidate['route'][1:]
   else:candidate['route']=candidate['route'][:-1]+points
   proposals.append((point.distance(u)+u.distance(v),candidate,None,'junction'))
 for via in base:
  if via['kind']!='via' or via['net']!=net or via['layer']!=a['layer']:continue
  v=via['g'].centroid;u=nearest_points(line,v)[0]
  if u.distance(v)>radius+(via['g'].bounds[2]-via['g'].bounds[0])/2+1e-7:continue
  candidate=copy.deepcopy(t);points=[{**a,'x':u.x,'y':u.y},{**a,'x':v.x,'y':v.y}]
  for p in points:p.pop('start_pcb_port_id',None);p.pop('end_pcb_port_id',None)
  if idx==0:candidate['route']=list(reversed(points))+candidate['route'][1:]
  else:candidate['route']=candidate['route'][:-1]+points
  proposals.append((point.distance(u)+u.distance(v),candidate,None,'via junction'))
 # A whole outer segment can be obsolete. Its removal is allowed only when
 # the exact physical terminal partition remains unchanged.
 candidate=copy.deepcopy(t);candidate['route'].pop(idx)
 if len(candidate['route'])<2:candidate['route']=[]
 proposals.append((1e6,candidate,None,'remove outer segment'))
 baseline.setdefault(net,partition(net))
 accepted=False
 for _,candidate,added,kind in sorted(proposals,key=lambda p:p[0]):
  if not safe(candidate,net) or added and not safe(added,net):continue
  if partition(net,candidate,added)!=baseline[net]:continue
  traces[identity]=candidate
  if added:traces[added['pcb_trace_id']]=added
  for item in [candidate,added]:
   if item:extra.extend((net,layer,p) for layer,p in wires(item))
  edits.append({'trace':identity,'kind':kind,'bridge':added and added['pcb_trace_id']});accepted=True;break
 if not accepted:unresolved.append(identity)
 print('Contact',len(edits),'remaining proposals',len(unresolved),g['nets'].get(net),kind if accepted else 'rejected',flush=True)
j=[e for e in j if e['type']!='pcb_trace']+[t for t in traces.values() if t['route']]
out.write_text(json.dumps(j));Path(str(out)+'.edits.json').write_text(json.dumps({'edits':edits,'unresolved':unresolved},indent=2))
print('Accepted',len(edits),'unresolved',len(unresolved),flush=True)
