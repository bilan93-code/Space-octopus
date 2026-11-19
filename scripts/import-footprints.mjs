import fs from 'node:fs';
import path from 'node:path';
import parse from 's-expression';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { KicadFootprintToCircuitJsonConverter } from 'kicad-to-circuit-json';
const parts = ['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n => JSON.parse(fs.readFileSync(`data/${n}.json`)));
fs.mkdirSync('footprints/kicad', {recursive:true});
const append=process.argv.includes('--append');
const requested=process.argv.slice(2).filter(a=>!a.startsWith('--'));
const catalog = append?JSON.parse(fs.readFileSync('footprints/catalog.json')):{}, provenance = append?JSON.parse(fs.readFileSync('footprints/provenance.json')):[];
for (const key of [...new Set(requested.length?requested:parts.map(p=>p.footprint))].sort()) {
 const [lib,name]=key.split('/');
 const file=`footprints/kicad/${lib}__${name}.kicad_mod`;
 const tiLand=key==='Package_DFN_QFN/TI_RTA0040B_DRV8353';
 const url=tiLand?'https://www.ti.com/lit/ds/symlink/drv8353.pdf':`https://raw.githubusercontent.com/KiCad/kicad-footprints/master/${lib}.pretty/${name}.kicad_mod`;
 if(!fs.existsSync(file)) {
  try { const local=`/usr/share/kicad/footprints/${lib}.pretty/${name}.kicad_mod`; if(fs.existsSync(local)) fs.copyFileSync(local,file); else execFileSync('curl',['-fsSL','--retry','2','--max-time','25',url,'-o',file],{stdio:'pipe'}); }
  catch(e) { console.error('MISSING',key); process.exitCode=1; continue; }
 }
 const raw=fs.readFileSync(file,'utf8');
 // KiCad's old 3D model 'at' syntax is unsupported by this converter. Remove
 // model blocks only; retain original source verbatim for provenance/audit.
 const convertedText=raw.replace(/\(model[\s\S]*?(?=\n\))/g,'');
 const c=new KicadFootprintToCircuitJsonConverter();
 try {c.addFile(`${name}.kicad_mod`,convertedText);c.runUntilFinished();}
 catch(e) {console.error('CONVERT FAILED',key,e.message);process.exitCode=1;continue;}
 const elements=c.getOutput().filter(e=>['pcb_smtpad','pcb_plated_hole','pcb_hole','pcb_silkscreen_path','pcb_silkscreen_line','pcb_silkscreen_circle','pcb_silkscreen_text','pcb_courtyard_outline'].includes(e.type));
 for(const e of elements) {
  if(e.port_hints)e.port_hints=e.port_hints.flatMap(p=>[p,`pin${p}`]);
  // IDs and parent links belong to each instantiated component, not the library.
  for(const k of Object.keys(e)) if(k.endsWith('_id'))delete e[k];
 }
 const pads=elements.filter(e=>e.type==='pcb_smtpad'||e.type==='pcb_plated_hole');
 const bounds=[...pads,...elements.filter(e=>e.type==='pcb_hole')].map(p=>{const x=p.x??0,y=p.y??0,w=p.width??p.outer_width??p.outer_diameter??p.hole_diameter??1,h=p.height??p.outer_height??p.outer_diameter??p.hole_diameter??1;return [x-w/2,y-h/2,x+w/2,y+h/2]});
 const box=[Math.min(...bounds.map(b=>b[0])),Math.min(...bounds.map(b=>b[1])),Math.max(...bounds.map(b=>b[2])),Math.max(...bounds.map(b=>b[3]))];
 // Include silk extent (e.g. electrolytic body, headers) in placement clearance.
 for(const e of elements)for(const p of [...(e.route??e.points??[]),...(e.center?[e.center]:[])]){const r=e.radius??0;box[0]=Math.min(box[0],p.x-r);box[1]=Math.min(box[1],p.y-r);box[2]=Math.max(box[2],p.x+r);box[3]=Math.max(box[3],p.y+r)}
 const tree=parse(raw);
 // KiCad roundrect_rratio is a fraction of the shortest pad dimension. The
 // converter currently copies it into corner_radius without converting to mm.
 for(const e of elements.filter(e=>(e.type==='pcb_smtpad'&&e.shape==='rect')||(e.type==='pcb_plated_hole'&&e.shape==='circular_hole_with_rect_pad'))){
  const pad=tree.find(p=>Array.isArray(p)&&p[0]==='pad'&&p.some(a=>Array.isArray(a)&&a[0]==='at'&&Math.abs(+a[1]-e.x)<1e-6&&Math.abs(-a[2]-e.y)<1e-6));
  const ratio=pad?.find(p=>Array.isArray(p)&&p[0]==='roundrect_rratio');
  const r=ratio?+ratio[1]*Math.min(e.width??e.rect_pad_width,e.height??e.rect_pad_height):0;
  if(e.type==='pcb_smtpad')e.corner_radius=r;else e.rect_border_radius=r;
 }
 const courtyard=[];
 for(const e of tree) {
  if(!Array.isArray(e)||!['fp_line','fp_rect','fp_circle'].includes(e[0])) continue;
  const layer=e.find(v=>Array.isArray(v)&&v[0]==='layer');
  if(!layer||String(layer[1]).replaceAll('"','')!=='F.CrtYd')continue;
  const xy=e.filter(v=>Array.isArray(v)&&['start','end','center'].includes(v[0])).map(v=>[+v[1],-(+v[2])]);
  if(e[0]==='fp_circle') {const [a,b]=xy;const r=Math.hypot(a[0]-b[0],a[1]-b[1]);courtyard.push([a[0]-r,a[1]-r],[a[0]+r,a[1]+r]);} else courtyard.push(...xy);
 }
 for(const [x,y] of courtyard){box[0]=Math.min(box[0],x);box[1]=Math.min(box[1],y);box[2]=Math.max(box[2],x);box[3]=Math.max(box[3],y)}
 catalog[key]={elements,box,pads:[...new Set(pads.flatMap(p=>p.port_hints??[]).filter(n=>/^\d+$/.test(n)))].sort((a,b)=>+a-+b)};
 const previous=provenance.findIndex(p=>p.footprint===key);if(previous>=0)provenance.splice(previous,1);
 provenance.push({footprint:key,url,file,source:tiLand?'TI RTA0040B, docs/evidence/ti-drv8353.pdf':fs.existsSync(`/usr/share/kicad/footprints/${lib}.pretty/${name}.kicad_mod`)?'installed KiCad library':'GitHub KiCad library',sha256:createHash('sha256').update(raw).digest('hex'),warnings:c.getWarnings()});
 console.log(key,catalog[key].pads.join(','));
}
fs.writeFileSync('footprints/catalog.json',JSON.stringify(catalog,null,2)+'\n');
fs.writeFileSync('footprints/provenance.json',JSON.stringify(provenance,null,2)+'\n');
