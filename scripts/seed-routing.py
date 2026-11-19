"""Explicit fine-pitch escapes and thermal vias before the local detailed router."""
import json,sys,math
from pathlib import Path
j=[a for a in json.loads(Path('output/space-octopus.circuit.json').read_text()) if a['type']!='cad_component'];placement=json.loads(Path('data/placement.json').read_text())
src={a['source_component_id']:a['name'] for a in j if a['type']=='source_component'}
sp={a['source_port_id']:a for a in j if a['type']=='source_port'}
net={};st={}
for a in j:
 if a['type']=='source_trace' and len(a.get('connected_source_net_ids',[]))==1:
  n=a['connected_source_net_ids'][0];st[n]=a['source_trace_id']
  for p in a.get('connected_source_port_ids',[]):net[p]=n
routes=[]
def trace(n,pts,layer='bottom',width=.15):
 a={'type':'pcb_trace','pcb_trace_id':'seed_'+str(len(routes)),'source_trace_id':st[n],'connection_name':n,'route':[{'route_type':'wire','x':x,'y':y,'layer':layer,'width':width} for x,y in pts]};routes.append(a);return a

def via(n,x,y,d=.4,h=.2):
 a=trace(n,[(x,y)],'bottom');a['route'] += [{'route_type':'via','x':x,'y':y,'from_layer':'bottom','to_layer':'top','layers':['top','inner1','inner2','bottom'],'via_diameter':d,'via_hole_diameter':h},{'route_type':'wire','x':x,'y':y,'layer':'top','width':.15}]

for a in j:
 if a['type']!='pcb_port' or a.get('source_port_id') not in net:continue
 p=sp[a['source_port_id']];ref=src.get(p['source_component_id']);pin=p['pin_number']
 if ref not in ['U1','U2']:continue
 n=net[a['source_port_id']];cx,cy=placement[ref]['bodyCenter'];x,y=a['x'],a['y'];dx,dy=x-cx,y-cy
 if ref=='U2' and pin==41:
  for xx in [-.8,0,.8]:
   for yy in [-.8,0,.8]:via(n,cx+xx,cy+yy,.6,.3)
  continue
 # Dedicated shunt positive/negative Kelvin pins are routed as branches later.
 if ref=='U2' and pin in [9,10,11,12,19,20]:continue
 shift=(1.325 if pin%2 else -1.325) if ref=='U1' else (1.05 if pin%2 else 2.05)
 if abs(dx)>abs(dy):vx=x+math.copysign(1,dx)*shift;vy=y
 else:vx=x;vy=y+math.copysign(1,dy)*shift
 trace(n,[(x,y),(vx,vy)]);via(n,vx,vy)

Path('routing-work/revision').mkdir(parents=True,exist_ok=True)
Path('routing-work/revision/seed.circuit.json').write_text(json.dumps([a for a in j if a['type'] not in ['pcb_trace','pcb_via','pcb_copper_pour'] and 'error' not in a['type']]+routes))
print('Protected fanout/thermal traces:',len(routes))
# High-current backbones use wide outer copper. Fine signal escape geometry
# remains independent, so motor current never relies on a .15-mm logic track.
pp={}
for a in j:
 if a['type']=='pcb_port' and a.get('source_port_id') in sp:
  p=sp[a['source_port_id']];pp[(src.get(p['source_component_id']),p.get('pin_number',next((int(v.removeprefix('pin')) for v in p.get('port_hints',[]) if v.removeprefix('pin').isdigit()),None)))]=a
names={a['name']:a['source_net_id'] for a in j if a['type']=='source_net'}
def pos(ref,pin):a=pp[(ref,pin)];return (a['x'],a['y'])
def power(name,pts,layer='top',w=4):return trace(names[name],pts,layer,w)
def array(name,xs,ys):
 for x in xs:
  for y in ys:via(names[name],x,y,.8,.4)

# Main input positive: both outside layers, joined by the input/fuse barrels.
for face in ['top','bottom']:
 power('DC_IN',[pos('J1',1),(-43,0),(-30.5,0),(-30.5,39),pos('F1',1)],face,6.5)
