import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {convertCircuitJsonToGerberFiles,convertCircuitJsonToExcellonDrillCommands,stringifyExcellonDrill} from 'circuit-json-to-gerber';
import {convertCircuitJsonToPickAndPlaceCsv} from 'circuit-json-to-pnp-csv';
import {orderGerberPours} from './gerber-input.mjs';
import {isFitted} from './assembly-parts.mjs';
const json=JSON.parse(fs.readFileSync('output/space-octopus.circuit.json'));
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n=>JSON.parse(fs.readFileSync(`data/${n}.json`)));
const audit=fs.existsSync('output/copper-audit.json')?JSON.parse(fs.readFileSync('output/copper-audit.json')):null;
const dir='output/review-fabrication';fs.mkdirSync(dir,{recursive:true});
// These files are fully generated; prevent obsolete exports surviving a build.
for(const name of fs.readdirSync(dir))if(fs.statSync(path.join(dir,name)).isFile())fs.unlinkSync(path.join(dir,name));
const files=convertCircuitJsonToGerberFiles(orderGerberPours(json));const report=[];
// The locked exporter includes circular cutouts in both the profile and NPTH
// drills. This board specifies a routed opening, so generate NPTH commands
// from drilled holes only, keeping the exact circular arcs in Edge_Cuts.
files['drill_npth.drl']=stringifyExcellonDrill(convertCircuitJsonToExcellonDrillCommands({circuitJson:json.filter(e=>e.type!=='pcb_cutout'),is_plated:false}));
for(const [name,content] of Object.entries(files)){
 const dest=path.join(dir,path.basename(name));fs.writeFileSync(dest,content);
 report.push({file:path.basename(name),bytes:Buffer.byteLength(content),sha256:createHash('sha256').update(content).digest('hex')});
}
const fitted=new Set(parts.filter(isFitted).map(p=>p.ref));
const sources=new Map(json.filter(e=>e.type==='source_component').map(e=>[e.source_component_id,e.name]));
const assemblyJson=json.filter(e=>e.type!=='pcb_component'||fitted.has(sources.get(e.source_component_id)));
const warnings=[];const csv=convertCircuitJsonToPickAndPlaceCsv(assemblyJson,{onRotationWarning:w=>warnings.push(w)});
fs.writeFileSync('output/pick-and-place-review.csv',csv);
fs.writeFileSync(`${dir}/README.txt`,`ENGINEERING REVIEW ONLY — DO NOT FABRICATE\n\nGenerated from the tscircuit Circuit JSON, including the current copper.\nCopper audit: ${audit?.status??'not run'}; ${audit?.unconnectedNetCount??'unknown'} disconnected nets.\nPower-current capacity, switching behavior, differential timing, selected packages, stackup, cooling and motor assembly fit require engineering validation. Dedicated Kelvin branches have a separate isolation audit.\nThe layout requires filled and capped via-in-pad manufacture, including bypass and exposed-pad vias. Specify the actual stackup, copper weights, mask and paste process with the provider.\nThe proposed 28 mm central opening is exported as a routed circular cutout on the board-outline layer. Confirm machining tolerances with the fabricator.\nPick-and-place rotations are footprint coordinates and require assembly-provider review.\nRead output/copper-audit.json, output/kelvin-audit.json and output/electrical-audit.json before using these files.\n`);
fs.writeFileSync('output/fabrication-export-status.json',JSON.stringify({purpose:'engineering review only',fabricationReady:false,circuitJsonSha256:createHash('sha256').update(fs.readFileSync('output/space-octopus.circuit.json')).digest('hex'),files:report,pickAndPlaceWarnings:warnings,source:'circuit-json-to-gerber 0.0.123 / circuit-json-to-pnp-csv',notes:'Mechanical aperture machining and assembly rotations require review.'},null,2)+'\n');
console.log(`Exported ${report.length} Gerber/Excellon review files and pick-and-place CSV.`);
