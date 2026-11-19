"""Connect repeated physical contacts externally for unambiguous PCB continuity."""
import json,sys,collections
from pathlib import Path
from shapely.geometry import LineString
src=Path(sys.argv[1]);out=Path(sys.argv[2] if len(sys.argv)>2 else 'routing-work/revision/package-pad-links.circuit.json');s={'__name__':'package_pads'};sys.argv=['check-copper.py',str(src),'/tmp/unused-package-pads.json'];exec(compile(Path('scripts/check-copper.py').read_text().split('# Distinct-net copper')[0],'package_pads','exec'),s)
j=s['j'];pc={a['pcb_component_id']:s['sources'].get(a.get('source_component_id')) for a in s['bytype']['pcb_component']};st={}
for t in j:
 if t['type']=='source_trace':
  for n in t.get('connected_source_net_ids',[]):st[n]=t['source_trace_id']
new=[];rip=set();details=[];problems=[]
for ref in ['Q'+str(i) for i in range(1,8)]+['SW1']:
 for pin in (['1','2'] if ref=='SW1' else ['2']):
  pads=[a for a in s['bytype']['pcb_smtpad'] if pc.get(a.get('pcb_component_id'))==ref and pin in a.get('port_hints',[])]
  if len(pads)!=2:raise RuntimeError(f'{ref}.{pin}: expected two physical contacts')
  a,b=pads;net=s['portnet'][a['pcb_port_id']];assert net==s['portnet'][b['pcb_port_id']] and a['layer']==b['layer'];width=.25 if ref=='SW1' else 1.5;line=LineString([(a['x'],a['y']),(b['x'],b['y'])]);g=line.buffer(width/2,quad_segs=32)
  for item in s['items']:
   if item['layer']!=a['layer'] or item['net']==net or item['kind']=='pour' or g.distance(item['g'])>=.2-1e-5:continue
   identity=item['id'].rsplit(':',1)[0]
   if identity.startswith('finish_'):rip.add(identity)
   else:problems.append((ref,pin,item['id'],s['nets'].get(item['net'])))
  identity='seed_'+str(50000+len(new));new.append({'type':'pcb_trace','pcb_trace_id':identity,'connection_name':net,'source_trace_id':st[net],'route':[{'route_type':'wire','x':p['x'],'y':p['y'],'layer':a['layer'],'width':width} for p in [a,b]]});details.append({'reference':ref,'pin':pin,'layer':a['layer'],'widthMm':width,'lengthMm':line.length})
# Dedicated short connections from the driver's ordinary GND pins to EP.
pp={}
for pid,port in s['ports'].items():
 source=s['sourceports'].get(port.get('source_port_id'),{})
 if s['sources'].get(source.get('source_component_id'))=='U2':pp.setdefault(source.get('pin_number'),port)
ep=pp[41]
for pin in [25,39]:
 a=pp[pin];net=s['portnet'][a['pcb_port_id']];middle=(-21.5,a['y']) if pin==25 else (a['x'],1.4);points=[(a['x'],a['y']),middle,(ep['x'],ep['y'])];g=LineString(points).buffer(.125,quad_segs=32)
 for item in s['items']:
  if item['layer']!='bottom' or item['net']==net or item['kind']=='pour' or g.distance(item['g'])>=.2-1e-5:continue
  identity=item['id'].rsplit(':',1)[0]
  if identity.startswith('finish_'):rip.add(identity)
  else:problems.append(('U2',str(pin),item['id'],s['nets'].get(item['net'])))
 new.append({'type':'pcb_trace','pcb_trace_id':'seed_'+str(50000+len(new)),'connection_name':net,'source_trace_id':st[net],'route':[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.25} for x,y in points]});details.append({'reference':'U2','pin':str(pin),'layer':'bottom','widthMm':.25,'lengthMm':LineString(points).length})
if problems:raise RuntimeError('Package links hit protected copper: '+repr(problems))
replace={a['pcb_trace_id'] for a in new};j=[a for a in j if a.get('pcb_trace_id') not in rip|replace]+new;out.write_text(json.dumps(j));report={'links':details,'displacedSignalRoutes':sorted(rip),'output':str(out)};Path('routing-work/revision/package-pad-links-status.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
