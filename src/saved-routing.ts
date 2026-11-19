import saved from '../data/routed-traces.json';
import {attachRouteContacts} from './route-contacts';
import kelvinRouting from '../data/kelvin-routing.json';
import {parts,placement,footprints} from './design';
import {geometry} from './geometry';
export const routingRules={isViaInPadAllowed:true,minTraceWidth:.15,nominalTraceWidth:.25,minTraceToPadEdgeClearance:.2,minPadEdgeToPadEdgeClearance:.2,minBoardEdgeClearance:.5,minViaHoleDiameter:.2,minViaPadDiameter:.4,minTraceToHoleEdgeClearance:.5};
export const groundPlaneRules={layer:'inner1' as const,clearance:.25,boardEdgeMargin:.6,cutoutMargin:.6};
export const groundPlaneLayers=['top','inner1','bottom'] as const;
export const busCapacitorAntipadRadiusMm=2.2;
export function getDesignSignature(){
 const value=JSON.stringify({routingGeometryVersion:11,parts:parts.map(p=>({ref:p.ref,pins:p.pins,footprint:p.footprint,dnp:p.dnp})),placement,footprints,geometry,routingRules,groundPlaneRules,groundPlaneLayers,busCapacitorAntipadRadiusMm,kelvinRouting,powerPlaneLayer:'inner2'});
 let h1=2166136261,h2=5381;for(let i=0;i<value.length;i++){h1=Math.imul(h1^value.charCodeAt(i),16777619);h2=Math.imul(h2,33)^value.charCodeAt(i);}
 return `${(h1>>>0).toString(16)}${(h2>>>0).toString(16)}`;
}
export const hasSavedRouting=saved.traces.length>0;
const netNames=(saved as any).netNamesById??Object.fromEntries([...new Set(parts.flatMap(p=>Object.values(p.pins).filter(Boolean)))].sort().map((n,i)=>[`source_net_${i}`,n]));
const viaMap=new Map<string,any>();
for(const t of saved.traces as any[])for(const p of t.route)if(p.route_type==='via'){
 const key=`${t.connection_name}:${p.x.toFixed(7)}:${p.y.toFixed(7)}`;
 viaMap.set(key,{x:p.x,y:p.y,hole:p.via_hole_diameter??p.hole_diameter??.3,diameter:p.via_diameter??p.outer_diameter??.6,net:netNames[t.connection_name]});
}
export const savedVias=[...viaMap.values()];
export function wireTraces(){
 const output:any[]=[];
 for(const t of saved.traces as any[]){let chunk:any[]=[],index=0;
  const flush=()=>{if(chunk.length>=2)output.push({...t,pcb_trace_id:`${t.pcb_trace_id}_wire${index++}`,route:chunk});chunk=[];};
  for(const p of t.route){
   if(p.route_type!=='wire'){flush();continue;}
   const last=chunk.at(-1);
   if(last&&last.layer!==p.layer)flush();
   // Coincident wire vertices describe a copper disk. Retain it: the disk
   // can be a real junction between neighboring trace end caps.
   const point={...p};delete point.start_pcb_port_id;delete point.end_pcb_port_id;
   chunk.push(point);
  }
  flush();
 }
 return output;
}
// Reuse routes only while the pin map, footprint geometry, placement, outline
// and routing rules match. A changed design must be routed and audited again.
export async function savedRoutingAlgorithm(_input:any,json:any[]){
 if(saved.signature!==getDesignSignature())throw new Error('Saved copper is stale. Run npm run route to regenerate it.');
 const listeners:Record<string,(e:any)=>void>={};
 let stopped=false;
 return {on:(name:string,cb:(e:any)=>void)=>{listeners[name]=cb;},start:()=>queueMicrotask(()=>{if(!stopped)listeners.complete?.({type:'complete',traces:attachRouteContacts(wireTraces(),json)});}),stop:()=>{stopped=true;}};
}
