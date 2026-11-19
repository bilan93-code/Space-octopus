import fs from 'node:fs';
import {createHash} from 'node:crypto';
const read=p=>JSON.parse(fs.readFileSync(p));const g=read('data/board-geometry.json'),j=read('output/space-octopus.circuit.json');
// Independent transcription from the supplied motor report, pp4,10,39.
const expected={housingOD:112,boltPCD:104,holeDiameter:4.5,angles:[30,90,150,210,270,330],shaftOD:12,locknutOD:19,shoulderOpening:28,rearCapEndZ:105,boltEndZ:109,shaftEndZ:120};
const errors=[];const check=(ok,msg)=>{if(!ok)errors.push(msg)};
check(g.outerDiameterMm===expected.housingOD,'PCB OD differs from motor housing OD112');
check(g.mounting.boltCircleDiameterMm===expected.boltPCD,'Mounting PCD differs from motor PCD104');
check(g.mounting.holeDiameterMm===expected.holeDiameter,'Mounting drills differ from motor Ø4.5 clearance');
check(JSON.stringify(g.mounting.anglesDegrees)===JSON.stringify(expected.angles),'Mounting angles differ from appendix bolt centers');
check(g.centralOpeningDiameterMm>=expected.locknutOD,'Proposed central opening cannot clear nominal locknut');
check(g.centralOpeningConfirmed===false&&g.assemblyFitVerified===false,'Do not claim assembly fit from dimensional capture');
const board=j.find(e=>e.type==='pcb_board');check(board?.width===112&&board?.height===112,'Rendered PCB envelope does not match motor OD112');
const source=fs.readFileSync('docs/Motor_Gmsh_Elmer_Design_Study.pdf');
const report={status:errors.length?'failed':'passed',nominalInterface:expected,pcbOpeningMm:g.centralOpeningDiameterMm,openingStatus:'proposed from motor shoulder opening; encoder support and axial fit pending',assemblyFitVerified:false,source:{file:'docs/Motor_Gmsh_Elmer_Design_Study.pdf',pages:[4,10,39],sha256:createHash('sha256').update(source).digest('hex')},errors};
fs.writeFileSync('output/motor-interface-audit.json',JSON.stringify(report,null,2)+'\n');
console.log(`Motor interface audit: ${report.status}; nominal Ø112, PCD104, six Ø4.5 holes.`);errors.forEach(e=>console.error(e));process.exitCode=errors.length?1:0;
