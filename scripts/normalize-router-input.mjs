// A package can expose several physical pads for one electrical pin (TO-263
// drain/tab, thermal EPs). These are fixed nets, never assignable jumpers.
export function normalizeRouterInput(input,json){
 const portNet=new Map();
 for(const t of json.filter(x=>x.type==='source_trace'))if(t.connected_source_net_ids?.length===1)for(const p of t.connected_source_port_ids??[])portNet.set(p,t.connected_source_net_ids[0]);
 for(const c of json.filter(x=>x.type==='source_component'))for(const ids of c.internally_connected_source_port_ids??[]){const ns=[...new Set(ids.map(id=>portNet.get(id)).filter(Boolean))];if(ns.length>1)throw new Error('Internally connected package pads have conflicting nets');if(ns.length===1)for(const id of ids)portNet.set(id,ns[0]);}
 const pcbNet=new Map(json.filter(x=>x.type==='pcb_port').map(p=>[p.pcb_port_id,portNet.get(p.source_port_id)]));
 let fixedPads=0,expandedHoles=0;
 for(const o of input.obstacles){
  if(o.isNonPlatedHole){o.width+=1;o.height+=1;expandedHoles++;}
  const pid=o.circuitJsonMetadata?.pcb_port_id;
  if(pid){const net=pcbNet.get(pid);if(net&&!o.connectedTo?.includes(net)){o.connectedTo=[...(o.connectedTo??[]),net];fixedPads++;}delete o.offBoardConnectsTo;o.netIsAssignable=false;}
 }
 // The canonical board already requires filled/capped via-in-pad fabrication.
 input.allowViaInPad=true;input.allowBlindAndBuriedVias=false;
 return {fixedPads,expandedHoles};
}
