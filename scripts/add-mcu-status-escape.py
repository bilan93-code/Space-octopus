"""Give the crowded MCU status output a second outward escape."""
import json,sys,math
from pathlib import Path
from shapely.geometry import Point,LineString
src=Path(sys.argv[1]);out=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/mcu-status-escape.circuit.json');s={'__name__':'mcu_escape'};sys.argv=['check-copper.py',str(src),'/tmp/unused-mcu-escape.json'];exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'mcu_escape','exec'),s)
j=s['j'];port=next(p for p in s['ports'].values() if s['sources'].get(s['sourceports'].get(p.get('source_port_id'),{}).get('source_component_id'))=='U1' and s['sourceports'][p['source_port_id']].get('pin_number')==24);net=s['portnet'][port['pcb_port_id']];drills=[]
for a in j:
 if a['type']=='pcb_trace':drills.extend((v['x'],v['y'],v.get('via_hole_diameter',.3)/2) for v in a['route'] if v['route_type']=='via')
 elif a['type'] in ['pcb_via','pcb_plated_hole','pcb_hole'] and 'hole_diameter' in a:drills.append((a['x'],a['y'],a['hole_diameter']/2))
options=[];fail=[]
for length,shift in [(r,d) for r in [1.6,1.7,1.8,1.9,2.,2.1,2.2,2.3,2.4,2.5,2.6,2.8,3.] for d in [0,-.2,.2,-.3,.3,-.4,.4]]:
 x,y=port['x']+shift,port['y']-length;via=Point(x,y).buffer(.2,quad_segs=32);points=[(port['x'],port['y']),(port['x'],-7.45),(x,y)] if shift else [(port['x'],port['y']),(x,y)];wire=LineString(points).buffer(.075,quad_segs=32)
 if any(math.hypot(x-a,y-b)<r+.1+.2-1e-5 for a,b,r in drills):continue
 hits=[a for a in s['items'] if a['net']!=net and a['kind']!='pour' and (a['g'].distance(via)<.2-1e-5 or a['layer']=='bottom' and a['g'].distance(wire)<.2-1e-5)];rip={a['id'].rsplit(':',1)[0] for a in hits}
 if any(not identity.startswith('finish_') for identity in rip):fail.append((length,sorted(rip)));continue
 options.append((len(rip),length+abs(shift),x,y,rip,points))
if not options:raise RuntimeError('No clear MCU escape: '+repr(fail))
_,length,x,y,rip,points=min(options,key=lambda c:c[:2]);st=next(a['source_trace_id'] for a in j if a['type']=='source_trace' and net in a.get('connected_source_net_ids',[]));route=[*[{'route_type':'wire','x':a,'y':b,'layer':'bottom','width':.15} for a,b in points],{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'top','layers':s['layers'],'via_diameter':.4,'via_hole_diameter':.2},{'route_type':'wire','x':x,'y':y,'layer':'top','width':.15}];j=[a for a in j if a.get('pcb_trace_id') not in rip and a.get('pcb_trace_id')!='seed_60000']+[{'type':'pcb_trace','pcb_trace_id':'seed_60000','source_trace_id':st,'connection_name':net,'route':route}];out.write_text(json.dumps(j));print(json.dumps({'escapeLengthMm':LineString(points).length,'via':[x,y],'displacedRoutes':sorted(rip),'output':str(out)},indent=2))
