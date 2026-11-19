"""Keep physical paths between real terminals; remove abandoned revision stubs.
Power tracks, fixed escapes, thermal arrays and Kelvin copper are mandatory.
Any net whose existing terminal connectivity worsens is restored unchanged.
"""
import json,sys,collections,heapq,copy,subprocess,os,hashlib
from pathlib import Path
from shapely.strtree import STRtree
from shapely.geometry import Point
src=Path(sys.argv[1]);require_complete='--require-complete' in sys.argv[2:];work=Path(os.environ.get('PRUNE_WORK','routing-work/motor-mount-revision/pruned'));work.mkdir(parents=True,exist_ok=True)
s={};old=sys.argv;sys.argv=['check-copper.py',str(src),str(work/'before.json')]
checker=Path('scripts/check-copper.py');cache_path=Path(os.environ['PRUNE_AUDIT_CACHE']) if os.environ.get('PRUNE_AUDIT_CACHE') else None
cached=json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else None
if cached and cache_path.stat().st_mtime>=checker.stat().st_mtime and cached.get('circuitJsonSha256')==hashlib.sha256(src.read_bytes()).hexdigest() and all(cached.get(k)==0 for k in ['shortCount','clearanceViolationCount','edgeViolationCount','holeViolationCount','unsupportedCount']):
 exec(compile(checker.read_text().split('# Distinct-net copper')[0],'g','exec'),s);s['report']=cached;(work/'before.json').write_text(json.dumps(cached,indent=2)+'\n');print('Reused independent input audit for unchanged copper.',flush=True)
else:
 try:exec(compile(checker.read_text(),'g','exec'),s)
 except SystemExit:pass
sys.argv=old;j=s['j'];before=s['report'];assert before['shortCount']==before['clearanceViolationCount']==0
if require_complete:assert before['status']=='passed' and before['fullyConnectedNets']==before['nets'],'Complete and audit the input routing before final cleanup.'
traces={a['pcb_trace_id']:a for a in s['bytype']['pcb_trace']};assert len(traces)==len(s['bytype']['pcb_trace']),'Duplicate trace identifiers must be resolved before pruning.'
# Routing locks and temporary signal breakouts may be pruned once their real
# terminal paths are proven. Keep local supply/ground stitches and wide copper.
def temporary_signal(identity,t):
 name=s['nets'].get(t.get('connection_name') or s['trace_net'].get(t.get('source_trace_id')),'')
 local_power={'GND','VBUS','DC_IN','V12','V5','V3V3','VDDA3V3','CP_L','CP_H','VCP','DRV_VGLS','DRV_DVDD','BUCK12_SW','BUCK5_SW','BST12','FB12','FB5','RON12','RIPPLE12','HSE_CLK','OSC8_OUT'}
 return identity.startswith('seed_') and name not in local_power and not name.startswith('SHUNT_')
fixed={identity for identity,t in traces.items() if (identity.startswith(('seed_','kelvin_','plane_stitch_')) and not identity.startswith('seed_frozen_') and not temporary_signal(identity,t)) or any(v.get('width',0)>=.6 for v in t['route'])}
manifest=json.loads(Path('data/kelvin-routing.json').read_text());protected=[]
for b in manifest['branches']:
 protected +=[(b['phase'],b['positiveSourceVia']),(b['phase'],b['positivePickupVia']),('GND',b['sourceVia']),('GND',b['pickupGroundVia'])]
keep=set();keep_pours=set();stats=[]
for net,name in s['nets'].items():
 objects=[a for a in s['items'] if a['net']==net];count=len(objects)
 if not count:continue
 tree=STRtree([a['g'] for a in objects]);adj=[[] for _ in objects];parents=list(range(count));mandatory=set();plating=collections.defaultdict(list)
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def edge(a,b):adj[a].append(b);adj[b].append(a);parents[root(b)]=root(a)
 for i,a in enumerate(objects):
  identity=a['id'].rsplit(':',1)[0]
  if a['kind']=='pad' and a.get('port'):mandatory.add(i)
  if identity in fixed:mandatory.add(i)
  if a['kind']=='via':
   plating[('via',a['id'])].append(i)
   if a['g'].bounds[2]-a['g'].bounds[0]>=.59:mandatory.add(i)
   if any((key=='GND' and name=='GND' or name=='SHUNT_'+key+'_TOP') and a['g'].centroid.distance(Point(*p))<1e-5 for key,p in protected):mandatory.add(i)
  elif a['kind']=='pad' and len(s['ports'].get(a.get('port'),{}).get('layers',[]))>1:plating[('pad',a['id'])].append(i)
  for k in tree.query(a['g'],predicate='dwithin',distance=1e-7):
   k=int(k)
   if k>i and objects[k]['layer']==a['layer']:edge(i,k)
 for nodes in plating.values():
  for i in nodes[1:]:edge(nodes[0],i)
 groups=collections.defaultdict(list)
 for i in range(count):groups[root(i)].append(i)
 # A lone SMT terminal retains one nearby through-via escape.
 for nodes in groups.values():
  pads=[i for i in nodes if objects[i]['kind']=='pad' and objects[i].get('port')]
  ports={objects[i]['port'] for i in pads}
  if len(ports)==1 and pads:
   port=s['ports'][next(iter(ports))]
   if len(port['layers'])==1:
    vias=[i for i in nodes if objects[i]['kind']=='via' and objects[i]['g'].centroid.distance(Point(port['x'],port['y']))<=3]
    if vias:mandatory.add(min(vias,key=lambda i:objects[i]['g'].centroid.distance(Point(port['x'],port['y']))))
 kept=set()
 for nodes in groups.values():
  required=[i for i in nodes if i in mandatory]
  if not required:continue
  # Keep fill regions attached to terminals or protected copper; discard
  # islands left floating by the successive clearance cuts.
  keep_pours.update(objects[i]['id'] for i in nodes if objects[i]['kind']=='pour')
  pours=[i for i in nodes if objects[i]['kind']=='pour'];start=max(pours,key=lambda i:objects[i]['g'].area) if pours else required[0]
  dist={start:0.};prev={};queue=[(0.,start)];remaining=set(required)
  while queue and remaining:
   d,i=heapq.heappop(queue)
   if d!=dist[i]:continue
   remaining.discard(i)
   for k in adj[i]:
    a=objects[k];weight=.001 if a['kind']!='track' else max(.001,a['g'].area/.15)
    nd=d+weight
    if nd<dist.get(k,float('inf')):dist[k]=nd;prev[k]=i;heapq.heappush(queue,(nd,k))
  for i in required:
   while i not in kept:
    kept.add(i)
    if i not in prev:break
    i=prev[i]
 for i in kept:keep.add(objects[i]['id'])
 stats.append({'net':name,'copperItems':count,'keptItems':len(kept)})
