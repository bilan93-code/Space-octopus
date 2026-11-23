import fs from 'node:fs';
import assert from 'node:assert/strict';
const read=p=>JSON.parse(fs.readFileSync(p));
const delivery=read('output/delivery-audit.json'),validation=read('output/validation-results.json'),status=read('output/engineering-status.json'),model=read('output/3d-status.json'),mount=read('output/motor-mount-audit.json'),sim=read('output/simulation/audit.json'),packages=read('output/package-review.json'),backbone=read('output/power-backbone-audit.json');
assert(delivery.status==='passed'&&validation.allPassed&&validation.checks.length===18);
assert(delivery.circuitJsonSha256===status.circuitJsonSha256,'Delivery and engineering status must describe the same circuit.');
assert(backbone.status==='passed'&&backbone.minimumIncludedTrackWidthMm>=2&&backbone.method?.includes('Both VBUS and GND load terminals must connect even with every fill removed.'),'The saved backbone audit must verify wide GND and VBUS paths with all copper fills excluded.');
const wideBackbones=['GND','VBUS'].map(net=>{
 const check=backbone.checks?.find(c=>c.net===net);
 assert(check?.passed===true,`The wide ${net} backbone test must pass with all fills excluded.`);
 return check;
});
assert(backbone.brakeFuseFeed?.passed===true,'The brake fuse requires a connected via array and output branch');
const parallelInputPaths=[['inner2',3.0],['bottom',2.4]].map(([layer,width])=>{
 const check=backbone.parallelInputPaths?.find(c=>c.net==='VBUS'&&c.from==='J1.1'&&c.to==='C1.1'&&c.layer===layer&&c.minimumTrackWidthMm===width);
 assert(check?.passed===true,`The independent VBUS input ${layer} path test must pass at minimum ${width} mm.`);
 return check;
});
const groundLayers=['top','inner1','bottom'];
assert(groundLayers.every(layer=>Number.isInteger(status.groundRegionsByLayer?.[layer]))&&Number.isInteger(status.powerRegionsByLayer?.inner2),'Engineering status must record GND and VBUS fill counts by layer.');
const groundFillSummary=groundLayers.map(layer=>`${layer}: ${status.groundRegionsByLayer[layer]}`).join(', ');
const warnings=Object.entries(delivery.kicadWarnings).map(([k,n])=>`${n} ${k}`).join(', ')||'none';
const coverage=`# tscircuit capability coverage

This board uses locked tscircuit 0.0.3169. The relevant board-design workflows below have outputs and checks. This remains an **engineering draft**, with fabricationReady=false. This does not claim every optional ecosystem feature or physical hardware qualification.

| Workflow | Delivered evidence |
|---|---|
| Editable React/TypeScript design | Source, canonical inventory, footprints, placement and locked dependencies; type checking |
| Electrical capture | ${status.inventoryItems} inventory items, ${status.nets} nets, nine schematic sheets, physical pin maps and mutation checks |
| Circular PCB and motor interface | Ø112 outline, four copper layers, proposed Ø28 aperture, six Ø4.5 holes on Ø104 PCD |
| Routing and native checks | ${status.fullyConnectedNets}/${status.nets} nets connected; zero native tscircuit errors; independent copper, drill, power and Kelvin checks |
| Power and reference copper | ${status.groundRegions} native GND-fill regions (${groundFillSummary}); ${status.powerRegionsByLayer.inner2} VBUS-fill regions on inner2; wide power branches, thermal/transfer arrays and protected sense pickups |
| Wide GND backbone, all fills excluded | Verified: ${wideBackbones[0].required.length} required load-current terminals share one physical island using pads, plated barrels and tracks at least ${backbone.minimumIncludedTrackWidthMm} mm wide |
| Wide VBUS backbone, all fills excluded | Verified: ${wideBackbones[1].required.length} required load-current terminals share one physical island using pads, plated barrels and tracks at least ${backbone.minimumIncludedTrackWidthMm} mm wide |
| Parallel VBUS input path on inner2 | Independently verified complete J1.1–C1.1 path with minimum ${parallelInputPaths[0].minimumTrackWidthMm} mm tracks |
| Parallel VBUS input path on bottom | Independently verified complete J1.1–C1.1 path with minimum ${parallelInputPaths[1].minimumTrackWidthMm} mm tracks |
| Brake branch | F2.1 via array to VBUS inner2 and F2.2 to the brake-resistor wire land at J11.1 |
| Assembly-side revision | All connectors and C1–C5 outward; low-profile motor-facing parts; exact face-envelope checks |
| Silkscreen and cleanup | Readable references, clipped artwork, fabrication-layer references where crowded, and documented copper cleanup |
| Package review | Physical pin presence, ${packages.independentlyComparedMcuPins} MCU pin names independently compared; ${packages.provisionalParts} provisional choices remain explicit |
| 3D | ${model.cadComponents} populated models, ${model.placeholderCount} bounding boxes; offline PCB/motor preview, separate assembly view, GLB and STEP |
| Motor-clearance concept | Proposed ${mount.provisionalGapMm} mm gap; ${mount.minimumModeledMotorClearanceMm.toFixed(2)} mm minimum modeled clearance, including lead trim |
| Analog simulation | ${sim.benches.length} source-derived DC, transient and AC benches; ${sim.checks.length} passing assertions, Circuit JSON graphs, CSV and SPICE decks |
| Signal-path review | Measured planar differential and gate paths with explicit timing/impedance limits |
| BOM and assembly | BOM, physical pin maps, ${status.populatedComponents} pick-and-place rows; wire terminals and bare solder jumper excluded |
| Fabrication review | Four-layer Gerbers, drills, exact routed-aperture arcs, contours and checksums |
| KiCad interoperability | Editable routed derivative, schematics, local footprints/models, native PDFs, schematic ERC, PCB DRC and pad/net/layer parity |
| Regression and delivery | ${validation.checks.length} design checks, fault injections, offline browser verification and a checksum-verified archive |

The power tests above are recorded in [the power-backbone audit](../output/power-backbone-audit.json) by [scripts/check-power-backbone.py](../scripts/check-power-backbone.py), within the existing load-current design check. **All copper fills are excluded** from the GND and VBUS backbone tests; each parallel VBUS input path is also checked without fills. These geometric tests do not qualify current capacity, thermal rise, via current sharing or pulse capability.

Native KiCad warnings: **${warnings}**. See the actual DRC and cleanup reports. The original reviewed archive is retained separately.

The native autorouters were tested and did not finish; verified custom routing is replayed through tscircuit's routing API. Audited BRep regions are replayed through its copper-pour API. Neither is described as a successful automatic native routing/fill result.

The model report identifies representative package bodies and the nominal F2 surface-mount fuse envelope. D2's stock model is trimmed to the required 2 mm lead projection. See the fitted bill of materials for the brake fuse order code. No model appearance establishes manufacturer approval.

The 7 mm gap and spacer bodies are a mounting concept. Replacement cap fasteners, cap clamping, thread engagement, torque, insulation, enclosure/plug space and encoder support remain unapproved. The separate Ø45 encoder must not be assumed to fit through the proposed Ø28 PCB aperture.

Manufacturer package drawings, the selected stackup, differential impedance, switching/source-return loops, current sharing, temperature rise, firmware and physical fault testing remain release gates. The simulations use extracted ideal passive networks and nominal functional models; they are not a complete motor-drive simulation. Datasheet access restrictions are recorded in the package review.

Registry publication and board ordering are external actions outside this local design task.
`;
fs.writeFileSync('docs/TSCIRCUIT_FEATURE_COVERAGE.md',coverage);
const readme=`# Space Octopus motor-controller PCB

Circular tscircuit design with an editable KiCad derivative and an outward-facing interface revision.

**Engineering draft — ${status.fullyConnectedNets}/${status.nets} nets connected; zero native tscircuit and KiCad errors; all ${validation.checks.length} design checks pass.** KiCad warnings: ${warnings}. Fabrication approval remains open.

Native GND-fill counts by layer are ${groundFillSummary}; VBUS has ${status.powerRegionsByLayer.inner2} fill regions on inner2. The [power-backbone audit](output/power-backbone-audit.json), produced by [scripts/check-power-backbone.py](scripts/check-power-backbone.py), verifies the power paths: wide GND and VBUS backbones with **all copper fills excluded** and tracks at least ${backbone.minimumIncludedTrackWidthMm} mm wide; an independent complete VBUS input J1.1–C1.1 path on inner2 at minimum ${parallelInputPaths[0].minimumTrackWidthMm} mm; and an independent complete path on bottom at minimum ${parallelInputPaths[1].minimumTrackWidthMm} mm. These checks do not qualify current capacity or current sharing.

All connectors and C1–C5 face outward. The proposed cap-to-PCB gap is 7 mm, with ${mount.minimumModeledMotorClearanceMm.toFixed(2)} mm minimum modeled clearance after the specified lead trim. Mounting fasteners and the encoder axial assembly require engineering confirmation. This remains an engineering review, not fabrication approval.

Open [the review](output/index.html), [interactive 3D](output/3d.html), [analog checks](output/simulation/index.html), [the mounting drawing](output/Motor112_Mounting_Concept.pdf) and [the capability checklist](docs/TSCIRCUIT_FEATURE_COVERAGE.md). Serve the output directory with \`npm run preview\` and open \`http://localhost:3021\` for the interactive pages.

The populated assembly has ${model.withStepModel} STEP-backed models and zero bounding-box placeholders. The model report documents the representative bodies and their fit assumptions. D2 requires leads trimmed to no more than 2 mm below the motor-facing PCB surface. The nominal source model records that trim.

Install dependencies with \`npm ci\` and \`python -m pip install -r requirements-copper.txt\`. Run \`npm run test\` for type checking, native rendering, 3D generation and the ${validation.checks.length} design checks. KiCad 9 is required for the native derivative/export checks. CadQuery in \`requirements-mechanical.txt\` is only needed to regenerate the vendored trimmed STEP asset.

Use \`output/kicad/SpaceOctopus.kicad_pro\` for the current KiCad project. The root \`kicad/\` directory is the earlier snapshot. The earlier fully reviewed archive is retained separately as \`Space-octopus-RevA-reviewed.zip\`.

The review archive includes source, data, schematics, BOM/assembly files, Gerbers/drills, PDFs, native KiCad, STEP/GLB, simulation decks/results and checksums. Read [the mounting detail](docs/MOTOR_MOUNT_REVISION.md), [package review](output/package-review.json), [electrical audit](output/electrical-audit.json), [copper audit](output/copper-audit.json), [Kelvin audit](output/kelvin-audit.json) and [delivery audit](output/delivery-audit.json).

The native autorouters did not complete this layout. Its audited copper uses tscircuit's custom routing and native copper-pour interfaces. The 13 Arms target and conditional 22 Arms pulse case still require qualification on the chosen stackup and cooling arrangement. Exact provisional packages, connector ratings/harnesses, switching behavior, differential impedance and hardware protection must be reviewed before manufacture.

Source PDFs are in \`docs/\`. Library licenses are in \`licenses/\`; current model provenance is in \`assets/3d/current-model-provenance.json\`.
`;
fs.writeFileSync('README.md',readme);console.log('Updated source-driven feature coverage and project README.');
