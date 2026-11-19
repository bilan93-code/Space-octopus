"""Small independent fixtures: the copper audit must reject actual PCB faults."""
import json,math,subprocess,sys,tempfile,copy
from pathlib import Path
base=[{'type':'pcb_board','pcb_board_id':'pcb_board_0','outline':[{'x':56*math.cos(a*math.pi/16),'y':56*math.sin(a*math.pi/16)} for a in range(32)]}]
for i,(x,y,net) in enumerate([(-5,0,'A'),(5,0,'A'),(5,5,'B')]):
 base +=[{'type':'source_component','source_component_id':f'c{i}','name':f'U{i+1}'},{'type':'source_port','source_port_id':f's{i}','source_component_id':f'c{i}','pin_number':1},{'type':'source_trace','source_trace_id':f't{i}','connected_source_net_ids':[net],'connected_source_port_ids':[f's{i}']},{'type':'pcb_component','pcb_component_id':f'c{i}','source_component_id':f'c{i}'},{'type':'pcb_port','pcb_port_id':f'p{i}','source_port_id':f's{i}','x':x,'y':y,'layers':['top']},{'type':'pcb_smtpad','pcb_smtpad_id':f'pad{i}','pcb_port_id':f'p{i}','x':x,'y':y,'shape':'rect','width':1,'height':1,'layer':'top'}]
base +=[{'type':'source_net','source_net_id':n,'name':n} for n in ['A','B']]
def trace(identity,x1,y1,x2,y2):return {'type':'pcb_trace','pcb_trace_id':identity,'source_trace_id':'t0','route':[{'route_type':'wire','x':x,'y':y,'layer':'top','width':.25} for x,y in [(x1,y1),(x2,y2)]]}
baseline=base+[trace('wire',-5,0,5,0)]
with tempfile.TemporaryDirectory(prefix='octopus-copper-tests-') as d:
 def audit(name,j):
  src=Path(d)/(name+'.json');out=Path(d)/(name+'-audit.json');src.write_text(json.dumps(j))
  subprocess.run([sys.executable,'scripts/check-copper.py',str(src),str(out)],stdout=subprocess.DEVNULL,check=False)
  return json.loads(out.read_text())
 assert audit('baseline',baseline)['status']=='passed'
 assert audit('open',base)['unconnectedNetCount']==1
 assert audit('short',base+[trace('short',-5,0,5,5)])['shortCount']>0
 clearance=audit('clearance',baseline+[trace('near',-5,4.25,5,4.25)])
 assert clearance['shortCount']==0 and clearance['clearanceViolationCount']>0
 assert audit('hole',baseline+[{'type':'pcb_hole','pcb_hole_id':'hole0','x':0,'y':0,'hole_shape':'circle','hole_diameter':2}])['holeViolationCount']>0
 vias=[{'type':'pcb_via','pcb_via_id':'via'+net,'source_net_id':net,'x':0,'y':3,'outer_diameter':.6,'hole_diameter':.3,'layers':['top','inner1','inner2','bottom']} for net in ['A','B']]
 assert audit('coincident_vias',baseline+vias)['shortCount']>0
subprocess.run([sys.executable,'scripts/check-routing-priority.py'],check=True)
subprocess.run([sys.executable,'scripts/check-gerber-nesting.py'],check=True)
print('Copper mutation checks passed: clean baseline; open, short, clearance and hole faults detected; routing priorities preserved.')
