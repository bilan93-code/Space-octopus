"""Connection-aware assembly-face placement; motor interface never moves.
Through-hole bodies and opposite-face solder projections are distinct envelopes.
"""
import argparse,json,math,re
from pathlib import Path
from functools import lru_cache
from shapely.prepared import prep
from shapely.strtree import STRtree
from shapely.geometry import Point,box,mapping,LineString
from shapely.affinity import rotate,scale,translate
from shapely.ops import unary_union
ap=argparse.ArgumentParser();ap.add_argument('--dry-run',action='store_true');ap.add_argument('--repair',action='store_true');args=ap.parse_args()
previous=json.loads(Path('data/placement.json').read_text()) if args.repair else {}
g=json.loads(Path('data/board-geometry.json').read_text())
parts=sum([json.loads(Path('data/'+n+'.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']],[])
cat=json.loads(Path('footprints/catalog.json').read_text());by={p['ref']:p for p in parts}
gap=g['courtyardGapMm'];radius=g['outerDiameterMm']/2
usable=Point(0,0).buffer(radius-g['edgeMarginMm'],quad_segs=256).difference(Point(0,0).buffer(g['centralOpeningDiameterMm']/2+g['edgeMarginMm'],quad_segs=128))
usable_test=prep(usable.buffer(1e-6))
placed={};occupied={'top':[],'bottom':[]};reservations={'top':[],'bottom':[]}
spatial={};spatial_counts={}
bottom={'U1','U2','J1','J2','J11','Q2','Q4','Q6','RSH1','RSH2','RSH3','C5'}
def default_layer(p):
 if p['ref'] in bottom:return 'bottom'
 if p['ref'].startswith('Q') or p['ref'] in ['F1','F2','C1','C2','C3','C4','C5']:return 'top'
 return 'bottom' if p['sheet'] in ['02_MCU','03_GateDriver','05_Sensing','06_FaultLogic','07_Interfaces'] else 'top'
@lru_cache(maxsize=None)
def local_shapes(ref,layer,rot):
 p=by[ref];c=cat[p['footprint']];b=c['box'];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2;body=box(*b)
 if p['ref'] in ['C1','C2','C3','C4']:body=Point(3.75,0).buffer(9.25,quad_segs=64);cx=3.75;cy=0
 if p['kind']=='hole':
  r=g['mounting']['keepoutDiameterMm']/2;body=box(-r,-r,r,r);cx=cy=0
 body=translate(body,-cx,-cy);leads=[]
 for e in c['elements']:
  if e['type'] not in ['pcb_plated_hole','pcb_hole']:continue
  r=e['hole_diameter']/2 if e['type']=='pcb_hole' else max(e.get('hole_diameter',0),e.get('hole_width',0),e.get('hole_height',0))/2+.4
  if e['type']=='pcb_plated_hole':
   w=e.get('outer_diameter',e.get('rect_pad_width',e.get('outer_width',2*r)));h=e.get('outer_diameter',e.get('rect_pad_height',e.get('outer_height',2*r)))
   if e['shape']=='pill':
    rr=min(w,h)/2;lead=LineString([(-max(0,w/2-rr),-max(0,h/2-rr)),(max(0,w/2-rr),max(0,h/2-rr))]).buffer(rr,quad_segs=24)
   elif e['shape']=='circle':lead=Point(0,0).buffer(w/2,quad_segs=24)
   else:lead=box(-w/2,-h/2,w/2,h/2)
   lead=rotate(lead,e.get('ccw_rotation',0),origin=(0,0)).buffer(.2)
   leads.append(translate(lead,e['x']-cx,e['y']-cy))
  else:leads.append(Point(e['x']-cx,e['y']-cy).buffer(r,quad_segs=24))
 result={layer:body}
 if leads:result['bottom' if layer=='top' else 'top']=unary_union(leads)
 if p['kind']=='hole':result={'top':body,'bottom':body}
 def tf(s):return rotate(scale(s,xfact=-1 if layer=='bottom' else 1,yfact=1,origin=(0,0)),rot,origin=(0,0))
 return {l:tf(s) for l,s in result.items()}
def try_put(ref,x,y,rot=0,layer=None,fixed=False):
 p=by[ref];layer=layer or default_layer(p);world={l:translate(s,x,y) for l,s in local_shapes(ref,layer,rot).items()}
 if p['kind']!='hole' and any(not usable_test.covers(s) for s in world.values()):return False
 for l,s in world.items():
  count=len(occupied[l])+len(reservations[l])
  if spatial_counts.get(l)!=count:spatial[l]=STRtree(occupied[l]+reservations[l]);spatial_counts[l]=count
  if len(spatial[l].query(s,predicate='dwithin',distance=gap-1e-6)):return False
 b=cat[p['footprint']]['box'];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
 if ref in ['C1','C2','C3','C4']:cx=3.75;cy=0
 t=math.radians(rot);cx*=(-1 if layer=='bottom' else 1)
 ox=x-(cx*math.cos(t)-cy*math.sin(t));oy=y-(cx*math.sin(t)+cy*math.cos(t))
 placed[ref]={'x':round(ox,5),'y':round(oy,5),'rotation':rot,'bodyCenter':[x,y],'courtyard':list(world[layer].bounds),'fixed':fixed,'layer':layer,'occupiesLayers':list(world),'assemblyEnvelopes':{l:mapping(s) for l,s in world.items()}}
 for l,s in world.items():occupied[l].append(s)
 return True
fixed={}
for i,a in enumerate(g['mounting']['anglesDegrees'],1):
 t=math.radians(a);r=g['mounting']['boltCircleDiameterMm']/2;fixed['H'+str(i)]=(r*math.cos(t),r*math.sin(t),0)
fixed.update({'F1':(0,39,0),'F2':(0,-39,0),'C1':(-36,10.5,90),'C2':(-36,-10.5,90),'C3':(36,10.5,90),'C4':(36,-10.5,90),'U1':(22,0,0),'U2':(-20,0,0),'J1':(-47.5,0,90),'J2':(48.3,0,90),'J11':(30,-34,0),'Q1':(-9,22,0),'Q2':(-9,22,180),'Q3':(9,22,180),'Q4':(9,22,0),'Q5':(0,-22,180),'Q6':(0,-22,0),'Q7':(-19,-23,0),'RSH1':(-22,24.54,0),'RSH2':(22,19.46,180),'RSH3':(13,-24.54,180),'C5':(-24,-20,90),'D2':(11,-50,0)})
# Local bypass and converter placement takes precedence over blind area packing.
# The four MCU VDD capacitors sit on the opposite face beside the corresponding
# VDD/VSS fanout pair; converter inductors and bootstrap parts share a cell.
functional={
 'U3':(31.6,37.1,180,'top'),'L101':(31.6,27,270,'top'),
 'C101':(37.3,36.3,90,'top'),'C102':(27,41.85,0,'top'),
 'C103':(29.9375,22.75,0,'bottom'),'C104':(34.3,21,90,'bottom'),
 'C105':(26.6,35.83,270,'top'),'C106':(25.9,38.5,0,'top'),
 'R101':(33.1,41.5,0,'top'),'R102':(23.25,38,90,'top'),'R103':(23.5,41.5,90,'top'),
 'R104':(30.45,42.5,90,'top'),'C107':(24,34.5,90,'top'),
 'U4':(22,11.5,180,'bottom'),'L102':(30.4,11.4,180,'bottom'),
 'C108':(15.2,11.7,0,'bottom'),'C109':(37,10.5,180,'bottom'),
 'R105':(22,15.5,0,'bottom'),'R106':(18,14.8,0,'bottom'),
 'U5':(20.3,1.7,180,'top'),'C110':(24.5,3,0,'top'),'C111':(21,-1.55,0,'top'),
 'U19':(24,-9,0,'top'),'C112':(26,-9,0,'bottom'),'C113':(20.9,-9.8,270,'top'),
 'C201':(26.9,-3.75,0,'top'),'C202':(18.25,-5.675,270,'top'),
 'C203':(16.325,3.75,180,'top'),'C204':(25.75,5.675,90,'top'),
 'C205':(22,-9,0,'bottom'),'C206':(18,-10,0,'top'),
 'C301':(-21,10.4,0,'bottom'),'C302':(-17.2,1.25,180,'top'),'C303':(-16.5,6.2,0,'top'),'C304':(-17.3,-7.5,0,'bottom'),'C305':(-23,7.2,0,'bottom'),'C306':(-19,7,0,'bottom'),'C307':(-26,-1.5,270,'top'),'U6':(37.4,0,0,'bottom'),'C705':(42.3,-.635,90,'bottom'),'C706':(31.8,-1.85,0,'bottom'),'C707':(39,-3.9,0,'bottom'),'C905':(-30.1,-29,0,'top'),'C512':(-18,-9.8,180,'top'),'C407':(-25.8,-5.25,90,'top'),'C605':(18,-16,180,'bottom'),'C501':(24.6,-1.75,180,'top'),'C502':(24.25,.6,180,'top'),'C503':(23,-4.45,270,'top'),'C504':(31,1.9,180,'bottom'),'C511':(31.2,.02,180,'bottom'),'C207':(20.5,-5.675,280.7,'top'),'FB201':(18,-12,0,'top'),
}
# Drop former noncritical anchors for the functional cells before packing.
for ref,v in functional.items():fixed.pop(ref,None)
for ref,v in fixed.items():
 if not try_put(ref,*v,fixed=True):raise RuntimeError('Critical anchor does not fit: '+ref)
for ref,(x,y,rot,face) in functional.items():
 if not try_put(ref,x,y,rot,face,fixed=True):raise RuntimeError('Functional anchor does not fit: '+ref)
reservations['bottom']=[box(13.5,-8.2,30.5,8.2),box(-26,-5.8,-14,5.8)]
reservations['top']=reservations['bottom'].copy()
# Keep later small-part placements out of the planned high-current corridors.
for face,pts,w in [('top',[(-44,0),(-30.5,0),(-30.5,39),(-18.75,39)],6.5),('bottom',[(-44,0),(-30.5,0),(-30.5,39),(-18.75,39)],6.5),('bottom',[(-6,28),(-6,34),(32,34),(32,10.7),(46.99,10.16)],4),('top',[(20,26),(23,26),(23,10.7),(46.99,10.7),(46.99,0)],4),('bottom',[(10.5,-20),(13,-18.2),(47,-18.2),(47,-10.16)],4),('bottom',[(-22,-29),(-22,-34),(35.075,-34)],4)]:
 reservations[face].append(LineString(pts).buffer(w/2+.4))
# Revisions can preserve the exact power copper while moving conflicting
# small parts. All pre-routed power vias reserve both assembly faces.
if args.repair:
 reservations['top']=reservations['top'][:2];reservations['bottom']=reservations['bottom'][:2]
power_seed=Path('routing-work/revision/seed.circuit.json')
if args.repair and power_seed.exists():
 for tr in json.loads(power_seed.read_text()):
  if tr.get('type')!='pcb_trace' or not tr.get('pcb_trace_id','').startswith('seed_') or int(tr['pcb_trace_id'].split('_')[1])<191:continue
  for k,v in enumerate(tr['route']):
   if v['route_type']=='via':
    sg=Point(v['x'],v['y']).buffer(v.get('via_diameter',.8)/2+.2)
    for face in ['top','bottom']:reservations[face].append(sg)
   elif k and tr['route'][k-1]['route_type']=='wire':
    u=tr['route'][k-1];sg=LineString([(u['x'],u['y']),(v['x'],v['y'])]).buffer(v['width']/2+.2)
    reservations[v['layer']].append(sg)
anchors={'00_Input':(-29,28),'01_Supplies':(-28,-7),'02_MCU':(24,10),'03_GateDriver':(-22,7),'04_Inverter':(-12,22),'05_Sensing':(-20,12),'06_FaultLogic':(12,33),'07_Interfaces':(25,-22),'08_Brake':(-21,-26),'Mechanical':(0,45)}
prefer={'C5':(0,44),'U10':(0,33),'U7':(-25,12),'U8':(-25,18),'U3':(-25,-12),'U4':(-27,-4),'U5':(-20,-8),'L101':(-25,-4),'L102':(-27,4),'U17':(-25,-25),'U16':(-20,-31),'U18':(27,-23),'U20':(27,-16),'U6':(30,25),'J4':(36,-25),'J5':(38,26),'J6':(29,36),'J10':(27,-43),'J7':(18,44),'J9':(33,39),'J3':(-36,27),'J8':(-31,-29)}
for i in range(1,7):
 q=placed['Q'+str(i)];cx,cy=q['bodyCenter'];layer=q['layer'];rot=q['rotation'];p=by['Q'+str(i)];e=next(e for e in cat[p['footprint']]['elements'] if e.get('port_hints',[''])[0]=='1')
 t=math.radians(rot);xx=(e['x']+1.875)*(-1 if layer=='bottom' else 1);yy=e['y'];gx=cx+xx*math.cos(t)-yy*math.sin(t);gy=cy+xx*math.sin(t)+yy*math.cos(t)
 for ref,dy in [('R'+str(400+i),1.3),('R'+str(406+i),-1.3)]:prefer[ref]=(gx,gy+dy)
bypass_parent={}
for part in parts:
 if part['kind']!='capacitor' or 'bypass' not in part.get('notes','').lower():continue
 m=re.search(r'(?:at|nearest) (U\d+)',part['notes'])
 if m:bypass_parent[part['ref']]=m[1]
def pad_position(ref,pin):
 p=by[ref];v=placed[ref];e=next(e for e in cat[p['footprint']]['elements'] if e.get('port_hints',[None])[0]==str(pin))
 t=math.radians(v['rotation']);x=e['x']*(-1 if v['layer']=='bottom' else 1);y=e['y']
 return (v['x']+x*math.cos(t)-y*math.sin(t),v['y']+x*math.sin(t)+y*math.cos(t))
def bypass_target(part):
 parent=bypass_parent.get(part['ref'])
 if parent not in placed:return None
 rail=part['pins']['1'];pins=[pin for pin,net in by[parent]['pins'].items() if net==rail]
 supply=[pin for pin in pins if re.search(r'VCC|VDD|VIO|V12|VIN|V\+',by[parent]['pinLabels'].get(pin,''))]
 if supply:pins=supply
 if not pins:return None
 return pad_position(parent,pins[0])
rails={'GND','VBUS','V12','V5','V3V3','VDDA3V3','FAULT_RAW_N'}
def area(p):b=cat[p['footprint']]['box'];return (b[2]-b[0])*(b[3]-b[1])
def target(p):
 bt=bypass_target(p)
 if bt:return bt
 if p['ref'] in prefer:return prefer[p['ref']]
 own=set(p['pins'].values())-rails-{None};scores=[]
 for ref,v in placed.items():
  shared=own.intersection(by[ref]['pins'].values())
  if shared:scores.append((len(shared)*(3 if by[ref]['kind']=='chip' else 1),v['bodyCenter']))
 if scores:
  total=sum(w for w,_ in scores);return tuple(sum(w*v[i] for w,v in scores)/total for i in [0,1])
 return anchors[p['sheet']]
def priority(p):
 r=p['ref'];return (0 if r=='C5' else 1 if p['kind']=='connector' else 2 if r in prefer else 3 if p['kind'] in ['chip','inductor'] else 4 if r in bypass_parent else 5,-area(p),r)
for p in sorted(parts,key=priority):
 ref=p['ref']
 if ref in placed:continue
 if ref in previous:
  old=previous[ref]
  bt=bypass_target(p)
  if (not bt or math.dist(old['bodyCenter'],bt)<3.5) and try_put(ref,*old['bodyCenter'],old['rotation'],old['layer']):continue
 tx,ty=target(p);layer=placed[bypass_parent[ref]]['layer'] if ref in bypass_parent and bypass_parent[ref] in placed else default_layer(p)
 if ref.startswith('R4') and 401<=int(ref[1:])<=412:layer=placed['Q'+str((int(ref[1:])-401)%6+1)]['layer']
 candidates=sorted(((x-tx)**2+(y-ty)**2,x,y) for x in range(-53,54) for y in range(-53,54));found=False
 for face in [layer,'bottom' if layer=='top' else 'top']:
  for _,x,y in candidates:
   for rot in [0,90,180,270]:
    if try_put(ref,x,y,rot,face):found=True;break
   if found:break
  if found:break
 if not found:raise RuntimeError('No legal assembly position for '+ref)
 print(ref,placed[ref]['bodyCenter'],placed[ref]['layer'],flush=True)
if not args.dry_run:Path('data/placement.json').write_text(json.dumps(placed,indent=2)+'\n')
print('Placed',len(placed),'parts with assembly-face bodies, opposite-face lead envelopes, and reserved MCU/driver fanouts.')
