"""Independent geometric connectivity/clearance audit of tscircuit copper.
Requires shapely 2.1.x. This does not validate power capacity or EMC.
"""
import json,math,sys,collections,hashlib
from pathlib import Path
from shapely.geometry import Point,LineString,box,Polygon
from shapely.affinity import rotate,translate
from shapely.ops import unary_union
from shapely.strtree import STRtree

src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json')
out=Path(sys.argv[2] if len(sys.argv)>2 else 'output/copper-audit.json')
source_bytes=src.read_bytes();j=json.loads(source_bytes);bytype=collections.defaultdict(list)
for e in j:bytype[e['type']].append(e)
nets={e['source_net_id']:e['name'] for e in bytype['source_net']}
source_net={};trace_net={}
for e in bytype['source_trace']:
 ns=e.get('connected_source_net_ids',[])
 if len(ns)==1:
  trace_net[e['source_trace_id']]=ns[0]
  for p in e.get('connected_source_port_ids',[]):source_net[p]=ns[0]
for c in bytype['source_component']:
 for ids in c.get('internally_connected_source_port_ids',[]):
  values={source_net[p] for p in ids if p in source_net}
  if len(values)==1:
   for p in ids:source_net[p]=next(iter(values))
ports={e['pcb_port_id']:e for e in bytype['pcb_port']}
portnet={k:source_net.get(v.get('source_port_id')) for k,v in ports.items()}
sources={e['source_component_id']:e['name'] for e in bytype['source_component']}
sourceports={e['source_port_id']:e for e in bytype['source_port']}
def portlabel(pid):
 p=sourceports.get(ports.get(pid,{}).get('source_port_id'),{})
 hint=next((h[3:] for h in p.get('port_hints',[]) if h.startswith('pin') and h[3:].isdigit()),'?')
 return f"{sources.get(p.get('source_component_id'),'?')}.{p.get('pin_number',hint)}"
layers=['top','inner1','inner2','bottom'];items=[];barrels=[];widths=[];via_keys=set();unsupported=[]
def add(g,net,ls,identity,kind,port=None):
 for layer in ls:items.append({'g':g,'net':net or ('NC:'+str(port or identity)),'layer':layer,'id':identity,'kind':kind,'port':port})
def padshape(p):
 x,y=p['x'],p['y'];shape=p['shape']
 if shape=='circle':return Point(x,y).buffer(p.get('radius',p.get('outer_diameter',0)/2),quad_segs=32)
 w=p.get('width',p.get('rect_pad_width',p.get('outer_width')));h=p.get('height',p.get('rect_pad_height',p.get('outer_height')))
 if w is None or h is None:unsupported.append(p);return None
 if shape=='pill':
  r=min(w,h)/2;g=LineString([(-max(0,w/2-r),-max(0,h/2-r)),(max(0,w/2-r),max(0,h/2-r))]).buffer(r,quad_segs=32)
 else:
  r=min(p.get('corner_radius',p.get('rect_border_radius',0)),w/2,h/2)
  g=box(-w/2+r,-h/2+r,w/2-r,h/2-r).buffer(r,quad_segs=32) if r>0 else box(-w/2,-h/2,w/2,h/2)
 return translate(rotate(g,p.get('rect_ccw_rotation',p.get('ccw_rotation',0)),origin=(0,0)),x,y)
for p in bytype['pcb_smtpad']+bytype['pcb_plated_hole']:
 g=padshape(p)
 if g is None:continue
 pid=p.get('pcb_port_id');net=portnet.get(pid);ls=p.get('layers',[p.get('layer','top')]);identity=p.get('pcb_smtpad_id',p.get('pcb_plated_hole_id'))
 add(g,net,ls,identity,'pad',pid)
 if p['type']=='pcb_plated_hole':barrels.append((net or 'NC:'+str(pid or identity),ls,g))
