"""Reconnect revised load terminals with >=2 mm copper before signal routing."""
import json,sys,math,struct,subprocess,collections
from pathlib import Path
import numpy as np
from shapely import contains_xy
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union

work=Path('routing-work/motor-mount-revision/power');work.mkdir(parents=True,exist_ok=True)
path=Path(sys.argv[1]);j=json.loads(path.read_text())
reinforce='--reinforce-input' in sys.argv
reinforce_layer=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--input-layer=')),'top')
trace_ids=[a['pcb_trace_id'] for a in j if a['type']=='pcb_trace']
assert len(trace_ids)==len(set(trace_ids)), 'Duplicate trace IDs must be resolved before power routing.'
already={a.get('pcb_trace_id') for a in j}
requirements={
 'DC_IN':['J1.1','F1.1'],
 'VBUS':['F1.2','C1.1','C2.1','C3.1','C4.1','C5.1','Q1.2','Q3.2','Q5.2','F2.1','C905.1'],
 'PH_U':['Q1.3','Q2.2','J2.1'],'PH_V':['Q3.3','Q4.2','J2.2'],'PH_W':['Q5.3','Q6.2','J2.3'],
 'SHUNT_U_TOP':['Q2.3','RSH1.1'],'SHUNT_V_TOP':['Q4.3','RSH2.1'],'SHUNT_W_TOP':['Q6.3','RSH3.1'],
 'BRAKE_PLUS':['F2.2','J11.1','D2.1'],'BRAKE_DRAIN':['Q7.2','J11.2','D2.2'],
 'GND':['Q7.3','RSH1.2','RSH2.2','RSH3.2','C1.2','C2.2','C3.2','C4.2','C5.2','J1.2'],
}
if reinforce:requirements={'DC_IN':requirements['DC_IN']}
def load():
 path.write_text(json.dumps(j));s={'__name__':'power_geometry'};old=sys.argv;sys.argv=['check-copper.py',str(path),str(work/'unused.json')]
 exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'power_geometry','exec'),s);sys.argv=old
 s['outline']=Polygon([(p['x'],p['y']) for p in s['bytype']['pcb_board'][0]['outline']])
 refs={p['pcb_component_id']:s['sources'].get(p.get('source_component_id'),'') for p in s['bytype']['pcb_component']}
 s['hardware']=[box(h['x']-4.75,h['y']-4.75,h['x']+4.75,h['y']+4.75).buffer(.2) for h in s['bytype']['pcb_hole'] if refs.get(h.get('pcb_component_id'),'').startswith('H')]
 guard=collections.defaultdict(list)
 for a in s['items']:
  if a['id'].startswith('kelvin_'):guard[a['net']].append(a['g'])
 s['kelvin_via_ids']={a['id'].rsplit(':',1)[0] for a in s['items'] if a['kind']=='via' and a['net'] in guard and any(a['g'].intersects(g) for g in guard[a['net']])}
 s['protected_via_ids']=s['kelvin_via_ids']|{a['id'].rsplit(':',1)[0] for a in s['items'] if a['kind']=='via' and a['g'].bounds[2]-a['g'].bounds[0]>=.59}
 sense=collections.defaultdict(lambda:collections.defaultdict(list))
 for a in s['items']:
  if a['id'].startswith('kelvin_') or a['id'].rsplit(':',1)[0] in s['kelvin_via_ids']:
   sense[a['net']][a['layer']].append(a['g'])
 s['power_sense_guards']={}
 for n,bylayer in sense.items():
  s['power_sense_guards'][n]={}
  for layer,gs in bylayer.items():
   force=unary_union([a['g'] for a in s['items'] if a['kind']=='pad' and a['net']==n and a['layer']==layer and s['portlabel'](a.get('port')).startswith('RSH')])
   s['power_sense_guards'][n][layer]=unary_union(gs).difference(force)
 return s
s=load();netids={v:k for k,v in s['nets'].items()};traceby={n:t['source_trace_id'] for t in s['bytype']['source_trace'] for n in t.get('connected_source_net_ids',[])}
ports={s['portlabel'](pid):p for pid,p in s['ports'].items()}
# Parallel plated barrels connect the relocated local bus bypass to the planes.
for label in ['C905.1','C905.2']:
 p=ports[label];n=s['portnet'][p['pcb_port_id']]
 for dy in [-.4,.4]:
  if f'seed_mount_bypass_{label}_{dy}' in already:continue
  x,y=p['x'],p['y']+dy
  g=Point(x,y).buffer(.3,quad_segs=32)
  if any(a['net']!=n and g.distance(a['g'])<.2-1e-5 and (a['kind']=='pad' or a['id'].startswith('kelvin_')) for a in s['items']):continue
  j.append({'type':'pcb_trace','pcb_trace_id':f'seed_mount_bypass_{label}_{dy}','connection_name':n,'source_trace_id':traceby[n],'route':[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.2},{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'inner2','layers':s['layers'],'via_diameter':.6,'via_hole_diameter':.3},{'route_type':'wire','x':x,'y':y,'layer':'inner2','width':.2}]})
