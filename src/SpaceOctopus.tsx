import React from 'react';
import {SavedCopperPour} from './SavedCopperPour';
import {ImportedFootprint} from './Footprint';
import {geometry,circularOutline} from './geometry';
import {parts,footprints,placement,sheets,sheetNotes,electricalValue,type Part} from './design';
import {routingPhase} from './routing';
import cadModels from '../data/cad-models.json';
import kelvinRouting from '../data/kelvin-routing.json';
import silkPlan from '../data/silkscreen-plan.json';
import {pinAttributesFor} from './pin-attributes';
import {routingRules,groundPlaneRules,groundPlaneLayers,busCapacitorAntipadRadiusMm,hasSavedRouting,savedRoutingAlgorithm,savedVias} from './saved-routing';

/** Physical pad numbers always match the selected footprint, including EPs.
 * Semiconductors use explicit pin boxes: native MOSFET pin order differs from
 * CSD19536KTT. This preserves G=1, D/tab=2, S=3 in every export.
 */
function Component({part:p,index,chipIndex}:{part:Part;index:number;chipIndex:number}) {
 const fp=footprints[p.footprint]; const loc=placement[p.ref];
 const major=p.kind==='chip'||p.kind==='connector';
 const maxPins=Math.ceil(Object.keys(p.pins).length/2);
 const schX=major ? -32+(chipIndex%5)*16 : -34+(index%9)*8;
 const schY=major ? 17-Math.floor(chipIndex/5)*14 : -10-Math.floor(index/9)*6;
 const footprint=<ImportedFootprint data={fp} refdes={p.ref} hideReference={p.kind==='hole'}/>;
 const connections=Object.fromEntries(Object.entries(p.pins).filter(([,n])=>n!==null).map(([pin,net])=>[`pin${pin}`,`net.${net}`]));
 const omitAssembly=p.dnp||p.assembly==='wire-termination';
 const cadModel=omitAssembly||p.ref==='JP701'||['hole','fiducial','testpoint'].includes(p.kind)?null:(cadModels as Record<string,any>)[p.footprint];
 const common={name:p.ref,footprint,cadModel,pinAttributes:pinAttributesFor(p),pcbX:loc.x,pcbY:loc.y,pcbRotation:loc.rotation,layer:loc.layer,schX,schY,connections,doNotPlace:omitAssembly};
 if(p.kind==='resistor')return <resistor {...common} resistance={electricalValue(p.value)} />;
 if(p.kind==='capacitor'&&!p.pinLabels['1'])return <capacitor {...common} capacitance={electricalValue(p.value)} />;
 return <chip {...common} manufacturerPartNumber={p.mpn} displayName={p.value}
  pinLabels={Object.fromEntries(Object.entries(p.pins).map(([pin,net])=>[`pin${pin}`,`${(p.pinLabels[pin]??(net===null?'NC':'PIN')).replace(/\+/g,'PLUS').replace(/-/g,'MINUS').replace(/[^A-Za-z0-9_]/g,'_')}_${pin}`]))}
  noConnect={Object.entries(p.pins).filter(([,net])=>net===null).map(([pin])=>`pin${pin}`)}
  noSchematicRepresentation={['hole','fiducial'].includes(p.kind)}
  schWidth={major ? (maxPins>20?7:4):1.8} schHeight={Math.max(1.2,maxPins*0.5+0.5)} />
}

