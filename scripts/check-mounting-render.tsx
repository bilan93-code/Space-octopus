import React from 'react';
import assert from 'node:assert/strict';
import {Circuit} from 'tscircuit';
import {ImportedFootprint} from '../src/Footprint';
import {parts,footprints,placement} from '../src/design';
import {geometry,circularOutline} from '../src/geometry';
import {getPlatedHolePolygon} from '@tscircuit/circuit-json-util';
const c=new Circuit();
c.add(<board width={112} height={112} outline={circularOutline} layers={4} routingDisabled>
 {parts.filter(p=>/^H\d+$/.test(p.ref)).map(p=><chip key={p.ref} name={p.ref} pcbX={placement[p.ref].x} pcbY={placement[p.ref].y} noSchematicRepresentation footprint={<ImportedFootprint data={footprints[p.footprint]} refdes={p.ref} hideReference/>}/>)}
 {parts.filter(p=>/^H\d+$/.test(p.ref)).map(p=><React.Fragment key={p.ref}><keepout shape="rect" pcbX={placement[p.ref].x} pcbY={placement[p.ref].y} width={geometry.mounting.keepoutDiameterMm} height={geometry.mounting.keepoutDiameterMm} layers={['top','inner1','inner2','bottom']} excludeRefs={[`.${p.ref}`]}/></React.Fragment>)}
 {['J1','J5'].map((ref,i)=>{const p=parts.find(p=>p.ref===ref)!;return <chip key={ref} name={ref} pcbX={i===0?-30:30} pcbY={0} noSchematicRepresentation footprint={<ImportedFootprint data={footprints[p.footprint]} refdes={ref}/>}/>;})}
</board>);
await c.renderUntilSettled();const j=c.getCircuitJson();
const errors=j.filter(e=>e.type.includes('error'));assert.deepEqual(errors,[]);
const holes=j.filter(e=>e.type==='pcb_hole'),keepouts=j.filter(e=>e.type==='pcb_keepout');
assert.equal(holes.length,6);assert.equal(keepouts.length,6);
for(const h of holes){assert('hole_diameter' in h);assert.equal(h.hole_diameter,4.5);}
for(const k of keepouts){assert.equal(k.shape,'rect');assert.equal(k.width,geometry.mounting.keepoutDiameterMm);assert.equal(k.layers.length,4);}
for(const p of j.filter(e=>e.type==='pcb_plated_hole'))assert(Number.isFinite(getPlatedHolePolygon(p).area()),'Through-hole copper polygon must have a finite area.');
console.log('Mounting regression: six Ø4.5 drills and separate 9.5 mm square hardware keepouts render inside the Ø112 board without placement errors.');
