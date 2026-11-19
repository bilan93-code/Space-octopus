"""Add clearance-checked, short face routes to new through-via escape sites.

Uses exact current copper and drills, ignoring only mutable reference fills.
No existing trace or barrel is removed. A full board audit follows this step.
"""
import json,sys,math,heapq,collections,re
from pathlib import Path
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point,Polygon,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree

src=Path(sys.argv[1]);out=Path(sys.argv[2]);ripup='--ripup' in sys.argv[3:];open_exit='--open-exit' in sys.argv[3:];rip_frozen='--rip-frozen-signals' in sys.argv[3:];rip_fanout='--rip-signal-fanout' in sys.argv[3:];suffix=next((a.split('=',1)[1] for a in sys.argv[3:] if a.startswith('--suffix=')),'');requested={a for a in sys.argv[3:] if not a.startswith('--')};selected={a for a in requested if '.' not in a};selected_ports={a for a in requested if '.' in a};s={}
minimum_radius=float(next((a.split('=',1)[1] for a in sys.argv[3:] if a.startswith('--minimum-radius=')),'1.5'))
minimum_own_via_distance=float(next((a.split('=',1)[1] for a in sys.argv[3:] if a.startswith('--minimum-own-via-distance=')),'1.05'))
via_goal_window=next((list(map(float,a.split('=',1)[1].split(','))) for a in sys.argv[3:] if a.startswith('--via-window=')),None)
if via_goal_window:assert len(via_goal_window)==4 and via_goal_window[0]<via_goal_window[2] and via_goal_window[1]<via_goal_window[3]
debug='--debug' in sys.argv[3:]
rip_reference_fanout='--rip-reference-fanout' in sys.argv[3:]
rip_gate_fanout='--rip-gate-fanout' in sys.argv[3:]
if open_exit:
 try:from scipy.ndimage import binary_propagation
 except ImportError:
  def binary_propagation(seed,mask):
   reached=seed.copy()
   while True:
    nxt=reached.copy();nxt[1:,:]|=reached[:-1,:];nxt[:-1,:]|=reached[1:,:];nxt[:,1:]|=reached[:,:-1];nxt[:,:-1]|=reached[:,1:];nxt&=mask
    if np.array_equal(nxt,reached):return reached
    reached=nxt
code=Path('scripts/check-copper.py').read_text();sys.argv=['check-copper.py',str(src),'/tmp/escape-open-unused.json']
exec(compile(code.split('# Distinct-net copper')[0],'geometry','exec'),s)
all_net_names=s['nets']
if selected or selected_ports:
 requested_ids={n for n,name in all_net_names.items() if name in selected}|{s['portnet'].get(pid) for pid in s['ports'] if s['portlabel'](pid) in selected_ports}
 s['nets']={n:name for n,name in all_net_names.items() if n in requested_ids}
