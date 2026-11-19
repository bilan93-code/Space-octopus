"""Local copper finishing from tscircuit geometry; exact audit follows each path.
This produces connectivity routes only, not qualified motor-current copper.
"""
import json,sys,math,struct,subprocess,time,collections,os,re,hashlib
from pathlib import Path
import numpy as np
from shapely import contains_xy,make_valid,difference,prepare
from shapely.errors import GEOSException
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree

def polygon_parts(g):
 if g.is_empty:return []
 if g.geom_type=='Polygon':return [g]
 return [p for child in getattr(g,'geoms',[]) for p in polygon_parts(child)]

def safe_difference(a,b):
 try:return a.difference(b)
 except GEOSException:return difference(make_valid(a),make_valid(b),grid_size=1e-6)

work=Path(os.environ.get('ROUTING_WORK','routing-work/grid'));work.mkdir(parents=True,exist_ok=True)
binary=Path('/tmp/octopus-routing/grid-astar');binary.parent.mkdir(parents=True,exist_ok=True)
if not binary.exists() or binary.stat().st_mtime<Path('scripts/grid-astar.cpp').stat().st_mtime:
 subprocess.run(['g++','-O3','-std=c++17','scripts/grid-astar.cpp','-o',str(binary)],check=True)
inputfile=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json')
scope={'__name__':'copper_geometry'};sys.argv=['check-copper.py',str(inputfile),str(work/'input-audit.json')]
audit_script=Path('scripts/check-copper.py');audit_code=audit_script.read_text();cache_path=Path(os.environ['ROUTING_AUDIT_CACHE']) if os.environ.get('ROUTING_AUDIT_CACHE') else None
cached=json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else None
cache_valid=cached is not None and cache_path.stat().st_mtime>=audit_script.stat().st_mtime and cached.get('circuitJsonSha256')==hashlib.sha256(inputfile.read_bytes()).hexdigest() and all(cached.get(k)==0 for k in ['shortCount','clearanceViolationCount','edgeViolationCount','holeViolationCount','unsupportedCount'])
if cache_valid:
 # Reuse only a fresh independent audit of these exact unchanged bytes.
 # All newly generated paths and the delivered result are checked again.
 exec(compile(audit_code.split('# Distinct-net copper')[0],'check-copper.py','exec'),scope)
 boundary_setup=audit_code[audit_code.index("\nboard=bytype['pcb_board']"):].split('# Build conductive islands')[0]
 exec(compile(boundary_setup,'copper_boundaries','exec'),scope)
 scope['report']=cached;(work/'input-audit.json').write_text(json.dumps(cached,indent=2)+'\n')
 print('Reused fresh independent audit for unchanged copper:',cached['fullyConnectedNets'],'connected nets.',flush=True)
else:
 try:exec(compile(audit_code,'check-copper.py','exec'),scope)
 except SystemExit:pass
j=scope['j'];prior=scope['report']
bad={x['id'].rsplit(':',1)[0] for x in prior['edges']+prior['holes']}
for x in prior['clearances']:
 for key in ['a','b']:
  if x[key].startswith(('local_','finish_')):bad.add(x[key].rsplit(':',1)[0])
if Path('output/render-diagnostics.json').exists():
 for e in json.loads(Path('output/render-diagnostics.json').read_text()):
  if e['type']=='pcb_pad_trace_clearance_error':bad.add(e['pcb_trace_id'])
j=[x for x in j if x['type'] not in ['pcb_trace','pcb_via'] or x.get('pcb_trace_id',x.get('pcb_via_id')) not in bad]
working=work/'working.circuit.json';working.write_text(json.dumps(j));print('Removed',len(bad),'copper items failing clearance checks.',flush=True)
if bad:
 scope={'__name__':'copper_geometry'};sys.argv=['check-copper.py',str(working),str(work/'initial-audit.json')]
 try:exec(compile(Path('scripts/check-copper.py').read_text(),'check-copper.py','exec'),scope)
 except SystemExit:pass
else:(work/'initial-audit.json').write_text(json.dumps(prior,indent=2)+'\n')
items=scope['items'];barrels=scope['barrels'];nets=scope['nets'];ports=scope['ports'];portnet=scope['portnet'];bytype=scope['bytype'];layers=scope['layers'];add=scope['add']
board=scope['outline'];holes=bytype['pcb_hole'];pad_items=[a for a in items if a['kind']=='pad']
allpad=unary_union([a['g'] for a in pad_items]);npth=unary_union([Point(h['x'],h['y']).buffer(h['hole_diameter']/2,quad_segs=128) for h in holes]+[Point(c['center']['x'],c['center']['y']).buffer(c['radius'],quad_segs=128) for c in bytype['pcb_cutout'] if c['shape']=='circle'])
hardware=unary_union(scope['hardware'])
rectpads={p['pcb_plated_hole_id'] for p in bytype['pcb_plated_hole'] if p['shape']=='circular_hole_with_rect_pad'}
ground_escapes=os.environ.get('ROUTING_GROUND_ESCAPES')=='1'
ic_components={p['pcb_component_id'] for p in bytype['pcb_component'] if scope['pcb_refs'].get(p['pcb_component_id'],'').startswith('U')}
ic_pad_geometries=collections.defaultdict(list)
for a in pad_items:
 c=ports.get(a.get('port'),{}).get('pcb_component_id')
 if c in ic_components:ic_pad_geometries[c].append(a['g'])
