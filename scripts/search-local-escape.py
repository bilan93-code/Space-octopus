"""Find a mechanically legal signal escape while preserving fixed power/sense copper."""
import argparse,json,math,sys
from pathlib import Path
from shapely.geometry import Point,LineString,Polygon,box
from shapely.ops import unary_union
from shapely.strtree import STRtree

parser=argparse.ArgumentParser()
parser.add_argument('circuit');parser.add_argument('terminal')
parser.add_argument('--min-distance',type=float,default=1.5)
parser.add_argument('--max-distance',type=float,default=4.)
parser.add_argument('--max-rip-nets',type=int,default=999)
args=parser.parse_args();s={}
sys.argv=['check-copper.py',args.circuit,'/tmp/escape-search-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s)
p=next(p for k,p in s['ports'].items() if s['portlabel'](k)==args.terminal)
net=s['portnet'][p['pcb_port_id']];name=s['nets'][net];face=p['layers'][0]
assert len(p['layers'])==1 and name!='GND' and not name.startswith('SHUNT_')
outline=Polygon([(v['x'],v['y']) for v in s['bytype']['pcb_board'][0]['outline']]).buffer(-.5)
blocked=[Point(v['x'],v['y']).buffer(v['hole_diameter']/2+.5,quad_segs=128) for v in s['bytype']['pcb_hole']]
blocked.extend(Point(v['center']['x'],v['center']['y']).buffer(v['radius']+.5,quad_segs=128) for v in s['bytype']['pcb_cutout'] if v['shape']=='circle')
refs={v['pcb_component_id']:s['sources'].get(v.get('source_component_id'),'') for v in s['bytype']['pcb_component']}
blocked.extend(box(v['x']-4.75,v['y']-4.75,v['x']+4.75,v['y']+4.75).buffer(.2) for v in s['bytype']['pcb_hole'] if refs.get(v.get('pcb_component_id'),'').startswith('H'))
blocked=unary_union(blocked)
guard=[]
for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches']:
    guard.extend(b[k] for k in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia'])
protected={t['pcb_trace_id'] for t in s['bytype']['pcb_trace'] if t['pcb_trace_id'].startswith(('seed_','kelvin_','plane_stitch_')) or any(v.get('width',0)>=.6 for v in t['route'])}
for a in s['items']:
    if a['kind']=='via' and (a['g'].bounds[2]-a['g'].bounds[0]>=.59 or any(a['g'].centroid.distance(Point(*v))<1e-5 for v in guard)):protected.add(a['id'].rsplit(':',1)[0])
drills=[(v['x'],v['y'],v.get('via_hole_diameter',.2)/2) for t in s['bytype']['pcb_trace'] for v in t['route'] if v['route_type']=='via']
drills.extend((v['x'],v['y'],v.get('hole_diameter',max(v.get('hole_width',0),v.get('hole_height',0)))/2) for v in s['bytype']['pcb_via']+s['bytype']['pcb_plated_hole']+s['bytype']['pcb_hole'])
radius=args.max_distance;local=box(p['x']-radius-1,p['y']-radius-1,p['x']+radius+1,p['y']+radius+1)
foreign=[a for a in s['items'] if a['net']!=net and a['kind']!='pour' and a['g'].intersects(local)]
tree=STRtree([a['g'] for a in foreign])
limit=round(radius*10)
candidates=sorted((a*a+b*b,a/10,b/10) for a in range(-limit,limit+1) for b in range(-limit,limit+1) if (args.min_distance*10)**2<=a*a+b*b<=(radius*10)**2)
results=[]
for allow_rip in [False,True]:
    hard=[a for a in foreign if not allow_rip or a['kind']=='pad' or a['id'].rsplit(':',1)[0] in protected]
    hv=unary_union([a['g'].intersection(local) for a in hard]);hw=unary_union([a['g'].intersection(local) for a in hard if a['layer']==face])
    chosen=None
    for _,dx,dy in candidates:
        x,y=p['x']+dx,p['y']+dy
        if any(math.hypot(x-a,y-b)<r+.3-1e-5 for a,b,r in drills):continue
        via=Point(x,y).buffer(.2,quad_segs=32);wire=LineString([(p['x'],p['y']),(x,y)]).buffer(.075,quad_segs=32)
        if not outline.covers(via) or not outline.covers(wire) or blocked.intersection(via).area>1e-8 or blocked.intersection(wire).area>1e-8:continue
        if hv.distance(via)<.2-1e-5 or hw.distance(wire)<.2-1e-5:continue
        indices=set(map(int,tree.query(via,predicate='dwithin',distance=.2)))|set(map(int,tree.query(wire,predicate='dwithin',distance=.2)))
        bad=sorted({(a['id'].rsplit(':',1)[0],s['nets'].get(a['net'],a['net'])) for k in indices for a in [foreign[k]] if via.distance(a['g'])<.2-1e-5 or a['layer']==face and wire.distance(a['g'])<.2-1e-5})
        if len({n for identity,n in bad})>args.max_rip_nets:continue
        chosen={'point':[round(x,5),round(y,5)],'displaced':bad};break
    results.append({'ordinaryRipAllowed':allow_rip,'candidate':chosen})
print(json.dumps({'terminal':args.terminal,'net':name,'searches':results},indent=2))
