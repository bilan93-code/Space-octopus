import fs from 'node:fs';
import {isFitted} from './assembly-parts.mjs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const tscircuitOnly=process.argv.includes('--tscircuit-only');

const read=name=>JSON.parse(fs.readFileSync(`output/${name}`));
const sha=path=>createHash('sha256').update(fs.readFileSync(path)).digest('hex');
const circuit=read('space-octopus.circuit.json'),sourceSha=sha('output/space-octopus.circuit.json');
const parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical']
 .flatMap(name=>JSON.parse(fs.readFileSync(`data/${name}.json`)));
const netCount=new Set(parts.flatMap(part=>Object.values(part.pins)).filter(Boolean)).size;
const assemblyCount=parts.filter(isFitted).length;
const checks=[];
function check(name,condition){assert(condition,name);checks.push({name,passed:true});}
const validation=read('validation-results.json'),copper=read('copper-audit.json');
check('All 18 design checks passed on this circuit',validation.allPassed&&validation.circuitJsonSha256===sourceSha&&validation.checks.length===18&&validation.checks.every(c=>c.passed));
check(`${netCount} physically connected nets`,copper.status==='passed'&&copper.fullyConnectedNets===netCount&&copper.unconnectedNetCount===0);
check('Native tscircuit diagnostics are clear',read('render-diagnostics.json').length===0&&!circuit.some(e=>e.type.includes('error')));
const checkerCorrection=read('native-checker-corrections.json');
check('Native checker geometry correction is documented and matches both installed modules',checkerCorrection.modules.length===2&&!checkerCorrection.diagnosticsSuppressed&&!checkerCorrection.clearanceLimitsChanged&&checkerCorrection.modules.every(m=>['0.0.277','0.0.278'].includes(m.version)&&m.patchedModuleSha256===sha(m.file)));
check('Copper audit matches the delivered circuit',copper.circuitJsonSha256===sourceSha&&copper.tracks===circuit.filter(e=>e.type==='pcb_trace').length&&copper.vias===circuit.filter(e=>e.type==='pcb_via').length);
const status=read('engineering-status.json');
check('Review status matches the circuit',status.circuitJsonSha256===sourceSha&&status.fullyConnectedNets===netCount);
const fabrication=read('fabrication-export-status.json'),fabAudit=read('fabrication-file-audit.json');
check('Fabrication files use the current circuit',fabrication.circuitJsonSha256===sourceSha);
for(const f of fabrication.files)check(`Fabrication checksum: ${f.file}`,sha(`output/review-fabrication/${f.file}`)===f.sha256);
check('Routed aperture, drill and assembly exports passed',fabAudit.status==='passed'&&fabAudit.closedProfileContours===2&&fabAudit.cutoutSemicircles===2&&fabAudit.nonplatedDrills===6&&fabAudit.assemblyRows===assemblyCount);
check('Fiducials have 2 mm mask openings and no paste',fabAudit.fiducialMaskOpenings===3&&fabAudit.fiducialPasteOpenings===0);
let drc={violations:[]};
if(!tscircuitOnly){
const kicad=read('kicad/export-status.json'),parity=read('kicad/reports/native-parity.json');
drc=read('kicad/reports/drc.json');
const erc=read('kicad/reports/erc.json');
check('KiCad uses the current circuit',kicad.sourceSha256===sourceSha&&kicad.pcbItems===parts.length&&kicad.nets===netCount);
check('KiCad pin, net and layer parity passed',parity.status==='passed'&&parity.electricalParity&&parity.routingComplete);
check('KiCad mounting keepouts match the source',kicad.mountingRuleAreas===6&&parity.mountingRuleAreasChecked===6);
check('KiCad preserves all three fiducial mask openings',parity.fiducialMaskOpeningsChecked===3);
check('KiCad has no errors or disconnected items',!drc.violations.some(v=>v.severity==='error')&&drc.unconnected_items.length===0);
check('All ten native schematic sheets pass ERC',erc.sheets.length===10&&erc.sheets.every(s=>s.violations.length===0));
}
const browser=read('browser-audit.json'),model=fs.readFileSync('output/space-octopus.glb');
check('Offline 2D and 3D browser checks passed',browser.passed&&browser.twoDimensional.passed&&browser.threeDimensional.passed&&browser.pageErrors.length===0);
check('3D preview uses the delivered GLB',browser.threeDimensional.modelSha256===sha('output/space-octopus.glb'));
check('Self-contained GLB is complete',model.toString('ascii',0,4)==='glTF'&&model.readUInt32LE(4)===2&&model.readUInt32LE(8)===model.length);