ground_escape_area=unary_union([unary_union(gs).envelope.buffer(2) for gs in ic_pad_geometries.values()]) if ground_escapes else Polygon()
for a in items:
 if a['id'] in rectpads:a['routing_g']=box(*a['g'].bounds)
def polygons(net):
 own=[a for a in items if a['net']==net];nodes=[];ls=[]
 for layer in layers:
  u=unary_union([a['g'] for a in own if a['layer']==layer]).buffer(1e-7)
  parts=polygon_parts(u)
  nodes+=parts;ls +=[layer]*len(parts)
 parent=list(range(len(nodes)))
 for p in nodes:prepare(p)
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(ids):
  for k in ids[1:]:parent[root(k)]=root(ids[0])
 for bn,bl,g in barrels:
  if bn==net:join([i for i,p in enumerate(nodes) if ls[i] in bl and p.intersects(g)])
 for c in bytype['source_component']:
  for ids in c.get('internally_connected_source_port_ids',[]):
   pp=[p for p in ports.values() if p.get('source_port_id') in ids and portnet.get(p['pcb_port_id'])==net]
   join([i for i,g in enumerate(nodes) if any(ls[i] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5 for p in pp)])
 grouped=collections.defaultdict(lambda:collections.defaultdict(list));terminals=collections.defaultdict(list)
 for i,g in enumerate(nodes):grouped[root(i)][ls[i]].append(g)
 for pid,p in ports.items():
  if portnet.get(pid)!=net:continue
  pt=Point(p['x'],p['y'])
  ids=[i for i,g in enumerate(nodes) if ls[i] in p['layers'] and (g.covers(pt) or g.distance(pt)<1e-5)]
  if ids:terminals[root(ids[0])].append(p)
 return {r:{l:unary_union(gs) for l,gs in gl.items()} for r,gl in grouped.items() if r in terminals},terminals

# Later same-net branches must not attach to a Kelvin pickup before its pad.
# The baseline contains the explicit sense traces, stubs and isolated barrels.
sense_guard=collections.defaultdict(lambda:collections.defaultdict(list))
pickup_manifest=json.loads(Path('data/kelvin-routing.json').read_text());protected_pickup_points=[]
for branch in pickup_manifest['branches']:
 for name,points in [('GND',[branch['sourceVia'],branch['pickupGroundVia']]),('SHUNT_'+branch['phase']+'_TOP',[branch.get('positiveSourceVia'),branch.get('positivePickupVia')])]:
  net=next(k for k,v in nets.items() if v==name)
  for point in points:
   if point is not None:
    protected_pickup_points.append((net,Point(*point)))
    for layer in layers:sense_guard[net][layer].append(Point(*point).buffer(.2,quad_segs=32))
protected_pickup_ids={a['id'].rsplit(':',1)[0] for a in items if a['kind']=='via' and any(a['net']==n and a['g'].centroid.distance(p)<1e-5 for n,p in protected_pickup_points)}
for a in pad_items:
 if a.get('port') and scope['portlabel'](a['port']) in ['U2.9','U2.10','U2.11','U2.12','U2.19','U2.20']:
  sense_guard[a['net']][a['layer']].append(a['g'])
guard_traces=[tr for tr in j if tr.get('type')=='pcb_trace' and tr.get('pcb_trace_id','').startswith('kelvin_')]
if not guard_traces:raise RuntimeError('Input has no dedicated Kelvin pickup routes; seed those before general routing.')
if not any(v.get('route_type')=='via' for tr in guard_traces for v in tr['route']):
 saved_guard=Path('data/routed-traces.json')
 if not saved_guard.exists():raise RuntimeError('Rendered Kelvin traces require the saved raw via geometry.')
 saved_data=json.loads(saved_guard.read_text());current_net_ids={v:k for k,v in nets.items()}
 for tr in saved_data['traces']:
  if not tr.get('pcb_trace_id','').startswith('kelvin_'):continue
  name=saved_data.get('netNamesById',{}).get(tr.get('connection_name'))
  if name in current_net_ids:guard_traces.append({**tr,'connection_name':current_net_ids[name]})
if guard_traces:
 for tr in guard_traces:
  if tr.get('type')!='pcb_trace' or not tr.get('pcb_trace_id','').startswith('kelvin_'):continue
  net=tr['connection_name']
  for k,v in enumerate(tr['route']):
   if v['route_type']=='via':
    for l in layers:sense_guard[net][l].append(Point(v['x'],v['y']).buffer(v.get('via_diameter',.4)/2,quad_segs=24))
   elif k and tr['route'][k-1]['route_type']=='wire':
    u=tr['route'][k-1];sense_guard[net][v['layer']].append(LineString([(u['x'],u['y']),(v['x'],v['y'])]).buffer(v['width']/2,quad_segs=24))
