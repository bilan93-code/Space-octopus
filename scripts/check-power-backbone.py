"""Power terminals must connect without relying on narrow signal traces."""
import hashlib,json,sys,collections
from pathlib import Path
from shapely.geometry import Point
from shapely.ops import unary_union
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');out=Path(sys.argv[2] if len(sys.argv)>2 else 'output/power-backbone-audit.json');s={'__name__':'power_geometry'};sys.argv=['check-copper.py',str(src),'/tmp/unused-power-audit.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'power_geometry','exec'),s)
minimum = 2.0
segment_width = {
    f"{trace['pcb_trace_id']}:{i}": point.get('width', trace['route'][i - 1].get('width', .25))
    for trace in s['bytype']['pcb_trace'] for i, point in enumerate(trace['route'])
    if i and point['route_type'] == 'wire'
}
wide = {identity for identity, width in segment_width.items() if width >= minimum}
requirements={
 'DC_IN':['J1.1','F1.1'],
 'VBUS':['F1.2','C1.1','C2.1','C3.1','C4.1','C5.1','Q1.2','Q3.2','Q5.2','F2.1','C905.1'],
 'GND':['J1.2','C1.2','C2.2','C3.2','C4.2','C5.2','RSH1.2','RSH2.2','RSH3.2','Q7.3'],
 'PH_U':['Q1.3','Q2.2','J2.1'],'PH_V':['Q3.3','Q4.2','J2.2'],'PH_W':['Q5.3','Q6.2','J2.3'],
 'SHUNT_U_TOP':['Q2.3','RSH1.1'],'SHUNT_V_TOP':['Q4.3','RSH2.1'],'SHUNT_W_TOP':['Q6.3','RSH3.1'],
 'BRAKE_PLUS':['F2.2','J11.1','D2.1'],'BRAKE_DRAIN':['Q7.2','J11.2','D2.2'],
}
ids={v:k for k,v in s['nets'].items()};results=[]
for name,required in requirements.items():
 net=ids[name];own=[a for a in s['items'] if a['net']==net and (a['kind']!='track' or a['id'] in wide) and (name not in ['VBUS','GND'] or a['kind']!='pour')];nodes=[];ls=[]
 for l in s['layers']:
  u=unary_union([a['g'] for a in own if a['layer']==l]).buffer(1e-7)
  pp=list(u.geoms) if u.geom_type=='MultiPolygon' else ([u] if not u.is_empty else [])
  nodes.extend(pp);ls.extend([l]*len(pp))
 parents=list(range(len(nodes)))
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def join(indices):
  for k in indices[1:]:parents[root(k)]=root(indices[0])
 for n,layers,g in s['barrels']:
  if n==net:join([k for k,g2 in enumerate(nodes) if ls[k] in layers and g2.intersects(g)])
 for c in s['bytype']['source_component']:
  for source_ids in c.get('internally_connected_source_port_ids',[]):
   pp=[p for p in s['ports'].values() if p.get('source_port_id') in source_ids and s['portnet'].get(p['pcb_port_id'])==net]
   join([i for i,g in enumerate(nodes) if any(ls[i] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5 for p in pp)])
 terminals=collections.defaultdict(set)
 for pid,p in s['ports'].items():
  label=s['portlabel'](pid)
  if label not in required:continue
  found=[k for k,g in enumerate(nodes) if ls[k] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5]
  if found:terminals[root(found[0])].add(label)
 present=set().union(*terminals.values()) if terminals else set();passed=any(set(required)<=v for v in terminals.values())
 results.append({'net':name,'passed':passed,'required':required,'missing':sorted(set(required)-present),'islands':[sorted(v) for v in terminals.values()]})
parallel=[]
dc=ids['DC_IN'];ends=[Point(p['x'],p['y']) for pid,p in s['ports'].items() if s['portlabel'](pid) in ['J1.1','F1.1']]
assert len(ends)==2
for layer,width in [('inner2',4.5),('bottom',2.4)]:
 selected={f"{t['pcb_trace_id']}:{k}" for t in s['bytype']['pcb_trace'] for k,v in enumerate(t['route']) if k and v['route_type']=='wire' and v.get('width',0)>=width-1e-6}
 g=unary_union([a['g'] for a in s['items'] if a['net']==dc and a['layer']==layer and (a['kind'] in ['pad','via'] or a['kind']=='track' and a['id'] in selected)]).buffer(1e-7)
 islands=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
 parallel.append({'layer':layer,'minimumTrackWidthMm':width,'passed':any(all(p.distance(end)<1e-5 for end in ends) for p in islands)})
# Direct-solder power wires have larger bores than the former terminal pins.
# Prove a load-width conductor lands on the remaining copper outside each bore.
wire_layers = {
    'J1.1': {'inner2': 4.5, 'bottom': 2.4},
    'J1.2': {'inner1': 2.0, 'bottom': 2.0},
    'J2.1': {'top': 2.0}, 'J2.2': {'top': 2.0}, 'J2.3': {'top': 2.0},
    'J11.1': {'top': 2.0}, 'J11.2': {'bottom': 2.0},
}
hole_by_label = {s['portlabel'](p.get('pcb_port_id')): p for p in s['bytype']['pcb_plated_hole']}
wire_contacts = []
for terminal, required_layers in wire_layers.items():
    hole = hole_by_label.get(terminal)
    result = {'terminal': terminal, 'passed': False, 'contactAreaMm2ByLayer': {}}
    wire_contacts.append(result)
    if not hole:
        continue
    radius = hole['hole_diameter'] / 2
    center = Point(hole['x'], hole['y'])
    pad = s['padshape'](hole)
    ring = pad.difference(center.buffer(radius, quad_segs=128))
    net = s['portnet'][hole['pcb_port_id']]
    for layer, width in required_layers.items():
        conductors = [a['g'] for a in s['items'] if a['layer'] == layer
                      and a['net'] == net and a['kind'] == 'track'
                      and segment_width.get(a['id'], 0) >= width - 1e-6 and a['g'].intersects(pad)]
        result['contactAreaMm2ByLayer'][layer] = round(ring.intersection(unary_union(conductors)).area, 4)
    # The 32-segment-per-quadrant circular pad approximation is inscribed by <1 µm.
    annulus = center.distance(pad.boundary) - radius
    result['minimumAnnulusMm'] = round(annulus, 3)
    result['passed'] = annulus >= .399 and all(area > .01 for area in result['contactAreaMm2ByLayer'].values())

report={'circuitJsonSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'status':'passed' if all(v['passed'] for v in results+parallel+wire_contacts) else 'failed','source':str(src),'minimumIncludedTrackWidthMm':minimum,'checks':results,'parallelInputPaths':parallel,'wireTerminalContacts':wire_contacts,'method':'Keep pads, plated barrels and tracks at least 2 mm wide. Both VBUS and GND load terminals must connect even with every fill removed. Require each listed set of load-current terminals to share one physical copper island. Independently require both complete input paths on their declared layers and minimum widths. For each wire termination, subtract its bore and check for positive-area overlap between the remaining annulus and the specified load-width tracks.','limitations':'This excludes thin-signal bottlenecks. It does not qualify copper weight, thermal rise, via current sharing or pulse capability.'};out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(report['status']!='passed')