# The high-side drain goes to the VBUS reference plane through parallel barrels,
# kept outside the opposite-face phase tabs.
array('VBUS',[0],[18+i*.8 for i in range(11)])
power('VBUS',[(-5.625,22),(5.625,22)],'top',4)
array('VBUS',[-9.4],[-19-i*.8 for i in range(9)])
power('VBUS',[(-3.375,-22),(-9.4,-22)],'top',2.4)
# Source/drain bridge connections are local, with eight vias per phase node.
for name,high,low,xs,ys in [('PH_U','Q1','Q2',[-20.5,-19.6],[28.4,29.1,29.8,30.5]),('PH_V','Q3','Q4',[19.5,20.4],[28.4,29.1,29.8,30.5]),('PH_W','Q5','Q6',[10.5,11.4],[-28.4,-29.1,-29.8,-30.5])]:
 array(name,xs,ys);c=(sum(xs)/2,sum(ys)/len(ys))
 power(name,[pos(high,3),(c[0],pos(high,3)[1]),c],'top',3)
 power(name,[pos(low,2),(pos(low,2)[0],c[1]),c],'bottom',3)
 # Stitch all barrels together, rather than counting isolated same-net vias.
 for face in ['top','bottom']:
  power(name,[(xs[0],ys[0]),(xs[-1],ys[-1])],face,2)
# Three motor phase leads have separate outer-layer paths and 3-mm necks at
# the bulk-capacitor pin gap. Peak current capability still needs thermal test.
power('PH_U',[(-5.625,22),(-5.625,33.79),(37.9,33.79),(37.9,18.2)],'bottom',4)
power('PH_U',[(37.9,18.2),(40.4,18.2),(40.4,10.7),(42,10.7),pos('J2',1)],'bottom',3)
power('PH_V',[(19.95,29.45),(23,29.45),(23,10.7),(42,10.7)],'top',3)
power('PH_V',[(42,10.7),(43.5,10.7),(43.5,0),pos('J2',2)],'top',3)
power('PH_W',[(10.95,-29.45),(22,-29.45),(22,-18.2),(47,-18.2),pos('J2',3)],'top',4)
# Low-side sources terminate on their own 1-milliohm shunt before GND.
for i,q in enumerate(['Q2','Q4','Q6'],1):power('SHUNT_'+['U','V','W'][i-1]+'_TOP',[pos(q,3),pos('RSH'+str(i),1)],'bottom',3)
for i,x,y in [(1,-24.1,28),(2,28,16),(3,19,-22.5)]:
 array('GND',[x-.4,x+.4],[y-.7,y,y+.7]);power('GND',[pos('RSH'+str(i),2),(x,y)],'bottom',3)
# Brake device drain transfer and return.
array('BRAKE_DRAIN',[-17.5,-16.7],[-30,-30.7,-31.4]);power('BRAKE_DRAIN',[pos('Q7',2),(-17.1,-30.7)],'top',3)
power('BRAKE_DRAIN',[(-17.1,-30.7),(-14.8,-30.7),(-14.8,-33.8),(pos('J11',2)[0],-33.8),pos('J11',2)],'bottom',3.6)
power('BRAKE_PLUS',[pos('F2',2),(21,-39),(35.085,-39),pos('J11',1)],'top',4)
array('GND',[-30.5,-29.7],[-24,-24.7,-25.4]);power('GND',[pos('Q7',3),(-30.1,pos('Q7',3)[1]),(-30.1,-24.7)],'top',3)
# The flyback diode has separate wide paths on the two outer faces.
power('BRAKE_PLUS',[pos('D2',1),(18.75,-43),pos('F2',2)],'top',3.6)
power('BRAKE_DRAIN',[pos('D2',2),(24.925,-43),pos('J11',2)],'bottom',3.6)
# Compact converter cells and local bypass connections are fixed before
# routing the remaining logic. Filled/capped vias provide reference access.
def local(name,pts,face='top',w=.25):return power(name,pts,face,w)
local('BUCK12_SW',[pos('U3',8),pos('L101',1)],w=.8)
local('BUCK12_SW',[pos('U3',8),pos('C105',2)],w=.25)
local('BST12',[pos('U3',7),pos('C105',1)],w=.25)
for pin in [2,3]:local('VBUS',[pos('U3',pin),pos('C101',1)],w=.5)
via(names['VBUS'],37.3,36.4,.6,.3)
local('VBUS',[pos('C101',1),(37.3,36.4)],w=.4)
via(names['VBUS'],*pos('C102',1),.6,.3)
# The output capacitor is directly beneath the inductor output electrode.
via(names['V12'],*pos('C103',1),.8,.4)
local('V12',[pos('L101',2),pos('C103',1)],w=.8)
local('V12',[pos('C103',1),pos('C104',1)],'bottom',.8)
via(names['GND'],27.9,22.75)
local('GND',[pos('C103',2),(27.9,22.75)],'bottom',.4)
# A thermal array spreads regulator losses into the GND reference copper.
ep=pos('U3',9)
for dx in [-.65,0,.65]:
 for dy in [-.8,0,.8]:via(names['GND'],ep[0]+dx,ep[1]+dy,.6,.3)
