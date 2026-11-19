"""Reserve wide VBUS paths before restoring the remaining signal connections."""
import json,sys,struct,subprocess,math
from pathlib import Path
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point,Polygon,LineString,box
from shapely.ops import unary_union
src=Path(sys.argv[1] if len(sys.argv)>1 else 'routing-work/revision/with-local-escapes.circuit.json');out=Path('routing-work/revision/power-bus');out.mkdir(parents=True,exist_ok=True);s={'__name__':'power_geometry'};sys.argv=['check-copper.py',str(src),'/tmp/unused-power-audit.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'power_geometry','exec'),s)
j=s['j'];net=next(k for k,v in s['nets'].items() if v=='VBUS');sp=s['sourceports'];sc=s['sources'];pp={}
for pid,p in s['ports'].items():
 v=sp.get(p.get('source_port_id'),{});pin=v.get('pin_number',next((int(h.removeprefix('pin')) for h in v.get('port_hints',[]) if h.removeprefix('pin').isdigit()),None));pp.setdefault((sc.get(v.get('source_component_id')),pin),(p['x'],p['y']))
board=s['bytype']['pcb_board'][0];outline=Polygon([(p['x'],p['y']) for p in board['outline']]);holes=unary_union([Point(h['x'],h['y']).buffer(h['hole_diameter']/2) for h in s['bytype']['pcb_hole']]+[Point(c['center']['x'],c['center']['y']).buffer(c['radius'],quad_segs=128) for c in s['bytype']['pcb_cutout'] if c['shape']=='circle']);hardware=[]
refs={e['pcb_component_id']:sc.get(e.get('source_component_id'),'') for e in s['bytype']['pcb_component']}
for h in s['bytype']['pcb_hole']:
 if refs.get(h.get('pcb_component_id'),'').startswith('H'):hardware.append(box(h['x']-4.75,h['y']-4.75,h['x']+4.75,h['y']+4.75).buffer(.2))
immutable=[a for a in s['items'] if a['layer']=='inner2' and a['net']!=net and (a['kind']=='pad' or a['id'].startswith(('seed_','kelvin_','plane_stitch_')))];obstacle=unary_union([a['g'] for a in immutable]);hardware=unary_union(hardware)
step=.1;axis=np.arange(1131)*step-56.5;w=h=len(axis);xx=axis[None,:];yy=axis[:,None];tree=Point(*pp[('F1',2)]).buffer(.1);traces=[];details=[]
goals=[('upper bridge',(0,22)),('lower bridge',(-9.4,-22))]+[(r,pp[(r,1)]) for r in ['C1','C2','C3','C4','C5','F2','C905']]
traceid=next(t['source_trace_id'] for t in j if t['type']=='source_trace' and net in t.get('connected_source_net_ids',[]));masks_by_width={}
while goals:
 index=min(range(len(goals)),key=lambda k:Point(*goals[k][1]).distance(tree));name,start=goals.pop(index);found=False
 for width in [3.,2.]:
  if width not in masks_by_width:
   allowed=outline.buffer(-.5-width/2-.003).difference(holes.buffer(.5+width/2+.003)).difference(hardware.buffer(width/2+.003)).difference(obstacle.buffer(.2+width/2+.003))
   masks_by_width[width]=(allowed,contains_xy(allowed,xx,yy))
  allowed,mask=masks_by_width[width];masks=np.zeros((4,h,w),dtype=np.uint8);masks[2]=mask;goalmask=np.zeros_like(masks);goalmask[2]=contains_xy(tree.buffer(.04),xx,yy)&mask;sx,sy=[round((v+56.5)/step) for v in start];gy,gx=np.where(goalmask[2])
  if not mask[sy,sx] or not len(gx):continue
  with (out/'masks.bin').open('wb') as f:f.write(struct.pack('<9i',w,h,sx,sy,2,int(gx.min()),int(gy.min()),int(gx.max()),int(gy.max())));f.write(masks.tobytes());f.write(np.zeros((h,w),dtype=np.uint8).tobytes());f.write(goalmask.tobytes())
  subprocess.run(['/tmp/octopus-routing/grid-astar',str(out/'masks.bin'),str(out/'path.json')],check=False);result=json.loads((out/'path.json').read_text())
  if not result['found']:continue
  raw=[(float(axis[x]),float(axis[y])) for x,y,l in result['path']];points=[start,*raw];smooth=[points[0]];idx=0;visible=allowed.buffer(1e-7)
  while idx<len(points)-1:
   nxt=idx+1
   for k in range(len(points)-1,idx,-1):
    if visible.covers(LineString([points[idx],points[k]])):nxt=k;break
   smooth.append(points[nxt]);idx=nxt
  if LineString(smooth).length<1e-6:
   details.append({'target':name,'alreadyOnBackbone':True});found=True;print(name,'already on backbone',flush=True);break
  g=LineString(smooth).buffer(width/2,quad_segs=32)
  assert all(g.distance(a['g'])>=.2-1e-5 for a in immutable)
  trace={'type':'pcb_trace','pcb_trace_id':'seed_'+str(20000+len(traces)),'source_trace_id':traceid,'connection_name':net,'route':[{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':width} for x,y in smooth]};traces.append(trace);tree=tree.union(g);details.append({'target':name,'widthMm':width,'lengthMm':LineString(smooth).length});found=True;print(name,width,round(LineString(smooth).length,2),'mm',flush=True);break
 if not found:raise RuntimeError('No >=2-mm VBUS path to '+name)
(out/'traces.json').write_text(json.dumps(traces,indent=2)+'\n');(out/'status.json').write_text(json.dumps({'status':'passed','paths':details},indent=2)+'\n');print('Saved',len(traces),'wide VBUS branches.')
