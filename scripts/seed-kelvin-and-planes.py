"""Route paired shunt pickup branches and seed local reference-plane access.
Both ends of each negative pickup have an antipad in the GND plane. Their
first GND connection is the corresponding shunt electrode.
"""
import json,sys,math,struct,subprocess
from pathlib import Path
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point,LineString,Polygon,box,mapping
from shapely.ops import unary_union
work=Path('routing-work/revision/kelvin');work.mkdir(parents=True,exist_ok=True)
src=Path('routing-work/revision/seed.circuit.json');scope={'__name__':'copper_geometry'};sys.argv=['check-copper.py',str(src),str(work/'initial-audit.json')]
try:exec(compile(Path('scripts/check-copper.py').read_text(),'check-copper.py','exec'),scope)
except SystemExit:pass
j=scope['j'];items=scope['items'];layers=scope['layers'];ports=scope['ports'];sp=scope['sourceports'];sources=scope['sources'];netids={v:k for k,v in scope['nets'].items()}
pp={}
for pid,p in ports.items():
 s=sp.get(p.get('source_port_id'),{});ref=sources.get(s.get('source_component_id'));pin=s.get('pin_number')
 if pin is None:pin=next((int(h.removeprefix('pin')) for h in s.get('port_hints',[]) if h.removeprefix('pin').isdigit()),None)
 if pin is not None and (ref,pin) not in pp:pp[(ref,pin)]=p
traceby={}
for a in j:
 if a['type']=='source_trace':
  for n in a.get('connected_source_net_ids',[]):traceby[n]=a['source_trace_id']
new=[];negative_guards=[];manifest=[];sn_ports={pp[('U2',i)]['pcb_port_id'] for i in [10,11,20]}
drills=[]
for obj in j:
 if obj['type']=='pcb_trace':
  drills.extend((v['x'],v['y'],v.get('via_hole_diameter',.3)/2) for v in obj['route'] if v['route_type']=='via')
 elif obj['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in obj:drills.append((obj['x'],obj['y'],obj['hole_diameter']/2))

def tr(net,pts,layer,width=.15,negative=False):
 identity='kelvin_'+str(len(new));route=[{'route_type':'wire','x':float(x),'y':float(y),'width':width,'layer':layer} for x,y in pts]
 new.append({'type':'pcb_trace','pcb_trace_id':identity,'source_trace_id':traceby[net],'connection_name':net,'route':route})
 g=LineString(pts).buffer(width/2,quad_segs=24)
 items.append({'g':g,'net':net,'layer':layer,'id':identity,'kind':'track'})
 if negative:negative_guards.append(g)
 return identity

def via(net,x,y,identity=None):
 identity=identity or 'kelvin_'+str(len(new));r=[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.15},{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'inner2','layers':layers,'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.15}]
 new.append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'source_trace_id':traceby[net],'route':r});g=Point(x,y).buffer(.2,quad_segs=32)
 drills.append((x,y,.1))
 for l in layers:items.append({'g':g,'net':net,'layer':l,'id':identity,'kind':'via'})
 return identity

def coords(p):return (p['x'],p['y'])

def centre_path(start,end,letter):
 # A .15/.6-mm pair has a .375-mm copper envelope about its centreline.
 obstacles=unary_union([a['g'] for a in items if a['layer']=='inner2'])
 board=scope['outline'].buffer(-.88).difference(unary_union([Point(h['x'],h['y']).buffer(h['hole_diameter']/2+.88,quad_segs=64) for h in scope['bytype']['pcb_hole']]))
 for c in scope['bytype']['pcb_cutout']:
  if c['shape']=='circle':board=board.difference(Point(c['center']['x'],c['center']['y']).buffer(c['radius']+.88,quad_segs=128))
 board=board.difference(unary_union(scope['hardware']).buffer(.38))
 allowed=board.difference(obstacles.buffer(.578))
 step=.1;axis=np.arange(-560,561)*step;w=h=len(axis);xx=axis[None,:];yy=axis[:,None]
 masks=np.zeros((4,h,w),dtype=np.uint8);mask=contains_xy(allowed,xx,yy)
 if letter=='U':mask &= yy<=end[1]+1e-7
 elif letter=='V':mask &= ~((np.abs(xx-end[0])<2)&(yy>end[1]+1e-7))
 else:mask &= yy>=end[1]-1e-7
 if letter=='U':mask &= xx<=-22+1e-7
 masks[2]=mask;goals=np.zeros_like(masks);sx,sy=[round((v+56)/step) for v in start];gx,gy=[round((v+56)/step) for v in end]
 if not masks[2,sy,sx] or not masks[2,gy,gx]:raise RuntimeError(f'{letter}: blocked pair endpoint {start} {end}')
 goals[2,gy,gx]=1;header=[w,h,sx,sy,2,gx,gy,gx,gy]
 binary=Path('/tmp/octopus-routing/grid-astar')
 if not binary.exists():subprocess.run(['g++','-O3','-std=c++17','scripts/grid-astar.cpp','-o',str(binary)],check=True)
 with (work/'mask.bin').open('wb') as f:f.write(struct.pack('<9i',*header));f.write(masks.tobytes());f.write(np.zeros((h,w),dtype=np.uint8).tobytes());f.write(goals.tobytes())
 subprocess.run([str(binary),str(work/'mask.bin'),str(work/'path.json')],check=False)
 result=json.loads((work/'path.json').read_text())
 if not result['found']:raise RuntimeError(f'{letter}: no clear paired route')
 raw=[(float(axis[x]),float(axis[y])) for x,y,l in result['path']];points=[raw[0]]
 for k in range(1,len(raw)-1):
  a,b,c=raw[k-1:k+2]
  if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-6:points.append(b)
 points.append(raw[-1])
 # Visibility smoothing preserves the full pair-envelope clearance and removes
 # sub-millimetre stair steps before offsetting the two conductors.
 smooth=[points[0]];idx=0
 while idx<len(points)-1:
  nxt=idx+1
  for k in range(len(points)-1,idx,-1):
   if allowed.buffer(1e-7).covers(LineString([points[idx],points[k]])):nxt=k;break
  smooth.append(points[nxt]);idx=nxt
 return smooth