export default function SpaceOctopus({routing=true,useSavedRoutes=true,groundPlane=true}:{routing?:boolean;useSavedRoutes?:boolean;groundPlane?:boolean}={}) {
 const nets=[...new Set(parts.flatMap(p=>Object.values(p.pins).filter((n):n is string=>n!==null)))].sort();
 const replay=hasSavedRouting&&useSavedRoutes;
 let boardInstance:any;
 const attachBoard=(board:any)=>{boardInstance=board;if(board&&replay&&groundPlane&&!board._savedPlanesAdded){board._savedPlanesAdded=true;for(const [layer,net] of [...groundPlaneLayers.map(l=>[l,'GND']),['inner2','VBUS']])board.add(new SavedCopperPour({layer:layer as any,connectsTo:`net.${net}`}));}};
 return <board {...({ref:attachBoard} as any)} name="SpaceOctopusCircularDraft" width={geometry.outerDiameterMm} height={geometry.outerDiameterMm} outline={circularOutline} thickness={1.6} layers={4}
  routingDisabled={!routing} routeRemaining={true} autorouter={{local:true,traceClearance:0.2,allowViaInPad:true,...(replay?{algorithmFn:(input:any)=>savedRoutingAlgorithm(input,boardInstance.root.db.toArray())}:{})}} autorouterEffortLevel="5x"
  {...routingRules}
  schLayout={{layoutMode:'none'}} schAutoLayoutEnabled={false}
  schTraceAutoLabelEnabled schMaxTraceDistance={0.01}>
  {nets.map(n=><React.Fragment key={n}><net name={n} routingPhaseIndex={replay?undefined:routingPhase(n,nets)} isGroundNet={n==='GND'} nominalTraceWidth={0.25} isPowerNet={['VBUS','V12','V5','V3V3','VDDA3V3','REF25','ENC12'].includes(n)}/></React.Fragment>)}
  {replay&&savedVias.map((v,i)=><React.Fragment key={`saved_via_${i}`}><via name={`SV${i+1}`} pcbX={v.x} pcbY={v.y} holeDiameter={v.hole} outerDiameter={v.diameter} fromLayer="top" toLayer="bottom" connectsTo={`net.${v.net}`} netIsAssignable={false}/></React.Fragment>)}
  {!replay&&[...new Set(nets.map(n=>routingPhase(n,nets)))].map(i=><React.Fragment key={i}><autoroutingphase phaseIndex={i} name={`stage_${i}`} /></React.Fragment>)}
  {sheets.map((sheet,s)=>{
   let small=0,major=0;
   return <React.Fragment key={sheet}><schematicsheet name={sheet} sheetIndex={s} sheetWidth={850} sheetHeight={650}>
    <schematictext schX={-40} schY={29} text={`SPACE OCTOPUS / ${sheet.replace('_',' ')}`} fontSize={0.9} anchor="left"/>
    <schematictext schX={-40} schY={27.5} text={sheetNotes[s]} fontSize={0.42} anchor="left"/>
    <schematictext schX={-40} schY={-31} text="REV A / ENGINEERING DRAFT / SEE COPPER AUDIT / PACKAGE AND SYSTEM VALIDATION PENDING" fontSize={0.38} anchor="left"/>
    {parts.filter(p=>p.sheet===sheet).map(p=><Component key={p.ref} part={p} index={small+=p.kind==='chip'||p.kind==='connector'?0:1} chipIndex={p.kind==='chip'||p.kind==='connector'?major++:0}/>)}
   </schematicsheet></React.Fragment>
  })}
  {parts.filter(p=>p.sheet==='Mechanical').map(p=><Component key={p.ref} part={p} index={0} chipIndex={0}/>)}
  {parts.filter(p=>/^H\d+$/.test(p.ref)).map(p=><React.Fragment key={`hardware_${p.ref}`}><keepout shape="rect" pcbX={placement[p.ref].x} pcbY={placement[p.ref].y} width={geometry.mounting.keepoutDiameterMm} height={geometry.mounting.keepoutDiameterMm} layers={['top','inner1','inner2','bottom']} excludeRefs={[`.${p.ref}`]}/></React.Fragment>)}
  {groundPlane&&parts.filter(p=>/^H\d+$/.test(p.ref)).map(p=><React.Fragment key={`plane_hardware_${p.ref}`}><keepout shape="rect" pcbX={placement[p.ref].x} pcbY={placement[p.ref].y} width={geometry.mounting.keepoutDiameterMm+2*(geometry.mounting.copperKeepoutGapMm+0.01)} height={geometry.mounting.keepoutDiameterMm+2*(geometry.mounting.copperKeepoutGapMm+0.01)} layers={['inner1','inner2']} allowTraces allowPlacements warningOnly excludeRefs={[`.${p.ref}`]}/></React.Fragment>)}
  {(geometry.centralOpeningDiameterMm ?? 0)>0 && <cutout shape="circle" pcbX={0} pcbY={0} radius={geometry.centralOpeningDiameterMm!/2}/>}
  {groundPlane&&!replay&&groundPlaneLayers.map(layer=><React.Fragment key={`ground_${layer}`}><copperpour {...groundPlaneRules} layer={layer} connectsTo="net.GND"/></React.Fragment>)}
  {groundPlane&&!replay&&<copperpour {...groundPlaneRules} layer="inner2" connectsTo="net.VBUS"/>}
  {groundPlane&&parts.filter(p=>/^C[1-4]$/.test(p.ref)).map(p=><React.Fragment key={`bus_cap_antipad_${p.ref}`}><keepout shape="circle" pcbX={placement[p.ref].x} pcbY={placement[p.ref].y} radius={busCapacitorAntipadRadiusMm} layers={['inner1']} allowTraces allowPlacements warningOnly/></React.Fragment>)}
  {groundPlane&&kelvinRouting.branches.flatMap(b=>b.isolateFromGroundPlaneAt).map((p,i)=><React.Fragment key={`kelvin_antipad_${i}`}><keepout shape="circle" pcbX={p.x} pcbY={p.y} radius={p.radius} layers={['inner1']} allowTraces allowPlacements warningOnly/></React.Fragment>)}
  {silkPlan.enabled?(<>
   {(silkPlan.texts as any[]).map((t,i)=><React.Fragment key={`silk_text_${i}`}><silkscreentext text={t.text} pcbX={t.x} pcbY={t.y} fontSize={t.fontSize} layer={t.layer}/></React.Fragment>)}
   {(silkPlan.paths as any[]).map((p,i)=><React.Fragment key={`silk_path_${i}`}><silkscreenpath route={p.route} strokeWidth={p.strokeWidth} layer={p.layer}/></React.Fragment>)}
  </>):<>
   <silkscreentext text="SPACE OCTOPUS / ROUND" pcbX={0} pcbY={geometry.outerDiameterMm*0.34375} fontSize={0.8}/>
   <silkscreentext text={geometry.diameterConfirmed ? `D${geometry.outerDiameterMm} / 48V` : `D${geometry.outerDiameterMm} PREVIEW / FIT PENDING`} pcbX={0} pcbY={-geometry.outerDiameterMm*0.3046875} fontSize={0.8}/>
  </>}
 </board>;
}
