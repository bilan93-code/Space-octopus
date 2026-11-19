"""Clip reference-plane copper from the exact captured copper geometry."""
import json,sys,os
from pathlib import Path
from shapely.geometry import Point,Polygon,box
from shapely.ops import unary_union
src=Path(sys.argv[1] if len(sys.argv)>1 else 'routing-work/revision/complete-seed.circuit.json');scope={'__name__':'copper_geometry'};sys.argv=['check-copper.py',str(src),'routing-work/revision/pre-plane-audit.json']
try:exec(compile(Path('scripts/check-copper.py').read_text(),'check-copper.py','exec'),scope)
except SystemExit:pass
j=scope['j'];items=scope['items'];nets={v:k for k,v in scope['nets'].items()};g=scope['outline'].buffer(-.6)
for h in scope['bytype']['pcb_hole']:g=g.difference(Point(h['x'],h['y']).buffer(h['hole_diameter']/2+.6,quad_segs=96))
for c in scope['bytype']['pcb_cutout']:
 if c['shape']=='circle':g=g.difference(Point(c['center']['x'],c['center']['y']).buffer(c['radius']+.6,quad_segs=128))
g=g.difference(unary_union(scope['hardware']).buffer(.01))
planes=[];copper=[];kelvin=json.loads(Path('data/kelvin-routing.json').read_text())
negative_pickups=[Point(*p) for b in kelvin['branches'] for p in [b['sourceVia'],b['pickupGroundVia']]]
for layer,name in [('top','GND'),('inner1','GND'),('inner2','VBUS'),('bottom','GND')]:
 blocked=unary_union([a['g'] for a in items if a['layer']==layer and a['net']!=nets[name]])
 region=g.difference(blocked.buffer(.25,quad_segs=16))
 # The optical marks have 1 mm copper inside a 2 mm mask opening. Keep
 # surrounding copper outside that opening, with a 0.25 mm mask web.
 if layer=='top':
  for p in scope['bytype']['pcb_smtpad']:
   if scope['pcb_refs'].get(p.get('pcb_component_id'),'').startswith('FID'):
    region=region.difference(Point(p['x'],p['y']).buffer(1.25,quad_segs=64))
 if name=='GND':
  # Keep negative sense paths isolated until their shunt force pads.
  sense=[a['g'] for a in items if a['layer']==layer and a['net']==nets['GND'] and (
   a['id'].startswith('kelvin_') or a['kind']=='pad' and scope['portlabel'](a.get('port')) in ['U2.10','U2.11','U2.20'] or
   a['kind']=='via' and any(a['g'].centroid.distance(p)<1e-5 for p in negative_pickups))]
  force=unary_union([a['g'] for a in items if a['layer']==layer and a['kind']=='pad' and a['net']==nets['GND'] and scope['portlabel'](a.get('port')).startswith('RSH')])
  region=region.difference(unary_union(sense).difference(force).buffer(.25,quad_segs=24))
  for p in scope['ports'].values():
   sp=scope['sourceports'].get(p.get('source_port_id'),{});ref=scope['sources'].get(sp.get('source_component_id'))
   if ref in ['C1','C2','C3','C4'] and str(sp.get('pin_number'))=='1':region=region.difference(Point(p['x'],p['y']).buffer(2.2,quad_segs=64))
  for b in kelvin['branches']:
   for p in b['isolateFromGroundPlaneAt']:region=region.difference(Point(p['x'],p['y']).buffer(p['radius'],quad_segs=64))
 # Remove thin copper whiskers geometrically, retaining the existing clearances.
 minimum_feature=float(os.environ.get('PLANE_MIN_FEATURE_MM','.22'))
 if minimum_feature>0:region=region.buffer(-minimum_feature/2,quad_segs=12).buffer(minimum_feature/2,quad_segs=12).intersection(region)
 region=region.simplify(.005,preserve_topology=True)
 polys=list(region.geoms) if region.geom_type=='MultiPolygon' else [region]
 for poly in polys:
  if poly.area<.01:continue
  outer=[list(p) for p in poly.exterior.coords[:-1]];holes=[[list(p) for p in ring.coords[:-1]] for ring in poly.interiors]
  planes.append({'layer':layer,'name':name,'outer':outer,'holes':holes,'areaMm2':poly.area})
  def ring(coords):return {'vertices':[{'x':x,'y':y,'bulge':0} for x,y in coords]}
  copper.append({'type':'pcb_copper_pour','pcb_copper_pour_id':'plane_'+str(len(copper)),'layer':layer,'source_net_id':nets[name],'shape':'brep','brep_shape':{'outer_ring':ring(outer),'inner_rings':[ring(v) for v in holes]}})
Path('routing-work/revision/planes.json').write_text(json.dumps(planes));Path('routing-work/revision/with-planes.circuit.json').write_text(json.dumps([a for a in j if a['type']!='pcb_copper_pour']+copper));print('Clipped',len(planes),'copper plane regions.')
