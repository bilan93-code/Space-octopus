import fs from 'node:fs';
import {isFitted} from './assembly-parts.mjs';
import {createHash} from 'node:crypto';
const tscircuitOnly=process.argv.includes('--tscircuit-only');
const read=f=>JSON.parse(fs.readFileSync(f));
const copper=read('output/copper-audit.json');
const json=read('output/space-octopus.circuit.json');
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n=>read(`data/${n}.json`));
const netNames=new Map(json.filter(e=>e.type==='source_net').map(e=>[e.source_net_id,e.name]));
const pours=json.filter(e=>e.type==='pcb_copper_pour');
const groundLayers=['top','inner1','bottom'];
const regionsByLayer=(net,layers)=>Object.fromEntries(layers.map(layer=>[layer,pours.filter(e=>e.layer===layer&&netNames.get(e.source_net_id)===net).length]));
const groundRegionsByLayer=regionsByLayer('GND',groundLayers),powerRegionsByLayer=regionsByLayer('VBUS',['inner2']);
const savedBackbone=fs.existsSync('output/power-backbone-audit.json')?read('output/power-backbone-audit.json'):null;
const circuitSha=createHash('sha256').update(fs.readFileSync('output/space-octopus.circuit.json')).digest('hex');
if(copper.circuitJsonSha256!==circuitSha)throw new Error('Regenerate the copper audit on the current Circuit JSON before generating status.');
const backbone=savedBackbone?.circuitJsonSha256===circuitSha?savedBackbone:null;
// Older audits allowed GND fills and did not record the two parallel input tests.
const allFillsExcluded=backbone?.method?.includes('Both VBUS and GND load terminals must connect even with every fill removed.')??false;
const powerBackbone={
 auditStatus:backbone?.status??'not checked',source:backbone?.source??null,
 minimumIncludedTrackWidthMm:backbone?.minimumIncludedTrackWidthMm??null,allFillsExcluded,
 checks:['GND','VBUS'].map(net=>{
  const check=backbone?.checks?.find(c=>c.net===net);
  return {...check,net,passed:check?.passed??null,verified:check?.passed===true&&allFillsExcluded&&backbone.minimumIncludedTrackWidthMm>=2};
 }),
 brakeFuseFeed:{...backbone?.brakeFuseFeed,verified:backbone?.brakeFuseFeed?.passed===true},
 parallelInputPaths:[['inner2',3.0],['bottom',2.4]].map(([layer,minimumTrackWidthMm])=>{
  const check=backbone?.parallelInputPaths?.find(c=>c.net==='VBUS'&&c.from==='J1.1'&&c.to==='C1.1'&&c.layer===layer&&c.minimumTrackWidthMm===minimumTrackWidthMm);
  return {...check,layer,minimumTrackWidthMm,passed:check?.passed??null,verified:check?.passed===true};
 }),
 method:backbone?.method??null,limitations:backbone?.limitations??null,
};
const powerTestsVerified=[...powerBackbone.checks,...powerBackbone.parallelInputPaths,powerBackbone.brakeFuseFeed].every(c=>c.verified);
const testResult=c=>c.passed===false?'failed':c.verified?'verified':'not verified in the saved audit';
const groundFillSummary=groundLayers.map(layer=>`${layer}: ${groundRegionsByLayer[layer]}`).join(', ');
const native=json.filter(e=>e.type.includes('error'));const nativeCounts={};for(const e of native)nativeCounts[e.type]=(nativeCounts[e.type]??0)+1;
const status={stage:copper.unconnectedNetCount?'engineering draft — routing incomplete':'engineering draft — routing connected',fabricationReady:false,inventoryItems:parts.length,populatedComponents:parts.filter(isFitted).length,nets:copper.nets,fullyConnectedNets:copper.fullyConnectedNets,unconnectedNetCount:copper.unconnectedNetCount,traceObjects:copper.tracks,vias:copper.vias,groundRegions:Object.values(groundRegionsByLayer).reduce((sum,n)=>sum+n,0),powerRegions:powerRegionsByLayer.inner2,groundRegionsByLayer,powerRegionsByLayer,powerBackbone,shorts:copper.shortCount,clearanceFindings:copper.clearanceViolationCount,edgeFindings:copper.edgeViolationCount,holeAndHardwareFindings:copper.holeViolationCount,nativeDiagnosticCounts:nativeCounts,circuitJsonSha256:circuitSha,routingBackend:'Explicit power, fanout and Kelvin routing plus local grid finishing, replayed through tscircuit; audited native copper-pour primitives',remainingWork:[...(copper.unconnectedNetCount?['Connect the listed open net islands.']:[]),...(!powerTestsVerified?['Verify the wide GND and VBUS backbones with every fill excluded and both VBUS input branches and the F2 via array.']:[]),'Review switching loops, gate/source inductance and differential signal timing/impedance.','Verify the upstream input protection and capacitor precharge on the future battery PCB.','Confirm the proposed F2 land pattern, DC interrupt rating, hot derating and repetitive pulse life.','Verify the separate 4.7 ohm ±5%, 300 W brake resistor PCB, harness and cooling against measured braking energy.','Size power copper and via arrays for the actual current waveform, stackup and cooling.','Confirm provisional manufacturer packages, connectors and harness pin numbering.','Verify motor standoffs, underside components, encoder and axial assembly fit.']};
status.kicadContinuation=tscircuitOnly?'This publication uses the tscircuit design.':'See native KiCad parity and DRC reports.';
fs.writeFileSync('output/engineering-status.json',JSON.stringify(status,null,2)+'\n');
const attempts=fs.existsSync('output/routing-attempts.json')?read('output/routing-attempts.json'):{};
attempts.nativeAttemptScope='Native autorouter attempts apply to the earlier Rev A layout. The outward-facing revision preserves audited copper and uses checked local rerouting.';
attempts.localGridFinishing={outcome:status.unconnectedNetCount?'Routing incomplete':'Complete verified routing, replayed through the tscircuit custom-router API',selectedConnectedNets:status.fullyConnectedNets,selectedOpenNets:status.unconnectedNetCount,copperClearanceMm:.2,boardAndNpthClearanceMm:.5,configuredGridMm:[.2,.1,.05],traceObjects:status.traceObjects,vias:status.vias,circuitJsonSha256:status.circuitJsonSha256};
attempts.groundFill={engine:'Audited polygon geometry replayed by native CopperPour primitives',referenceLayer:'inner1',groundLayers,busLayer:'inner2',clearanceMm:.25,edgeMarginMm:.6,cutoutMarginMm:.6,geometryChecked:copper.status==='passed',groundRegions:status.groundRegions,powerRegions:status.powerRegions,groundRegionsByLayer,powerRegionsByLayer,automaticSolverLimitation:'Self-intersecting automatic fill rings required explicit audited BRep regions.'};
attempts.fabricationReady=false;
if(fs.existsSync('data/native-routing-review.json'))attempts.motorMountNativeComparisons=read('data/native-routing-review.json');
fs.writeFileSync('output/routing-attempts.json',JSON.stringify(attempts,null,2)+'\n');
const q=s=>'"'+String(s??'').replaceAll('"','""')+'"';
const rows=[['Net','Island','Physical terminals']];for(const n of copper.unconnectedNets)for(const [i,pins] of n.islands.entries())rows.push([n.net,i+1,[...new Set(pins)].sort().join('; ')]);
fs.writeFileSync('output/unrouted-net-islands.csv',rows.map(r=>r.map(q).join(',')).join('\n')+'\n');
fs.writeFileSync('docs/TSCIRCUIT_STATUS.md',`# Current tscircuit review status

${status.fullyConnectedNets}/${status.nets} electrical nets are physically connected; ${status.unconnectedNetCount} remain split into islands. The independent geometry audit found ${status.shorts} shorts, ${status.clearanceFindings} copper-clearance findings, ${status.edgeFindings} edge findings and ${status.holeAndHardwareFindings} hole/hardware findings.

The draft has ${status.traceObjects} trace objects, ${status.vias} vias and ${status.groundRegions} GND-fill regions (${groundFillSummary}), with ${status.powerRegions} VBUS-fill regions on inner2. Pours are counted by their source net and layer. See [the remaining islands](../output/unrouted-net-islands.csv), [native diagnostics](../output/render-diagnostics.json), [the copper audit](../output/copper-audit.json) and [validation results](../output/validation-results.json). ${status.unconnectedNetCount?'Native DRC and connectivity checks do not pass while those open connections remain.':'See validation results for the native DRC and independent connectivity checks.'}

The [power-backbone checker](../scripts/check-power-backbone.py) requires separate wide GND and VBUS backbones using pads, plated barrels and tracks at least 2 mm wide, with **all copper fills excluded**. It also tests both VBUS routes from J1.1 to the positive terminal of C1 and the F2 transfer through the inner2 rail. Results below come from [the saved audit](../output/power-backbone-audit.json); missing tests or missing all-fill exclusion evidence remain unverified.

| Distinct geometric test | Recorded result |
|---|---|
| Wide GND backbone, all fills excluded | ${testResult(powerBackbone.checks[0])} |
| Wide VBUS backbone, all fills excluded | ${testResult(powerBackbone.checks[1])} |
| J1.1 to C1.1 on inner2, 4.5 mm launch into ≥3.0 mm copper | ${testResult(powerBackbone.parallelInputPaths[0])} |
| J1.1 to C1.1 on bottom, ≥2.4 mm copper | ${testResult(powerBackbone.parallelInputPaths[1])} |
| F2 input via array and F2 output to J11.1 | ${testResult(powerBackbone.brakeFuseFeed)} |

**Engineering qualification remains open.** The layout includes parallel VBUS paths with a 4.5 mm inner2 launch feeding a 3 mm rail and a 2.4 mm bottom rail, wide phase/brake copper and parallel through-via arrays. Local converter/bypass cells and dedicated shunt pickups have independent checks. Current capacity, switching behavior, differential timing, thermal design, provisional packages and motor axial fit remain release gates. Filled and capped via-in-pad manufacture is required.

J1.1 connects directly to VBUS. Input protection and precharge belong on the upstream battery PCB. F2 is the proposed surface-mount fuse for the 4.7 Ω ±5%, 300 W resistor on the separate braking PCB at J11. Its land pattern, DC breaking capacity and pulse performance require confirmation.

The board has ${status.populatedComponents} populated component positions. J1, J2 and J11 are bare plated wire terminals. The [3D model report](../output/3d-status.json) identifies parts shown with representative bodies, including F2. D2 models the required 2 mm lead trim. DNP devices and bare PCB features have no body model. ${tscircuitOnly?'The editable design for this publication is the tscircuit project.':'The current routed KiCad derivative is in [output/kicad](../output/kicad/README.md); the root KiCad folder is an earlier snapshot.'}
`);
console.log(`${status.fullyConnectedNets}/${status.nets} nets connected; ${status.unconnectedNetCount} incomplete. Geometry: ${status.shorts} shorts, ${status.clearanceFindings} clearance findings.`);
