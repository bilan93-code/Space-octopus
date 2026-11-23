import fs from 'node:fs';
import assert from 'node:assert/strict';
const read=n=>JSON.parse(fs.readFileSync(`output/${n}`));
const audit=read('tscircuit-completion-audit.json'),status=read('engineering-status.json');
const model=read('3d-status.json'),mount=read('motor-mount-audit.json'),sim=read('simulation/audit.json'),packages=read('package-review.json');
assert(audit.status==='passed'&&audit.circuitJsonSha256===status.circuitJsonSha256);
const text=`# tscircuit stage completed

The current circular actuator-board revision has **${status.fullyConnectedNets}/${status.nets} nets physically connected, zero native tscircuit errors and all 18 design checks passing**. Its source and exported files are checked by [the completion audit](../output/tscircuit-completion-audit.json). This verifies the local CAD/routing outputs for this revision; component and system qualification remain open. It does not claim every optional tscircuit feature has been used. **fabricationReady=false**.

| Workflow | Evidence |
|---|---|
| Editable electrical capture | React/TypeScript source, ${status.inventoryItems} inventory items, ${status.nets} nets, nine schematic sheets, physical pin maps and mutation checks |
| Circular mechanical interface | Ø112 mm board, four copper layers, proposed Ø28 mm aperture, six Ø4.5 mm holes on Ø104 mm PCD |
| Routing | Verified custom copper replayed through tscircuit's routing API; 0.2 mm copper spacing and 0.5 mm edge/drill spacing checked independently |
| Power copper | GND and VBUS load paths verified with all fills removed, using tracks at least 2 mm wide; J1.1 to C1.1 measured on inner2 (4.5 mm launch, 3 mm minimum) and bottom (2.4 mm), with F2 feed vias and its output to J11.1 checked |
| Sense and local layout | Six Kelvin branches, deliberate-fault checks, local converter/bypass layout, assembly envelopes and drilling checks |
| Copper pours | Native copper-pour primitives with audited BRep geometry; nested Gerber polarity regression |
| Native checker correction | Reproducible rounded through-hole pad geometry fix for checks 0.0.277/0.0.278; passing and failing fixtures at three rotations; no diagnostic suppression or changed clearance limits. See [replay notes](NATIVE_REPLAY_GEOMETRY.md). |
| Motor-facing assembly | Connectors and C1–C5 face outward; J1/J2/J11 are direct-solder wire terminals; low devices underneath; proposed ${mount.provisionalGapMm} mm gap and ${mount.minimumModeledMotorClearanceMm.toFixed(2)} mm minimum modeled motor clearance |
| Silkscreen and masks | Readable references, clipped artwork, fabricated reference locations; fiducial mask openings and no paste on bare features |
| 3D | ${model.withStepModel} STEP-backed package models, ${model.placeholderCount} bounding-box placeholders, self-contained GLB, offline motor/PCB viewer and separated assembly view |
| Simulations | ${sim.benches.length} source-derived analog benches and ${sim.checks.length} assertions; SPICE decks, CSV results and graphs |
| Package review | ${packages.independentlyComparedMcuPins} MCU pin names independently compared; ${packages.provisionalParts} provisional choices recorded |
| Timing/path review | Measured differential and gate routes with explicit impedance and switching limits |
| Assembly/fabrication review | BOM, ${status.populatedComponents} pick-and-place rows, four-layer Gerbers, Excellon drills, exact aperture arcs, nine-page schematic PDF and mechanical/mounting PDFs |
| Reproducibility | Locked dependencies, source signatures, 18 design checks, offline browser checks and checksum-verified archive |

Native autorouters were attempted and did not complete this board. The final routes use the custom-router API; automatic fill geometry also required an audited BRep adapter. These outcomes are recorded rather than described as successful automatic routing/filling.

The simulations cover extracted nominal analog networks, not the full inverter, motor or firmware. Current and thermal capability, switching/source-return loops, differential impedance, exact manufacturer packages, harness ratings and physical fault protection require engineering qualification. Filled and capped via-in-pad manufacture is required.

Y1, U2 and U13 use representative model bodies. D2 requires the documented lead trim to at most 2 mm below the motor-facing PCB surface. The 7 mm gap and spacers are a mounting concept: replacement cap fasteners must preserve motor-cap clamping, and thread engagement, torque, insulation, enclosure clearance and encoder support remain unresolved. The separate Ø45 mm encoder must not be assumed to pass through the Ø28 mm PCB opening.

Further **KiCad work awaits user approval**. Existing native files are intermediate exports and are excluded from the tscircuit completion archive. The next KiCad stage can perform native schematic/ERC and board/DRC verification and create a native editable derivative and assembly STEP. No further native work was run to complete this tscircuit stage.

Registry publication, board ordering and physical qualification are outside this local design stage.
`;
fs.writeFileSync('docs/TSCIRCUIT_COMPLETION.md',text);
fs.writeFileSync('docs/TSCIRCUIT_FEATURE_COVERAGE.md',text.replace('# tscircuit stage completed','# tscircuit capability coverage'));
fs.writeFileSync('README.md',`# Space Octopus actuator PCB — tscircuit stage

**${status.fullyConnectedNets}/${status.nets} nets connected; zero native tscircuit errors; all 18 design checks pass.** CAD/routing checks are complete for this revision; component and system qualification remain open. This remains an engineering draft, with fabricationReady=false.

The board is Ø112 mm with a proposed Ø28 mm aperture, four copper layers and six Ø4.5 mm holes on the motor's Ø104 mm PCD. All connectors and C1–C5 face outward. The proposed cap-to-PCB gap is 7 mm; minimum modeled clearance is ${mount.minimumModeledMotorClearanceMm.toFixed(2)} mm after the specified lead trim. Fasteners, cap clamping, encoder fit, current/thermal capability and exact provisional packages require qualification.

The [17 November bulk/watchdog amendment](docs/BULK_WATCHDOG_FIX.md) selects four Rubycon 820µF/100V capacitors and corrects U13 to TPS3431SDRBR. The capacitor maximum seated envelope projects 43mm outward; reserve 46mm with vent clearance. Live stock and overall manufacturing release remain open.\n\nOpen [the board/schematic review](output/index.html), [interactive 3D](output/3d.html), [analog results](output/simulation/index.html), [schematic PDF](output/Space_Octopus_RevA_Schematics.pdf), [mounting concept](output/Motor112_Mounting_Concept.pdf) and [the completed-work checklist](docs/TSCIRCUIT_COMPLETION.md). The [completion audit](output/tscircuit-completion-audit.json) verifies current artifact hashes. The GLB contains ${model.withStepModel} STEP-backed models and no bounding-box placeholders; three model families are representative.

Serve the interactive files with \`npm run preview\`, then open \`http://localhost:3021\`. The viewer runs offline with vendored Three.js.

Install locked dependencies with \`npm ci\` and \`python -m pip install -r requirements-copper.txt\`. Run \`npm test\` to typecheck, render, generate 3D and execute the 18 design checks. Editable source starts at [index.tsx](index.tsx). Saved copper is rejected if pin maps, footprints, placement, outline or routing rules change. CadQuery is needed to regenerate the trimmed diode and maximum-envelope capacitor assets.

To regenerate review outputs, run \`npm run export:review\`, \`npm run export:pdf\`, \`node scripts/check-preview.cjs\`, \`node scripts/create-status.mjs --tscircuit-only\`, \`node scripts/check-delivery.mjs --tscircuit-only\`, \`node scripts/create-tscircuit-completion.mjs\`, then \`python scripts/package-review.py --tscircuit-only\`.

**Further KiCad work awaits approval.** Existing KiCad files and the old assembly STEP are intermediate snapshots and are excluded from this tscircuit archive. Source STEP package assets are included; a complete native assembly STEP is deferred.

Source PDFs are in \`docs/\`. Library licenses are in \`licenses/\`; model provenance is in \`assets/3d/current-model-provenance.json\`. Read the [power](output/power-backbone-audit.json), [Kelvin](output/kelvin-audit.json), [package](output/package-review.json) and [motor-clearance](output/motor-mount-audit.json) reports before engineering review. Gerbers/drills and assembly files are review outputs, not a manufacturing release.
`);
console.log('Wrote tscircuit-only completion report, coverage and README.');
