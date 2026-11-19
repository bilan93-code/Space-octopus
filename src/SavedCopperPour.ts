import {CopperPour} from 'tscircuit';
import saved from '../data/routed-traces.json';

/** Replay audited polygons as native pours. The automatic fill solver
 * produced a self-intersecting ring on this densely routed layout.
 */
export class SavedCopperPour extends CopperPour {
 doInitialPcbCopperPourRender() {
  if(this.root?.pcbDisabled)return;
  const scope=this.getSubcircuit();
  const net=(scope as any).selectOne((this as any)._parsedProps.connectsTo);
  if(!net?.source_net_id)throw new Error('Saved pour has no native source net.');
  const layer=(this as any)._parsedProps.layer;
  const regions=((saved as any).planes??[]).filter((p:any)=>p.layer===layer);
  if(!regions.length)throw new Error('Saved routing has no audited plane regions.');
  for(const region of regions)(this.root!.db.pcb_copper_pour as any).insert({
   shape:'brep',layer,source_net_id:net.source_net_id,
   subcircuit_id:scope.subcircuit_id,covered_with_solder_mask:true,
   brep_shape:region.brep_shape,
  });
 }
}
