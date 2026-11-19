import fs from 'node:fs';
import assert from 'node:assert/strict';
import {audit} from './check-design.mjs';
const read=p=>JSON.parse(fs.readFileSync(p));
const components=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical','external-parts'].flatMap(n=>read(`data/${n}.json`));
const catalog=read('footprints/catalog.json');
assert.equal(audit({components,catalog}).status,'passed');
const cases=[
 ['Cartridge holder substituted for the soldered input fuse',p=>p('F1').holder={mpn:'0031.8002'},'assembly.F1.axial-fuse'],
 ['Input fuse fitted in the brake position',p=>p('F2').mpn=p('F1').mpn,'assembly.F2.axial-fuse'],
 ['Grounded charge-pump reservoir',p=>p('C304').pins['2']='GND','connection.C304'],
 ['Reversed current comparator',p=>{[p('U7').pins['4'],p('U7').pins['5']]=[p('U7').pins['5'],p('U7').pins['4']]},'comparator.U-low.polarity'],
 ['Bypassed driver SPI resistor',p=>p('U2').pins['29']=p('U1').pins['52'],'driver.spi.SCK'],
 ['Wrong low-side source',p=>p('Q2').pins['3']='GND','pin.Q2.3'],
 ['Missing driver thermal pad',p=>delete p('U2').pins['41'],'package.U2.pins'],
 ['Wrong encoder power pin',p=>p('J4').pins['1']='VBUS','pin.J4.1'],
 ['Reversed fault diode',p=>{[p('D10').pins['1'],p('D10').pins['2']]=[p('D10').pins['2'],p('D10').pins['1']]},'fault.D10.polarity'],
 ['Missing disabled-PWM pulldown',p=>p('R307').pins['2']='V3V3','connection.R307'],
 ['Wrong bus divider value',p=>p('R506').value='100 kohm','threshold.bus'],
];
for(const [name,mutate,expected] of cases){
 const clone=structuredClone(components);const part=ref=>clone.find(p=>p.ref===ref);mutate(part);
 const report=audit({components:clone,catalog});
 assert(report.checks.some(c=>c.id===expected&&c.status==='failed'),`${name}: audit did not detect the injected error`);
}
console.log(`Mutation checks: ${cases.length} electrical faults detected.`);
