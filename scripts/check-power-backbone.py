"""Power terminals must connect without relying on narrow signal traces."""
import hashlib,json,sys,collections,math
from pathlib import Path
from functools import lru_cache
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
 'VBUS':['J1.1','C1.1','C2.1','C3.1','C4.1','C5.1','Q1.2','Q3.2','Q5.2','F2.1','C905.1'],
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
# Check revised high-current branches geometrically, independently of trace names.
# Shrinking copper separates near-tangent contacts which a raw polygon union joins.
positions = {s['portlabel'](pid): Point(p['x'], p['y']) for pid, p in s['ports'].items()}
bulk = ['C1.1','C2.1','C3.1','C4.1']

@lru_cache(None)
def tracks(net, layer, width, below_width=None):
    return unary_union([a['g'] for a in s['items'] if a['net'] == ids[net] and a['layer'] == layer
                        and a['kind'] == 'track' and segment_width.get(a['id'], 0) >= width - 1e-6
                        and (below_width is None or segment_width[a['id']] < below_width - 1e-6)])

@lru_cache(None)
def corridors(net, layer, width, below_width=None):
    pads = [a['g'] for a in s['items'] if a['net'] == ids[net] and a['layer'] == layer and a['kind'] == 'pad']
    copper = unary_union([tracks(net, layer, width, below_width), *pads])
    radius = width / 2 - .02
    core = copper.buffer(-radius)
    islands = ([core] if core.geom_type == 'Polygon' else list(core.geoms)) if not core.is_empty else []
    return [p.buffer(radius).intersection(copper) for p in islands]

def through_vias(net):
    result = []
    for v in s['bytype']['pcb_via']:
        via_net = v.get('source_net_id') or s['trace_net'].get(v.get('source_trace_id'))
        if via_net != ids[net] or not set(s['layers']).issubset(v['layers']):
            continue
        center = Point(v['x'], v['y'])
        result.append((center, v['outer_diameter'], v['hole_diameter']))
    return result

def endpoints(island, labels):
    return [label for label in labels if label in positions and island.distance(positions[label]) < 1e-5]

def direct_capacitors(net, layer, width, terminal):
    return sorted({c for island in corridors(net, layer, width)
                   if endpoints(island, [terminal]) for c in endpoints(island, bulk)})

def via_transfer(vias, launch, destination):
    # Count distinct finished barrels, rather than copper primitives duplicated on each face.
    return {(round(c.x, 5), round(c.y, 5)): (outer, bore) for c, outer, bore in vias
            if launch.covers(c) and destination.covers(c)}

# Fanout from the top-mounted brake fuse must carry current into the inner rail
# through the designed array. A lone via on an otherwise wide track is insufficient.
brake_pads = {s['portlabel'](pad.get('pcb_port_id')): s['padshape'](pad) for pad in s['bytype']['pcb_smtpad']}
feed_pad, output_pad = brake_pads.get('F2.1'), brake_pads.get('F2.2')
feed_vias = [(c, outer, bore) for c, outer, bore in through_vias('VBUS')
             if outer >= .75 - 1e-6 and bore >= .35 - 1e-6 and feed_pad is not None
             and feed_pad.covers(c.buffer(outer / 2, quad_segs=32))]
feed_rails = [(island, endpoints(island, bulk)) for island in corridors('VBUS','inner2',3.0)]
best_transfer, reached = {}, []
for rail, caps in feed_rails:
    if caps:
        transfer = via_transfer(feed_vias, feed_pad, rail) if feed_pad is not None else {}
        if len(transfer) > len(best_transfer):
            best_transfer, reached = transfer, caps
# A via-centre hit alone can conceal poor wetting at a track end. Intersect
# each physical annular land (finished bore removed) with actual routed copper.
via_contact_fractions = []
for (x, y), (outer, bore) in best_transfer.items():
    center = Point(x, y)
    ring = center.buffer(outer / 2, quad_segs=48).difference(center.buffer(bore / 2, quad_segs=48))
    via_contact_fractions.append(ring.intersection(tracks('VBUS','inner2',3.0)).area / ring.area)
