/** Draw containing pours before islands nested inside their clearance holes. */
export function orderGerberPours(circuit) {
 const outerArea=p=>{
  const v=p.brep_shape?.outer_ring?.vertices??p.points;
  if(!v)return (p.width??0)*(p.height??0);
  return Math.abs(v.reduce((sum,a,i)=>{const b=v[(i+1)%v.length];return sum+a.x*b.y-b.x*a.y},0))/2;
 };
 return [...circuit.filter(e=>e.type!=='pcb_copper_pour'),...circuit.filter(e=>e.type==='pcb_copper_pour').sort((a,b)=>outerArea(b)-outerArea(a))];
}
