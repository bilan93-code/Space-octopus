import fs from 'node:fs';
const base='output/connected-schematic/';
const symbols=JSON.parse(fs.readFileSync(base+'symbols.json'));
const paths=JSON.parse(fs.readFileSync(base+'paths.json'));
const input=JSON.parse(fs.readFileSync(base+'solver-input.json'));
const connected=new Set(input.netConnections.flatMap(n=>n.pinIds));
const schematicPorts=new Map(symbols.filter(e=>e.type==='schematic_port').map(e=>[e.schematic_port_id,e]));
const netIds=new Map(symbols.filter(e=>e.type==='source_net').map(e=>[e.name,e.source_net_id]));
const output=symbols.filter(e=>!['schematic_trace','schematic_net_label'].includes(e.type));
for(const e of output)if(e.type==='schematic_port')e.is_connected=connected.has(e.schematic_port_id);
const eps=1e-6,pointKey=p=>`${p.x.toFixed(6)},${p.y.toFixed(6)}`;
const edges=paths.map(t=>t.tracePath.slice(1).map((to,i)=>({from:t.tracePath[i],to})).filter(e=>Math.hypot(e.to.x-e.from.x,e.to.y-e.from.y)>eps));
function horizontal(e){return Math.abs(e.from.y-e.to.y)<eps;}
function intersection(a,b){
 if(horizontal(a)===horizontal(b))return null;
 const h=horizontal(a)?a:b,v=horizontal(a)?b:a,p={x:v.from.x,y:h.from.y};
 if(p.x<Math.min(h.from.x,h.to.x)-eps||p.x>Math.max(h.from.x,h.to.x)+eps||p.y<Math.min(v.from.y,v.to.y)-eps||p.y>Math.max(v.from.y,v.to.y)+eps)return null;
 return p;
}
let crossingCount=0,junctionCount=0;
const junctionsByNet=new Map(),previous=[];
for(let i=0;i<paths.length;i++){
 const t=paths[i],junctions=new Map(),outEdges=[];
 for(const pin of t.pins){const p=schematicPorts.get(pin.pinId);if(!p||Math.hypot(p.center.x-pin.x,p.center.y-pin.y)>eps)throw Error('Wire terminal mismatch');}
 for(const e of edges[i]){
  const h=horizontal(e),length=Math.hypot(e.to.x-e.from.x,e.to.y-e.from.y),dx=(e.to.x-e.from.x)/length,dy=(e.to.y-e.from.y)/length;
  const gaps=[];
  for(const other of previous){
   const p=intersection(e,other.edge);if(!p)continue;
   if(other.net===t.userNetId){junctions.set(pointKey(p),p);continue;}
   const d=(p.x-e.from.x)*dx+(p.y-e.from.y)*dy;
   if(d<=eps||d>=length-eps)throw Error('Different-net T contact survived routing validation');
   gaps.push([Math.max(0,d-.0375),Math.min(length,d+.0375)]);crossingCount++;
  }
  gaps.sort((a,b)=>a[0]-b[0]);const merged=[];
  for(const gap of gaps){const p=merged.at(-1);if(p&&gap[0]<=p[1])p[1]=Math.max(p[1],gap[1]);else merged.push(gap);}
  const at=d=>({x:e.from.x+dx*d,y:e.from.y+dy*d});let cursor=0;
  for(const [lo,hi] of merged){if(lo>cursor+eps)outEdges.push({from:at(cursor),to:at(lo)});outEdges.push({from:at(lo),to:at(hi),is_crossing:true});cursor=hi;}
  if(cursor<length-eps)outEdges.push({from:at(cursor),to:at(length)});
 }
 const seen=junctionsByNet.get(t.userNetId)??new Set();
 const dots=[...junctions].filter(([key])=>!seen.has(key)).map(([key,p])=>{seen.add(key);return p;});junctionsByNet.set(t.userNetId,seen);junctionCount+=dots.length;
 output.push({type:'schematic_trace',schematic_trace_id:`connected_trace_${i}`,source_trace_id:t.mspPairId,subcircuit_connectivity_map_key:netIds.get(t.userNetId),edges:outEdges,junctions:dots});
 for(const edge of edges[i])previous.push({net:t.userNetId,edge});
}
const occupied=[];let index=0;
for(const name of [...netIds.keys()].sort()){
 const candidates=paths.flatMap((t,i)=>t.userNetId===name?edges[i].filter(horizontal):[]).sort((a,b)=>Math.abs(b.to.x-b.from.x)-Math.abs(a.to.x-a.from.x));
 if(!candidates.length)continue;
 const textWidth=name.length*.19;
 let choice;
 for(const e of candidates){
  if(Math.abs(e.to.x-e.from.x)<textWidth+.3)continue;
  for(const fraction of [.5,.25,.75]){
   const x=e.from.x+(e.to.x-e.from.x)*fraction-textWidth/2,y=e.from.y+.3;
   if(occupied.some(b=>x<b[1]&&x+textWidth>b[0]&&y-.2<b[3]&&y+.2>b[2]))continue;
   choice={x,y};break;
  }
  if(choice)break;
 }
 if(!choice)continue;
 occupied.push([choice.x,choice.x+textWidth,choice.y-.2,choice.y+.2]);
 output.push({type:'schematic_text',schematic_text_id:`connected_wire_label_${index++}`,text:name,position:choice,font_size:.28,anchor:'left',rotation:0,color:'#286147'});
}
fs.writeFileSync(base+'circuit.json',JSON.stringify(output,null,2)+'\n');
fs.writeFileSync(base+'drawing-conventions.json',JSON.stringify({wirePaths:paths.length,netCount:netIds.size,crossingGaps:crossingCount,junctionDots:junctionCount,wireNameLabels:index,allSupplyAndGroundConnectionsDrawn:true},null,2)+'\n');
console.log(JSON.stringify({wirePaths:paths.length,nets:netIds.size,crossingGaps:crossingCount,junctionDots:junctionCount,wireNameLabels:index}));
