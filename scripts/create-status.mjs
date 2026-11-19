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
const backbone=fs.existsSync('output/power-backbone-audit.json')?read('output/power-backbone-audit.json'):null;
// Older audits allowed GND fills and did not record the two parallel input tests.
const allFillsExcluded=backbone?.method?.includes('Both VBUS and GND load terminals must connect even with every fill removed.')??false;
const powerBackbone={
 auditStatus:backbone?.status??'not checked',source:backbone?.source??null,
 minimumIncludedTrackWidthMm:backbone?.minimumIncludedTrackWidthMm??null,allFillsExcluded,
 checks:['GND','VBUS'].map(net=>{
  const check=backbone?.checks?.find(c=>c.net===net);
  return {...check,net,passed:check?.passed??null,verified:check?.passed===true&&allFillsExcluded&&backbone.minimumIncludedTrackWidthMm>=2};
 }),
 parallelInputPaths:[['inner2',4.5],['bottom',2.4]].map(([layer,minimumTrackWidthMm])=>{
  const check=backbone?.parallelInputPaths?.find(c=>c.layer===layer&&c.minimumTrackWidthMm===minimumTrackWidthMm);
  return {...check,layer,minimumTrackWidthMm,passed:check?.passed??null,verified:check?.passed===true};
 }),
 method:backbone?.method??null,limitations:backbone?.limitations??null,
};
const powerTestsVerified=[...powerBackbone.checks,...powerBackbone.parallelInputPaths].every(c=>c.verified);
const testResult=c=>c.passed===false?'failed':c.verified?'verified':'not verified in the saved audit';
const groundFillSummary=groundLayers.map(layer=>`${layer}: ${groundRegionsByLayer[layer]}`).join(', ');
const native=json.filter(e=>e.type.includes('error'));const nativeCounts={};for(const e of native)nativeCounts[e.type]=(nativeCounts[e.type]??0)+1;
const status={stage:copper.unconnectedNetCount?'engineering draft — routing incomplete':'engineering draft — routing connected',fabricationReady:false,inventoryItems:parts.length,populatedComponents:parts.filter(isFitted).length,nets:copper.nets,fullyConnectedNets:copper.fullyConnectedNets,unconnectedNetCount:copper.unconnectedNetCount,traceObjects:copper.tracks,vias:copper.vias,groundRegions:Object.values(groundRegionsByLayer).reduce((sum,n)=>sum+n,0),powerRegions:powerRegionsByLayer.inner2,groundRegionsByLayer,powerRegionsByLayer,powerBackbone,shorts:copper.shortCount,clearanceFindings:copper.clearanceViolationCount,edgeFindings:copper.edgeViolationCount,holeAndHardwareFindings:copper.holeViolationCount,nativeDiagnosticCounts:nativeCounts,circuitJsonSha256:createHash('sha256').update(fs.readFileSync('output/space-octopus.circuit.json')).digest('hex'),routingBackend:'Explicit power, fanout and Kelvin routing plus local grid finishing, replayed through tscircuit; audited native copper-pour primitives',remainingWork:[...(copper.unconnectedNetCount?['Connect the listed open net islands.']:[]),...(!powerTestsVerified?['Verify the wide GND and VBUS backbones with every fill excluded and both parallel DC_IN paths.']:[]),'Review switching loops, gate/source inductance and differential signal timing/impedance.','Size power copper and via arrays for the actual current waveform, stackup and cooling.','Confirm provisional manufacturer packages, connectors and harness pin numbering.','Verify motor standoffs, underside components, encoder and axial assembly fit.']};
status.kicadContinuation=tscircuitOnly?'Awaiting user approval after tscircuit completion; existing native files are intermediate snapshots.':'See native KiCad parity and DRC reports.';
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

The [power-backbone checker](../scripts/check-power-backbone.py) requires separate wide GND and VBUS backbones using pads, plated barrels and tracks at least 2 mm wide, with **all copper fills excluded**. It also tests each complete J1.1–F1.1 DC_IN path independently. Results below come from [the saved audit](../output/power-backbone-audit.json); missing tests or missing all-fill exclusion evidence remain unverified.

| Distinct geometric test | Recorded result |
|---|---|
| Wide GND backbone, all fills excluded | ${testResult(powerBackbone.checks[0])} |
| Wide VBUS backbone, all fills excluded | ${testResult(powerBackbone.checks[1])} |
| Parallel DC_IN path: inner2, minimum 4.5 mm | ${testResult(powerBackbone.parallelInputPaths[0])} |
| Parallel DC_IN path: bottom, minimum 2.4 mm | ${testResult(powerBackbone.parallelInputPaths[1])} |

**Engineering qualification remains open.** The layout includes parallel 4.5 mm inner2 and 2.4 mm bottom input paths, wide phase/brake copper and parallel through-via arrays. Local converter/bypass cells and dedicated shunt pickups have independent checks. Current capacity, switching behavior, differential timing, thermal design, provisional packages and motor axial fit remain release gates. Filled and capped via-in-pad manufacture is required.

The board has ${status.populatedComponents} populated component positions. J1, J2 and J11 are bare plated wire terminals. Y1, U2 and U13 use representative bodies; D2 models the required 2 mm lead trim. DNP devices and bare PCB features have no body model. ${tscircuitOnly?'Further KiCad work awaits user approval after the tscircuit stage. Existing KiCad files are intermediate snapshots and are excluded from the tscircuit completion archive.':'The current routed KiCad derivative is in [output/kicad](../output/kicad/README.md); the root KiCad folder is an earlier snapshot.'}
`);
console.log(`${status.fullyConnectedNets}/${status.nets} nets connected; ${status.unconnectedNetCount} incomplete. Geometry: ${status.shorts} shorts, ${status.clearanceFindings} clearance findings.`);
