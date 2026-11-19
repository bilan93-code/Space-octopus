import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {convertCircuitJsonToSchematicSvg} from 'circuit-to-svg';
const {chromium}=createRequire(import.meta.url)('playwright');

// Presentation-only export: never write the canonical circuit, PCB or BOM.
const sourceBytes=fs.readFileSync('output/space-octopus.circuit.json');
const circuit=JSON.parse(sourceBytes);
const sources=new Map(circuit.filter(e=>e.type==='source_component').map(e=>[e.source_component_id,e]));
const sheetRows=[['00_Input','01_Supplies','08_Brake'],['02_MCU','06_FaultLogic','07_Interfaces'],['05_Sensing','03_GateDriver','04_Inverter']];
const titles={'00_Input':'DC input and bus capacitors','01_Supplies':'Power supplies and reference','02_MCU':'Microcontroller and programming','03_GateDriver':'Three-phase gate driver','04_Inverter':'MOSFET inverter and current shunts','05_Sensing':'Current, voltage and temperature sensing','06_FaultLogic':'Watchdog, fault latch and PWM permission','07_Interfaces':'Encoder, CAN and external interfaces','08_Brake':'Regenerative braking chopper'};
const allowed=new Set(['schematic_component','schematic_port','schematic_trace','schematic_net_label','schematic_text']);
const rendered=circuit.filter(e=>e.type.startsWith('source_'));
const panels=[];
let serial=0;
function label(text,x,y,size,id){return {type:'schematic_text',schematic_text_id:id??`full_schematic_text_${serial++}`,text,position:{x,y},font_size:size,anchor:'left',rotation:0,color:'#183c47'};}
function points(object,result=[]){
 if(object&&typeof object==='object'){
  if(typeof object.x==='number'&&typeof object.y==='number')result.push(object);
  for(const value of Object.values(object))if(value&&typeof value==='object')points(value,result);
 }
 return result;
}
function compressor(intervals,maxGap=1.4){
 intervals.sort((a,b)=>a[0]-b[0]);const merged=[];
 for(const [lo,hi] of intervals){const prev=merged.at(-1);if(prev&&lo<=prev[1])prev[1]=Math.max(prev[1],hi);else merged.push([lo,hi]);}
 const gaps=[];
 for(let i=1;i<merged.length;i++){const left=merged[i-1][1],right=merged[i][0];if(right-left>maxGap)gaps.push({left,right,remove:right-left-maxGap});}
 return value=>value-gaps.reduce((sum,g)=>sum+(value>=g.right?g.remove:value>g.left?(value-g.left)*g.remove/(g.right-g.left):0),0);
}
for(const name of sheetRows.flat()){
 const sheet=circuit.find(e=>e.type==='schematic_sheet'&&e.name===name);
 if(!sheet)throw new Error(`Missing sheet ${name}`);
 const elements=structuredClone(circuit.filter(e=>allowed.has(e.type)&&e.schematic_sheet_id===sheet.schematic_sheet_id&&(e.type!=='schematic_text'||e.schematic_component_id)));
 const components=elements.filter(e=>e.type==='schematic_component');
 for(const component of components){
  const ref=sources.get(component.source_component_id)?.name;
  if(!ref)throw new Error('Schematic component has no reference');
  if(!elements.some(e=>e.type==='schematic_text'&&e.schematic_component_id===component.schematic_component_id&&e.text===ref)){
   const text=label(ref,component.center.x-component.size.width/2,component.center.y+component.size.height/2+.66,.25);
   text.schematic_component_id=component.schematic_component_id;elements.push(text);
  }
 }
 const intervals={x:[],y:[]};
 const protect=(x,y,w,h)=>{intervals.x.push([x-w/2,x+w/2]);intervals.y.push([y-h/2,y+h/2]);};
 for(const element of elements){
  if(element.type==='schematic_component')protect(element.center.x,element.center.y,element.size.width+1.4,element.size.height+1.4);
  if(element.type==='schematic_text'){
   const size=element.font_size??.18,w=Math.max(.8,element.text.length*size*.75);
   const x=element.position.x+(element.anchor==='left'?w/2:element.anchor==='right'?-w/2:0);
   protect(x,element.position.y,w+.6,Math.max(.7,size*2));
  }
  if(element.type==='schematic_net_label'){
   const width=Math.max(1,element.text.length*.18);
   const p=element.anchor_position??element.center;
   protect(p.x,p.y,2*width+1,1.4);
  }
  for(const p of points(element))protect(p.x,p.y,.35,.35);
 }
 const fx=compressor(intervals.x),fy=compressor(intervals.y);
 // Every symbol retains its dimensions; only empty strips / straight wire lengths contract.
 for(const c of components){
  if(Math.abs(fx(c.center.x+c.size.width/2)-fx(c.center.x-c.size.width/2)-c.size.width)>1e-8||Math.abs(fy(c.center.y+c.size.height/2)-fy(c.center.y-c.size.height/2)-c.size.height)>1e-8)throw new Error('Symbol distortion');
 }
 for(const e of elements){for(const p of points(e)){p.x=fx(p.x);p.y=fy(p.y);}delete e.schematic_sheet_id;delete e.schematic_group_id;}
 const minX=fx(Math.min(...intervals.x.map(a=>a[0])))-.7,maxX=fx(Math.max(...intervals.x.map(a=>a[1])))+.7;
 const minY=fy(Math.min(...intervals.y.map(a=>a[0])))-.7,maxY=fy(Math.max(...intervals.y.map(a=>a[1])))+.7;
 panels.push({name,elements,minX,maxX,minY,maxY,width:maxX-minX,height:maxY-minY,components:components.length});
}
const byName=new Map(panels.map(p=>[p.name,p]));
const colWidths=[0,1,2].map(i=>Math.max(...sheetRows.map(row=>byName.get(row[i]).width)));
const rowHeights=sheetRows.map(row=>Math.max(...row.map(n=>byName.get(n).height))+3.2);
let y=0;
for(let row=0;row<3;row++){
 let x=0;
 for(let col=0;col<3;col++){
  const panel=byName.get(sheetRows[row][col]);
  const dx=x-panel.minX,dy=y-2.2-panel.maxY;
  for(const e of panel.elements){for(const p of points(e)){p.x+=dx;p.y+=dy;}rendered.push(e);}
  rendered.push(label(titles[panel.name],x,y,.65));
  x+=colWidths[col]+3;
 }
 y-=rowHeights[row]+2;
}
const expected=circuit.filter(e=>e.type==='schematic_component');
const actual=rendered.filter(e=>e.type==='schematic_component');
if(actual.length!==expected.length)throw new Error(`Component coverage ${actual.length}/${expected.length}`);
for(const type of ['schematic_component','schematic_port','schematic_trace','schematic_net_label']){
 const id=`${type}_id`,a=circuit.filter(e=>e.type===type).map(e=>e[id]).sort(),b=rendered.filter(e=>e.type===type).map(e=>e[id]).sort();
 if(JSON.stringify(a)!==JSON.stringify(b))throw new Error(`Coverage mismatch: ${type}`);
}
const width=colWidths.reduce((a,b)=>a+b,0)+6;
rendered.push(label('SPACE OCTOPUS | COMPLETE SCHEMATIC',0,4.2,1));
rendered.push(label('All circuits on one page. Identical net labels connect electrically throughout this drawing.',0,2.5,.38));
rendered.push(label('REV A + C1-C4 / U13 amendment | 4 x 820 uF bus bank | Engineering review - manufacturing qualification pending',0,y+.4,.35));
const svgWidth=7200,svgHeight=Math.ceil(svgWidth*(Math.abs(y)+7)/width);
const svg=convertCircuitJsonToSchematicSvg(rendered,{width:svgWidth,height:svgHeight,showErrorsInTextOverlay:false,colorOverrides:{schematic:{background:'#ffffff',sheet_background:'#ffffff',wire:'#176539',reference:'#173d5c',value:'#173d5c'}}}).replace('<svg ',`<svg viewBox="0 0 ${svgWidth} ${svgHeight}" `);
const base='output/Space_Octopus_Complete_Schematic_One_Page';
fs.writeFileSync(base+'.svg',svg);
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();
 const widthMm=1682,heightMm=widthMm*svgHeight/svgWidth;
 await page.setContent(`<html><title>Space Octopus - Complete schematic - One page</title><style>@page{size:${widthMm}mm ${heightMm}mm;margin:0}html,body{margin:0;padding:0}svg{display:block;width:${widthMm}mm;height:${heightMm}mm}</style>${svg}</html>`);
 await page.evaluate(()=>document.fonts.ready);
 await page.pdf({path:base+'.pdf',printBackground:true,preferCSSPageSize:true});
}finally{await browser.close();}
const audit={sourceCircuitSha256:createHash('sha256').update(sourceBytes).digest('hex'),sourceUnchanged:fs.readFileSync('output/space-octopus.circuit.json').equals(sourceBytes),schematicComponents:actual.length,schematicPorts:rendered.filter(e=>e.type==='schematic_port').length,schematicTraces:rendered.filter(e=>e.type==='schematic_trace').length,netLabels:rendered.filter(e=>e.type==='schematic_net_label').length,sections:panels.map(p=>({name:p.name,components:p.components})),presentationOnly:true,electricalConnectionsChanged:false,netLabelConvention:'Identical labels represent the same electrical net throughout the single page.',pdf:base+'.pdf'};
fs.writeFileSync('output/full-schematic-export-audit.json',JSON.stringify(audit,null,2)+'\n');
console.log(JSON.stringify(audit,null,2));