for t in bytype['pcb_trace']:
 net=trace_net.get(t.get('source_trace_id')) or (t.get('connection_name') if t.get('connection_name') in nets else None)
 if net is None:unsupported.append({'traceWithoutNet':t.get('pcb_trace_id')});continue
 for k,p in enumerate(t['route']):
  if p.get('route_type')=='via':
   dia=p.get('outer_diameter',p.get('via_diameter',.6));g=Point(p['x'],p['y']).buffer(dia/2,quad_segs=32)
   # Only through vias are supported by this four-layer design.
   add(g,net,layers,f"{t['pcb_trace_id']}:v{k}",'via');barrels.append((net,layers,g));via_keys.add((round(p['x'],5),round(p['y'],5),net))
  if k==0:continue
  a=t['route'][k-1]
  if p.get('route_type')=='wire' and a.get('route_type')=='wire' and a.get('layer')!=p.get('layer'):
   unsupported.append({'layerJumpWithoutVia':t['pcb_trace_id']});continue
  layer=p.get('layer') or a.get('layer')
  if layer is None:continue
  width=p.get('width',a.get('width',.25));widths.append(width)
  g=LineString([(a['x'],a['y']),(p['x'],p['y'])]).buffer(width/2,quad_segs=16)
  add(g,net,[layer],f"{t['pcb_trace_id']}:{k}",'track')

for v in bytype['pcb_via']:
 net=v.get('source_net_id') or trace_net.get(v.get('source_trace_id'))
 if net is None:unsupported.append({'viaWithoutNet':v['pcb_via_id']});continue
 key=(round(v['x'],5),round(v['y'],5),net)
 if key in via_keys:continue
 g=Point(v['x'],v['y']).buffer(v['outer_diameter']/2,quad_segs=32);ls=v.get('layers',layers)
 add(g,net,ls,v['pcb_via_id'],'via');barrels.append((net,ls,g));via_keys.add(key)
for p in bytype['pcb_copper_pour']:
 if p.get('shape')=='brep':
  rings=p['brep_shape'];allrings=[rings['outer_ring'],*rings.get('inner_rings',[])]
  if any(v.get('bulge',0) for r in allrings for v in r['vertices']):unsupported.append({'curvedPour':p['pcb_copper_pour_id']});continue
  g=Polygon([(v['x'],v['y']) for v in rings['outer_ring']['vertices']],[[(v['x'],v['y']) for v in r['vertices']] for r in rings.get('inner_rings',[])])
 elif p.get('shape')=='polygon':g=Polygon([(v['x'],v['y']) for v in p['points']])
 else:unsupported.append({'pourShape':p.get('shape')});continue
 if not g.is_valid:unsupported.append({'invalidPour':p['pcb_copper_pour_id']});g=g.buffer(0)
 add(g,p.get('source_net_id'),[p['layer']],p['pcb_copper_pour_id'],'pour')
# Distinct-net copper, including NC pads, must retain 0.2 mm separation.
clearance=[];shorts=[]
for layer in layers:
 group=[x for x in items if x['layer']==layer];geoms=[x['g'] for x in group];tree=STRtree(geoms)
 seen=set()
 for i,a in enumerate(group):
  for idx in tree.query(a['g'].buffer(.2)):
   k=int(idx)
   if k<=i:continue
   b=group[k]
   if a['net']==b['net']:continue
   # Record one finding per pair of copper primitives.
   distance=a['g'].distance(b['g'])
   if distance>=.2-1e-5:continue
   finding={'layer':layer,'a':a['id'],'b':b['id'],'netA':nets.get(a['net'],a['net']),'netB':nets.get(b['net'],b['net']),'distanceMm':round(distance,6)}
   clearance.append(finding)
   if a['g'].intersection(b['g']).area>1e-8:shorts.append(finding)

board=bytype['pcb_board'][0];outline=Polygon([(p['x'],p['y']) for p in board['outline']]);interior=outline.buffer(-.5)
holes=[]
for c in bytype['pcb_cutout']:
 if c['shape']=='circle':holes.append(Point(c['center']['x'],c['center']['y']).buffer(c['radius']+.5,quad_segs=128))
 else:unsupported.append({'cutout':c})
for h in bytype['pcb_hole']:
 if h.get('hole_shape','circle')=='circle':holes.append(Point(h['x'],h['y']).buffer(h['hole_diameter']/2+.5,quad_segs=128))