s=load();step=.1;axis=np.arange(1131)*step-56.5;w=h=len(axis);xx=axis[None,:];yy=axis[:,None]
def components(net,required):
 wideids={f"{t['pcb_trace_id']}:{k}" for t in s['bytype']['pcb_trace'] for k,v in enumerate(t['route']) if k and v['route_type']=='wire' and v.get('width',0)>=2}
 own=[a for a in s['items'] if a['net']==net and (a['kind']!='track' or a['id'] in wideids) and a['kind']!='pour' and not(reinforce and a['kind']=='track' and a['layer']!=reinforce_layer)]
 nodes=[];ls=[]
 for l in s['layers']:
  u=unary_union([a['g'] for a in own if a['layer']==l]).buffer(1e-7)
  ps=list(u.geoms) if u.geom_type=='MultiPolygon' else [u] if not u.is_empty else []
  nodes+=ps;ls +=[l]*len(ps)
 parent=list(range(len(nodes)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(ids):
  for i in ids[1:]:parent[root(i)]=root(ids[0])
 for n,layers,g in s['barrels']:
  if n==net:join([i for i,p in enumerate(nodes) if ls[i] in layers and p.intersects(g)])
 # Repeated drain/tab contacts are a declared internal device connection.
 for c in s['bytype']['source_component']:
  for ids in c.get('internally_connected_source_port_ids',[]):
   pp=[p for p in s['ports'].values() if p.get('source_port_id') in ids and s['portnet'].get(p['pcb_port_id'])==net]
   join([i for i,g in enumerate(nodes) if any(ls[i] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5 for p in pp)])
 groups=collections.defaultdict(lambda:{'layers':collections.defaultdict(list),'terminals':[]})
 for i,g in enumerate(nodes):groups[root(i)]['layers'][ls[i]].append(g)
 for label in required:
  p=ports[label];ids=[i for i,g in enumerate(nodes) if ls[i] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5]
  if not ids:raise RuntimeError('Missing terminal copper '+label)
  groups[root(ids[0])]['terminals'].append(label)
 return [{**v,'layers':{l:unary_union(gs) for l,gs in v['layers'].items()}} for v in groups.values() if v['terminals']]

details=[]
for name,required in requirements.items():
 net=netids[name]
 for iteration in range(30):
  groups=components(net,required)
  if len(groups)==1:print(name,'connected',flush=True);break
  groups.sort(key=lambda g:sum(v.area for v in g['layers'].values()),reverse=True)
  candidates=[]
  for ia,a in enumerate(groups):
   for b in groups[ia+1:]:
    for layer in ([reinforce_layer] if reinforce else ['inner2','top','bottom'] if name=='VBUS' else ['inner1','top','bottom'] if name=='GND' else ['bottom','top']):
     if layer in a['layers'] and layer in b['layers']:
      candidates.append((a['layers'][layer].distance(b['layers'][layer]),a,b,layer))
  found=False
  for width in ([4.5,4.,3.5,3.,2.4,2.] if reinforce else [3.,2.4,2.]):
   for _,a,b,layer in sorted(candidates,key=lambda c:c[0]):
    wide_traces={t['pcb_trace_id'] for t in s['bytype']['pcb_trace'] if any(p.get('width',0)>=2 for p in t['route'])}
    foreign=[v for v in s['items'] if v['net']!=net and v['layer']==layer and (v['kind']=='pad' or v['id'].startswith(('seed_','kelvin_','plane_stitch_')) or v['id'].rsplit(':',1)[0] in wide_traces or v['id'].rsplit(':',1)[0] in s['protected_via_ids'])]
    allowed=s['outline'].buffer(-.503-width/2)
    holes=unary_union([Point(v['x'],v['y']).buffer(v['hole_diameter']/2,quad_segs=64) for v in s['bytype']['pcb_hole']]+[Point(v['center']['x'],v['center']['y']).buffer(v['radius'],quad_segs=128) for v in s['bytype']['pcb_cutout'] if v['shape']=='circle'])
    allowed=allowed.difference(holes.buffer(.503+width/2)).difference(unary_union(s['hardware']).buffer(width/2+.003)).difference(unary_union([v['g'] for v in foreign]).buffer(.203+width/2))
    allowed=allowed.difference(s['power_sense_guards'].get(net,{}).get(layer,Polygon()).buffer(.203+width/2))
    mask=contains_xy(allowed,xx,yy)
    # A centreline can terminate inside existing wide copper or a load pad.
    aa=a['layers'][layer].buffer(-width/2+.08);bb=b['layers'][layer].buffer(-width/2+.08)
    if aa.is_empty:aa=a['layers'][layer].buffer(-.05)
    if bb.is_empty:bb=b['layers'][layer].buffer(-.05)
    starts=contains_xy(aa,xx,yy)&mask;goals=contains_xy(bb,xx,yy)&mask
    sy,sx=np.where(starts);gy,gx=np.where(goals)
    if not len(sx) or not len(gx):
     print('Blocked',name,layer,width,a['terminals'],b['terminals'],'start/goal',len(sx),len(gx),flush=True);continue
    index=np.argmin((axis[sx]-bb.centroid.x)**2+(axis[sy]-bb.centroid.y)**2);sx,sy=int(sx[index]),int(sy[index])
    masks=np.zeros((4,h,w),dtype=np.uint8);goalmasks=np.zeros_like(masks);li=s['layers'].index(layer);masks[li]=mask;goalmasks[li]=goals
    soft=np.zeros_like(masks)
    if name=='GND':
     # Prefer a clear channel before displacing already completed logic routes.
     existing=unary_union([a['g'] for a in s['items'] if a['net']!=net and a['layer']==layer and a['kind']!='pour'])
     soft[li]=contains_xy(existing.buffer(.203+width/2),xx,yy)
    with (work/'masks.bin').open('wb') as f:
     f.write(struct.pack('<9i',w,h,sx,sy,li,int(gx.min()),int(gy.min()),int(gx.max()),int(gy.max())));f.write(masks.tobytes());f.write(np.zeros((h,w),dtype=np.uint8).tobytes());f.write(goalmasks.tobytes())
     if name=='GND':f.write(soft.tobytes());f.write(np.zeros((h,w),dtype=np.uint8).tobytes())
    subprocess.run(['/tmp/octopus-routing/grid-astar',str(work/'masks.bin'),str(work/'path.json')],stdout=subprocess.DEVNULL,check=False)
    result=json.loads((work/'path.json').read_text())
    if not result['found']:
     print('No corridor',name,layer,width,a['terminals'],b['terminals'],flush=True);continue
    raw=[(float(axis[x]),float(axis[y])) for x,y,l in result['path']];smooth=[raw[0]];idx=0
    while idx<len(raw)-1:
     nxt=idx+1
     for k in range(len(raw)-1,idx,-1):
      if allowed.buffer(1e-7).covers(LineString([raw[idx],raw[k]])):nxt=k;break
     smooth.append(raw[nxt]);idx=nxt
    g=LineString(smooth).buffer(width/2,quad_segs=32)
    bad={v['id'].rsplit(':',1)[0] for v in s['items'] if v['net']!=net and v['layer']==layer and g.distance(v['g'])<.2-1e-5}
    if any(v.startswith('kelvin_') or v in s['protected_via_ids'] for v in bad):raise RuntimeError('Protected pickup hit')
    j=[v for v in j if v.get('pcb_trace_id') not in bad]
    numbers=[int(a['pcb_trace_id'].removeprefix('seed_mount_power_')) for a in j if a['type']=='pcb_trace' and a.get('pcb_trace_id','').startswith('seed_mount_power_') and a['pcb_trace_id'].removeprefix('seed_mount_power_').isdigit()]
    identity='seed_mount_power_'+str(max(numbers,default=-1)+1);j.append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'source_trace_id':traceby[net],'route':[{'route_type':'wire','x':x,'y':y,'layer':layer,'width':width} for x,y in smooth]})
    details.append({'net':name,'widthMm':width,'layer':layer,'lengthMm':LineString(smooth).length,'ripped':len(bad)})
    print(name,width,layer,round(LineString(smooth).length,2),'mm; displaced',len(bad),'signal routes',flush=True)
    s=load();found=True;break
   if found:break
  if not found:raise RuntimeError('No wide path for '+name+' '+str([g['terminals'] for g in groups]))
 else:raise RuntimeError('Power routing did not converge '+name)
(work/'status.json').write_text(json.dumps(details,indent=2)+'\n');path.write_text(json.dumps(j));print('Added',len(details),'power connections.')
