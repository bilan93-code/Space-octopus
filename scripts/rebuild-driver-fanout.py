"""Jointly fit the six V/W gate/phase escape vias without crossing pin exits."""
import json,sys,math,collections
import numpy as np
from shapely import distance,contains_xy
from scipy.ndimage import binary_propagation
from pathlib import Path
from shapely.geometry import Point,LineString,box
from shapely.strtree import STRtree
from shapely.ops import unary_union

src,out=map(Path,sys.argv[1:3]);j=json.loads(src.read_text())
names={a['source_net_id']:a['name'] for a in j if a['type']=='source_net'}
trace_net={a['source_trace_id']:a['connected_source_net_ids'][0] for a in j if a['type']=='source_trace' and a.get('connected_source_net_ids')}
selected=set(next((a.split('=',1)[1] for a in sys.argv[3:] if a.startswith('--nets=')),'GL_V,PH_V,GH_V,GH_W,PH_W,GL_W').split(','));require_outlet='--require-outlet' in sys.argv[3:];ids={n for n,name in names.items() if name in selected}
window=box(-23,-6.5,-17,-3.0);clipped=[];modified=[]
def net(a):return a.get('connection_name') or a.get('source_net_id') or trace_net.get(a.get('source_trace_id'))
for a in j:
 if a['type']!='pcb_trace' or net(a) not in ids or any(v.get('width',0)>=.6 or v.get('via_diameter',0)>=.59 for v in a['route']):clipped.append(a);continue
 intersects=any(v['route_type']=='via' and window.covers(Point(v['x'],v['y'])) for v in a['route']) or any(p['route_type']==q['route_type']=='wire' and LineString([(p['x'],p['y']),(q['x'],q['y'])]).intersects(window) for p,q in zip(a['route'],a['route'][1:]))
 if not intersects:clipped.append(a);continue
 modified.append(a['pcb_trace_id']);sequence=0
 for k,v in enumerate(a['route']):
  if v['route_type']=='via':
   if not window.covers(Point(v['x'],v['y'])):
    pos={'x':v['x'],'y':v['y']};clipped.append({**a,'pcb_trace_id':a['pcb_trace_id']+'_driverbarrel'+str(k),'route':[{'route_type':'wire',**pos,'layer':'top','width':.2},v,{'route_type':'wire',**pos,'layer':'bottom','width':.2}]})
  elif k and a['route'][k-1]['route_type']=='wire':
   p=a['route'][k-1];g=LineString([(p['x'],p['y']),(v['x'],v['y'])]).difference(window)
   pieces=[g] if g.geom_type=='LineString' else list(getattr(g,'geoms',[]))
   for piece in pieces:
    if piece.geom_type!='LineString' or piece.length<1e-8:continue
    clipped.append({**a,'pcb_trace_id':a['pcb_trace_id']+'_driverclip'+str(sequence),'route':[{'route_type':'wire','x':x,'y':y,'layer':v['layer'],'width':v['width']} for x,y in piece.coords]});sequence+=1
