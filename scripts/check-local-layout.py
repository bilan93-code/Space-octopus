"""Measure converter, bypass and ADC placements from captured PCB ports."""
import json,sys,re,math
from pathlib import Path
src=Path(sys.argv[1] if len(sys.argv)>1 else 'output/space-octopus.circuit.json');j=json.loads(src.read_text());parts=sum([json.loads(Path('data/'+n+'.json').read_text()) for n in ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake']],[]);by={p['ref']:p for p in parts}
sc={e['source_component_id']:e['name'] for e in j if e['type']=='source_component'};sp={e['source_port_id']:e for e in j if e['type']=='source_port'};ports={}
for e in j:
 if e['type']!='pcb_port' or e.get('source_port_id') not in sp:continue
 s=sp[e['source_port_id']];ref=sc.get(s.get('source_component_id'));pin=s.get('pin_number',next((int(h.removeprefix('pin')) for h in s.get('port_hints',[]) if h.removeprefix('pin').isdigit()),None))
 if pin is not None:ports.setdefault((ref,str(pin)),(e['x'],e['y']))
checks=[]
def check(label,a,b,limit):
 d=math.dist(ports[a],ports[b]);checks.append({'check':label,'from':'.'.join(a),'to':'.'.join(b),'distanceMm':round(d,3),'limitMm':limit,'passed':d<=limit})
for label,a,b,limit in [('12V switch',('U3','8'),('L101','1'),6),('5V switch',('U4','7'),('L102','1'),6),('Bootstrap',('U3','7'),('C105','1'),3.5),('Bootstrap return',('U3','8'),('C105','2'),3.5),('12V input bypass',('U3','2'),('C101','1'),4.5),('5V input bypass',('U4','2'),('C108','1'),4),('LDO input',('U5','3'),('C110','1'),3.5),('LDO output',('U5','5'),('C111','1'),3.5),('Reference output',('U19','2'),('C113','1'),3.5),('Driver V12 bypass',('U2','3'),('C302','1'),2.5),('Flying capacitor CP_L',('U2','1'),('C303','1'),5),('Flying capacitor CP_H',('U2','2'),('C303','2'),5)]:check(label,a,b,limit)
check('Brake local bypass',('Q7','3'),('C905','2'),7)
check('Driver VREF bypass',('U2','24'),('C307','1'),5)
for cap,pin in [('C201','16'),('C202','32'),('C203','48'),('C204','64')]:check('MCU VDD bypass',('U1',pin),(cap,'1'),2)
for cap,pin in [('C501','12'),('C502','13'),('C503','14'),('C504','8'),('C511','11')]:check('ADC charge reservoir',('U1',pin),(cap,'1'),5)
for p in parts:
 if p['kind']!='capacitor' or 'bypass' not in p.get('notes','').lower():continue
 m=re.search(r'(?:at|nearest) (U\d+)',p['notes'])
 if not m:continue
 ref=m[1];rail=p['pins']['1'];pins=[pin for pin,n in by[ref]['pins'].items() if n==rail];typed=[pin for pin in pins if re.search(r'VCC|VDD|VIO|VIN|V\+',by[ref]['pinLabels'].get(pin,''))];pins=typed or pins
 if pins:
  closest=min(pins,key=lambda pin:math.dist(ports[(ref,pin)],ports[(p['ref'],'1')]))
  check('Named local bypass',(ref,closest),(p['ref'],'1'),5)
report={'status':'passed' if all(c['passed'] for c in checks) else 'failed','source':str(src),'checks':checks,'limitations':'Placement distance checks do not establish loop inductance, converter stability, effective capacitance or EMC compliance.'};Path('output/local-layout-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('Local layout:',report['status'],len(checks),'checks')
for c in checks:
 if not c['passed']:print(c)
raise SystemExit(report['status']!='passed')
