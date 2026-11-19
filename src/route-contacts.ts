/** Identify physical pin contacts without extending audited wire geometry.
 * Separate tiny contact anchors lie inside the existing pad electrodes.
 */
export function attachRouteContacts(traces:any[],json:any[]){
 const ports=new Map(json.filter(a=>a.type==='pcb_port').map(a=>[a.pcb_port_id,a]));
 const sourceTraces=json.filter(a=>a.type==='source_trace');
 const byPort=new Map(sourceTraces.flatMap(a=>a.connected_source_port_ids.map((p:string)=>[p,a])));
 for(const c of json.filter(a=>a.type==='source_component'))for(const ids of c.internally_connected_source_port_ids??[]){
  const source=ids.map((id:string)=>byPort.get(id)).find(Boolean);
  if(source)for(const id of ids)if(!byPort.has(id))byPort.set(id,source);
 }
 const byTrace=new Map(sourceTraces.map(a=>[a.source_trace_id,a]));
 const pads=json.filter(a=>['pcb_smtpad','pcb_plated_hole'].includes(a.type)&&a.pcb_port_id).map(p=>{
  const port=ports.get(p.pcb_port_id);const source=byPort.get(port?.source_port_id) as any;
  return {p,port,source,net:source?.connected_source_net_ids?.[0]};
 });
 const attached=new Set<string>();
 const touches=(point:any,p:any)=>{
  if(!(p.layers??[p.layer]).includes(point.layer))return false;
  const theta=-(p.rect_ccw_rotation??p.ccw_rotation??0)*Math.PI/180;
  const dx=point.x-p.x,dy=point.y-p.y,x=dx*Math.cos(theta)-dy*Math.sin(theta),y=dx*Math.sin(theta)+dy*Math.cos(theta),r=(point.width??.15)/2;
  if(p.shape==='circle')return Math.hypot(x,y)<(p.radius??p.outer_diameter/2)+r-1e-6;
  const w=p.width??p.rect_pad_width??p.outer_width??p.outer_diameter,h=p.height??p.rect_pad_height??p.outer_height??w;
  return Math.hypot(Math.max(0,Math.abs(x)-w/2),Math.max(0,Math.abs(y)-h/2))<r-1e-6;
 };
 const anchored=new Set<string>();
 for(const trace of traces){
  const net=trace.connection_name;let firstSource:any;
  for(const point of [trace.route[0],trace.route.at(-1)]){
   const candidates=pads.filter(a=>a.net===net&&touches(point,a.p)).sort((a,b)=>Math.hypot(a.p.x-point.x,a.p.y-point.y)-Math.hypot(b.p.x-point.x,b.p.y-point.y));
   if(!candidates.length)continue;
   const contact=candidates[0];
   delete point.start_pcb_port_id;delete point.end_pcb_port_id;
   anchored.add(trace.pcb_trace_id);firstSource??=contact.source;
  }
  if(firstSource)trace.source_trace_id=firstSource.source_trace_id;
  else if(!byTrace.has(trace.source_trace_id))throw new Error('Wire fragment has no valid source trace.');
 }
 const contacts:any[]=[];
 const usedIds=new Set(traces.map(t=>t.pcb_trace_id));let contactIndex=0;
 for(const {p,port,source,net} of pads){
  if(!source||!net||attached.has(port!.pcb_port_id))continue;
  const base={route_type:'wire',x:p.x,y:p.y,layer:p.layer??p.layers[0],width:.15};
  while(usedIds.has(`pad_contact_${contactIndex}`))contactIndex++;
  contacts.push({type:'pcb_trace',pcb_trace_id:`pad_contact_${contactIndex++}`,source_trace_id:source.source_trace_id,connection_name:net,route:[{...base,start_pcb_port_id:port!.pcb_port_id},{...base,x:p.x+.01,end_pcb_port_id:port!.pcb_port_id}]});
  attached.add(port!.pcb_port_id);
 }
 // Put each physical pin's own contact ahead of remote fragments of its net.
 traces.sort((a,b)=>Number(anchored.has(b.pcb_trace_id))-Number(anchored.has(a.pcb_trace_id)));
 return [...contacts,...traces];
}