brake_top = corridors('BRAKE_PLUS','top',3.0)
output_connected = any(len(endpoints(rail, ['F2.2','J11.1'])) == 2 for rail in brake_top)
brake = {
    'passed': len(best_transfer) >= 16 and all(f > 0 for f in via_contact_fractions) and output_connected,
    'F2.1': {'layer': 'inner2', 'minimumTrackWidthMm': 3.0, 'capacitorTerminalsReached': reached,
             'throughViasSharingFeedAndTrunk': len(best_transfer), 'minimumViaBoreMm': .35,
             'minimumViaAnnulusTrackCoverageFraction': round(min(via_contact_fractions, default=0), 3),
             'finishedHoleAreaInFuseLandMm2': round(sum(math.pi * (bore/2)**2 for outer,bore in best_transfer.values()), 3),
             'totalConnectedBoreDiameterMm': round(sum(bore for outer, bore in best_transfer.values()), 3)},
    'F2.2': {'layer': 'top', 'minimumTrackWidthMm': 3.0, 'reachesJ11Pin1': output_connected,
             'landOverlapWithWideTracksMm2': round(output_pad.intersection(tracks('BRAKE_PLUS','top',3.0)).area, 3)
                                             if output_pad is not None else 0},
}

# The inlet branches run to a physical DC-link capacitor terminal on independent
# copper layers. The inner branch transitions from a 4.5 mm launch to a 3 mm rail.
parallel = []
for layer, width in [('inner2', 3.0), ('bottom', 2.4)]:
    reached_caps = direct_capacitors('VBUS', layer, width, 'J1.1')
    parallel.append({'net': 'VBUS', 'from': 'J1.1', 'to': 'C1.1', 'layer': layer,
                     'minimumTrackWidthMm': width, 'capacitorTerminalsReached': reached_caps,
                     'passed': 'C1.1' in reached_caps})

inlet_pad = next((s['padshape'](a) for a in s['bytype']['pcb_plated_hole']
                  if s['portlabel'](a.get('pcb_port_id')) == 'J1.1'), None)
wide_launch = [g for g in corridors('VBUS','inner2',4.5) if endpoints(g, ['J1.1'])]
capacitor_legs = [g for g in corridors('VBUS','inner2',3.0,4.5) if endpoints(g, ['C1.1'])]
# Require an actual handoff outside the input land. A fat, disconnected stub
# beside J1 and an unrelated 3 mm path must not masquerade as a two-width feed.
handoff = unary_union([launch.intersection(leg) for launch in wide_launch for leg in capacitor_legs])
if inlet_pad is not None:
    handoff = handoff.difference(inlet_pad)
parallel[0]['launchWidthMm'] = 4.5
parallel[0]['launchHandoffAreaMm2'] = round(handoff.area, 3)
parallel[0]['passed'] = parallel[0]['passed'] and handoff.area > .01
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
    result = {'terminal': terminal, 'passed': False, 'contactAreaMm2ByLayer': {}, 'annulusCoverageFractionByLayer': {}}
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
        area = ring.intersection(unary_union(conductors)).area
        result['contactAreaMm2ByLayer'][layer] = round(area, 4)
        result['annulusCoverageFractionByLayer'][layer] = round(area / ring.area, 3)
    # The 32-segment-per-quadrant circular pad approximation is inscribed by <1 µm.
    annulus = center.distance(pad.boundary) - radius
    result['minimumAnnulusMm'] = round(annulus, 3)
    result['passed'] = annulus >= .399 and all(area > .01 for area in result['contactAreaMm2ByLayer'].values())

report={'circuitJsonSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'status':'passed' if all(v['passed'] for v in results+parallel+wire_contacts+[brake]) else 'failed','source':str(src),'minimumIncludedTrackWidthMm':minimum,'checks':results,'parallelInputPaths':parallel,'wireTerminalContacts':wire_contacts,'brakeFuseFeed':brake,'method':'Keep pads, plated barrels and tracks at least 2 mm wide. Both VBUS and GND load terminals must connect even with every fill removed. Require each listed set of load-current terminals to share one physical copper island. Follow the revised VBUS input to a real bulk capacitor terminal. On the revised branches shrink the no-fill copper by half the specified track width less 0.02 mm, separate disconnected cores, then expand each core to test its terminal and via contacts. Test the F2 input through-via array separately from its output route to J11.1. For each wire termination, subtract its bore and check for positive-area overlap between the remaining annulus and the specified load-width tracks.','limitations':'This excludes thin-signal bottlenecks. The geometric neck screen treats pad faces as solid, with separate annular contact checks at the harness. Copper weight, barrel plating, vacuum thermal rise, current sharing and pulse capability still require stackup and thermal qualification.'};out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(report['status']!='passed')
