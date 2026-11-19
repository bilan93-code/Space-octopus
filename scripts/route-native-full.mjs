// Independent one-pass comparison using tscircuit's own local router.
import fs from 'node:fs';
import {getSimpleRouteJsonFromCircuitJson} from 'tscircuit';
import {AutoroutingPipelineSolver9_PreloadedTraceGraph,AutoroutingPipelineSolver5} from '@tscircuit/capacity-autorouter';
import {normalizeRouterInput} from './normalize-router-input.mjs';
const dir=process.argv.find(a=>a.startsWith('--output='))?.slice(9)??(process.argv.includes('--pipeline5')?'routing-work/native-pipeline5':'routing-work/native-full');fs.mkdirSync(dir,{recursive:true});
const source=process.argv.find(a=>a.startsWith('--input='))?.slice(8)??'output/space-octopus.circuit.json';
let json=JSON.parse(fs.readFileSync(source));
if(process.argv.includes('--omit-pours'))json=json.filter(e=>e.type!=='pcb_copper_pour');
const firstTraceByNet=new Map();for(const t of json.filter(e=>e.type==='source_trace'))for(const n of t.connected_source_net_ids??[])if(!firstTraceByNet.has(n))firstTraceByNet.set(n,t.source_trace_id);
for(const t of json.filter(e=>e.type==='pcb_trace'))if(!t.source_trace_id&&t.connection_name)t.source_trace_id=firstTraceByNet.get(t.connection_name);
// Raw custom-router records contain inline barrels. Present native wire/via
// primitives and remove zero-length wire chunks before the core geometry API.
if(json.some(e=>e.type==='pcb_trace'&&e.route.some(p=>p.route_type==='via'))){
 const traceNet=new Map(json.filter(e=>e.type==='source_trace').map(e=>[e.source_trace_id,e.connected_source_net_ids?.[0]]));
 const normalized=json.filter(e=>e.type!=='pcb_trace'),viaKeys=new Set(normalized.filter(e=>e.type==='pcb_via').map(v=>`${v.source_net_id}:${v.x.toFixed(7)}:${v.y.toFixed(7)}`));
 for(const t of json.filter(e=>e.type==='pcb_trace')){
  let chunk=[],sequence=0;const net=t.connection_name??traceNet.get(t.source_trace_id);
  const flush=()=>{if(chunk.length>1)normalized.push({...t,pcb_trace_id:t.pcb_trace_id+'_native'+sequence++,route:chunk});chunk=[];};
  for(const p of t.route){
   if(p.route_type==='via'){
    flush();const key=`${net}:${p.x.toFixed(7)}:${p.y.toFixed(7)}`;
    if(!viaKeys.has(key)){normalized.push({type:'pcb_via',pcb_via_id:`native_barrel_${viaKeys.size}`,x:p.x,y:p.y,layers:['top','inner1','inner2','bottom'],outer_diameter:p.via_diameter??.4,hole_diameter:p.via_hole_diameter??.2,source_net_id:net,source_trace_id:t.source_trace_id});viaKeys.add(key);}
    continue;
   }
   const last=chunk.at(-1);if(last&&last.layer!==p.layer)flush();
   const previous=chunk.at(-1);if(!previous||Math.hypot(previous.x-p.x,previous.y-p.y)>1e-8)chunk.push(p);
  }
  flush();
 }
 json=normalized;
}
const {simpleRouteJson:input}=getSimpleRouteJsonFromCircuitJson({circuitJson:json,minTraceWidth:.15,nominalTraceWidth:.25,minTraceToPadEdgeClearance:.2,minPadEdgeToPadEdgeClearance:.2,minBoardEdgeClearance:.5,minTraceToHoleEdgeClearance:.5,minViaHoleDiameter:.2,minViaPadDiameter:.4,ignoreExistingTopLevelPcbRouteState:!process.argv.includes('--resume')});
console.log('Fixed-net input normalization:',normalizeRouterInput(input,json));
fs.writeFileSync(`${dir}/input.json`,JSON.stringify(input,null,2));
console.log(`Routing ${input.connections.length} nets, ${input.obstacles.length} obstacles, ${input.layerCount} layers.`);
const Solver=process.argv.includes('--pipeline5')?AutoroutingPipelineSolver5:AutoroutingPipelineSolver9_PreloadedTraceGraph;
const solver=new Solver(input,{effort:1});let last=0;const start=Date.now();
const limit=Number(process.env.OCTOPUS_ROUTER_MAX_SECONDS??180)*1000;
while(!solver.solved&&!solver.failed&&Date.now()-start<limit){const until=Date.now()+40;do{solver.step();}while(!solver.solved&&!solver.failed&&Date.now()<until);if(Date.now()-last>10000){console.log(Math.round((Date.now()-start)/1000)+'s',solver.getCurrentPhase?.(),solver.computeProgress?.());last=Date.now();}await new Promise(r=>setTimeout(r,0));}
const status={solved:solver.solved,failed:solver.failed,timedOut:!solver.solved&&!solver.failed,error:solver.error,elapsedSeconds:(Date.now()-start)/1000,phaseTimes:solver.timeSpentOnPhase};
if(solver.solved){const traces=solver.getOutputSimplifiedPcbTraces();fs.writeFileSync(`${dir}/traces.json`,JSON.stringify(traces,null,2));status.traces=traces.length;}
fs.writeFileSync(`${dir}/status.json`,JSON.stringify(status,null,2));console.log(status);
process.exitCode=solver.solved?0:1;
