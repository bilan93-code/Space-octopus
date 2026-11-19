import React from 'react';
import fs from 'node:fs';
import {Circuit} from 'tscircuit';
import SpaceOctopus from '../src/SpaceOctopus';
const c=new Circuit();(c as any).schematicDisabled=true;
c.add(<SpaceOctopus groundPlane/>);
let exception:string|undefined;
try{await c.renderUntilSettled();}catch(e){exception=String(e);console.error(e);}
const j=c.getCircuitJson();fs.writeFileSync('routing-work/plane-probe.circuit.json',JSON.stringify(j));
const pours=j.filter(e=>e.type==='pcb_copper_pour');console.log('Ground-plane probe:',{exception,pourCount:pours.length});
const errs=j.filter(e=>e.type.includes('error'));console.log('Native errors by type:',errs.reduce((a:Record<string,number>,e)=>(a[e.type]=(a[e.type]??0)+1,a),{}));