local('BUCK5_SW',[pos('U4',7),(25.9,pos('U4',7)[1])],'bottom',.25)
local('BUCK5_SW',[(25.9,pos('U4',7)[1]),pos('L102',1)],'bottom',.8)
local('V5',[pos('L102',2),pos('C109',1)],'bottom',.8)
via(names['V5'],25.6,12.65)
via(names['V5'],pos('L102',2)[0],12.65)
local('V5',[pos('U4',6),(25.6,pos('U4',6)[1]),(25.6,12.65)],'bottom',.15)
local('V5',[(25.6,12.65),(pos('L102',2)[0],12.65)],w=.15)
local('V5',[(pos('L102',2)[0],12.65),pos('L102',2)],'bottom',.15)
for pin in [2,3]:local('V12',[pos('U4',pin),pos('C108',1)],'bottom',.4)
# LDO input/output bypass loops.
local('V5',[pos('U5',3),pos('C110',1)],w=.3)
local('V5',[pos('U5',1),(22.55,pos('U5',1)[1]),(22.55,pos('U5',3)[1]),pos('U5',3)],w=.25)
local('V3V3',[pos('U5',5),pos('C111',1)],w=.4)
via(names['GND'],26.35,3)
local('GND',[pos('C110',2),(26.35,3)],w=.25)
# Four separate MCU VDD bypasses and the analogue bypass/filter.
local('V3V3',[pos('C201',1),(26.35,-3.75)],w=.15)
local('GND',[pos('C201',2),(29,-3.25)],w=.15)
local('V3V3',[pos('C202',1),(18.25,-4.35)],w=.15)
local('GND',[pos('C202',2),(18.75,-7)],w=.15)
local('V3V3',[pos('C204',1),(25.75,4.35)],w=.15)
local('GND',[pos('C204',2),(25.25,7)],w=.15)
local('V3V3',[pos('C203',1),(17.65,3.75)],w=.15)
local('GND',[pos('C203',2),(15,3.25)],w=.15)
local('VDDA3V3',[pos('C207',1),(20.25,-4.35)],w=.15)
local('GND',[pos('C207',2),(20.75,-7)],w=.15)
local('VDDA3V3',[pos('FB201',2),pos('C206',1)],w=.25)
# The precision reference has its own short input/output bypass connections.
via(names['V5'],*pos('C112',1))
local('V5',[pos('U19',1),(pos('U19',1)[0],-7.8),(26.5,-7.8),pos('C112',1)],w=.25)
local('REF25',[pos('U19',2),pos('C113',1)],w=.25)
# ADC charge reservoirs sit beside the corresponding MCU input fanouts.
local('IU_ADC',[pos('C501',1),(26.35,-1.75)],w=.15)
local('IV_ADC',[pos('C502',1),(25.8,1),(27.2,1),(28.3,-2.25),(29,-2.25)],w=.15)
local('IW_ADC',[pos('C503',1),(24.9,-2.6),(26.35,-2.75)],w=.15)
via(names['GND'],21.75,-3.5)
local('GND',[pos('C503',2),(21.75,pos('C503',2)[1]),(21.75,-3.5)],w=.15)
local('VBUS_SENSE',[pos('U1',8),(29.575,pos('U1',8)[1]),(29.575,pos('C504',1)[1]),pos('C504',1)],'bottom',.15)
local('REF25_MON',[pos('U1',11),(29.6,pos('U1',11)[1]),pos('C511',1)],'bottom',.15)
# CAN supply bypasses have independent local paths.
local('V5',[pos('U6',3),pos('C705',1)],'bottom',.25)
local('V3V3',[pos('U6',5),pos('C706',1)],'bottom',.25)
local('V5',[pos('C705',1),(41.2,pos('C705',1)[1]),(41.2,pos('C707',1)[1]),pos('C707',1)],'bottom',.25)
via(names['GND'],42.3,-2)
local('GND',[pos('C705',2),(42.3,-2)],'bottom',.25)
# Gate-driver charge pump and supply bypasses.
local('V12',[pos('C302',1),(-16,1.25)],w=.25)
local('CP_L',[pos('C303',1),(-16,2.25)],w=.2)
local('CP_H',[pos('C303',2),(-15,1.75)],w=.2)
via(names['VCP'],*pos('C304',1))
via(names['VBUS'],*pos('C304',2))
local('VCP',[(-16,.25),(-17.25,-.5),(-17.25,-6.5),pos('C304',1)],w=.15)
local('VDDA3V3',[pos('C307',1),(-25,-.75)],w=.15)
via(names['V3V3'],-16.65,-9.2)
local('V3V3',[pos('C512',1),(-16.65,-9.2)],w=.15)
local('V3V3',[(-16.65,-9.2),pos('U7',3)],'bottom',.15)
for pin,name in [(1,'VBUS'),(2,'GND')]:
 for dy in [-.4,.4]:via(names[name],pos('C905',pin)[0],pos('C905',pin)[1]+dy,.6,.3)
