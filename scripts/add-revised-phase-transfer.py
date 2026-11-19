"""Relocate PH_U's parallel transfer barrels clear of the encoder header."""
import sys,json
from pathlib import Path
from shapely.geometry import Point,LineString
work=Path('routing-work/motor-mount-revision');path=work/'rebased.circuit.json'
s={'__name__':'phase_geometry'};sys.argv=['check-copper.py',str(path),str(work/'unused.json')]
exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'geometry','exec'),s)
j=s['j'];n=next(k for k,v in s['nets'].items() if v=='PH_U');tid=next(t['source_trace_id'] for t in j if t['type']=='source_trace' and n in t.get('connected_source_net_ids',[]));new=[];geometries=[]
def wire(pts,layer,width):
 new.append({'type':'pcb_trace','pcb_trace_id':'seed_mount_phase_'+str(len(new)),'connection_name':n,'source_trace_id':tid,'route':[{'route_type':'wire','x':x,'y':y,'layer':layer,'width':width} for x,y in pts]});geometries.append((LineString(pts).buffer(width/2,quad_segs=32),layer))
for x in [-18.4]:
 for y in [17.3,18.0,18.7,19.4,20.1,20.8,21.5,22.2]:
  new.append({'type':'pcb_trace','pcb_trace_id':'seed_mount_phase_'+str(len(new)),'connection_name':n,'source_trace_id':tid,'route':[{'route_type':'wire','x':x,'y':y,'layer':'top','width':.2},{'route_type':'via','x':x,'y':y,'layers':s['layers'],'from_layer':'top','to_layer':'bottom','via_diameter':.8,'via_hole_diameter':.4},{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.2}]})
  geometries.extend((Point(x,y).buffer(.4,quad_segs=32),l) for l in s['layers'])
wire([(-14.775,19.46),(-18.4,19.46)],'top',3)
wire([(-14.775,21.6),(-18.4,21.6)],'bottom',2)
for l in ['top','bottom']:wire([(-18.4,17.3),(-18.4,21.5)],l,2)
bad=set();pads=[]
for a in s['items']:
 if a['net']==n:continue
 if any(l==a['layer'] and g.distance(a['g'])<.2-1e-5 for g,l in geometries):
  if a['kind']=='pad':pads.append((a['id'],s['portlabel'](a.get('port'))))
  else:bad.add(a['id'].rsplit(':',1)[0])
if pads:raise RuntimeError('Transfer interferes with pads: '+str(pads))
if any(b.startswith('kelvin_') for b in bad):raise RuntimeError('Transfer interferes with Kelvin pickup')
j=[a for a in j if a.get('pcb_trace_id') not in bad and not a.get('pcb_trace_id','').startswith('seed_mount_phase_')]
path.write_text(json.dumps(j+new));print('Relocated 8 parallel phase barrels; displaced',len(bad),'routes.')
