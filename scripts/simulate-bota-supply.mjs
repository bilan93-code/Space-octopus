import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {Simulation} from 'eecircuit-engine';

const input=process.argv[2]??'output/space-octopus.circuit.json';
const bytes=fs.readFileSync(input),circuit=JSON.parse(bytes);
const parts=Object.fromEntries(circuit.filter(p=>p.type==='source_component').map(p=>[p.name,p]));
const nets=Object.fromEntries(circuit.filter(n=>n.type==='source_net').map(n=>[n.source_net_id,n.name]));
const portNet=new Map();
for(const t of circuit.filter(t=>t.type==='source_trace' && t.connected_source_net_ids.length===1)){
 for(const id of t.connected_source_port_ids)portNet.set(id,nets[t.connected_source_net_ids[0]]);
}
function pin(ref,no){
 const p=circuit.find(p=>p.type==='source_port'&&p.source_component_id===parts[ref].source_component_id&&p.pin_number===no);
 return portNet.get(p?.source_port_id);
}
function value(ref,a,b,field){
 if(pin(ref,1)!==a||pin(ref,2)!==b)throw Error('Unexpected power-branch wiring at '+ref);
 const v=parts[ref][field];if(!(v>0))throw Error('Missing '+ref+' '+field);return v;
}
const cap=(ref,net)=>value(ref,net,'GND','capacitance');
const res=(ref,a,b)=>value(ref,a,b,'resistance');
for(const [ref,no,expected] of [['U21',1,'V12'],['U21',2,'V12'],['U21',3,'V12'],['U21',5,'BOTA_IMAX'],['U21',6,'BOTA_REF'],['U21',7,'GND'],['U21',8,'BOTA_ADJ'],['U21',9,'BOTA_9V'],['U21',10,'BOTA_9V'],['U21',11,'GND'],['J12',1,'BOTA_9V'],['J12',2,'GND']]){
 if(pin(ref,no)!==expected)throw Error('Unexpected net at '+ref+'.'+no);
}
cap('C116','BOTA_IMAX');cap('C117','BOTA_REF');
const vinSet=1.2*(1+res('R102','V12','FB12')/res('R103','FB12','GND'));
const rt=res('R107','BOTA_9V','BOTA_ADJ'),rb=res('R108','BOTA_ADJ','GND');
const limit=.6*500/res('R109','BOTA_IMAX','GND'),outputSet=.6*(1+rt/rb);
const settings={busMaxV:54,busMinV:42,regulatedRailFloorV:11.4,encoderA:.2,gateAndBrakeA:.1,ldoGroundA:.025,buck5Efficiency:.8,load5A:.5,outputToleranceR:.01,currentLimitScreenFraction:.10,inductorMinH:68e-6*.8,switchingFrequencyMinHz:270e3,effectiveCapFraction:.5};
const s=settings;
const maxRipple=vinSet*(1-vinSet/s.busMaxV)/(s.inductorMinH*s.switchingFrequencyMinHz);
const conservativeRating=Math.min(1,1.25-maxRipple/2);
const branchMax=limit*1.1/.99,branchMin=limit*.9/1.01;
// LT3065 Rev. F pages 5 and 6. Allow the maximum documented ADJ bias
// in either direction as a conservative screen for this divider.
const rtol=s.outputToleranceR;
const adjBiasV=60e-9*rt*(1+rtol);
const regulatedOutputRangeV={
 minimum:.588*(1+rt*(1-rtol)/(rb*(1+rtol)))-adjBiasV,
 maximum:.612*(1+rt*(1+rtol)/(rb*(1-rtol)))+adjBiasV,
 basis:'In regulation with 1% divider resistors and 0.588–0.612 V reference. A 60 nA ADJ bias allowance uses the datasheet test condition. Startup, dropout and component faults are outside this calculation.',
};
const nominalSensor=1.6/outputSet;
const other=s.encoderA+s.gateAndBrakeA+s.load5A*5/(s.regulatedRailFloorV*s.buck5Efficiency);
const capacitor12=['C103','C104','C108','C301','C302','C903','C904','C114'].reduce((v,r)=>v+cap(r,'V12'),0)*s.effectiveCapFraction;
const cout=cap('C115','BOTA_9V')*s.effectiveCapFraction;
const out='output/prototype/power';fs.mkdirSync(out,{recursive:true});
const sim=new Simulation();await sim.start();const runs=[];
const operatingCases=[['operating',.5,nominalSensor,branchMin],['startup_250mA',.5,.25,limit],['startup_500mA',.5,.5,branchMax],['heavy_5V_and_startup',1,.5,branchMax]];
const sweep=[];
async function simulate(name,i5,requested,startupLimit,constantPower5=false){
 // Averaged, already-running rail. A finite control response, effective MLCCs,
 // current ceilings and resistive sensor-loading below 9 V make overload visible.
 const base=s.encoderA+s.gateAndBrakeA+i5*5/(s.regulatedRailFloorV*s.buck5Efficiency);
 const initialI=s.encoderA+s.gateAndBrakeA+i5*5/(vinSet*s.buck5Efficiency)+s.ldoGroundA;
 const deck=`Bota branch load step extracted from Space Octopus Circuit JSON
Bcommand cmd 0 V=min(max((${vinSet}-v(rail))/.08,0),${conservativeRating})
Rresponse cmd response 1k
Cresponse response 0 5n
Bsource 0 rail I=v(response)
Crail rail 0 ${capacitor12}
${constantPower5 ? `Bexisting rail 0 I=min(max(v(rail)/6,0),1)*(${s.encoderA+s.gateAndBrakeA}+${i5*5/s.buck5Efficiency}/max(v(rail),6))` : `Rexisting rail 0 ${vinSet/base}`}
Breg rail sensor I=min(max((min(${outputSet},v(rail)-.51)-v(sensor))/.08,0),${startupLimit})
Cout sensor 0 ${cout}
Rdivider sensor 0 ${rt+rb}
Iground rail 0 ${s.ldoGroundA}
Vload step 0 PWL(0 0 .999m 0 1m ${requested} 2.999m ${requested} 3m ${nominalSensor} 5m ${nominalSensor})
Bload sensor 0 I=v(step)*max(v(sensor),0)/${outputSet}
${constantPower5 ? `.ic v(rail)=${vinSet-.08*initialI} v(sensor)=${outputSet} v(response)=${Math.min(initialI,conservativeRating)}` : ''}
.tran 2u 5m${constantPower5 ? ' uic' : ''}
.save v(rail) v(sensor) v(response)
.end
`;
 if(!constantPower5)fs.writeFileSync(out+'/'+name+'.cir',deck);
 sim.setNetList(deck);const result=await sim.runSim();
 if(!result||sim.getError().some(v=>/error|fatal/i.test(v)))throw Error(name+': '+sim.getError());
 const data=Object.fromEntries(result.data.map(v=>[v.name.toLowerCase(),v.values]));
 const range=(key,start,end)=>data[key].filter((_,i)=>data.time[i]>=start&&data.time[i]<=end);
 return {name,load5A:i5,sensorDemandA:requested,modeledLimitA:startupLimit,railMinV:Math.min(...range('v(rail)',.001,.005)),sensorMinV:Math.min(...range('v(sensor)',.001,.003)),peakSupplyA:Math.max(...range('v(response)',.001,.005))};
}
for(const [name,i5,request,ceiling] of operatingCases)runs.push(await simulate(name,i5,request,ceiling));
const limitCorners={low:branchMin,nominal:limit,high:branchMax};
for(const i5 of [.25,.5,.55,.6,.75,1]){
 for(const demand of [nominalSensor,.20,.24,.25,.273,.30,.35,.40,.45,.50]){
  for(const [corner,ceiling] of Object.entries(limitCorners)){
   const result=await simulate(corner,i5,demand,ceiling,true);
   const withinScreen=result.railMinV>=s.regulatedRailFloorV && result.sensorMinV>=6;
   sweep.push({...result,withinScreen});
  }
 }
}
const header=['Current limit corner','5 V load A','Sensor demand at 9 V A','Branch limit A','Minimum 12 V rail V','Minimum sensor V','Peak source current A','12 V >= 11.4 and sensor >= 6 V'];
const csv=sweep.map(r=>[r.name,r.load5A,r.sensorDemandA,r.modeledLimitA,r.railMinV,r.sensorMinV,r.peakSupplyA,r.withinScreen]);
fs.writeFileSync(out+'/load-sweep.csv',[header,...csv].map(row=>row.join(',')).join('\n')+'\n');
const sweepDescription={caseCount:sweep.length,limitCorners,load5A:[.25,.5,.55,.6,.75,1],sensorDemandA:[nominalSensor,.20,.24,.25,.273,.30,.35,.40,.45,.50],data:'load-sweep.csv',model:'Existing 5 V converter is a constant-power load, with a 6 V numerical floor after failure. Motor encoder and gate loads use constant current. Sensor loading is resistive below 9 V. Steps last 2 ms on a running rail.',screen:'Minimum shared rail 11.4 V and minimum sensor port 6 V over the modeled step. Passing does not demonstrate sensor boot or thermal margin.'};
const report={sweepDescription,regulatedOutputRangeV,circuitSha256:createHash('sha256').update(bytes).digest('hex'),settings,vinSet,outputSet,nominalSensor,nominalLimitA:limit,minLimitScreenA:branchMin,maxLimitScreenA:branchMax,worstScreenRippleApp:maxRipple,conservativeRailCapacityA:conservativeRating,steadyMarginA:conservativeRating-other-s.ldoGroundA-nominalSensor,startupMarginA:conservativeRating-other-s.ldoGroundA-branchMax,maximumConcurrent5VloadAtLimitedStartupA:(conservativeRating-s.encoderA-s.gateAndBrakeA-s.ldoGroundA-branchMax)*s.regulatedRailFloorV*s.buck5Efficiency/5,effectiveRailCapF:capacitor12,effectiveOutCapF:cout,runs,limitations:['Bounded engineering scenarios; frequency, effective capacitance, regulator response and gate-driver budgets require measurement. No switching-loop or manufacturer macro-model.', 'Existing electronics are modeled as a matched resistive load for transient screening; use DC budget for the constant-power 5 V converter envelope.', 'Unknown sensor startup is swept as an equivalent load. A current-limited sensor may brown out or restart; the model cannot predict successful boot.', 'The 10% current-limit spread is a screen extrapolated from the LT3065 test conditions, not a guaranteed 12 V/9 V specification. Thermal foldback, cable and cold startup are not modeled.']};
fs.writeFileSync(out+'/load-study.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({steadyMarginA:report.steadyMarginA,startupMarginA:report.startupMarginA,runs},null,2));