# Native replay materializes barrels separately from the Kelvin wire chunks.
for via in [a for a in j if a.get('type')=='pcb_via']:
 net=via.get('source_net_id') or scope['trace_net'].get(via.get('source_trace_id'))
 if net not in sense_guard:continue
 center=Point(via['x'],via['y'])
 if any(center.distance(g)<via['outer_diameter']/2+1e-7 for gs in list(sense_guard[net].values()) for g in gs):
  for layer in via['layers']:sense_guard[net][layer].append(center.buffer(via['outer_diameter']/2,quad_segs=24))

def route_rank(net):
 name=nets.get(net,'')
 if name=='GND':return 0
 if name.startswith(('GH_','GL_','Q1_G','Q2_G','Q3_G','Q4_G','Q5_G','Q6_G','PH_','SHUNT_','BRAKE_GATE','BRAKE_DRV')):return 1
 if name in ['V12','V5','V3V3','VDDA3V3','VBUS','CP_L','CP_H','VCP','DRV_VGLS','DRV_DVDD','BUCK12_SW','BUCK5_SW','BST12','FB12','FB5','RON12','RIPPLE12']:return 2
 if name.startswith(('FAULT','PERMIT','RESET','PWM','DRV_ENABLE','I_LOW','I_HIGH','IU_','IV_','IW_','REF25','WDT','WDI')):return 3
 if name.startswith(('EXP_','UART','SW','LED')):return 5
 return 4
wide_trace_ids={tr['pcb_trace_id'] for tr in j if tr['type']=='pcb_trace' and any(v.get('width',0)>=.6 for v in tr['route'])}
locked_nets=set()
thaw_names={v for v in os.environ.get('ROUTING_THAW_NETS','').split(',') if v}
def immutable(a,net):
 if thaw_names and nets.get(a['net']) not in thaw_names:return True
 earlier_peer=os.environ.get('ROUTING_FREEZE_EQUAL_RANK')=='1' and route_rank(a['net'])==route_rank(net) and nets.get(a['net'],'')<nets.get(net,'')
 supply_names={'GND','VBUS','DC_IN','V12','V5','V3V3','VDDA3V3','CP_L','CP_H','VCP','DRV_VGLS','DRV_DVDD','BUCK12_SW','BUCK5_SW','BST12','FB12','FB5','RON12','RIPPLE12','HSE_CLK','OSC8_OUT'}
 thaw=os.environ.get('ROUTING_THAW_OLD_SIGNALS')=='1' and (not thaw_names or nets.get(a['net']) in thaw_names) and a['net'] not in locked_nets and nets.get(a['net']) not in supply_names and not nets.get(a['net'],'').startswith('SHUNT_') and a['id'].startswith('seed_frozen_') and '_finish_' in a['id'] and '_saved_pcb_via_' not in a['id']
 fixed=a['kind'] in ['pad','pour'] or (a['kind']=='via' and a['g'].bounds[2]-a['g'].bounds[0]>=.59) or (a['id'].startswith(('seed_','kelvin_','plane_stitch_')) and not thaw) or a['id'].rsplit(':',1)[0] in protected_pickup_ids
 if fixed:return True
 reordered=os.environ.get('ROUTING_REORDER_NETS','').split(',')
 if '*' in reordered or nets.get(net) in reordered:return a['id'].rsplit(':',1)[0] in wide_trace_ids
 return route_rank(a['net'])<route_rank(net) or earlier_peer

def wire_obstacle(a,net,soft=False):
 # Fills are clipped around new routes; fixed power/sense copper is retained.
 if a['kind']=='pour' and (a['layer']=='inner2' or ground_escapes):return False
 return a['net']!=net and (not soft or immutable(a,net))