hole_union=unary_union(holes);edge=[];hole_hits=[]
mechanical=json.loads(Path('data/board-geometry.json').read_text())
pcb_refs={c['pcb_component_id']:sources.get(c.get('source_component_id'),'') for c in bytype['pcb_component']}
hardware=[]
for h in bytype['pcb_hole']:
 if pcb_refs.get(h.get('pcb_component_id'),'').startswith('H'):
  r=mechanical['mounting']['keepoutDiameterMm']/2
  hardware.append(box(h['x']-r,h['y']-r,h['x']+r,h['y']+r).buffer(mechanical['mounting'].get('copperKeepoutGapMm',.2)))
hole_union=unary_union([hole_union,*hardware])
for a in items:
 if a['kind']=='pad':continue
 if not interior.buffer(1e-5).covers(a['g']):edge.append({'id':a['id'],'layer':a['layer']})
 if a['g'].intersection(hole_union).area>1e-8:hole_hits.append({'id':a['id'],'layer':a['layer']})

# Build conductive islands on each layer, join them only through plated barrels,
# then place every physical terminal on that graph. No airwire counts are used.
connectivity=[];netGraphs={}
for net,name in nets.items():
 group=[a for a in items if a['net']==net];nodes=[];node_layer=[]
 for layer in layers:
  u=unary_union([a['g'] for a in group if a['layer']==layer]).buffer(1e-7)
  polygons=list(u.geoms) if u.geom_type=='MultiPolygon' else ([u] if not u.is_empty else [])
  for p in polygons:nodes.append(p);node_layer.append(layer)
 parent=list(range(len(nodes)))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(ids):
  for k in ids[1:]:parent[root(k)]=root(ids[0])
 for bn,ls,g in barrels:
  if bn==net:join([i for i,p in enumerate(nodes) if node_layer[i] in ls and p.intersects(g)])
 # Multiple pads with the same package pin are electrically joined inside the
 # device. Their declared internal connection must also exist in this graph.
 for c in bytype['source_component']:
  for ids in c.get('internally_connected_source_port_ids',[]):
   pp=[p for p in ports.values() if p.get('source_port_id') in ids and portnet.get(p['pcb_port_id'])==net]
   join([i for i,g in enumerate(nodes) if any(node_layer[i] in p['layers'] and g.distance(Point(p['x'],p['y']))<1e-5 for p in pp)])
 terminals=collections.defaultdict(list)
 for pid in sorted({a['port'] for a in group if a.get('port')}):
  pp=ports[pid];point=Point(pp['x'],pp['y']);ids=[i for i,p in enumerate(nodes) if node_layer[i] in pp['layers'] and p.distance(point)<1e-5]
  if ids:terminals[root(ids[0])].append(portlabel(pid))
  else:terminals['missing:'+pid].append(portlabel(pid))
 connectivity.append({'net':name,'terminalCount':sum(map(len,terminals.values())),'connected':len(terminals)<=1,'islands':list(terminals.values())})
 netGraphs[net]={'nodes':nodes,'layers':node_layer,'roots':[root(i) for i in range(len(nodes))],'terminals':dict(terminals)}
unconnected=[n for n in connectivity if not n['connected']]
report={'source':str(src),'status':'passed' if not any([unsupported,shorts,clearance,edge,hole_hits,unconnected]) else 'failed','method':'Independent Shapely geometry audit of pads, wires and plated barrels; 0.2 mm copper separation, 0.5 mm edge/NPTH clearance. Rounded pads retain the source corner radii; declared package-internal pin connections are included.','tracks':len(bytype['pcb_trace']),'vias':len(via_keys),'minWireWidthMm':min(widths,default=None),'maxWireWidthMm':max(widths,default=None),'nets':len(nets),'fullyConnectedNets':len(nets)-len(unconnected),'unconnectedNetCount':len(unconnected),'shortCount':len(shorts),'clearanceViolationCount':len(clearance),'edgeViolationCount':len(edge),'holeViolationCount':len(hole_hits),'unsupportedCount':len(unsupported),'unconnectedNets':unconnected,'shorts':shorts,'clearances':clearance,'edges':edge,'holes':hole_hits,'unsupported':unsupported,'fabricationReady':False,'limitations':['Power-current and thermal qualification pending.','Gate/source loops, Kelvin return paths and differential pairs require engineering review.','Selected provisional packages and assembly fit require confirmation.']}
report['circuitJsonSha256']=hashlib.sha256(source_bytes).hexdigest()
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if not isinstance(v,(list,dict))},indent=2))
sys.exit(0 if report['status']=='passed' else 1)
