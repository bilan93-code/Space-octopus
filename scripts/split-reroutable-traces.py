"""Preserve signal copper while giving rip-up repairs smaller editable sections."""
import json,sys,copy,hashlib
from pathlib import Path

src,dst=map(Path,sys.argv[1:3]);j=json.loads(src.read_text())
include_references='--include-narrow-references' in sys.argv[3:]
names={a['source_net_id']:a['name'] for a in j if a['type']=='source_net'}
trace_net={a['source_trace_id']:a['connected_source_net_ids'][0] for a in j if a['type']=='source_trace' and len(a.get('connected_source_net_ids',[]))==1}
supplies={'GND','VBUS','DC_IN','V12','V5','V3V3','VDDA3V3','CP_L','CP_H','VCP','DRV_VGLS','DRV_DVDD','BUCK12_SW','BUCK5_SW','BST12','FB12','FB5','RON12','RIPPLE12','HSE_CLK','OSC8_OUT'}
out=[];split=0
for a in j:
 identity=a.get('pcb_trace_id','');net=a.get('connection_name') or trace_net.get(a.get('source_trace_id'));name=names.get(net,'')
 ordinary=(identity.startswith('finish_') or identity.startswith('seed_frozen_') and '_finish_' in identity) and '_saved_pcb_via_' not in identity
 reference_fixed=name in supplies and (not include_references or name in ['HSE_CLK','OSC8_OUT'])
 if a['type']!='pcb_trace' or not ordinary or reference_fixed or name.startswith('SHUNT_') or len(a['route'])<=3 or any(p.get('width',0)>=.6 or p.get('route_type')=='via' and p.get('outer_diameter',p.get('via_diameter',.6))>=.59 for p in a['route']):
  out.append(a);continue
 split+=1
 assert net in names,'A split signal must retain its electrical net.'
 for k,p in enumerate(a['route']):
  if p['route_type']=='via':
   # A separate barrel retains the same through-hole copper and drill.
   out.append({'type':'pcb_via','pcb_via_id':identity+'_section_via_'+str(k),'source_net_id':net,'x':p['x'],'y':p['y'],'outer_diameter':p.get('outer_diameter',p.get('via_diameter',.6)),'hole_diameter':p.get('hole_diameter',p.get('via_hole_diameter',.3)),'layers':['top','inner1','inner2','bottom']})
  if k:
   q=a['route'][k-1];layer=p.get('layer') or q.get('layer')
   if layer is None:continue
   if q['route_type']==p['route_type']=='wire':assert q['layer']==p['layer']
   width=p.get('width',q.get('width',.25))
   route=[{'route_type':'wire','x':v['x'],'y':v['y'],'layer':layer,'width':width} for v in [q,p]]
   out.append({**a,'pcb_trace_id':identity+'_section_wire_'+str(k),'route':route})
ids=[a.get('pcb_trace_id',a.get('pcb_via_id')) for a in out if a['type'] in ['pcb_trace','pcb_via']]
assert len(ids)==len(set(ids)),'Copper identities must remain unique.'
dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(json.dumps(out))
report={'source':str(src),'output':str(dst),'sourceSha256':hashlib.sha256(src.read_bytes()).hexdigest(),'outputSha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'splitSignalRoutes':split,'beforeCopperObjects':sum(a['type'] in ['pcb_trace','pcb_via'] for a in j),'afterCopperObjects':len(ids),'verification':'Run independent copper and connectivity checks before routing this representation.'}
dst.with_suffix('.split.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
