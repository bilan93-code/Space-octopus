import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const sourcePath='output/space-octopus.circuit.json';
const sourceSha=()=>createHash('sha256').update(fs.readFileSync(sourcePath)).digest('hex');
const circuitJsonSha256=sourceSha();
const checks=[
 ['copper geometry','python',['scripts/check-copper.py']],
 ['load-current copper backbone','python',['scripts/check-power-backbone.py']],
 ['drill web spacing','python',['scripts/check-drills.py']],
 ['electrical capture','node',['scripts/check-design.mjs']],
 ['rendered capture and native DRC','node',['scripts/check-rendered.mjs']],
 ['assembly envelopes','python',['scripts/check-assembly.py']],
 ['local bypass and converter placement','python',['scripts/check-local-layout.py']],
 ['Kelvin pickup isolation','python',['scripts/check-kelvin.py']],
 ['Kelvin fault detection','python',['scripts/check-kelvin-mutations.py','output/space-octopus.circuit.json']],
 ['motor dimensions','node',['scripts/check-motor-interface.mjs']],
 ['electrical mutations','node',['scripts/check-mutations.mjs']],
 ['mounting and through-hole copper','node_modules/.bin/tsx',['scripts/check-mounting-render.tsx']],
 ['copper mutations','python',['scripts/check-copper-mutations.py']],
 ['package pin capture','node',['scripts/review-packages.mjs']],
 ['bulk capacitor and watchdog manufacturer review','python',['scripts/check-bulk-watchdog.py']],
 ['nominal analog simulations','node',['scripts/simulate-analog.mjs']],
 ['motor body and lead clearance','node',['scripts/check-motor-mount.mjs']],
 ['rendered silkscreen','python',['scripts/check-silkscreen.py']],
];
const retry=process.argv.includes('--retry-failed');
const previous=retry?JSON.parse(fs.readFileSync('output/validation-results.json')):null;
if(retry){
 const previousSha=previous.circuitJsonSha256??JSON.parse(fs.readFileSync('output/copper-audit.json')).circuitJsonSha256;
 if(previousSha!==circuitJsonSha256||fs.statSync('output/validation-results.json').mtimeMs<fs.statSync(sourcePath).mtimeMs||previous.checks.length!==checks.length)throw new Error('Cannot reuse checks from a changed circuit. Run all checks.');
}
const results=retry?previous.checks:[];
for(const [name,cmd,args] of checks){
 if(retry&&results.find(r=>r.name===name)?.passed)continue;
 const r=spawnSync(cmd,args,{encoding:'utf8',maxBuffer:4*1024*1024});console.log(`${name}: ${r.status===0?'passed':'failed'}`);if(r.stdout)console.log(r.stdout.trim());if(r.stderr)console.error(r.stderr.trim().slice(0,2000));
 const result={name,passed:r.status===0,exitCode:r.status,error:r.error?.message};const index=results.findIndex(a=>a.name===name);if(index>=0)results[index]=result;else results.push(result);
}
if(sourceSha()!==circuitJsonSha256)throw new Error('Circuit changed during validation.');
fs.writeFileSync('output/validation-results.json',JSON.stringify({allPassed:results.every(r=>r.passed),circuitJsonSha256,fabricationReady:false,checks:results},null,2)+'\n');
process.exitCode=results.every(r=>r.passed)?0:1;
