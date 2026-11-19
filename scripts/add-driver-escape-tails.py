"""Preserve short phase-sense escapes through the existing QFN fanout fence."""
import json,sys
from pathlib import Path
from shapely.geometry import LineString
path=Path(sys.argv[1]);s={};old=sys.argv;sys.argv=['check-copper.py',str(path),'/tmp/tail-unused']
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'g','exec'),s);sys.argv=old
j=s['j'];new=[];bad=set()
for name,pts in [('PH_V',[(-19.25,-3.55),(-19.25,-4.5),(-24.2,-4.5)]),('PH_W',[(-20.75,-3.95),(-24.2,-3.95)])]:
 n=next(k for k,v in s['nets'].items() if v==name);g=LineString(pts).buffer(.075,quad_segs=32)
 for a in s['items']:
  if a['net']==n or a['layer']!='inner1' or a['kind']=='pour' or g.distance(a['g'])>=.2-1e-5:continue
  identity=a['id'].rsplit(':',1)[0]
  if not identity.startswith('finish_'):raise RuntimeError('Protected escape collision '+a['id'])
  bad.add(identity)
 tid=next(t['source_trace_id'] for t in s['bytype']['source_trace'] if n in t.get('connected_source_net_ids',[]))
 new.append({'type':'pcb_trace','pcb_trace_id':'seed_driver_escape_'+name,'connection_name':n,'source_trace_id':tid,'route':[{'route_type':'wire','x':x,'y':y,'layer':'inner1','width':.15} for x,y in pts]})
j=[a for a in j if a['type']!='pcb_copper_pour' and a.get('pcb_trace_id') not in bad and not a.get('pcb_trace_id','').startswith('seed_driver_escape_')]
path.write_text(json.dumps(j+new));print('Added two phase-sense escape tails; displaced',sorted(bad))
