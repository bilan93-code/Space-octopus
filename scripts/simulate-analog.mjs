import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {circuitJsonToSpice} from 'circuit-json-to-spice';
import {Simulation} from 'eecircuit-engine';
import {eecircuitResultToSimulationGraphs,simulationGraphsToCircuitJson} from '@tscircuit/ngspice-spice-engine';

const input=process.argv[2]??'output/space-octopus.circuit.json';
const bytes=fs.readFileSync(input),json=JSON.parse(bytes);
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake'].flatMap(n=>JSON.parse(fs.readFileSync(`data/${n}.json`)));
const by=Object.fromEntries(parts.map(p=>[p.ref,p]));
const out='output/simulation';fs.mkdirSync(out,{recursive:true});
const engine=new Simulation();await engine.start();
const results=[],checks=[];
function circuit(refs){
 const ids=new Set(json.filter(e=>e.type==='source_component'&&refs.includes(e.name)).map(e=>e.source_component_id));
 const ports=new Set(json.filter(e=>e.type==='source_port'&&ids.has(e.source_component_id)).map(e=>e.source_port_id));
 const subset=json.filter(e=>e.type==='source_component'&&ids.has(e.source_component_id)||e.type==='source_port'&&ports.has(e.source_port_id)||e.type==='source_net'||e.type==='source_trace')
 .map(e=>e.type==='source_trace'?{...e,connected_source_port_ids:e.connected_source_port_ids?.filter(p=>ports.has(p))}:e)
 .filter(e=>e.type!=='source_trace'||e.connected_source_port_ids?.length);
 const text=circuitJsonToSpice(subset).toSpiceString().replace(/\.END\s*$/i,'');
 const nodes={GND:'0'};
 for(const line of text.split('\n')){
  const t=line.trim().split(/\s+/);const p=by[t[0]?.slice(1)];if(!p)continue;
  for(const [pin,index] of [['1',1],['2',2]]){
   const net=p.pins[pin];if(nodes[net]&&nodes[net]!==t[index])throw Error(`Inconsistent converter node ${net}`);nodes[net]=t[index];
  }
 }
 return {text,nodes,refs};
}
function check(name,actual,expected,tolerance){checks.push({name,actual,expected,tolerance,passed:Number.isFinite(actual)&&Math.abs(actual-expected)<=tolerance});}
function at(xs,ys,x){let i=xs.findIndex(v=>v>=x);if(i<1)return ys[Math.max(0,i<0?ys.length-1:0)];let f=(x-xs[i-1])/(xs[i]-xs[i-1]);return ys[i-1]+f*(ys[i]-ys[i-1]);}
async function run(name,c,extra,analysis,probes){
 const deck=c.text+extra+'\n.options reltol=1e-8 abstol=1e-13 vntol=1e-9\n'+analysis+'\n.save '+probes.map(n=>`v(${n})`).join(' ')+'\n.end\n';
 fs.writeFileSync(`${out}/${name}.cir`,deck);engine.setNetList(deck);const result=await engine.runSim();
 const errors=engine.getError().filter(s=>/error|fatal/i.test(s));if(!result||errors.length)throw Error(name+': '+errors.join('; '));
 fs.writeFileSync(`${out}/${name}.raw.json`,JSON.stringify(result));
 const graphs=eecircuitResultToSimulationGraphs(result,deck);fs.writeFileSync(`${out}/${name}.circuit.json`,JSON.stringify(simulationGraphsToCircuitJson(graphs,deck),null,2)+'\n');
 const d=Object.fromEntries(result.data.map(v=>[v.name.toLowerCase(),v.values.map(x=>typeof x==='number'?x:Math.hypot(x.real,x.img))]));const axis=d[result.data[0].name.toLowerCase()];
 if(result.dataType==='complex')for(const v of result.data.slice(1))d[v.name.toLowerCase()+'_phase_deg']=v.values.map(x=>Math.atan2(x.img,x.real)*180/Math.PI);
 const names=Object.keys(d);fs.writeFileSync(`${out}/${name}.csv`,names.join(',')+'\n'+axis.map((_,i)=>names.map(n=>d[n][i]).join(',')).join('\n')+'\n');
 results.push({name,refs:c.refs,labels:Object.fromEntries(Object.entries(c.nodes).map(([net,node])=>['v('+node.toLowerCase()+')',net])),analysis,points:result.numPoints,engine:result.header.match(/Command: ([^\n]+)/)?.[1],data:d,axis:result.data[0].name});return {d,axis};
}
const bus=circuit(['R504','R505','R506','C504']);
const dc=await run('bus-divider-dc',bus,`VINPUT ${bus.nodes.VBUS} 0 0`,'.dc VINPUT 0 65.1 0.1',[bus.nodes.VBUS_SENSE]);
for(const v of [0,48,65])check(`Bus divider at ${v} V`,at(dc.axis,dc.d[`v(${bus.nodes.VBUS_SENSE.toLowerCase()})`],v),v/31,1e-6);
const step=await run('bus-divider-step',bus,`VINPUT ${bus.nodes.VBUS} 0 PULSE(0 48 1u 1n 1n 1m 2m)`,'.tran 0.05u 100u',[bus.nodes.VBUS_SENSE]);
const tau=1/(1/300000+1/10000)*1e-9;
check('Bus filter at one time constant',at(step.axis,step.d[`v(${bus.nodes.VBUS_SENSE.toLowerCase()})`],1e-6+tau),48/31*(1-Math.exp(-1)),.001);
for(const [r,c,raw,adc] of [['R501','C501','IU_RAW','IU_ADC'],['R502','C502','IV_RAW','IV_ADC'],['R503','C503','IW_RAW','IW_ADC']]){
 const b=circuit([r,c]);const sim=await run(`${adc.toLowerCase()}-step`,b,`VINPUT ${b.nodes[raw]} 0 PULSE(1.65 2 10n 0.01n 0.01n 2u 4u)`,'.tran 0.5n 500n',[b.nodes[adc]]);
 const rs=json.find(e=>e.type==='source_component'&&e.name===r).resistance,cs=json.find(e=>e.type==='source_component'&&e.name===c).capacitance;
 check(`${adc} at one time constant`,at(sim.axis,sim.d[`v(${b.nodes[adc].toLowerCase()})`],10e-9+rs*cs),1.65+.35*(1-Math.exp(-1)),.0003);
 check(`${adc} settled`,sim.d[`v(${b.nodes[adc].toLowerCase()})`].at(-1),2,.0001);
}
const thresholds={};
for(const [state,vout] of [['off',0],['on',3.3]]){
 const b=circuit(['R901','R902','R903','R904','R905']);
 const sim=await run(`brake-${state}-threshold`,b,`VBUS ${b.nodes.VBUS} 0 0\nVRAIL ${b.nodes.V3V3} 0 3.3\nVSTATE ${b.nodes.BRAKE_ON} 0 ${vout}`,'.dc VBUS 0 70 0.05',[b.nodes.BRAKE_SENSE]);
 const sense=sim.d[`v(${b.nodes.BRAKE_SENSE.toLowerCase()})`];thresholds[state]=at(sense,sim.axis,2.5);
 const expected=(2.5*(1/300000+1/14000+1/499000)-vout/499000)*300000;
 check(`Brake ${state} threshold`,thresholds[state],expected,1e-5);
}
check('Brake hysteresis has correct direction',thresholds.off>thresholds.on?1:0,1,0);
for(const [name,b,inputNet,outputNet,fc,gain] of [
 ['bus-filter-ac',bus,'VBUS','VBUS_SENSE',1/(2*Math.PI*tau),1/31],
 ['current-filter-ac',circuit(['R501','C501']),'IU_RAW','IU_ADC',1/(2*Math.PI*47e-9),1],
]){
 const sim=await run(name,b,`VINPUT ${b.nodes[inputNet]} 0 DC 0 AC 1`,`.ac dec 40 ${fc/100} ${fc*100}`,[b.nodes[outputNet]]);const key=`v(${b.nodes[outputNet].toLowerCase()})`;
 check(`${name} cutoff amplitude`,at(sim.axis,sim.d[key],fc),gain/Math.sqrt(2),gain*.0001);
 check(`${name} cutoff phase`,at(sim.axis,sim.d[key+'_phase_deg'],fc),-45,.01);
}
{
 const b=circuit(['R516','R518','C510']);const nominal=10000,beta=Number(by.NTC1.value.match(/B(\d+)/)?.[1]);if(!beta)throw Error('Board NTC beta is not specified');
 const sim=await run('board-ntc-nominal-sweep',b,`VRAIL ${b.nodes.VDDA3V3} 0 3.3\nVTEMP degrees 0 0\nBNTC ${b.nodes.NTC_BOARD_RAW} 0 I={V(${b.nodes.NTC_BOARD_RAW})/(${nominal}*exp(${beta}*(1/(V(degrees)+273.15)-1/298.15)))}`,'.dc VTEMP 0 126 1',[b.nodes.NTC_BOARD_ADC]);
 for(const t of [0,25,80,125]){const r=nominal*Math.exp(beta*(1/(t+273.15)-1/298.15));check(`Nominal board NTC at ${t} C`,at(sim.axis,sim.d[`v(${b.nodes.NTC_BOARD_ADC.toLowerCase()})`],t),3.3*r/(10000+r),1e-5);}
}
const report={status:checks.every(c=>c.passed)?'passed':'failed',source:input,sourceSha256:createHash('sha256').update(bytes).digest('hex'),engine:'eecircuit-engine 1.9.0 / ngspice 45.2; local WASM; tscircuit Circuit JSON → circuit-json-to-spice → tscircuit simulation graphs',benches:results.map(({data,...r})=>r),checks,brakeThresholdsV:thresholds,limitations:['Extracted passive networks use ideal voltage sources and nominal linear components.','Brake thresholds use forced ideal output states and a 2.5 V reference, not a validated comparator or gate-driver model.','No complete inverter, firmware, motor, thermal, parasitic, EMC, tolerance or ADC sample-and-hold qualification.']};
fs.writeFileSync(`${out}/audit.json`,JSON.stringify(report,null,2)+'\n');
function plot(r,phase=false){
 const xs=r.data[r.axis.toLowerCase()];const ac=r.analysis.startsWith('.ac');
 const series=Object.entries(r.data).filter(([n])=>n.startsWith('v(')&&n!==r.axis.toLowerCase()&&(phase?n.endsWith('_phase_deg'):!n.endsWith('_phase_deg')));
 const unit=ac?'Frequency (Hz, logarithmic)':r.name.includes('ntc')?'Temperature (°C)':r.axis==='time'?(xs.at(-1)<1e-5?'Time (ns)':'Time (µs)'):'Input voltage (V)';
 const factor=r.axis==='time'?(xs.at(-1)<1e-5?1e9:1e6):1;
 const X=xs.map(v=>ac?Math.log10(v):v*factor);const curves=series.map(([name,v])=>({name,label:r.labels[name.replace('_phase_deg','')]??name,values:ac&&!phase?v.map(y=>20*Math.log10(Math.max(y,1e-30))):v}));
 let lo=Math.min(...curves.flatMap(v=>v.values)),hi=Math.max(...curves.flatMap(v=>v.values));if(hi===lo)hi=lo+1;
 const pad=(hi-lo)*.08;lo-=pad;hi+=pad;const colors=['#168a99','#d46938','#654daa'];
 const px=v=>70+700*(v-X[0])/(X.at(-1)-X[0]),py=v=>255-215*(v-lo)/(hi-lo);
 const ticks=Array.from({length:5},(_,i)=>{const xx=X[0]+(X.at(-1)-X[0])*i/4,yy=lo+(hi-lo)*i/4;return `<path d="M70 ${py(yy)}H770" stroke="#e2e8ed"/><text x="62" y="${py(yy)+4}" text-anchor="end">${yy.toPrecision(3)}</text><text x="${px(xx)}" y="277" text-anchor="middle">${(ac?10**xx:xx).toPrecision(3)}</text>`}).join('');
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 330" width="800" height="330" role="img" aria-label="${r.name}${phase?' phase':''}"><rect width="800" height="330" fill="white"/><g font-family="sans-serif" font-size="11" fill="#46586b">${ticks}<path d="M70 35V255H770" fill="none" stroke="#73838e"/><text x="70" y="20">${phase?'Phase (degrees)':ac?'Magnitude (dB)':'Voltage (V)'}</text><text x="420" y="301" text-anchor="middle">${unit}</text>${curves.map((v,i)=>`<polyline fill="none" stroke="${colors[i%3]}" stroke-width="2" points="${v.values.map((y,k)=>`${px(X[k])},${py(y)}`).join(' ')}"/><text x="${75+i*210}" y="323" fill="${colors[i%3]}">${v.label}</text>`).join('')}</g></svg>`;
 const file=r.name+(phase?'-phase':'')+'.svg';fs.writeFileSync(out+'/'+file,svg);return `<a href="${file}" download title="Download SVG plot">${svg}</a>`;
}
const cards=results.map(r=>`<article><h2>${r.name.replaceAll('-',' ')}</h2><p>${r.refs.join(', ')} · ${r.points} samples · <a href="${r.name}.csv">CSV</a> · <a href="${r.name}.cir">SPICE deck</a></p>${plot(r)}${r.analysis.startsWith('.ac')?plot(r,true):''}</article>`).join('');
fs.writeFileSync(`${out}/index.html`,`<!doctype html><meta charset="utf-8"><title>Space Octopus analog simulations</title><style>body{font:16px system-ui;background:#f4f6f8;color:#243245;max-width:1050px;margin:35px auto;padding:20px}article{background:white;padding:20px;margin:20px 0;border-radius:12px}svg{width:100%;height:auto}p{line-height:1.5}a{color:#087f90}</style><h1>Analog simulation checks</h1><p>${report.status.toUpperCase()} · ${checks.length} assertions · ${results.length} source-derived benches</p><p>Ideal passive networks and nominal functional models. Brake thresholds: ${thresholds.off.toFixed(3)} V on, ${thresholds.on.toFixed(3)} V off. These checks do not qualify the complete motor drive. See <a href="audit.json">the audit and model limits</a>. Click a plot to download its SVG.</p>${cards}`);
console.log('Analog simulations:',report.status,results.length,'benches,',checks.length,'checks');for(const c of checks.filter(c=>!c.passed))console.log(c);process.exit(report.status==='passed'?0:1);
