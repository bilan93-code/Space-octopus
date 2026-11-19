"""Merge protected wide power paths and remove only displaced signal routes."""
import json,sys
from pathlib import Path
from shapely.geometry import LineString
src=Path(sys.argv[1]);out=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/power-repaired.circuit.json');scope={'__name__':'power_merge'};sys.argv=['check-copper.py',str(src),'/tmp/unused-power-merge.json']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'power_merge','exec'),scope)
j=scope['j'];traces=json.load(open('routing-work/revision/power-bus/traces.json'));nets={v:k for k,v in scope['nets'].items()};rip=set();violations=[]
for t in traces:
 n=nets['VBUS'];t['connection_name']=n;t['source_trace_id']=next(x['source_trace_id'] for x in j if x['type']=='source_trace' and n in x.get('connected_source_net_ids',[]))
 for k,p in enumerate(t['route']):
  if not k:continue
  a=t['route'][k-1];g=LineString([(a['x'],a['y']),(p['x'],p['y'])]).buffer(p['width']/2,quad_segs=32)
  for item in scope['items']:
   if item['layer']!=p['layer'] or item['net']==n or item['kind']=='pour' or g.distance(item['g'])>=.2-1e-5:continue
   identity=item['id'].rsplit(':',1)[0]
   if identity.startswith('finish_'):rip.add(identity)
   else:violations.append((t['pcb_trace_id'],item['id'],scope['nets'].get(item['net'])))
if violations:raise RuntimeError('Power paths conflict with protected geometry: '+repr(violations))
replace={t['pcb_trace_id'] for t in traces};removed=[t for t in j if t.get('pcb_trace_id') in rip];affected=sorted({scope['nets'].get(t.get('connection_name'),'unknown') for t in removed})
j=[t for t in j if t.get('pcb_trace_id') not in rip|replace and t['type']!='pcb_copper_pour']+traces
out.write_text(json.dumps(j));report={'status':'merged','powerPaths':len(traces),'displacedSignalRoutes':len(rip),'affectedNets':affected,'output':str(out)};Path('routing-work/revision/power-merge-status.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
