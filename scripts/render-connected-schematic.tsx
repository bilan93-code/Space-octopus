import React from 'react';
import fs from 'node:fs';
import {Circuit} from 'tscircuit';
import {parts,placement,electricalValue} from '../src/design';

// Separate schematic presentation. The PCB, its saved routes and BOM are never modified.
const shown=parts.filter(p=>!['hole','fiducial'].includes(p.kind));
const layout=shown.map(p=>{
 const n=Object.keys(p.pins).length;
 const major=p.kind==='chip'||p.kind==='connector';
 const w=major?(n>40?7:4):1.8,h=p.kind==='resistor'||(p.kind==='capacitor'&&!p.pinLabels['1'])?1.2:Math.max(1.2,Math.ceil(n/2)*.5+.5);
 const x=placement[p.ref].x*2.8,y=placement[p.ref].y*2.8;
 return {ref:p.ref,x,y,anchorX:x,anchorY:y,w,h,boxW:Math.max(w+3.6,5.8),boxH:h+3.0};
});
for(let iteration=0;iteration<1800;iteration++){
 let overlaps=0;
 for(let i=0;i<layout.length;i++)for(let j=i+1;j<layout.length;j++){
  const a=layout[i],b=layout[j],dx=b.x-a.x,dy=b.y-a.y;
  const ox=(a.boxW+b.boxW)/2-Math.abs(dx),oy=(a.boxH+b.boxH)/2-Math.abs(dy);
  if(ox<=0||oy<=0)continue;overlaps++;
  if(ox<oy){const shift=(ox+.02)*.51*(dx>=0?1:-1);a.x-=shift;b.x+=shift;}
  else{const shift=(oy+.02)*.51*(dy>=0?1:-1);a.y-=shift;b.y+=shift;}
 }
 if(!overlaps)break;
 if(iteration===1799)throw Error('Component presentation envelopes still overlap');
}
const positions=new Map(layout.map(p=>[p.ref,p]));
const nets=[...new Set(shown.flatMap(p=>Object.values(p.pins).filter((n):n is string=>n!==null)))].sort();
function Part({p}:{p:typeof shown[number]}){
 const loc=positions.get(p.ref)!;
 const connections=Object.fromEntries(Object.entries(p.pins).filter(([,n])=>n!==null).map(([pin,net])=>[`pin${pin}`,`net.${net}`]));
 const common={name:p.ref,schX:loc.x,schY:loc.y,connections,doNotPlace:p.dnp};
 if(p.kind==='resistor')return <resistor {...common} resistance={electricalValue(p.value)}/>;
 if(p.kind==='capacitor'&&!p.pinLabels['1'])return <capacitor {...common} capacitance={electricalValue(p.value)}/>;
 return <chip {...common} manufacturerPartNumber={p.mpn} displayName={p.value}
  pinLabels={Object.fromEntries(Object.entries(p.pins).map(([pin,net])=>[`pin${pin}`,`${(p.pinLabels[pin]??(net===null?'NC':'PIN')).replace(/\+/g,'PLUS').replace(/-/g,'MINUS').replace(/[^A-Za-z0-9_]/g,'_')}_${pin}`]))}
  noConnect={Object.entries(p.pins).filter(([,net])=>net===null).map(([pin])=>`pin${pin}`)} schWidth={loc.w} schHeight={loc.h}/>;
}
const circuit=new Circuit();circuit.pcbDisabled=true;circuit.pcbRoutingDisabled=true;
fs.mkdirSync('output/connected-schematic',{recursive:true});
fs.writeFileSync('output/connected-schematic/placement.json',JSON.stringify(layout,null,2)+'\n');
circuit.on('solver:started',(event:any)=>{
 if(event.solverName!=='SchematicTracePipelineSolver')return;
 console.log(`Schematic routing started: ${event.solverParams.chips?.length} symbols.`);
 if(process.env.OCTOPUS_SYMBOLS_ONLY==='1'){
  fs.writeFileSync('output/connected-schematic/symbols.json',JSON.stringify(circuit.db.toArray(),null,2)+'\n');
  fs.writeFileSync('output/connected-schematic/solver-input.json',JSON.stringify(event.solverParams,null,2)+'\n');
  process.exit(0);
 }
});
circuit.add(<board name="SpaceOctopusConnectedSchematic" width={400} height={400} routingDisabled schLayout={{layoutMode:'none'}} schAutoLayoutEnabled={false} schTraceAutoLabelEnabled={false} schMaxTraceDistance={1000}>
 {nets.map(n=><React.Fragment key={n}><net name={n} isGroundNet={n==='GND'} isPowerNet={['VBUS','V12','V5','V3V3','VDDA3V3','REF25','ENC12'].includes(n)}/></React.Fragment>)}
 {shown.map(p=><Part key={p.ref} p={p}/>)}
</board>);
console.log(`Rendering ${shown.length} components / ${nets.length} nets; PCB-relative positions; visible signal wiring.`);
await circuit.renderUntilSettled();
const json=circuit.getCircuitJson();
fs.mkdirSync('output/connected-schematic',{recursive:true});
fs.writeFileSync('output/connected-schematic/circuit.json',JSON.stringify(json,null,2)+'\n');
fs.writeFileSync('output/connected-schematic/placement.json',JSON.stringify(layout,null,2)+'\n');
const errors=json.filter(e=>e.type.includes('error'));
console.log(JSON.stringify({components:json.filter(e=>e.type==='schematic_component').length,traces:json.filter(e=>e.type==='schematic_trace').length,labels:json.filter(e=>e.type==='schematic_net_label').length,diagnostics:errors.map((e:any)=>({type:e.type,message:e.message}))},null,2));
