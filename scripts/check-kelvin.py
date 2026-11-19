"""Remove each pickup electrode and prove its sense branch becomes isolated.
This catches hidden connections to a plane, a motor-current track or another
port before the intended shunt pickup, even though the net names are equal.
"""
import json,sys,collections,hashlib
from pathlib import Path
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');out=Path(sys.argv[2] if len(sys.argv)>2 else 'output/kelvin-audit.json');scope={'__name__':'copper_geometry'};sys.argv=['check-copper.py',str(src),str(out.with_suffix('.copper.json'))]
# Kelvin isolation needs physical conductive islands, not another full DRC of
# every unrelated signal. The independent copper check remains a separate gate.
code=Path('scripts/check-copper.py').read_text()
exec(compile(code.split('# Distinct-net copper')[0],'copper_geometry','exec'),scope)
allnets=scope['nets'];scope['nets']={n:name for n,name in allnets.items() if name=='GND' or name.startswith('SHUNT_')}
connect='connectivity=[];netGraphs={}'+code.split('connectivity=[];netGraphs={}')[1].split('unconnected=[n for n in connectivity')[0]
exec(compile(connect,'kelvin_connectivity','exec'),scope);scope['nets']=allnets
items=scope['items'];ports=scope['ports'];labels={k:scope['portlabel'](k) for k in ports};nets={v:k for k,v in scope['nets'].items()};results=[]
for branch in json.loads(Path('data/kelvin-routing.json').read_text())['branches']:
 for polarity,pin,padno,netname in [('positive',branch['positiveDriverPin'],1,'SHUNT_'+branch['phase']+'_TOP'),('negative',branch['negativeDriverPin'],2,'GND')]:
  n=nets[netname];pickup=next(k for k,v in labels.items() if v==f"{branch['shunt']}.{padno}");source=next(k for k,v in labels.items() if v==f'U2.{pin}')
  electrode_by_layer={l:unary_union([a['g'] for a in items if a['kind']=='pad' and a.get('port')==pickup and a['layer']==l]).buffer(.025) for l in scope['layers']}
  allnodes=[];ls=[]
  for l in scope['layers']:
   g=unary_union([a['g'] for a in items if a['net']==n and a['layer']==l]).difference(electrode_by_layer[l]).buffer(1e-7)
   pieces=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
   for v in pieces:
    if v.is_empty:continue
    allnodes.append(v);ls.append(l)
  parent=list(range(len(allnodes)))
  def root(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  for bn,bl,g in scope['barrels']:
   if bn!=n:continue
   ids=[i for i,v in enumerate(allnodes) if ls[i] in bl and v.intersects(g)]
   for k in ids[1:]:parent[root(k)]=root(ids[0])
  def belongs(p):return {root(i) for i,v in enumerate(allnodes) if ls[i] in p['layers'] and v.distance(Point(p['x'],p['y']))<1e-5}
  island=belongs(ports[source]);other=[labels[k] for k,p in ports.items() if k!=source and k!=pickup and scope['portnet'].get(k)==n and belongs(p)&island]
  plane=False
  for a in items:
   if a['kind']!='pour' or a['net']!=n:continue
   if any(root(i) in island and ls[i]==a['layer'] and v.intersection(a['g']).area>1e-6 for i,v in enumerate(allnodes)):plane=True;break
  connected_before=any(labels[source] in terminals and labels[pickup] in terminals for terminals in scope['netGraphs'][n]['terminals'].values())
  passed=connected_before and bool(island) and not other and not plane
  results.append({'phase':branch['phase'],'polarity':polarity,'driverPin':pin,'pickup':labels[pickup],'passed':passed,'connectedToPickup':connected_before,'portsConnectedBeforePickup':other,'planeConnectedBeforePickup':plane})
report={'status':'passed' if all(r['passed'] for r in results) else 'failed','circuitJsonSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'method':'Remove the intended shunt electrode only from its physical copper layer, join only real copper and barrels, and require the driver pickup to have no other port or plane connection. No package-internal or logical-net equivalence is used. Full copper DRC is a separate design check.','branches':results}
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(report['status']!='passed')