def terminal_escape(net,groups,terminals):
 repair=os.environ.get('ROUTING_LOCAL_REPAIR')=='1'
 if nets[net]=='GND' and not repair or nets[net].startswith('SHUNT_'):return None,'no signal fanout required'
 target=max(groups,key=lambda r:(len(terminals[r]),len(groups[r]),sum(g.area for g in groups[r].values())))
 copper=[a for a in items if a['kind']!='pour'];tree=STRtree([a['g'] for a in copper]);drills=[]
 for t in j:
  if t['type']=='pcb_trace':drills.extend((v['x'],v['y'],v.get('via_hole_diameter',.3)/2) for v in t['route'] if v['route_type']=='via')
  elif t['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in t:drills.append((t['x'],t['y'],t['hole_diameter']/2))
 def hits(g,ls):
  return [copper[int(k)] for k in tree.query(g,predicate='dwithin',distance=.2) if copper[int(k)]['layer'] in ls and copper[int(k)]['net']!=net and g.distance(copper[int(k)]['g'])<.2-1e-5]
 candidates=[]
 for root,gl in groups.items():
  if root==target:continue
  driver_terminal=any(scope['portlabel'](p['pcb_port_id']) in ['U2.14','U2.17'] for p in terminals[root]) or os.environ.get('ROUTING_LOCAL_REPAIR')=='1'
  if any(l in gl for l in ['inner1','inner2']) and not repair:continue
  for p in terminals[root]:
   if len(p['layers'])!=1:continue
   for radius in [0,.6,.8,1.,1.25,1.5,2.,2.5,3.,4.,5.,6.,8.]:
    for angle in ([0] if radius==0 else range(0,360,45)):
     a=math.radians(angle);candidates.append((radius,p['x']+radius*math.cos(a),p['y']+radius*math.sin(a),p))
   if scope['portlabel'](p['pcb_port_id']) in ['U2.14','U2.17'] or os.environ.get('ROUTING_LOCAL_REPAIR')=='1' and scope['portlabel'](p['pcb_port_id']).startswith('U1.'):
    for dx in range(-25,26):
     for dy in range(-25,26):
      r=math.hypot(dx,dy)/10
      if .3<=r<=2.5:candidates.append((r,p['x']+dx/10,p['y']+dy/10,p))
 best=None;best_cost=float('inf')
 for radius,x,y,p in sorted(candidates,key=lambda c:c[0]):
  if radius>best_cost:break
  if any(math.hypot(x-a,y-b)<r+.1+.2-1e-5 for a,b,r in drills):continue
  face=p['layers'][0];vg=Point(x,y).buffer(.2,quad_segs=32);wg=LineString([(p['x'],p['y']),(x,y)]).buffer(.075,quad_segs=32)
  if repair and any(bn==net and Point(x,y).distance(g.centroid)<1.25 for bn,bl,g in barrels):continue
  if not board.buffer(-.5+1e-6).covers(vg) or vg.distance(npth)<.5-1e-5 or wg.distance(npth)<.5-1e-5 or vg.intersection(hardware).area>1e-8 or wg.intersection(hardware).area>1e-8:continue
  obstructing=hits(vg,layers)+hits(wg,[face]);ripped={a['id'].rsplit(':',1)[0] for a in obstructing}
  if ripped and os.environ.get('ROUTING_RIPUP','0')!='1':continue
  def escape_protected(a):
   if os.environ.get('ROUTING_LOCAL_REPAIR')!='1':return immutable(a,net)
   # A local repair can move an earlier ordinary wire. Pads, wide power,
   # thermal barrels, fixed fanout and Kelvin copper remain reserved.
   return a['kind'] in ['pad','pour'] or a['kind']=='via' and a['g'].bounds[2]-a['g'].bounds[0]>=.59 or a['id'].startswith(('seed_','kelvin_','plane_stitch_')) or a['id'].rsplit(':',1)[0] in protected_pickup_ids
  if len(ripped)>3 or any(not identity.startswith('finish_') for identity in ripped) or any(escape_protected(a) for a in obstructing):continue
  if any(vg.distance(g)<.2-1e-5 for l in layers for g in sense_guard[net][l]) or any(wg.distance(g)<.2-1e-5 for g in sense_guard[net][face]):continue
  cost=radius+4*len(ripped)
  if cost>=best_cost:continue
  route=[{'route_type':'wire','x':p['x'],'y':p['y'],'layer':face,'width':.15},{'route_type':'wire','x':x,'y':y,'layer':face,'width':.15},{'route_type':'via','x':x,'y':y,'from_layer':face,'to_layer':'inner2','layers':layers,'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}]
  best=(route,[(wg,[face],'track'),(vg,layers,'via')],[(net,layers,vg)],ripped);best_cost=cost
  if cost==0:break
 return (best,f'terminal fanout, {len(best[3])} signal routes displaced') if best else (None,'no safe terminal fanout')

maskcache={};failurecache={};goalmaskcache={}
def attempt(net,start,goal,grid,epsilon,soft=False,_retry=0):
 key=(net,grid,epsilon,soft)
 # Hard routing is a subset of the relaxed routing graph. An exhausted
 # relaxed component cannot acquire a path by adding more obstacles.
 relaxed_key=(net,grid,epsilon,True)
 if not soft and relaxed_key in maskcache:
  relaxed=maskcache[relaxed_key];sx=round((start[0]-relaxed[0][0])/grid);sy=round((start[1]-relaxed[1][0])/grid);sl=start[2]
  if 0<=sx<relaxed[2] and 0<=sy<relaxed[3]:
   if not relaxed[4][sl,sy,sx]:return None,'source blocked in the relaxed graph'
   reached=failurecache.get((relaxed_key,id(goal)))
   if reached is not None and reached[sl,sy,sx]:return None,'source disconnected in the exhausted relaxed graph'
 if key in maskcache:xaxis,yaxis,w,h,masks,vmask,other,hard,via_hard,smask,vsmask=maskcache[key]
 else:
  gp=nearest_points(Point(start[0],start[1]),unary_union(list(goal.values())))[1]
  def axis(a,b):
   return np.arange(round(113/grid)+1)*grid-56.5
  xaxis=axis(start[0],gp.x);yaxis=axis(start[1],gp.y);w=len(xaxis);h=len(yaxis);xx=xaxis[None,:];yy=yaxis[:,None]
  def raster(g):return contains_xy(g,xx,yy)
  allowed=board.buffer(-.575-epsilon).difference(npth.buffer(.575+epsilon)).difference(hardware.buffer(.075+epsilon));base=raster(allowed)
  hard={l:unary_union([a.get('routing_g',a['g']) for a in items if a['layer']==l and wire_obstacle(a,net,soft)]+sense_guard[net][l]) for l in layers}
  other={l:unary_union([a.get('routing_g',a['g']) for a in items if a['net']!=net and a['layer']==l and not(a['kind']=='pour' and (l=='inner2' or ground_escapes))]) for l in layers} if soft else hard
  masks=np.stack([base & ~raster(hard[l].buffer(.275+epsilon)) for l in layers])
  # The fourth layer is available for difficult escapes. A high A* step cost
  # keeps these paths short while retaining fill around the actual copper.
  via_hard={l:unary_union([a.get('routing_g',a['g']) for a in items if a['net']!=net and a['layer']==l and a['kind']!='pour' and (not soft or immutable(a,net))]+sense_guard[net][l]) for l in layers}
  # Via-in-pad is enabled by the source rules and uses filled/capped barrels.
  # Foreign pads remain excluded by via_hard; an own-net SMT pad is legal.
  via=board.buffer(-.7-epsilon).difference(npth.buffer(.7+epsilon)).difference(hardware.buffer(.2+epsilon))
  via=via.difference(unary_union([g for _,_,g in barrels]).buffer(.251))
  # Apply the hard copper exclusion in the raster as well. Complex polygon
  # differences can retain tiny invalid allowed pockets near dense copper.
  via_exclusion=unary_union(list(via_hard.values())).buffer(.4+epsilon)
  vmask=raster(via)&~raster(via_exclusion)
  smask=np.stack([raster(other[l].buffer(.275+epsilon)) for l in layers]) if soft else None
  vsmask=raster(unary_union(list(other.values())).buffer(.4+epsilon)) if soft else None
  maskcache[key]=(xaxis,yaxis,w,h,masks,vmask,other,hard,via_hard,smask,vsmask)
 sx=round((start[0]-xaxis[0])/grid);sy=round((start[1]-yaxis[0])/grid);sl=start[2]
 if not(0<=sx<w and 0<=sy<h):return None,'source outside grid'
 if not masks[sl,sy,sx]:return None,'blocked source'
 failed_key=(key,id(goal))
 if failed_key in failurecache and failurecache[failed_key][sl,sy,sx]:return None,'disconnected source region'
 if failed_key not in goalmaskcache:
  # A 0.15 mm round-ended wire connects within its 0.075 mm radius.
  goalmaskcache[failed_key]=np.stack([contains_xy(goal.get(l,Polygon()).buffer(.074),xaxis[None,:],yaxis[:,None]) for l in layers]) & masks
 goals=goalmaskcache[failed_key]
 if not goals.any():return None,'no target grid points'
 gy,gx=np.where(np.any(goals,axis=0))
 header=[w,h,sx,sy,sl,int(gx.min()),int(gy.min()),int(gx.max()),int(gy.max())]
 with (work/'masks.bin').open('wb') as f:
  f.write(struct.pack('<9i',*header));f.write(masks.astype(np.uint8).tobytes());f.write(vmask.astype(np.uint8).tobytes());f.write(goals.astype(np.uint8).tobytes())
  if soft:f.write(smask.astype(np.uint8).tobytes());f.write(vsmask.astype(np.uint8).tobytes())
 (work/'path.json').unlink(missing_ok=True)
 completed=subprocess.run(['/tmp/octopus-routing/grid-astar',str(work/'masks.bin'),str(work/'path.json')],check=False)
 if completed.returncode not in [0,1] or not(work/'path.json').exists():raise RuntimeError('Grid search failed without a valid result: '+str(completed.returncode))
 result=json.loads((work/'path.json').read_text())
 if not result['found']:
  if result.get('exhausted'):
   reached=np.fromfile(str(work/'path.json')+'.reachable.bin',dtype=np.uint8).reshape(4,h,w).astype(bool)
   failurecache[failed_key]=failurecache.get(failed_key,False)|reached
  return None,f"no path ({result['expanded']} cells)"
 path=result['path'];assert path[0]==[sx,sy,sl],'Grid search returned a path for another source.'
 compressed=[path[0]]
 for i in range(1,len(path)-1):
  before=tuple(path[i][k]-path[i-1][k] for k in range(3));after=tuple(path[i+1][k]-path[i][k] for k in range(3))
  if before!=after:compressed.append(path[i])
 if len(path)>1:compressed.append(path[-1])
 route=[{'route_type':'wire','x':start[0],'y':start[1],'width':.15,'layer':layers[sl]}]
 for x,y,l in compressed:
  pos={'x':float(xaxis[x]),'y':float(yaxis[y])};prev=route[-1]
  if prev['layer']!=layers[l]:
   route.append({'route_type':'via',**pos,'from_layer':prev['layer'],'to_layer':layers[l],'layers':layers,'via_diameter':.4,'via_hole_diameter':.2})
  route.append({'route_type':'wire',**pos,'layer':layers[l],'width':.15})
 # Validate the actual segments, not just the grid cells.
 newitems=[];newbarrels=[];ripped=set()
 collision_tree=STRtree([a['g'] for a in items]) if soft else None
 def collisions(g,ls,skip_planes=False):
  for index in collision_tree.query(g,predicate='dwithin',distance=.2):
   a=items[int(index)]
   if a['net']!=net and a['layer'] in ls and not(a['kind']=='pour' and (skip_planes or a['layer']=='inner2' or ground_escapes)) and g.distance(a['g'])<.2-1e-5:
    if immutable(a,net):return False
    ripped.add(a['id'].rsplit(':',1)[0])
  return True
 for i,p in enumerate(route):
  if p['route_type']=='via':
   g=Point(p['x'],p['y']).buffer(.2,quad_segs=32)
   # Two 0.2 mm drills need at least 0.2 mm of board between them.
   # The raster excludes existing drills; also check vias in this new path.
   if any(g.centroid.distance(previous.centroid)<.4-1e-5 for _,_,previous in newbarrels):
    if _retry<8:
     ix=round((p['x']-xaxis[0])/grid);iy=round((p['y']-yaxis[0])/grid);r=math.ceil(.25/grid)
     vmask[max(0,iy-r):min(h,iy+r+1),max(0,ix-r):min(w,ix+r+1)]=False
     return attempt(net,start,goal,grid,epsilon,soft,_retry+1)
    return None,'new-path drill spacing'
   closest=min(g.distance(via_hard[l]) for l in layers)
   if closest<.2-1e-5:
    if _retry<8:
     # Exact geometry is authoritative. Exclude a rejected via neighborhood
     # and search another path instead of repeating the same invalid site.
     ix=round((p['x']-xaxis[0])/grid);iy=round((p['y']-yaxis[0])/grid);r=math.ceil(.25/grid)
     x0=max(0,ix-r);x1=min(w,ix+r+1);y0=max(0,iy-r);y1=min(h,iy+r+1)
     vmask[y0:y1,x0:x1]=False
     return attempt(net,start,goal,grid,epsilon,soft,_retry+1)
    return None,f"via clearance {p['x']:.5f},{p['y']:.5f}: {closest:.6f} mm"
   if soft and not collisions(g,layers,skip_planes=True):return None,'via pad clearance'
   if not board.buffer(-.5+1e-6).covers(g) or g.distance(npth)<.5-1e-5 or g.intersection(hardware).area>1e-8:return None,'via boundary clearance'
   newitems.append((g,layers,'via'));newbarrels.append((net,layers,g))
  elif i:
   a=route[i-1];l=p['layer'];g=LineString([(a['x'],a['y']),(p['x'],p['y'])]).buffer(.075,quad_segs=32)
   if g.distance(hard[l])<.2-1e-5:return None,'track clearance'
   if soft and not collisions(g,[l]):return None,'track pad clearance'
   if not board.buffer(-.5+1e-6).covers(g) or g.distance(npth)<.5-1e-5 or g.intersection(hardware).area>1e-8:return None,'track boundary clearance'
   newitems.append((g,[l],'track'))
 return (route,newitems,newbarrels,ripped),f"{result['expanded']} cells, {len(ripped)} items rerouted"

def freeze_connected_geometry(net,persist=True):
 if os.environ.get('ROUTING_FREEZE_CONNECTED')!='1':return
 if nets[net] in ['GND','VBUS'] and os.environ.get('ROUTING_FREEZE_REFERENCES')!='1':return
 locked_nets.add(net)
 renames={}
 for a in j:
  if a['type'] not in ['pcb_trace','pcb_via']:continue
  n=a.get('connection_name') or a.get('source_net_id') or scope['trace_net'].get(a.get('source_trace_id'))
  key='pcb_trace_id' if a['type']=='pcb_trace' else 'pcb_via_id';identity=a[key]
  if n==net and not identity.startswith(('seed_','kelvin_','plane_stitch_')):
   renames[identity]='seed_frozen_'+nets[net]+'_'+identity;a[key]=renames[identity]
 if not renames:return
 for a in items:
  split=a['id'].rsplit(':',1);identity=split[0]
  if identity in renames:a['id']=renames[identity]+(':'+split[1] if len(split)>1 else '')
 if persist:
  (work/'pending.circuit.json').write_text(json.dumps(j));(work/'pending.circuit.json').replace(working)
 print('Preserved completed net:',nets[net],len(renames),'copper objects.',flush=True)

finished=max([int(m.group(1)) for x in j if x['type']=='pcb_trace' for m in [re.search(r'(?:^|_)finish_(\d+)',x['pcb_trace_id'])] if m],default=-1)+1
initial_sequence=finished
selected_names={v for v in os.environ.get('ROUTING_NETS','').split(',') if v}
first_order={name:i for i,name in enumerate(os.environ.get('ROUTING_FIRST_NETS','').split(',')) if name}
last_order={name:i for i,name in enumerate(os.environ.get('ROUTING_LAST_NETS','').split(',')) if name}
failures=[];starttime=time.time();dirty={net for net in nets if (not selected_names or nets[net] in selected_names) and len(polygons(net)[0])>1};bestScore=len(dirty)
(work/'best.circuit.json').write_text(json.dumps(j))
if os.environ.get('ROUTING_FREEZE_INITIAL_CONNECTED')=='1':
 for net in nets:
  if net not in dirty:freeze_connected_geometry(net,persist=False)
 (work/'pending.circuit.json').write_text(json.dumps(j));(work/'pending.circuit.json').replace(working)
for passindex in range(int(os.environ.get('ROUTING_PASSES','3'))):
 repair_order={f['net']:i for i,f in enumerate(failures)}
 if passindex and os.environ.get('ROUTING_REPAIR_EPOCHS')=='1':locked_nets.clear()
 failures=[];print('Finishing pass',passindex+1,':',len(dirty),'nets to join.',flush=True)
 for net,name in sorted(nets.items(),key=lambda kv:(2,last_order[kv[1]]) if kv[1] in last_order else (-1,repair_order[kv[1]]) if kv[1] in repair_order else (0,first_order[kv[1]]) if kv[1] in first_order else(1,route_rank(kv[0]),kv[1])):
  if selected_names and name not in selected_names:continue
  if net not in dirty:continue
  maskcache.clear()
  for iteration in range(30):
   groups,terminals=polygons(net)
   if len(groups)<=1:dirty.discard(net);freeze_connected_geometry(net);break
   failurecache.clear();goalmaskcache.clear();target=max(groups,key=lambda r:(len(terminals[r]),len(groups[r]),sum(g.area for g in groups[r].values())));goal=groups[target];goalflat=unary_union(list(goal.values()))
   candidates=[]
   for r in groups:
    if r==target:continue
    for p in terminals[r]:
     for layer in p['layers']:candidates.append((Point(p['x'],p['y']).distance(goalflat),p['x'],p['y'],layers.index(layer),r))
   for r,gl in groups.items():
    if r==target:continue
    for a in j:
     if a['type']=='pcb_via' and a.get('source_net_id')==net:
      ps=[{'x':a['x'],'y':a['y'],'layer':l} for l in a.get('layers',layers)]
     elif a['type']=='pcb_trace' and (a.get('connection_name')==net or scope['trace_net'].get(a.get('source_trace_id'))==net):
      ps=[v for v in a['route'] if v['route_type']=='wire']+[
       {'x':v['x'],'y':v['y'],'layer':l}
       for v in a['route'] if v['route_type']=='via' for l in layers]
     else:continue
     for v in ps:
      l=v['layer'];pt=Point(v['x'],v['y'])
      if l in gl and gl[l].distance(pt)<1e-5:candidates.append((pt.distance(goalflat),v['x'],v['y'],layers.index(l),r))
   candidate_counts=collections.Counter();ordered=[];overflow=[]
   # A through via is a real source on every copper layer. Preserve that
   # diversity instead of filling the candidate budget with outer-pad points.
   for candidate in sorted(set(candidates),key=lambda c:({2:0,0:1,3:2,1:3}[c[3]],c[0],c[1],c[2])):
    key=(candidate[4],candidate[3])
    if candidate_counts[key]>=2:overflow.append(candidate[:4])
    else:ordered.append(candidate[:4])
    candidate_counts[key]+=1
   candidates=ordered+overflow;success=False;reason='no source'
   settings=[(.1,.002,False),(0,0,False),(.05,.002,False)]
   if os.environ.get('ROUTING_RIPUP','0')=='1' and (passindex>0 or os.environ.get('ROUTING_SOFT_FROM_FIRST')=='1'):
    settings=([(.1,.002,True),(0,0,False),(.05,.002,True),(.1,.002,False),(.05,.002,False)]) if os.environ.get('ROUTING_SOFT_FROM_FIRST')=='1' else settings+[(.1,.002,True),(.05,.002,True)]
   if passindex==0 and os.environ.get('ROUTING_COARSE_FIRST')=='1':
    use_soft=os.environ.get('ROUTING_RIPUP')=='1';settings=[(.2,.004,use_soft),(.1,.002,use_soft),(0,0,False),(.05,.002,use_soft)]
   if os.environ.get('ROUTING_EXACT_GRID'):
    settings=[(float(os.environ['ROUTING_EXACT_GRID']),float(os.environ.get('ROUTING_SEARCH_EPSILON','0')),os.environ.get('ROUTING_RIPUP')=='1')]
   for grid,eps,soft in settings:
    seen_cells=set()
    for _,x,y,l in (candidates if grid else [(0,0,0,0)]):
     if grid:
      cell=(round((x+56.5)/grid),round((y+56.5)/grid),l)
      if cell in seen_cells:continue
      seen_cells.add(cell)
     result,reason=attempt(net,(x,y,l),goal,grid,eps,soft) if grid else terminal_escape(net,groups,terminals)
     if result:
      route,newitems,newbarrels,ripped=result;identity=f'finish_{finished}' if grid else 'seed_'+str(max([int(a['pcb_trace_id'].split('_')[1]) for a in j if a['type']=='pcb_trace' and a['pcb_trace_id'].startswith('seed_') and a['pcb_trace_id'].split('_')[1].isdigit()]+[39999])+1)
      if ripped:
       # Removed mutable copper was absent from the relaxed hard mask already.
       # Retaining its old soft penalty and drill exclusion is conservative;
       # each new path still receives the exact live-copper checks below.
       removed=[a for a in items if a['id'].rsplit(':',1)[0] in ripped]
       dirty.update(a['net'] for a in removed if a['net'] in nets)
       removed_vias={(a['net'],a['g'].wkb) for a in removed if a['kind']=='via'}
       items[:]=[a for a in items if a['id'].rsplit(':',1)[0] not in ripped]
       barrels[:]=[(n,ls,g) for n,ls,g in barrels if (n,g.wkb) not in removed_vias]
       j[:]=[t for t in j if t['type'] not in ['pcb_trace','pcb_via'] or t.get('pcb_trace_id',t.get('pcb_via_id')) not in ripped]
      cutters={l:unary_union([g.buffer(.25) for g,ls,kind in newitems if l in ls]) for l in layers}
      for a in items:
       if a['kind']=='pour' and a['net']!=net and a['g'].intersects(cutters[a['layer']]):
        a['g']=safe_difference(a['g'],cutters[a['layer']]);dirty.add(a['net'])
      # Persist split plane islands as valid native BRep polygons.
      j[:]=[a for a in j if a['type']!='pcb_copper_pour']
      for a in [a for a in items if a['kind']=='pour']:
       polygons_for_pour=polygon_parts(a['g'])
       for island,pg in enumerate(polygons_for_pour):
        if pg.is_empty:continue
        def ring(r):return {'vertices':[{'x':float(x),'y':float(y),'bulge':0} for x,y in list(r.coords)[:-1]]}
        j.append({'type':'pcb_copper_pour','pcb_copper_pour_id':a['id']+'_'+str(island),'source_net_id':a['net'],'layer':a['layer'],'shape':'brep','brep_shape':{'outer_ring':ring(pg.exterior),'inner_rings':[ring(r) for r in pg.interiors]}})
      for k,(g,ls,kind) in enumerate(newitems):add(g,net,ls,f'{identity}:{k}',kind)
      # Cached masks remain valid for foreign copper, but each new drill must
      # also reserve space against subsequent vias on this same net.
      for _,_,g in newbarrels:
       excluded=g.buffer(.251)
       for cached in maskcache.values():
        xa,ya,_,_,_,vm=cached[:6];x0,y0,x1,y1=excluded.bounds
        ix0,ix1=np.searchsorted(xa,[x0,x1],side='left');iy0,iy1=np.searchsorted(ya,[y0,y1],side='left');ix1=min(len(xa),ix1+1);iy1=min(len(ya),iy1+1)
        if ix1>ix0 and iy1>iy0:vm[iy0:iy1,ix0:ix1] &= ~contains_xy(excluded,xa[None,ix0:ix1],ya[iy0:iy1,None])
      barrels.extend(newbarrels);j.append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'route':route});finished+=1
      (work/'pending.circuit.json').write_text(json.dumps(j));(work/'pending.circuit.json').replace(working);action='joined an island' if grid else 'added a terminal escape';print(f'{name}: {action}, {reason}, {grid} mm grid ({round(time.time()-starttime)}s)',flush=True);success=True;break
    if success:break
   if not success:failures.append({'net':name,'islands':len(groups),'reason':reason});print(name,'remaining:',len(groups),reason,flush=True);break
  if len(dirty)<bestScore:
   bestScore=len(dirty);(work/'best.circuit.json').write_text(json.dumps(j));print('Best remaining:',bestScore,'nets.',flush=True)
 if not dirty:break
traces=[x for x in j if x['type']=='pcb_trace'];(work/'traces.json').write_text(json.dumps(traces,indent=2)+'\n')
(work/'status.json').write_text(json.dumps({'addedConnections':finished-initial_sequence,'nextTraceSequence':finished,'failures':failures,'selectedNets':sorted(selected_names) or None,'removedItems':len(bad),'seconds':time.time()-starttime},indent=2)+'\n')
print('Finishing result:',finished-initial_sequence,'connections added;',len(failures),'nets remain.',flush=True)
