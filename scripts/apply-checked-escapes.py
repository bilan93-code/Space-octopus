"""Merge declared local escape proposals against the latest copper.

Exact copper clearance is rechecked; foreign fills are clipped around additions.
Run the full copper, drill, power and Kelvin audits on the result.
"""
import json,sys
from pathlib import Path
from shapely import make_valid
from shapely.ops import unary_union
from shapely.strtree import STRtree

src,proposal,out=map(Path,sys.argv[1:4]);j=json.loads(src.read_text());p=json.loads(proposal.read_text())
report=json.loads(proposal.with_suffix('.escapes.json').read_text())
displaced={identity for e in report['escapes'] for identity in e['displaced']}
assert not displaced or '--allow-reported-signal-displacement' in sys.argv[4:],'Signal displacement must be explicitly selected.'
if displaced:
 manifest=json.loads(Path('data/kelvin-routing.json').read_text())
 pickups=[b[key] for b in manifest['branches'] for key in ['sourceVia','pickupGroundVia','positiveSourceVia','positivePickupVia']]
 for a in j:
  identity=a.get('pcb_trace_id',a.get('pcb_via_id'))
  if identity not in displaced:continue
  assert not identity.startswith(('kelvin_','plane_stitch_','seed_input_','seed_ground_'))
  if a['type']=='pcb_trace':
   assert all(v.get('width',0)<.6 and v.get('via_diameter',0)<.59 for v in a['route'])
   vias=[v for v in a['route'] if v['route_type']=='via']
  else:
   assert a['type']=='pcb_via' and a['outer_diameter']<.59
   vias=[a]
  assert not any((v['x']-x)**2+(v['y']-y)**2<1e-10 for v in vias for x,y in pickups)
 j=[a for a in j if a.get('pcb_trace_id',a.get('pcb_via_id')) not in displaced]
existing={a['pcb_trace_id'] for a in j if a['type']=='pcb_trace'}
added=[a for a in p if a['type']=='pcb_trace' and a['pcb_trace_id'].startswith('seed_local_repair_') and a['pcb_trace_id'] not in existing]
assert added,'No new escape proposals.'
identities={a['pcb_trace_id'] for a in added}
out.write_text(json.dumps(j+added));s={};sys.argv=['check-copper.py',str(out),'/tmp/escape-merge-unused.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s)
new=[a for a in s['items'] if a['id'].rsplit(':',1)[0] in identities]
foreign=[a for a in s['items'] if a['kind']!='pour'];tree=STRtree([a['g'] for a in foreign])
for a in new:
 for k in tree.query(a['g'],predicate='dwithin',distance=.2):
  b=foreign[int(k)]
  assert a['net']==b['net'] or a['layer']!=b['layer'] or a['g'].distance(b['g'])>=.2-1e-5,('Escape conflicts with latest copper',a['id'],b['id'])
def polygons(g):
 if g.is_empty:return []
 if g.geom_type=='Polygon':return [g]
 return [p for c in getattr(g,'geoms',[]) for p in polygons(c)]
def ring(r):return {'vertices':[{'x':float(x),'y':float(y),'bulge':0} for x,y in list(r.coords)[:-1]]}
result=[a for a in j if a['type']!='pcb_copper_pour']+added
for a in [a for a in s['items'] if a['kind']=='pour']:
 cutters=unary_union([b['g'].buffer(.25) for b in new if b['net']!=a['net'] and b['layer']==a['layer']])
 g=make_valid(a['g']).difference(cutters)
 for k,pg in enumerate(polygons(g)):
  result.append({'type':'pcb_copper_pour','pcb_copper_pour_id':a['id']+'_escape'+str(k),'source_net_id':a['net'],'layer':a['layer'],'shape':'brep','brep_shape':{'outer_ring':ring(pg.exterior),'inner_rings':[ring(r) for r in pg.interiors]}})
out.write_text(json.dumps(result));print('Merged',len(added),'local escapes against current copper; displaced',len(displaced),'declared signal copper objects.')
