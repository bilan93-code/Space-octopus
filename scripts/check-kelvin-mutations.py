"""Same-net faults must fail Kelvin isolation even when copper DRC is clean."""
import json,sys,subprocess,tempfile,copy,math
from pathlib import Path
src=Path('routing-work/revision/complete-native.circuit.json')
if len(sys.argv)>1:src=Path(sys.argv[1])
base=json.loads(src.read_text());manifest=json.loads(Path('data/kelvin-routing.json').read_text());net={a['name']:a['source_net_id'] for a in base if a['type']=='source_net'}
with tempfile.TemporaryDirectory(prefix='octopus-kelvin-') as folder:
 def audit(name,j):
  f=Path(folder)/(name+'.json');o=Path(folder)/(name+'-audit.json');f.write_text(json.dumps(j));r=subprocess.run([sys.executable,'scripts/check-kelvin.py',str(f),str(o)],stdout=subprocess.DEVNULL,check=False)
  return json.loads(o.read_text())
 assert audit('baseline',base)['status']=='passed'
 p=manifest['branches'][0]['isolateFromGroundPlaneAt'][0];points=[{'x':p['x']+.62*math.cos(a*math.pi/32),'y':p['y']+.62*math.sin(a*math.pi/32)} for a in range(64)]
 wrong_ground=base+[{'type':'pcb_copper_pour','pcb_copper_pour_id':'fault_ground_shortcut','source_net_id':net['GND'],'layer':'inner1','shape':'polygon','points':points}]
 report=audit('early_ground_connection',wrong_ground)
 assert any(b['phase']=='U' and b['polarity']=='negative' and not b['passed'] and b['planeConnectedBeforePickup'] for b in report['branches'])
 route=[{'route_type':'wire','x':x,'y':y,'layer':'bottom','width':.15} for x,y in [(8.85,-26.5),(5.775,-24.54)]]
 wrong_power=base+[{'type':'pcb_trace','pcb_trace_id':'fault_positive_pickup','connection_name':net['SHUNT_W_TOP'],'route':route}]
 report=audit('motor_current_pickup',wrong_power)
 assert any(b['phase']=='W' and b['polarity']=='positive' and not b['passed'] for b in report['branches'])
 p=next(b for b in manifest['branches'] if b['phase']=='W')['sourceVia']
 missing_barrel=[a for a in base if not(a['type']=='pcb_via' and math.hypot(a['x']-p[0],a['y']-p[1])<1e-5)]
 assert len(missing_barrel)==len(base)-1,'Expected one native W-negative pickup barrel.'
 report=audit('missing_pickup_barrel',missing_barrel)
 assert any(b['phase']=='W' and b['polarity']=='negative' and not b['passed'] and not b['connectedToPickup'] for b in report['branches'])
print('Kelvin mutations passed: early ground join, motor-current pickup and missing pickup barrel were detected.')