exec(compile('connectivity=[];netGraphs={}'+code.split('connectivity=[];netGraphs={}')[1].split('unconnected=[n for n in connectivity')[0],'connectivity','exec'),s)
s['nets']=all_net_names
j=s['j'];items=[a for a in s['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in items]);extra=[];added=[];reports=[]
outline=Polygon([(p['x'],p['y']) for p in s['bytype']['pcb_board'][0]['outline']])
refs={c['pcb_component_id']:s['sources'].get(c.get('source_component_id'),'') for c in s['bytype']['pcb_component']}
hardware=unary_union([box(h['x']-4.75,h['y']-4.75,h['x']+4.75,h['y']+4.75).buffer(.2) for h in s['bytype']['pcb_hole'] if refs.get(h.get('pcb_component_id'),'').startswith('H')])
holes=unary_union([Point(h['x'],h['y']).buffer(h['hole_diameter']/2) for h in s['bytype']['pcb_hole']]+[Point(c['center']['x'],c['center']['y']).buffer(c['radius']) for c in s['bytype']['pcb_cutout'] if c['shape']=='circle'])
wire_area=outline.buffer(-.578).difference(holes.buffer(.578)).difference(hardware.buffer(.078))
via_area=outline.buffer(-.703).difference(holes.buffer(.703)).difference(hardware.buffer(.203))
drills=[];own_vias=collections.defaultdict(list)
for t in s['bytype']['pcb_trace']:
 n=t.get('connection_name') or s['trace_net'].get(t.get('source_trace_id'))
 for v in t['route']:
  if v['route_type']=='via':drills.append(Point(v['x'],v['y']).buffer(v.get('via_hole_diameter',.3)/2+.303));own_vias[n].append(Point(v['x'],v['y']))
for v in s['bytype']['pcb_via']+s['bytype']['pcb_plated_hole']:
 drills.append(Point(v['x'],v['y']).buffer(v.get('hole_diameter',max(v.get('hole_width',0),v.get('hole_height',0)))/2+.303))
 if v['type']=='pcb_via':own_vias[v.get('source_net_id')].append(Point(v['x'],v['y']))
drill_union=unary_union(drills);portbylabel={s['portlabel'](pid):p for pid,p in s['ports'].items()}
trace_ids={n:t['source_trace_id'] for t in s['bytype']['source_trace'] for n in t.get('connected_source_net_ids',[])}
existing={a['pcb_trace_id'] for a in s['bytype']['pcb_trace']};wide_ids={a['pcb_trace_id'] for a in s['bytype']['pcb_trace'] if any(v.get('width',0)>=.6 for v in a['route'])};pickup_points=[Point(*b[k]) for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches'] for k in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia']];step=.05;radius=6.;count=round(2*radius/step)+1
for status in s['connectivity']:
 name=status['net']
 if status['connected'] or selected and name not in selected or selected_ports and not any(label in selected_ports for group in status['islands'] for label in group) or name.startswith('SHUNT_'):continue
 net=next(n for n,v in s['nets'].items() if v==name)
 for group in status['islands']:
  if len(group)>2:continue
  candidates=[{**portbylabel[label],'layers':[layer]} for label in dict.fromkeys(group) if label in portbylabel and(not selected_ports or label in selected_ports) for layer in portbylabel[label]['layers']]
  if not candidates:continue
  best=None
  for p in candidates:
   label=s['portlabel'](p['pcb_port_id']);identity='seed_local_repair_'+label.replace('.','_')+('_'+suffix if suffix else '')
   if identity in existing:continue
   xaxis=p['x']+np.arange(count)*step-radius;yaxis=p['y']+np.arange(count)*step-radius
   if open_exit:
    xaxis=np.arange(count)*step+math.floor((p['x']-radius+56.5)/step)*step-56.5;yaxis=np.arange(count)*step+math.floor((p['y']-radius+56.5)/step)*step-56.5
   xx=xaxis[None,:];yy=yaxis[:,None];window=box(xaxis[0]-1,yaxis[0]-1,xaxis[-1]+1,yaxis[-1]+1)
   nearby=[items[int(k)] for k in tree.query(window)]+[a for a in extra if a['g'].intersects(window)]
   foreign=[a for a in nearby if a['net']!=net or name=='GND' and(a.get('id','').startswith('kelvin_') or a.get('kind')=='via' and any(a['g'].centroid.distance(pv)<1e-5 for pv in pickup_points) or a.get('port') and s['portlabel'](a['port']) in ['U2.10','U2.11','U2.20'])];face=p['layers'][0]
   def protected(a):
    identity=a.get('id','')
    ordinary=identity.startswith('finish_') or rip_frozen and identity.startswith('seed_frozen_')
    foreign_name=s['nets'].get(a['net'],'')
    if rip_fanout and (rip_reference_fanout or foreign_name not in ['GND','VBUS','V12','V5','V3V3','VDDA3V3']) and not foreign_name.startswith(('SHUNT_','PH_')) and (rip_gate_fanout or not foreign_name.startswith(('GH_','GL_'))):
     ordinary|=bool(re.match(r'seed_\d',identity)) or identity.startswith(('seed_local_escape_','saved_pcb_via_'))
    supplies={'GND','VBUS','DC_IN','V12','V5','V3V3','VDDA3V3','CP_L','CP_H','VCP','DRV_VGLS','DRV_DVDD','BUCK12_SW','BUCK5_SW','BST12','FB12','FB5','RON12','RIPPLE12','HSE_CLK','OSC8_OUT'}
    if foreign_name.startswith('SHUNT_') or foreign_name in supplies and not rip_reference_fanout:ordinary=False
    return a.get('kind')=='pad' or identity.rsplit(':',1)[0] in wide_ids or a.get('kind')=='via' and(a['g'].bounds[2]-a['g'].bounds[0]>=.59 or any(a['g'].centroid.distance(pv)<1e-5 for pv in pickup_points)) or not ordinary
   hard=[a for a in foreign if not ripup or protected(a)]
   wire_block=unary_union([a['g'] for a in hard if a['layer']==face]).buffer(.278)
   via_block=unary_union([a['g'] for a in hard]).buffer(.403)
   soft_wire=contains_xy(unary_union([a['g'] for a in foreign if a['layer']==face]).buffer(.278),xx,yy) if ripup else np.zeros((count,count),dtype=bool)
   soft_via=contains_xy(unary_union([a['g'] for a in foreign]).buffer(.403),xx,yy) if ripup else np.zeros((count,count),dtype=bool)
   free=contains_xy(wire_area,xx,yy)&~contains_xy(wire_block,xx,yy)
   goal=contains_xy(via_area,xx,yy)&~contains_xy(via_block,xx,yy)&~contains_xy(drill_union,xx,yy)
   if via_goal_window:
    x0,y0,x1,y1=via_goal_window;goal&=(xx>=x0)&(xx<=x1)&(yy>=y0)&(yy<=y1)
   if open_exit:
    reachable=np.zeros_like(goal);boundary=np.zeros_like(goal);boundary[0,:]=boundary[-1,:]=True;boundary[:,0]=boundary[:,-1]=True;base=contains_xy(wire_area,xx,yy)
    for l in s['layers']:
     lf=base&~contains_xy(unary_union([a['g'] for a in hard if a['layer']==l]).buffer(.278),xx,yy)
     reachable|=binary_propagation(boundary&lf,mask=lf)
    goal&=reachable
   dist2=(xx-p['x'])**2+(yy-p['y'])**2;goal&=dist2>=minimum_radius**2
   for pv in own_vias[net]:goal&=(xx-pv.x)**2+(yy-pv.y)**2>=minimum_own_via_distance**2
   sx=round((p['x']-xaxis[0])/step);sy=round((p['y']-yaxis[0])/step)
   if debug:print(json.dumps({'terminal':label,'freeStart':bool(free[sy,sx]),'goalCells':int(goal.sum())}),flush=True)
   if not free[sy,sx] or not goal.any():continue
   # Fourteen/ten weights preserve diagonal length without corner cutting.
   start=sy*count+sx;distance={start:0};parent={};queue=[(0,start)];end=None;end_cost=float('inf')
   while queue:
    d,i=heapq.heappop(queue)
    if d!=distance[i]:continue
    if d>=end_cost:break
    y,x=divmod(i,count)
    if goal[y,x] and d+(5000 if soft_via[y,x] else 0)<end_cost:end=i;end_cost=d+(5000 if soft_via[y,x] else 0)
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
     nx=x+dx;ny=y+dy
     if nx<0 or ny<0 or nx>=count or ny>=count or not free[ny,nx]:continue
     if dx and dy and(not free[y,nx] or not free[ny,x]):continue
     k=ny*count+nx;nd=d+(14 if dx and dy else 10)+(500 if soft_wire[ny,nx] else 0)
     if nd<distance.get(k,float('inf')):distance[k]=nd;parent[k]=i;heapq.heappush(queue,(nd,k))
   if end is None:
    if debug:print('No escape reached; explored',len(distance),'cells.',flush=True)
    continue
   path=[end]
   while path[-1] in parent:path.append(parent[path[-1]])
   path.reverse();vertices=[(float(xaxis[i%count]),float(yaxis[i//count])) for i in path];compressed=[vertices[0]]
   for a,b,c in zip(vertices,vertices[1:],vertices[2:]):
    if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-8:compressed.append(b)
   compressed.append(vertices[-1]);compressed.insert(0,(p['x'],p['y']));wire=LineString(compressed).buffer(.075,quad_segs=32);vg=Point(*compressed[-1]).buffer(.2,quad_segs=32)
   conflicts=[a for a in foreign if vg.distance(a['g'])<.2-1e-5 or a['layer']==face and wire.distance(a['g'])<.2-1e-5]
   ripped={a['id'].rsplit(':',1)[0] for a in conflicts}
   if debug:print(json.dumps({'terminal':label,'candidateVia':compressed[-1],'conflicts':sorted(ripped),'protectedConflicts':sorted({a['id'].rsplit(':',1)[0] for a in conflicts if protected(a)})}),flush=True)
   if conflicts and(not ripup or len(ripped)>12 or len({a['net'] for a in conflicts})>3 or any(protected(a) for a in conflicts)):continue
   if not outline.buffer(-.5+1e-6).covers(vg) or vg.distance(holes)<.5-1e-5 or wire.intersects(hardware) or vg.intersects(hardware):continue
   route=[{'route_type':'wire','x':x,'y':y,'layer':face,'width':.15} for x,y in compressed];x,y=compressed[-1]
   route +=[{'route_type':'via','x':x,'y':y,'from_layer':face,'to_layer':'inner2','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}]
   proposal=({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'source_trace_id':trace_ids[net],'route':route},wire,vg,face,label,ripped)
   if best is None or wire.area<best[1].area:best=proposal
  if best:
   tr,wire,vg,face,label,ripped=best
   if ripped:
    items[:]=[a for a in items if a['id'].rsplit(':',1)[0] not in ripped];tree=STRtree([a['g'] for a in items]);j[:]=[a for a in j if a['type'] not in ['pcb_trace','pcb_via'] or a.get('pcb_trace_id',a.get('pcb_via_id')) not in ripped]
   added.append(tr);existing.add(tr['pcb_trace_id']);extra +=[{'g':wire,'net':net,'layer':face,'kind':'track','id':tr['pcb_trace_id']}]+[{'g':vg,'net':net,'layer':l,'kind':'via','id':tr['pcb_trace_id']} for l in s['layers']];own_vias[net].append(vg.centroid);drill_union=unary_union([drill_union,vg.centroid.buffer(.403)])
   report={'net':name,'terminal':label,'via':[vg.centroid.x,vg.centroid.y],'displaced':sorted(ripped),'wireLengthMm':LineString([(v['x'],v['y']) for v in tr['route'] if v['route_type']=='wire' and v['layer']==face]).length};reports.append(report);print(json.dumps(report),flush=True)
out.write_text(json.dumps([a for a in j if a['type']!='pcb_copper_pour']+added))
out.with_suffix('.escapes.json').write_text(json.dumps({'added':len(added),'escapes':reports},indent=2)+'\n');print('Added',len(added),'checked local escapes.',flush=True)
