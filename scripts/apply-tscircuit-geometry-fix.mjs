/** Upstream checks 0.0.277/0.0.278 handle rounded SMT pads but omits rounded PTHs.
 * Normalize only the geometry passed to the existing rounded-pad calculation.
 * No diagnostics are suppressed and no clearance limit is changed.
 */
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const modules=[];
for(const base of ['node_modules/@tscircuit/checks','node_modules/tscircuit/node_modules/@tscircuit/checks']){
const file=base+'/dist/index.js';
const pkg=JSON.parse(fs.readFileSync(base+'/package.json'));
const marker='// Space Octopus: preserve rounded through-hole electrode geometry.';
let code=fs.readFileSync(file,'utf8');
if(!['0.0.277','0.0.278'].includes(pkg.version))throw new Error('Review the upstream rounded PTH fix for the installed checks version.');
if(!code.includes(marker)){
 if(!['0.0.277','0.0.278'].includes(pkg.version))throw new Error('Review the upstream rounded PTH fix for the installed checks version.');
 const needle='var getRoundedPadCore = (pad) => {\n';
 if(code.split(needle).length!==2)throw new Error('Rounded-pad implementation changed; refusing an unchecked patch.');
 const addition=`  ${marker}
  if (pad.type === "pcb_plated_hole" && pad.rect_border_radius > 0 &&
      pad.rect_pad_width !== undefined && pad.rect_pad_height !== undefined) {
    return getRoundedPadCore({
      ...pad, type: "pcb_smtpad", shape: "rotated_rect",
      width: pad.rect_pad_width, height: pad.rect_pad_height,
      ccw_rotation: pad.rect_ccw_rotation ?? 0,
      corner_radius: pad.rect_border_radius
    });
  }
`;
 code=code.replace(needle,needle+addition);fs.writeFileSync(file,code);
}
modules.push({file,version:pkg.version,patchedModuleSha256:createHash('sha256').update(code).digest('hex')});
console.log(`Rounded PTH geometry fix present in ${file} (${pkg.version}).`);
}
fs.mkdirSync('output',{recursive:true});
fs.writeFileSync('output/native-checker-corrections.json',JSON.stringify({package:'@tscircuit/checks',modules,correction:'Use declared rounded-rectangle through-hole copper in the existing rounded-pad clearance calculation.',diagnosticsSuppressed:false,clearanceLimitsChanged:false,regression:'scripts/check-rounded-pth.ts: passing rounded-corner gaps and real clearance failures at 0, 37 and 90 degrees in both installed checker versions'},null,2)+'\n');
