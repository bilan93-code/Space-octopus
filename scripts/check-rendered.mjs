import fs from 'node:fs';
import assert from 'node:assert/strict';
import {courtyardInsideBoard} from './geometry-checks.mjs';
const read=p=>JSON.parse(fs.readFileSync(p));
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n=>read(`data/${n}.json`));
const j=read('output/space-octopus.circuit.json'),netlist=read('output/expanded-netlist.json');
const errors=[];const check=(condition,message)=>{if(!condition)errors.push(message)};
const sources=j.filter(e=>e.type==='source_component');
const catalog=read('footprints/catalog.json');
const placement=read('data/placement.json');
check(!sources.some(s=>s.name==='F1')&&!j.some(e=>e.type==='source_net'&&e.name==='DC_IN'),'Retired input fuse or separate DC_IN net remains in the rendered board');
check(sources.length===parts.length,'Rendered component count differs from inventory');
for(const p of parts){
 const source=sources.find(s=>s.name===p.ref);check(!!source,`${p.ref}: missing source`);if(!source)continue;
 if(p.kind==='fuse')check(source.manufacturer_part_number===p.mpn,`${p.ref}: rendered fuse MPN differs from the design`);
 const pcb=j.find(e=>e.type==='pcb_component'&&e.source_component_id===source.source_component_id);check(!!pcb,`${p.ref}: missing PCB component`);
 if(pcb)check(pcb.layer===placement[p.ref].layer,`${p.ref}: rendered PCB face differs from placement`);
 const ports=j.filter(e=>e.type==='source_port'&&e.source_component_id===source.source_component_id);
 for(const [pin,net] of Object.entries(p.pins)){
  check(ports.some(port=>port.pin_number===+pin),`${p.ref}.${pin}: no physical source port`);
  const nets=Object.entries(netlist).filter(([,list])=>list.includes(`${p.ref}.${pin}`)).map(([name])=>name);
  check(JSON.stringify(nets)===(net===null?'[]':JSON.stringify([net])),`${p.ref}.${pin}: rendered net ${nets} differs from ${net}`);
  if(pcb)check(j.some(e=>e.type==='pcb_port'&&e.pcb_component_id===pcb.pcb_component_id&&ports.some(s=>s.pin_number===+pin&&s.source_port_id===e.source_port_id)),`${p.ref}.${pin}: no physical PCB port`);
 }
 if(pcb){
  const pads=j.filter(e=>['pcb_smtpad','pcb_plated_hole','pcb_hole'].includes(e.type)&&e.pcb_component_id===pcb.pcb_component_id);
  const expected=catalog[p.footprint].elements.filter(e=>['pcb_smtpad','pcb_plated_hole','pcb_hole'].includes(e.type));
  check(pads.length===expected.length,`${p.ref}: rendered pad/hole count ${pads.length} != ${expected.length}`);
  if(p.ref==='F2'){
   check(!pcb.do_not_place && pads.length===2 && pads.every(pad=>pad.type==='pcb_smtpad' && pad.layer===pcb.layer),'F2: expected two populated surface-mount fuse lands');
   check(pads.every(pad=>j.some(e=>e.type==='pcb_solder_paste' && e.pcb_smtpad_id===pad.pcb_smtpad_id && e.layer===pcb.layer)),'F2: each fuse land needs a stencil aperture');
  }
  if(p.assembly==='wire-termination'){
   check(!source.manufacturer_part_number && pcb.do_not_place===true,`${p.ref}: wire lands must be excluded from component assembly`);
   check(pads.every(pad=>pad.type==='pcb_plated_hole' && pad.hole_diameter===1.8 && ['top','inner1','inner2','bottom'].every(layer=>pad.layers.includes(layer))),`${p.ref}: wire terminals require 1.8 mm four-layer plated holes`);
   check(!j.some(e=>e.pcb_component_id===pcb.pcb_component_id && ['cad_component','pcb_solder_paste'].includes(e.type)),`${p.ref}: wire lands should have neither a component body nor stencil apertures`);
  }
 }
}
const geometry=read('data/board-geometry.json');
const boxes=Object.entries(placement);
for(const [ref,p] of boxes){
 if(!ref.match(/^H[0-9]+$/))check(courtyardInsideBoard(p.courtyard,geometry),`${ref}: courtyard violates circular edge or central-opening margin`);
 else check(Math.hypot(...p.bodyCenter)+geometry.mounting.holeDiameterMm/2+geometry.edgeMarginMm<=geometry.outerDiameterMm/2*Math.cos(Math.PI/geometry.outlineSegments),`${ref}: drill-to-board edge margin too small`);
 const source=sources.find(s=>s.name===ref);const pcb=j.find(e=>e.type==='pcb_component'&&e.source_component_id===source?.source_component_id);
 for(const pad of j.filter(e=>['pcb_smtpad','pcb_plated_hole'].includes(e.type)&&e.pcb_component_id===pcb?.pcb_component_id)){
  const b=p.courtyard;check(pad.x>=b[0]-0.001&&pad.x<=b[2]+0.001&&pad.y>=b[1]-0.001&&pad.y<=b[3]+0.001,`${ref}: rendered pad center outside reserved courtyard (mirroring/rotation)`);
 }
}
const board=j.find(e=>e.type==='pcb_board');
check(!!board,'Missing PCB board');
check(board?.outline?.length===geometry.outlineSegments,'Circular outline segment count differs from geometry');
for(const point of board?.outline??[])check(Math.abs(Math.hypot(point.x,point.y)-geometry.outerDiameterMm/2)<1e-6,'Rendered circular outline radius differs from geometry');
check(board?.num_layers===4||board?.layers?.length===4,'Expected four copper layers');
for(const [i,angle] of geometry.mounting.anglesDegrees.entries()){
 const pos=placement[`H${i+1}`];const t=angle*Math.PI/180,r=geometry.mounting.boltCircleDiameterMm/2;
 check(!!pos&&Math.hypot(pos.bodyCenter[0]-r*Math.cos(t),pos.bodyCenter[1]-r*Math.sin(t))<1e-6,`H${i+1}: moved away from configured bolt circle`);
 const source=sources.find(s=>s.name===`H${i+1}`);
 const component=j.find(e=>e.type==='pcb_component'&&e.source_component_id===source?.source_component_id);
 const hole=j.find(e=>e.type==='pcb_hole'&&e.pcb_component_id===component?.pcb_component_id);
 check(!!hole&&Math.abs(hole.hole_diameter-geometry.mounting.holeDiameterMm)<1e-6,`H${i+1}: physical hole diameter differs from configured mount`);
}
// These catch the failure mode of changing only the outline while leaving
// components in rectangular corners, plus central-aperture collisions.
assert(!courtyardInsideBoard([55,40,58,45],{...geometry,outerDiameterMm:128,centralOpeningDiameterMm:null}),'Reject former rectangular-corner placement');
assert(!courtyardInsideBoard([-2,-2,2,2],{...geometry,centralOpeningDiameterMm:12}),'Reject central-opening overlap');
assert(courtyardInsideBoard([-2,-2,2,2],{...geometry,centralOpeningDiameterMm:null}),'Allow central placement in full-disc preview');
assert(courtyardInsideBoard([54.99,-.01,54.999,.01],{...geometry,centralOpeningDiameterMm:null}),'Nominal 1 mm circular courtyard margin must match the assembly check');
assert(!courtyardInsideBoard([55.001,-.01,55.01,.01],{...geometry,centralOpeningDiameterMm:null}),'Reject a courtyard inside the nominal 1 mm margin');
// Exact per-face envelopes replace the former both-face AABB assumption.
// Through-hole solder projections are checked on the opposite face as well.
const {spawnSync}=await import('node:child_process');
const roundedPth=spawnSync('node_modules/.bin/tsx',['scripts/check-rounded-pth.ts'],{encoding:'utf8',env:process.env});
check(roundedPth.status===0,`Rounded PTH clearance regression failed: ${roundedPth.stdout} ${roundedPth.stderr}`);
const contacts=spawnSync('node_modules/.bin/tsx',['scripts/check-route-contact-geometry.ts'],{encoding:'utf8',env:process.env});
check(contacts.status===0,`Native pin-contact geometry regression failed: ${contacts.stdout} ${contacts.stderr}`);
const assembly=spawnSync(process.env.PYTHON??'python3',['scripts/check-assembly.py'],{encoding:'utf8',env:process.env});
check(assembly.status===0,`Assembly envelope check failed: ${assembly.stdout} ${assembly.stderr}`);
check(j.some(e=>e.type==='pcb_cutout'&&e.shape==='circle'&&Math.abs(e.radius*2-geometry.centralOpeningDiameterMm)<1e-6),'Missing physical central aperture');
check(j.filter(e=>e.type==='schematic_sheet').length===9,'Expected nine schematic sheets');
const captureErrors=[...errors];
const renderErrors=j.filter(e=>e.type.includes('error'));check(renderErrors.length===0,`${renderErrors.length} native render/DRC errors; see render-diagnostics.json`);
const copper=fs.existsSync('output/copper-audit.json')?read('output/copper-audit.json'):null;
const report={status:errors.length?'failed':'passed',captureAndPlacementStatus:captureErrors.length?'failed':'passed',components:sources.length,nets:Object.keys(netlist).length,sheets:9,pcbRouted:copper?.status==='passed',pcbTraceCount:j.filter(e=>e.type==='pcb_trace').length,fullyConnectedNets:copper?.fullyConnectedNets??null,unconnectedNetCount:copper?.unconnectedNetCount??null,nativeDiagnosticCount:renderErrors.length,outerDiameterMm:geometry.outerDiameterMm,nominalMotorDimensionsSourced:geometry.nominalMotorDimensionsSourced,centralOpeningDiameterMm:geometry.centralOpeningDiameterMm,mechanicalFitConfirmed:geometry.assemblyFitVerified,errors,notes:'Capture and placement are checked separately from native DRC and copper connectivity. Planning courtyard spacing is not a voltage-clearance rule.'};
fs.writeFileSync('output/rendered-audit.json',JSON.stringify(report,null,2)+'\n');
console.log(`Rendered audit: ${report.status}; ${report.components} components, ${report.nets} nets.`);
for(const e of errors)console.error(e);
process.exitCode=errors.length?1:0;
