import React from 'react';
import type {PlatedHole} from '@tscircuit/core';
import type {Footprint} from './design';
import {geometry} from './geometry';
import silkPlan from '../data/silkscreen-plan.json';
// The core otherwise pastes both ends of every plated barrel in a mixed SMT
// package. These four filled heat-transfer holes are not solder terminals.
function suppressThermalDrillPaste(hole:PlatedHole|null) {
 if(hole)hole._getIsSmt=()=>false;
}
/** Instantiate converted pads as primitives. The current core does not inflate
 * footprint.circuitJson; explicit children preserve pad geometry and hints. */
export function ImportedFootprint({data,refdes,hideReference=false}:{data:Footprint;refdes:string;hideReference?:boolean}) {
 // The NPTH land is the drilled hole. Fastener clearance is a separate copper
 // keepout; its reservation can extend past the physical board edge.
 const mounting=/^H\d+$/.test(refdes);
 const r=geometry.mounting.holeDiameterMm/2;const b=mounting?[-r,-r,r,r]:data.box;
 return <footprint>
 {refdes==='U2'&&[-1.37,0,1.37].flatMap(x=>[-1.37,0,1.37].map(y=>
   <solderpaste key={x+','+y} shape="rect" pcbX={x} pcbY={y} width={1.17} height={1.17} layer="top"/>
 ))}
 {refdes==='U13'&&<>
   <solderpaste shape="rect" pcbX={0} pcbY={0} width={1.34} height={1.55} layer="top"/>
   {[-.325,.325].flatMap(x=>[-1.337,1.337].map(y=>
    <solderpaste key={x+','+y} shape="rect" pcbX={x} pcbY={y} width={.23} height={.725} layer="top"/>
   ))}
 </>}
 {/^C[1-4]$/.test(refdes)
  ? <courtyardcircle pcbX={3.75} pcbY={0} radius={9.25} layer="top"/>
  : <courtyardrect pcbX={(b[0]+b[2])/2} pcbY={(b[1]+b[3])/2} width={b[2]-b[0]} height={b[3]-b[1]} layer="top"/>}
 {data.elements.map((raw,i)=>{
  // Converter schemas are a union; narrow by type before supplying props.
  const e=raw as Record<string,any>;const position={pcbX:e.x??0,pcbY:e.y??0};
  let child:React.ReactNode=null;
  if((refdes==='U2'||refdes==='U13')&&e.type==='pcb_smtpad'&&e.shape==='rect'){
   const exposed=e.port_hints.includes(refdes==='U2'?'41':'9');
   return <React.Fragment key={i}>
    <smtpad {...position} shape="rect" width={e.width} height={e.height} cornerRadius={e.corner_radius} portHints={e.port_hints} layer={e.layer??'top'} noSolderPaste/>
    {!exposed&&<solderpaste {...position} shape="rect" width={e.width} height={e.height} layer="top"/>}
   </React.Fragment>;
  }
  if(e.type==='pcb_smtpad')child=e.shape==='circle'
   ? <smtpad {...position} shape="circle" radius={e.radius??e.width/2} portHints={e.port_hints} layer="top" solderMaskMargin={refdes.startsWith('FID')?.5:undefined} noSolderPaste={/^(FID|TP|JP)/.test(refdes)}/>
   : <smtpad {...position} shape="rect" width={e.width} height={e.height} cornerRadius={e.corner_radius} portHints={e.port_hints} layer="top" noSolderPaste={/^(TP|JP)/.test(refdes)}/>;
  if(e.type==='pcb_plated_hole')child=e.shape==='circle'
   ? <platedhole {...(refdes==='U13'?{ref:suppressThermalDrillPaste}:{})} {...position} shape="circle" holeDiameter={e.hole_diameter} outerDiameter={e.outer_diameter} portHints={e.port_hints}/>
   : e.shape==='pill' ? <platedhole {...position} shape="pill" holeWidth={e.hole_width} holeHeight={e.hole_height} outerWidth={e.outer_width} outerHeight={e.outer_height} pcbRotation={e.ccw_rotation??0} portHints={e.port_hints}/>
   : <platedhole {...position} shape="circular_hole_with_rect_pad" holeDiameter={e.hole_diameter} rectPadWidth={e.rect_pad_width} rectPadHeight={e.rect_pad_height} rectBorderRadius={e.rect_border_radius??0} holeOffsetX={e.hole_offset_x??0} holeOffsetY={e.hole_offset_y??0} portHints={e.port_hints}/>;
  if(e.type==='pcb_hole')child=<hole {...position} diameter={e.hole_diameter}/>;
  if(!silkPlan.enabled&&e.type==='pcb_silkscreen_path')child=<silkscreenpath route={e.route} strokeWidth={e.stroke_width} layer="top"/>;
  if(!silkPlan.enabled&&e.type==='pcb_silkscreen_circle')child=<silkscreencircle pcbX={e.center.x} pcbY={e.center.y} radius={e.radius} strokeWidth={e.stroke_width} layer="top"/>;
  if(!silkPlan.enabled&&e.type==='pcb_silkscreen_text'&&e.text==='REF**'&&!hideReference)child=<silkscreentext pcbX={e.anchor_position.x} pcbY={e.anchor_position.y} text={refdes} fontSize={0.7} layer="top"/>;
  return <React.Fragment key={i}>{child}</React.Fragment>;
 })}</footprint>;
}
