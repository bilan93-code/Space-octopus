import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {Matrix4,Vector3,Quaternion,Box3} from 'three';
const file=process.argv[2]??'output/space-octopus.glb';const bytes=fs.readFileSync(file);const gltf=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
const placement=JSON.parse(fs.readFileSync('data/placement.json')),parts=['input-supplies-mcu-driver-inverter','sensing-fault-interfaces-brake','mechanical'].flatMap(n=>JSON.parse(fs.readFileSync(`data/${n}.json`)));
const by=Object.fromEntries(parts.map(p=>[p.ref,p]));const boxes={};
function walk(i,parent,ref){const n=gltf.nodes[i];const m=n.matrix?new Matrix4().fromArray(n.matrix):new Matrix4().compose(new Vector3(...(n.translation??[0,0,0])),new Quaternion(...(n.rotation??[0,0,0,1])),new Vector3(...(n.scale??[1,1,1])));m.premultiply(parent);if(by[n.name])ref=n.name;
 if(ref&&n.mesh!==undefined)for(const p of gltf.meshes[n.mesh].primitives){const a=gltf.accessors[p.attributes.POSITION];if(!a.min||!a.max)throw Error('Missing mesh bounds');const b=new Box3(new Vector3(...a.min),new Vector3(...a.max)).applyMatrix4(m);(boxes[ref]??=new Box3()).union(b);}
 for(const c of n.children??[])walk(c,m,ref);
}
for(const i of gltf.scenes[gltf.scene??0].nodes)walk(i,new Matrix4(),null);
const capZ=105,boardLowerZ=112,thickness=1.6,gap=boardLowerZ-capZ;
const components=Object.entries(boxes).map(([ref,b])=>{const face=placement[ref].layer;const motorProtrusion=Math.max(0,-.8-b.min.y);const protrusion=face==='bottom'?motorProtrusion:Math.max(0,b.max.y-.8);return {ref,face,modelBounds:{min:b.min.toArray(),max:b.max.toArray()},protrusionMm:protrusion,motorFacingProtrusionMm:motorProtrusion,motorClearanceMm:gap-motorProtrusion};});
const checks=[];const check=(name,passed)=>checks.push({name,passed});
check('Every connector faces away from the motor',parts.filter(p=>p.kind==='connector').every(p=>placement[p.ref].layer==='top'));
check('All five bulk capacitors face away from the motor',['C1','C2','C3','C4','C5'].every(r=>placement[r].layer==='top'));
check('Every modeled body and lead clears the nominal end-cap plane',components.every(c=>c.motorClearanceMm>=1));
const boltPoints=Array.from({length:6},(_,i)=>{const a=(30+60*i)*Math.PI/180;return [52*Math.cos(a),-52*Math.sin(a)];});
check('Modeled package bounds clear the six spacer envelopes',components.every(c=>{const b=c.modelBounds;if(b.max[1]<-7.8||b.min[1]>-.8)return true;return boltPoints.every(([x,z])=>Math.hypot(Math.max(b.min[0]-x,0,x-b.max[0]),Math.max(b.min[2]-z,0,z-b.max[2]))>=3.5);}));
check('Shaft and locknut fit inside the proposed aperture',28>19+2);
check('Bare solder jumper has no invented component body',!boxes.JP701);
const maximumOutwardProtrusionMm=Math.max(...components.map(c=>Math.max(0,c.modelBounds.max[1]-.8)));
const motorFacing=[...components].sort((a,b)=>a.motorClearanceMm-b.motorClearanceMm);
const report={status:checks.every(c=>c.passed)?'passed':'failed',sourceModel:file,sourceModelSha256:createHash('sha256').update(bytes).digest('hex'),maximumOutwardProtrusionMm,capToHighestModeledPartMm:gap+thickness+maximumOutwardProtrusionMm,provisionalGapMm:gap,capEndZMm:capZ,originalBoltHeadEndZMm:109,shaftEndZMm:120,pcbMotorFacingZMm:boardLowerZ,pcbOutwardZMm:boardLowerZ+thickness,shaftProjectionAbovePcbMm:120-boardLowerZ-thickness,minimumModeledMotorClearanceMm:motorFacing[0]?.motorClearanceMm,checks,components,assemblyFitVerified:false,limitations:['The 7 mm motor-to-PCB gap is provisional; enclosure and plug service space are not supplied.','The six mounting positions reuse structural end-cap bolt locations. Spacer bodies are a mounting concept; replacement studs, cap clamping, thread engagement, torque and insulation must be engineered before assembly.','Nominal STEP bodies and ideal motor envelopes omit solder, manufacturing tolerances, cable bends and vibration. Trim actual through-hole leads to <=2 mm on the motor-facing side.','Y1, U2, U13 and U21 are representative package bodies. F1 and F2 use a project-formed axial envelope. Confirm the actual lead form and standoff. Motor-facing parts need actual maximum-height confirmation.','Encoder support, axial sensing gap and 12-to-15 mm shaft adapter remain external mechanical design items. The 45 mm encoder cannot be assumed to pass through the proposed 28 mm PCB opening.']};
fs.writeFileSync('output/motor-mount-audit.json',JSON.stringify(report,null,2)+'\n');
fs.writeFileSync('output/component-heights.csv','Reference,Face,Model protrusion mm,Nominal cap clearance mm\n'+components.map(c=>[c.ref,c.face,c.protrusionMm,c.motorClearanceMm??''].join(',')).join('\n')+'\n');
console.log('Motor mount:',report.status,'minimum modeled cap clearance',report.minimumModeledMotorClearanceMm?.toFixed(2),'mm; mounting hardware remains provisional.');process.exitCode=report.status==='passed'?0:1;
