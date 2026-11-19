import fs from 'node:fs';
import {getDesignSignature} from '../src/saved-routing';
const input=process.argv[2];if(!input)throw new Error('Provide a routed Circuit JSON or traces JSON file.');
const data=JSON.parse(fs.readFileSync(input,'utf8'));
// Pin identity anchors are regenerated from the current native footprint pads.
const traces=(Array.isArray(data)?data:data.traces).filter((e:any)=>e.type==='pcb_trace'&&!e.pcb_trace_id.startsWith('pad_contact_'));
if(!traces.length)throw new Error('Input has no copper. Existing saved routing was retained.');
if(new Set(traces.map((t:any)=>t.pcb_trace_id)).size!==traces.length)throw new Error('Duplicate copper trace IDs; resolve them before saving.');
// Associate segment geometry with a real source trace in its electrical net.
// Individual Specctra segments do not carry tscircuit's source-trace IDs.
const source=JSON.parse(fs.readFileSync('output/space-octopus.circuit.json','utf8'));
const netNamesById=Object.fromEntries(source.filter((e:any)=>e.type==='source_net').map((e:any)=>[e.source_net_id,e.name]));
const traceByNet=new Map<string,string>();
for(const t of source.filter((e:any)=>e.type==='source_trace'))for(const net of t.connected_source_net_ids??[])if(!traceByNet.has(net))traceByNet.set(net,t.source_trace_id);
for(const t of traces)if(!t.source_trace_id&&t.connection_name)t.source_trace_id=traceByNet.get(t.connection_name);
const inputJson=Array.isArray(data)?data:[];
const viaPositions=new Set(traces.flatMap((t:any)=>t.route.filter((p:any)=>p.route_type==='via').map((p:any)=>`${p.x.toFixed(7)}:${p.y.toFixed(7)}`)));
for(const v of inputJson.filter((e:any)=>e.type==='pcb_via')){
 const key=`${v.x.toFixed(7)}:${v.y.toFixed(7)}`;if(viaPositions.has(key))continue;
 const net=v.source_net_id??source.find((t:any)=>t.type==='source_trace'&&t.source_trace_id===v.source_trace_id)?.connected_source_net_ids?.[0];
 if(!net)throw new Error(`Cannot resolve via ${v.pcb_via_id} net.`);
 const pos={x:v.x,y:v.y};traces.push({type:'pcb_trace',pcb_trace_id:`saved_${v.pcb_via_id}`,connection_name:net,source_trace_id:traceByNet.get(net),route:[{route_type:'wire',...pos,layer:'top',width:.2},{route_type:'via',...pos,from_layer:'top',to_layer:'bottom',layers:['top','inner1','inner2','bottom'],via_diameter:v.outer_diameter,via_hole_diameter:v.hole_diameter},{route_type:'wire',...pos,layer:'bottom',width:.2}]});viaPositions.add(key);
}
const backend=process.argv[3]??'local routing';
// Repeated clipping leaves numerically coincident vertices. Flatten treats
// these as zero-length edges; remove them before native geometry validation.
const toleranceMm=2e-6;let removedVertices=0,droppedRegions=0;
const cleanRing=(ring:any)=>{
 const vertices:any[]=[];
 for(const v of ring.vertices){const previous=vertices.at(-1);if(previous&&Math.hypot(v.x-previous.x,v.y-previous.y)<=toleranceMm)removedVertices++;else vertices.push(v);}
 while(vertices.length>1&&Math.hypot(vertices[0].x-vertices.at(-1).x,vertices[0].y-vertices.at(-1).y)<=toleranceMm){vertices.pop();removedVertices++;}
 return {...ring,vertices};
};
const planes=inputJson.filter((e:any)=>e.type==='pcb_copper_pour').flatMap((p:any)=>{
 if(p.shape!=='brep')return[p];
 const outer_ring=cleanRing(p.brep_shape.outer_ring),inner_rings=p.brep_shape.inner_rings.map(cleanRing).filter((r:any)=>r.vertices.length>=3);
 if(outer_ring.vertices.length<3){droppedRegions++;return[];}
 return[{...p,brep_shape:{outer_ring,inner_rings}}];
});
fs.writeFileSync('data/routed-traces.json',JSON.stringify({signature:getDesignSignature(),backend,netNamesById,traces,planes},null,2)+'\n');
fs.writeFileSync('output/pour-normalization-audit.json',JSON.stringify({source:input,toleranceMm,removedVertices,droppedRegions,verification:'Native rendering and independent copper audits must pass after normalization.'},null,2)+'\n');
console.log(`Removed ${removedVertices} numerically coincident pour vertices; dropped ${droppedRegions} degenerate regions.`);
console.log(`Saved ${traces.length} tscircuit routes; input ${input}; backend ${backend}. Run the copper audit after rendering.`);
