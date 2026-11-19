"""Measure connected signal centreline paths; no stackup/impedance claim."""
import json,sys,math,heapq,collections,hashlib
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.ops import nearest_points
from shapely.strtree import STRtree
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');s={};sys.argv=['check-copper.py',str(src),'/tmp/path-unused']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s)
parts=sum([json.loads(Path('data/'+n+'.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake']],[]);by={p['ref']:p for p in parts};netid={v:k for k,v in s['nets'].items()};cache={}
def pin(ref,net):return ref+'.'+next(k for k,v in by[ref]['pins'].items() if v==net)
def measure(name,start,end):
 n=netid[name]
 if n not in cache:
  objects=[]
  for t in s['bytype']['pcb_trace']:
   if (s['trace_net'].get(t.get('source_trace_id')) or t.get('connection_name'))!=n:continue
   for k,(a,b) in enumerate(zip(t['route'],t['route'][1:])):
    if a['route_type']!=b['route_type'] or a['route_type']!='wire' or a['layer']!=b['layer']:continue
    line=LineString([(a['x'],a['y']),(b['x'],b['y'])])
    if line.length<1e-7:continue
    objects.append({'kind':'wire','line':line,'g':line.buffer(b['width']/2,quad_segs=16),'layer':a['layer'],'cuts':{0.,line.length}})
  seen=set()
  for a in s['items']:
   if a['net']!=n or a['kind'] not in ['pad','via']:continue
   key=(a['id'],a['layer'])
   if key in seen:continue
   seen.add(key);objects.append({**a,'node':('contact',a['id'],a['layer'])})
  tree=STRtree([a['g'] for a in objects]);joins=[];adj=collections.defaultdict(list);labels=collections.defaultdict(list);via_nodes=collections.defaultdict(list)
  def node(i,d):p=objects[i]['line'].interpolate(d);return ('wire',i,round(d,6))
  for i,a in enumerate(objects):
   if a['kind']=='pad' and a.get('port'):labels[s['portlabel'](a['port'])].append(a['node'])
   if a['kind']=='via':via_nodes[a['id']].append(a['node'])
   for k in tree.query(a['g'],predicate='dwithin',distance=1e-7):
    k=int(k)
    if k<=i:continue
    b=objects[k]
    if a['layer']!=b['layer']:continue
    if a['kind']=='wire' and b['kind']=='wire':
     p,q=nearest_points(a['line'],b['line']);da=a['line'].project(p);db=b['line'].project(q);a['cuts'].add(da);b['cuts'].add(db);joins.append((node(i,da),node(k,db),p.distance(q)))
    elif a['kind']=='wire' or b['kind']=='wire':
     wi,wire,c=(i,a,b) if a['kind']=='wire' else (k,b,a);p=nearest_points(wire['line'],c['g'].representative_point())[0];d=wire['line'].project(p);wire['cuts'].add(d);joins.append((node(wi,d),c['node'],0))
    else:joins.append((a['node'],b['node'],0))
  for i,a in enumerate(objects):
   if a['kind']=='wire':
    cuts=sorted(a['cuts'])
    for x,y in zip(cuts,cuts[1:]):joins.append((node(i,x),node(i,y),y-x))
  for nodes in via_nodes.values():
   for a in nodes[1:]:joins.append((nodes[0],a,0))
  for pid,p in s['ports'].items():
   if s['portnet'].get(pid)!=n or len(p['layers'])<2:continue
   nodes=labels.get(s['portlabel'](pid),[])
   for a in nodes[1:]:joins.append((nodes[0],a,0))
  for a,b,w in joins:adj[a].append((b,w));adj[b].append((a,w))
  cache[n]=(adj,labels)
 adj,labels=cache[n];goals=set(labels[end]);queue=[];distance={};parent={};serial=0
 for a in labels[start]:distance[a]=0;heapq.heappush(queue,(0,serial,a));serial+=1
 target=None
 while queue:
  d,_,a=heapq.heappop(queue)
  if d!=distance[a]:continue
  if a in goals:target=a;break
  for b,w in adj[a]:
   nd=d+w
   if nd<distance.get(b,float('inf')):distance[b]=nd;parent[b]=a;heapq.heappush(queue,(nd,serial,b));serial+=1
 if target is None:return {'net':name,'from':start,'to':end,'measured':False}
 path=[target]
 while path[-1] in parent:path.append(parent[path[-1]])
 vias=set()
 for a,b in zip(path,path[1:]):
  if a[0]==b[0]=='contact' and a[1]==b[1] and a[2]!=b[2] and any(x['kind']=='via' and x['id']==a[1] for x in s['items']):vias.add(a[1])
 return {'net':name,'from':start,'to':end,'measured':True,'planarCenterlineLengthMm':round(distance[target],3),'viaTransitions':len(vias)}
pairs=[]
for label,names,driver,connector in [('BiSS clock',['ENC_CLK_P','ENC_CLK_N'],'U18','J4'),('BiSS data',['ENC_DATA_P','ENC_DATA_N'],'U20','J4'),('CAN to J5',['CANH','CANL'],'U6','J5'),('CAN to J6',['CANH','CANL'],'U6','J6')]:
 paths=[measure(n,pin(driver,n),pin(connector,n)) for n in names];pair={'pair':label,'paths':paths}
 if all(p['measured'] for p in paths):pair['planarLengthDifferenceMm']=round(abs(paths[0]['planarCenterlineLengthMm']-paths[1]['planarCenterlineLengthMm']),3);pair['illustrativeSkewNsAt7PsPerMm']=round(pair['planarLengthDifferenceMm']*.007,3)
 pairs.append(pair)
gates=[]
for i in range(1,8):
 net='BRAKE_GATE' if i==7 else 'Q'+str(i)+'_G';q='Q'+str(i)
 resistors=[p for p in parts if p['kind']=='resistor' and net in p['pins'].values() and any(v and (v.startswith(('GH_','GL_','BRAKE_DRV_'))) for v in p['pins'].values())]
 for r in resistors:gates.append(measure(net,pin(r['ref'],net),q+'.1'))
report={'status':'measured' if all(p['measured'] for pair in pairs for p in pair['paths']) and all(p['measured'] for p in gates) else 'measurement incomplete','pairs':pairs,'gateResistorToMosfetPaths':gates,'source':str(src),'timingAndImpedanceQualified':False,'method':'Dijkstra paths through intersecting native copper shapes, with wire centreline lengths. Pad interiors and via axial distances contribute zero to the reported planar length.','limitations':['These are approximate planar path measurements, not a transmission-line solver.','The 7 ps/mm comparison is illustrative; actual propagation, differential impedance and return-current continuity need the selected stackup and material data.','The source plan starts BiSS clocking at 2 MHz (500 ns period); this alone does not set an edge-rate or EMC budget.','Gate path length alone does not measure gate/source loop inductance or switching stability.']}
report['circuitJsonSha256']=hashlib.sha256(src.read_bytes()).hexdigest()
Path('output/signal-path-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
