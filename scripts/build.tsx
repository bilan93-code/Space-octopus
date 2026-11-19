import React from 'react';
import fs from 'node:fs';
import { Circuit } from 'tscircuit';
import {convertCircuitJsonToPcbSvg,convertCircuitJsonToSchematicSvg} from 'circuit-to-svg';
import {Resvg} from '@resvg/resvg-js';
import SpaceOctopus from '../src/SpaceOctopus';
import {parts,sheets,placement} from '../src/design';
fs.mkdirSync('output/schematics',{recursive:true});
const inputFlag=process.argv.indexOf('--from-json');
let j:any[];
if(inputFlag>=0)j=JSON.parse(fs.readFileSync(process.argv[inputFlag+1],'utf8'));
else {
 const circuit=new Circuit();circuit.add(<SpaceOctopus routing={!process.argv.includes('--capture-only')} useSavedRoutes={!process.argv.includes('--capture-only')} groundPlane={!process.argv.includes('--capture-only')}/>);
 await circuit.renderUntilSettled();j=circuit.getCircuitJson();
}
const jsonOutput=process.argv.find(a=>a.startsWith('--json-output='))?.split('=')[1]??'output/space-octopus.circuit.json';
const serialized=JSON.stringify(j,null,2)+'\n';
if(!fs.existsSync(jsonOutput)||fs.readFileSync(jsonOutput,'utf8')!==serialized)fs.writeFileSync(jsonOutput,serialized);
const errors=j.filter(e=>e.type.includes('error'));
const showAirwires=errors.some(e=>e.type==='pcb_port_not_connected_error');
if(jsonOutput==='output/space-octopus.circuit.json')fs.writeFileSync('output/render-diagnostics.json',JSON.stringify(errors,null,2)+'\n');
if(process.argv.includes('--json-only')){
 console.log(`Rendered ${j.filter(e=>e.type==='pcb_trace').length} copper routes; ${errors.length} native diagnostics.`);
 const counts:Record<string,number>={};for(const e of errors)counts[e.type]=(counts[e.type]??0)+1;console.log(counts);
 process.exit(errors.length?1:0);
}
const pcb=convertCircuitJsonToPcbSvg(j,{width:1600,height:1400,matchBoardAspectRatio:true,layer:'top',shouldDrawRatsNest:false,showCourtyards:true,showPinNumbers:true});
fs.writeFileSync('output/pcb-placement.svg',pcb);
fs.writeFileSync('output/pcb-placement.png',new Resvg(pcb,{fitTo:{mode:'width',value:1800}}).render().asPng());
const bottom=convertCircuitJsonToPcbSvg(j,{width:1600,height:1400,matchBoardAspectRatio:true,layer:'bottom',shouldDrawRatsNest:false,showCourtyards:true,showPinNumbers:true});
fs.writeFileSync('output/pcb-bottom.svg',bottom);
fs.writeFileSync('output/pcb-bottom-ratsnest.svg',showAirwires?convertCircuitJsonToPcbSvg(j,{width:1600,height:1400,matchBoardAspectRatio:true,layer:'bottom',shouldDrawRatsNest:true}):bottom);
fs.writeFileSync('output/pcb-bottom.png',new Resvg(bottom,{fitTo:{mode:'width',value:1800}}).render().asPng());
fs.writeFileSync('output/pcb-ratsnest.svg',showAirwires?convertCircuitJsonToPcbSvg(j,{width:1600,height:1400,matchBoardAspectRatio:true,layer:'top',shouldDrawRatsNest:true}):pcb);
for(const [i,sheet] of (process.argv.includes('--pcb-only')?[]:Array.from(sheets.entries()))){
 const svg=convertCircuitJsonToSchematicSvg(j,{schematicSheetIndex:i,width:2400,height:1800,showErrorsInTextOverlay:false});
 fs.writeFileSync(`output/schematics/${sheet}.svg`,svg);
}
const q=(s:unknown)=>`"${String(s??'').replaceAll('"','""')}"`;
fs.writeFileSync('output/bom.csv',[['Reference','Sheet','Value','MPN','Footprint','DNP','Provisional','Open item','PCB face','LCSC'],...parts.filter(p=>!['hole','fiducial','testpoint'].includes(p.kind)).map(p=>[p.ref,p.sheet,p.value,p.mpn??'',p.footprint,p.dnp,p.provisional,p.provisionalReason??'',placement[p.ref].layer,p.lcsc??''])].map(row=>row.map(q).join(',')).join('\n')+'\n');
fs.writeFileSync('output/pcb-features.csv',[['Reference','Feature','Footprint'],...parts.filter(p=>['hole','fiducial','testpoint'].includes(p.kind)).map(p=>[p.ref,p.kind,p.footprint])].map(row=>row.map(q).join(',')).join('\n')+'\n');
// Expanded netlist is read from rendered source traces, independently of data.
const sources=new Map(j.filter(e=>e.type==='source_component').map(e=>[e.source_component_id,e]));
const ports=new Map(j.filter(e=>e.type==='source_port').map(e=>[e.source_port_id,e]));
const netNames=new Map(j.filter(e=>e.type==='source_net').map(e=>[e.source_net_id,e.name]));
const netlist:Record<string,string[]>={};
for(const t of j.filter(e=>e.type==='source_trace')){
 for(const net of t.connected_source_net_ids??[]){
  const name=netNames.get(net!)!;netlist[name]??=[];
  for(const portId of t.connected_source_port_ids??[]){
   const port=ports.get(portId)!; const ref=sources.get(port.source_component_id!)!.name;
   netlist[name].push(`${ref}.${port.pin_number}`);
  }
 }
}
for(const n of Object.keys(netlist))netlist[n]=[...new Set(netlist[n])].sort();
fs.writeFileSync('output/expanded-netlist.json',JSON.stringify(netlist,null,2)+'\n');
fs.mkdirSync('output/pin-assignments',{recursive:true});
for(const p of parts.filter(p=>p.kind==='chip'||p.kind==='connector')){
 fs.writeFileSync(`output/pin-assignments/${p.ref}.csv`,[['Pin','Label','Net'],...Object.entries(p.pins).map(([pin,net])=>[pin,p.pinLabels[pin]??'',net??'NC'])].map(row=>row.map(q).join(',')).join('\n')+'\n');
}
console.log(`Built ${sources.size} PCB components, ${Object.keys(netlist).length} nets, ${sheets.length} schematic sheets; ${errors.length} render errors.`);
for(const e of errors.slice(0,8))console.log(e);
// Producing a review artifact is distinct from passing DRC. All diagnostics
// remain in the JSON/report; npm run check is the strict validation gate.