configs=[
 ('U',9,10,(-17.8,-1.75),(-16,-2.25),(-21,-2),(-22,-2),(-22,18),(-22,20),'right'),
 ('V',12,11,(-18.25,-3.55),(-17.75,-5),(-16.9,-4),(-16.9,-3),(22,14.5),(22,16.5),'left'),
 ('W',19,20,(-21.75,-7.3),(-22.25,-6.1),(-20,-8),(-19,-8),(13,-19),(13,-21),'right')]
for i,(letter,sp_pin,sn_pin,sv,nv,start,astar_start,astar_end,end,side) in enumerate(configs,1):
 positive=netids['SHUNT_'+letter+'_TOP'];ground=netids['GND'];ps=coords(pp[('U2',sp_pin)]);ns=coords(pp[('U2',sn_pin)]);pt=coords(pp[('RSH'+str(i),1)]);nt=coords(pp[('RSH'+str(i),2)])
 # Route the centre first; the four endpoint vias are deliberately excluded
 # from the pair corridor and are joined by explicit end stubs below.
 path=[start]+centre_path(astar_start,astar_end,letter)+[end];line=LineString(path)
 if not line.is_simple:raise RuntimeError(letter+': centreline doubles back')
 offset=.3 if side=='left' else -.3
 pcurve=line.offset_curve(offset,join_style=1,quad_segs=6);ncurve=line.offset_curve(-offset,join_style=1,quad_segs=6)
 if pcurve.geom_type!='LineString' or ncurve.geom_type!='LineString':raise RuntimeError(letter+': invalid offset pair')
 target_vias={'U':((-17.9,26.5),(-25.4,22.5)),'V':((17.65,21.5),(24.9625,21.5)),'W':((8.85,-26.5),(15.9625,-26.5))}
 pv,nvt=target_vias[letter]
 ppoints=[sv,*pcurve.coords,pv];npoints=[nv,*ncurve.coords,*([(ncurve.coords[-1][0],21.5)] if letter=='U' else []),nvt]
 def pickup_stub(p,v):return [p,(p[0],p[1]+math.copysign(1.55,v[1]-p[1])),v]
 tr(positive,pickup_stub(pt,pv),'bottom');tr(ground,pickup_stub(nt,nvt),'bottom',negative=True)
 tr(positive,[ps,sv],'bottom');tr(ground,[ns,nv],'bottom',negative=True)
 via(positive,*sv);via(ground,*nv);via(positive,*pv);via(ground,*nvt)
 a=tr(positive,ppoints,'inner2');b=tr(ground,npoints,'inner2',negative=True)
 manifest.append({'phase':letter,'positiveDriverPin':sp_pin,'negativeDriverPin':sn_pin,'shunt':'RSH'+str(i),'isolateFromGroundPlaneAt':[{'x':v[0],'y':v[1],'radius':.51} for v in [nv,nvt]],'positiveTraceId':a,'negativeTraceId':b,'positiveLengthMm':LineString(ppoints).length,'negativeLengthMm':LineString(npoints).length,'pairPitchMm':.6,'traceWidthMm':.15,'planeLayer':'inner2','sourceVia':list(nv),'pickupGroundVia':list(nvt),'groundPickupPad':list(nt)})
 print('Paired Kelvin pickup',letter,round(line.length,2),'mm',flush=True)

# Local GND access makes the reference plane a short connection for every IC
# decoupler. These vias require filled/capped via-in-pad manufacture.
count=0;rejected=[]
for pad in list(scope['bytype']['pcb_smtpad']):
 pid=pad.get('pcb_port_id')
 if scope['portnet'].get(pid)!=netids['GND'] or pid in sn_ports:continue
 p=Point(pad['x'],pad['y']);g=p.buffer(.2,quad_segs=32)
 if any(a['kind']=='via' and a['net']==netids['GND'] and a['g'].covers(p) for a in items):continue
 if any(math.hypot(p.x-x,p.y-y)<r+.1+.2-1e-5 for x,y,r in drills):rejected.append(pid);continue
 if any(a['net']!=netids['GND'] and a['g'].distance(g)<.2-1e-5 for a in items):rejected.append(pid);continue
 ref=scope['pcb_refs'].get(pad.get('pcb_component_id'),'')
 if not ref.startswith('RSH') and any(guard.distance(g)<.25 for guard in negative_guards):rejected.append(pid);continue
 if not scope['outline'].buffer(-.5).covers(g) or any(g.intersects(h) for h in scope['hardware']):rejected.append(pid);continue
 via(netids['GND'],pad['x'],pad['y'],identity='plane_stitch_'+str(count));count+=1

Path('data/kelvin-routing.json').write_text(json.dumps({'branches':manifest,'groundViaInPadCount':count,'requires':'Filled and capped via-in-pad manufacture; antipads at every negative pickup source and shunt-end via.'},indent=2)+'\n')
Path('routing-work/revision/complete-seed.circuit.json').write_text(json.dumps(j+new))
print('Added',count,'local GND plane vias;',len(rejected),'pads require routed plane access.')
