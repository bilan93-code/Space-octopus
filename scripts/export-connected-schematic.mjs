import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {convertCircuitJsonToSchematicSvg} from 'circuit-to-svg';
const {chromium}=createRequire(import.meta.url)('playwright');

const canonicalBytes=fs.readFileSync('output/space-octopus.circuit.json');
const bytes=fs.readFileSync('output/connected-schematic/circuit.json');
const circuit=JSON.parse(bytes);
const sources=new Map(circuit.filter(e=>e.type==='source_component').map(e=>[e.source_component_id,e]));
const ports=new Map(circuit.filter(e=>e.type==='source_port').map(e=>[e.source_port_id,e]));
const nets=new Map(circuit.filter(e=>e.type==='source_net').map(e=>[e.source_net_id,e.name]));
const sourceParts=[...JSON.parse(fs.readFileSync('data/input-supplies-mcu-driver-inverter.json')),...JSON.parse(fs.readFileSync('data/sensing-fault-interfaces-brake.json')),...JSON.parse(fs.readFileSync('data/mechanical.json'))];
const byRef=new Map(sourceParts.map(p=>[p.ref,p]));
const expected=JSON.parse(fs.readFileSync('output/expanded-netlist.json'));
const actual={};
for(const trace of circuit.filter(e=>e.type==='source_trace'))for(const id of trace.connected_source_net_ids??[]){
 const name=nets.get(id);actual[name]??=new Set();
 for(const portId of trace.connected_source_port_ids??[]){const port=ports.get(portId);actual[name].add(`${sources.get(port.source_component_id).name}.${port.pin_number}`);}
}
if(JSON.stringify(Object.keys(expected).sort())!==JSON.stringify(Object.keys(actual).sort()))throw Error('Net-name mismatch');
for(const name of Object.keys(expected))if(JSON.stringify([...new Set(expected[name])].sort())!==JSON.stringify([...actual[name]].sort()))throw Error(`Pin-to-net mismatch: ${name}`);

const rendered=structuredClone(circuit.filter(e=>(e.type.startsWith('schematic_')||e.type.startsWith('source_'))&&!['schematic_group','schematic_sheet'].includes(e.type)&&!e.type.endsWith('_warning')&&!e.type.endsWith('_error')));
for(const e of rendered){delete e.schematic_group_id;delete e.schematic_sheet_id;}
const components=rendered.filter(e=>e.type==='schematic_component');
const expectedRefs=sourceParts.filter(p=>!['hole','fiducial'].includes(p.kind)).map(p=>p.ref).sort();
const foundRefs=components.map(e=>sources.get(e.source_component_id).name).sort();
if(JSON.stringify(expectedRefs)!==JSON.stringify(foundRefs))throw Error('Schematic component coverage mismatch');
let serial=0;
function text(value,x,y,size){return {type:'schematic_text',schematic_text_id:`connected_pdf_text_${serial++}`,text:value,position:{x,y},font_size:size,anchor:'left',rotation:0,color:'#143c51'};}
for(const component of components){
 const ref=sources.get(component.source_component_id).name;
 if(!rendered.some(e=>e.type==='schematic_text'&&e.schematic_component_id===component.schematic_component_id&&e.text===ref)){
  const t=text(ref,component.center.x-component.size.width/2,component.center.y+component.size.height/2+.68,.3);t.schematic_component_id=component.schematic_component_id;rendered.push(t);
 }
 if(byRef.get(ref).dnp){const t=text('DNP',component.center.x-.4,component.center.y-component.size.height/2-.6,.2);rendered.push(t);}
}
const all=[];
function gather(o){if(o&&typeof o==='object'){if(typeof o.x==='number'&&typeof o.y==='number')all.push(o);for(const v of Object.values(o))if(v&&typeof v==='object')gather(v);}}
for(const e of rendered.filter(e=>e.type.startsWith('schematic_')))gather(e);
const minX=Math.min(...all.map(p=>p.x))-6,maxX=Math.max(...all.map(p=>p.x))+6,minY=Math.min(...all.map(p=>p.y))-5,maxY=Math.max(...all.map(p=>p.y))+5;
rendered.push(text('SPACE OCTOPUS | CONNECTED SCHEMATIC',minX,maxY+8,1.45));
rendered.push(text('All components together. Symbols follow PCB placement and are spaced for legibility.',minX,maxY+5.2,.45));
rendered.push(text(`All ${Object.keys(actual).length} nets are drawn, including power and ground. Junction dots join wires. Gaps mark crossings.`,minX,maxY+3.4,.45));
rendered.push(text('Current tscircuit design | 4 x 820 uF / 100 V bus capacitors | TPS3431SDRBR watchdog | Engineering review',minX,minY-3,.45));
const width=10000,height=Math.ceil(width*(maxY-minY+15)/(maxX-minX));
const svg=convertCircuitJsonToSchematicSvg(rendered,{width,height,showErrorsInTextOverlay:false,colorOverrides:{schematic:{background:'#ffffff',sheet_background:'#ffffff',wire:'#1c6543',reference:'#143c51',value:'#143c51'}}}).replace('<svg ',`<svg viewBox="0 0 ${width} ${height}" `);
const base='output/Space_Octopus_Connected_Schematic';fs.writeFileSync(base+'.svg',svg);
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();const widthMm=2800,heightMm=widthMm*height/width;
 await page.setContent(`<html><title>Space Octopus - All components and connections</title><style>@page{size:${widthMm}mm ${heightMm}mm;margin:0}html,body{margin:0;padding:0}svg{display:block;width:${widthMm}mm;height:${heightMm}mm}</style>${svg}</html>`);
 await page.evaluate(()=>document.fonts.ready);
 await page.pdf({path:base+'.pdf',printBackground:true,preferCSSPageSize:true});
}finally{await browser.close();}
const labels=rendered.filter(e=>e.type==='schematic_net_label');
const labelCounts={};for(const l of labels)labelCounts[l.text]=(labelCounts[l.text]??0)+1;
const audit={sourceCircuitSha256:createHash('sha256').update(canonicalBytes).digest('hex'),schematicCaptureSha256:createHash('sha256').update(bytes).digest('hex'),canonicalCircuitUnchanged:fs.readFileSync('output/space-octopus.circuit.json').equals(canonicalBytes),componentCount:components.length,netCount:Object.keys(actual).length,allPinNetAssignmentsMatchCanonical:true,traceCount:rendered.filter(e=>e.type==='schematic_trace').length,labelCounts,pdf:base+'.pdf',pcbRelativePresentation:true,copperRoutesModified:false};
fs.writeFileSync('output/connected-schematic/export-audit.json',JSON.stringify(audit,null,2)+'\n');console.log(JSON.stringify(audit,null,2));
