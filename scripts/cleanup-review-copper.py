"""Remove KiCad-reported stubs, retaining audited electrical and Kelvin paths."""
import json,sys,copy,subprocess
from pathlib import Path
from shapely.geometry import Point,LineString
from shapely.ops import unary_union,nearest_points
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');work=Path('routing-work/motor-mount-revision/cleanup');work.mkdir(parents=True,exist_ok=True);s={};old=sys.argv;sys.argv=['check-copper.py',str(src),str(work/'before.json')]
try:exec(compile(Path('scripts/check-copper.py').read_text(),'g','exec'),s)
except SystemExit:pass
sys.argv=old
assert s['report']['status']=='passed','Cleanups require a fully connected, clearance-clean input.'
original=s['j'];j=copy.deepcopy(original);drc=json.loads(Path('output/kicad/reports/drc.json').read_text());mapping={a['uuid']:a for a in json.loads(Path('output/kicad/track-map.json').read_text())};changes=[];guard=[];retained=[]
for b in json.loads(Path('data/kelvin-routing.json').read_text())['branches']:
 guard +=[b['sourceVia'],b['pickupGroundVia'],b['positiveSourceVia'],b['positivePickupVia']]
def net(a):return a.get('source_net_id') or s['trace_net'].get(a.get('source_trace_id')) or a.get('connection_name')
byid={a.get('pcb_trace_id'):a for a in j if a['type']=='pcb_trace'};remove=set()
for finding in drc['violations']:
 if finding['type']=='via_dangling':
  for item in finding['items']:
   x,y=item['pos']['x']-100,100-item['pos']['y']
   if any(Point(x,y).distance(Point(*p))<1e-4 for p in guard):continue
   for a in j:
    if a['type']=='pcb_via' and abs(a['x']-x)<1e-4 and abs(a['y']-y)<1e-4:
     if a['outer_diameter']>=.59:
      retained.append({'id':a['pcb_via_id'],'reason':'Preserve thermal and power-transfer barrels; electrical connectivity alone does not establish their thermal role.'});continue
     remove.add(a['pcb_via_id']);changes.append({'kind':'unused via','id':a['pcb_via_id'],'net':net(a)})
 elif finding['type']=='track_dangling':
  for item in finding['items']:
   m=mapping.get(item['uuid'])
   if not m or m['traceId'] not in byid or m['traceId'].startswith('kelvin_'):continue
   tr=byid[m['traceId']];k=m['segmentIndex'];r=tr['route']
   if k not in [1,len(r)-1]:continue
   first=k==1;a,b=(r[0],r[1]) if first else (r[-1],r[-2]);line=LineString([(a['x'],a['y']),(b['x'],b['y'])]);n=net(tr)
   other=unary_union([v['g'] for v in s['items'] if v['layer']==m['layer'] and v['net']==n and v['id']!=f"{m['traceId']}:{k}"])
   if other.covers(line.buffer(a.get('width',.15)/2)):
    if first:r.pop(0)
    else:r.pop()
   else:
    if other.distance(Point(a['x'],a['y']))<a.get('width',.15)/2+.001:continue
    intersection=line.intersection(other.buffer(-.025))
    if intersection.is_empty:continue
    p=nearest_points(Point(a['x'],a['y']),intersection)[1];a['x'],a['y']=p.x,p.y
   changes.append({'kind':'free track end','id':tr['pcb_trace_id'],'net':n})
j=[a for a in j if a.get('pcb_via_id') not in remove and not(a['type']=='pcb_trace' and len(a['route'])<2)]
candidate=work/'candidate.circuit.json';candidate.write_text(json.dumps(j));failed=set()
def run(script,report):
 subprocess.run([sys.executable,script,str(candidate),str(work/report)],stdout=subprocess.DEVNULL,check=False)
 return json.loads((work/report).read_text())
cu=run('scripts/check-copper.py','copper.json');failed.update(a['net'] for a in cu['unconnectedNets'])
power=run('scripts/check-power-backbone.py','power.json');failed.update(a['net'] for a in power['checks'] if not a['passed'])
kelvin=run('scripts/check-kelvin.py','kelvin.json')
for a in kelvin['branches']:
 if not a['passed']:failed.add('GND' if a['polarity']=='negative' else 'SHUNT_'+a['phase']+'_TOP')
failed_ids={n for n,name in s['nets'].items() if name in failed}
if failed_ids:
 j=[a for a in j if a['type'] not in ['pcb_trace','pcb_via'] or net(a) not in failed_ids]+[a for a in original if a['type'] in ['pcb_trace','pcb_via'] and net(a) in failed_ids];candidate.write_text(json.dumps(j))
 cu=run('scripts/check-copper.py','copper.json');power=run('scripts/check-power-backbone.py','power.json');kelvin=run('scripts/check-kelvin.py','kelvin.json')
assert cu['status']==power['status']==kelvin['status']=='passed','Cleanup candidate failed a required electrical check.'
accepted=[a for a in changes if a['net'] not in failed_ids]
report={'status':'passed','input':str(src),'candidate':str(candidate),'acceptedChanges':accepted,'retainedIntentionalVias':retained,'revertedNets':sorted(failed),'method':'Only reported unused signal vias and free trace ends are changed; Kelvin paths and thermal/power barrels are protected. Failed net changes are restored. Require all-net connectivity, both wide input paths, the power backbone and all six Kelvin branches afterward.'};Path('output/copper-cleanup-audit.json').write_text(json.dumps(report,indent=2)+'\n');print('Copper cleanup:',len(accepted),'accepted changes;',len(failed),'nets retained their original copper.')