candidate_path=out.with_suffix('.clipped.json');candidate_path.write_text(json.dumps(clipped));s={};sys.argv=['g',str(candidate_path),'/tmp/driver-fanout-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
objects=[a for a in s['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in objects]);wide={a['pcb_trace_id'] for a in clipped if a['type']=='pcb_trace' and any(v.get('width',0)>=.6 for v in a['route'])}
pickups=[Point(*b[k]) for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches'] for k in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia']]
def protected(a):
 identity=a['id'].rsplit(':',1)[0]
 return a['kind']=='pad' or identity in wide or identity.startswith(('kelvin_','plane_stitch_','seed_local_repair_','seed_joint_driver_','seed_input_','seed_ground_')) or a['kind']=='via' and (a['g'].bounds[2]-a['g'].bounds[0]>=.59 or any(a['g'].centroid.distance(p)<1e-5 for p in pickups))
pins=[p for p in [(13,'GL_V',-18.75),(14,'PH_V',-19.25),(15,'GH_V',-19.75),(16,'GH_W',-20.25),(17,'PH_W',-20.75),(18,'GL_W',-21.25)] if p[1] in selected];choices={}
for pin,name,x in pins:
 n=next(k for k,v in names.items() if v==name);candidates=[]
 for dx in [0,.1,-.1,.2,-.2,.3,-.3]:
  for y in [-3.75-.1*i for i in range(23)]:
   coords=[(x,-2.95),(x,-3.65),(x+dx,y)];wire=LineString(coords).buffer(.075,quad_segs=32);via=Point(x+dx,y).buffer(.2,quad_segs=32);ripped=set();blocked=False
   for g,ls in [(wire,['bottom']),(via,s['layers'])]:
    for k in tree.query(g,predicate='dwithin',distance=.2):
     a=objects[int(k)]
     if a['net']==n or a['layer'] not in ls or g.distance(a['g'])>=.2-1e-5:continue
     if protected(a):blocked=True;break
     ripped.add(a['id'].rsplit(':',1)[0])
    if blocked:break
   if not blocked:candidates.append({'pin':pin,'name':name,'net':n,'coords':coords,'wire':wire,'via':via,'ripped':ripped,'cost':1000*len(ripped)+LineString(coords).length})
 choices[name]=sorted(candidates,key=lambda c:c['cost']);print(name,'legal candidates',len(candidates),flush=True)
 assert candidates,('No joint fanout sites for',name)
order=sorted(choices,key=lambda n:len(choices[n]));compat={};best=None;visited=0
if require_outlet:
 xa=np.arange(201)*.05-25;ya=np.arange(171)*.05-10;xx=xa[None,:];yy=ya[:,None];boundary=np.zeros((len(ya),len(xa)),dtype=bool);boundary[0,:]=boundary[-1,:]=True;boundary[:,0]=boundary[:,-1]=True
 rectpads={p['pcb_plated_hole_id'] for p in s['bytype']['pcb_plated_hole'] if p['shape']=='circular_hole_with_rect_pad'}
 free_base={}
 for name in order:
  netid=next(n for n,v in names.items() if v==name)
  free_base[name]=np.stack([~contains_xy(unary_union([box(*a['g'].bounds) if a['id'] in rectpads else a['g'] for a in objects if a['net']!=netid and a['layer']==l]).buffer(.278),xx,yy) for l in s['layers']])
 def blocked(c):
  if 'mask' not in c:
   vm=contains_xy(c['via'].buffer(.278),xx,yy);wm=contains_xy(c['wire'].buffer(.278),xx,yy)
   c['mask']=np.stack([vm|wm if l=='bottom' else vm for l in s['layers']])
  return c['mask']
 def find_path(free,start):
  sx,sy=start
  if not free[sy,sx]:return None
  reached=binary_propagation(boundary&free,mask=free)
  if not reached[sy,sx]:return None
  w=len(xa);origin=sy*w+sx;queue=collections.deque([origin]);parent={origin:None};end=None
  while queue:
   i=queue.popleft();y,x=divmod(i,w)
   if boundary[y,x]:end=i;break
   for nx,ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
    if nx<0 or nx>=w or ny<0 or ny>=len(ya) or not free[ny,nx]:continue
    k=ny*w+nx
    if k not in parent:parent[k]=i;queue.append(k)
  path=[]
  while end is not None:path.append(end);end=parent[end]
  path.reverse();coords=[(float(xa[i%w]),float(ya[i//w])) for i in path];compressed=[coords[0]]
  for a,b,c in zip(coords,coords[1:],coords[2:]):
   if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-8:compressed.append(b)
  compressed.append(coords[-1]);return compressed
 def outlets(chosen):
  for route_order in [chosen,list(reversed(chosen))]:
   extra=np.zeros_like(free_base[route_order[0]['name']]);planned={};ok=True
   for c in route_order:
    free=free_base[c['name']].copy()&~extra
    for b in chosen:
     if b is not c:free&=~blocked(b)
    x,y=c['coords'][-1];start=(round((x-xa[0])/.05),round((y-ya[0])/.05));found=None
    for li,layer in enumerate(s['layers']):
     coords=find_path(free[li],start)
     if coords:
      found=(layer,coords);extra[li]|=contains_xy(LineString(coords).buffer(.353),xx,yy);break
    if found is None:ok=False;break
    planned[c['name']]=found
   if ok:
    for c in chosen:c['outlet']=planned[c['name']]
    return True
  return False
for i,a in enumerate(order):
 ca=choices[a];la=np.array([LineString(c['coords']) for c in ca],dtype=object);pa=np.array([Point(c['coords'][-1]) for c in ca],dtype=object)
 for b in order[i+1:]:
  cb=choices[b];lb=np.array([LineString(c['coords']) for c in cb],dtype=object);pb=np.array([Point(c['coords'][-1]) for c in cb],dtype=object)
  # Exact centreline/circle distances avoid repeated polygon-distance work.
  ok=(distance(pa[:,None],pb[None,:])>=.6-1e-5)&(distance(la[:,None],lb[None,:])>=.35-1e-5)&(distance(pa[:,None],lb[None,:])>=.475-1e-5)&(distance(la[:,None],pb[None,:])>=.475-1e-5)
  compat[a,b]=ok;compat[b,a]=ok.T
def search(index,chosen,domains):
 global best,visited
 visited+=1
 if best is not None or visited>50000:return
 if index==len(order):
  if not require_outlet or outlets(chosen):best=list(chosen)
  return
 name=order[index]
 for k in domains[name]:
  future={n:[v for v in domains[n] if compat[name,n][k,v]] for n in order[index+1:]}
  if any(not values for values in future.values()):continue
  search(index+1,chosen+[choices[name][k]],future)
  if best is not None:return
for zero_rips in [True,False]:
 domains={n:[k for k,c in enumerate(choices[n]) if not zero_rips or not c['ripped']] for n in order}
 if any(not values for values in domains.values()):continue
 visited=0;search(0,[],domains)
 if best is not None:break
assert best,'No compatible joint fanout found.'
ripped=set().union(*(c['ripped'] for c in best));result=[a for a in clipped if a.get('pcb_trace_id',a.get('pcb_via_id')) not in ripped and a['type']!='pcb_copper_pour'];new=[]
for c in best:
 x,y=c['coords'][-1];route=[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.15} for x,y in c['coords']]+[{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'inner1','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner1','width':.15}]
 result.append({'type':'pcb_trace','pcb_trace_id':'seed_joint_driver_U2_'+str(c['pin']),'connection_name':c['net'],'route':route});new +=[(c['net'],'bottom',c['wire'])]+[(c['net'],l,c['via']) for l in s['layers']]
 if c.get('outlet'):
  layer,coords=c['outlet'];result.append({'type':'pcb_trace','pcb_trace_id':'seed_joint_driver_U2_'+str(c['pin'])+'_outlet','connection_name':c['net'],'route':[{'route_type':'wire','x':x,'y':y,'layer':layer,'width':.15} for x,y in coords]});new.append((c['net'],layer,LineString(coords).buffer(.075,quad_segs=32)))
def polygons(g):
 if g.is_empty:return []
 if g.geom_type=='Polygon':return [g]
 return [p for child in getattr(g,'geoms',[]) for p in polygons(child)]
def ring(r):return {'vertices':[{'x':float(x),'y':float(y),'bulge':0} for x,y in list(r.coords)[:-1]]}
for a in [a for a in s['items'] if a['kind']=='pour']:
 cutter=unary_union([g.buffer(.25) for n,l,g in new if n!=a['net'] and l==a['layer']]);g=a['g'].difference(cutter)
 for k,pg in enumerate(polygons(g)):result.append({'type':'pcb_copper_pour','pcb_copper_pour_id':a['id']+'_joint'+str(k),'source_net_id':a['net'],'layer':a['layer'],'shape':'brep','brep_shape':{'outer_ring':ring(pg.exterior),'inner_rings':[ring(r) for r in pg.interiors]}})
out.write_text(json.dumps(result));report={'source':str(src),'output':str(out),'modifiedFanoutTraces':modified,'displacedForeignTracks':sorted(ripped),'searchStates':visited,'fanouts':[{'pin':c['pin'],'net':c['name'],'via':c['coords'][-1],'wireLengthMm':LineString(c['coords']).length} for c in best]};out.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