# An additional source escape avoids the driver fanout fence. The watchdog's
# configuration pin is enclosed by its two local supply paths on the bottom.
local('PH_W',[pos('U2',17),(-20.75,-5.7)],'bottom',.15)
via(names['PH_W'],-20.75,-5.7)
via(names['WDT_CWD'],*pos('U13',2))
# Join repeated package contacts on the PCB as well as in the device model.
# This gives the reset capacitor a direct ground path, independent of the
# pushbutton's internal common contact, and joins MOSFET drain leads to tabs.
component_refs={a['pcb_component_id']:src.get(a.get('source_component_id')) for a in j if a['type']=='pcb_component'}
port_lookup={a['pcb_port_id']:a for a in j if a['type']=='pcb_port'}
for ref in ['Q'+str(i) for i in range(1,8)]+['SW1']:
 for pin in (['1','2'] if ref=='SW1' else ['2']):
  pads=[a for a in j if a['type']=='pcb_smtpad' and component_refs.get(a.get('pcb_component_id'))==ref and pin in a.get('port_hints',[])]
  if len(pads)!=2:raise RuntimeError(f'{ref}.{pin}: repeated physical contacts changed')
  n=net[port_lookup[pads[0]['pcb_port_id']]['source_port_id']]
  trace(n,[(a['x'],a['y']) for a in pads],pads[0]['layer'],.25 if ref=='SW1' else 1.5)
local('GND',[pos('U2',25),(-21.5,pos('U2',25)[1]),pos('U2',41)],'bottom',.25)
local('GND',[pos('U2',39),(pos('U2',39)[0],1.4),pos('U2',41)],'bottom',.25)
local('LED_FAULT',[pos('U1',24),(22.25,-7.45),(21.95,-7.675)],'bottom',.15)
via(names['LED_FAULT'],21.95,-7.675)
clock=pos('U18',7);clock_via=(clock[0]+3,clock[1]-1.5)
local('ENC_CLK_N',[clock,(clock_via[0],clock[1]),clock_via],'bottom',.15)
via(names['ENC_CLK_N'],*clock_via)
Path('routing-work/revision/seed.circuit.json').write_text(json.dumps([a for a in j if a['type'] not in ['pcb_trace','pcb_via','pcb_copper_pour'] and 'error' not in a['type']]+routes))
print('Seeded fanouts, power straps and via arrays:',len(routes))
