"""Find clear local positions for trapped filter parts and a probe pad.
Only writes reviewable proposals; canonical placement is not changed.
"""
import json,sys,math
from pathlib import Path
from shapely.geometry import Point,shape,Polygon,box
from shapely.affinity import translate,rotate
from shapely.strtree import STRtree

src=Path(sys.argv[1]);out=Path(sys.argv[2]);s={};sys.argv=['x',str(src)]
code=Path('scripts/check-copper.py').read_text();exec(compile(code.split('# Distinct-net copper')[0],'g','exec'),s)
exec(compile('connectivity=[];netGraphs={}'+code.split('connectivity=[];netGraphs={}')[1].split('unconnected=[n for n in connectivity')[0],'c','exec'),s)
placement=json.loads(Path('data/placement.json').read_text());refs={a['pcb_component_id']:s['sources'].get(a.get('source_component_id')) for a in s['bytype']['pcb_component']}
outline=Polygon([(v['x'],v['y']) for v in s['bytype']['pcb_board'][0]['outline']]).buffer(-1)
usable=outline.difference(Point(0,0).buffer(15,quad_segs=128));envelopes={l:[] for l in ['top','bottom']};owners={l:[] for l in envelopes}
for ref,p in placement.items():
 for l,g in p['assemblyEnvelopes'].items():envelopes[l].append(shape(g));owners[l].append(ref)
et={l:STRtree(gs) for l,gs in envelopes.items()};copper=[a for a in s['items'] if a['kind']!='pour'];ct=STRtree([a['g'] for a in copper]);proposals=[]
targets={'R517':('C509',2),'R518':('C510',2),'R505':('C504',2),'R506':('C504',1),'TP8':('U2',1)}
extra_envelopes=[];extra_pads=[]
for ref,(target,pin) in targets.items():
 p=placement[ref];ox,oy=p['bodyCenter'];tx,ty=placement[target]['bodyCenter'];ownpads=[a for a in s['items'] if a['kind']=='pad' and refs.get(s['ports'].get(a.get('port'),{}).get('pcb_component_id'))==ref]
 assert ownpads,ref
 candidates=[]
 if ref=='TP8':
  net=ownpads[0]['net']
  graph=s['netGraphs'][net];root=max(graph['terminals'],key=lambda k:len(graph['terminals'][k]));main=[g for g,l,r in zip(graph['nodes'],graph['layers'],graph['roots']) if r==root and l==p['layer']]
  for t in s['bytype']['pcb_trace']:
   if (t.get('connection_name') or s['trace_net'].get(t.get('source_trace_id')))!=net:continue
   for u,v in zip(t['route'],t['route'][1:]):
    if u['route_type']!=v['route_type'] or u['route_type']!='wire' or u['layer']!=p['layer']:continue
    length=math.dist((u['x'],u['y']),(v['x'],v['y']))
    for i in range(max(1,math.ceil(length/.4))+1):
     f=i/max(1,math.ceil(length/.4));x=u['x']+f*(v['x']-u['x']);y=u['y']+f*(v['y']-u['y'])
     if math.hypot(x-ox,y-oy)>2 and any(g.distance(Point(x,y))<1e-5 for g in main):candidates.append((math.hypot(x-tx,y-ty),x,y,0))
 else:
  extent=80 if ref in ['R505','R506'] else 36
  for ix in range(-extent,extent+1):
   for iy in range(-extent,extent+1):
    x=tx+ix/4;y=ty+iy/4
    for turn in [0,90,180,270]:candidates.append((math.hypot(x-tx,y-ty)+(.01 if turn else 0),x,y,turn))
 found=None
 for score,x,y,turn in sorted(set(candidates)):
  world={l:translate(rotate(shape(g),turn,origin=(ox,oy)),x-ox,y-oy) for l,g in p['assemblyEnvelopes'].items()}
  if any(not usable.covers(g) for g in world.values()):continue
  if any(owners[l][int(k)]!=ref for l,g in world.items() for k in et[l].query(g,predicate='dwithin',distance=.4-1e-5)):continue
  if any(l in world and g.distance(world[l])<.4-1e-5 for l,g in extra_envelopes):continue
  pads=[{**a,'g':translate(rotate(a['g'],turn,origin=(ox,oy)),x-ox,y-oy)} for a in ownpads]
  bad=False
  for a in pads:
   for k in ct.query(a['g'],predicate='dwithin',distance=.2):
    b=copper[int(k)]
    if a['layer']==b['layer'] and a['net']!=b['net'] and a['g'].distance(b['g'])<.2-1e-5:bad=True;break
   if bad:break
   if any(a['layer']==b['layer'] and a['net']!=b['net'] and a['g'].distance(b['g'])<.2-1e-5 for b in extra_pads):bad=True;break
  if bad:continue
  found={'ref':ref,'oldCenter':[ox,oy],'center':[x,y],'rotation':(p['rotation']+turn)%360,'target':target,'distanceToTargetMm':math.hypot(x-tx,y-ty),'newEnvelopes':{l:g.__geo_interface__ for l,g in world.items()},'pads':[(s['portlabel'](a['port']),a['g'].centroid.x,a['g'].centroid.y) for a in pads]};extra_envelopes +=list(world.items());extra_pads+=pads;break
 proposals.append(found or {'ref':ref,'failed':True});print(json.dumps(proposals[-1]),flush=True)
out.write_text(json.dumps({'source':str(src),'proposals':proposals},indent=2)+'\n')
