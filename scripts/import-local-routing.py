"""Return a local routing session to the tscircuit source. Does not edit KiCad.
Uses pcbnew only as a Specctra session reader; source connectivity is retained.
"""
import json,sys
from pathlib import Path
import pcbnew as p
src=sys.argv[1] if len(sys.argv)>1 else 'routing-work/recovered.kicad_pcb'
out=sys.argv[2] if len(sys.argv)>2 else 'routing-work/recovered-traces.json'
j=json.loads(Path('output/space-octopus.circuit.json').read_text())
netids={x['name']:x['source_net_id'] for x in j if x['type']=='source_net'}
b=p.LoadBoard(src);layers={p.F_Cu:'top',p.In1_Cu:'inner1',p.In2_Cu:'inner2',p.B_Cu:'bottom'};traces=[]
def xy(pos):return {'x':p.ToMM(pos.x)-100,'y':100-p.ToMM(pos.y)}
for i,t in enumerate(b.GetTracks()):
 name=t.GetNetname()
 if name not in netids:raise ValueError('Unrecognized net '+name)
 if isinstance(t,p.PCB_VIA):
  pos=xy(t.GetPosition());route=[{'route_type':'wire',**pos,'width':.2,'layer':'top'},{'route_type':'via',**pos,'from_layer':'top','to_layer':'bottom','via_diameter':p.ToMM(t.GetWidth(p.F_Cu)),'via_hole_diameter':p.ToMM(t.GetDrill()),'layers':['top','inner1','inner2','bottom']},{'route_type':'wire',**pos,'width':.2,'layer':'bottom'}]
 else:route=[{'route_type':'wire',**xy(v),'width':p.ToMM(t.GetWidth()),'layer':layers[t.GetLayer()]} for v in [t.GetStart(),t.GetEnd()]]
 traces.append({'type':'pcb_trace','pcb_trace_id':f'local_{i}','connection_name':netids[name],'route':route})
Path(out).write_text(json.dumps(traces,indent=2)+'\n')
Path('routing-work/recovered.circuit.json').write_text(json.dumps([x for x in j if x['type'] not in ['pcb_trace','pcb_via']]+traces))
print(f'Imported {len(traces)} copper items into tscircuit route format.')