new=[a for a in j if a['type'] not in ['pcb_trace','pcb_via'] and (a['type']!='pcb_copper_pour' or a['pcb_copper_pour_id'] in keep_pours)]
for a in s['bytype']['pcb_via']:
 if a['pcb_via_id'] in keep:new.append(a)
for identity,t in traces.items():
 if identity in fixed:new.append(t);continue
 chunk=[];index=0
 def flush():
  global index
  if len(chunk)>1:new.append({**t,'pcb_trace_id':identity+'_pruned'+str(index),'route':list(chunk)});index+=1
  chunk.clear()
 for k,p in enumerate(t['route']):
  if p['route_type']=='via':
   flush()
   if identity+':v'+str(k) in keep:
    n=t.get('connection_name') or s['trace_net'].get(t.get('source_trace_id'));pos={'x':p['x'],'y':p['y']}
    new.append({**t,'pcb_trace_id':identity+'_barrel'+str(k),'route':[{'route_type':'wire',**pos,'layer':'top','width':.2},p,{'route_type':'wire',**pos,'layer':'bottom','width':.2}]})
  elif k and t['route'][k-1]['route_type']=='wire' and identity+':'+str(k) in keep:
   q=t['route'][k-1]
   if not chunk:chunk.append(q)
   chunk.append(p)
  else:flush()
 flush()
candidate=work/'candidate.circuit.json';candidate.write_text(json.dumps(new));subprocess.run([sys.executable,'scripts/check-copper.py',str(candidate),str(work/'after.json')],stdout=subprocess.DEVNULL,check=False);after=json.loads((work/'after.json').read_text())
def partitions(report):
 result={a['net']:[set(v) for v in a['islands']] for a in report['unconnectedNets']}
 for n,name in s['nets'].items():
  if name not in result:result[name]=[{s['portlabel'](pid) for pid in s['ports'] if s['portnet'].get(pid)==n}]
 return result
oldparts=partitions(before);newparts=partitions(after);revert={name for name,groups in oldparts.items() if any(not any(group<=b for b in newparts[name]) for group in groups)};revert_ids={n for n,name in s['nets'].items() if name in revert}
def net(a):return a.get('source_net_id') or s['trace_net'].get(a.get('source_trace_id')) or a.get('connection_name')
if revert:
 new=[a for a in new if a['type'] not in ['pcb_trace','pcb_via'] or net(a) not in revert_ids]+[a for a in j if a['type'] in ['pcb_trace','pcb_via'] and net(a) in revert_ids];candidate.write_text(json.dumps(new));subprocess.run([sys.executable,'scripts/check-copper.py',str(candidate),str(work/'after.json')],stdout=subprocess.DEVNULL,check=False);after=json.loads((work/'after.json').read_text())
assert after['shortCount']==after['clearanceViolationCount']==0
if require_complete:assert after['status']=='passed' and after['fullyConnectedNets']==before['nets'],'Final cleanup must preserve all nets and physical rules.'
report={'status':'passed','source':str(src),'candidate':str(candidate),'beforeTraces':len(s['bytype']['pcb_trace']),'afterTraces':sum(a['type']=='pcb_trace' for a in new),'beforePours':len(s['bytype']['pcb_copper_pour']),'afterPours':sum(a['type']=='pcb_copper_pour' for a in new),'revertedNets':sorted(revert),'beforeConnectedNets':before['fullyConnectedNets'],'afterConnectedNets':after['fullyConnectedNets'],'nets':stats};(work/'status.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='nets'})
