"""Compare copper islands read from the exported RS-274X files with source pin nets."""
import argparse
from collections import defaultdict
from hashlib import sha256
from itertools import groupby
from pathlib import Path
import json
import warnings

from gerbonara import GerberFile
from gerbonara.graphic_primitives import Circle, Line
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path('output/space-octopus.circuit.json'))
parser.add_argument('--gerbers', type=Path, default=Path('output/review-fabrication'))
parser.add_argument('--report', type=Path, default=Path('output/gerber-connectivity.json'))
parser.add_argument('--edge-loss', type=float, default=0, help='Inward offset per copper edge in mm')
args = parser.parse_args()
layout, base = args.source, args.gerbers
data = defaultdict(list)
for record in json.loads(layout.read_bytes()):
    data[record['type']].append(record)
names = {n['source_net_id']: n['name'] for n in data['source_net']}
logical = {p: names[t['connected_source_net_ids'][0]]
           for t in data['source_trace'] if len(t['connected_source_net_ids']) == 1
           for p in t['connected_source_port_ids']}
components = {p['source_component_id']: p['name'] for p in data['source_component']}
source_ports = {p['source_port_id']: p for p in data['source_port']}
pcb_ports = {p['pcb_port_id']: p['source_port_id'] for p in data['pcb_port']}
internal = [group for c in data['source_component'] for group in c.get('internally_connected_source_port_ids', [])]
for group in internal:
    nets = {logical[p] for p in group if p in logical}
    if len(nets) == 1:
        for port in group:
            logical[port] = next(iter(nets))

def polygon(primitive):
    if isinstance(primitive, Circle):
        return Point(primitive.x, primitive.y).buffer(primitive.r, quad_segs=48)
    if isinstance(primitive, Line):
        return LineString([(primitive.x1, primitive.y1), (primitive.x2, primitive.y2)]).buffer(primitive.width / 2, quad_segs=32)
    arc = primitive.to_arc_poly()
    outline = arc.approximate_arcs(.0002).outline if any(a is not None and a[0] is not None for a in arc.arc_centers) else arc.outline
    if len(outline) < 3:
        return Polygon()
    geom = Polygon(outline)
    return geom if geom.is_valid else geom.buffer(0)

def load_layer(path):
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        layer = GerberFile.open(path)
        pieces = (p for obj in layer.objects for p in obj.to_primitives())
        image = Polygon()
        for dark, group in groupby(pieces, key=lambda p: p.polarity_dark):
            region = unary_union([polygon(p) for p in group])
            image = image.union(region) if dark else image.difference(region)
    if args.edge_loss > 0:
        image = image.buffer(-args.edge_loss, quad_segs=12)
    return list(image.geoms) if image.geom_type == 'MultiPolygon' else [image]

layers = {'top': 'F_Cu', 'inner1': 'In1_Cu', 'inner2': 'In2_Cu', 'bottom': 'B_Cu'}
images = {layer: load_layer(base / (file + '.gbr')) for layer, file in layers.items()}
indices = {layer: STRtree(polys) for layer, polys in images.items()}
parents = {}

def root(n):
    while n in parents:
        n = parents[n]
    return n

def join(nodes):
    if nodes:
        first = root(nodes[0])
        for item in nodes[1:]:
            last = root(item)
            if first != last:
                parents[last] = first

pads = defaultdict(list)
missing = []
via_checks = []
for item in data['pcb_smtpad'] + data['pcb_plated_hole'] + data['pcb_via']:
    via = item['type'] == 'pcb_via'
    port = pcb_ports.get(item.get('pcb_port_id'))
    identity = item[item['type'] + '_id']
    label = identity
    if port:
        source = source_ports[port]
        label = components[source['source_component_id']] + '.' + str(source.get('pin_number', source.get('name', port)))
    # Sample solid metal outside the drill. Also require every physical hole to
    # exist in the Excellon file via the separate fabrication audit.
    x, y = item['x'], item['y']
    if item['type'] == 'pcb_smtpad':
        points = [Point(x, y)]
    else:
        r = item.get('hole_diameter', item.get('hole_width')) / 2 + .025
        points = [Point(x+dx, y+dy) for dx, dy in ((r,0), (-r,0), (0,r), (0,-r))]
    nodes = []
    for layer in item.get('layers', [item.get('layer')]):
        for p in points:
            hit = list(indices[layer].query(p, predicate='intersects'))
            if len(hit) == 1:
                nodes.append((layer, int(hit[0])))
            else:
                missing.append({'terminal': label, 'layer': layer, 'x': p.x, 'y': p.y, 'islands': len(hit)})
    join(nodes)
    if port:
        pads[port].extend(nodes)
    if via:
        via_checks.append((names[item['source_net_id']], nodes, identity))
for group in internal:
    join([node for port in group for node in pads[port]])
by_net = defaultdict(set)
by_island = defaultdict(set)
for port, nodes in pads.items():
    name = logical.get(port, 'NC ' + port)
    for node in nodes:
        island = root(node)
        by_net[name].add(island)
        by_island[island].add(name)
net_opens = {n: len(by_net[n]) for n in names.values() if len(by_net[n]) != 1}
shorts = [sorted(nets) for nets in by_island.values() if len(nets) > 1]
wrong_vias = []
for net, nodes, label in via_checks:
    landed_nets = by_island[root(nodes[0])] if nodes else set()
    if landed_nets != {net}:
        wrong_vias.append({'via':label, 'expected':net, 'islandNets':sorted(landed_nets)})
report = {'sourceSha256': sha256(layout.read_bytes()).hexdigest(),
          'copperFilesSha256': {v: sha256((base / (v+'.gbr')).read_bytes()).hexdigest() for v in layers.values()},
          'reader':'Gerbonara 1.6.3, RS-274X geometry with artwork polarity and plated drill spans',
          'edgeLossMm':args.edge_loss,'nets':len(names),'physicalSmtPads':len(data['pcb_smtpad']),'physicalPlatedPads':len(data['pcb_plated_hole']),
          'vias':len(via_checks),'copperIslandsByLayer':{layer:len(polys) for layer,polys in images.items()},
          'missingTerminalCopper':missing,'opens':net_opens,'shorts':shorts,'viaNetDisagreements':wrong_vias}
report['passed'] = not (missing or net_opens or shorts or wrong_vias)
args.report.write_text(json.dumps(report,indent=2)+'\n')
print('Gerber copper extraction:',report['nets'],'nets;',len(missing),'missing copper samples;',len(net_opens),'opens;',len(shorts),'shorts;',len(wrong_vias),'via net mismatches')
raise SystemExit(not report['passed'])
