/** Nominal circle/opening tests for component courtyard AABBs.
 * Match the assembly-envelope check's nominal circular placement margin.
 * Copper-to-edge DRC separately uses the actual tessellated board outline.
 */
export function courtyardInsideBoard(box,geometry) {
 const radius=geometry.outerDiameterMm/2-geometry.edgeMarginMm;
 if(box.length!==4||box.some(n=>!Number.isFinite(n))||box[0]>box[2]||box[1]>box[3])return false;
 if([box[0],box[2]].some(x=>[box[1],box[3]].some(y=>Math.hypot(x,y)>radius+1e-7)))return false;
 const opening=geometry.centralOpeningDiameterMm??0;
 if(opening>0){
  const x=Math.max(box[0],Math.min(0,box[2])),y=Math.max(box[1],Math.min(0,box[3]));
  if(Math.hypot(x,y)<opening/2+geometry.edgeMarginMm-1e-7)return false;
  const d=opening/2+geometry.edgeMarginMm;
  if(geometry.centralOpeningPlacementKeepout==='square'&&!(box[2]<=-d||box[0]>=d||box[3]<=-d||box[1]>=d))return false;
 }
 return true;
}