const models=read('3d-status.json'),mount=read('motor-mount-audit.json'),simulation=read('simulation/audit.json'),packages=read('package-review.json');
check('All populated component models are present',models.cadComponents===assemblyCount&&models.withStepModel===assemblyCount&&models.placeholderCount===0&&models.sourceCircuitSha256===sourceSha);
check('Motor model and lead clearances passed',mount.status==='passed'&&mount.sourceModelSha256===sha('output/space-octopus.glb')&&mount.checks.every(c=>c.passed));
check('Extracted analog simulations match this circuit',simulation.status==='passed'&&simulation.sourceSha256===sourceSha&&simulation.benches.length===10&&simulation.checks.length===21&&simulation.checks.every(c=>c.passed));
check('Package and MCU pin capture review passed',packages.status==='passed'&&packages.independentlyComparedMcuPins===64);
const targeted=read('bulk-watchdog-audit.json');
check('Bulk and watchdog amendment matches this circuit',targeted.status==='passed'&&targeted.sourceCircuitSha256===sourceSha&&targeted.checks.every(c=>c.passed));
check('Rendered silkscreen passed',read('silkscreen-rendered-audit.json').status==='passed');
const signalPaths=read('signal-path-review.json'),kelvin=read('kelvin-audit.json');
check('All signal paths were measured from this circuit',signalPaths.status==='measured'&&signalPaths.circuitJsonSha256===sourceSha);
check('All six Kelvin branches passed on this circuit',kelvin.status==='passed'&&kelvin.branches.length===6&&kelvin.branches.every(b=>b.passed)&&kelvin.circuitJsonSha256===sourceSha);

const bounds=browser.threeDimensional.bounds;
check('3D model has the nominal motor diameter',Math.abs(bounds.max[0]-bounds.min[0]-112)<.01);
for(const [file,pages] of [['Space_Octopus_RevA_Schematics.pdf',9],['Motor112_PCB_Interface.pdf',1],['Motor112_Mounting_Concept.pdf',1],...(!tscircuitOnly?[['kicad/SpaceOctopus-schematics.pdf',10]]:[])]){
 const info=spawnSync('pdfinfo',[`output/${file}`],{encoding:'utf8'});
 check(`${file}: ${pages} PDF pages`,info.status===0&&Number(info.stdout.match(/^Pages:\s+(\d+)/m)?.[1])===pages);
}
if(!tscircuitOnly){
const step=fs.readFileSync('output/Space_Octopus_RevA_Assembly.step','utf8');
check('Assembly STEP file is complete',step.startsWith('ISO-10303-21;')&&step.trimEnd().endsWith('END-ISO-10303-21;'));
}
const warningCounts={};for(const w of drc.violations)warningCounts[w.type]=(warningCounts[w.type]??0)+1;
const report={status:'passed',circuitJsonSha256:sourceSha,fullyConnectedNets:netCount,nativeTscircuitErrors:0,kicadErrors:0,kicadUnconnectedItems:0,kicadWarnings:warningCounts,checks,allTscircuitFeaturesUsed:false,allApplicableBoardWorkflowsCovered:true,fabricationReady:false,limitations:['Native autorouters did not finish; the verified copper is replayed through the custom routing API.',`${drc.violations.filter(v=>v.severity==='warning').length} KiCad warning findings are recorded in the delivered DRC report.`,'Ten extracted analog benches passed; full inverter, firmware, electromagnetic and thermal qualification is not completed.','Selected provisional packages, current/temperature capability and motor axial fit require qualification.']};
if(tscircuitOnly){
 delete report.kicadErrors;delete report.kicadUnconnectedItems;delete report.kicadWarnings;
 report.stage='tscircuit complete — KiCad continuation awaiting approval';
 report.kicadContinuation='Existing native files are intermediate snapshots; excluded from this stage.';
 report.limitations=report.limitations.filter(s=>!s.includes('KiCad warning'));
 const nesting=read('gerber-ordering-audit.json');
 check('Nested Gerber copper polarity regression passed',nesting.status==='passed'&&nesting.adapterSha256===sha('scripts/gerber-input.mjs'));
 report.checks=checks;
}
fs.writeFileSync(tscircuitOnly?'output/tscircuit-completion-audit.json':'output/delivery-audit.json',JSON.stringify(report,null,2)+'\n');
console.log(`Delivery audit passed: ${checks.length} checks; ${netCount}/${netCount} nets; zero native tscircuit errors.${tscircuitOnly?' KiCad continuation deferred.':' Native KiCad checks passed; warnings retained.'}`);
