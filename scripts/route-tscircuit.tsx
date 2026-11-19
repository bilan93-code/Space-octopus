import React from 'react';
import {Circuit} from 'tscircuit';
import SpaceOctopus from '../src/SpaceOctopus';
import fs from 'node:fs';
fs.mkdirSync('routing-work/tscircuit',{recursive:true});
const cacheDir='routing-work/tscircuit/cache';fs.mkdirSync(cacheDir,{recursive:true});
const localCacheEngine={getItem:(key:string)=>{const f=`${cacheDir}/${encodeURIComponent(key)}.json`;return fs.existsSync(f)?fs.readFileSync(f,'utf8'):null;},setItem:(key:string,value:string)=>{fs.writeFileSync(`${cacheDir}/${encodeURIComponent(key)}.json`,value);}};
const circuit=new Circuit({platform:{localCacheEngine}});let last=0;
circuit.on('autorouting:start',(e:any)=>{console.log('Routing started:',e.phaseName,e.connectionCount,'connections,',e.obstacleCount,'obstacles');fs.writeFileSync(`routing-work/tscircuit/${e.phaseName}.input.json`,JSON.stringify(e.simpleRouteJson,null,2));});
circuit.on('autorouting:end',(e:any)=>{console.log('Routing completed:',e.phaseName,e.simpleRouteJson?.traces?.length,'traces');fs.writeFileSync(`routing-work/tscircuit/${e.phaseName}.result.json`,JSON.stringify(e,null,2));fs.writeFileSync('routing-work/tscircuit/checkpoint.circuit.json',JSON.stringify(circuit.getCircuitJson()));});
circuit.on('autorouting:progress',(e:any)=>{if(Date.now()-last>5000){console.log('Routing progress:',JSON.stringify(e).slice(0,700));last=Date.now();}});
circuit.on('autorouting:error',(e:any)=>console.log('Routing error',JSON.stringify(e).slice(0,1000)));
circuit.on('solver:ended',(e:any)=>console.log('Solver ended:',e.solverName));
circuit.add(<SpaceOctopus useSavedRoutes={false}/>);
try {await circuit.renderUntilSettled();}catch(e){console.error('Render failed:',e);}
const j=circuit.getCircuitJson();fs.writeFileSync('routing-work/tscircuit/routed.circuit.json',JSON.stringify(j,null,2));
const counts:Record<string,number>={};for(const e of j)counts[e.type]=(counts[e.type]??0)+1;
console.log('Result:',JSON.stringify(counts));
console.log('Errors:',JSON.stringify(j.filter(e=>e.type.includes('error')).slice(0,12)));
